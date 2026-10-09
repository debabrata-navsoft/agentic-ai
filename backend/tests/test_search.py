from fastapi.testclient import TestClient

from app.search import DocumentStore, Index, Passage, chunk, stem, tokenize

FRUIT = """Apples grow on trees in cool climates. An apple tree can live for a hundred years.

Bananas grow in tropical regions. The banana plant is technically a giant herb, not a tree."""

PLANETS = """Mars is the fourth planet from the sun. Its red colour comes from iron oxide dust.

Jupiter is the largest planet. It has a giant storm called the Great Red Spot."""


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("The kings were loving apples") == ["king", "lov", "apple"]
    assert stem("glass") == "glass"
    assert stem("stories") == stem("story") and stem("boxes") == stem("box")


def test_chunk_respects_size_and_keeps_all_text():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(10))
    chunks = chunk(text, size=400)
    assert all(len(c) <= 400 for c in chunks)
    assert sum(c.count("Paragraph") for c in chunks) == 10


def test_bm25_ranks_rare_terms_higher():
    index = Index([Passage("a", 0, "red red red apple"), Passage("b", 1, "red storm on jupiter")])
    # "jupiter" appears in one passage, so it outweighs "red" which is everywhere.
    assert index.search("red jupiter")[0][0].doc == "b"
    assert index.search("nothing matches") == []


def test_answer_quotes_best_sentence(tmp_path):
    (tmp_path / "fruit.txt").write_text(FRUIT)
    (tmp_path / "planets.md").write_text(PLANETS)
    store = DocumentStore(tmp_path)

    res = store.search("which planet has the great red spot?")
    assert res["results"][0]["doc"] == "planets.md"
    assert "Great Red Spot" in res["answer"]
    assert "banana" not in res["answer"].lower()


def test_docs_api(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "CHECKPOINT", tmp_path / "model.pt")
    monkeypatch.setattr(main, "DOCS_DIR", tmp_path / "docs")
    with TestClient(main.app) as client:
        assert client.get("/api/docs").json() == []

        r = client.post("/api/docs", files={"file": ("../../fruit.txt", FRUIT.encode())})
        assert r.status_code == 201 and r.json()["name"] == "fruit.txt"  # path stripped
        assert (tmp_path / "docs" / "fruit.txt").exists()
        assert client.post("/api/docs", files={"file": ("x.exe", b"hi")}).status_code == 400

        res = client.post("/api/search", json={"query": "where do bananas grow"}).json()
        assert "tropical" in res["answer"] and res["results"][0]["doc"] == "fruit.txt"

        assert client.delete("/api/docs/fruit.txt").status_code == 204
        assert client.delete("/api/docs/fruit.txt").status_code == 404
        assert client.post("/api/search", json={"query": "bananas"}).json()["results"] == []


def test_picks_up_files_changed_on_disk(tmp_path):
    store = DocumentStore(tmp_path)
    assert store.search("bananas")["results"] == []

    (tmp_path / "fruit.txt").write_text(FRUIT)  # copied in by hand, not via add()
    assert store.search("bananas")["results"][0]["doc"] == "fruit.txt"

    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    docs = {d["name"]: d["passages"] for d in store.documents()}
    assert docs == {"broken.pdf": 0, "fruit.txt": 1}

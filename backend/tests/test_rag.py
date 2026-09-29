import hashlib
import json
import math
import re

import pytest

from app.rag import KnowledgeBase, UnsupportedFileError
from app.rag.chunking import chunk_text, extract_text
from conftest import run_tool

DIM = 256


def fake_embedder(texts: list[str]) -> list[list[float]]:
    """Hashed bag-of-words: deterministic and good enough to test retrieval ranking."""
    out = []
    for text in texts:
        vec = [0.0] * DIM
        for word in re.findall(r"[a-z]+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


@pytest.fixture
def kb(tmp_path, store):
    return KnowledgeBase(tmp_path / "chroma", store, embedder=fake_embedder)


def test_chunking_respects_size_and_overlaps():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(20))
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 500 + 50 + 2 for c in chunks)
    assert chunks[0][-50:] in chunks[1]  # overlap carried forward


def test_chunking_splits_huge_paragraph():
    assert len(chunk_text("x" * 2500, size=1000, overlap=0)) == 3


def test_extract_rejects_unknown_type():
    with pytest.raises(UnsupportedFileError):
        extract_text("image.png", b"\x89PNG")


def test_add_search_delete(kb, user):
    uid = user["id"]
    kb.add_document(uid, "pets.md", b"Our office dog is named Biscuit and loves tennis balls.")
    doc = kb.add_document(
        uid, "policy.txt",
        b"Employees get 24 days of paid vacation leave per year.\n\nRemote work is allowed on Fridays.",
    )

    hits = kb.search(uid, "how many vacation days do employees get", top_k=2)
    assert hits[0]["source"] == "policy.txt"
    assert "24 days" in hits[0]["text"]
    assert hits[0]["score"] > hits[-1]["score"] or len(hits) == 1

    assert {d["name"] for d in kb.list_documents(uid)} == {"pets.md", "policy.txt"}
    assert kb.delete_document(uid, doc["id"])
    assert all(h["source"] != "policy.txt" for h in kb.search(uid, "vacation", top_k=5))
    assert not kb.delete_document(uid, doc["id"])


def test_documents_are_private(kb, store, user):
    other = store.create_user("bob@example.com", "Bob", "unused-hash")
    doc = kb.add_document(user["id"], "secret.md", b"The launch code is 1234.")

    assert kb.search(other["id"], "launch code") == []
    assert kb.list_documents(other["id"]) == []
    assert not kb.delete_document(other["id"], doc["id"])
    assert kb.search(user["id"], "launch code")[0]["source"] == "secret.md"


def test_search_tool(kb, ctx):
    ctx.kb = kb
    out, is_error = run_tool(ctx, "search_knowledge_base", {"query": "anything"})
    assert not is_error and "empty" in out

    kb.add_document(ctx.user_id, "faq.md", b"The Wi-Fi password is hunter2.")
    out, is_error = run_tool(ctx, "search_knowledge_base", {"query": "wifi password"})
    assert not is_error
    assert json.loads(out)[0]["source"] == "faq.md"

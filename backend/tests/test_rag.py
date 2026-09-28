import asyncio
import hashlib
import json
import math
import re

import pytest

from app.rag import KnowledgeBase, UnsupportedFileError
from app.rag.chunking import chunk_text, extract_text
from app.store import Store
from app.tools import ToolContext, build_registry

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
def kb(tmp_path):
    return KnowledgeBase(tmp_path / "chroma", Store(tmp_path / "t.db"), embedder=fake_embedder)


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


def test_add_search_delete(kb):
    kb.add_document("pets.md", b"Our office dog is named Biscuit and loves tennis balls.")
    doc = kb.add_document(
        "policy.txt", b"Employees get 24 days of paid vacation leave per year.\n\nRemote work is allowed on Fridays."
    )

    hits = kb.search("how many vacation days do employees get", top_k=2)
    assert hits[0]["source"] == "policy.txt"
    assert "24 days" in hits[0]["text"]
    assert hits[0]["score"] > hits[-1]["score"] or len(hits) == 1

    assert {d["name"] for d in kb.list_documents()} == {"pets.md", "policy.txt"}
    assert kb.delete_document(doc["id"])
    assert all(h["source"] != "policy.txt" for h in kb.search("vacation", top_k=5))
    assert not kb.delete_document(doc["id"])


def test_search_tool(kb, tmp_path):
    ctx = ToolContext(store=Store(tmp_path / "t2.db"), workspace=tmp_path, kb=kb)
    tool = build_registry().get("search_knowledge_base")

    out, is_error = asyncio.run(tool.run({"query": "anything"}, ctx))
    assert not is_error and "empty" in out

    kb.add_document("faq.md", b"The Wi-Fi password is hunter2.")
    out, is_error = asyncio.run(tool.run({"query": "wifi password"}, ctx))
    assert not is_error
    assert json.loads(out)[0]["source"] == "faq.md"

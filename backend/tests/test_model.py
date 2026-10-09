import json
import math

import pytest
import torch
from fastapi.testclient import TestClient

from app.model import GPT, CharTokenizer, GPTConfig, load_checkpoint, save_checkpoint
from app.train import get_batch

TEXT = "hello world. the quick brown fox jumps over the lazy dog.\n" * 20


def tiny_model(tok: CharTokenizer) -> GPT:
    torch.manual_seed(0)
    return GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=16, n_layer=2, n_head=2, n_embd=32, dropout=0.0))


def test_tokenizer_roundtrip():
    tok = CharTokenizer.from_text(TEXT)
    assert tok.decode(tok.encode("the dog")) == "the dog"
    assert tok.unknown("hi Z!") == {"Z", "!"}


def test_untrained_loss_is_near_uniform():
    tok = CharTokenizer.from_text(TEXT)
    model = tiny_model(tok)
    x, y = get_batch(torch.tensor(tok.encode(TEXT)), 16, 8)
    _, loss = model(x, y)
    assert loss.item() == pytest.approx(math.log(tok.vocab_size), abs=0.3)


def test_training_reduces_loss():
    tok = CharTokenizer.from_text(TEXT)
    model = tiny_model(tok)
    data = torch.tensor(tok.encode(TEXT))
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    x, y = get_batch(data, 16, 16)
    first = model(x, y)[1].item()
    for _ in range(100):
        _, loss = model(*get_batch(data, 16, 16))
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert model(x, y)[1].item() < first / 2


def test_attention_is_causal():
    tok = CharTokenizer.from_text(TEXT)
    model = tiny_model(tok).eval()
    a = torch.tensor([tok.encode("hello world")])
    b = torch.tensor([tok.encode("hello fox  ")])
    # Changing later characters must not change predictions for earlier positions.
    assert torch.allclose(model(a)[0][:, :6], model(b)[0][:, :6], atol=1e-6)


def test_generate_crops_to_block_size():
    tok = CharTokenizer.from_text(TEXT)
    out = list(tiny_model(tok).generate(tok.encode("hello"), 40, top_k=5))
    assert len(out) == 40 and all(0 <= i < tok.vocab_size for i in out)


def test_api(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "CHECKPOINT", tmp_path / "model.pt")
    monkeypatch.setattr(main, "DOCS_DIR", tmp_path / "docs")
    with TestClient(main.app) as client:
        assert client.get("/api/model").json()["loaded"] is False
        assert client.post("/api/generate", json={"prompt": "hi"}).status_code == 503

        tok = CharTokenizer.from_text(TEXT)
        save_checkpoint(main.CHECKPOINT, tiny_model(tok), tok, step=0, val_loss=9.9)
        info = client.post("/api/model/reload").json()
        assert info["loaded"] and info["step"] == 0
        assert load_checkpoint(main.CHECKPOINT)[1].chars == tok.chars

        r = client.post("/api/generate", json={"prompt": "hello Z", "max_new_tokens": 10})
        events = [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]
        assert events[0] == {"notice": "Ignored characters the model never saw: Z"}
        assert len([e for e in events if "text" in e]) == 10
        assert events[-1] == {"done": True}

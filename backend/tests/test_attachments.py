import base64

import pytest

from app.attachments import Attachment, AttachmentError, user_content
from app.transcript import to_transcript

MB = 1024 * 1024


def att(name: str, media_type: str, data: bytes) -> Attachment:
    return Attachment(name=name, media_type=media_type, data=base64.b64encode(data).decode())


def test_plain_text_stays_a_string():
    assert user_content("hi", [], MB) == "hi"


def test_attachments_become_blocks_before_the_text():
    png = att("cat.png", "image/png", b"\x89PNG fake")
    pdf = att("report.pdf", "application/pdf", b"%PDF-1.7 fake")
    code = att("main.py", "", b"print('hi')")
    content = user_content("what is this?", [png, pdf, code], MB)

    assert [b["type"] for b in content] == ["image", "document", "document", "text"]
    assert content[0]["source"] == {"type": "base64", "media_type": "image/png", "data": png.data}
    assert content[1]["source"]["media_type"] == "application/pdf"
    assert content[2]["source"] == {"type": "text", "media_type": "text/plain", "data": "print('hi')"}
    assert content[2]["title"] == "main.py"
    assert content[3] == {"type": "text", "text": "what is this?"}


def test_attachment_only_message_has_no_text_block():
    content = user_content("  ", [att("a.txt", "text/plain", b"x")], MB)
    assert [b["type"] for b in content] == ["document"]


@pytest.mark.parametrize(
    "bad, error",
    [
        (Attachment(name="a.png", media_type="image/png", data="not base64!"), "base64"),
        (att("a.docx", "application/octet-stream", b"PK\x03\x04"), "unsupported"),
        (att("big.txt", "text/plain", b"x" * (MB + 1)), "larger than 1 MB"),
        (att("big.png", "image/png", b"x" * (5 * MB + 1)), "under 5 MB"),
    ],
)
def test_rejects_bad_attachments(bad, error):
    with pytest.raises(AttachmentError, match=error):
        user_content("hi", [bad], MB)


def test_transcript_shows_attachments():
    png = att("cat.png", "image/png", b"img")
    content = user_content("look", [png, att("notes.md", "text/markdown", b"# hi")], MB)
    [msg] = to_transcript([{"role": "user", "content": content}])

    assert msg["text"] == "look"
    assert msg["attachments"] == [
        {"name": "image", "media_type": "image/png", "url": f"data:image/png;base64,{png.data}"},
        {"name": "notes.md", "media_type": "text/plain"},
    ]

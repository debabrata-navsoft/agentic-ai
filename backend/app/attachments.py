"""Turn files attached to a chat message into Claude content blocks.

Images become `image` blocks and PDFs become base64 `document` blocks, so Claude reads them
natively (vision, PDF pages). Text and code files become plain-text `document` blocks.
The blocks are stored in session history like any other user content.
"""

import base64
import binascii
from pathlib import PurePath
from typing import Any

from pydantic import BaseModel, Field

from app.rag.chunking import TEXT_EXTENSIONS

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # the API's per-image limit
MAX_ATTACHMENTS = 10


class Attachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    media_type: str = Field(max_length=100)
    data: str  # base64, no data: prefix


class AttachmentError(ValueError):
    pass


def to_block(att: Attachment, max_bytes: int) -> dict[str, Any]:
    try:
        raw = base64.b64decode(att.data, validate=True)
    except (binascii.Error, ValueError):
        raise AttachmentError(f"{att.name}: not valid base64")
    if not raw:
        raise AttachmentError(f"{att.name}: file is empty")

    if att.media_type in IMAGE_TYPES:
        if len(raw) > MAX_IMAGE_BYTES:
            raise AttachmentError(f"{att.name}: images must be under 5 MB")
        return {"type": "image", "source": {"type": "base64", "media_type": att.media_type, "data": att.data}}

    if len(raw) > max_bytes:
        raise AttachmentError(f"{att.name}: file is larger than {max_bytes // (1024 * 1024)} MB")
    ext = PurePath(att.name).suffix.lower()
    if att.media_type == "application/pdf" or ext == ".pdf":
        source = {"type": "base64", "media_type": "application/pdf", "data": att.data}
    elif ext in TEXT_EXTENSIONS or att.media_type.startswith("text/"):
        source = {"type": "text", "media_type": "text/plain", "data": raw.decode("utf-8", errors="replace")}
    else:
        raise AttachmentError(f"{att.name}: unsupported file type. Attach images, PDFs, or text/code files.")
    return {"type": "document", "source": source, "title": att.name}


def user_content(text: str, attachments: list[Attachment], max_bytes: int) -> str | list[dict[str, Any]]:
    """A user message's `content`: plain text, or the attachment blocks followed by the text."""
    if not attachments:
        return text
    blocks = [to_block(a, max_bytes) for a in attachments]
    if text.strip():
        blocks.append({"type": "text", "text": text})
    return blocks

"""File-upload validation — pure, security-first (security-review §5).

We allow only PDF and DOCX, and validate **three** independent ways before a byte is
stored: the extension, the declared MIME type, AND the file's magic bytes (so a
renamed or content-type-spoofed file is rejected). Size is bounded by the caller.
This is pure logic so it is exhaustively unit-testable; the actual storage + the
malware-scan gate live in the service/worker.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# extension -> (allowed declared MIME types, magic-byte prefixes)
_ALLOWED: dict[str, tuple[frozenset[str], tuple[bytes, ...]]] = {
    ".pdf": (frozenset({"application/pdf"}), (b"%PDF",)),
    ".docx": (
        frozenset(
            {
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/zip",  # DOCX is a zip; some clients send this
                "application/octet-stream",
            }
        ),
        (b"PK\x03\x04",),  # zip local-file header
    ),
}


class InvalidUpload(Exception):
    """Raised when an upload fails validation. Mapped to 422 at the API layer."""


@dataclass(frozen=True)
class ValidatedUpload:
    extension: str
    mime_type: str
    byte_size: int
    sha256: str


def _extension(filename: str) -> str:
    name = filename.lower().strip()
    for ext in _ALLOWED:
        if name.endswith(ext):
            return ext
    raise InvalidUpload(f"file type not allowed (only {', '.join(_ALLOWED)})")


def validate_upload(
    *, filename: str, content_type: str, data: bytes, max_bytes: int
) -> ValidatedUpload:
    if not data:
        raise InvalidUpload("empty file")
    if len(data) > max_bytes:
        raise InvalidUpload(f"file exceeds maximum size of {max_bytes} bytes")

    ext = _extension(filename)
    allowed_mimes, magic_prefixes = _ALLOWED[ext]

    declared = (content_type or "").split(";")[0].strip().lower()
    if declared not in allowed_mimes:
        raise InvalidUpload(f"declared content-type {declared!r} does not match {ext}")

    if not any(data.startswith(p) for p in magic_prefixes):
        # The bytes don't look like the claimed type — reject a spoofed/renamed file.
        raise InvalidUpload(f"file contents are not a valid {ext}")

    return ValidatedUpload(
        extension=ext,
        # Store the canonical MIME for the extension, not the client's claim.
        mime_type=next(iter(allowed_mimes)),
        byte_size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )

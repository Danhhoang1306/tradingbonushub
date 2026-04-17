"""File upload validation — checks magic bytes to prevent MIME spoofing.

Also provides a size-check helper for upload endpoints.
"""
from fastapi import HTTPException


# Maximum upload sizes by category
MAX_UPLOAD_IMAGE = 10 * 1024 * 1024   # 10 MB for images/PDFs
MAX_UPLOAD_DATA  = 50 * 1024 * 1024   # 50 MB for Excel/CSV data files
MAX_UPLOAD_HTML  = 2 * 1024 * 1024    # 2 MB for HTML templates


def check_upload_size(data: bytes, max_bytes: int = MAX_UPLOAD_DATA,
                      label: str = "File") -> None:
    """Raise HTTPException 413 if data exceeds max_bytes."""
    if len(data) > max_bytes:
        size_mb = max_bytes / (1024 * 1024)
        raise HTTPException(413, f"{label} too large (max {size_mb:.0f} MB)")

# Magic byte signatures for allowed file types
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "image/webp"),       # WebP starts with RIFF....WEBP
    (b"<?xml", "image/svg+xml"),   # SVG as XML
    (b"<svg", "image/svg+xml"),    # SVG without XML declaration
    (b"%PDF", "application/pdf"),
]


def validate_file_type(data: bytes, claimed_mime: str) -> bool:
    """Validate that the file's magic bytes match the claimed MIME type.

    Returns True if the file content matches the claimed type.
    For SVG files, also checks for the <svg tag within the first 1KB.
    """
    if not data:
        return False

    # WebP special case: RIFF....WEBP
    if claimed_mime == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"

    # SVG special case: may start with BOM, whitespace, or XML declaration
    if claimed_mime == "image/svg+xml":
        # Check first 1KB for SVG indicators
        head = data[:1024]
        try:
            text = head.decode("utf-8", errors="ignore").strip().lower()
        except Exception:
            return False
        return "<svg" in text or "<!doctype svg" in text

    # Standard magic byte check
    for sig, mime in _SIGNATURES:
        if mime == claimed_mime and data[:len(sig)] == sig:
            return True

    return False

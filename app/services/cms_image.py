"""CMS image processing: resize, convert to WebP, organise by date."""
import io
import os
import uuid
from datetime import datetime
from pathlib import Path

UPLOAD_ROOT = Path("static/uploads")
MAX_WIDTH = 1920
THUMB_WIDTH = 400


def _year_month() -> tuple[str, str]:
    now = datetime.utcnow()
    return str(now.year), f"{now.month:02d}"


def save_upload(data: bytes, original_name: str, mime_type: str) -> tuple[str, str, int]:
    """Save uploaded file, optionally convert to WebP.

    Returns (filename_on_disk, public_url, final_size_bytes).
    """
    year, month = _year_month()
    folder = UPLOAD_ROOT / year / month
    folder.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex[:12]

    # Try image processing with Pillow
    if mime_type.startswith("image/") and mime_type != "image/svg+xml":
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            img = img.convert("RGB")

            # Resize if wider than MAX_WIDTH
            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                img = img.resize(
                    (MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS
                )

            filename = f"{uid}.webp"
            path = folder / filename
            img.save(path, "WEBP", quality=85, optimize=True)
            final_size = path.stat().st_size
        except Exception:
            # Pillow not available or error — save original
            ext = Path(original_name).suffix.lower() or ".bin"
            filename = f"{uid}{ext}"
            path = folder / filename
            path.write_bytes(data)
            final_size = len(data)
    else:
        ext = Path(original_name).suffix.lower() or ".bin"
        filename = f"{uid}{ext}"
        path = folder / filename
        path.write_bytes(data)
        final_size = len(data)

    public_url = f"/static/uploads/{year}/{month}/{filename}"
    return filename, public_url, final_size


def delete_upload(url: str) -> None:
    """Delete file from disk given its public URL."""
    if not url.startswith("/static/uploads/"):
        return
    rel = url.removeprefix("/static/")
    path = Path("static") / rel
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

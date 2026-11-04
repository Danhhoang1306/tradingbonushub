"""Upload ảnh vào thư viện (MediaFile). Chỉ PNG/JPEG/WEBP, xác minh bằng Pillow, tối đa 5MB."""
import io
import secrets

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import content
from app.config import config
from app.models import Banner, Broker, MediaFile, Post

MAX_BYTES = 5 * 1024 * 1024
FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


class UploadError(ValueError):
    pass


def has_file(upload: UploadFile | None) -> bool:
    return upload is not None and bool(upload.filename)


def save_image(db: Session, upload: UploadFile, alt: str = "") -> MediaFile:
    upload.file.seek(0)
    data = upload.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise UploadError("Ảnh vượt quá 5MB.")
    if not data:
        raise UploadError("File rỗng.")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise UploadError("File không phải ảnh hợp lệ.")
    if fmt not in FORMATS:
        raise UploadError("Chỉ nhận ảnh PNG, JPEG hoặc WEBP.")
    name = f"{secrets.token_hex(16)}.{FORMATS[fmt]}"
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    (config.upload_dir / name).write_bytes(data)
    media = MediaFile(path=f"/media/{name}", alt=alt.strip()[:255], width=width, height=height, size=len(data))
    db.add(media)
    db.flush()
    return media


def is_library_path(db: Session, path: str) -> bool:
    return bool(path) and db.scalar(select(MediaFile.id).where(MediaFile.path == path)) is not None


def used_text(db: Session) -> str:
    """Gộp mọi chỗ có thể tham chiếu ảnh. Tên file là hex ngẫu nhiên nên `path in used_text` là đủ chính xác.
    Gọi một lần rồi kiểm tra nhiều ảnh (trang Thư viện)."""
    parts = list(db.scalars(select(Broker.logo_path)))
    parts += [x for row in db.execute(select(Post.cover_path, Post.body_md)) for x in row]
    parts += list(db.scalars(select(Banner.image_path)))
    parts.append(content.media_paths_in_settings(db))
    return "\n".join(parts)


def is_in_use(db: Session, path: str) -> bool:
    return path in used_text(db)


def delete_file(media: MediaFile) -> None:
    name = media.path.rsplit("/", 1)[-1]
    target = (config.upload_dir / name)
    if target.parent.resolve() == config.upload_dir.resolve() and target.exists():
        target.unlink()

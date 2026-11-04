"""Upload ảnh: chỉ PNG/JPEG/WEBP thật, tối đa 5MB, tên file ngẫu nhiên, chặn xóa khi đang dùng."""
import io
import re
import os
from pathlib import Path

from PIL import Image

from conftest import errors_of, flash_code, make_broker
from app import content
from app.models import Broker, MediaFile


def image_bytes(fmt="PNG", size=(32, 20)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (25, 68, 223)).save(buf, format=fmt)
    return buf.getvalue()


def upload(admin, name, data, mime="image/png", alt="Ảnh thử"):
    return admin.post("/admin/media/upload", {"alt": alt}, files=[("files", (name, data, mime))])


def test_upload_valid_images(admin, db):
    for fmt, name, mime in (("PNG", "a.png", "image/png"), ("JPEG", "b.jpg", "image/jpeg"), ("WEBP", "c.webp", "image/webp")):
        assert upload(admin, name, image_bytes(fmt), mime).status_code == 303
    files = db.query(MediaFile).all()
    assert len(files) == 3
    m = files[0]
    assert m.width == 32 and m.height == 20 and m.alt == "Ảnh thử" and m.size > 0
    stored = Path(os.environ["UPLOAD_DIR"]) / m.path.rsplit("/", 1)[1]
    assert stored.exists() and re.fullmatch(r"/media/[0-9a-f]{32}\.png", m.path)
    assert {p.path.rsplit(".", 1)[1] for p in files} == {"png", "jpg", "webp"}
    r = admin.get(m.path)
    assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff"


def test_upload_rejects_fake_image(admin, db):
    r = upload(admin, "shell.png", b"<?php echo 'hi'; ?>")
    assert r.status_code == 400 and "không phải ảnh hợp lệ" in errors_of(r)["files"]
    r = upload(admin, "page.png", b"\x89PNG\r\n\x1a\n" + b"<html>fake</html>" * 10)
    assert r.status_code == 400
    assert db.query(MediaFile).count() == 0
    assert not any(Path(os.environ["UPLOAD_DIR"]).iterdir())


def test_upload_rejects_other_formats(admin, db):
    r = upload(admin, "a.gif", image_bytes("GIF"), "image/gif")
    assert r.status_code == 400 and "PNG, JPEG hoặc WEBP" in errors_of(r)["files"]
    assert db.query(MediaFile).count() == 0


def test_upload_rejects_large_file(admin, db):
    big = image_bytes() + b"\0" * (5 * 1024 * 1024)
    r = upload(admin, "big.png", big)
    assert r.status_code in (400, 413) and db.query(MediaFile).count() == 0


def test_upload_requires_file(admin):
    assert admin.post("/admin/media/upload", {"alt": "x"}).status_code == 400


def test_image_field_in_form_and_delete_guard(admin, db):
    r = admin.post("/admin/brokers/new", {"name": "Sàn Logo", "kind": "forex"},
                   files=[("logo_path_file", ("logo.png", image_bytes(), "image/png"))])
    assert r.status_code == 303
    k = db.query(Broker).one()
    m = db.query(MediaFile).one()
    assert k.logo_path == m.path
    admin.post(f"/admin/media/{m.id}/edit", {"alt": "Logo sàn"})
    db.expire_all()
    assert db.get(MediaFile, m.id).alt == "Logo sàn"
    assert admin.post(f"/admin/media/{m.id}/delete").status_code == 303
    r = admin.get("/admin/media")
    assert flash_code(r) == "media_in_use" and r.context["media"][0]["in_use"]
    assert db.query(MediaFile).count() == 1
    # gỡ khỏi sàn rồi mới xóa được
    k.logo_path = ""
    db.commit()
    admin.post(f"/admin/media/{m.id}/delete")
    assert db.query(MediaFile).count() == 0


def test_image_used_in_settings_blocks_delete(admin, db):
    upload(admin, "hero.png", image_bytes())
    m = db.query(MediaFile).one()
    admin.post("/admin/home/hero", {"headline": "H", "image_path": m.path})
    assert content.get(db, "hero")["image_path"] == m.path
    admin.post(f"/admin/media/{m.id}/delete")
    assert db.query(MediaFile).count() == 1


def test_image_field_rejects_fake_upload_and_foreign_path(admin, db):
    r = admin.post("/admin/brokers/new", {"name": "Sàn X", "kind": "forex"},
                   files=[("logo_path_file", ("x.png", b"not an image", "image/png"))])
    assert r.status_code == 400 and "logo_path" in errors_of(r)
    r = admin.post("/admin/brokers/new", {"name": "Sàn X", "kind": "forex", "logo_path": "https://evil.example/x.png"})
    assert r.status_code == 400 and "logo_path" in errors_of(r)
    make_broker(db, "Sàn Y")
    assert db.query(Broker).count() == 1

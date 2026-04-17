"""Tests for file upload magic byte validation."""
import pytest

from app.utils.file_validation import validate_file_type


class TestValidateFileType:
    """Verify magic byte checks for all supported MIME types."""

    def test_valid_png(self):
        # PNG magic bytes
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert validate_file_type(data, "image/png")

    def test_valid_jpeg(self):
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        assert validate_file_type(data, "image/jpeg")

    def test_valid_gif87a(self):
        data = b"GIF87a" + b"\x00" * 100
        assert validate_file_type(data, "image/gif")

    def test_valid_gif89a(self):
        data = b"GIF89a" + b"\x00" * 100
        assert validate_file_type(data, "image/gif")

    def test_valid_webp(self):
        data = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
        assert validate_file_type(data, "image/webp")

    def test_valid_svg_with_xml(self):
        data = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        assert validate_file_type(data, "image/svg+xml")

    def test_valid_svg_without_xml(self):
        data = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        assert validate_file_type(data, "image/svg+xml")

    def test_valid_pdf(self):
        data = b"%PDF-1.7\n" + b"\x00" * 100
        assert validate_file_type(data, "application/pdf")

    # ── Rejection cases ──────────────────────────────────────────────────────

    def test_empty_data(self):
        assert not validate_file_type(b"", "image/png")

    def test_wrong_mime_for_png(self):
        """PNG data with JPEG mime type should fail."""
        data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        assert not validate_file_type(data, "image/jpeg")

    def test_exe_disguised_as_png(self):
        """EXE file with PNG mime type should fail."""
        data = b"MZ" + b"\x00" * 100
        assert not validate_file_type(data, "image/png")

    def test_script_disguised_as_jpeg(self):
        """HTML/JS file with JPEG mime type should fail."""
        data = b"<script>alert('xss')</script>"
        assert not validate_file_type(data, "image/jpeg")

    def test_webp_wrong_magic(self):
        """RIFF without WEBP marker should fail."""
        data = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 100
        assert not validate_file_type(data, "image/webp")

    def test_svg_without_svg_tag(self):
        """Random XML without <svg> should fail."""
        data = b'<?xml version="1.0"?><html><body>not svg</body></html>'
        assert not validate_file_type(data, "image/svg+xml")

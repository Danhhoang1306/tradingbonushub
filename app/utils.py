import html
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

import markdown as md
import nh3

VN_TZ = timezone(timedelta(hours=7))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ALLOWED_TAGS = {"p", "br", "hr", "h2", "h3", "h4", "strong", "em", "b", "i", "u", "s", "blockquote", "code", "pre",
                "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td"}
ALLOWED_ATTRS = {"a": {"href", "title"}, "img": {"src", "alt", "title", "width", "height"}, "th": {"align"}, "td": {"align"}}


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def render_markdown(text: str) -> str:
    body = md.markdown(text or "", extensions=["tables", "sane_lists", "fenced_code"])
    # Trang đã có <h1>: giữ định dạng của tiêu đề nhập trong bài bằng cách đưa về h2..h4.
    body = re.sub(r"<(/?)h1\b", r"<\1h2", body)
    body = re.sub(r"<(/?)h[56]\b", r"<\1h4", body)
    return nh3.clean(body, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, url_schemes={"http", "https", "mailto"},
                     link_rel="noopener noreferrer nofollow")


def read_minutes(text: str) -> int:
    return max(1, math.ceil(len(re.findall(r"\w+", text or "")) / 200))


def slugify(text: str) -> str:
    for ch in "đĐÐð":  # các chữ D gạch ngang không tách được bằng NFKD (Ð U+00D0 hay gặp khi gõ hoặc dán)
        text = (text or "").replace(ch, "d")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower())[:120].strip("-")


def parse_date(value: str) -> date | None:
    """Nhận YYYY-MM-DD (input type=date) hoặc DD/MM/YYYY. Rỗng -> None. Sai -> ValueError."""
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(value)


def parse_float(value: str) -> float | None:
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(value)
    return number


def to_int(value: str) -> int | None:
    """Số nguyên dương từ chuỗi chữ số ASCII; khác thì None (tránh '²'.isdigit() == True)."""
    value = (value or "").strip()
    return int(value) if value.isascii() and value.isdigit() and len(value) < 12 else None


def mono_from_name(name: str) -> str:
    letters = slugify(name).replace("-", "") or re.sub(r"[\W_]", "", name or "")  # tên không Latin: lấy nguyên chữ
    return letters[:2].upper()[:2]


def plain_excerpt(markdown_text: str, limit: int = 160) -> str:
    """Đoạn chữ thuần đầu bài, dùng làm meta description khi bài không có tóm tắt."""
    text = html.unescape(nh3.clean(render_markdown(markdown_text), tags=set(), attributes={}))  # Jinja sẽ escape lúc in
    return " ".join(text.split())[:limit]


def as_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_vn(dt: datetime | None) -> datetime | None:
    """Datetime lưu trong DB là UTC không tz; đổi sang giờ Việt Nam để hiển thị."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(VN_TZ)

import html
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from itertools import product

import markdown as md
import nh3

VN_TZ = timezone(timedelta(hours=7))
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DAY_MONTH_RE = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?")

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


def _day_month(value: str, year: int) -> date | None:
    """DD/MM hoặc DD/MM/YYYY. Rỗng -> None. Sai -> ValueError."""
    if not value:
        return None
    m = DAY_MONTH_RE.fullmatch(value)
    if m is None:
        raise ValueError(value)
    return date(int(m[3] or year), int(m[2]), int(m[1]))


def parse_date_range(value: str, today: date) -> tuple[date | None, date | None]:
    """Ô "Chạy từ – đến" của thiết kế: `01/11 – 30/11`. Ngày từ thiếu năm là năm nay. Ngày đến thiếu năm là năm của
    ngày từ, nhỏ hơn ngày từ thì sang năm sau. Rỗng -> (None, None). Sai -> ValueError."""
    parts = re.split(r"\s*[–—-]\s*", (value or "").strip())
    if len(parts) > 2:
        raise ValueError(value)
    start = _day_month(parts[0], today.year)
    if len(parts) == 1 or not parts[1]:
        return start, None
    if start and parts[1].count("/") == 1:
        for year in (start.year, start.year + 1):
            try:
                end = _day_month(parts[1], year)
            except ValueError:  # gồm 29/02 của năm không nhuận
                continue
            if end >= start:
                return start, end
        raise ValueError(value)
    end = _day_month(parts[1], today.year)
    if start and end < start:
        raise ValueError(value)
    return start, end


def date_range_label(start: date | None, end: date | None, today: date) -> str:
    """Dạng ngắn nhất mà parse_date_range đọc lại đúng ngày đó, nên lưu lại không làm đổi giá trị."""
    if not start and not end:
        return ""

    def text(start_fmt: str, end_fmt: str) -> str:
        return f"{start.strftime(start_fmt) if start else ''} – {end.strftime(end_fmt) if end else ''}".strip()

    for start_fmt, end_fmt in product(("%d/%m", "%d/%m/%Y"), repeat=2):
        label = text(start_fmt, end_fmt)
        try:
            if parse_date_range(label, today) == (start, end):
                return label
        except ValueError:
            pass
    return text("%d/%m/%Y", "%d/%m/%Y")


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

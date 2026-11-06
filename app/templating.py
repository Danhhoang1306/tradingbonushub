"""Jinja: filter/helper dùng chung + render kèm flash."""
from datetime import date, datetime

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup

from app import content
from app.config import config
from app.models import KIND_LABELS
from app.security import FLASH_COOKIE, cookie_kwargs
from app.utils import render_markdown, to_vn, today_vn

templates = Jinja2Templates(directory=str(config.templates_dir))
# Production không nạp lại template từ đĩa: sửa file khi site đang chạy không được làm hỏng site.
templates.env.auto_reload = not config.is_production
env = templates.env

FLASH_MESSAGES = {
    "saved": ("success", "Đã lưu"),
    "created": ("success", "Đã thêm"),
    "deleted": ("success", "Đã xóa"),
    "toggled": ("success", "Đã cập nhật"),
    "sent": ("success", "Đã gửi email"),
    "uploaded": ("success", "Đã tải ảnh lên"),
    "logged_out": ("success", "Đã đăng xuất"),
    "compare_limit": ("error", "Chỉ được chọn tối đa 3 sàn để so sánh."),
    "media_in_use": ("error", "Ảnh đang được dùng, không thể xóa."),
    "not_allowed": ("error", "Tài khoản của bạn không có quyền thực hiện thao tác này."),
    "csrf": ("error", "Phiên làm việc đã hết hạn, vui lòng thử lại."),
    "self_delete": ("error", "Không thể xóa hoặc khóa chính tài khoản đang đăng nhập."),
    "no_recipients": ("error", "Không có người nhận phù hợp."),
    "send_failed": ("error", "Không gửi được email nào. Kiểm tra cấu hình SMTP rồi gửi lại từ bản nháp."),
    "send_partial": ("error", "Mới gửi được một phần. Bấm gửi lại để gửi tiếp cho người còn lại."),
    "too_long": ("error", "Nội dung quá dài."),
    "invalid_url": ("error", "Link phải bắt đầu bằng http:// hoặc https://"),
}

PLACEMENT_LABELS = {"after-bonus": "Sau Bonus mới nhất", "before-blog": "Trước Tin tức",
                    "rail-left": "Cột trái (hero)", "rail-right": "Cột phải (hero)"}
POST_STATUS_LABELS = {"draft": "Nháp", "published": "Đã đăng"}
SUBSCRIBER_STATUS_LABELS = {"pending": "Chờ xác nhận", "confirmed": "Đã xác nhận", "unsubscribed": "Đã hủy"}
ROLE_LABELS = {"admin": "Quản trị", "editor": "Biên tập"}
BANNER_STATE_LABELS = {"running": "Đang chạy", "paused": "Tạm dừng", "scheduled": "Chưa bắt đầu", "ended": "Đã kết thúc",
                       "no_link": "Thiếu link đích", "broker_hidden": "Sàn đang ẩn"}


def _as_date(value):
    if isinstance(value, datetime):
        return to_vn(value)
    return value


def date_vn(value) -> str:
    v = _as_date(value)
    return v.strftime("%d/%m/%Y") if isinstance(v, (date, datetime)) else ""


def short_date(value) -> str:
    v = _as_date(value)
    return v.strftime("%d/%m") if isinstance(v, (date, datetime)) else ""


def datetime_vn(value) -> str:
    v = _as_date(value)
    return v.strftime("%d/%m/%Y %H:%M") if isinstance(v, datetime) else date_vn(v)


def iso_date(value) -> str:
    return value.isoformat() if isinstance(value, date) else ""


def expiry_label(value) -> str:
    return short_date(value) if value else "Liên tục"


def login_day(value) -> str:
    v = _as_date(value)
    return "Hôm nay" if isinstance(v, datetime) and v.date() == today_vn() else date_vn(value)


def num(value) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def ctr(clicks, views) -> str:
    return f"{clicks / views * 100:.1f}%" if views else "—"


@pass_context
def type_label(ctx, type_id: str) -> str:
    site = ctx.get("site")
    labels = site["type_labels"] if site else content.type_labels(content.DEFAULTS)
    return labels.get(type_id, type_id)


def markdown_filter(text: str) -> Markup:
    return Markup(render_markdown(text))


env.filters.update(
    date_vn=date_vn, short_date=short_date, datetime_vn=datetime_vn, iso_date=iso_date, expiry_label=expiry_label,
    login_day=login_day,
    num=num, type_label=type_label, markdown=markdown_filter,
    placement_label=lambda v: PLACEMENT_LABELS.get(v, v), post_status_label=lambda v: POST_STATUS_LABELS.get(v, v),
    subscriber_status_label=lambda v: SUBSCRIBER_STATUS_LABELS.get(v, v), role_label=lambda v: ROLE_LABELS.get(v, v),
    kind_label=lambda v: KIND_LABELS.get(v, v), banner_state_label=lambda v: BANNER_STATE_LABELS.get(v, v),
)
env.globals.update(ctr=ctr)


def set_flash(response, code: str):
    response.set_cookie(FLASH_COOKIE, code, max_age=60, **cookie_kwargs())
    return response


def render(request: Request, name: str, context: dict, status_code: int = 200):
    code = request.cookies.get(FLASH_COOKIE)
    flash = None
    if code in FLASH_MESSAGES:
        kind, text = FLASH_MESSAGES[code]
        flash = {"kind": kind, "text": text, "code": code}
    ctx = {"flash": flash, **context}
    response = templates.TemplateResponse(request, name, ctx, status_code=status_code)
    if code:
        response.delete_cookie(FLASH_COOKIE, path="/")
    return response

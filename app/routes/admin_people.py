"""Quản trị khách: Người đăng ký (+ gửi email chiến dịch) và Tin nhắn liên hệ."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from app import content
from app.config import config
from app.mailer import build, send_email, send_many
from app.models import BONUS_TYPES, Campaign, ContactMessage, Subscriber, utcnow
from app.routes.admin_base import Admin, admin_api, admin_get, admin_post, done, get_or_404, render_admin, subtabs
from app.utils import to_int

router = APIRouter()

SUB_TABS = (("list", "Danh sách"), ("mail", "Gửi email"))
SUB_STATUS = (("all", "Tất cả"), ("confirmed", "Đã xác nhận"), ("pending", "Chờ xác nhận"), ("unsubscribed", "Đã hủy"))
MSG_TABS = (("all", "Tất cả"), ("unread", "Chưa đọc"))


def recipients(confirmed: list[Subscriber], audience: list[str]) -> list[Subscriber]:
    """Lọc người đã xác nhận theo audience. Audience rỗng = tất cả. Người không chọn sở thích nhận mọi email."""
    return [s for s in confirmed if not audience or not s.interests or set(s.interests) & set(audience)]


def confirmed_subscribers(db) -> list[Subscriber]:
    return list(db.scalars(select(Subscriber).where(Subscriber.status == "confirmed")))


def _valid_audience(values: list[str]) -> list[str]:
    return [x for x in dict.fromkeys(values) if x in BONUS_TYPES]


def _draft(db, campaign_id: int) -> Campaign:
    """Chỉ bản nháp mới mở lại/gửi được: chặn gửi trùng một chiến dịch đã gửi."""
    c = db.get(Campaign, campaign_id)
    if c is None or c.status != "draft":
        raise HTTPException(404)
    return c


def _subs_page(a: Admin, tab: str = "list", status: str = "all", q: str = "", aud: list[str] | None = None,
               mail_form: dict | None = None, status_code=200, **extra):
    db = a.db
    tab = tab if tab in dict(SUB_TABS) else "list"
    status = status if status in dict(SUB_STATUS) else "all"
    labels = content.type_labels(content.get_all(db))
    counts = dict(db.execute(select(Subscriber.status, func.count()).group_by(Subscriber.status)).all())
    stmt = select(Subscriber).order_by(Subscriber.created_at.desc(), Subscriber.id.desc())
    if status != "all":
        stmt = stmt.where(Subscriber.status == status)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Subscriber.email.ilike(like), Subscriber.name.ilike(like)))
    rows = [{"id": s.id, "name": s.name, "email": s.email, "interests": list(s.interests),
             "interest_labels": [labels.get(i, i) for i in s.interests], "status": s.status, "created_at": s.created_at,
             "confirmed_at": s.confirmed_at, "delete_url": f"/admin/subscribers/{s.id}/delete"}
            for s in db.scalars(stmt)] if tab == "list" else []
    mail = mail_form or {"subject": "", "body": "", "audience": _valid_audience(aud or []), "draft_id": None, "errors": {}}
    confirmed = confirmed_subscribers(db)
    campaigns = [{"id": c.id, "subject": c.subject, "audience_labels": [labels.get(i, i) for i in c.audience],
                  "status": c.status, "sent_count": c.sent_count, "sent_at": c.sent_at, "created_at": c.created_at,
                  "edit_url": f"/admin/subscribers?tab=mail&draft={c.id}" if c.status == "draft" else None}
                 for c in db.scalars(select(Campaign).order_by(Campaign.created_at.desc()).limit(20))]
    return render_admin(
        a, "admin/subscribers.html", "subscribers", "Người đăng ký", status_code,
        subtabs=subtabs("/admin/subscribers", SUB_TABS, tab), current_tab=tab, q=q, current_status=status,
        status_filters=[{"id": s, "label": label, "count": sum(counts.values()) if s == "all" else counts.get(s, 0),
                         "url": f"/admin/subscribers?tab=list&status={s}", "active": s == status} for s, label in SUB_STATUS],
        subscribers=rows,
        audience_options=[{"id": t, "label": labels[t], "selected": t in mail["audience"],
                           "count": len(recipients(confirmed, [t]))} for t in BONUS_TYPES],
        audience_count=len(recipients(confirmed, mail["audience"])), mail_form=mail | {
            "action": "/admin/subscribers/mail", "test_action": "/admin/subscribers/mail/test"},
        audience_count_url="/admin/subscribers/audience-count", campaigns=campaigns, **extra)


@router.get("/subscribers")
def subs_get(tab: str = "list", status: str = "all", q: str = "", aud: list[str] = Query([]),
             draft: int | None = None, a: Admin = Depends(admin_get)):
    if draft is not None:  # mở lại bản nháp vào form Gửi email
        c = _draft(a.db, draft)
        return _subs_page(a, "mail", mail_form={"subject": c.subject, "body": c.body, "audience": list(c.audience),
                                                "draft_id": c.id, "errors": {}})
    return _subs_page(a, tab, status, q, aud)


@router.get("/subscribers/audience-count")
def subs_audience_count(aud: list[str] = Query([]), a: Admin = Depends(admin_api)):
    """Số người nhận theo nhóm `aud` (lặp). Trống = tất cả người đã xác nhận."""
    return {"count": len(recipients(confirmed_subscribers(a.db), _valid_audience(aud)))}


@router.post("/subscribers/{sid}/delete")
def subs_delete(sid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, Subscriber, sid))
    a.db.commit()
    return done("/admin/subscribers", "deleted")


def _mail_input(a: Admin) -> dict:
    subject, body = " ".join(a.text("subject").split()), a.long_text("body")  # tiêu đề email không được có xuống dòng
    errors = {}
    if not subject:
        errors["subject"] = "Nhập tiêu đề email."
    if not body:
        errors["body"] = "Nhập nội dung email."
    return {"subject": subject, "body": body, "audience": _valid_audience(a.many("audience")),
            "draft_id": to_int(a.text("draft_id")), "errors": errors}


@router.post("/subscribers/mail")
def subs_mail(a: Admin = Depends(admin_post)):
    """Trường: subject, body, audience (lặp), draft_id (khi sửa bản nháp), action = send | draft."""
    mail = _mail_input(a)
    if mail["errors"]:
        return _subs_page(a, "mail", mail_form=mail, status_code=400)
    subject, body, audience = mail["subject"], mail["body"], mail["audience"]
    campaign = _draft(a.db, mail["draft_id"]) if mail["draft_id"] else Campaign(status="draft")
    campaign.subject, campaign.body, campaign.audience = subject, body, audience
    a.db.add(campaign)
    if a.text("action") == "draft":
        a.db.commit()
        return done(f"/admin/subscribers?tab=mail&draft={campaign.id}")
    targets = recipients(confirmed_subscribers(a.db), audience)
    if not targets:
        a.db.rollback()
        draft = f"&draft={mail['draft_id']}" if mail["draft_id"] else ""
        return done(f"/admin/subscribers?tab=mail{draft}", "no_recipients")
    campaign.status = "sending"  # ghi lại trước khi gửi: nếu request đứt giữa chừng vẫn thấy trong lịch sử
    a.db.commit()
    sent = send_many([build(s.email, subject, body, f"{config.base_url}/huy-dang-ky/{s.token}") for s in targets])
    campaign.status, campaign.sent_count, campaign.sent_at = "sent", sent, utcnow()
    a.db.commit()
    return done("/admin/subscribers?tab=mail", "sent")


@router.post("/subscribers/mail/test")
def subs_mail_test(a: Admin = Depends(admin_post)):
    """Gửi thử nội dung đang soạn cho chính admin đang đăng nhập. Không lưu gì, render lại form với chữ đã nhập."""
    mail = _mail_input(a)
    if mail["errors"]:
        return _subs_page(a, "mail", mail_form=mail, status_code=400)
    ok = send_email(a.user.email, f"[Gửi thử] {mail['subject']}",
                    f"{mail['body']}\n\n---\nĐây là email gửi thử. Email thật có link hủy đăng ký riêng ở vị trí này.")
    flash = ({"kind": "success", "text": f"Đã gửi thử tới {a.user.email}", "code": "test_sent"} if ok else
             {"kind": "error", "text": "Không gửi được email thử. Kiểm tra cấu hình SMTP.", "code": "test_failed"})
    return _subs_page(a, "mail", mail_form=mail, status_code=200 if ok else 502, flash=flash)


# ======================= TIN NHẮN =======================

def _messages_page(a: Admin, tab: str = "all", selected: ContactMessage | None = None):
    tab = tab if tab in dict(MSG_TABS) else "all"
    tab_qs = "" if tab == "all" else f"?tab={tab}"
    stmt = select(ContactMessage).order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
    if tab == "unread":
        stmt = stmt.where(ContactMessage.is_read.is_(False))

    def view(m: ContactMessage) -> dict:
        return {"id": m.id, "topic": m.topic, "name": m.name, "email": m.email, "body": m.body, "is_read": m.is_read,
                "created_at": m.created_at, "open_url": f"/admin/messages/{m.id}{tab_qs}",
                "toggle_url": f"/admin/messages/{m.id}/toggle", "delete_url": f"/admin/messages/{m.id}/delete"}

    return render_admin(a, "admin/messages.html", "messages", "Tin nhắn",
                        subtabs=subtabs("/admin/messages", MSG_TABS, tab), current_tab=tab,
                        messages=[view(m) for m in a.db.scalars(stmt)], selected=view(selected) if selected else None)


@router.get("/messages")
def messages_get(tab: str = "all", a: Admin = Depends(admin_get)):
    return _messages_page(a, tab)


@router.get("/messages/{mid}")
def messages_open(mid: int, tab: str = "all", a: Admin = Depends(admin_get)):
    m = get_or_404(a.db, ContactMessage, mid)
    if not m.is_read:
        m.is_read = True
        a.db.commit()
    return _messages_page(a, tab, m)


@router.post("/messages/{mid}/toggle")
def messages_toggle(mid: int, a: Admin = Depends(admin_post)):
    """Đánh dấu đã đọc / chưa đọc. Trường `back` giữ tab đang xem."""
    m = get_or_404(a.db, ContactMessage, mid)
    m.is_read = not m.is_read
    a.db.commit()
    return done(a.back("/admin/messages"), "toggled")


@router.post("/messages/{mid}/delete")
def messages_delete(mid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, ContactMessage, mid))
    a.db.commit()
    back = a.back("/admin/messages")
    if back.split("?")[0] == f"/admin/messages/{mid}":  # đang mở chính tin vừa xóa: về danh sách cùng tab
        back = "/admin/messages" + ("?" + back.split("?", 1)[1] if "?" in back else "")
    return done(back, "deleted")

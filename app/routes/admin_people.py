"""Quản trị khách: Người đăng ký (+ gửi email chiến dịch) và Tin nhắn liên hệ."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update

from app import content, queries
from app.config import config
from app.mailer import build, send_email, send_many, shared_connection
from app.models import BONUS_TYPES, CAMPAIGN_RESUMABLE, Campaign, ContactMessage, Subscriber, utcnow
from app.routes.admin_base import Admin, admin_api, admin_get, admin_post, done, get_or_404, render_admin, subtabs
from app.templating import FLASH_MESSAGES
from app.utils import to_int

router = APIRouter()

SEND_BATCH = 20  # ghi tiến độ sau mỗi lô: server tắt giữa chừng thì gửi tiếp chỉ trùng tối đa một lô
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
    """Chỉ bản nháp hoặc chiến dịch gửi dở mới mở lại/gửi/xóa được: chặn gửi trùng chiến dịch đã gửi xong."""
    queries.release_stuck_campaigns(db)
    c = db.get(Campaign, campaign_id)
    if c is None or c.status not in CAMPAIGN_RESUMABLE:
        raise HTTPException(404)
    return c


def _subs_page(a: Admin, tab: str = "list", status: str = "all", q: str = "", aud: list[str] | None = None,
               mail_form: dict | None = None, status_code=200, **extra):
    db = a.db
    queries.release_stuck_campaigns(db)
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
    if mail.get("draft_id"):  # gửi tiếp chiến dịch dở: không đếm người đã nhận
        resumed = db.get(Campaign, mail["draft_id"])
        received = set(resumed.sent_to or []) if resumed else set()
        confirmed = [s for s in confirmed if s.email not in received]
    campaigns = [{"id": c.id, "subject": c.subject, "audience_labels": [labels.get(i, i) for i in c.audience],
                  "status": c.status, "sent_count": c.sent_count, "sent_at": c.sent_at, "created_at": c.created_at,
                  "edit_url": f"/admin/subscribers?tab=mail&draft={c.id}" if c.status in CAMPAIGN_RESUMABLE else None,
                  "delete_url": f"/admin/subscribers/campaigns/{c.id}/delete" if c.status in CAMPAIGN_RESUMABLE else None}
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
    return done(a.back_after_delete("/admin/subscribers"), "deleted")


@router.post("/subscribers/campaigns/{cid}/delete")
def campaign_delete(cid: int, a: Admin = Depends(admin_post)):
    a.db.delete(_draft(a.db, cid))
    a.db.commit()
    return done("/admin/subscribers?tab=mail", "deleted")


def _mail_input(a: Admin) -> dict:
    subject, body = " ".join(a.text("subject").split()), a.long_text("body")  # tiêu đề email không được có xuống dòng
    errors = {}
    if not subject:
        errors["subject"] = "Nhập tiêu đề email."
    if not body:
        errors["body"] = "Nhập nội dung email."
    a.check_lengths(errors)
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
    a.db.flush()
    if a.text("action") == "draft":
        a.db.commit()
        return done(f"/admin/subscribers?tab=mail&draft={campaign.id}")
    # Giành quyền gửi bằng UPDATE có điều kiện: hai request gửi cùng chiến dịch thì chỉ một request được đi tiếp.
    claimed = a.db.execute(update(Campaign).where(Campaign.id == campaign.id, Campaign.status.in_(CAMPAIGN_RESUMABLE))
                           .values(status="sending"))
    if claimed.rowcount == 0:
        a.db.rollback()
        raise HTTPException(404)
    a.db.refresh(campaign)
    already = set(campaign.sent_to or [])  # gửi tiếp chiến dịch gửi dở: không gửi lại người đã nhận
    targets = [s for s in recipients(confirmed_subscribers(a.db), audience) if s.email not in already]
    if not targets and already:  # người còn lại đã hủy hoặc bị xóa: chiến dịch đã xong
        campaign.status, campaign.sent_at = "sent", utcnow()
        a.db.commit()
        return done("/admin/subscribers?tab=mail", "sent")
    if not targets:
        a.db.rollback()
        kind, text = FLASH_MESSAGES["no_recipients"]  # render lại, không mất nội dung đang soạn
        return _subs_page(a, "mail", mail_form=mail, status_code=400,
                          flash={"kind": kind, "text": text, "code": "no_recipients"})
    a.db.commit()  # ghi `sending` trước khi gửi: nếu request đứt giữa chừng vẫn thấy trong lịch sử
    received_before = len(already)
    messages = [build(s.email, subject, body, f"{config.base_url}/huy-dang-ky/{s.token}") for s in targets]
    sent = 0
    with shared_connection():
        for start in range(0, len(messages), SEND_BATCH):
            batch = messages[start:start + SEND_BATCH]
            ok = send_many(batch)
            sent += ok
            # Lưu địa chỉ gốc: header To có thể bị chuẩn hóa (dấu phẩy, khoảng trắng), so lại sẽ gửi trùng.
            already |= {s.email for s, m in zip(targets[start:start + SEND_BATCH], batch) if getattr(m, "delivered", False)}
            campaign.sent_to = sorted(already)
            campaign.sent_count = received_before + sent
            a.db.commit()  # cũng làm mới updated_at, để phân biệt đang gửi với đã chết
            if ok == 0:  # cả lô hỏng là SMTP có vấn đề; vài địa chỉ bị từ chối thì gửi tiếp cho người khác
                break
    if sent == len(messages):
        campaign.status, campaign.sent_at = "sent", utcnow()
        a.db.commit()
        return done("/admin/subscribers?tab=mail", "sent")
    # Gửi hỏng: admin phải thấy, và còn gửi lại được. Không bao giờ status=sent khi còn người chưa nhận.
    campaign.status = "partial" if campaign.sent_count else "draft"
    if campaign.sent_count:
        campaign.sent_at = utcnow()
    a.db.commit()
    return done(f"/admin/subscribers?tab=mail&draft={campaign.id}", "send_partial" if campaign.sent_count else "send_failed")


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
    return done(a.back_after_delete("/admin/messages"), "deleted")

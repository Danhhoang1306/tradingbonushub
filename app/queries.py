"""Truy vấn nghiệp vụ dùng chung + chuyển ORM sang dict cho template (hợp đồng trong docs/VIEW_CONTEXT.md)."""
from datetime import date, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, joinedload

from app.models import KIND_LABELS, Banner, Bonus, Broker, Campaign, ClickLog, Post, utcnow
from app.security import is_http_url
from app.utils import today_vn

EXPIRING_DAYS = 60


def bonus_visible_clause(today: date):
    return and_(Bonus.is_active.is_(True), Broker.is_active.is_(True),
                or_(Bonus.expiry_date.is_(None), Bonus.expiry_date >= today))


def visible_bonuses(db: Session, type_: str | None = None, sort: str = "new", limit: int | None = None,
                    broker_id: int | None = None) -> list[Bonus]:
    q = (select(Bonus).join(Bonus.broker).options(joinedload(Bonus.broker))
         .where(bonus_visible_clause(today_vn())))
    if type_:
        q = q.where(Bonus.type == type_)
    if broker_id:
        q = q.where(Bonus.broker_id == broker_id)
    if sort == "value":
        q = q.order_by(Bonus.value_num.is_(None), Bonus.value_num.desc(), Bonus.id.desc())
    elif sort == "expiry":
        q = q.order_by(Bonus.expiry_date.is_(None), Bonus.expiry_date.asc(), Bonus.id.desc())
    elif sort == "input":
        q = q.order_by(Bonus.id)
    else:
        q = q.order_by(Bonus.created_at.desc(), Bonus.id.desc())
    if limit:
        q = q.limit(limit)
    return list(db.scalars(q).unique())


def visible_bonus_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(Bonus.type, func.count()).join(Bonus.broker)
                      .where(bonus_visible_clause(today_vn())).group_by(Bonus.type)).all()
    return {t: n for t, n in rows}


def bonus_count_by_broker(db: Session) -> dict[int, int]:
    rows = db.execute(select(Bonus.broker_id, func.count()).join(Bonus.broker)
                      .where(bonus_visible_clause(today_vn())).group_by(Bonus.broker_id)).all()
    return {b: n for b, n in rows}


def top_bonus_by_broker(db: Session) -> dict[int, Bonus]:
    """Bonus giá trị cao nhất (rồi mới nhất) đang hiển thị của mỗi sàn."""
    out: dict[int, Bonus] = {}
    for b in visible_bonuses(db, sort="value"):
        out.setdefault(b.broker_id, b)
    return out


def banner_live_clause(today: date):
    return and_(Banner.is_active.is_(True),
                or_(Banner.start_date.is_(None), Banner.start_date <= today),
                or_(Banner.end_date.is_(None), Banner.end_date >= today))


def live_banner(db: Session, placement: str) -> Banner | None:
    today = today_vn()
    q = (select(Banner).where(banner_live_clause(today), Banner.placement == placement)
         .order_by(Banner.updated_at.desc(), Banner.id.desc()))
    return next((b for b in db.scalars(q) if banner_state(b, today) == "running"), None)


def banner_target(b: Banner) -> str:
    """Link đích thật của banner: target_url, không có thì link affiliate của sàn. Rỗng = banner chết."""
    if is_http_url(b.target_url):
        return b.target_url
    return b.broker.affiliate_url if b.broker and is_http_url(b.broker.affiliate_url) else ""


def banner_state(b: Banner, today: date | None = None) -> str:
    today = today or today_vn()
    if not b.is_active:
        return "paused"
    if b.start_date and b.start_date > today:
        return "scheduled"
    if b.end_date and b.end_date < today:
        return "ended"
    if b.broker and not b.broker.is_active:
        return "broker_hidden"
    if not banner_target(b):
        return "no_link"
    return "running"


def log_click(db: Session, kind: str, ref_id: int) -> None:
    stmt = sqlite_insert(ClickLog).values(kind=kind, ref_id=ref_id, day=today_vn(), count=1)
    stmt = stmt.on_conflict_do_update(index_elements=["kind", "ref_id", "day"],
                                      set_={"count": ClickLog.count + 1, "updated_at": func.current_timestamp()})
    db.execute(stmt)


def bump(db: Session, model, row_id: int, column: str) -> None:
    """Cộng lượt xem/click, giữ nguyên updated_at (lastmod sitemap, thứ tự banner không đổi vì một lượt xem)."""
    db.execute(update(model).where(model.id == row_id)
               .values({column: getattr(model, column) + 1, "updated_at": model.updated_at}))


def delete_clicks(db: Session, kind: str, ref_id: int) -> None:
    """SQLite dùng lại id: phải xóa theo, nếu không sàn/banner mới thừa hưởng click của bản đã xóa."""
    db.execute(delete(ClickLog).where(ClickLog.kind == kind, ClickLog.ref_id == ref_id))


SENDING_STALE_MINUTES = 15  # mỗi lô email đều ghi lại tiến độ, nên im lặng lâu hơn mức này là server đã tắt giữa chừng


def release_stuck_campaigns(db: Session, stale_minutes: int = SENDING_STALE_MINUTES) -> int:
    """Chiến dịch kẹt `sending` trở lại trạng thái mở được: có người đã nhận thì `partial`, chưa có thì `draft`.
    stale_minutes=0 dùng lúc khởi động: app chạy một process nên mọi `sending` khi đó đều đã chết."""
    cutoff = utcnow() - timedelta(minutes=stale_minutes)
    stuck = db.scalars(select(Campaign).where(Campaign.status == "sending", Campaign.updated_at <= cutoff)).all()
    for c in stuck:
        c.sent_count = len(c.sent_to or [])
        c.status = "partial" if c.sent_count else "draft"
    if stuck:
        db.commit()
    return len(stuck)


def daily_clicks(db: Session, days: int = 30, kind: str | None = None) -> list[dict]:
    start = today_vn() - timedelta(days=days - 1)
    q = select(ClickLog.day, func.sum(ClickLog.count)).where(ClickLog.day >= start)
    if kind:
        q = q.where(ClickLog.kind == kind)
    rows = dict(db.execute(q.group_by(ClickLog.day)).all())
    out = [{"day": start + timedelta(days=i), "clicks": int(rows.get(start + timedelta(days=i), 0))} for i in range(days)]
    peak = max(d["clicks"] for d in out) or 1
    return [d | {"percent": round(d["clicks"] / peak * 100)} for d in out]  # percent: chiều cao cột so với ngày cao nhất


def post_public_clause():
    """Đã đăng và tới ngày đăng (ngày tương lai = hẹn giờ)."""
    return and_(Post.status == "published", or_(Post.published_at.is_(None), Post.published_at <= utcnow()))


def published_posts_query():
    return select(Post).where(post_public_clause()).order_by(Post.published_at.desc(), Post.id.desc())


# ---------- ORM -> dict ----------

def broker_mini(k: Broker) -> dict:
    return {"id": k.id, "slug": k.slug, "name": k.name, "mono": k.mono, "kind": k.kind, "license": k.license,
            "logo_path": k.logo_path, "url": f"/san/{k.slug}",
            "go_url": f"/go/broker/{k.id}" if k.affiliate_url and k.is_active else None}


def bonus_view(b: Bonus, labels: dict[str, str]) -> dict:
    today = today_vn()
    return {
        "id": b.id, "type": b.type, "type_label": labels.get(b.type, b.type), "amount": b.amount,
        "value_num": b.value_num, "title": b.title, "min_deposit": b.min_deposit, "withdrawable": b.withdrawable,
        "expiry_date": b.expiry_date,
        "expires_soon": bool(b.expiry_date and today <= b.expiry_date <= today + timedelta(days=EXPIRING_DAYS)),
        "go_url": f"/go/broker/{b.broker_id}" if b.broker.affiliate_url else None,
        "broker": broker_mini(b.broker),
    }


def broker_view(k: Broker, labels: dict[str, str], bonus_count: int = 0, top: Bonus | None = None) -> dict:
    return broker_mini(k) | {
        "kind_label": KIND_LABELS.get(k.kind, k.kind),
        "tagline": k.tagline, "summary": k.summary, "min_deposit": k.min_deposit, "leverage": k.leverage,
        "platforms": k.platforms, "spread": k.spread, "withdrawal": k.withdrawal, "founded": k.founded,
        "pros": list(k.pros or []), "cons": list(k.cons or []), "accounts": list(k.accounts or []),
        "payment_methods": list(k.payment_methods or []), "featured": k.featured, "in_compare": k.in_compare,
        "bonus_count": bonus_count, "top_bonus": bonus_view(top, labels) if top else None,
    }


def post_view(p: Post) -> dict:
    return {"id": p.id, "slug": p.slug, "title": p.title, "category": p.category, "excerpt": p.excerpt,
            "cover_path": p.cover_path, "read_minutes": p.read_minutes, "published_at": p.published_at,
            "views": p.views, "url": f"/tin-tuc/{p.slug}"}


RAIL_PLACEMENTS = ("rail-left", "rail-right")  # chỉ hiện ở màn rộng: view đếm bằng beacon JS, không đếm lúc render


def banner_view(b: Banner, labels: dict[str, str], top: Bonus | None = None) -> dict:
    return {"id": b.id, "name": b.name, "image_path": b.image_path, "placement": b.placement,
            "url": f"/go/ad/{b.id}", "view_url": f"/api/ad-view/{b.id}" if b.placement in RAIL_PLACEMENTS else None,
            "broker": broker_mini(b.broker) if b.broker else None,
            "bonus": bonus_view(top, labels) if top else None}

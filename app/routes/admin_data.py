"""Quản trị dữ liệu: Bonus, Sàn, Quảng cáo, Bài viết. Danh sách + drawer form (new/edit) cùng một template."""
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from app import content, queries
from app.models import BONUS_TYPES, BROKER_KINDS, KIND_LABELS, PLACEMENTS, POST_CATEGORIES, Banner, Bonus, Broker, ClickLog, Post, utcnow
from app.routes.admin_base import Admin, _tab, admin_get, admin_post, done, get_or_404, media_library, render_admin, subtabs
from app.security import is_http_url
from app.templating import PLACEMENT_LABELS
from app.utils import VN_TZ, as_utc_naive, mono_from_name, parse_date, parse_float, read_minutes, slugify, to_int, to_vn, today_vn

router = APIRouter()

BONUS_TABS = (("all", "Tất cả"), ("on", "Đang hiển thị"), ("off", "Đã ẩn"), ("exp", "Sắp hết hạn"))
BROKER_TABS = (("list", "Danh sách"), ("links", "Link affiliate"))
ADS_TABS = (("banner", "Banner"), ("stats", "Thống kê"))
POST_TABS = (("all", "Tất cả"), ("pub", "Đã đăng"), ("draft", "Nháp"))
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _drawer(title: str, action: str, values: dict, errors: dict | None = None, delete_url: str | None = None,
            view_url: str | None = None) -> dict:
    return {"title": title, "action": action, "data": values, "errors": errors or {}, "is_new": delete_url is None,
            "delete_url": delete_url, "view_url": view_url}


def _labels(db) -> dict:
    return content.type_labels(content.get_all(db))


def _broker_options(db) -> list[dict]:
    return [{"id": k.id, "name": k.name, "is_active": k.is_active} for k in db.scalars(select(Broker).order_by(Broker.name))]



# ======================= BONUS =======================

def _bonus_values(b: Bonus | None) -> dict:
    if b is None:
        return {"broker_id": None, "type": "deposit", "title": "", "amount": "", "value_num": "", "min_deposit": "",
                "withdrawable": "", "expiry_date": "", "is_active": True}
    return {"broker_id": b.broker_id, "type": b.type, "title": b.title, "amount": b.amount,
            "value_num": "" if b.value_num is None else f"{b.value_num:g}", "min_deposit": b.min_deposit,
            "withdrawable": b.withdrawable, "expiry_date": b.expiry_date.isoformat() if b.expiry_date else "",
            "is_active": b.is_active}


def _bonus_page(a: Admin, tab: str = "all", q: str = "", type: str = "all", drawer: dict | None = None, status_code=200):
    db, today = a.db, today_vn()
    tab, type = _tab(tab, BONUS_TABS), (type if type in BONUS_TYPES else "all")
    stmt = select(Bonus).join(Bonus.broker).options(joinedload(Bonus.broker)).order_by(Bonus.created_at.desc(), Bonus.id.desc())
    if tab == "on":
        stmt = stmt.where(queries.bonus_visible_clause(today))
    elif tab == "off":
        stmt = stmt.where(~queries.bonus_visible_clause(today))
    elif tab == "exp":
        stmt = stmt.where(queries.bonus_visible_clause(today), Bonus.expiry_date.is_not(None),
                          Bonus.expiry_date <= today + timedelta(days=queries.EXPIRING_DAYS))
    if type != "all":
        stmt = stmt.where(Bonus.type == type)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Bonus.title.ilike(like), Broker.name.ilike(like)))
    labels = _labels(db)
    rows = []
    for b in db.scalars(stmt).unique():
        expired = bool(b.expiry_date and b.expiry_date < today)
        rows.append(queries.bonus_view(b, labels) | {
            "is_active": b.is_active, "expired": expired, "broker_active": b.broker.is_active,
            "visible": b.is_active and b.broker.is_active and not expired,
            "edit_url": f"/admin/bonus/{b.id}/edit", "toggle_url": f"/admin/bonus/{b.id}/toggle",
            "delete_url": f"/admin/bonus/{b.id}/delete"})
    return render_admin(
        a, "admin/bonus.html", "bonus", "Bonus", status_code,
        subtabs=subtabs("/admin/bonus", BONUS_TABS, tab), current_tab=tab, q=q, current_type=type,
        type_filters=[{"id": "all", "label": "Tất cả"}] + [{"id": t, "label": labels[t]} for t in BONUS_TYPES],
        bonuses=rows, add_url="/admin/bonus/new", add_label="Thêm bonus",
        broker_options=_broker_options(db), type_options=[{"id": t, "label": labels[t]} for t in BONUS_TYPES],
        drawer=drawer)


@router.get("/bonus")
def bonus_list(tab: str = "all", q: str = "", type: str = "all", a: Admin = Depends(admin_get)):
    return _bonus_page(a, tab, q, type)


@router.get("/bonus/new")
def bonus_new(a: Admin = Depends(admin_get)):
    return _bonus_page(a, drawer=_drawer("Thêm bonus", "/admin/bonus/new", _bonus_values(None)))


@router.get("/bonus/{bid}/edit")
def bonus_edit(bid: int, a: Admin = Depends(admin_get)):
    b = get_or_404(a.db, Bonus, bid)
    return _bonus_page(a, drawer=_drawer("Sửa bonus", f"/admin/bonus/{bid}/edit", _bonus_values(b),
                                         delete_url=f"/admin/bonus/{bid}/delete"))


def _bonus_save(a: Admin, b: Bonus | None):
    errors, v = {}, {
        "broker_id": a.text("broker_id"), "type": a.text("type"), "title": a.text("title"), "amount": a.text("amount", 60),
        "value_num": a.text("value_num", 30), "min_deposit": a.text("min_deposit", 60),
        "withdrawable": a.text("withdrawable", 60), "expiry_date": a.text("expiry_date", 20), "is_active": a.flag("is_active")}
    broker_id = to_int(v["broker_id"])
    broker = a.db.get(Broker, broker_id) if broker_id else None
    if broker is None:
        errors["broker_id"] = "Chọn sàn."
    if v["type"] not in BONUS_TYPES:
        errors["type"] = "Chọn loại bonus."
    if not v["title"]:
        errors["title"] = "Nhập tiêu đề."
    try:
        value_num = parse_float(v["value_num"])
    except ValueError:
        errors["value_num"] = "Giá trị phải là số."
    try:
        expiry = parse_date(v["expiry_date"])
    except ValueError:
        errors["expiry_date"] = "Ngày không hợp lệ."
    if errors:
        title, action = ("Thêm bonus", "/admin/bonus/new") if b is None else ("Sửa bonus", f"/admin/bonus/{b.id}/edit")
        return _bonus_page(a, drawer=_drawer(title, action, v, errors, None if b is None else f"/admin/bonus/{b.id}/delete"),
                           status_code=400)
    is_new = b is None
    if is_new:
        b = Bonus()
        a.db.add(b)
    b.broker_id, b.type, b.title, b.amount, b.value_num = broker.id, v["type"], v["title"], v["amount"], value_num
    b.min_deposit, b.withdrawable, b.expiry_date, b.is_active = v["min_deposit"], v["withdrawable"], expiry, v["is_active"]
    a.db.commit()
    return done("/admin/bonus", "created" if is_new else "saved")


@router.post("/bonus/new")
def bonus_create(a: Admin = Depends(admin_post)):
    return _bonus_save(a, None)


@router.post("/bonus/{bid}/edit")
def bonus_update(bid: int, a: Admin = Depends(admin_post)):
    return _bonus_save(a, get_or_404(a.db, Bonus, bid))


@router.post("/bonus/{bid}/toggle")
def bonus_toggle(bid: int, a: Admin = Depends(admin_post)):
    b = get_or_404(a.db, Bonus, bid)
    b.is_active = not b.is_active
    a.db.commit()
    return done(a.back("/admin/bonus"), "toggled")


@router.post("/bonus/{bid}/delete")
def bonus_delete(bid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, Bonus, bid))
    a.db.commit()
    return done("/admin/bonus", "deleted")


# ======================= SÀN =======================

BROKER_TEXT = ("name", "slug", "mono", "kind", "tagline", "license", "min_deposit", "leverage", "platforms", "spread",
               "withdrawal", "founded", "affiliate_url", "logo_path")
ACCOUNT_FIELDS = ("name", "min_deposit", "spread", "commission")
PAYMENT_FIELDS = ("method", "deposit", "withdraw", "time")


def _broker_values(k: Broker | None) -> dict:
    if k is None:
        return {f: "" for f in BROKER_TEXT} | {"kind": "forex", "summary": "", "pros": [], "cons": [], "accounts": [],
                                               "payment_methods": [], "in_compare": False, "featured": False,
                                               "is_active": True}
    return {f: getattr(k, f) for f in BROKER_TEXT} | {
        "summary": k.summary, "pros": list(k.pros), "cons": list(k.cons), "accounts": list(k.accounts),
        "payment_methods": list(k.payment_methods), "in_compare": k.in_compare, "featured": k.featured,
        "is_active": k.is_active}


def _broker_page(a: Admin, tab: str = "list", drawer: dict | None = None, status_code=200):
    db, tab = a.db, _tab(tab, BROKER_TABS)
    counts = queries.bonus_count_by_broker(db)
    start = today_vn() - timedelta(days=29)
    clicks30 = dict(db.execute(select(ClickLog.ref_id, func.sum(ClickLog.count))
                               .where(ClickLog.kind == "broker", ClickLog.day >= start).group_by(ClickLog.ref_id)).all())
    brokers = db.scalars(select(Broker).order_by(Broker.featured.desc(), Broker.name)).all()
    rows = [{
        "id": k.id, "slug": k.slug, "name": k.name, "mono": k.mono, "kind": k.kind, "license": k.license,
        "min_deposit": k.min_deposit, "leverage": k.leverage, "platforms": k.platforms, "affiliate_url": k.affiliate_url,
        "logo_path": k.logo_path, "in_compare": k.in_compare, "featured": k.featured, "is_active": k.is_active,
        "clicks": k.clicks, "clicks_30d": int(clicks30.get(k.id, 0)), "bonus_count": counts.get(k.id, 0),
        "view_url": f"/san/{k.slug}", "edit_url": f"/admin/brokers/{k.id}/edit", "toggle_url": f"/admin/brokers/{k.id}/toggle",
        "link_url": f"/admin/brokers/{k.id}/link", "delete_url": f"/admin/brokers/{k.id}/delete"} for k in brokers]
    return render_admin(
        a, "admin/brokers.html", "brokers", "Sàn", status_code,
        subtabs=subtabs("/admin/brokers", BROKER_TABS, tab), current_tab=tab, brokers=rows,
        compare_count=sum(1 for k in brokers if k.in_compare), max_compare=3,
        add_url="/admin/brokers/new", add_label="Thêm sàn", kind_options=[{"id": k, "label": KIND_LABELS[k]} for k in BROKER_KINDS],
        drawer=drawer, media_library=media_library(db) if drawer else [])


@router.get("/brokers")
def broker_list(tab: str = "list", a: Admin = Depends(admin_get)):
    return _broker_page(a, tab)


@router.get("/brokers/new")
def broker_new(a: Admin = Depends(admin_get)):
    return _broker_page(a, drawer=_drawer("Thêm sàn", "/admin/brokers/new", _broker_values(None)))


@router.get("/brokers/{kid}/edit")
def broker_edit(kid: int, a: Admin = Depends(admin_get)):
    k = get_or_404(a.db, Broker, kid)
    return _broker_page(a, drawer=_drawer("Sửa sàn", f"/admin/brokers/{kid}/edit", _broker_values(k),
                                          delete_url=f"/admin/brokers/{kid}/delete", view_url=f"/san/{k.slug}"))


def _compare_full(db, exclude_id: int | None) -> bool:
    return db.scalar(select(func.count()).select_from(Broker).where(Broker.in_compare.is_(True),
                                                                   Broker.id != (exclude_id or 0))) >= 3


def _set_featured(db, k: Broker) -> None:
    for other in db.scalars(select(Broker).where(Broker.featured.is_(True), Broker.id != (k.id or 0))):
        other.featured = False
    k.featured = True


def _broker_save(a: Admin, k: Broker | None):
    db, errors = a.db, {}
    v = {f: a.text(f, 1000 if f == "affiliate_url" else 255) for f in BROKER_TEXT}
    v |= {"summary": a.long_text("summary"), "pros": a.lines("pros"), "cons": a.lines("cons"),
          "accounts": a.rows("account", ACCOUNT_FIELDS), "payment_methods": a.rows("payment", PAYMENT_FIELDS),
          "in_compare": a.flag("in_compare"), "featured": a.flag("featured"), "is_active": a.flag("is_active")}
    v["logo_path"] = a.image("logo_path", errors, k.logo_path if k else "")
    if not v["name"]:
        errors["name"] = "Nhập tên sàn."
    v["slug"] = slugify(v["slug"] or v["name"])
    if not v["slug"] or not SLUG_RE.match(v["slug"]):
        errors["slug"] = "Slug chỉ gồm chữ thường, số và dấu gạch ngang."
    elif db.scalar(select(Broker.id).where(Broker.slug == v["slug"], Broker.id != (k.id if k else 0))):
        errors["slug"] = "Slug đã được dùng."
    v["mono"] = (v["mono"] or mono_from_name(v["name"]))[:2].upper()
    if v["kind"] not in BROKER_KINDS:
        errors["kind"] = "Chọn loại sàn."
    if v["affiliate_url"] and not is_http_url(v["affiliate_url"]):
        errors["affiliate_url"] = "Link phải bắt đầu bằng http:// hoặc https://"
    if v["in_compare"] and not (k and k.in_compare) and _compare_full(db, k.id if k else None):
        errors["in_compare"] = "Chỉ được chọn tối đa 3 sàn để so sánh."
    if errors:
        title, action = ("Thêm sàn", "/admin/brokers/new") if k is None else ("Sửa sàn", f"/admin/brokers/{k.id}/edit")
        return _broker_page(a, drawer=_drawer(title, action, v, errors,
                                              None if k is None else f"/admin/brokers/{k.id}/delete"), status_code=400)
    is_new = k is None
    if is_new:
        k = Broker()
        db.add(k)
    for f in BROKER_TEXT + ("summary", "pros", "cons", "accounts", "payment_methods", "in_compare", "is_active"):
        setattr(k, f, v[f])
    if v["featured"]:
        db.flush()
        _set_featured(db, k)
    else:
        k.featured = False
    db.commit()
    return done("/admin/brokers", "created" if is_new else "saved")


@router.post("/brokers/new")
def broker_create(a: Admin = Depends(admin_post)):
    return _broker_save(a, None)


@router.post("/brokers/{kid}/edit")
def broker_update(kid: int, a: Admin = Depends(admin_post)):
    return _broker_save(a, get_or_404(a.db, Broker, kid))


@router.post("/brokers/{kid}/toggle")
def broker_toggle(kid: int, a: Admin = Depends(admin_post)):
    """Trường `field`: is_active | in_compare | featured."""
    k = get_or_404(a.db, Broker, kid)
    field = a.text("field") or "is_active"
    if field == "in_compare":
        if not k.in_compare and _compare_full(a.db, k.id):
            return done(a.back("/admin/brokers"), "compare_limit")
        k.in_compare = not k.in_compare
    elif field == "featured":
        if k.featured:
            k.featured = False
        else:
            _set_featured(a.db, k)
    elif field == "is_active":
        k.is_active = not k.is_active
    else:
        raise HTTPException(400, "field không hợp lệ")
    a.db.commit()
    return done(a.back("/admin/brokers"), "toggled")


@router.post("/brokers/{kid}/link")
def broker_link(kid: int, a: Admin = Depends(admin_post)):
    k = get_or_404(a.db, Broker, kid)
    url = a.text("affiliate_url", 1000)
    if url and not is_http_url(url):
        return done("/admin/brokers?tab=links", "invalid_url")
    k.affiliate_url = url
    a.db.commit()
    return done("/admin/brokers?tab=links")


@router.post("/brokers/{kid}/delete")
def broker_delete(kid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, Broker, kid))
    a.db.commit()
    return done("/admin/brokers", "deleted")


# ======================= QUẢNG CÁO =======================

def _banner_values(b: Banner | None) -> dict:
    if b is None:
        return {"name": "", "broker_id": None, "placement": "after-bonus", "target_url": "", "image_path": "",
                "start_date": "", "end_date": "", "is_active": True}
    return {"name": b.name, "broker_id": b.broker_id, "placement": b.placement, "target_url": b.target_url,
            "image_path": b.image_path, "start_date": b.start_date.isoformat() if b.start_date else "",
            "end_date": b.end_date.isoformat() if b.end_date else "", "is_active": b.is_active}


def _ads_page(a: Admin, tab: str = "banner", drawer: dict | None = None, status_code=200):
    db, tab, today = a.db, _tab(tab, ADS_TABS), today_vn()
    banners = db.scalars(select(Banner).options(joinedload(Banner.broker)).order_by(Banner.created_at.desc())).all()
    rows = [{
        "id": b.id, "name": b.name, "image_path": b.image_path, "placement": b.placement, "target_url": b.target_url,
        "broker": {"id": b.broker.id, "name": b.broker.name} if b.broker else None, "start_date": b.start_date,
        "end_date": b.end_date, "is_active": b.is_active, "state": queries.banner_state(b, today), "views": b.views,
        "clicks": b.clicks, "edit_url": f"/admin/ads/{b.id}/edit", "toggle_url": f"/admin/ads/{b.id}/toggle",
        "delete_url": f"/admin/ads/{b.id}/delete"} for b in banners]
    return render_admin(
        a, "admin/ads.html", "ads", "Quảng cáo", status_code,
        subtabs=subtabs("/admin/ads", ADS_TABS, tab), current_tab=tab, banners=rows,
        totals={"views": sum(b.views for b in banners), "clicks": sum(b.clicks for b in banners)},
        ad_click_days=queries.daily_clicks(db, 30, kind="ad"),
        add_url="/admin/ads/new", add_label="Thêm banner", broker_options=_broker_options(db),
        placement_options=[{"id": p, "label": PLACEMENT_LABELS[p]} for p in PLACEMENTS],
        drawer=drawer, media_library=media_library(db) if drawer else [])



@router.get("/ads")
def ads_list(tab: str = "banner", a: Admin = Depends(admin_get)):
    return _ads_page(a, tab)


@router.get("/ads/new")
def ads_new(a: Admin = Depends(admin_get)):
    return _ads_page(a, drawer=_drawer("Thêm banner", "/admin/ads/new", _banner_values(None)))


@router.get("/ads/{aid}/edit")
def ads_edit(aid: int, a: Admin = Depends(admin_get)):
    b = get_or_404(a.db, Banner, aid)
    return _ads_page(a, drawer=_drawer("Sửa banner", f"/admin/ads/{aid}/edit", _banner_values(b),
                                       delete_url=f"/admin/ads/{aid}/delete"))


def _ads_save(a: Admin, b: Banner | None):
    db, errors = a.db, {}
    v = {"name": a.text("name", 120), "broker_id": a.text("broker_id"), "placement": a.text("placement"),
         "target_url": a.text("target_url", 1000), "start_date": a.text("start_date", 20),
         "end_date": a.text("end_date", 20), "is_active": a.flag("is_active")}
    v["image_path"] = a.image("image_path", errors, b.image_path if b else "")
    broker = None
    if v["broker_id"]:
        broker_id = to_int(v["broker_id"])
        broker = db.get(Broker, broker_id) if broker_id else None
        if broker is None:
            errors["broker_id"] = "Sàn không tồn tại."
    if not v["name"]:
        errors["name"] = "Nhập tên banner."
    if v["placement"] not in PLACEMENTS:
        errors["placement"] = "Chọn vị trí."
    if v["target_url"] and not is_http_url(v["target_url"]):
        errors["target_url"] = "Link phải bắt đầu bằng http:// hoặc https://"
    if not v["target_url"] and not (broker and broker.affiliate_url):
        errors.setdefault("target_url", "Nhập link đích hoặc chọn sàn có link affiliate.")
    try:
        start, end = parse_date(v["start_date"]), parse_date(v["end_date"])
        if start and end and end < start:
            errors["end_date"] = "Ngày kết thúc phải sau ngày bắt đầu."
    except ValueError:
        errors["start_date"] = "Ngày không hợp lệ."
    if errors:
        title, action = ("Thêm banner", "/admin/ads/new") if b is None else ("Sửa banner", f"/admin/ads/{b.id}/edit")
        return _ads_page(a, drawer=_drawer(title, action, v, errors, None if b is None else f"/admin/ads/{b.id}/delete"),
                         status_code=400)
    is_new = b is None
    if is_new:
        b = Banner()
        db.add(b)
    b.name, b.broker_id, b.placement, b.target_url = v["name"], broker.id if broker else None, v["placement"], v["target_url"]
    b.image_path, b.start_date, b.end_date, b.is_active = v["image_path"], start, end, v["is_active"]
    db.commit()
    return done("/admin/ads", "created" if is_new else "saved")


@router.post("/ads/new")
def ads_create(a: Admin = Depends(admin_post)):
    return _ads_save(a, None)


@router.post("/ads/{aid}/edit")
def ads_update(aid: int, a: Admin = Depends(admin_post)):
    return _ads_save(a, get_or_404(a.db, Banner, aid))


@router.post("/ads/{aid}/toggle")
def ads_toggle(aid: int, a: Admin = Depends(admin_post)):
    b = get_or_404(a.db, Banner, aid)
    b.is_active = not b.is_active
    a.db.commit()
    return done(a.back("/admin/ads"), "toggled")


@router.post("/ads/{aid}/delete")
def ads_delete(aid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, Banner, aid))
    a.db.commit()
    return done("/admin/ads", "deleted")


# ======================= BÀI VIẾT =======================

def _post_values(p: Post | None) -> dict:
    if p is None:
        return {"title": "", "slug": "", "category": POST_CATEGORIES[0], "excerpt": "", "body_md": "", "cover_path": "",
                "status": "draft", "published_at": "", "show_home": False}
    pub = to_vn(p.published_at).date().isoformat() if p.published_at else ""
    return {"title": p.title, "slug": p.slug, "category": p.category, "excerpt": p.excerpt, "body_md": p.body_md,
            "cover_path": p.cover_path, "status": p.status, "published_at": pub, "show_home": p.show_home}


def _posts_page(a: Admin, tab: str = "all", q: str = "", drawer: dict | None = None, status_code=200):
    db, tab = a.db, _tab(tab, POST_TABS)
    stmt = select(Post).order_by(Post.published_at.is_(None).desc(), Post.published_at.desc(), Post.id.desc())
    if tab == "pub":
        stmt = stmt.where(Post.status == "published")
    elif tab == "draft":
        stmt = stmt.where(Post.status == "draft")
    if q.strip():
        stmt = stmt.where(Post.title.ilike(f"%{q.strip()}%"))
    rows = [queries.post_view(p) | {
        "status": p.status, "show_home": p.show_home, "view_url": f"/tin-tuc/{p.slug}" if p.status == "published" else None,
        "edit_url": f"/admin/posts/{p.id}/edit", "toggle_url": f"/admin/posts/{p.id}/toggle",
        "delete_url": f"/admin/posts/{p.id}/delete"} for p in db.scalars(stmt)]
    return render_admin(
        a, "admin/posts.html", "posts", "Bài viết", status_code,
        subtabs=subtabs("/admin/posts", POST_TABS, tab), current_tab=tab, q=q, posts=rows,
        add_url="/admin/posts/new", add_label="Thêm bài viết", category_options=list(POST_CATEGORIES),
        drawer=drawer, media_library=media_library(db) if drawer else [])


@router.get("/posts")
def posts_list(tab: str = "all", q: str = "", a: Admin = Depends(admin_get)):
    return _posts_page(a, tab, q)


@router.get("/posts/new")
def posts_new(a: Admin = Depends(admin_get)):
    return _posts_page(a, drawer=_drawer("Thêm bài viết", "/admin/posts/new", _post_values(None)))


@router.get("/posts/{pid}/edit")
def posts_edit(pid: int, a: Admin = Depends(admin_get)):
    p = get_or_404(a.db, Post, pid)
    return _posts_page(a, drawer=_drawer("Sửa bài viết", f"/admin/posts/{pid}/edit", _post_values(p),
                                         delete_url=f"/admin/posts/{pid}/delete",
                                         view_url=f"/tin-tuc/{p.slug}" if p.status == "published" else None))


def _posts_save(a: Admin, p: Post | None):
    db, errors = a.db, {}
    v = {"title": a.text("title"), "slug": a.text("slug", 200), "category": a.text("category", 40),
         "excerpt": a.text("excerpt", 1000), "body_md": a.long_text("body_md"), "status": a.text("status", 20),
         "published_at": a.text("published_at", 20), "show_home": a.flag("show_home")}
    v["cover_path"] = a.image("cover_path", errors, p.cover_path if p else "")
    if not v["title"]:
        errors["title"] = "Nhập tiêu đề."
    v["slug"] = slugify(v["slug"] or v["title"])
    if not v["slug"] or not SLUG_RE.match(v["slug"]):
        errors["slug"] = "Slug chỉ gồm chữ thường, số và dấu gạch ngang."
    elif db.scalar(select(Post.id).where(Post.slug == v["slug"], Post.id != (p.id if p else 0))):
        errors["slug"] = "Slug đã được dùng."
    if v["category"] not in POST_CATEGORIES:
        errors["category"] = "Chọn chuyên mục."
    if v["status"] not in ("draft", "published"):
        errors["status"] = "Trạng thái không hợp lệ."
    published_at = None
    try:
        d = parse_date(v["published_at"])
        if d:
            published_at = as_utc_naive(datetime(d.year, d.month, d.day, 8, 0, tzinfo=VN_TZ))
    except ValueError:
        errors["published_at"] = "Ngày không hợp lệ."
    if errors:
        title, action = ("Thêm bài viết", "/admin/posts/new") if p is None else ("Sửa bài viết", f"/admin/posts/{p.id}/edit")
        return _posts_page(a, drawer=_drawer(title, action, v, errors, None if p is None else f"/admin/posts/{p.id}/delete"),
                           status_code=400)
    is_new = p is None
    if is_new:
        p = Post()
        db.add(p)
    p.title, p.slug, p.category, p.excerpt, p.body_md = v["title"], v["slug"], v["category"], v["excerpt"], v["body_md"]
    p.cover_path, p.status, p.show_home, p.read_minutes = v["cover_path"], v["status"], v["show_home"], read_minutes(v["body_md"])
    if published_at:
        p.published_at = published_at
    elif p.status == "published" and p.published_at is None:
        p.published_at = utcnow()
    db.commit()
    return done("/admin/posts", "created" if is_new else "saved")


@router.post("/posts/new")
def posts_create(a: Admin = Depends(admin_post)):
    return _posts_save(a, None)


@router.post("/posts/{pid}/edit")
def posts_update(pid: int, a: Admin = Depends(admin_post)):
    return _posts_save(a, get_or_404(a.db, Post, pid))


@router.post("/posts/{pid}/toggle")
def posts_toggle(pid: int, a: Admin = Depends(admin_post)):
    """Bật/tắt hiện ở trang chủ (show_home)."""
    p = get_or_404(a.db, Post, pid)
    p.show_home = not p.show_home
    a.db.commit()
    return done(a.back("/admin/posts"), "toggled")


@router.post("/posts/{pid}/delete")
def posts_delete(pid: int, a: Admin = Depends(admin_post)):
    a.db.delete(get_or_404(a.db, Post, pid))
    a.db.commit()
    return done("/admin/posts", "deleted")

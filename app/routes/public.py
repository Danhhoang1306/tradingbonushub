import logging
import math
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import content, queries
from app.config import config
from app.db import get_db
from app.mailer import send_email
from app.models import BONUS_TYPES, POST_CATEGORIES, Banner, Broker, ContactMessage, Post, Subscriber, utcnow
from app.security import ad_view_limiter, client_ip, is_http_url, is_local_path, new_token, public_form_limiter
from app.templating import FLASH_MESSAGES, render, set_flash
from app.utils import EMAIL_RE, plain_excerpt, render_markdown, to_int, today_vn

log = logging.getLogger("app.public")
router = APIRouter()

POSTS_PER_PAGE = 12
CONFIRM_EMAILS_PER_DAY = 3      # email xác nhận tối đa cho một địa chỉ trong 24 giờ
UNSUBSCRIBED_RESEND_DAYS = 30   # người đã hủy: nhập lại địa chỉ của họ chỉ gây tối đa 1 email mỗi 30 ngày
BONUS_SORTS = (("new", "Mới nhất"), ("value", "Giá trị cao"), ("expiry", "Sắp hết hạn"))
BROKER_TABS = (("overview", "Tổng quan"), ("bonus", "Bonus"), ("accounts", "Tài khoản & phí"), ("pay", "Nạp & rút"))
ABOUT_TABS = (("about", "Về chúng tôi", "/gioi-thieu"), ("method", "Cách đánh giá", "/gioi-thieu/cach-danh-gia"),
              ("affiliate", "Công bố affiliate", "/gioi-thieu/affiliate"), ("contact", "Liên hệ", "/lien-he"))
COMPARE_ROWS = (("Giấy phép", "license"), ("Nạp tối thiểu", "min_deposit"), ("Đòn bẩy tối đa", "leverage"),
                ("Spread / phí", "spread"), ("Nền tảng", "platforms"), ("Rút tiền", "withdrawal"),
                ("Thành lập", "founded"), ("Bonus đang có", "bonus_count"))

FLASH_MESSAGES.update({
    "sub_ok": ("success", "Kiểm tra hộp thư để xác nhận email."),
    "sub_invalid": ("error", "Vui lòng nhập email hợp lệ."),
    "sub_rate": ("error", "Bạn thao tác quá nhanh, vui lòng thử lại sau ít phút."),
    "sub_failed": ("error", "Chưa gửi được email xác nhận. Vui lòng thử lại sau."),
    "contact_ok": ("success", "Cảm ơn bạn. Chúng tôi sẽ trả lời qua email."),
})


# ---------- khung chung ----------

def site_ctx(db: Session) -> dict:
    try:
        site = content.get_all(db)
    except Exception:  # DB hỏng (kể cả lỗi lúc mở kết nối): trang lỗi vẫn phải render được
        log.exception("Không đọc được Setting, dùng nội dung mặc định")
        site = content.resolve({})
        try:
            db.rollback()
        except Exception:
            log.exception("Không rollback được phiên DB")
    site["type_labels"] = content.type_labels(site)
    site["bonus_types"] = [t | {"url": f"/bonus?type={t['id']}"} for t in site["bonus_types"]]
    site["year"] = today_vn().year
    site["footer"]["copyright"] = site["footer"]["copyright"].replace("{year}", str(site["year"]))
    return site


def page_ctx(request: Request, db: Session, *, page_key: str | None = None, title: str | None = None,
             desc: str | None = None, crumbs: list | None = None, noindex: bool = False,
             system_title: str | None = None, **extra) -> dict:
    site = site_ctx(db)
    page = site["pages"].get(page_key, {}) if page_key else {}
    if system_title:
        title = site["system_text"][system_title]
    # Trang tự đặt tiêu đề (sàn, bài viết, trang lỗi): SEO chung của mục không được đè lên, mỗi trang có SEO riêng.
    page_seo = {} if title is not None else page
    title = title if title is not None else page.get("title", "")
    desc = desc if desc is not None else page.get("desc", "")
    meta_title = page_seo.get("meta_title") or (f"{title} – {site['site_name']}" if title else site["meta_title"])
    meta_desc = page_seo.get("meta_desc") or desc or site["meta_desc"]
    og = site["branding"]["og_image"]
    request.state.analytics = bool(site["analytics_head"].strip())
    return {
        "site": site,
        "page": {"key": page_key, "title": title, "desc": desc, "label": page.get("label", "")},
        "meta": {"title": meta_title, "description": meta_desc, "keywords": site["meta_keywords"],
                 "canonical": config.base_url + request.url.path,
                 "og_image": (config.base_url + og) if og.startswith("/") else og, "noindex": noindex},
        "crumbs": [{"label": "Trang chủ", "url": "/"}] + (crumbs or []),
        "current_path": request.url.path,
        **extra,
    }


def not_found(request: Request, db: Session):
    return render(request, "public/404.html", page_ctx(request, db, system_title="not_found_title", desc="", noindex=True),
                  status_code=404)


def _qs(**params) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, "", "all", "new", 1)}
    return ("?" + urlencode(clean)) if clean else ""


def _crumb(ctx: dict, key: str, url: str) -> dict:
    """Mục breadcrumb lấy nhãn từ Setting pages (admin sửa được)."""
    return {"label": ctx["site"]["pages"][key]["label"], "url": url}


def _is_head(request: Request) -> bool:
    return bool(request.scope.get("is_head"))


def _canonical(ctx: dict, **params) -> None:
    """Giữ trong canonical các tham số đổi nội dung trang (đã chuẩn hóa). `sort` và `ids` không đổi tập nội dung."""
    ctx["meta"]["canonical"] += _qs(**params)


# ---------- trang chủ ----------

@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    ctx = page_ctx(request, db)
    site = ctx["site"]
    labels = site["type_labels"]
    ctx["meta"]["title"] = site["meta_title"]
    ctx["meta"]["description"] = site["meta_desc"]
    tops = queries.top_bonus_by_broker(db)
    counts = queries.bonus_count_by_broker(db)

    latest = [queries.bonus_view(b, labels) for b in queries.visible_bonuses(db, limit=8)]
    featured = db.scalar(select(Broker).where(Broker.featured.is_(True), Broker.is_active.is_(True)))
    hero_bonus = queries.bonus_view(tops[featured.id], labels) if featured and featured.id in tops else None

    enabled = {s["id"] for s in site["sections"] if s["on"]}
    placement_section = {"after-bonus": "ad1", "before-blog": "ad2"}

    def banner(placement):
        section = placement_section.get(placement)
        if section and section not in enabled:  # section tắt: banner không hiển thị, không đếm
            return None
        b = queries.live_banner(db, placement)
        if b is None:
            return None
        if section and not _is_head(request):  # rail đếm qua beacon
            queries.bump(db, Banner, b.id, "views")
        return queries.banner_view(b, labels, tops.get(b.broker_id))

    banners = {p: banner(p) for p in ("rail-left", "rail-right", "after-bonus", "before-blog")}
    compare = db.scalars(select(Broker).where(Broker.in_compare.is_(True), Broker.is_active.is_(True))
                         .order_by(Broker.featured.desc(), Broker.name).limit(3)).all()
    posts = db.scalars(queries.published_posts_query().where(Post.show_home.is_(True)).limit(3)).all()
    db.commit()

    type_counts = Counter(b["type"] for b in latest)
    has_data = {"bonus": bool(latest), "ad1": bool(banners["after-bonus"]), "compare": bool(compare),
                "ad2": bool(banners["before-blog"]), "blog": bool(posts)}
    ctx.update(
        home_sections=[s["id"] for s in site["sections"] if s["on"] and has_data.get(s["id"], True)],
        hero=site["hero"], hero_bonus=hero_bonus,
        rail_left=banners["rail-left"], rail_right=banners["rail-right"],
        active_bonus_count=sum(queries.visible_bonus_counts(db).values()),
        latest_bonuses=latest,
        bonus_filters=[{"id": "all", "label": "Tất cả", "count": len(latest)}] + [
            {"id": t["id"], "label": t["label"], "count": type_counts[t["id"]]}
            for t in site["bonus_types"] if type_counts.get(t["id"])],
        ad1=banners["after-bonus"], ad2=banners["before-blog"],
        compare_brokers=[queries.broker_view(k, labels, counts.get(k.id, 0), tops.get(k.id)) for k in compare],
        blog_posts=[queries.post_view(p) for p in posts],
    )
    return render(request, "public/home.html", ctx)


# ---------- bonus ----------

@router.get("/bonus")
def bonus_list(request: Request, type: str = "all", sort: str = "new", db: Session = Depends(get_db)):
    type_ = type if type in BONUS_TYPES else "all"
    sort = sort if sort in dict(BONUS_SORTS) else "new"
    ctx = page_ctx(request, db, page_key="bonus")
    labels = ctx["site"]["type_labels"]
    counts = queries.visible_bonus_counts(db)
    bonuses = [queries.bonus_view(b, labels) for b in
               queries.visible_bonuses(db, None if type_ == "all" else type_, sort)]
    ctx["crumbs"].append(_crumb(ctx, "bonus", "/bonus"))
    _canonical(ctx, type=type_)
    ctx.update(
        current_type=type_, current_sort=sort, bonuses=bonuses, bonus_count=len(bonuses),
        tabs=[{"id": "all", "label": "Tất cả", "count": sum(counts.values()), "url": "/bonus" + _qs(sort=sort),
               "active": type_ == "all"}] + [
            {"id": t, "label": labels[t], "count": counts.get(t, 0), "url": "/bonus" + _qs(type=t, sort=sort),
             "active": type_ == t} for t in BONUS_TYPES],
        sorts=[{"id": s, "label": label, "url": "/bonus" + _qs(type=type_, sort=s), "active": sort == s}
               for s, label in BONUS_SORTS],
    )
    return render(request, "public/bonus_list.html", ctx)


# ---------- sàn ----------

def _broker_tabs(brokers: list[Broker], active: str) -> list[dict]:
    counts_by_kind, total = Counter(k.kind for k in brokers), len(brokers)
    return [
        {"id": "all", "label": "Tất cả sàn", "count": total, "url": "/san", "active": active == "all"},
        {"id": "forex", "label": "Forex", "count": counts_by_kind.get("forex", 0), "url": "/san?kind=forex",
         "active": active == "forex"},
        {"id": "crypto", "label": "Crypto", "count": counts_by_kind.get("crypto", 0), "url": "/san?kind=crypto",
         "active": active == "crypto"},
        {"id": "compare", "label": "So sánh", "count": None, "url": "/san/so-sanh", "active": active == "compare"},
    ]


def _active_brokers(db: Session) -> list[Broker]:
    return list(db.scalars(select(Broker).where(Broker.is_active.is_(True)).order_by(Broker.featured.desc(), Broker.name)))


@router.get("/san")
def broker_list(request: Request, kind: str = "all", db: Session = Depends(get_db)):
    kind = kind if kind in ("forex", "crypto") else "all"
    ctx = page_ctx(request, db, page_key="san")
    labels = ctx["site"]["type_labels"]
    all_brokers = _active_brokers(db)
    counts = queries.bonus_count_by_broker(db)
    ctx["crumbs"].append(_crumb(ctx, "san", "/san"))
    _canonical(ctx, kind=kind)
    ctx.update(current_kind=kind, tabs=_broker_tabs(all_brokers, kind),
               brokers=[queries.broker_view(k, labels, counts.get(k.id, 0)) for k in all_brokers
                        if kind == "all" or k.kind == kind])
    return render(request, "public/broker_list.html", ctx)


@router.get("/san/so-sanh")
def broker_compare(request: Request, ids: str | None = None, db: Session = Depends(get_db)):
    ctx = page_ctx(request, db, page_key="compare")
    labels = ctx["site"]["type_labels"]
    brokers = _active_brokers(db)
    by_id = {k.id: k for k in brokers}
    if ids is not None:  # có tham số, kể cả rỗng (`?ids=` = đã bỏ chọn hết): theo đúng lựa chọn
        chosen = []
        for part in ids.split(","):
            n = to_int(part)
            if n in by_id and n not in chosen:
                chosen.append(n)
        chosen = chosen[:3]
    else:
        chosen = [k.id for k in brokers if k.in_compare][:3]
    counts = queries.bonus_count_by_broker(db)

    def url_for(sel: list[int]) -> str:
        return "/san/so-sanh?ids=" + ",".join(map(str, sel)) if sel else "/san/so-sanh?ids="

    pick = []
    for k in brokers:
        on = k.id in chosen
        target = [i for i in chosen if i != k.id] if on else chosen + [k.id]
        pick.append({"id": k.id, "name": k.name, "selected": on,
                     "url": url_for(target) if (on or len(chosen) < 3) else None})
    cols = [queries.broker_view(by_id[i], labels, counts.get(i, 0)) for i in chosen]
    ctx["crumbs"] += [_crumb(ctx, "san", "/san"), _crumb(ctx, "compare", "/san/so-sanh")]
    ctx.update(tabs=_broker_tabs(brokers, "compare"), compare_pick=pick, compare_brokers=cols,
               compare_rows=[{"label": label, "cells": [c[key] for c in cols]} for label, key in COMPARE_ROWS],
               max_compare=3)
    return render(request, "public/broker_compare.html", ctx)


@router.get("/san/{slug}")
def broker_detail(request: Request, slug: str, tab: str = "overview", db: Session = Depends(get_db)):
    k = db.scalar(select(Broker).where(Broker.slug == slug, Broker.is_active.is_(True)))
    if k is None:
        return not_found(request, db)
    tab = tab if tab in dict(BROKER_TABS) else "overview"
    desc = ". ".join(x for x in (k.tagline, f"Thành lập {k.founded}" if k.founded else "") if x)
    ctx = page_ctx(request, db, page_key="san", title=f"Đánh giá {k.name}", desc=(desc + ".") if desc else "")
    ctx["crumbs"] += [_crumb(ctx, "san", "/san"), {"label": k.name, "url": f"/san/{k.slug}"}]
    _canonical(ctx, tab=None if tab == "overview" else tab)
    labels = ctx["site"]["type_labels"]
    bonuses = [queries.bonus_view(b, labels) for b in queries.visible_bonuses(db, sort="value", broker_id=k.id)]
    view = queries.broker_view(k, labels, len(bonuses))
    if k.summary:
        ctx["meta"]["description"] = k.summary[:300]
    ctx.update(
        broker=view, current_tab=tab, bonuses=bonuses,
        tabs=[{"id": t, "label": label, "count": len(bonuses) if t == "bonus" else None,
               "url": f"/san/{k.slug}" + ("" if t == "overview" else f"?tab={t}"), "active": tab == t}
              for t, label in BROKER_TABS],
        facts=[{"label": label, "value": view[key]} for label, key in COMPARE_ROWS[:6]],
    )
    return render(request, "public/broker_detail.html", ctx)


# ---------- tin tức ----------

@router.get("/tin-tuc")
def post_list(request: Request, cat: str = "all", page: int = 1, db: Session = Depends(get_db)):
    cat = cat if cat in POST_CATEGORIES else "all"
    ctx = page_ctx(request, db, page_key="tin")
    counts = dict(db.execute(select(Post.category, func.count()).where(queries.post_public_clause())
                             .group_by(Post.category)).all())
    q = queries.published_posts_query()
    if cat != "all":
        q = q.where(Post.category == cat)
    total = sum(counts.values()) if cat == "all" else counts.get(cat, 0)
    pages = max(1, math.ceil(total / POSTS_PER_PAGE))
    page = min(max(1, page), pages)
    posts = db.scalars(q.offset((page - 1) * POSTS_PER_PAGE).limit(POSTS_PER_PAGE)).all()
    ctx["crumbs"].append(_crumb(ctx, "tin", "/tin-tuc"))
    _canonical(ctx, cat=cat, page=page)
    ctx.update(
        current_cat=cat, posts=[queries.post_view(p) for p in posts],
        tabs=[{"id": "all", "label": "Tất cả", "count": sum(counts.values()), "url": "/tin-tuc", "active": cat == "all"}]
        + [{"id": c, "label": c, "count": counts.get(c, 0), "url": "/tin-tuc" + _qs(cat=c), "active": cat == c}
           for c in POST_CATEGORIES],
        pagination={"page": page, "pages": pages,
                    "prev_url": ("/tin-tuc" + _qs(cat=cat, page=page - 1)) if page > 1 else None,
                    "next_url": ("/tin-tuc" + _qs(cat=cat, page=page + 1)) if page < pages else None},
    )
    return render(request, "public/post_list.html", ctx)


@router.get("/tin-tuc/{slug}")
def post_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Post).where(Post.slug == slug, queries.post_public_clause()))
    if p is None:
        return not_found(request, db)
    if not _is_head(request):
        queries.bump(db, Post, p.id, "views")
        db.commit()
    related = db.scalars(queries.published_posts_query().where(Post.category == p.category, Post.id != p.id).limit(3)).all()
    ctx = page_ctx(request, db, page_key="tin", title=p.title, desc=p.excerpt)
    ctx["crumbs"] += [_crumb(ctx, "tin", "/tin-tuc"), {"label": p.category, "url": "/tin-tuc" + _qs(cat=p.category)}]
    if not p.excerpt:
        ctx["meta"]["description"] = plain_excerpt(p.body_md) or ctx["meta"]["description"]
    if p.cover_path:
        ctx["meta"]["og_image"] = config.base_url + p.cover_path
    ctx.update(post=queries.post_view(p) | {"body_html": render_markdown(p.body_md)},
               related_posts=[queries.post_view(r) for r in related])
    return render(request, "public/post_detail.html", ctx)


# ---------- giới thiệu / liên hệ / pháp lý ----------

def _about_tabs(active: str) -> list[dict]:
    return [{"id": t, "label": label, "count": None, "url": url, "active": t == active} for t, label, url in ABOUT_TABS]


def _about(request: Request, db: Session, tab: str):
    ctx = page_ctx(request, db, page_key="gioithieu" if tab == "about" else tab)
    ctx["crumbs"].append(_crumb(ctx, "gioithieu", "/gioi-thieu"))
    data = ctx["site"]["about_blocks"][tab]
    ctx.update(current_tab=tab, about_image=data.get("image", ""),
               about_blocks=[{"n": f"0{i + 1}.", "title": b.get("title", ""), "text": b.get("text", "")}
                             for i, b in enumerate(data.get("blocks", []))],
               tabs=_about_tabs(tab))
    return render(request, "public/about.html", ctx)


@router.get("/gioi-thieu")
def about(request: Request, db: Session = Depends(get_db)):
    return _about(request, db, "about")


@router.get("/gioi-thieu/cach-danh-gia")
def about_method(request: Request, db: Session = Depends(get_db)):
    return _about(request, db, "method")


@router.get("/gioi-thieu/affiliate")
def about_affiliate(request: Request, db: Session = Depends(get_db)):
    return _about(request, db, "affiliate")


def _contact_ctx(request: Request, db: Session, values: dict | None = None, errors: dict | None = None) -> dict:
    ctx = page_ctx(request, db, page_key="lienhe")
    ctx["crumbs"].append(_crumb(ctx, "lienhe", "/lien-he"))
    ctx["meta"]["canonical"] = config.base_url + "/lien-he"  # còn render lại tại /api/contact khi lỗi
    ctx["current_path"] = "/lien-he"
    ctx["meta"]["noindex"] = bool(errors)
    topics = ctx["site"]["contact_page"]["topics"]
    ctx.update(contact=ctx["site"]["contact_page"],
               tabs=_about_tabs("contact"),
               form={"action": "/api/contact", "data": values or {"topic": topics[0] if topics else "",
                                                                    "name": "", "email": "", "body": ""},
                     "errors": errors or {}})
    return ctx


@router.get("/lien-he")
def contact_page(request: Request, db: Session = Depends(get_db)):
    return render(request, "public/contact.html", _contact_ctx(request, db))


def _legal(request: Request, db: Session, key: str, md_key: str, path: str):
    ctx = page_ctx(request, db, page_key=key)
    ctx["crumbs"].append({"label": ctx["page"]["title"], "url": path})
    ctx["body_html"] = render_markdown(ctx["site"]["legal"][md_key])
    return render(request, "public/legal.html", ctx)


@router.get("/dieu-khoan")
def terms(request: Request, db: Session = Depends(get_db)):
    return _legal(request, db, "terms", "terms_md", "/dieu-khoan")


@router.get("/bao-mat")
def privacy(request: Request, db: Session = Depends(get_db)):
    return _legal(request, db, "privacy", "privacy_md", "/bao-mat")


# ---------- form public ----------

def _clean_email(value: str) -> str | None:
    value = (value or "").strip().lower()
    return value if len(value) <= 255 and EMAIL_RE.match(value) else None


def _send_confirm(sub: Subscriber, site_name: str) -> bool:
    """Địa chỉ chưa xác minh: thân email tuyệt đối không chứa chữ do người gửi form đặt (tên, sở thích...)."""
    confirm = f"{config.base_url}/xac-nhan/{sub.token}"
    return send_email(sub.email, f"Xác nhận đăng ký nhận bonus – {site_name}",
                      f"Chào bạn,\n\nBấm vào liên kết sau để xác nhận nhận email về ưu đãi:\n{confirm}\n\n"
                      "Nếu bạn không đăng ký, hãy bỏ qua email này.",
                      unsubscribe_url=f"{config.base_url}/huy-dang-ky/{sub.token}")


def _may_send_confirm(sub: Subscriber) -> bool:
    if sub.confirm_sent_at is None:
        return True
    age = utcnow() - sub.confirm_sent_at
    if sub.status == "unsubscribed":
        return age >= timedelta(days=UNSUBSCRIBED_RESEND_DAYS)
    return age >= timedelta(days=1) or sub.confirm_count < CONFIRM_EMAILS_PER_DAY


def _note_confirm_sent(sub: Subscriber) -> None:
    now = utcnow()
    if sub.confirm_sent_at is None or now - sub.confirm_sent_at >= timedelta(days=1):
        sub.confirm_sent_at, sub.confirm_count = now, 1
    else:
        sub.confirm_count += 1


@router.post("/api/subscribe")
def subscribe(request: Request, db: Session = Depends(get_db), name: str = Form(""), email: str = Form(""),
              interests: list[str] = Form([]), website: str = Form(""), next: str = Form("/")):
    target = (next if is_local_path(next) else "/").split("#")[0] + "#dang-ky"
    resp = RedirectResponse(target, status_code=303)
    if website.strip():  # honeypot: giả vờ thành công
        return set_flash(resp, "sub_ok")
    key = "sub:" + client_ip(request)
    if public_form_limiter.blocked(key):
        return set_flash(resp, "sub_rate")
    addr = _clean_email(email)
    if addr is None:
        return set_flash(resp, "sub_invalid")
    public_form_limiter.hit(key)
    interests = [t for t in dict.fromkeys(interests) if t in BONUS_TYPES]
    sub = db.scalar(select(Subscriber).where(Subscriber.email == addr))
    if sub is None:
        sub = Subscriber(name=name.strip()[:120], email=addr, interests=interests, status="pending", token=new_token())
        db.add(sub)
    elif sub.status == "confirmed" or not _may_send_confirm(sub):
        return set_flash(resp, "sub_ok")  # không gửi thêm; cùng thông báo để không lộ trạng thái của địa chỉ
    else:
        if sub.status == "unsubscribed":  # đổi token: link trong email cũ không kích hoạt lại được
            sub.status, sub.token = "pending", new_token()
            sub.confirm_sent_at, sub.confirm_count = None, 0
        # Đang chờ xác nhận: giữ token để link trong email trước vẫn dùng được.
        sub.name = name.strip()[:120] or sub.name
        sub.interests = interests
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return set_flash(resp, "sub_ok")
    if not _send_confirm(sub, content.get(db, "site_name")):
        return set_flash(resp, "sub_failed")  # không báo "kiểm tra hộp thư" khi email chưa đi
    _note_confirm_sent(sub)
    db.commit()
    return set_flash(resp, "sub_ok")


def _subscription_result(request: Request, db: Session, status: str, action_url: str | None = None):
    ctx = page_ctx(request, db, system_title=f"sub_{status}_title", desc="", noindex=True)
    ctx["status"], ctx["action_url"] = status, action_url
    return render(request, "public/subscription.html", ctx, status_code=404 if status == "invalid" else 200)


# GET chỉ hiện nút, POST mới đổi trạng thái: máy quét link trong email chỉ gọi GET.
@router.get("/xac-nhan/{token}")
def confirm_page(request: Request, token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None or sub.status == "unsubscribed":
        return _subscription_result(request, db, "invalid")
    if sub.status == "confirmed":
        return _subscription_result(request, db, "confirmed")
    return _subscription_result(request, db, "ask_confirm", f"/xac-nhan/{token}")


@router.post("/xac-nhan/{token}")
def confirm_subscription(request: Request, token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None or sub.status == "unsubscribed":
        return _subscription_result(request, db, "invalid")
    if sub.status == "pending":
        sub.status, sub.confirmed_at = "confirmed", utcnow()
        db.commit()
    return _subscription_result(request, db, "confirmed")


@router.get("/huy-dang-ky/{token}")
def unsubscribe_page(request: Request, token: str, db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None:
        return _subscription_result(request, db, "invalid")
    if sub.status == "unsubscribed":
        return _subscription_result(request, db, "unsubscribed")
    return _subscription_result(request, db, "ask_unsubscribe", f"/huy-dang-ky/{token}")


@router.post("/huy-dang-ky/{token}")
def unsubscribe(request: Request, token: str, db: Session = Depends(get_db)):
    """Cũng là đích one-click của List-Unsubscribe-Post (RFC 8058)."""
    sub = db.scalar(select(Subscriber).where(Subscriber.token == token))
    if sub is None:
        return _subscription_result(request, db, "invalid")
    sub.status = "unsubscribed"
    db.commit()
    return _subscription_result(request, db, "unsubscribed")


@router.post("/api/contact")
def contact_submit(request: Request, db: Session = Depends(get_db), topic: str = Form(""), name: str = Form(""),
                   email: str = Form(""), body: str = Form(""), website: str = Form("")):
    if website.strip():
        return set_flash(RedirectResponse("/lien-he", status_code=303), "contact_ok")
    values = {"topic": topic.strip(), "name": name.strip(), "email": email.strip(), "body": body.strip()}
    key = "contact:" + client_ip(request)
    if public_form_limiter.blocked(key):
        return render(request, "public/contact.html",
                      _contact_ctx(request, db, values, {"form": "Bạn gửi quá nhiều tin nhắn, vui lòng thử lại sau ít phút."}),
                      status_code=429)
    errors = {}
    addr = _clean_email(email)
    if addr is None:
        errors["email"] = "Vui lòng nhập email hợp lệ."
    if values["topic"] and values["topic"] not in content.get(db, "contact_page")["topics"]:
        errors["topic"] = "Vui lòng chọn chủ đề trong danh sách."
    if len(values["name"]) > 120:
        errors["name"] = "Tên tối đa 120 ký tự."
    if not values["body"]:
        errors["body"] = "Vui lòng nhập nội dung."
    elif len(values["body"]) > 5000:
        errors["body"] = "Nội dung tối đa 5000 ký tự."
    if errors:
        return render(request, "public/contact.html", _contact_ctx(request, db, values, errors), status_code=400)
    public_form_limiter.hit(key)
    db.add(ContactMessage(topic=values["topic"], name=values["name"], email=addr, body=values["body"]))
    db.commit()
    return set_flash(RedirectResponse("/lien-he", status_code=303), "contact_ok")


# ---------- beacon + chuyển hướng affiliate ----------

@router.post("/api/ad-view/{banner_id}", status_code=204)
def ad_view(banner_id: int, request: Request, db: Session = Depends(get_db)):
    """FE gọi bằng navigator.sendBeacon khi quảng cáo dọc thật sự hiển thị (rail ẩn dưới 1572px)."""
    key = "view:" + client_ip(request)
    if ad_view_limiter.blocked(key):
        return Response(status_code=204)
    b = db.get(Banner, banner_id)
    if b is None or b.placement not in queries.RAIL_PLACEMENTS or queries.banner_state(b) != "running":
        raise HTTPException(404)
    ad_view_limiter.hit(key)
    queries.bump(db, Banner, b.id, "views")
    db.commit()
    return Response(status_code=204)


@router.get("/go/broker/{broker_id}")
def go_broker(broker_id: int, db: Session = Depends(get_db)):
    k = db.get(Broker, broker_id)
    if k is None or not k.is_active or not is_http_url(k.affiliate_url):
        raise HTTPException(404)
    queries.bump(db, Broker, k.id, "clicks")
    queries.log_click(db, "broker", k.id)
    db.commit()
    return RedirectResponse(k.affiliate_url, status_code=302, headers={"X-Robots-Tag": "noindex, nofollow"})


@router.get("/go/ad/{banner_id}")
def go_ad(banner_id: int, db: Session = Depends(get_db)):
    b = db.get(Banner, banner_id)
    if b is None or queries.banner_state(b) != "running":
        raise HTTPException(404)
    target = queries.banner_target(b)
    queries.bump(db, Banner, b.id, "clicks")
    queries.log_click(db, "ad", b.id)
    db.commit()
    return RedirectResponse(target, status_code=302, headers={"X-Robots-Tag": "noindex, nofollow"})


# ---------- SEO / hệ thống ----------

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (f"User-agent: *\nDisallow: /admin\nDisallow: /go/\nDisallow: /api/\n"
            f"Disallow: /xac-nhan/\nDisallow: /huy-dang-ky/\nSitemap: {config.base_url}/sitemap.xml\n")


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)):
    urls = [("/", None), ("/bonus", None), ("/san", None), ("/san/so-sanh", None), ("/tin-tuc", None),
            ("/gioi-thieu", None), ("/gioi-thieu/cach-danh-gia", None), ("/gioi-thieu/affiliate", None),
            ("/lien-he", None), ("/dieu-khoan", None), ("/bao-mat", None)]
    urls += [(f"/san/{k.slug}", k.updated_at) for k in db.scalars(select(Broker).where(Broker.is_active.is_(True)))]
    urls += [(f"/tin-tuc/{p.slug}", p.updated_at) for p in db.scalars(queries.published_posts_query())]
    items = "".join(
        f"<url><loc>{escape(config.base_url + u)}</loc>" + (f"<lastmod>{d.date().isoformat()}</lastmod>" if d else "") + "</url>"
        for u, d in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
    return Response(xml, media_type="application/xml")


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "time": datetime.now().isoformat(timespec="seconds")}

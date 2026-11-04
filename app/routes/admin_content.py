"""Quản trị nội dung: Trang chủ, Trang, Thư viện ảnh, Cài đặt (gồm tài khoản quản trị)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app import content, uploads
from app.models import ROLES, AdminUser, MediaFile
from app.routes.admin_base import (Admin, _tab, admin_get, admin_post, done, get_or_404, media_library, render_admin,
                                   require_admin_role, subtabs)
from app.security import SESSION_COOKIE, hash_password, is_http_url, is_link, revoke_sessions
from app.utils import EMAIL_RE

router = APIRouter()

HOME_TABS = (("sections", "Section"), ("hero", "Hero"), ("about", "Về chúng tôi"), ("why", "Tại sao chọn"),
             ("types", "Loại bonus"), ("contact", "Liên hệ"), ("menu", "Menu & chân trang"))
PAGE_TABS = (("bonus", "Bonus"), ("san", "Sàn"), ("tin", "Tin tức"), ("gioithieu", "Giới thiệu"), ("lienhe", "Liên hệ"),
             ("terms", "Điều khoản"), ("privacy", "Bảo mật"), ("system", "Chữ hệ thống"))
PAGE_URLS = {"bonus": "/bonus", "san": "/san", "tin": "/tin-tuc", "gioithieu": "/gioi-thieu", "lienhe": "/lien-he",
             "terms": "/dieu-khoan", "privacy": "/bao-mat", "system": "/"}
SETTINGS_TABS = (("general", "Chung"), ("seo", "SEO"), ("social", "Mạng xã hội"), ("tracking", "Tracking"),
                 ("users", "Tài khoản quản trị"))
# Chỉ các tab có ô ảnh mới nhận media_library.
HOME_IMAGE_TABS = ("hero", "about", "why", "types", "contact")
PAGE_IMAGE_TABS = ("gioithieu",)
SETTINGS_IMAGE_TABS = ("general", "seo")
HOME_VIEW = {"sections": "/", "hero": "/", "about": "/", "why": "/", "types": "/", "contact": "/#dang-ky", "menu": "/"}


def _check_links(rows: list[dict], errors: dict, field: str) -> None:
    bad = [r["url"] for r in rows if r.get("url") and not is_link(r["url"])]
    if bad:
        errors[field] = "Link không hợp lệ: " + ", ".join(bad[:3])


# ======================= TRANG CHỦ =======================

def _home_page(a: Admin, tab: str, errors: dict | None = None, values: dict | None = None, status_code=200):
    tab = _tab(tab, HOME_TABS)
    s = content.get_all(a.db)
    sections = [sec | {"n": f"{i + 1:02d}", "toggle_url": f"/admin/home/sections/{sec['id']}/toggle",
                       "move_url": f"/admin/home/sections/{sec['id']}/move", "first": i == 0,
                       "last": i == len(s["sections"]) - 1} for i, sec in enumerate(s["sections"])]
    return render_admin(
        a, "admin/home.html", "home", "Nội dung trang chủ", status_code,
        subtabs=subtabs("/admin/home", HOME_TABS, tab), current_tab=tab, settings=s, sections=sections,
        form={"action": f"/admin/home/{tab}", "data": values or {}, "errors": errors or {}},
        view_url=HOME_VIEW[tab], media_library=media_library(a.db) if tab in HOME_IMAGE_TABS else [])


@router.get("/home")
def home_get(tab: str = "sections", a: Admin = Depends(admin_get)):
    return _home_page(a, tab)


@router.post("/home/sections/{sid}/toggle")
def home_section_toggle(sid: str, a: Admin = Depends(admin_post)):
    sections = content.get(a.db, "sections")
    if sid not in {x["id"] for x in sections}:
        raise HTTPException(404)
    content.put(a.db, "sections", [x | {"on": not x["on"]} if x["id"] == sid else x for x in sections])
    a.db.commit()
    return done("/admin/home?tab=sections", "toggled")


@router.post("/home/sections/{sid}/move")
def home_section_move(sid: str, a: Admin = Depends(admin_post)):
    """Trường `direction`: up | down."""
    sections = content.get(a.db, "sections")
    ids = [x["id"] for x in sections]
    if sid not in ids:
        raise HTTPException(404)
    i = ids.index(sid)
    j = i - 1 if a.text("direction") == "up" else i + 1
    if 0 <= j < len(sections):
        sections[i], sections[j] = sections[j], sections[i]
        content.put(a.db, "sections", sections)
        a.db.commit()
    return done("/admin/home?tab=sections")


def _text_fields(a: Admin, current: dict, names: tuple[str, ...], long: tuple[str, ...] = ()) -> dict:
    return current | {n: (a.long_text(n) if n in long else a.text(n, 1000)) for n in names}


def _images(a: Admin, errors: dict, current: list, count: int) -> list[str]:
    cur = (list(current) + [""] * count)[:count]
    return [a.image(f"image_{i}", errors, cur[i]) for i in range(count)]


@router.post("/home/{tab}")
def home_save(tab: str, a: Admin = Depends(admin_post)):
    if tab not in dict(HOME_TABS):
        raise HTTPException(404)
    s, errors, updates, parsed = content.get_all(a.db), {}, {}, {}
    if tab == "sections":  # tiêu đề các section có dữ liệu
        for key in ("home_bonus", "home_compare", "home_blog"):
            prefix = key.split("_", 1)[1]
            updates[key] = s[key] | {"eyebrow": a.text(f"{prefix}_eyebrow"), "title": a.text(f"{prefix}_title")}
    elif tab == "hero":
        hero = _text_fields(a, s["hero"], ("eyebrow", "headline", "sub", "cta"), ("sub",))
        hero["image_path"] = a.image("image_path", errors, s["hero"]["image_path"])
        hero["card_label"] = a.keep("card_label", s["hero"]["card_label"], 120)
        updates["hero"] = hero
    elif tab == "about":
        about = _text_fields(a, s["home_about"], ("eyebrow", "title", "text", "badge", "count_label"), ("text",))
        about["points"] = parsed["points"] = a.rows("point", ("title", "text"))
        about["images"] = _images(a, errors, s["home_about"]["images"], 3)
        updates["home_about"] = about
    elif tab == "why":
        why = _text_fields(a, s["home_why"], ("eyebrow", "title", "text", "stat_value", "stat_label"), ("text",))
        why["reasons"] = parsed["reasons"] = a.rows("reason", ("title", "text"))
        why["images"] = _images(a, errors, s["home_why"]["images"], 2)
        updates["home_why"] = why
    elif tab == "types":
        types = _text_fields(a, s["home_types"], ("eyebrow", "title"))
        types["image"] = a.image("image", errors, s["home_types"]["image"])
        updates["home_types"] = types
        bonus_types = []
        for t in s["bonus_types"]:
            i = t["id"]
            row = {"id": i, "short": a.text(f"{i}_short", 60) or t["short"], "label": a.text(f"{i}_label", 120) or t["label"],
                   "desc": a.text(f"{i}_desc", 1000), "points": a.lines(f"{i}_points")}
            bonus_types.append(row)
        updates["bonus_types"] = bonus_types
    elif tab == "contact":
        c = _text_fields(a, s["home_contact"], ("eyebrow", "title", "text", "success_title", "success_text"))
        c["image"] = a.image("image", errors, s["home_contact"]["image"])
        updates["home_contact"] = c
    elif tab == "menu":
        menu = a.rows("menu", ("label", "url"))
        _check_links(menu, errors, "menu")
        columns = parsed["columns"] = []
        parsed["menu"] = menu
        titles, links = a.many("footer_col_title", 120), a.many("footer_col_links", 5000)
        for i, title in enumerate(titles):
            rows = []
            for line in (links[i] if i < len(links) else "").splitlines():
                if line.strip():
                    label, _, url = line.partition("|")
                    rows.append({"label": label.strip(), "url": url.strip()})
            if title or rows:
                _check_links(rows, errors, "footer_col_links")
                columns.append({"title": title, "links": rows})
        updates["menu"] = menu
        updates["footer"] = s["footer"] | {"about_text": a.text("about_text", 2000), "risk_note": a.text("risk_note", 2000),
                                           "copyright": a.text("copyright", 500), "columns": columns,
                                           "affiliate_note": a.keep("affiliate_note", s["footer"]["affiliate_note"], 500)}
        updates["cta_note"] = a.keep("cta_note", s["cta_note"], 500)
        updates["ads_note"] = a.keep("ads_note", s["ads_note"], 500)
    if errors:
        return _home_page(a, tab, errors, values=a.form_data(**parsed), status_code=400)
    for k, v in updates.items():
        content.put(a.db, k, v)
    a.db.commit()
    return done(f"/admin/home?tab={tab}")


# ======================= TRANG =======================

def _pages_page(a: Admin, tab: str, errors: dict | None = None, values: dict | None = None, status_code=200):
    tab = _tab(tab, PAGE_TABS)
    return render_admin(
        a, "admin/pages.html", "pages", "Trang", status_code,
        subtabs=subtabs("/admin/pages", PAGE_TABS, tab), current_tab=tab, settings=content.get_all(a.db),
        form={"action": f"/admin/pages/{tab}", "data": values or {}, "errors": errors or {}}, view_url=PAGE_URLS[tab],
        about_tabs=[{"id": "about", "label": "Về chúng tôi"}, {"id": "method", "label": "Cách đánh giá"},
                    {"id": "affiliate", "label": "Công bố affiliate"}],
        media_library=media_library(a.db) if tab in PAGE_IMAGE_TABS else [])


@router.get("/pages")
def pages_get(tab: str = "bonus", a: Admin = Depends(admin_get)):
    return _pages_page(a, tab)


@router.post("/pages/{tab}")
def pages_save(tab: str, a: Admin = Depends(admin_post)):
    if tab not in dict(PAGE_TABS):
        raise HTTPException(404)
    s, errors = content.get_all(a.db), {}
    if tab == "system":  # không có tiêu đề/SEO riêng, chỉ các chữ hệ thống
        content.put(a.db, "system_text", {k: a.keep(k, v, 500) for k, v in s["system_text"].items()})
        a.db.commit()
        return done("/admin/pages?tab=system")
    pages = s["pages"]
    pages[tab] = {"title": a.text("title"), "desc": a.text("desc", 1000), "meta_title": a.text("meta_title"),
                  "meta_desc": a.text("meta_desc", 500)}
    if not pages[tab]["title"]:
        errors["title"] = "Nhập tiêu đề trang."
    updates, parsed = {"pages": pages}, {}
    if tab == "gioithieu":
        blocks = {}
        for key in content.ABOUT_TABS:
            blocks[key] = {"image": a.image(f"{key}_image", errors, s["about_blocks"][key].get("image", "")),
                           "blocks": a.rows(f"{key}_block", ("title", "text"))}
        updates["about_blocks"] = parsed["about_blocks"] = blocks
    elif tab == "lienhe":
        updates["contact_page"] = {"intro": a.text("intro", 2000), "topics": a.lines("topics"),
                                   "response_note": a.text("response_note", 1000),
                                   "success_title": a.keep("success_title", s["contact_page"]["success_title"], 120),
                                   "success_text": a.text("success_text", 1000)}
    elif tab in ("terms", "privacy"):
        updates["legal"] = s["legal"] | {f"{tab}_md": a.long_text("body_md")}
    if errors:
        return _pages_page(a, tab, errors, a.form_data(**parsed), 400)
    for k, v in updates.items():
        content.put(a.db, k, v)
    a.db.commit()
    return done(f"/admin/pages?tab={tab}")


# ======================= THƯ VIỆN ẢNH =======================

def _media_page(a: Admin, q: str = "", errors: dict | None = None, status_code=200):
    stmt = select(MediaFile).order_by(MediaFile.created_at.desc(), MediaFile.id.desc())
    if q.strip():
        stmt = stmt.where(MediaFile.alt.ilike(f"%{q.strip()}%"))
    used = uploads.used_text(a.db)
    items = [{"id": m.id, "path": m.path, "alt": m.alt, "width": m.width, "height": m.height, "size": m.size,
              "created_at": m.created_at, "in_use": m.path in used,
              "edit_url": f"/admin/media/{m.id}/edit", "delete_url": f"/admin/media/{m.id}/delete"}
             for m in a.db.scalars(stmt)]
    return render_admin(a, "admin/media.html", "media", "Thư viện ảnh", status_code, q=q, media=items,
                        upload_action="/admin/media/upload", errors=errors or {})


@router.get("/media")
def media_get(q: str = "", a: Admin = Depends(admin_get)):
    return _media_page(a, q)


@router.post("/media/upload")
def media_upload(a: Admin = Depends(admin_post)):
    """Trường `files` (một hoặc nhiều file) + `alt`."""
    files = [f for f in a.form.getlist("files") if isinstance(f, UploadFile) and uploads.has_file(f)]
    if not files:
        return _media_page(a, errors={"files": "Chọn ít nhất một ảnh."}, status_code=400)
    for f in files:
        try:
            uploads.save_image(a.db, f, a.text("alt"))
            a.db.commit()
        except uploads.UploadError as e:  # các ảnh trước đó đã được lưu
            return _media_page(a, errors={"files": f"{f.filename}: {e}"}, status_code=400)
    return done("/admin/media", "uploaded")


@router.post("/media/{mid}/edit")
def media_edit(mid: int, a: Admin = Depends(admin_post)):
    m = get_or_404(a.db, MediaFile, mid)
    m.alt = a.text("alt")
    a.db.commit()
    return done("/admin/media")


@router.post("/media/{mid}/delete")
def media_delete(mid: int, a: Admin = Depends(admin_post)):
    m = get_or_404(a.db, MediaFile, mid)
    if uploads.is_in_use(a.db, m.path):
        return done("/admin/media", "media_in_use")
    uploads.delete_file(m)
    a.db.delete(m)
    a.db.commit()
    return done("/admin/media", "deleted")


# ======================= CÀI ĐẶT =======================

def _settings_page(a: Admin, tab: str, errors: dict | None = None, values: dict | None = None, status_code=200,
                   errors_user_id: int | None = None):
    tab = _tab(tab, SETTINGS_TABS)
    users = [{"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active, "last_login_at": u.last_login_at,
              "is_self": u.id == a.user.id, "edit_url": f"/admin/settings/users/{u.id}/edit",
              "toggle_url": f"/admin/settings/users/{u.id}/toggle", "delete_url": f"/admin/settings/users/{u.id}/delete"}
             for u in a.db.scalars(select(AdminUser).order_by(AdminUser.created_at))] if tab == "users" else []
    return render_admin(
        a, "admin/settings.html", "settings", "Cài đặt", status_code,
        subtabs=subtabs("/admin/settings", SETTINGS_TABS, tab), current_tab=tab, settings=content.get_all(a.db),
        form={"action": f"/admin/settings/{tab}", "data": values or {}, "errors": errors or {},
              "errors_user_id": errors_user_id}, users=users,
        role_options=[{"id": "admin", "label": "Quản trị"}, {"id": "editor", "label": "Biên tập"}],
        user_create_action="/admin/settings/users/new", media_library=media_library(a.db) if tab in SETTINGS_IMAGE_TABS else [])


@router.get("/settings")
def settings_get(tab: str = "general", a: Admin = Depends(admin_get)):
    require_admin_role(a)
    return _settings_page(a, tab)


@router.post("/settings/users/new")
def user_create(a: Admin = Depends(admin_post)):
    require_admin_role(a)
    email, password, role = a.text("email").lower(), a.text("password", 200), a.text("role")
    errors = {}
    if not EMAIL_RE.match(email):
        errors["email"] = "Email không hợp lệ."
    elif a.db.scalar(select(AdminUser.id).where(AdminUser.email == email)):
        errors["email"] = "Email đã tồn tại."
    if len(password) < 10:
        errors["password"] = "Mật khẩu tối thiểu 10 ký tự."
    if role not in ROLES:
        errors["role"] = "Chọn vai trò."
    if errors:
        return _settings_page(a, "users", errors, a.form_data(), 400)
    a.db.add(AdminUser(email=email, password_hash=hash_password(password), role=role))
    a.db.commit()
    return done("/admin/settings?tab=users", "created")


@router.post("/settings/users/{uid}/edit")
def user_edit(uid: int, a: Admin = Depends(admin_post)):
    """Đổi vai trò (`role`) và/hoặc mật khẩu (`password`, để trống = giữ nguyên)."""
    require_admin_role(a)
    u = get_or_404(a.db, AdminUser, uid)
    role, password = a.text("role"), a.text("password", 200)
    errors = {}
    if role and role not in ROLES:
        errors["edit_role"] = "Vai trò không hợp lệ."
    if role and role != "admin" and u.id == a.user.id:
        errors["edit_role"] = "Không thể tự hạ quyền tài khoản đang đăng nhập."
    if password and len(password) < 10:
        errors["edit_password"] = "Mật khẩu tối thiểu 10 ký tự."
    if errors:  # khóa edit_* + errors_user_id: tách khỏi lỗi của form thêm tài khoản
        return _settings_page(a, "users", errors, status_code=400, errors_user_id=u.id)
    if role:
        u.role = role
    if password:
        u.password_hash = hash_password(password)
        # đăng xuất các phiên cũ (giữ phiên đang thao tác nếu tự đổi mật khẩu)
        revoke_sessions(a.db, u.id, a.request.cookies.get(SESSION_COOKIE) if u.id == a.user.id else None)
    a.db.commit()
    return done("/admin/settings?tab=users")


@router.post("/settings/users/{uid}/toggle")
def user_toggle(uid: int, a: Admin = Depends(admin_post)):
    require_admin_role(a)
    u = get_or_404(a.db, AdminUser, uid)
    if u.id == a.user.id:
        return done("/admin/settings?tab=users", "self_delete")
    u.is_active = not u.is_active
    a.db.commit()
    return done("/admin/settings?tab=users", "toggled")


@router.post("/settings/users/{uid}/delete")
def user_delete(uid: int, a: Admin = Depends(admin_post)):
    require_admin_role(a)
    u = get_or_404(a.db, AdminUser, uid)
    if u.id == a.user.id:
        return done("/admin/settings?tab=users", "self_delete")
    a.db.delete(u)
    a.db.commit()
    return done("/admin/settings?tab=users", "deleted")


@router.post("/settings/{tab}")
def settings_save(tab: str, a: Admin = Depends(admin_post)):
    require_admin_role(a)
    if tab not in dict(SETTINGS_TABS) or tab == "users":
        raise HTTPException(404)
    s, errors, updates, parsed = content.get_all(a.db), {}, {}, {}
    if tab == "general":
        updates = {"site_name": a.text("site_name", 120), "contact_email": a.text("contact_email").lower(),
                   "partner_email": a.text("partner_email").lower(), "telegram": a.text("telegram", 120)}
        if not updates["site_name"]:
            errors["site_name"] = "Nhập tên website."
        for k in ("contact_email", "partner_email"):
            if updates[k] and not EMAIL_RE.match(updates[k]):
                errors[k] = "Email không hợp lệ."
        updates["branding"] = s["branding"] | {
            "logo_path": a.image("logo_path", errors, s["branding"]["logo_path"]),
            "favicon_path": a.image("favicon_path", errors, s["branding"]["favicon_path"])}
    elif tab == "seo":
        updates = {"meta_title": a.text("meta_title"), "meta_desc": a.text("meta_desc", 500),
                   "meta_keywords": a.text("meta_keywords", 500)}
        updates["branding"] = s["branding"] | {"og_image": a.image("og_image", errors, s["branding"]["og_image"])}
    elif tab == "social":
        social = a.rows("social", ("label", "url"))
        bad = [r["url"] for r in social if not is_http_url(r["url"])]
        if bad:
            errors["social"] = "Link mạng xã hội phải là http(s): " + ", ".join(bad[:3])
        updates, parsed = {"social": social}, {"social": social}
    elif tab == "tracking":
        updates = {"analytics_head": a.long_text("analytics_head")[:20000]}
    if errors:
        return _settings_page(a, tab, errors, a.form_data(**parsed), 400)
    for k, v in updates.items():
        content.put(a.db, k, v)
    a.db.commit()
    return done(f"/admin/settings?tab={tab}")

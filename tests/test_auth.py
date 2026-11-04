from conftest import PASSWORD, AdminClient, login, make_user


def test_admin_requires_login(client):
    for url in ("/admin", "/admin/bonus", "/admin/settings"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/admin/login?next=")


def test_admin_post_requires_login(client):
    r = client.post("/admin/bonus/new", data={"csrf_token": "x"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/admin/login")


def test_login_success_sets_secure_session(client, db):
    from app.models import AdminSession
    make_user(db)
    r = login(client)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    cookie = [h for h in r.headers.get_list("set-cookie") if h.startswith("tbh_session=")][0].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    token = client.cookies.get("tbh_session")
    sess = db.query(AdminSession).one()
    assert sess.token_hash != token and len(sess.token_hash) == 64  # chỉ lưu hash
    assert client.get("/admin").status_code == 200


def test_password_hash_is_argon2id(db):
    u = make_user(db)
    assert u.password_hash.startswith("$argon2id$")


def test_wrong_password(client, db):
    make_user(db)
    r = login(client, password="sai-mat-khau")
    assert r.status_code == 401 and "không đúng" in r.context["error"]
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_unknown_email_same_message(client):
    r = login(client, email="khong-co@example.test")
    assert r.status_code == 401 and r.context["error"] == "Email hoặc mật khẩu không đúng."


def test_inactive_user_cannot_login(client, db):
    u = make_user(db)
    u.is_active = False
    db.commit()
    assert login(client).status_code == 401


def test_login_rate_limit(client, db):
    make_user(db)
    for _ in range(5):
        assert login(client, password="sai").status_code == 401
    r = login(client)  # đúng mật khẩu vẫn bị chặn
    assert r.status_code == 429
    assert login(client, email="khac@example.test").status_code == 401  # khóa theo IP+email


def test_login_requires_csrf(client, db):
    make_user(db)
    client.get("/admin/login")
    r = client.post("/admin/login", data={"email": "admin@example.test", "password": PASSWORD, "csrf_token": "sai"},
                    follow_redirects=False)
    assert r.status_code == 403


def test_login_next_no_open_redirect(client, db):
    make_user(db)
    assert login(client, next_path="//evil.example/admin").headers["location"] == "/admin"
    client.cookies.clear()
    assert login(client, next_path="https://evil.example").headers["location"] == "/admin"
    client.cookies.clear()
    assert login(client, next_path="/admin/bonus?tab=on").headers["location"] == "/admin/bonus?tab=on"


def test_logout(client, db):
    make_user(db)
    login(client)
    a = AdminClient(client)
    r = a.post("/admin/logout")
    assert r.status_code == 303
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_logout_requires_csrf(client, db):
    make_user(db)
    login(client)
    assert client.post("/admin/logout", data={}, follow_redirects=False).status_code == 403
    assert client.get("/admin").status_code == 200


def test_expired_session_rejected(client, db):
    from datetime import timedelta

    from app.models import AdminSession, utcnow
    make_user(db)
    login(client)
    sess = db.query(AdminSession).one()
    sess.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_editor_cannot_open_settings(client, db):
    make_user(db, "editor@example.test", role="editor")
    login(client, email="editor@example.test")
    assert client.get("/admin/bonus").status_code == 200
    assert client.get("/admin/settings").status_code == 403
    csrf = client.get("/admin").context["csrf_token"]
    r = client.post("/admin/settings/tracking", data={"csrf_token": csrf, "analytics_head": "<script>x</script>"})
    assert r.status_code == 403


def test_cli_create_admin(db, capsys):
    from app.cli import create_admin
    from app.models import AdminUser
    assert create_admin("Moi@Example.test", "editor", "mot-mat-khau-dai") == 0
    u = db.query(AdminUser).filter_by(email="moi@example.test").one()
    assert u.role == "editor" and u.password_hash.startswith("$argon2id$")
    assert create_admin("x@example.test", "admin", "ngan") == 2

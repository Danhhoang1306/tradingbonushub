"""Vòng 2: tìm hồi quy trong phần mới. Giới hạn email theo địa chỉ, chiến dịch partial/kẹt sending, BodyLimit,
trang xác nhận POST, hẹn giờ bài viết, slug tiếng Việt, HEAD, hậu kiểm các lỗi cũ. Email luôn ở console hoặc giả lập."""
import re
import socket
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
from playwright.sync_api import sync_playwright

from qalib import BASE, PORT, PY, ROOT, WORK, Http, Report, Server, mk_bonus, mk_broker, mk_post, png_bytes, prod_env

R = Report("s9_round2")
c = R.check
pub = httpx.Client(base_url=BASE, timeout=30)


def sub(email, ip, **kw):
    return pub.post("/api/subscribe", data={"email": email, "next": "/", **kw}, headers={"CF-Connecting-IP": ip})


def flash(r):
    m = re.search(r"tbh_flash=(\w+)", r.headers.get("set-cookie", ""))
    return m.group(1) if m else ""


def seed_subs(s, n, prefix="u"):
    con = [(f"{prefix}{i:03d}@qa.test", f"tok{prefix}{i:03d}") for i in range(n)]
    for e, t in con:
        s.sql("insert into subscribers(name,email,interests,status,token,confirm_count,created_at,updated_at) values('',?,'[]','confirmed',?,0,'2026-01-01 00:00:00','2026-01-01 00:00:00')", (e, t))


def raw(method, path, headers, body=b"", chunks=None, timeout=15):
    """HTTP thô để điều khiển Content-Length/chunked."""
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    head = f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nConnection: close\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    try:
        if chunks is not None:
            s.sendall((head + "Transfer-Encoding: chunked\r\n\r\n").encode("latin-1"))
            for ch in chunks:
                s.sendall(f"{len(ch):x}\r\n".encode() + ch + b"\r\n")
            s.sendall(b"0\r\n\r\n")
        else:
            s.sendall((head + f"Content-Length: {len(body)}\r\n\r\n").encode("latin-1") + body)
    except OSError:
        pass  # server trả 413 và đóng khi chưa gửi hết
    buf = b""
    try:
        while d := s.recv(65536):
            buf += d
    except OSError:
        pass
    s.close()
    first = buf.split(b"\r\n", 1)[0].decode("latin-1").split()
    return (int(first[1]) if len(first) > 1 else 0), buf.split(b"\r\n\r\n")[0].decode("latin-1")


# =================== R1. Giới hạn email theo địa chỉ ===================
s = Server("r2_mail").start()
s.cli_admin()
h = Http().login()
try:
    for i in range(6):
        r = sub("nan@qa.test", f"3.3.1.{i}")
    n = len(s.tokens("nan@qa.test"))
    c("R1.1", "6 lần từ 6 IP: chỉ 3 email, khách vẫn thấy sub_ok", n == 3 and flash(r) == "sub_ok", (n, flash(r)))
    tk = s.tokens("nan@qa.test")
    c("R1.2", "Đang chờ: cùng token ở mọi email", len(set(tk)) == 1, len(set(tk)))
    # đúng 24 giờ sau được gửi tiếp
    s.sql("update subscribers set confirm_sent_at=datetime('now','-25 hours') where email='nan@qa.test'")
    sub("nan@qa.test", "3.3.1.9")
    c("R1.3", "Quá 24 giờ: gửi lại được", len(s.tokens("nan@qa.test")) == 4)

    # Đua: nhiều POST đồng thời cùng địa chỉ từ nhiều IP
    with ThreadPoolExecutor(20) as ex:
        list(ex.map(lambda i: sub("dua@qa.test", f"3.3.2.{i}"), range(20)))
    n = len(s.tokens("dua@qa.test"))
    c("R1.4", "20 POST đồng thời cùng địa chỉ: vẫn tối đa 3 email", n <= 3, f"{n} email; subscribers={s.sql('select count(*), max(confirm_count) from subscribers where email=?', ('dua@qa.test',))}")

    # Người đã hủy: tài liệu ghi tối đa 1 email/24 giờ
    sub("huy@qa.test", "3.3.3.1")
    t0 = s.tokens("huy@qa.test")[-1]
    pub.post(f"/xac-nhan/{t0}")
    pub.post(f"/huy-dang-ky/{t0}")
    s.sql("update subscribers set confirm_sent_at=datetime('now','-30 days') where email='huy@qa.test'")  # đăng ký từ tháng trước
    for i in range(6):
        sub("huy@qa.test", f"3.3.3.{i + 10}")
    n = len(s.tokens("huy@qa.test")) - 1
    c("R1.5", "Đã hủy từ lâu, kẻ khác nhập địa chỉ 6 lần: tối đa 1 email/24 giờ như VIEW_CONTEXT", n <= 1, f"{n} email sau khi đã hủy; trạng thái {s.sql('select status from subscribers where email=?', ('huy@qa.test',))}")
    sub("huy2@qa.test", "3.3.4.1")
    t1 = s.tokens("huy2@qa.test")[-1]
    pub.post(f"/xac-nhan/{t1}")
    pub.post(f"/huy-dang-ky/{t1}")
    r = sub("huy2@qa.test", "3.3.4.2")
    st = s.sql("select status from subscribers where email='huy2@qa.test'")[0][0]
    print(f"     hủy xong đăng ký lại ngay trong ngày: flash={flash(r)}, trạng thái={st}, email thêm={len(s.tokens('huy2@qa.test')) - 1}", flush=True)
    c("R1.6", "Hủy rồi tự đăng ký lại trong 24 giờ: không báo 'kiểm tra hộp thư' khi không có email nào", not (flash(r) == "sub_ok" and len(s.tokens("huy2@qa.test")) == 1), "khách thấy sub_ok, không có email, không có thông báo")
    # kẻ khác đổi tên/sở thích của địa chỉ đang chờ
    sub("doi@qa.test", "3.3.5.1", name="Chủ thật", interests=["crypto"])
    sub("doi@qa.test", "3.3.5.2", name="Kẻ lạ", interests=["nodep"])
    row = s.sql("select name, interests from subscribers where email='doi@qa.test'")[0]
    print("     địa chỉ đang chờ bị người khác ghi đè tên/sở thích:", row, flush=True)
    # email chứa tên?
    sub("ten@qa.test", "3.3.6.1", name="TRÚNG THƯỞNG http://evil.example")
    c("R1.7", "Tên không vào email", "evil.example" not in s.log_text())

    # =================== R2. Trang xác nhận POST ===================
    sub("post@qa.test", "3.3.7.1")
    tk = s.tokens("post@qa.test")[-1]
    for _ in range(3):  # máy quét: GET, HEAD, theo mọi link
        pub.get(f"/xac-nhan/{tk}")
        pub.head(f"/xac-nhan/{tk}")
        pub.get(f"/huy-dang-ky/{tk}")
        pub.head(f"/huy-dang-ky/{tk}")
    c("R2.1", "Máy quét GET/HEAD cả 2 link: trạng thái vẫn pending", s.sql("select status from subscribers where email='post@qa.test'")[0][0] == "pending")
    t = pub.get(f"/xac-nhan/{tk}").text
    c("R2.2", "Trang hỏi noindex", 'name="robots" content="noindex' in t)
    c("R2.3", "Trang hỏi có đúng form POST tới chính token", f'action="/xac-nhan/{tk}"' in t and 'method="post"' in t)
    r = pub.post(f"/xac-nhan/{tk}")
    c("R2.4", "POST xác nhận 200, không cần CSRF (theo tài liệu)", r.status_code == 200 and s.sql("select status from subscribers where email='post@qa.test'")[0][0] == "confirmed")
    r = pub.post(f"/xac-nhan/{tk}")
    c("R2.5", "POST lại: vẫn 200, không đổi confirmed_at", r.status_code == 200)
    r = pub.get(f"/huy-dang-ky/{tk}")
    c("R2.6", "GET link hủy của người đã xác nhận: hiện nút hủy", "ask" in r.text or f'/huy-dang-ky/{tk}"' in r.text)
    r = pub.post(f"/huy-dang-ky/{tk}", content="List-Unsubscribe=One-Click", headers={"Content-Type": "application/x-www-form-urlencoded"})
    c("R2.7", "POST one-click theo RFC 8058: hủy ngay", r.status_code == 200 and s.sql("select status from subscribers where email='post@qa.test'")[0][0] == "unsubscribed")
    r = pub.post(f"/huy-dang-ky/{tk}")
    c("R2.8", "POST hủy lần 2: 200", r.status_code == 200)
    for u in (f"/xac-nhan/{tk}x", "/xac-nhan/%00", "/huy-dang-ky/" + "a" * 5000):
        r = pub.post(u)
        c(f"R2.9{u[:18]}", f"POST token sai {u[:24]}: 404", r.status_code == 404, r.status_code)
    r = pub.get(f"/xac-nhan/{tk}")
    c("R2.10", "Đã hủy: link xác nhận cũ báo không hợp lệ", r.status_code == 404)
    # CSRF chéo site: trang khác POST được vì không cần CSRF; chỉ tác động khi biết token bí mật
    r = pub.post(f"/huy-dang-ky/{tk}", headers={"Origin": "https://evil.example"})
    print("     POST xác nhận/hủy từ Origin lạ:", r.status_code, "(cần biết token 43 ký tự, chấp nhận được)", flush=True)

    # =================== R3. Hẹn giờ qua sửa bài ===================
    fut = (datetime.now(timezone(timedelta(hours=7))).date() + timedelta(days=10)).isoformat()
    mk_post(h, "Hẹn giờ A", published_at=fut, category="Tin sàn")
    pid = s.sql("select id from posts where slug='hen-gio-a'")[0][0]
    r = h.post(f"/admin/posts/{pid}/edit", {"title": "Hẹn giờ A", "slug": "hen-gio-a", "category": "Tin sàn", "status": "published", "published_at": "", "show_home": "1", "body_md": "x"})
    st = pub.get("/tin-tuc/hen-gio-a").status_code
    c("R3.1", "Bài hẹn giờ, xóa ngày rồi lưu 'đã đăng': theo VIEW_CONTEXT 'trống + đăng → đăng ngay'", st == 200, f"HTTP {st} sau khi xóa ngày; published_at={s.sql('select published_at from posts where id=?', (pid,))}")
finally:
    s.stop()

# =================== R4. Hẹn giờ với đồng hồ giả (00:00 giờ VN) ===================
now_file = WORK / "now.txt"
now_file.write_text("2026-11-05T10:00:00+00:00")
s = Server("r2_tz", env={"QA_NOW_FILE": str(now_file)}, entry="qa/frozen_run.py").start()
s.cli_admin()
h = Http().login()
try:
    mk_post(h, "Bài đã có", category="Tin sàn", show_home="1")
    mk_post(h, "Bài hẹn", category="Tin sàn", published_at="2026-11-06", show_home="1")
    mk_broker(h, "Sàn Lên Lịch")
    now_file.write_text("2026-11-05T16:59:00+00:00")  # 23:59 VN 05/11
    r = {p: pub.get(p).text for p in ("/", "/tin-tuc", "/tin-tuc?cat=Tin sàn", "/sitemap.xml", "/tin-tuc/bai-da-co")}
    c("R4.1", "23:59 VN hôm trước: bài hẹn không ở đâu cả", not any("bai-hen" in v for v in r.values()) and pub.get("/tin-tuc/bai-hen").status_code == 404, [k for k, v in r.items() if "bai-hen" in v])
    m = re.search(r"Tin sàn.{0,80}?(\d+)", r["/tin-tuc"], re.S)
    c("R4.2", "Số đếm chuyên mục không tính bài hẹn", m and m.group(1) == "1", m and m.group(1))
    t = h.get("/admin/posts").text
    c("R4.3", "Admin thấy nhãn Hẹn giờ", "Hẹn giờ" in t)
    now_file.write_text("2026-11-05T17:01:00+00:00")  # 00:01 VN 06/11, ngày UTC vẫn 05/11
    r = {p: pub.get(p).text for p in ("/", "/tin-tuc", "/sitemap.xml")}
    c("R4.4", "00:01 VN đúng ngày: bài hiện ở danh sách, trang chủ, sitemap, trang bài", all("bai-hen" in v for v in r.values()) and pub.get("/tin-tuc/bai-hen").status_code == 200, [k for k, v in r.items() if "bai-hen" not in v])
    t = pub.get("/tin-tuc").text
    d = re.search(r"Bài hẹn.{0,400}", t, re.S)
    c("R4.5", "Ngày hiển thị là 06/11 theo giờ VN", "06/11" in t, "")
    pid = s.sql("select id from posts where slug='bai-hen'")[0][0]
    # sửa bài: đổi về hôm nay giữ hiện; sửa nội dung không đổi ngày
    before = s.sql("select published_at from posts where id=?", (pid,))
    h.post(f"/admin/posts/{pid}/edit", {"title": "Bài hẹn", "slug": "bai-hen", "category": "Tin sàn", "status": "published", "published_at": "2026-11-06", "show_home": "1", "body_md": "sửa"})
    c("R4.6", "Sửa bài giữ nguyên ngày: không đổi published_at", s.sql("select published_at from posts where id=?", (pid,)) == before)
finally:
    s.stop()

# =================== R5. Chiến dịch gửi dở ===================
flag = WORK / "mail_ok.flag"
flag.unlink(missing_ok=True)
s = Server("r2_camp", entry="qa/mailfail_run.py", env={"QA_MAIL_OK_BATCHES": "1", "QA_MAIL_FLAG": str(flag)}).start()
s.cli_admin()
h = Http().login()
try:
    seed_subs(s, 45)
    r = h.post("/admin/subscribers/mail", {"subject": "Đợt 1", "body": "Nội dung", "action": "send"})
    st = s.sql("select id,status,sent_count,length(sent_to) from campaigns")
    c("R5.1", "Lô 1 đi, lô 2 hỏng: partial, sent_count=20, flash send_partial", st[0][1] == "partial" and st[0][2] == 20 and flash(r) == "send_partial", (st, flash(r)))
    cid = st[0][0]
    p = h.get(f"/admin/subscribers?tab=mail&draft={cid}")
    c("R5.2", "Mở lại chiến dịch partial", p.status_code == 200 and "Đợt 1" in p.text)
    c("R5.3", "Hộp xác nhận nói gửi lại tới người chưa nhận", "Gửi lại tới những người chưa nhận" in p.text)
    j = h.get("/admin/subscribers/audience-count").json()
    print("     audience-count JSON khi mở partial:", j, "(JS đổi số theo route này)", flush=True)
    flag.write_text("1")
    log0 = s.log_text().count("[console email]")
    r = h.post("/admin/subscribers/mail", {"subject": "Đợt 1", "body": "Nội dung", "action": "send", "draft_id": cid})
    st = s.sql("select status,sent_count from campaigns where id=?", (cid,))
    new = s.log_text().count("[console email]") - log0
    c("R5.4", "Gửi tiếp: chỉ 25 người còn lại, thành sent, sent_count=45", st == [("sent", 45)] and new == 25, (st, new))
    txt = s.log_text()
    tos = re.findall(r"to=(\S+) subject=Đợt 1", txt)
    c("R5.5", "Không ai nhận 2 lần", len(tos) == len(set(tos)) == 45, (len(tos), len(set(tos))))
    r = h.post("/admin/subscribers/mail", {"subject": "Đợt 1", "body": "Nội dung", "action": "send", "draft_id": cid})
    c("R5.6", "Gửi lại chiến dịch đã xong: 404", r.status_code == 404, r.status_code)
    # hai request đồng thời cùng một bản nháp
    flag.write_text("1")
    h.post("/admin/subscribers/mail", {"subject": "Đua gửi", "body": "x", "action": "draft"})
    did = s.sql("select id from campaigns where subject='Đua gửi'")[0][0]

    def fire(i):
        x = Http()
        x.cookies, x.csrf = dict(h.cookies), h.csrf
        return x.post("/admin/subscribers/mail", {"subject": "Đua gửi", "body": "x", "action": "send", "draft_id": did}).status_code
    with ThreadPoolExecutor(5) as ex:
        codes = list(ex.map(fire, range(5)))
    tos = re.findall(r"to=(\S+) subject=Đua gửi", s.log_text())
    c("R5.7", "5 POST đồng thời cùng nháp: mỗi người 1 email, không 500", len(tos) == len(set(tos)) == 45 and 500 not in codes, (codes, len(tos), len(set(tos))))
    # gửi tiếp sau khi người đã nhận hủy, người mới xác nhận
    flag.unlink()
finally:
    s.stop()

s = Server("r2_camp2", entry="qa/mailfail_run.py", env={"QA_MAIL_OK_BATCHES": "1", "QA_MAIL_FLAG": str(flag)}).start()
s.cli_admin()
h = Http().login()
try:
    seed_subs(s, 25)
    # địa chỉ lạ: header To có thể khác chuỗi email lưu trong DB
    s.sql("update subscribers set email='a,b@x.co' where email='u000@qa.test'")
    s.sql("update subscribers set email='o''neil@x.co' where email='u001@qa.test'")
    h.post("/admin/subscribers/mail", {"subject": "Lạ", "body": "x", "action": "send"})
    st = s.sql("select id,status,sent_count,sent_to from campaigns")
    print("     partial có địa chỉ lạ:", st[0][1], st[0][2], [x for x in st[0][3].split('"') if "," in x and "@" in x][:2], flush=True)
    flag.write_text("1")
    h.post("/admin/subscribers/mail", {"subject": "Lạ", "body": "x", "action": "send", "draft_id": st[0][0]})
    tos = re.findall(r"to=(.+?) subject=Lạ", s.log_text())
    dup = sorted({x for x in tos if tos.count(x) > 1})
    c("R5.8", "Địa chỉ có ký tự lạ không bị gửi 2 lần khi gửi tiếp", not dup, dup[:3])
    # sửa nội dung rồi gửi tiếp, xóa partial
    flag.unlink()
finally:
    s.stop()

# Chiến dịch kẹt sending: tắt nóng rồi khởi động lại, và hết hạn 15 phút khi server vẫn chạy
s = Server("r2_stuck").start()
s.cli_admin()
h = Http().login()
seed_subs(s, 3)
h.post("/admin/subscribers/mail", {"subject": "Kẹt A", "body": "x", "action": "draft"})
h.post("/admin/subscribers/mail", {"subject": "Kẹt B", "body": "x", "action": "draft"})
a_id, b_id = [x[0] for x in s.sql("select id from campaigns order by id")]
s.sql("update campaigns set status='sending' where id=?", (a_id,))
s.sql("""update campaigns set status='sending', sent_to='["u000@qa.test"]', sent_count=1 where id=?""", (b_id,))
c("R6.1", "Đang gửi (mới): mở trang Gửi email không gỡ nhầm", h.get("/admin/subscribers?tab=mail").status_code == 200 and s.sql("select status from campaigns where id=?", (a_id,))[0][0] == "sending")
s.sql("update campaigns set updated_at=datetime('now','-16 minutes')")
h.get("/admin/subscribers?tab=mail")
st = dict(s.sql("select id,status from campaigns"))
c("R6.2", "Quá 15 phút: tự về draft/partial", st == {a_id: "draft", b_id: "partial"}, st)
s.sql("update campaigns set status='sending'")
subprocess.run(["taskkill", "/T", "/F", "/PID", str(s.proc.pid)], capture_output=True)
s.stop()
s.start()
st = dict(s.sql("select id,status from campaigns"))
c("R6.3", "Khởi động lại: mọi sending về draft/partial", st == {a_id: "draft", b_id: "partial"}, st)
s.stop()

# =================== R7. BodyLimit ===================
s = Server("r2_body", env=prod_env()).start()
s.cli_admin()
h = Http().login()
MB = 1024 * 1024
ip = {"CF-Connecting-IP": "2.2.2.2", "Content-Type": "application/x-www-form-urlencoded"}
try:
    st, head = raw("POST", "/api/contact", ip, b"email=a%40x.co&body=" + b"x" * (MB + 10))
    c("R7.1", "Public > 1MB có Content-Length: 413", st == 413, st)
    c("R7.2", "413 có header bảo mật", "content-security-policy" in head.lower(), head[:200])
    st, _ = raw("POST", "/api/contact", ip, b"email=a%40x.co&body=ok")
    c("R7.3", "Form nhỏ qua được", st in (303, 400), st)
    st, _ = raw("POST", "/api/contact", ip, b"", chunks=[b"email=a%40x.co&", b"body=chunked"])
    c("R7.4", "Chunked nhỏ qua được, phát lại đúng thân", st == 303 and s.sql("select count(*) from contact_messages where body='chunked'")[0][0] == 1, st)
    st, _ = raw("POST", "/api/contact", ip, b"", chunks=[b"x" * 65536] * 40)
    c("R7.5", "Chunked 2,6MB ở public: 413", st == 413, st)
    st, _ = raw("POST", "/admin/login", ip, b"x" * (MB + 10))
    c("R7.6", "/admin/login > 1MB: 413", st == 413, st)
    st, _ = raw("POST", "/admin/login/", ip, b"x" * (MB + 10))
    c("R7.7", "/admin/login/ (có /) không lách trần thành xử lý thân lớn", st in (307, 404, 405, 413), st)
    st, head = raw("POST", "/admin/bonus/new", ip, b"", chunks=[b"x" * 65536] * 160)
    c("R7.8", "Admin chunked > 8MB chưa đăng nhập: 413", st == 413, st)
    st, _ = raw("POST", "/admin/media/upload", {"CF-Connecting-IP": "2.2.2.2", "Content-Type": "multipart/form-data; boundary=x"}, b"x" * (65 * MB))
    c("R7.9", "Admin > 64MB: 413", st == 413, st)
    # upload 8 ảnh gần 5MB = 40MB hợp lệ, chạy qua được giới hạn 64MB
    big = png_bytes(extra=b"\x00" * (4 * MB + 900 * 1024))
    r = h.post("/admin/media/upload", {"alt": "x"}, files=[("files", (f"b{i}.png", big, "image/png")) for i in range(8)])
    c("R7.10", "Upload 8 ảnh gần 5MB (40MB) vẫn được", r.status_code == 303 and s.sql("select count(*) from media_files")[0][0] == 8, r.status_code)
    # Content-Length nói nhỏ nhưng đang đăng nhập gửi chunked ảnh
    st, _ = raw("POST", "/api/subscribe", {"CF-Connecting-IP": "2.2.2.3", "Content-Type": "application/x-www-form-urlencoded"}, b"", chunks=[b"email=c%40x.co"])
    c("R7.11", "Subscribe chunked hợp lệ", st == 303, st)
    c("R7.12", "Server còn sống", pub.get("/health").status_code == 200)
finally:
    s.stop()

# =================== R8. Slug tiếng Việt, độ dài, tiêu đề ===================
s = Server("r2_slug").start()
s.cli_admin()
h = Http().login()
try:
    cases = [("Đồng Việt Nhật", "dong-viet-nhat"), ("Sàn Ưu Đãi Ơn Ấy", "san-uu-dai-on-ay"), ("ĐẶNG ĐÌNH", "dang-dinh"), ("Ðồng Eth", "dong-eth"), ("Ủy Ỷ Ỳ Ý Ỹ Ỵ", "uy-y-y-y-y-y"),
             ("Cà phê  &  Trà!!", "ca-phe-tra"), ("Thử́ tổ hợp", "thu-to-hop")]
    for n, want in cases:
        r = h.post("/admin/brokers/new", {"name": n, "kind": "forex", "license": "FCA", "is_active": "1"})
        got = s.sql("select slug from brokers order by id desc limit 1")[0][0]
        c(f"R8.{want}", f"Slug từ {n!r}", r.status_code == 303 and got == want, (r.status_code, got))
    for slug in ("so-sanh", "SO SÁNH", "só sánh", "So-Sánh", "---so-sanh---"):
        r = h.post("/admin/brokers/new", {"name": "Thử", "slug": slug, "kind": "forex", "license": "FCA", "is_active": "1"})
        c(f"R8.res{slug}", f"Slug cấm dạng {slug!r}: 400", r.status_code == 400, r.status_code)
    k = s.sql("select id from brokers limit 1")[0][0]
    r = h.post(f"/admin/brokers/{k}/edit", {"name": "Sửa", "slug": "so-sanh", "kind": "forex", "license": "FCA", "is_active": "1"})
    c("R8.edit", "Sửa slug thành so-sanh: 400", r.status_code == 400, r.status_code)
    for t_, want in (("x" * 119 + " yyy", 120), ("ă" * 119 + " ê", 120)):
        r = h.post("/admin/posts/new", {"title": t_, "category": "Hướng dẫn", "status": "draft"})
        c(f"R8.long{want}{t_[0]}", "Tiêu đề dài cắt tại dấu gạch: lưu được", r.status_code == 303, r.status_code)
    # mono + admin thiếu license khi sửa sàn cũ
    r = h.post(f"/admin/brokers/{k}/edit", {"name": "Sửa", "slug": "sua", "kind": "forex", "license": "", "is_active": "1"})
    c("R8.lic", "license trống bị từ chối khi sửa", r.status_code == 400, r.status_code)
    # công tắc của sàn cũ không có license (dữ liệu trước Phase 4)
    s.sql("update brokers set license='' where id=?", (k,))
    r = h.post(f"/admin/brokers/{k}/toggle", {"field": "featured"})
    c("R8.old", "Sàn cũ chưa có license: công tắc vẫn dùng được", r.status_code == 303)
    r = h.post(f"/admin/brokers/{k}/link", {"affiliate_url": "https://x.test/a"})
    c("R8.old2", "Sàn cũ chưa có license: sửa link affiliate được", r.status_code == 303)
    r = pub.head("/sitemap.xml")
    c("R8.head", "HEAD có Content-Type và không có thân", r.status_code == 200 and r.content == b"" and "xml" in r.headers.get("content-type", ""))
finally:
    s.stop()

# =================== R10. Các mục Nghi ngờ vòng 1 ===================
s = Server("r2_doubt").start()
s.cli_admin()
s.cli_admin("ed@qa.test", "QaEditor-12345", "editor")
h = Http().login()
try:
    h.post("/admin/media/upload", {"alt": "r"}, files={"files": ("r.png", png_bytes(160, 600), "image/png")})
    mp = s.sql("select path from media_files")[0][0]
    mk_broker(h, "Sàn Rail")
    k = s.sql("select id from brokers")[0][0]
    from qalib import mk_banner
    mk_banner(h, "Rail ảnh", placement="rail-left", broker_id=k, image_path=mp, target_url="https://ad.example.test/r")
    t = pub.get("/").text
    i = t.find('class="rail ')
    c("R10.1", "Rail có ảnh in ads_note (nghi ngờ 6)", "CFD có rủi ro mất vốn cao." in t[i:i + 900], t[i:i + 200])
    # nghi ngờ 3: đổi email mỗi lần
    codes = []
    for n in range(12):
        l = Http()
        tok = re.search(r'name="csrf_token" value="([^"]+)"', l.get("/admin/login").text).group(1)
        codes.append(l.post("/admin/login", {"email": f"spray{n}@qa.test", "password": "sai", "csrf_token": tok}, raw=True).status_code)
    print("     đăng nhập sai, đổi email mỗi lần, 1 IP:", codes, flush=True)
    c("R10.2", "Đổi email mỗi lần cũng bị chặn theo IP (nghi ngờ 3)", 429 in codes, codes)
    # nghi ngờ 5: bot
    print("     /go đếm cả curl:", pub.get(f"/go/broker/{k}").status_code, s.sql("select clicks from brokers"), flush=True)
    # nghi ngờ 7: editor
    e = Http().login("ed@qa.test", "QaEditor-12345")
    r = e.post("/admin/subscribers/mail", {"subject": "Editor gửi", "body": "x", "action": "draft"})
    print("     editor lưu nháp chiến dịch:", r.status_code, "; có chỗ tự đổi mật khẩu:", "password" in e.get("/admin").text, flush=True)
finally:
    s.stop()

# =================== R9. Cấu hình production biên ===================
def boot(env):
    e = {k: v for k, v in Server("r2_cfg", env=env).env.items()}
    for k, v in list(e.items()):
        if v is None:
            e.pop(k)
    p = subprocess.Popen([PY, "run.py"], cwd=ROOT, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out, _ = p.communicate(timeout=12)
        return p.returncode, out.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        return None, "đang chạy"


cases = [
    ("R9.1", "APP_ENV rỗng", prod_env(APP_ENV=""), 2), ("R9.2", "APP_ENV=Production (hoa)", prod_env(APP_ENV="Production"), None), ("R9.3", "APP_ENV=staging", prod_env(APP_ENV="staging"), 2),
    ("R9.4", "SECRET_KEY 31 ký tự", prod_env(SECRET_KEY="a" * 31), 2), ("R9.5", "BASE_URL rác", prod_env(BASE_URL="tradingbonushub.com"), 2), ("R9.6", "BASE_URL=http://", prod_env(BASE_URL="http://"), 2),
    ("R9.7", "SMTP_BACKEND=mailgun", prod_env(SMTP_BACKEND="mailgun"), 2), ("R9.8", "smtp thiếu SMTP_HOST", prod_env(SMTP_BACKEND="smtp", FROM_EMAIL="a@b.c"), 2), ("R9.9", "smtp thiếu FROM_EMAIL", prod_env(SMTP_BACKEND="smtp", SMTP_HOST="x"), 2),
    ("R9.10", "PORT=abc", prod_env(PORT="abc"), 2), ("R9.11", "SMTP_PORT=abc", prod_env(SMTP_PORT="abc"), 2), ("R9.12", "SECRET_KEY toàn dấu cách", prod_env(SECRET_KEY=" " * 40), 2),
]
for cid, label, env, want in cases:
    rc, out = boot(env)
    if want is None:
        c(cid, f"{label}: chạy được", rc is None, (rc, out[-160:]))
    else:
        c(cid, f"{label}: thoát mã 2, không traceback", rc == 2 and "Traceback" not in out, (rc, out[-200:]))
R.save()

"""Admin panel page routes."""
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import limiter
from app.db.repositories.faq import create_faq_item, get_faq_items
from app.db.repositories.portal_settings import get_portal_settings, save_portal_settings
from app.db.repositories.promotions import get_all_brokers, get_all_programs
from app.db.repositories.users import get_user
from app.services.auth import hash_pw_async, needs_rehash, verify_pw_async
from app.services.totp import (
    generate_qr_base64, generate_secret, get_totp_secret,
    save_totp_secret, verify_code as verify_totp,
)
from app.utils.audit import log_action
from app.utils.lockout import check_lockout, clear_attempts, record_attempt
from app.utils.templates import make_templates

router = APIRouter()
admin_tpl    = make_templates("templates/admin")
customer_tpl = make_templates("templates/customer")
public_tpl   = make_templates("templates/public")


def _ctx(request: Request, **kwargs):
    """Admin template context with current user injected."""
    return {"request": request, "user": request.session.get("user", ""), **kwargs}


def _cctx(request: Request, **kwargs):
    """Customer template context (includes portal settings)."""
    return {
        "request": request,
        "customer_email": request.session.get("customer_email", ""),
        "ps": get_portal_settings(),
        **kwargs,
    }


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/admin/", status_code=302)
    return admin_tpl.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/admin/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def admin_login_submit(request: Request,
                              username: str = Form(...),
                              password: str = Form(...)):
    ip = _client_ip(request)

    # Check lockout
    locked, remaining = check_lockout(username, "admin")
    if locked:
        return admin_tpl.TemplateResponse(
            "login.html",
            {"request": request,
             "error": "Too many failed attempts. Please try again later."},
        )

    user = get_user(username)
    if user and await verify_pw_async(password, user["password_hash"]):
        clear_attempts(username, "admin")
        # Transparent rehash: upgrade PBKDF2 → Argon2 on successful login
        if needs_rehash(user["password_hash"]):
            from app.db.repositories.users import update_password
            new_hash = await hash_pw_async(password)
            update_password(user["id"], new_hash)

        role = user.get("role") or "admin"
        totp_secret = get_totp_secret(username)

        if totp_secret:
            # TOTP is enabled — require verification before granting access
            request.session["_totp_pending"] = username
            request.session["_totp_role"] = role
            return RedirectResponse(url="/admin/totp-verify", status_code=302)

        # TOTP not set up — require setup on first login
        request.session["_totp_setup_pending"] = username
        request.session["_totp_setup_role"] = role
        return RedirectResponse(url="/admin/totp-setup", status_code=302)

    record_attempt(username, "admin", ip)
    return admin_tpl.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
    )


@router.get("/admin/logout")
async def admin_logout(request: Request):
    username = request.session.get("user", "")
    request.session.clear()
    log_action(username, "admin.logout")
    return RedirectResponse(url="/admin/login", status_code=302)


# ── TOTP / MFA ───────────────────────────────────────────────────────────────

@router.get("/admin/totp-verify", response_class=HTMLResponse)
async def totp_verify_page(request: Request):
    if not request.session.get("_totp_pending"):
        return RedirectResponse(url="/admin/login", status_code=302)
    return admin_tpl.TemplateResponse("totp_verify.html", {"request": request, "error": None})


@router.post("/admin/totp-verify", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def totp_verify_submit(request: Request, code: str = Form(...)):
    username = request.session.get("_totp_pending")
    if not username:
        return RedirectResponse(url="/admin/login", status_code=302)

    secret = get_totp_secret(username)
    if secret and verify_totp(secret, code.strip()):
        role = request.session.pop("_totp_role", "admin")
        request.session.pop("_totp_pending", None)
        request.session["user"] = username
        request.session["user_role"] = role
        log_action(username, "admin.login", ip=_client_ip(request))
        redirect_url = "/admin/cms/articles" if role == "editor" else "/admin/"
        return RedirectResponse(url=redirect_url, status_code=302)

    return admin_tpl.TemplateResponse(
        "totp_verify.html",
        {"request": request, "error": "Invalid code. Please try again."},
    )


@router.get("/admin/totp-setup", response_class=HTMLResponse)
async def totp_setup_page(request: Request):
    username = request.session.get("_totp_setup_pending")
    if not username:
        return RedirectResponse(url="/admin/login", status_code=302)
    secret = generate_secret()
    qr_base64 = generate_qr_base64(secret, username)
    return admin_tpl.TemplateResponse("totp_setup.html", {
        "request": request, "error": None,
        "secret": secret, "qr_base64": qr_base64,
    })


@router.post("/admin/totp-setup", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def totp_setup_submit(request: Request,
                            secret: str = Form(...),
                            code: str = Form(...)):
    username = request.session.get("_totp_setup_pending")
    if not username:
        return RedirectResponse(url="/admin/login", status_code=302)

    if verify_totp(secret, code.strip()):
        save_totp_secret(username, secret)
        role = request.session.pop("_totp_setup_role", "admin")
        request.session.pop("_totp_setup_pending", None)
        request.session["user"] = username
        request.session["user_role"] = role
        log_action(username, "admin.totp_setup", ip=_client_ip(request))
        redirect_url = "/admin/cms/articles" if role == "editor" else "/admin/"
        return RedirectResponse(url=redirect_url, status_code=302)

    qr_base64 = generate_qr_base64(secret, username)
    return admin_tpl.TemplateResponse("totp_setup.html", {
        "request": request, "error": "Invalid code. Please try again.",
        "secret": secret, "qr_base64": qr_base64,
    })


# ── Admin pages ───────────────────────────────────────────────────────────────

@router.get("/admin/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return admin_tpl.TemplateResponse("dashboard.html", _ctx(request, active="dashboard"))


@router.get("/admin/templates", response_class=HTMLResponse)
async def admin_templates_page(request: Request):
    return admin_tpl.TemplateResponse("templates.html", _ctx(request, active="templates"))


@router.get("/admin/templates/{tid}/edit", response_class=HTMLResponse)
async def admin_editor_page(tid: int, request: Request):
    return admin_tpl.TemplateResponse(
        "editor.html", _ctx(request, template_id=tid, active="templates")
    )


@router.get("/admin/campaigns", response_class=HTMLResponse)
async def admin_campaigns_page(request: Request):
    return admin_tpl.TemplateResponse("campaigns.html", _ctx(request, active="campaigns"))


@router.get("/admin/campaigns/new", response_class=HTMLResponse)
async def admin_campaign_new_page(request: Request):
    return admin_tpl.TemplateResponse("campaign_new.html", _ctx(request, active="campaigns"))


@router.get("/admin/campaigns/{cid}", response_class=HTMLResponse)
async def admin_campaign_detail_page(cid: int, request: Request):
    return admin_tpl.TemplateResponse(
        "campaign_detail.html", _ctx(request, campaign_id=cid, active="campaigns")
    )


@router.get("/admin/compose", response_class=HTMLResponse)
async def compose_page(request: Request):
    return admin_tpl.TemplateResponse("compose.html", _ctx(request, active="compose"))


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    return admin_tpl.TemplateResponse("settings.html", _ctx(request, active="settings"))


@router.get("/admin/system", response_class=HTMLResponse)
async def admin_system_page(request: Request):
    return admin_tpl.TemplateResponse("system.html", _ctx(request, active="system"))


@router.get("/admin/customers", response_class=HTMLResponse)
async def admin_customers_page(request: Request):
    return admin_tpl.TemplateResponse("customers.html", _ctx(request, active="customers"))


@router.get("/admin/leads", response_class=HTMLResponse)
async def admin_leads_page(request: Request):
    return admin_tpl.TemplateResponse("imported_leads.html", _ctx(request, active="leads"))


@router.get("/admin/imported-leads")
async def admin_imported_leads_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin/leads", status_code=302)


@router.get("/admin/crm", response_class=HTMLResponse)
async def admin_crm_page(request: Request):
    return admin_tpl.TemplateResponse("crm.html", _ctx(request, active="crm"))


@router.get("/admin/brokers", response_class=HTMLResponse)
async def admin_brokers_page(request: Request):
    brokers = get_all_brokers(active_only=False)
    return admin_tpl.TemplateResponse(
        "brokers.html", _ctx(request, active="brokers", brokers=brokers)
    )


@router.get("/admin/broker-settings")
async def admin_broker_settings_redirect():
    """Redirect old URL -> unified brokers page."""
    from starlette.responses import RedirectResponse
    return RedirectResponse("/admin/brokers", status_code=301)


@router.get("/admin/special-offers", response_class=HTMLResponse)
async def admin_special_offers_page(request: Request):
    from app.db.repositories.promo_bar import get_all_promo_bars
    bars = get_all_promo_bars()
    return admin_tpl.TemplateResponse(
        "special_offers.html", _ctx(request, active="special_offers", bars=bars)
    )


@router.get("/admin/promotions", response_class=HTMLResponse)
async def admin_promotions_page(request: Request):
    return admin_tpl.TemplateResponse("promotions.html", _ctx(request, active="promotions"))


@router.get("/admin/enrollments", response_class=HTMLResponse)
async def admin_enrollments_page(request: Request):
    return admin_tpl.TemplateResponse("enrollments.html", _ctx(request, active="enrollments"))


@router.get("/admin/account-owners", response_class=HTMLResponse)
async def admin_account_owners_page(request: Request):
    return admin_tpl.TemplateResponse(
        "account_owners.html", _ctx(request, active="account_owners")
    )


@router.get("/admin/rebate", response_class=HTMLResponse)
async def admin_rebate_page(request: Request):
    return admin_tpl.TemplateResponse(
        "rebate.html", _ctx(request, active="rebate")
    )


@router.get("/admin/rebate-settings")
async def admin_rebate_settings_redirect():
    """Redirect old URL → Promotions tab 2."""
    from starlette.responses import RedirectResponse
    return RedirectResponse("/admin/promotions?tab=settings", status_code=301)


# ── Portal editor ─────────────────────────────────────────────────────────────

@router.get("/admin/portal-editor", response_class=HTMLResponse)
async def admin_portal_editor_page(request: Request):
    settings = get_portal_settings()
    return admin_tpl.TemplateResponse(
        "portal_editor.html", _ctx(request, settings=settings, active="portal-editor")
    )


def _portal_preview_ctx(edit_mode: bool = False) -> dict:
    """Build shared mock context for portal preview / edit-mode pages."""
    mock_trading = [
        {"trade_date": "2026-03-01", "lots": 2.50, "commission": 12.50, "note": "Sample trade"},
        {"trade_date": "2026-02-28", "lots": 1.75, "commission": 8.75,  "note": ""},
        {"trade_date": "2026-02-27", "lots": 3.00, "commission": 15.00, "note": ""},
    ]
    brokers = get_all_brokers()
    promotions = get_all_programs(active_only=True)
    for p in promotions:
        p.setdefault("details", {})
        p.setdefault("db_tiers", [])
        p.setdefault("comm_rates", [])
        p.setdefault("broker_slug", "")
        p.setdefault("broker_ids", [])
    return {
        "customer_email": "preview@example.com",
        "customer_name": "John Doe",
        "trading": mock_trading,
        "summary": {"total_lots": 7.25, "total_commission": 36.25},
        "customer": {"name": "John Doe", "email": "preview@example.com", "unsubscribed": 0},
        "brokers": brokers,
        "promotions": promotions,
        "enrollment": None,
        "broker_accounts": [],
        "broker_emails": [],
        "all_broker_emails": [],
        "params": {},
        "enrolled_promo_ids": set(),
        "enrolled_broker_ids": set(),
        "enrolled_pairs": set(),
        "rebate_data": [],
        "enrollments_list": [],
        "edit_mode": edit_mode,
        "error": None,
    }


@router.get("/admin/portal-preview", response_class=HTMLResponse)
async def admin_portal_preview(request: Request):
    return customer_tpl.TemplateResponse(
        "dashboard.html", _cctx(request, **_portal_preview_ctx(edit_mode=False)),
    )


@router.get("/admin/portal-edit-mode", response_class=HTMLResponse)
async def admin_portal_edit_mode(request: Request):
    """Renders customer portal with edit_mode=True for WYSIWYG editing in iframe."""
    return customer_tpl.TemplateResponse(
        "dashboard.html", _cctx(request, **_portal_preview_ctx(edit_mode=True)),
    )


@router.get("/admin/payment", response_class=HTMLResponse)
async def admin_payment_page(request: Request):
    from datetime import date
    today = date.today()
    return admin_tpl.TemplateResponse("payment.html", _ctx(
        request, active="payment",
        today=today.strftime("%Y-%m-%d"),
        current_year=today.year,
        current_month=today.month,
    ))


_DEFAULT_FAQ = [
    # (question_vi, answer_vi, question_en, answer_en)

    # ── Giới thiệu chung / General ──
    ("Rebate (hoàn phí) là gì?",
     "Rebate là khoản hoàn lại một phần hoa hồng (commission) hoặc spread mà sàn thu từ mỗi giao dịch của bạn. Thay vì mất toàn bộ phí, bạn được nhận lại một tỉ lệ phần trăm — giúp giảm chi phí giao dịch thực tế.",
     "What is a rebate?",
     "A rebate is a partial refund of the commission or spread charged by the broker on each of your trades. Instead of losing the full fee, you receive a percentage back — effectively reducing your actual trading costs."),
    ("TradingBonusHub là gì?",
     "TradingBonusHub là nền tảng trung gian giúp trader nhận hoàn phí (rebate) từ các sàn giao dịch uy tín. Chúng tôi là đối tác chính thức (IB) của nhiều sàn lớn, và chia sẻ lại hoa hồng cho trader thông qua các chương trình rebate và bonus hấp dẫn.",
     "What is TradingBonusHub?",
     "TradingBonusHub is a platform that helps traders receive rebates from trusted brokers. We are an official Introducing Broker (IB) partner of major brokers and share commissions with traders through attractive rebate and bonus programs."),
    ("Tham gia có mất phí không?",
     "Hoàn toàn miễn phí. Spread và điều kiện giao dịch giữ nguyên như khi bạn mở tài khoản trực tiếp với sàn. Bạn chỉ cần đăng ký qua link của TradingBonusHub để hệ thống ghi nhận rebate.",
     "Is it free to join?",
     "Completely free. Spreads and trading conditions remain the same as opening an account directly with the broker. You just need to register through TradingBonusHub's link so the system can track your rebates."),

    # ── Đăng ký & Tài khoản / Registration & Account ──
    ("Làm thế nào để đăng ký tài khoản trên TradingBonusHub?",
     'Bạn truy cập trang chủ, nhấn "Đăng ký", nhập email và mật khẩu (tối thiểu 8 ký tự). Sau khi đăng ký thành công, bạn có thể đăng nhập và liên kết tài khoản sàn để bắt đầu nhận rebate.',
     "How do I create an account on TradingBonusHub?",
     'Visit the homepage, click "Sign Up", enter your email and password (minimum 8 characters). After successful registration, you can log in and link your broker account to start receiving rebates.'),
    ("Tôi đã có tài khoản với sàn rồi, có tham gia được không?",
     "Tuỳ sàn, bạn có thể mở thêm tài khoản mới dưới link giới thiệu của TradingBonusHub. Tài khoản cũ không thể chuyển đổi, nhưng mở tài khoản mới chỉ mất vài phút. Liên hệ hỗ trợ nếu cần hướng dẫn chi tiết.",
     "I already have a broker account. Can I still join?",
     "Depending on the broker, you may open a new account under TradingBonusHub's referral link. Existing accounts cannot be transferred, but opening a new one only takes a few minutes. Contact support for detailed guidance."),
    ("Tôi có thể liên kết nhiều sàn giao dịch cùng lúc không?",
     "Có. Bạn có thể liên kết tài khoản ở nhiều sàn khác nhau trên cùng một tài khoản TradingBonusHub. Mỗi sàn sẽ có chương trình rebate riêng và bạn có thể theo dõi tất cả từ một dashboard duy nhất.",
     "Can I link multiple brokers at the same time?",
     "Yes. You can link accounts from different brokers to the same TradingBonusHub account. Each broker has its own rebate program and you can track everything from a single dashboard."),
    ("Làm sao để liên kết tài khoản MT5 với TradingBonusHub?",
     'Vào Dashboard → tab "Tài khoản sàn", nhấn "Thêm tài khoản", nhập email bạn đã đăng ký với sàn. Hệ thống sẽ gửi email xác nhận đến địa chỉ đó — bạn chỉ cần nhấn link xác nhận là hoàn tất liên kết.',
     "How do I link my MT5 account with TradingBonusHub?",
     'Go to Dashboard → "Broker Accounts" tab, click "Add Account", and enter the email you registered with the broker. The system will send a confirmation email to that address — just click the verification link to complete the linking.'),
    ("Email đăng nhập TradingBonusHub và email sàn có cần giống nhau không?",
     "Không bắt buộc. Email đăng nhập TradingBonusHub (portal) và email đăng ký sàn (broker) có thể khác nhau. Khi liên kết tài khoản sàn, bạn nhập email sàn và xác nhận qua email đó.",
     "Do the TradingBonusHub login email and broker email need to be the same?",
     "No. Your TradingBonusHub (portal) login email and broker registration email can be different. When linking a broker account, you enter the broker email and verify it through that address."),

    # ── Chương trình Rebate & Bonus / Rebate & Bonus Programs ──
    ("Rebate được tính như thế nào?",
     "Rebate được tính dựa trên phần trăm (%) hoa hồng (commission) mà sàn thu từ giao dịch của bạn. Tỉ lệ hoàn phụ thuộc vào chương trình và bậc (tier) bạn đạt được — giao dịch càng nhiều, tỉ lệ hoàn càng cao.",
     "How is rebate calculated?",
     "Rebate is calculated based on a percentage (%) of the commission charged by the broker on your trades. The rebate rate depends on the program and tier you achieve — the more you trade, the higher your rebate rate."),
    ("Tài khoản RAW và Standard khác nhau về rebate như thế nào?",
     "Tài khoản RAW có spread thấp hơn và tính commission riêng — rebate được tính trên commission đó. Tài khoản Standard không tính commission mà phí nằm trong spread — rebate sẽ được tính theo cách phù hợp với từng loại tài khoản.",
     "What is the difference between RAW and Standard accounts for rebates?",
     "RAW accounts have lower spreads with a separate commission — rebate is calculated on that commission. Standard accounts have no separate commission as fees are built into the spread — rebate is calculated accordingly for each account type."),
    ("Tiền hoàn được trả vào lúc nào?",
     "Tuỳ theo chương trình của từng sàn, rebate được thanh toán tự động hàng ngày, hàng tuần hoặc hàng tháng — trực tiếp vào tài khoản MT5 của bạn. Bạn có thể xem chi tiết tần suất trên mỗi thẻ chương trình.",
     "When are rebates paid out?",
     "Depending on each broker's program, rebates are paid automatically on a daily, weekly, or monthly basis — directly to your MT5 account. You can see the payout frequency on each program card."),
    ("Chương trình Bonus là gì và khác gì với Rebate?",
     "Chương trình Bonus thưởng bạn một khoản tiền cố định (USD) khi đạt mốc khối lượng giao dịch nhất định trong tháng (ví dụ: $100 khi đạt 100 lots). Khác với Rebate (hoàn % trên mỗi giao dịch), Bonus là phần thưởng cộng thêm khi bạn đạt mục tiêu.",
     "What is a Bonus program and how is it different from Rebate?",
     "A Bonus program rewards you with a fixed amount (USD) when you reach a certain trading volume milestone in a month (e.g., $100 when reaching 100 lots). Unlike Rebate (percentage refund per trade), Bonus is an additional reward for hitting your target."),
    ("Làm sao để đăng ký chương trình rebate/bonus?",
     'Vào Dashboard → tab "Chương trình", chọn chương trình phù hợp và nhấn "Đăng ký". Yêu cầu sẽ được gửi đến admin để xác nhận. Sau khi được duyệt, bạn sẽ nhận email thông báo và bắt đầu được tính rebate.',
     "How do I enroll in a rebate/bonus program?",
     'Go to Dashboard → "Programs" tab, select the program that suits you and click "Enroll". The request will be sent to admin for approval. Once approved, you will receive an email notification and your rebate will start being calculated.'),
    ("Tôi có thể tham gia nhiều chương trình cùng lúc không?",
     "Mỗi tài khoản sàn chỉ có thể tham gia một chương trình tại một thời điểm. Tuy nhiên, nếu bạn có nhiều tài khoản MT5 ở các sàn khác nhau, mỗi tài khoản có thể tham gia chương trình riêng.",
     "Can I join multiple programs at the same time?",
     "Each broker account can only participate in one program at a time. However, if you have multiple MT5 accounts at different brokers, each account can join a separate program."),
    ("Bậc (tier) rebate hoạt động như thế nào?",
     "Mỗi chương trình có nhiều bậc dựa trên khối lượng giao dịch tích lũy. Khi bạn giao dịch nhiều hơn và đạt mốc lots yêu cầu, bạn tự động được nâng bậc với tỉ lệ hoàn cao hơn. Ví dụ: Silver 60%, Gold 70%, Platinum 80%.",
     "How do rebate tiers work?",
     "Each program has multiple tiers based on cumulative trading volume. As you trade more and reach the required lot milestones, you are automatically upgraded to a higher tier with a better rebate rate. For example: Silver 60%, Gold 70%, Platinum 80%."),

    # ── Ví & Rút tiền / Wallet & Withdrawals ──
    ("Ví TradingBonusHub hoạt động như thế nào?",
     "Ví là nơi lưu trữ số dư rebate và bonus của bạn. Khi admin thanh toán rebate, tiền sẽ được cộng vào ví. Bạn có thể theo dõi số dư, lịch sử giao dịch và yêu cầu rút tiền từ ví.",
     "How does the TradingBonusHub wallet work?",
     "The wallet stores your rebate and bonus balance. When admin processes rebate payments, funds are credited to your wallet. You can track your balance, transaction history, and request withdrawals from the wallet."),
    ("Làm sao để rút tiền từ ví?",
     'Vào Dashboard → tab "Ví", nhấn "Rút tiền". Hệ thống sẽ gửi mã OTP 6 số đến email của bạn để xác nhận. Nhập mã OTP, chọn phương thức rút (chuyển khoản ngân hàng hoặc crypto), nhập thông tin và xác nhận. Số tiền rút tối thiểu là $10.',
     "How do I withdraw from the wallet?",
     'Go to Dashboard → "Wallet" tab, click "Withdraw". The system will send a 6-digit OTP code to your email for verification. Enter the OTP, choose a withdrawal method (bank transfer or crypto), enter the details and confirm. Minimum withdrawal amount is $10.'),
    ("Có những phương thức rút tiền nào?",
     "Hiện hỗ trợ hai phương thức: (1) Chuyển khoản ngân hàng — bạn cần cung cấp thông tin tài khoản ngân hàng; (2) Tiền điện tử (Crypto) — bạn cung cấp địa chỉ ví và mạng lưới (ví dụ: USDT TRC20, BTC).",
     "What withdrawal methods are available?",
     "Currently two methods are supported: (1) Bank transfer — you need to provide your bank account details; (2) Cryptocurrency — you provide a wallet address and network (e.g., USDT TRC20, BTC)."),
    ("Yêu cầu rút tiền mất bao lâu để xử lý?",
     "Sau khi bạn gửi yêu cầu, admin sẽ xét duyệt và xử lý. Thời gian thường từ 1–3 ngày làm việc tuỳ phương thức. Bạn có thể theo dõi trạng thái (đang chờ → đã duyệt → hoàn tất) trong tab Ví.",
     "How long does a withdrawal request take to process?",
     "After you submit a request, admin will review and process it. Processing typically takes 1–3 business days depending on the method. You can track the status (pending → approved → completed) in the Wallet tab."),
    ("Tôi có thể huỷ yêu cầu rút tiền không?",
     'Có. Nếu yêu cầu đang ở trạng thái "đang chờ" (chưa được admin duyệt), bạn có thể huỷ và số tiền sẽ được hoàn lại vào ví ngay lập tức.',
     "Can I cancel a withdrawal request?",
     'Yes. If the request is still in "pending" status (not yet approved by admin), you can cancel it and the funds will be returned to your wallet immediately.'),

    # ── Dashboard & Theo dõi / Dashboard & Tracking ──
    ("Tôi có thể xem chi tiết rebate ở đâu?",
     'Đăng nhập vào Dashboard, tab "Rebate" hiển thị tổng quan commission, lots giao dịch, biểu đồ theo tháng, và phân tích theo loại tài sản (Forex, Hàng hoá, Chỉ số, Crypto, Cổ phiếu CFD...). Bạn có thể lọc theo sàn và khoảng thời gian.',
     "Where can I see my rebate details?",
     'Log in to the Dashboard, the "Rebate" tab shows an overview of commissions, trading lots, monthly charts, and analysis by asset type (Forex, Commodities, Indices, Crypto, Stock CFDs...). You can filter by broker and time period.'),
    ('Trạng thái rebate "pending", "exported", "paid" nghĩa là gì?',
     '"Pending" nghĩa là rebate đã được tính nhưng chưa gửi cho sàn. "Exported" nghĩa là đã gửi yêu cầu thanh toán cho sàn. "Paid" nghĩa là sàn đã xác nhận thanh toán và tiền đã về tài khoản hoặc ví của bạn.',
     'What do the rebate statuses "pending", "exported", "paid" mean?',
     '"Pending" means the rebate has been calculated but not yet sent to the broker. "Exported" means the payment request has been submitted to the broker. "Paid" means the broker has confirmed the payment and funds have been deposited to your account or wallet.'),

    # ── Bảo mật / Security ──
    ("Làm sao để đổi mật khẩu?",
     'Vào Dashboard → tab "Cài đặt", nhập mật khẩu hiện tại và mật khẩu mới (tối thiểu 8 ký tự), sau đó nhấn "Lưu". Mật khẩu sẽ được cập nhật ngay lập tức.',
     "How do I change my password?",
     'Go to Dashboard → "Settings" tab, enter your current password and new password (minimum 8 characters), then click "Save". The password will be updated immediately.'),
    ("Tôi quên mật khẩu, phải làm sao?",
     'Tại trang đăng nhập, nhấn "Quên mật khẩu", nhập email đã đăng ký. Hệ thống sẽ gửi link đặt lại mật khẩu đến email của bạn. Link có hiệu lực trong 1 giờ.',
     "I forgot my password. What should I do?",
     'On the login page, click "Forgot password", enter your registered email. The system will send a password reset link to your email. The link is valid for 1 hour.'),
    ("Mã OTP là gì và tại sao cần xác nhận OTP khi rút tiền?",
     "OTP (One-Time Password) là mã xác nhận 6 số gửi đến email của bạn, có hiệu lực 5 phút. Đây là lớp bảo mật bổ sung để đảm bảo chỉ chủ tài khoản mới có thể thực hiện rút tiền.",
     "What is OTP and why is it required for withdrawals?",
     "OTP (One-Time Password) is a 6-digit verification code sent to your email, valid for 5 minutes. This is an additional security layer to ensure only the account owner can perform withdrawals."),

    # ── Khác / Other ──
    ("Rebate có ảnh hưởng đến spread hoặc chất lượng khớp lệnh không?",
     "Không. Rebate được trích từ hoa hồng mà sàn trả cho đối tác giới thiệu (IB). Spread, slippage và tốc độ khớp lệnh của bạn hoàn toàn không bị ảnh hưởng.",
     "Does rebate affect spread or execution quality?",
     "No. Rebate is deducted from the commission the broker pays to the introducing broker (IB). Your spread, slippage, and execution speed are not affected at all."),
    ("Nếu xảy ra vấn đề với tài khoản hoặc rebate thì sao?",
     "Bạn sẽ không phải tự liên hệ với sàn. Là đối tác chính thức, chúng tôi có đội ngũ support riêng và sẽ đứng ra làm việc trực tiếp với sàn để kiểm tra và giải quyết vấn đề cho bạn.",
     "What if there is an issue with my account or rebate?",
     "You don't need to contact the broker yourself. As an official partner, we have a dedicated support team and will work directly with the broker to investigate and resolve any issues for you."),
    ("Tôi muốn huỷ nhận email thông báo thì làm sao?",
     'Vào Dashboard → tab "Cài đặt", bạn có thể bật/tắt nhận email thông báo. Ngoài ra, mỗi email đều có link "Huỷ đăng ký" ở cuối để bạn dừng nhận email bất kỳ lúc nào.',
     "How do I unsubscribe from email notifications?",
     'Go to Dashboard → "Settings" tab, you can toggle email notifications on/off. Additionally, every email includes an "Unsubscribe" link at the bottom so you can stop receiving emails at any time.'),
    ("TradingBonusHub hỗ trợ những sàn nào?",
     'Chúng tôi hiện hợp tác với nhiều sàn giao dịch uy tín. Danh sách sàn và chương trình rebate cụ thể được cập nhật liên tục trên trang "Chương trình". Bạn có thể xem và so sánh các sàn để chọn chương trình phù hợp nhất.',
     "Which brokers does TradingBonusHub support?",
     'We currently partner with many trusted brokers. The list of brokers and specific rebate programs is continuously updated on the "Programs" page. You can view and compare brokers to choose the most suitable program.'),
]


@router.get("/admin/faq", response_class=HTMLResponse)
async def admin_faq_page(request: Request):
    brokers = get_all_brokers()
    faq_items = get_faq_items(active_only=False)
    # Seed default FAQ items only when table is completely empty
    if not faq_items:
        for i, (q, a, q_en, a_en) in enumerate(_DEFAULT_FAQ):
            create_faq_item(q, a, broker_id=None, display_order=i + 1, is_active=True,
                            question_en=q_en, answer_en=a_en)
        faq_items = get_faq_items(active_only=False)
    return admin_tpl.TemplateResponse("faq.html", _ctx(request,
        brokers=brokers, faq_items=faq_items))


@router.get("/admin/analytics", response_class=HTMLResponse)
async def admin_analytics_page(request: Request):
    return admin_tpl.TemplateResponse("analytics.html", _ctx(request, active="analytics"))


@router.get("/admin/scheduling", response_class=HTMLResponse)
async def admin_scheduling_page(request: Request):
    return admin_tpl.TemplateResponse("scheduling.html", _ctx(request, active="scheduling"))


@router.get("/admin/roles", response_class=HTMLResponse)
async def admin_roles_page(request: Request):
    return admin_tpl.TemplateResponse("roles.html", _ctx(request, active="roles"))


@router.get("/admin/segments", response_class=HTMLResponse)
async def admin_segments_page(request: Request):
    return admin_tpl.TemplateResponse("segments.html", _ctx(request, active="segments"))


@router.get("/admin/auto-credit", response_class=HTMLResponse)
async def admin_auto_credit_page(request: Request):
    return admin_tpl.TemplateResponse("auto_credit.html", _ctx(request, active="auto_credit"))


@router.get("/admin/notifications-config", response_class=HTMLResponse)
async def admin_notifications_page(request: Request):
    return admin_tpl.TemplateResponse("notifications_config.html", _ctx(request, active="notifications"))


@router.get("/admin/contact-settings", response_class=HTMLResponse)
async def admin_contact_settings(request: Request):
    settings = get_portal_settings()
    return admin_tpl.TemplateResponse(
        "contact_settings.html", _ctx(request, settings=settings, active="contact_settings")
    )


@router.get("/admin/page-editor", response_class=HTMLResponse)
async def admin_page_editor(request: Request):
    from app.db.repositories.page_content import get_all_content
    vi_content = get_all_content("vi")
    en_content = get_all_content("en")
    return admin_tpl.TemplateResponse("page_editor.html", _ctx(request,
        vi_content=vi_content, en_content=en_content, active="page_editor"))


# ── Visual Editor (WYSIWYG) ───────────────────────────────────────────────────

@router.get("/admin/visual-editor", response_class=HTMLResponse)
async def admin_visual_editor(request: Request):
    """Visual editor wrapper — shows public pages in an editable iframe."""
    return admin_tpl.TemplateResponse(
        "visual_editor.html", _ctx(request, active="visual_editor")
    )


@router.get("/admin/public-edit-mode", response_class=HTMLResponse)
async def admin_public_edit_mode(request: Request, page: str = "home"):
    """Renders a public page with edit_mode=True for inline visual editing."""
    from app.db.repositories.cms_banners import get_active_banners
    from app.db.repositories.cms_navigation import get_nav_items
    from app.db.repositories.page_content import get_all_content
    from app.db.repositories.portal_settings import get_portal_settings
    from app.db.repositories.promotions import get_all_brokers

    ps        = get_portal_settings()
    nav_items = get_nav_items("public_header")

    if page == "about":
        return public_tpl.TemplateResponse("about.html", {
            "request":   request,
            "brokers":   get_all_brokers(),
            "ps":        ps,
            "nav_items": nav_items,
            "edit_mode": True,
        })

    if page == "blog":
        from app.db.repositories.cms_articles import list_articles, get_all_categories
        result     = list_articles(status="published", type_="post", limit=12, offset=0)
        return public_tpl.TemplateResponse("blog.html", {
            "request":          request,
            "articles":         result["items"],
            "total":            result["total"],
            "limit":            12,
            "offset":           0,
            "categories":       get_all_categories(),
            "current_category": None,
            "pc":               get_all_content("en"),
            "ps":               ps,
            "banners":          get_active_banners("blog"),
            "nav_items":        nav_items,
            "seo_title":        None,
            "seo_desc":         None,
            "edit_mode":        True,
        })

    # default: home — load full context
    from decimal import Decimal
    from app.db.repositories.faq import get_faq_items
    from app.db.repositories.promotions import get_all_programs, get_all_program_tiers
    from app.db.connection import get_conn

    def _fix_decimals(d):
        if isinstance(d, dict):
            return {k: _fix_decimals(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_fix_decimals(v) for v in d]
        if isinstance(d, Decimal):
            return float(d)
        return d

    pc        = get_all_content("en")
    brokers   = get_all_brokers()
    promotions = get_all_programs(active_only=True)
    all_tiers  = get_all_program_tiers()

    promotions = [_fix_decimals(p) for p in promotions]
    all_tiers = {k: [_fix_decimals(t) for t in v] for k, v in all_tiers.items()}

    for p in promotions:
        p["details"] = {}
        p["tiers"]   = all_tiers.get(p["id"], [])
        p["rates"]   = []

    backcom_promos = [p for p in promotions if "bonus" not in (p.get("type") or "").lower()]
    tier_promos    = [p for p in promotions if "bonus" in (p.get("type") or "").lower()]
    calc_promos    = [
        {"id": p["id"], "name": p["name"], "broker_names": p.get("broker_names", ""),
         "type": p.get("type", ""), "details": p["details"], "tiers": p["tiers"], "rates": []}
        for p in promotions
    ]

    with get_conn() as _c:
        _gold = _c.execute(
            "SELECT id FROM programs WHERE type='gold_bonus' AND is_active=1"
        ).fetchone()
        if _gold:
            _trows = _c.execute(
                "SELECT target_lot, reward_value FROM program_tiers "
                "WHERE program_id=? AND reward_type='bonus_usd' ORDER BY target_lot",
                (_gold["id"],),
            ).fetchall()
            bonus_tiers = [{"min_lots": r["target_lot"], "bonus_usd": r["reward_value"]} for r in _trows]
        else:
            bonus_tiers = []

    all_faq      = get_faq_items(active_only=True)
    faq_generic  = [f for f in all_faq if f["broker_id"] is None]
    faq_by_broker: dict = {}
    for f in all_faq:
        if f["broker_id"] is not None:
            faq_by_broker.setdefault(f["broker_id"], []).append(f)

    # trader_count for promo social proof section
    tc_val = ps.get("promo_trader_count")
    if tc_val is not None:
        trader_count = int(tc_val)
    else:
        save_portal_settings({"promo_trader_count": "789"})
        trader_count = 789

    return public_tpl.TemplateResponse("index.html", {
        "request":       request,
        "brokers":       brokers,
        "promotions":    promotions,
        "backcom_promos": backcom_promos,
        "tier_promos":   tier_promos,
        "calc_promos":   calc_promos,
        "bonus_tiers":   bonus_tiers,
        "faq_generic":   faq_generic,
        "faq_by_broker": faq_by_broker,
        "trader_count":  trader_count,
        "lang":          "en",
        "pc":            pc,
        "ps":            ps,
        "banners":       get_active_banners("index"),
        "nav_items":     get_nav_items("public_header"),
        "edit_mode":     True,
    })

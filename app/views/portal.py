"""Customer portal page routes."""
import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import limiter
from app.db.repositories.customers import (
    clear_verify_token, create_customer, get_customer_by_email,
    get_customer_by_reset_token, get_customer_by_verify_token,
    set_customer_password, set_reset_token, set_unsubscribed, set_verify_token,
    update_last_login,
)
from app.db.repositories.customer_accounts import (
    get_accounts_for_customer, get_account_by_broker_email,
    get_customer_account, get_customer_account_by_id, create_customer_account,
    link_customer_to_account, update_customer_account,
    upsert_customer_account, verify_broker_email_token,
)
from app.db.repositories.promotions import get_all_brokers, get_program, get_program_broker_ids
from app.db.repositories.portal_settings import get_portal_settings
from app.db.repositories.smtp import get_google_oauth_config, get_gmail_token, save_gmail_token
from app.services.auth import hash_pw_async, needs_rehash, verify_pw_async
from app.services.gmail import make_flow, _get_google_email_sync, send_transfer_email
from app.services.notifications import (
    notify_new_registration, send_reset_email, send_verification_email,
    send_broker_email_verify, send_enrollment_notification,
    notify_broker_email_linked,
)
from app.utils.lockout import check_lockout, record_attempt, clear_attempts
from app.utils.templates import make_templates

logger = structlog.get_logger(__name__)
router = APIRouter()
customer_tpl = make_templates("templates/customer")

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


async def _fire(coro, *, label: str) -> None:
    try:
        await coro
    except Exception as exc:
        logger.error("background_task_failed", label=label, error=str(exc))


def _lang(request: Request) -> str:
    return getattr(getattr(request, "state", None), "lang", None) or "en"


def _cctx(request: Request, **kwargs):
    return {
        "request": request,
        "customer_email": request.session.get("customer_email", ""),
        "ps": get_portal_settings(),
        "lang": _lang(request),
        **kwargs,
    }


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.get("/portal/register", response_class=HTMLResponse)
async def portal_register_page(request: Request, broker: str = ""):
    if request.session.get("customer_email"):
        return RedirectResponse(url="/portal/", status_code=302)
    if broker:
        request.session["ref_broker"] = broker
    return customer_tpl.TemplateResponse(
        "register.html",
        {"request": request, "error": None, "success": None, "ps": get_portal_settings(), "lang": _lang(request)},
    )


@router.post("/portal/register", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def portal_register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    ps = get_portal_settings()
    ctx = {"request": request, "ps": ps, "error": None, "success": None,
           "form_name": name.strip(), "form_email": email.strip().lower(),
           "lang": _lang(request)}
    email = email.strip().lower()
    name  = name.strip()

    if not name:
        ctx["error"] = "Please enter your full name."
        return customer_tpl.TemplateResponse("register.html", ctx)
    if len(password) < 8:
        ctx["error"] = "Password must be at least 8 characters."
        return customer_tpl.TemplateResponse("register.html", ctx)
    if password != confirm_password:
        ctx["error"] = "Passwords do not match."
        return customer_tpl.TemplateResponse("register.html", ctx)
    existing = get_customer_by_email(email)
    if existing:
        ctx["error"] = "This email is already registered."
        return customer_tpl.TemplateResponse("register.html", ctx)
    else:
        pw_hash = await hash_pw_async(password)
        new_id = create_customer(email, pw_hash, name=name, must_change_password=0,
                                 is_verified=1, verify_token=None)

    # Auto-link broker accounts that share this email — only if no other
    # customer already owns them (prevents email spoofing account takeover)
    if new_id:
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            conn.execute(
                "UPDATE customer_accounts SET customer_id=?"
                " WHERE broker_email=? AND customer_id IS NULL"
                " AND NOT EXISTS ("
                "   SELECT 1 FROM customer_accounts ca2"
                "   WHERE ca2.broker_id = customer_accounts.broker_id"
                "   AND ca2.customer_id = ? AND ca2.id <> customer_accounts.id"
                " )",
                (new_id, email, new_id),
            )

    asyncio.create_task(_fire(
        notify_new_registration(name, email), label="notify_new_registration"
    ))

    # Auto-login after registration — set session and go straight to dashboard
    request.session["customer_email"] = email
    request.session["customer_name"]  = name
    request.session["must_change_password"] = 0
    return RedirectResponse(url="/portal/dashboard", status_code=302)


@router.get("/portal/verify-email/{token}", response_class=HTMLResponse)
async def portal_verify_email(token: str, request: Request):
    ps = get_portal_settings()
    customer = get_customer_by_verify_token(token)
    if not customer:
        return customer_tpl.TemplateResponse(
            "login.html",
            {"request": request, "ps": ps, "lang": _lang(request),
             "error": "Verification link is invalid or has already been used."},
        )
    clear_verify_token(customer["login_email"])
    return RedirectResponse(url="/portal/login?verified=1", status_code=302)


@router.get("/portal/login", response_class=HTMLResponse)
async def portal_login_page(request: Request, broker: str = ""):
    if request.session.get("customer_email"):
        return RedirectResponse(url="/portal/", status_code=302)
    if broker:
        request.session["ref_broker"] = broker
    return customer_tpl.TemplateResponse(
        "login.html",
        {"request": request, "error": None, "ps": get_portal_settings(), "lang": _lang(request)},
    )


@router.post("/portal/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def portal_login_submit(request: Request,
                               email: str = Form(...),
                               password: str = Form(...)):
    email = email.strip().lower()
    ip    = _client_ip(request)
    ps    = get_portal_settings()

    locked, remaining = check_lockout(email, "portal")
    if locked:
        return customer_tpl.TemplateResponse(
            "login.html",
            {"request": request, "ps": ps, "lang": _lang(request),
             "error": f"Please try again after {remaining} minutes."},
        )

    customer = get_customer_by_email(email)
    if customer and await verify_pw_async(password, customer["password_hash"]):
        # Check if account is locked by admin
        if customer.get("is_locked"):
            return customer_tpl.TemplateResponse(
                "login.html",
                {"request": request, "ps": ps, "lang": _lang(request),
                 "error": "Your account has been suspended. Please contact support."},
            )
        clear_attempts(email, "portal")
        # Transparent rehash: upgrade PBKDF2 → Argon2 on successful login
        if needs_rehash(customer["password_hash"]):
            new_hash = await hash_pw_async(password)
            set_customer_password(customer["login_email"], new_hash)
        update_last_login(customer["login_email"])
        request.session["customer_email"] = customer["login_email"]
        request.session["customer_name"]  = customer["name"]
        request.session["must_change_password"] = customer["must_change_password"]
        return RedirectResponse(url="/portal/", status_code=302)

    record_attempt(email, "portal", ip)
    return customer_tpl.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid email or password.", "ps": ps, "lang": _lang(request)},
    )


@router.get("/portal/logout")
async def portal_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/portal/login", status_code=302)


# ── Dashboard (minimal — will be rebuilt) ─────────────────────────────────────

def _build_enrollments(broker_accounts: list) -> list:
    """Build enrollment rows from customer_accounts with program names."""
    program_ids: set = set()
    for a in broker_accounts:
        if a.get("pending_program_id"):
            program_ids.add(a["pending_program_id"])
        if a.get("program_id"):
            program_ids.add(a["program_id"])
    if not program_ids:
        return []
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        ph = ",".join("?" * len(program_ids))
        rows = conn.execute(
            f"SELECT id, name FROM programs WHERE id IN ({ph})",
            list(program_ids),
        ).fetchall()
    prog_names = {r["id"]: r["name"] for r in rows}

    result = []
    for a in broker_accounts:
        prog_id = a.get("program_id") or a.get("pending_program_id")
        if not prog_id:
            continue
        result.append({
            "account_id":     a["id"],
            "broker_name":    a.get("broker_name", ""),
            "broker_slug":    a.get("broker_slug", ""),
            "broker_email":   a.get("broker_email") or "",
            "use_id":         a.get("use_id") or "",
            "program_id":     prog_id,
            "program_name":   prog_names.get(prog_id, f"Program #{prog_id}"),
            "program_status": a.get("program_status") or "",
            "client_status":  a.get("client_status") or "",
            "is_active":      bool(a.get("program_id")),
        })
    return result


def _load_promotions_for_portal(lang: str = "en") -> list:
    """Load all active programs with broker info and tiers for the portal promotions tab.

    Uses separate queries instead of JOIN to avoid duplicating programs that
    are linked to multiple brokers.
    """
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        # Programs only — no JOIN, no duplicates
        rows = conn.execute(
            """SELECT p.id, p.name, p.name_en, p.type, p.rebate_pct, p.display_order,
                      p.rebate_usd_per_lot,
                      ISNULL(p.card_template, 'default') AS card_template,
                      ISNULL(p.is_recommended, 0)        AS is_recommended,
                      p.licenses, p.leverage, p.features, p.rebate_xau_label
               FROM programs p
               WHERE p.is_active = 1
               ORDER BY p.display_order, p.id"""
        ).fetchall()

        # All broker links for active programs
        broker_rows = conn.execute(
            """SELECT pb.program_id,
                      b.id       AS broker_id,
                      b.name     AS broker_name,
                      b.slug     AS broker_slug,
                      b.licenses AS broker_licenses,
                      b.leverage AS broker_leverage
               FROM program_brokers pb
               JOIN brokers b ON b.id = pb.broker_id
               WHERE b.is_active = 1
               ORDER BY b.display_order"""
        ).fetchall()

        brokers_map: dict = {}
        for br in broker_rows:
            brokers_map.setdefault(br["program_id"], []).append(dict(br))

        # Tiers for all programs
        tier_rows = conn.execute(
            "SELECT * FROM program_tiers ORDER BY program_id, tier_number"
        ).fetchall()
        tiers_map: dict = {}
        for t in tier_rows:
            tiers_map.setdefault(t["program_id"], []).append(dict(t))

    def _norm_tier(t: dict) -> dict:
        """Map DB column names → JS field names used by the calculator."""
        rv   = float(t.get("reward_value") or 0)
        rtyp = str(t.get("reward_type") or "")
        return {
            **t,
            "min_lots":    t.get("target_lot", 0),
            "rebate_pct":  rv if "backcom_pct" in rtyp else 0,
            "voucher_usd": rv if "bonus_usd" in rtyp else None,
        }

    def _fix_dec(d):
        from decimal import Decimal as _D
        if isinstance(d, dict):
            return {k: _fix_dec(v) for k, v in d.items()}
        if isinstance(d, list):
            return [_fix_dec(v) for v in d]
        if isinstance(d, _D):
            return float(d)
        return d

    result = []
    for r in rows:
        pid = r["id"]
        prog_brokers = brokers_map.get(pid, [])
        prog = _fix_dec(dict(r))
        primary = prog_brokers[0] if prog_brokers else {}
        if not prog.get("licenses"):
            prog["licenses"] = primary.get("broker_licenses")
        if not prog.get("leverage"):
            prog["leverage"] = primary.get("broker_leverage")
        # Localise program name for the current viewer
        if lang == "en" and (prog.get("name_en") or "").strip():
            prog["name"] = prog["name_en"]
        result.append({
            **prog,
            # Primary broker (for display / filter)
            "broker_id":   primary.get("broker_id"),
            "broker_name": primary.get("broker_name", ""),
            "broker_slug": primary.get("broker_slug", ""),
            # All broker IDs linked to this program (for multi-broker filter)
            "broker_ids":  [b["broker_id"] for b in prog_brokers],
            "short_desc":  "",
            "details":     {},
            "db_tiers":    [_fix_dec(_norm_tier(t)) for t in tiers_map.get(pid, [])],
            "comm_rates":  [],
            "enrollment_restriction": None,
            "account_type": None,
        })
    return result


@router.get("/portal/dashboard")
async def portal_dashboard_redirect(request: Request):
    qs = ("?" + str(request.query_params)) if request.query_params else ""
    return RedirectResponse(url=f"/portal/{qs}", status_code=301)


@router.get("/portal/", response_class=HTMLResponse)
async def portal_dashboard(request: Request):
    email    = request.session.get("customer_email", "")
    name     = request.session.get("customer_name", "")
    customer = get_customer_by_email(email) or {}
    brokers  = get_all_brokers()

    # Broker accounts for this customer
    broker_accounts = []
    if customer.get("id"):
        broker_accounts = get_accounts_for_customer(customer["id"])

    # Programs for promotions tab
    promotions = await asyncio.to_thread(_load_promotions_for_portal, _lang(request))

    # Broker IDs where customer is enrolled (pending or active)
    enrolled_broker_ids: set = {
        a["broker_id"] for a in broker_accounts
        if a.get("pending_program_id") or a.get("program_id")
    }
    # Promo IDs customer is currently enrolled in (to show "Enrolled")
    enrolled_promo_ids: set = (
        {a["pending_program_id"] for a in broker_accounts if a.get("pending_program_id")} |
        {a["program_id"] for a in broker_accounts if a.get("program_id")}
    )
    # (promo_id, broker_id) pairs — for exact match check in template
    enrolled_pairs: set = (
        {f"{a['pending_program_id']}_{a['broker_id']}" for a in broker_accounts if a.get("pending_program_id")} |
        {f"{a['program_id']}_{a['broker_id']}" for a in broker_accounts if a.get("program_id")}
    )

    # Verified accounts only — for history tab broker selector
    verified_accounts = [a for a in broker_accounts if a.get("customer_linked_at")]

    # Enrollment management tab
    enrollments_list = _build_enrollments(broker_accounts)

    return customer_tpl.TemplateResponse("dashboard.html", _cctx(request,
        customer_name=name,
        customer=customer,
        brokers=brokers,
        broker_accounts=broker_accounts,
        broker_emails=verified_accounts,
        all_broker_emails=broker_accounts,
        params=dict(request.query_params),
        enrollment=None,
        enrolled_promo_ids=enrolled_promo_ids,
        enrolled_broker_ids=enrolled_broker_ids,
        enrolled_pairs=enrolled_pairs,
        promotions=promotions,
        rebate_data=[],
        enrollments_list=enrollments_list,
        edit_mode=False,
        error=None,
    ))


# ── Broker account linking ─────────────────────────────────────────────────────

@router.get("/portal/api/broker-emails")
async def portal_get_broker_emails(request: Request):
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"items": []})
    rows = await asyncio.to_thread(get_accounts_for_customer, customer["id"])
    items = [
        {
            "id":           r["id"],
            "broker_id":    r["broker_id"],
            "broker_name":  r["broker_name"],
            "slug":         r["broker_slug"],
            "broker_email": r.get("broker_email", ""),
            "client_status": r.get("client_status", ""),
        }
        for r in rows
    ]
    return JSONResponse({"items": items})


@router.get("/portal/api/rebate-data")
async def portal_rebate_data(request: Request, broker: str = "all", month: str = "", period: str = "month"):
    """Aggregated rebate overview + daily chart for Tab 1 dashboard.

    Returns:
      rebate       — total_comm, total_lots (for donut)
      monthly      — monthly bars data (last 12 months)
      daily_chart  — daily bars + cumulative line for the selected month
      months_list  — list of available months for selector
      progress     — lots/comm vs. next bonus milestone
    """
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"rebate": {}, "daily_chart": {}, "progress": None})

    from app.db.connection import get_conn as _gc
    from datetime import date

    with _gc() as conn:
        # Resolve customer_account ids (verified only)
        q = """SELECT ca.id, ca.use_id, b.slug AS broker_slug
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               WHERE ca.customer_id = ?
                 AND ca.customer_linked_at IS NOT NULL"""
        params: list = [customer["id"]]
        if broker != "all":
            q += " AND b.slug = ?"
            params.append(broker)
        accounts = conn.execute(q, params).fetchall()

        if not accounts:
            return JSONResponse({"rebate": {}, "chart": {}, "progress": None})

        ca_ids   = [a["id"]     for a in accounts]
        use_ids  = [a["use_id"] for a in accounts if a["use_id"]]
        ph_ca    = ",".join("?" * len(ca_ids))
        ph_uid   = ",".join("?" * len(use_ids)) if use_ids else "''"

        def _f(v): return float(v or 0)

        # ── All-time aggregated assets from rebate_records ──────────────────────
        agg = conn.execute(
            f"""SELECT
                    SUM(total_volume)           AS total_volume,
                    SUM(total_commission)       AS total_commission,
                    SUM(fx_lot)                 AS fx_lot,
                    SUM(fx_commission)          AS fx_commission,
                    SUM(hang_hoa_lot)           AS hang_hoa_lot,
                    SUM(hang_hoa_commission)    AS hang_hoa_commission,
                    SUM(index_lot)              AS index_lot,
                    SUM(index_commission)       AS index_commission,
                    SUM(crypto_lot)             AS crypto_lot,
                    SUM(crypto_commission)      AS crypto_commission,
                    SUM(sharecfd_lot)           AS sharecfd_lot,
                    SUM(sharecfd_commission)    AS sharecfd_commission,
                    SUM(bond_lot)               AS bond_lot,
                    SUM(bond_commission)        AS bond_commission,
                    SUM(synthetic_lot)          AS synthetic_lot,
                    SUM(synthetic_commission)   AS synthetic_commission
               FROM rebate_records
               WHERE customer_account_id IN ({ph_ca})""",
            ca_ids,
        ).fetchone()

        rebate = {
            "total_comm": _f(agg["total_commission"]) if agg else 0,
            "total_lots": _f(agg["total_volume"])     if agg else 0,
            "assets": {
                "fx":        {"std_lots": _f(agg["fx_lot"]),        "std_comm": _f(agg["fx_commission"]),        "micro_lots": 0, "micro_comm": 0},
                "hang_hoa":  {"std_lots": _f(agg["hang_hoa_lot"]),  "std_comm": _f(agg["hang_hoa_commission"]),  "micro_lots": 0, "micro_comm": 0},
                "index":     {"std_lots": _f(agg["index_lot"]),     "std_comm": _f(agg["index_commission"]),     "micro_lots": 0, "micro_comm": 0},
                "crypto":    {"std_lots": _f(agg["crypto_lot"]),    "std_comm": _f(agg["crypto_commission"]),    "micro_lots": 0, "micro_comm": 0},
                "sharecfd":  {"std_lots": _f(agg["sharecfd_lot"]),  "std_comm": _f(agg["sharecfd_commission"]),  "micro_lots": 0, "micro_comm": 0},
                "bond":      {"std_lots": _f(agg["bond_lot"]),      "std_comm": _f(agg["bond_commission"]),      "micro_lots": 0, "micro_comm": 0},
                "synthetic": {"std_lots": _f(agg["synthetic_lot"]), "std_comm": _f(agg["synthetic_commission"]), "micro_lots": 0, "micro_comm": 0},
            } if agg else {},
        }

        # ── Monthly list from rebate_records ────────────────────────────────────
        months_list: list = []
        monthly_map: dict = {}  # "YYYY-MM" → month_rebate total
        selected_month = month  # e.g. "2026-03"

        if ca_ids:
            monthly_rows = conn.execute(
                f"""SELECT YEAR(rb.period_date)  AS year,
                           MONTH(rb.period_date) AS month,
                           SUM(rr.rebate_amount) AS month_rebate
                    FROM rebate_records rr
                    JOIN rebate_batches rb ON rb.id = rr.batch_id
                    WHERE rr.customer_account_id IN ({ph_ca})
                    GROUP BY YEAR(rb.period_date), MONTH(rb.period_date)
                    ORDER BY year DESC, month DESC""",
                ca_ids,
            ).fetchall()

            for r in monthly_rows:
                key = f"{r['year']}-{r['month']:02d}"
                label = f"T{r['month']}/{r['year']}"
                months_list.append({"key": key, "label": label})
                monthly_map[key] = _f(r["month_rebate"])

            months_list.reverse()  # ascending for display (oldest → newest)

            if not selected_month and monthly_rows:
                selected_month = f"{monthly_rows[0]['year']}-{monthly_rows[0]['month']:02d}"

        # ── Chart: daily bars for month view, monthly bars for year view ────────
        daily_chart: dict = {"labels": [], "commission": [], "cumulative": [],
                              "month_label": "", "month_key": selected_month,
                              "chart_period": period}

        if ca_ids:
            today_d = date.today()
            try:
                if period == "year":
                    # Monthly bars for current year (T1 → T12)
                    year_rows = conn.execute(
                        f"""SELECT MONTH(rb.period_date) AS m,
                                   SUM(rr.rebate_amount)  AS month_rebate
                            FROM rebate_records rr
                            JOIN rebate_batches rb ON rb.id = rr.batch_id
                            WHERE rr.customer_account_id IN ({ph_ca})
                              AND YEAR(rb.period_date) = ?
                            GROUP BY MONTH(rb.period_date)
                            ORDER BY m""",
                        ca_ids + [today_d.year],
                    ).fetchall()
                    month_map = {r["m"]: _f(r["month_rebate"]) for r in year_rows}
                    cum = 0.0
                    for m in range(1, 13):
                        amt = round(month_map.get(m, 0.0), 2)
                        cum = round(cum + amt, 2)
                        daily_chart["labels"].append(f"T{m}")
                        daily_chart["commission"].append(amt)
                        daily_chart["cumulative"].append(cum)
                    daily_chart["month_label"] = f"Year {today_d.year}"
                    daily_chart["month_key"]   = str(today_d.year)

                elif selected_month:
                    # Daily bars for selected month
                    sy, sm = int(selected_month[:4]), int(selected_month[5:7])
                    daily_chart["month_label"] = f"{sm}/{sy}"
                    day_rows = conn.execute(
                        f"""SELECT rb.period_date AS trade_date,
                                   SUM(rr.rebate_amount) AS day_rebate
                            FROM rebate_records rr
                            JOIN rebate_batches rb ON rb.id = rr.batch_id
                            WHERE rr.customer_account_id IN ({ph_ca})
                              AND YEAR(rb.period_date)  = ?
                              AND MONTH(rb.period_date) = ?
                            GROUP BY rb.period_date
                            ORDER BY trade_date""",
                        ca_ids + [sy, sm],
                    ).fetchall()
                    cum = 0.0
                    for row in day_rows:
                        amt = round(_f(row["day_rebate"]), 2)
                        cum = round(cum + amt, 2)
                        daily_chart["labels"].append(str(row["trade_date"])[8:10])
                        daily_chart["commission"].append(amt)
                        daily_chart["cumulative"].append(cum)
            except Exception:
                pass

        # ── Progress / rebate-rate widget ────────────────────────────────────
        today    = date.today()
        progress = None

        if ca_ids:
            prog_row = conn.execute(
                """SELECT p.id AS prog_id, p.type AS prog_type, p.name AS prog_name
                   FROM customer_accounts ca
                   JOIN programs p ON p.id = ca.program_id
                   WHERE ca.id = ?""",
                (ca_ids[0],),
            ).fetchone()

            if prog_row and prog_row["prog_type"] == "backcom":
                # Backcom: show current rebate % based on cumulative lots
                cum_row = conn.execute(
                    f"""SELECT SUM(rr.total_volume) AS cum_lots
                        FROM rebate_records rr
                        WHERE rr.customer_account_id IN ({ph_ca})""",
                    ca_ids,
                ).fetchone()
                cum_lots = _f(cum_row["cum_lots"]) if cum_row else 0.0

                tier_rows = conn.execute(
                    """SELECT target_lot, reward_value, label
                       FROM program_tiers
                       WHERE program_id = ? AND reward_type = 'backcom_pct'
                       ORDER BY target_lot""",
                    (prog_row["prog_id"],),
                ).fetchall()

                current_tier = tier_rows[0] if tier_rows else None
                next_tier    = None
                for i, t in enumerate(tier_rows):
                    if cum_lots >= _f(t["target_lot"]):
                        current_tier = t
                        next_tier = tier_rows[i + 1] if i + 1 < len(tier_rows) else None

                progress = {
                    "reward_type":        "backcom_pct",
                    "prog_name":          prog_row["prog_name"] or "",
                    "current_pct":        _f(current_tier["reward_value"]) if current_tier else 0.0,
                    "current_lots":       round(cum_lots, 2),
                    "current_tier_label": current_tier["label"] if current_tier else "",
                    "next_tier_lots":     _f(next_tier["target_lot"]) if next_tier else None,
                    "next_tier_pct":      _f(next_tier["reward_value"]) if next_tier else None,
                    "next_tier_label":    next_tier["label"] if next_tier else None,
                }
            else:
                # Bonus USD: commodity lots progress for current month
                mon_row = conn.execute(
                    f"""SELECT SUM(rr.hang_hoa_lot) AS total_hoa
                        FROM rebate_records rr
                        JOIN rebate_batches rb ON rb.id = rr.batch_id
                        WHERE rr.customer_account_id IN ({ph_ca})
                          AND YEAR(rb.period_date)  = ?
                          AND MONTH(rb.period_date) = ?""",
                    ca_ids + [today.year, today.month],
                ).fetchone()
                month_hang_hoa = _f(mon_row["total_hoa"]) if mon_row else 0.0

                next_ms = conn.execute(
                    """SELECT pt.id, pt.target_lot, pt.reward_value, pt.label, p.name AS prog_name
                       FROM program_tiers pt
                       JOIN programs p ON p.id = pt.program_id
                       WHERE pt.reward_type = 'bonus_usd' AND pt.target_lot > ?
                       ORDER BY pt.target_lot""",
                    (month_hang_hoa,),
                ).fetchone()

                if not next_ms:
                    next_ms = conn.execute(
                        """SELECT pt.id, pt.target_lot, pt.reward_value, pt.label, p.name AS prog_name
                           FROM program_tiers pt
                           JOIN programs p ON p.id = pt.program_id
                           WHERE pt.reward_type = 'bonus_usd'
                           ORDER BY pt.target_lot DESC""",
                    ).fetchone()
                    all_achieved = True
                else:
                    all_achieved = False

                if next_ms:
                    target = _f(next_ms["target_lot"])
                    pct    = min(100, round(month_hang_hoa / target * 100, 1)) if target else 0
                    progress = {
                        "reward_type":    "bonus_usd",
                        "month_label":    f"{today.month}/{today.year}",
                        "current_lots":   round(month_hang_hoa, 2),
                        "target_lots":    target,
                        "reward_value":   _f(next_ms["reward_value"]),
                        "pct":            pct,
                        "remaining_lots": 0 if all_achieved else round(max(0, target - month_hang_hoa), 2),
                        "tier_label":     next_ms["label"] or "",
                        "prog_name":      next_ms["prog_name"] or "",
                        "all_achieved":   all_achieved,
                    }

    return JSONResponse({
        "rebate":       rebate,
        "daily_chart":  daily_chart,
        "months_list":  months_list,
        "progress":     progress,
    })


@router.get("/portal/api/rebate-history")
async def portal_rebate_history(request: Request, broker: str = "all", period: str = "all"):
    """Return commission history for the logged-in customer (reads rebate_records)."""
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"history": []})

    from app.db.connection import get_conn as _gc
    from datetime import date

    today = date.today()

    with _gc() as conn:
        q = """SELECT ca.id, ca.use_id, ca.client_name, b.slug AS broker_slug
               FROM customer_accounts ca
               JOIN brokers b ON b.id = ca.broker_id
               WHERE ca.customer_id = ?
                 AND ca.customer_linked_at IS NOT NULL"""
        q_params: list = [customer["id"]]
        if broker != "all":
            q += " AND b.slug = ?"
            q_params.append(broker)
        accounts = conn.execute(q, q_params).fetchall()

        if not accounts:
            return JSONResponse({"history": []})

        ca_ids = [a["id"] for a in accounts]
        if not ca_ids:
            return JSONResponse({"history": []})

        ph = ",".join("?" * len(ca_ids))

        # Period filter — rb = rebate_batches alias; pe = program_events alias
        period_filter_rb = ""   # for rebate_records JOIN rebate_batches (alias rb)
        period_filter_pe = ""   # for program_events  (alias pe)
        extra_params: list = []
        if period == "year":
            period_filter_rb = "AND YEAR(rb.period_date) = ?"
            period_filter_pe = "AND YEAR(pe.period_date) = ?"
            extra_params     = [today.year]
        elif period in ("month", "week", "day"):
            period_filter_rb = "AND YEAR(rb.period_date) = ? AND MONTH(rb.period_date) = ?"
            period_filter_pe = "AND YEAR(pe.period_date) = ? AND MONTH(pe.period_date) = ?"
            extra_params     = [today.year, today.month]

        # Group by day (period_date from rebate_batches) — shows exact trading date per row
        # Status priority: paid=3 > exported=2 > pending=1
        rows = conn.execute(
            f"""SELECT ca.use_id,
                       rb.period_date,
                       SUM(rr.hang_hoa_lot)     AS total_lots,
                       SUM(rr.rebate_amount)    AS rebate_amount,
                       MIN(CASE rr.status
                               WHEN 'paid'     THEN 3
                               WHEN 'exported' THEN 2
                               ELSE 1
                           END) AS status_priority
                FROM rebate_records rr
                JOIN customer_accounts ca ON ca.id = rr.customer_account_id
                JOIN rebate_batches rb ON rb.id = rr.batch_id
                WHERE rr.customer_account_id IN ({ph})
                  {period_filter_rb}
                GROUP BY ca.use_id, rb.period_date
                ORDER BY rb.period_date DESC""",
            ca_ids + extra_params,
        ).fetchall()

        # Bonus payments (program_events with event_type='bonus_paid')
        bonus_rows = conn.execute(
            f"""SELECT ca.use_id,
                       pe.period_date,
                       pe.lots_at_event  AS total_lots,
                       pe.amount_usd     AS rebate_amount
                FROM program_events pe
                JOIN customer_accounts ca ON ca.id = pe.customer_account_id
                WHERE pe.customer_account_id IN ({ph})
                  AND pe.event_type = 'bonus_paid'
                  AND pe.period_date IS NOT NULL
                  {period_filter_pe}
                ORDER BY pe.period_date DESC""",
            ca_ids + extra_params,
        ).fetchall()

    def _f(v): return float(v or 0)

    _status_map = {3: "paid", 2: "exported", 1: "pending"}

    history = []
    for r in rows:
        history.append({
            "mt5_account":   r["use_id"] or "—",
            "period_date":   str(r["period_date"])[:10],
            "total_lots":    _f(r["total_lots"]),
            "rebate_amount": _f(r["rebate_amount"]),
            "status":        _status_map.get(r["status_priority"], "pending"),
            "note":          "Daily backcom",
        })
    for r in bonus_rows:
        history.append({
            "mt5_account":   r["use_id"] or "—",
            "period_date":   str(r["period_date"])[:10],
            "total_lots":    _f(r["total_lots"]),
            "rebate_amount": _f(r["rebate_amount"]),
            "status":        "paid",
            "note":          "Bonus",
        })

    history.sort(key=lambda x: x["period_date"], reverse=True)
    return JSONResponse({"history": history})


async def _link_broker_email(
    customer_id: int, broker_id: int, broker_email: str,
    verify_token: str = "",
) -> int:
    """Link broker_email to customer (pending verification), reusing lead row if found.

    Priority:
    1. Lead row matching broker_email → set customer_id + verify_token on it.
    2. Existing row for (customer_id, broker_id) → update broker_email + token.
    3. No match → create new row.
    Returns the customer_account id.
    """
    existing_by_email = await asyncio.to_thread(
        get_account_by_broker_email, broker_id, broker_email
    )
    if existing_by_email:
        if not existing_by_email.get("customer_id"):
            # Lead row found — but first check if customer already has a separate
            # account for this broker (would violate UQ_ca_customer_broker if we link).
            ca = await asyncio.to_thread(get_customer_account, customer_id, broker_id)
            if ca:
                # Customer already has an account — update it with the broker_email instead.
                await asyncio.to_thread(
                    update_customer_account, ca["id"],
                    broker_email=broker_email, link_verify_token=verify_token, customer_linked_at=None,
                )
                return ca["id"]
            await asyncio.to_thread(
                link_customer_to_account, existing_by_email["id"], customer_id, verify_token
            )
        else:
            # Already linked to this customer — update token for re-verification
            await asyncio.to_thread(
                update_customer_account, existing_by_email["id"],
                link_verify_token=verify_token, customer_linked_at=None,
            )
        return existing_by_email["id"]

    ca = await asyncio.to_thread(get_customer_account, customer_id, broker_id)
    if ca:
        await asyncio.to_thread(
            update_customer_account, ca["id"],
            broker_email=broker_email, link_verify_token=verify_token, customer_linked_at=None,
        )
        return ca["id"]

    return await asyncio.to_thread(
        create_customer_account, broker_id,
        customer_id=customer_id, broker_email=broker_email,
        link_verify_token=verify_token or None,
    )


@router.post("/portal/api/broker-emails")
async def portal_add_broker_email(request: Request):
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    data = await request.json()
    broker_id    = data.get("broker_id")
    broker_email = (data.get("broker_email") or "").strip().lower()
    if not broker_id or not broker_email or not _EMAIL_RE.match(broker_email):
        return JSONResponse({"error": "Invalid information"}, status_code=400)

    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        broker = conn.execute(
            "SELECT id, name FROM brokers WHERE id=?", (broker_id,)
        ).fetchone()
        if not broker:
            return JSONResponse({"error": "Broker not found"}, status_code=400)

    conflict = await asyncio.to_thread(get_account_by_broker_email, broker_id, broker_email)
    if conflict and conflict.get("customer_id") and conflict.get("login_email") != email:
        return JSONResponse(
            {"error": "This email is already linked to another account."}, status_code=409
        )

    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    verify_token = uuid.uuid4().hex
    from app.services.notifications import _site_url
    verify_url = f"{_site_url()}/portal/verify-broker-email?token={verify_token}"
    row_id = await _link_broker_email(customer["id"], broker_id, broker_email, verify_token)
    asyncio.create_task(_fire(
        send_broker_email_verify(broker_email, customer.get("name", email), broker["name"], verify_url),
        label="broker_email_verify",
    ))
    asyncio.create_task(_fire(
        notify_broker_email_linked(email, broker_email, broker["name"]),
        label="notify_broker_email_linked",
    ))
    return JSONResponse({"ok": True, "pending": True, "id": row_id,
                         "broker_name": broker["name"], "broker_email": broker_email,
                         "message": f"Verification email sent to {broker_email}. Please check your inbox and click confirm."})


@router.post("/portal/api/link-vantage-email")
async def portal_link_vantage_email(request: Request):
    """Save broker email to customer_accounts (legacy endpoint kept for compat)."""
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    data = await request.json()

    broker_email = (
        data.get("broker_email") or data.get("vantage_email") or ""
    ).strip().lower()
    if not broker_email or not _EMAIL_RE.match(broker_email):
        return JSONResponse({"error": "Invalid email"}, status_code=400)

    broker_id = data.get("broker_id")
    if not broker_id:
        from app.db.connection import get_conn as _gc
        with _gc() as conn:
            row = conn.execute("SELECT id FROM brokers WHERE slug='vantage'").fetchone()
            broker_id = row["id"] if row else None
    if not broker_id:
        return JSONResponse({"error": "Could not determine broker"}, status_code=400)

    conflict = await asyncio.to_thread(get_account_by_broker_email, broker_id, broker_email)
    if conflict and conflict.get("customer_id") and conflict.get("login_email") != email:
        return JSONResponse(
            {"error": "This email is already linked to another account."}, status_code=409
        )

    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    broker_row = None
    from app.db.connection import get_conn as _gc2
    with _gc2() as conn:
        broker_row = conn.execute("SELECT name FROM brokers WHERE id=?", (broker_id,)).fetchone()

    verify_token = uuid.uuid4().hex
    from app.services.notifications import _site_url
    verify_url = f"{_site_url()}/portal/verify-broker-email?token={verify_token}"
    await _link_broker_email(customer["id"], broker_id, broker_email, verify_token)
    broker_name = broker_row["name"] if broker_row else "broker"
    asyncio.create_task(_fire(
        send_broker_email_verify(
            broker_email, customer.get("name", email),
            broker_name, verify_url,
        ),
        label="broker_email_verify",
    ))
    asyncio.create_task(_fire(
        notify_broker_email_linked(email, broker_email, broker_name),
        label="notify_broker_email_linked",
    ))
    return JSONResponse({"ok": True, "pending": True,
                         "message": f"Verification email sent to {broker_email}. Please check your inbox and click confirm."})


@router.delete("/portal/api/broker-emails/{account_id}")
async def portal_delete_broker_email(account_id: int, request: Request):
    email = request.session.get("customer_email", "")
    if not email:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    customer = get_customer_by_email(email)
    if not customer:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Verify the account belongs to this customer before deleting
    ca = await asyncio.to_thread(get_customer_account_by_id, account_id)
    if not ca or ca.get("customer_id") != customer["id"]:
        return JSONResponse({"error": "Not found"}, status_code=404)

    from app.db.repositories.customer_accounts import unlink_customer_account
    await asyncio.to_thread(unlink_customer_account, account_id)
    return JSONResponse({"ok": True})


@router.get("/portal/verify-broker-email", response_class=HTMLResponse)
async def portal_verify_broker_email(request: Request, token: str = ""):
    """Single-click verification link sent to broker_email."""
    if not token:
        return customer_tpl.TemplateResponse("verify_broker_email.html",
            _cctx(request, success=False, message="Verification link is invalid."))
    ok = await asyncio.to_thread(verify_broker_email_token, token)
    if ok:
        return customer_tpl.TemplateResponse("verify_broker_email.html",
            _cctx(request, success=True, message="Verification successful! Broker account has been linked."))
    return customer_tpl.TemplateResponse("verify_broker_email.html",
        _cctx(request, success=False, message="Link has already been used or is invalid."))


# ── Password management ───────────────────────────────────────────────────────

@router.get("/portal/change-password", response_class=HTMLResponse)
async def portal_change_pw_page(request: Request):
    return customer_tpl.TemplateResponse("change_password.html", {
        "request": request,
        "customer_email": request.session.get("customer_email", ""),
        "ps": get_portal_settings(),
        "error": None,
    })


@router.post("/portal/change-password", response_class=HTMLResponse)
async def portal_change_pw_submit(request: Request,
                                   new_password: str = Form(...),
                                   confirm_password: str = Form(...)):
    email = request.session.get("customer_email", "")
    if not email:
        return RedirectResponse(url="/portal/login", status_code=302)
    ps  = get_portal_settings()
    ctx = {"request": request, "customer_email": email, "ps": ps}
    if len(new_password) < 8:
        return customer_tpl.TemplateResponse(
            "change_password.html", {**ctx, "error": "Password must be at least 8 characters."}
        )
    if new_password != confirm_password:
        return customer_tpl.TemplateResponse(
            "change_password.html", {**ctx, "error": "Passwords do not match."}
        )
    set_customer_password(email, await hash_pw_async(new_password), must_change=0)
    request.session["must_change_password"] = 0
    return RedirectResponse(url="/portal/", status_code=302)


@router.get("/portal/forgot-password", response_class=HTMLResponse)
async def portal_forgot_pw_page(request: Request):
    return customer_tpl.TemplateResponse("forgot_password.html", {
        "request": request, "customer_email": "", "ps": get_portal_settings(),
        "sent": False, "error": None,
    })


@router.post("/portal/forgot-password", response_class=HTMLResponse)
@limiter.limit("3/minute")
async def portal_forgot_pw_submit(request: Request, email: str = Form(...)):
    normalized = email.strip().lower()
    customer = get_customer_by_email(normalized)
    if not customer:
        return customer_tpl.TemplateResponse("forgot_password.html", {
            "request": request, "customer_email": "", "ps": get_portal_settings(),
            "sent": False, "error": "This email is not registered in the system.", "email_val": normalized,
        })

    token   = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    set_reset_token(customer["login_email"], token, expires)
    from app.db.repositories.smtp import get_smtp_config
    cfg = get_smtp_config()
    if cfg.get("host") and cfg.get("host") != "localhost":
        _oauth_cfg = get_google_oauth_config()
        base_url = (_oauth_cfg.get("site_url") or str(request.base_url)).rstrip("/")
        link = f"{base_url}/portal/reset-password/{token}"
        asyncio.create_task(_fire(
            send_reset_email(cfg, customer["login_email"], link), label="send_reset_email"
        ))
    return customer_tpl.TemplateResponse("forgot_password.html", {
        "request": request, "customer_email": "", "ps": get_portal_settings(),
        "sent": True, "error": None,
    })


@router.get("/portal/reset-password/{token}", response_class=HTMLResponse)
async def portal_reset_pw_page(token: str, request: Request):
    customer = get_customer_by_reset_token(token)
    valid = False
    if customer and customer.get("reset_token_expires"):
        expires = customer["reset_token_expires"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        valid = datetime.now(timezone.utc) < expires
    return customer_tpl.TemplateResponse("reset_password.html", {
        "request": request, "customer_email": "", "ps": get_portal_settings(),
        "token": token, "valid": valid, "error": None,
    })


@router.post("/portal/reset-password/{token}", response_class=HTMLResponse)
async def portal_reset_pw_submit(token: str, request: Request,
                                  new_password: str = Form(...),
                                  confirm_password: str = Form(...)):
    customer = get_customer_by_reset_token(token)
    ps  = get_portal_settings()
    ctx = {"request": request, "customer_email": "", "ps": ps, "token": token}
    if not customer or not customer.get("reset_token_expires"):
        return customer_tpl.TemplateResponse("reset_password.html",
                                             {**ctx, "valid": False, "error": None})
    expires = customer["reset_token_expires"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= expires:
        return customer_tpl.TemplateResponse("reset_password.html",
                                             {**ctx, "valid": False, "error": "Link has expired."})
    if len(new_password) < 8:
        return customer_tpl.TemplateResponse("reset_password.html",
                                             {**ctx, "valid": True, "error": "Password must be at least 8 characters."})
    if new_password != confirm_password:
        return customer_tpl.TemplateResponse("reset_password.html",
                                             {**ctx, "valid": True, "error": "Passwords do not match."})
    # Atomic: only reset if token is still valid (prevents TOCTOU race)
    pw_hash = await hash_pw_async(new_password)
    from app.db.connection import get_conn as _gc
    with _gc() as conn:
        result = conn.execute(
            "UPDATE customers SET password_hash=?, must_change_password=0, "
            "reset_token=NULL, reset_token_expires=NULL "
            "WHERE login_email=? AND reset_token=? AND reset_token_expires > GETUTCDATE()",
            (pw_hash, customer["login_email"], token),
        )
        if result.rowcount == 0:
            return customer_tpl.TemplateResponse("reset_password.html",
                                                 {**ctx, "valid": False, "error": "Link expired or already used."})
    return RedirectResponse(url="/portal/login?reset=1", status_code=302)


@router.post("/portal/unsubscribe")
async def portal_unsubscribe(request: Request):
    email = request.session.get("customer_email", "")
    if email:
        set_unsubscribed(email, 1)
    return RedirectResponse(url="/portal/", status_code=302)


@router.post("/portal/enroll")
@limiter.limit("10/minute")
async def portal_enroll(
    request: Request,
    promotion_id: int = Form(...),
    owner_id: Optional[int] = Form(None),
    mt5_account: Optional[str] = Form(None),
    vantage_email: Optional[str] = Form(None),
    transfer_method: str = Form("mailto_send"),
):
    customer_email = request.session.get("customer_email", "")
    if not customer_email:
        return JSONResponse({"ok": False, "detail": "Not logged in"}, status_code=401)

    customer = await asyncio.to_thread(get_customer_by_email, customer_email)
    if not customer:
        return JSONResponse({"ok": False, "detail": "Account not found"}, status_code=404)

    # Resolve broker from program
    broker_ids = await asyncio.to_thread(get_program_broker_ids, promotion_id)
    if not broker_ids:
        return JSONResponse({"ok": False, "detail": "Invalid program"}, status_code=400)

    # Find customer's account for one of the brokers in this program
    account = None
    matched_broker_id = None
    for bid in broker_ids:
        acc = await asyncio.to_thread(get_customer_account, customer["id"], bid)
        if acc:
            account = acc
            matched_broker_id = bid
            break

    # Dupoin / new-account flow: customer may not have a linked account yet.
    # If vantage_email is provided, create or link the account now.
    if not account and vantage_email and vantage_email.strip():
        broker_email_norm = vantage_email.strip().lower()
        target_broker_id = broker_ids[0]
        account_id = await _link_broker_email(
            customer["id"], target_broker_id, broker_email_norm,
        )
        account = await asyncio.to_thread(get_customer_account_by_id, account_id)
        matched_broker_id = target_broker_id

    if not account:
        return JSONResponse({"ok": False, "detail": "No linked broker account"}, status_code=400)

    # If broker_email was supplied but account already existed without one, save it
    if vantage_email and vantage_email.strip() and not account.get("broker_email"):
        await asyncio.to_thread(
            update_customer_account, account["id"],
            broker_email=vantage_email.strip().lower(),
        )

    # Block if already has an active/pending enrollment on this account
    if account.get("program_id") or account.get("pending_program_id"):
        return JSONResponse(
            {"ok": False, "detail": "This account already has an active or pending enrollment."},
            status_code=409,
        )

    # Map transfer_method → client_status
    new_status = "pending_transfer" if transfer_method == "mailto_send" else "pending_data"

    # Store pending enrollment — program_id set only after admin confirms
    await asyncio.to_thread(update_customer_account, account["id"],
                            pending_program_id=promotion_id,
                            program_status="unconfirmed",
                            client_status=new_status)

    # Persist MT5 account if provided
    if mt5_account and mt5_account.strip():
        from app.db.repositories.customer_accounts import upsert_trading_account
        await asyncio.to_thread(
            upsert_trading_account, account["id"], mt5_account.strip(),
        )

    prog = await asyncio.to_thread(get_program, promotion_id)
    promo_name = prog.get("name", "") if prog else str(promotion_id)

    logger.info("portal.enroll", customer=customer_email,
                program_id=promotion_id, status=new_status,
                mt5_account=mt5_account or "")

    asyncio.create_task(_fire(
        send_enrollment_notification(customer_email, promo_name, mt5_account or ""),
        label="send_enrollment_notification",
    ))

    return JSONResponse({"ok": True, "promo_name": promo_name})


@router.post("/portal/cancel-enrollment/{account_id}")
async def portal_cancel_enrollment(request: Request, account_id: int):
    customer_email = request.session.get("customer_email", "")
    if not customer_email:
        return RedirectResponse(url="/portal/login", status_code=302)

    customer = await asyncio.to_thread(get_customer_by_email, customer_email)
    if not customer:
        return RedirectResponse(url="/portal/login", status_code=302)

    account = await asyncio.to_thread(get_customer_account_by_id, account_id)
    if not account or account.get("customer_id") != customer["id"]:
        return RedirectResponse(url="/portal/", status_code=302)

    # Only allow cancelling unconfirmed (pending) enrollments.
    # Confirmed enrollments must be cancelled by admin.
    if account.get("program_status") == "confirmed":
        return RedirectResponse(url="/portal/?error=confirmed", status_code=302)

    await asyncio.to_thread(update_customer_account, account_id,
        pending_program_id=None,
        program_id=None,
        program_status=None,
        client_status="lead",
    )
    logger.info("portal.cancel_enrollment", customer=customer_email, account_id=account_id)
    return RedirectResponse(url="/portal/?cancelled=1", status_code=302)


# ── Gmail OAuth (transfer email) ───────────────────────────────────────────────

def _get_oauth_redirect_uri(cfg: dict) -> str:
    site = cfg.get("site_url", "").rstrip("/")
    return f"{site}/portal/oauth/callback"


@router.get("/portal/send-transfer", response_class=HTMLResponse)
async def portal_send_transfer(
    request: Request,
    ib_number: Optional[str] = None,
    broker_slug: Optional[str] = None,
):
    cfg = get_google_oauth_config()
    if not cfg.get("client_id") or not cfg.get("site_url"):
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            "request": request, "customer_email": "",
            "success": False,
            "error": "Feature not configured. Please contact support.",
        })
    if ib_number:
        request.session["transfer_ib_number"] = ib_number
    # Detect broker_slug from pending_transfer account if not provided
    if not broker_slug:
        customer_email = request.session.get("customer_email", "")
        if customer_email:
            cust = get_customer_by_email(customer_email)
            if cust:
                from app.db.connection import get_conn as _gc
                with _gc() as conn:
                    row = conn.execute(
                        """SELECT b.slug FROM customer_accounts ca
                           JOIN brokers b ON b.id = ca.broker_id
                           WHERE ca.customer_id = ? AND ca.client_status = 'pending_transfer'
                           LIMIT 1""",
                        (cust["id"],),
                    ).fetchone()
                    if row:
                        broker_slug = row["slug"]
    request.session["transfer_broker_slug"] = broker_slug or "vantage"

    redirect_uri = _get_oauth_redirect_uri(cfg)
    flow = make_flow(cfg["client_id"], cfg["client_secret"], redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true",
    )
    request.session["oauth_state"] = state
    return RedirectResponse(auth_url)


@router.get("/portal/oauth/callback", response_class=HTMLResponse)
async def portal_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    ctx = {"request": request, "customer_email": ""}

    if error:
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            **ctx, "success": False, "error": "You denied permission.",
        })
    if not code:
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            **ctx, "success": False, "error": "Missing authorization code from Google.",
        })

    cfg = get_google_oauth_config()
    redirect_uri = _get_oauth_redirect_uri(cfg)
    flow = make_flow(cfg["client_id"], cfg["client_secret"], redirect_uri)

    try:
        await asyncio.to_thread(flow.fetch_token, code=code)
    except Exception as e:
        logger.error("oauth.fetch_token_failed", error=str(e))
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            **ctx, "success": False, "error": f"Google authentication error: {e}",
        })

    creds = flow.credentials
    try:
        google_email = await asyncio.to_thread(_get_google_email_sync, creds)
    except Exception as e:
        logger.error("oauth.get_email_failed", error=str(e))
        google_email = "unknown"

    if creds.refresh_token:
        save_gmail_token(google_email, creds.refresh_token)

    ib_number   = request.session.pop("transfer_ib_number", "")
    broker_slug = request.session.pop("transfer_broker_slug", "vantage")

    try:
        await send_transfer_email(
            creds.refresh_token or get_gmail_token(google_email)["refresh_token"],
            cfg["client_id"], cfg["client_secret"], google_email,
            ib_number=ib_number,
            broker_slug=broker_slug,
        )
        logger.info("oauth.transfer_sent", from_email=google_email)
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            **ctx, "success": True, "google_email": google_email,
        })
    except Exception as e:
        logger.error("oauth.send_failed", from_email=google_email, error=str(e))
        from app.services.gmail import BROKER_TRANSFER_CONFIG
        broker_cfg = BROKER_TRANSFER_CONFIG.get(broker_slug) or BROKER_TRANSFER_CONFIG.get("vantage", {})
        return customer_tpl.TemplateResponse("send_transfer_result.html", {
            **ctx, "success": False, "error": f"Failed to send email: {e}",
            "ib_number": ib_number,
            "broker_support_email": broker_cfg.get("to", ""),
        })

"""Database schema.

Tables (29):
  Broker platform : brokers, ibs
  Programs        : programs, program_brokers, program_tiers
  Portal          : customers, customer_accounts, trading_accounts
  Rebate          : rebate_batches, commission_records, rebate_records, program_events
  Wallet          : customer_wallets, wallet_transactions, withdrawal_requests
  Email marketing : smtp_config, templates, campaigns, emails, opens
  Auth / System   : users, sessions, login_attempts, job_queue, audit_log
  Config          : portal_settings, google_oauth_config, gmail_send_tokens
  Content         : faq_items, contact_requests

Rebate flow:
  1. commission_records  — raw broker export, one row per trading_account per batch
                           contains per-instrument lots + commission (Excel column names)
  2. rebate_records      — aggregated per customer_account per batch (sum of all
                           trading accounts), program_tier applied → rebate_amount
  3. program_events      — milestone bonus history (bonus_milestone programs only)

Customer identification:
  customers.login_email        — web portal login (email A)
  customer_accounts.use_id     — broker platform User ID
  customer_accounts.broker_email — email registered at broker (email B, may differ)
  customer_accounts.ib_number  — IB managing this account (NULL for leads,
                                 required when client_status = 'active')
"""
import hashlib
import os
import re

import pyodbc

from app.db.connection import DATABASE, MASTER_CONN_STR, _CONN_STR, get_conn


# ── Helpers ────────────────────────────────────────────────────────────────────

def _table_exists(cur, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sys.tables WHERE name=? AND schema_id=SCHEMA_ID('dbo')",
        (name,),
    )
    return cur.fetchone() is not None


def _index_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sys.indexes WHERE name=?", (name,))
    return cur.fetchone() is not None


def _fk_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sys.foreign_keys WHERE name=?", (name,))
    return cur.fetchone() is not None


def _col_exists(cur, table: str, col: str) -> bool:
    cur.execute(
        "SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID(?) AND name=?",
        (f"dbo.{table}", col),
    )
    return cur.fetchone() is not None


# ── Entry point ────────────────────────────────────────────────────────────────

def init_db() -> None:
    _ensure_database()
    _drop_legacy_tables()
    _create_schema()
    _run_migrations()
    _seed_data()


def _run_migrations() -> None:
    """Additive schema migrations — safe to run on every startup."""
    with get_conn() as conn:
        def _col_exists(table: str, column: str) -> bool:
            return conn.execute(
                "SELECT 1 FROM sys.columns WHERE object_id=OBJECT_ID(?) AND name=?",
                (f"dbo.{table}", column),
            ).fetchone() is not None

        # v5: broker email verification flow
        if not _col_exists("customer_accounts", "link_verify_token"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD link_verify_token NVARCHAR(100) NULL"
            )
        if not _col_exists("customer_accounts", "customer_linked_at"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD customer_linked_at DATETIME2 NULL"
            )
            # Backfill: existing linked accounts (no pending token) are treated as verified
            conn.execute(
                """UPDATE customer_accounts
                   SET customer_linked_at = created_at
                   WHERE customer_id IS NOT NULL AND link_verify_token IS NULL"""
            )

        # v6: pending enrollment — program requested but not yet approved by admin
        if not _col_exists("customer_accounts", "pending_program_id"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD pending_program_id INT NULL"
            )
            conn.execute(
                "ALTER TABLE customer_accounts ADD CONSTRAINT FK_ca_pending_program "
                "FOREIGN KEY (pending_program_id) REFERENCES programs(id)"
            )
            # Migrate existing data: move program_id → pending_program_id for
            # pending_data / pending_transfer rows (not yet approved)
            conn.execute(
                """UPDATE customer_accounts
                   SET pending_program_id = program_id, program_id = NULL
                   WHERE program_id IS NOT NULL
                     AND client_status IN ('pending_data', 'pending_transfer')"""
            )

        # v7: program_status — admin confirmation state for enrolled programs
        if not _col_exists("customer_accounts", "program_status"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD program_status NVARCHAR(20) NULL"
            )
            conn.execute(
                """UPDATE customer_accounts SET program_status = 'unconfirmed'
                   WHERE pending_program_id IS NOT NULL"""
            )
            conn.execute(
                """UPDATE customer_accounts SET program_status = 'confirmed'
                   WHERE program_id IS NOT NULL"""
            )

        # v7b: customers.verify_token_expires — 24h expiry for email verify links
        if not _col_exists("customers", "verify_token_expires"):
            conn.execute(
                "ALTER TABLE customers ADD verify_token_expires DATETIME2 NULL"
            )

        # v8b: drop customer_type column — lead/client distinction is now derived
        # from customer_accounts.program_status = 'confirmed' instead.
        if _col_exists("customers", "customer_type"):
            try:
                # SQL Server: must drop DEFAULT constraint before dropping column
                conn.execute(
                    """DECLARE @con NVARCHAR(200)
                       SELECT @con = dc.name
                       FROM sys.default_constraints dc
                       JOIN sys.columns col ON dc.parent_object_id = col.object_id
                            AND dc.parent_column_id = col.column_id
                       JOIN sys.tables t ON col.object_id = t.object_id
                       WHERE t.name = 'customers' AND col.name = 'customer_type'
                       IF @con IS NOT NULL EXEC('ALTER TABLE customers DROP CONSTRAINT [' + @con + ']')"""
                )
                conn.execute("ALTER TABLE customers DROP COLUMN customer_type")
            except Exception:
                pass

        # v9: program_joined_at — when the customer started joining the program.
        # Only reset when unsubscribed; used as anchor for cumulative lot calculation.
        if not _col_exists("customer_accounts", "program_joined_at"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD program_joined_at DATETIME2 NULL"
            )
            # Backfill: existing confirmed accounts
            conn.execute(
                """UPDATE customer_accounts SET program_joined_at = created_at
                   WHERE program_id IS NOT NULL AND program_status = 'confirmed'"""
            )

        # v8: rebate_records.program_tier_id — make nullable so records without a
        # program (e.g. demo data, imported records) can still be stored.
        try:
            nullable = conn.execute(
                """SELECT is_nullable FROM sys.columns
                   WHERE object_id=OBJECT_ID('dbo.rebate_records') AND name='program_tier_id'"""
            ).fetchone()
            if nullable and not nullable["is_nullable"]:
                conn.execute(
                    "ALTER TABLE rebate_records DROP CONSTRAINT FK_rr_tier"
                )
                conn.execute(
                    "ALTER TABLE rebate_records ALTER COLUMN program_tier_id INT NULL"
                )
                conn.execute(
                    "ALTER TABLE rebate_records ADD CONSTRAINT FK_rr_tier "
                    "FOREIGN KEY (program_tier_id) REFERENCES program_tiers(id)"
                )
        except Exception:
            pass

        # v10: trading_date — persisted computed column on commission_records
        # CAST(uploaded_at AS DATE) is non-sargable; this column allows index seeks.
        if not _col_exists("commission_records", "trading_date"):
            conn.execute(
                "ALTER TABLE commission_records "
                "ADD trading_date AS CAST(uploaded_at AS DATE) PERSISTED"
            )
        if not conn.execute(
            "SELECT 1 FROM sys.indexes WHERE name='IX_cr_trading_date'"
        ).fetchone():
            conn.execute(
                "CREATE INDEX IX_cr_trading_date "
                "ON commission_records (trading_date, use_id)"
            )

        # v11: New Customer Promo — 100% rebate for first 30 days
        # promo_expires_at: when the promotional rate expires (auto-downgrade)
        # promo_original_program_id: program to revert to after promo ends
        if not _col_exists("customer_accounts", "promo_expires_at"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD promo_expires_at DATETIME2 NULL"
            )
        if not _col_exists("customer_accounts", "promo_original_program_id"):
            conn.execute(
                "ALTER TABLE customer_accounts ADD promo_original_program_id INT NULL"
            )

        # telegram: link tokens, sessions, message routing
        def _tbl(name: str) -> bool:
            return conn.execute(
                "SELECT 1 FROM sys.tables WHERE name=? AND schema_id=SCHEMA_ID('dbo')",
                (name,),
            ).fetchone() is not None

        if not _tbl("telegram_link_tokens"):
            conn.execute("""
                CREATE TABLE telegram_link_tokens (
                    token       NVARCHAR(32)  NOT NULL,
                    login_email NVARCHAR(255) NOT NULL,
                    expires_at  DATETIME2     NOT NULL,
                    CONSTRAINT PK_tg_link_tokens PRIMARY KEY (token)
                )
            """)
        if not _tbl("telegram_sessions"):
            conn.execute("""
                CREATE TABLE telegram_sessions (
                    login_email NVARCHAR(255) NOT NULL,
                    chat_id     BIGINT        NOT NULL,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_tg_sessions PRIMARY KEY (login_email)
                )
            """)
        if not _tbl("telegram_message_map"):
            conn.execute("""
                CREATE TABLE telegram_message_map (
                    admin_message_id  INT    NOT NULL,
                    customer_chat_id  BIGINT NOT NULL,
                    created_at        DATETIME2 NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_tg_msg_map PRIMARY KEY (admin_message_id)
                )
            """)

        # ── CMS: users.role ────────────────────────────────────────────────────
        if not _col_exists("users", "role"):
            conn.execute(
                "ALTER TABLE users ADD role NVARCHAR(20) NOT NULL DEFAULT 'admin'"
            )

        # ── CMS: media_files ───────────────────────────────────────────────────
        if not _tbl("media_files"):
            conn.execute("""
                CREATE TABLE media_files (
                    id            INT IDENTITY(1,1) NOT NULL,
                    filename      NVARCHAR(255) NOT NULL,
                    original_name NVARCHAR(255) NOT NULL DEFAULT '',
                    url           NVARCHAR(500) NOT NULL,
                    mime_type     NVARCHAR(100) NOT NULL DEFAULT '',
                    size_bytes    INT           NOT NULL DEFAULT 0,
                    alt_text      NVARCHAR(255) NOT NULL DEFAULT '',
                    uploaded_by   NVARCHAR(100) NOT NULL DEFAULT '',
                    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_media_files PRIMARY KEY (id)
                )
            """)
            conn.execute("CREATE INDEX IX_media_created ON media_files (created_at DESC)")

        # ── CMS: cms_article_categories ────────────────────────────────────────
        if not _tbl("cms_article_categories"):
            conn.execute("""
                CREATE TABLE cms_article_categories (
                    id            INT IDENTITY(1,1) NOT NULL,
                    name          NVARCHAR(255) NOT NULL,
                    slug          NVARCHAR(255) NOT NULL,
                    parent_id     INT           NULL,
                    display_order INT           NOT NULL DEFAULT 0,
                    CONSTRAINT PK_cms_cats  PRIMARY KEY (id),
                    CONSTRAINT UQ_cms_cats_slug UNIQUE (slug),
                    CONSTRAINT FK_cms_cats_parent FOREIGN KEY (parent_id)
                        REFERENCES cms_article_categories(id)
                )
            """)

        # ── CMS: cms_articles ──────────────────────────────────────────────────
        if not _tbl("cms_articles"):
            conn.execute("""
                CREATE TABLE cms_articles (
                    id            INT IDENTITY(1,1) NOT NULL,
                    slug          NVARCHAR(255) NOT NULL,
                    type          NVARCHAR(20)  NOT NULL DEFAULT 'post',
                    status        NVARCHAR(20)  NOT NULL DEFAULT 'draft',
                    lang          NVARCHAR(10)  NOT NULL DEFAULT 'vi',
                    title         NVARCHAR(500) NOT NULL DEFAULT '',
                    excerpt       NVARCHAR(MAX) NOT NULL DEFAULT '',
                    content       NVARCHAR(MAX) NOT NULL DEFAULT '',
                    cover_image_id INT          NULL,
                    category_id   INT           NULL,
                    author        NVARCHAR(100) NOT NULL DEFAULT '',
                    seo_title     NVARCHAR(255) NOT NULL DEFAULT '',
                    seo_desc      NVARCHAR(500) NOT NULL DEFAULT '',
                    seo_image     NVARCHAR(500) NOT NULL DEFAULT '',
                    published_at  DATETIME2     NULL,
                    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_cms_articles PRIMARY KEY (id),
                    CONSTRAINT UQ_cms_articles_slug UNIQUE (slug),
                    CONSTRAINT FK_cms_articles_cat FOREIGN KEY (category_id)
                        REFERENCES cms_article_categories(id),
                    CONSTRAINT FK_cms_articles_cover FOREIGN KEY (cover_image_id)
                        REFERENCES media_files(id)
                )
            """)
            conn.execute("CREATE INDEX IX_cms_articles_status ON cms_articles (status, published_at DESC)")
            conn.execute("CREATE INDEX IX_cms_articles_type   ON cms_articles (type, status)")

        # ── CMS: nav_items ─────────────────────────────────────────────────────
        if not _tbl("nav_items"):
            conn.execute("""
                CREATE TABLE nav_items (
                    id            INT IDENTITY(1,1) NOT NULL,
                    menu          NVARCHAR(50)  NOT NULL DEFAULT 'public_header',
                    label         NVARCHAR(255) NOT NULL DEFAULT '',
                    url           NVARCHAR(500) NOT NULL DEFAULT '',
                    target        NVARCHAR(10)  NOT NULL DEFAULT '_self',
                    parent_id     INT           NULL,
                    display_order INT           NOT NULL DEFAULT 0,
                    is_active     BIT           NOT NULL DEFAULT 1,
                    CONSTRAINT PK_nav_items PRIMARY KEY (id),
                    CONSTRAINT FK_nav_items_parent FOREIGN KEY (parent_id)
                        REFERENCES nav_items(id)
                )
            """)
            conn.execute("CREATE INDEX IX_nav_menu ON nav_items (menu, display_order)")

        # ── CMS: banners ───────────────────────────────────────────────────────
        if not _tbl("banners"):
            conn.execute("""
                CREATE TABLE banners (
                    id          INT IDENTITY(1,1) NOT NULL,
                    text        NVARCHAR(MAX) NOT NULL DEFAULT '',
                    link_text   NVARCHAR(255) NOT NULL DEFAULT '',
                    link_url    NVARCHAR(500) NOT NULL DEFAULT '',
                    style       NVARCHAR(20)  NOT NULL DEFAULT 'info',
                    pages       NVARCHAR(500) NOT NULL DEFAULT '*',
                    is_active   BIT           NOT NULL DEFAULT 1,
                    starts_at   DATETIME2     NULL,
                    ends_at     DATETIME2     NULL,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_banners PRIMARY KEY (id)
                )
            """)

        # ── CMS: redirects ─────────────────────────────────────────────────────
        if not _tbl("redirects"):
            conn.execute("""
                CREATE TABLE redirects (
                    id          INT IDENTITY(1,1) NOT NULL,
                    from_path   NVARCHAR(500) NOT NULL,
                    to_url      NVARCHAR(500) NOT NULL,
                    status_code INT           NOT NULL DEFAULT 301,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_redirects     PRIMARY KEY (id),
                    CONSTRAINT UQ_redirects_from UNIQUE (from_path)
                )
            """)

        # ── v11: customers.phone ───────────────────────────────────────────────
        if not _col_exists("customers", "phone"):
            conn.execute(
                "ALTER TABLE customers ADD phone NVARCHAR(50) NOT NULL DEFAULT ''"
            )

        # ── v12: customers.last_login_at ───────────────────────────────────────
        if not _col_exists("customers", "last_login_at"):
            conn.execute(
                "ALTER TABLE customers ADD last_login_at DATETIME2 NULL"
            )

        # ── v13: contact_requests.customer_id → customers ─────────────────────
        if not _col_exists("contact_requests", "customer_id"):
            conn.execute(
                "ALTER TABLE contact_requests ADD customer_id INT NULL"
            )
            if not conn.execute(
                "SELECT 1 FROM sys.foreign_keys WHERE name='FK_cr_customer'"
            ).fetchone():
                conn.execute(
                    "ALTER TABLE contact_requests ADD CONSTRAINT FK_cr_customer "
                    "FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL"
                )

        # ── v14: CHECK constraints on status columns ───────────────────────────
        # WITH NOCHECK so existing data is not re-validated.
        if not conn.execute(
            "SELECT 1 FROM sys.check_constraints WHERE name='CK_ca_client_status'"
        ).fetchone():
            conn.execute(
                "ALTER TABLE customer_accounts WITH NOCHECK ADD CONSTRAINT CK_ca_client_status "
                "CHECK (client_status IN ('lead','pending_data','pending_transfer','active','suspended'))"
            )
        if not conn.execute(
            "SELECT 1 FROM sys.check_constraints WHERE name='CK_ca_program_status'"
        ).fetchone():
            conn.execute(
                "ALTER TABLE customer_accounts WITH NOCHECK ADD CONSTRAINT CK_ca_program_status "
                "CHECK (program_status IN ('unconfirmed','confirmed') OR program_status IS NULL)"
            )

        # ── v15: FLOAT → DECIMAL(18,6) for all financial columns ──────────────
        # FLOAT (system_type_id=62) has precision errors; DECIMAL is exact.
        # SQL Server allows in-place type change when the column is not part of
        # a computed column expression or a filtered unique index over that column.
        def _is_float(table: str, col: str) -> bool:
            row = conn.execute(
                "SELECT system_type_id FROM sys.columns "
                "WHERE object_id=OBJECT_ID(?) AND name=?",
                (f"dbo.{table}", col),
            ).fetchone()
            return row is not None and row["system_type_id"] == 62  # 62 = float

        def _drop_default_constraints(table: str, col: str) -> None:
            """Drop all default constraints on a column before ALTER COLUMN."""
            rows = conn.execute(
                "SELECT d.name "
                "FROM sys.default_constraints d "
                "JOIN sys.columns c ON d.parent_object_id=c.object_id AND d.parent_column_id=c.column_id "
                "WHERE d.parent_object_id=OBJECT_ID(?) AND c.name=?",
                (f"dbo.{table}", col),
            ).fetchall()
            for r in rows:
                conn.execute(f"ALTER TABLE {table} DROP CONSTRAINT [{r['name']}]")

        def _alter_to_decimal(table: str, col: str, nullable: bool = False) -> None:
            if _is_float(table, col):
                _drop_default_constraints(table, col)
                null_str = "NULL" if nullable else "NOT NULL"
                conn.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {col} DECIMAL(18,6) {null_str}"
                )

        _financial_cols = [
            "total_volume", "total_commission",
            "fx_lot", "fx_commission",
            "hang_hoa_lot", "hang_hoa_commission",
            "index_lot", "index_commission",
            "crypto_lot", "crypto_commission",
            "sharecfd_lot", "sharecfd_commission",
            "bond_lot", "bond_commission",
            "synthetic_lot", "synthetic_commission",
        ]
        for col in _financial_cols:
            for tbl in ("commission_records", "rebate_records"):
                _alter_to_decimal(tbl, col)
        _alter_to_decimal("rebate_records", "rebate_amount")
        for col in ("lots_at_event", "amount_usd"):
            _alter_to_decimal("program_events", col)
        for col in ("target_lot", "reward_value"):
            _alter_to_decimal("program_tiers", col)
        _alter_to_decimal("ibs", "link_spread", nullable=True)

        # ── v16: Wallet system ────────────────────────────────────────────────
        if not _tbl("customer_wallets"):
            conn.execute("""
                CREATE TABLE customer_wallets (
                    id              INT IDENTITY(1,1) NOT NULL,
                    customer_id     INT           NOT NULL,
                    balance         DECIMAL(18,6) NOT NULL DEFAULT 0,
                    pending_balance DECIMAL(18,6) NOT NULL DEFAULT 0,
                    currency        NVARCHAR(10)  NOT NULL DEFAULT 'USD',
                    is_active       BIT           NOT NULL DEFAULT 1,
                    created_at      DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at      DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_customer_wallets PRIMARY KEY (id),
                    CONSTRAINT FK_cw_customer FOREIGN KEY (customer_id)
                        REFERENCES customers(id) ON DELETE CASCADE,
                    CONSTRAINT UQ_cw_customer UNIQUE (customer_id)
                )
            """)
            conn.execute("CREATE INDEX IX_cw_customer ON customer_wallets (customer_id)")

        if not _tbl("wallet_transactions"):
            conn.execute("""
                CREATE TABLE wallet_transactions (
                    id              INT IDENTITY(1,1) NOT NULL,
                    wallet_id       INT            NOT NULL,
                    tx_type         NVARCHAR(30)   NOT NULL,
                    amount          DECIMAL(18,6)  NOT NULL,
                    balance_after   DECIMAL(18,6)  NOT NULL DEFAULT 0,
                    reference_type  NVARCHAR(30)   NULL,
                    reference_id    INT            NULL,
                    description     NVARCHAR(500)  NOT NULL DEFAULT '',
                    status          NVARCHAR(20)   NOT NULL DEFAULT 'completed',
                    created_by      NVARCHAR(100)  NOT NULL DEFAULT '',
                    created_at      DATETIME2      NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_wallet_transactions PRIMARY KEY (id),
                    CONSTRAINT FK_wt_wallet FOREIGN KEY (wallet_id)
                        REFERENCES customer_wallets(id),
                    CONSTRAINT CK_wt_tx_type CHECK (tx_type IN (
                        'rebate_credit','bonus_credit','manual_credit',
                        'withdrawal','manual_debit','adjustment'
                    )),
                    CONSTRAINT CK_wt_status CHECK (status IN (
                        'pending','completed','rejected','cancelled'
                    ))
                )
            """)
            conn.execute("CREATE INDEX IX_wt_wallet ON wallet_transactions (wallet_id, created_at DESC)")
            conn.execute("CREATE INDEX IX_wt_status ON wallet_transactions (status)")
            conn.execute("CREATE INDEX IX_wt_ref    ON wallet_transactions (reference_type, reference_id)")

        if not _tbl("withdrawal_requests"):
            conn.execute("""
                CREATE TABLE withdrawal_requests (
                    id              INT IDENTITY(1,1) NOT NULL,
                    wallet_id       INT            NOT NULL,
                    amount          DECIMAL(18,6)  NOT NULL,
                    method          NVARCHAR(30)   NOT NULL DEFAULT 'bank_transfer',
                    wallet_address  NVARCHAR(255)  NULL,
                    wallet_network  NVARCHAR(50)   NULL,
                    bank_info       NVARCHAR(500)  NULL,
                    status          NVARCHAR(20)   NOT NULL DEFAULT 'pending',
                    admin_note      NVARCHAR(500)  NOT NULL DEFAULT '',
                    reviewed_by     NVARCHAR(100)  NULL,
                    reviewed_at     DATETIME2      NULL,
                    tx_hash         NVARCHAR(255)  NULL,
                    created_at      DATETIME2      NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_withdrawal_requests PRIMARY KEY (id),
                    CONSTRAINT FK_wr_wallet FOREIGN KEY (wallet_id)
                        REFERENCES customer_wallets(id),
                    CONSTRAINT CK_wr_method CHECK (method IN (
                        'bank_transfer','usdt_trc20','usdt_erc20','usdt_bep20',
                        'btc','eth','other_crypto'
                    )),
                    CONSTRAINT CK_wr_status CHECK (status IN (
                        'pending','approved','processing','completed','rejected','cancelled'
                    ))
                )
            """)
            conn.execute("CREATE INDEX IX_wr_wallet ON withdrawal_requests (wallet_id)")
            conn.execute("CREATE INDEX IX_wr_status ON withdrawal_requests (status, created_at DESC)")

        # ── v17: Withdrawal OTP verification ──────────────────────────────────
        if not _tbl("withdrawal_otps"):
            conn.execute("""
                CREATE TABLE withdrawal_otps (
                    id           INT IDENTITY(1,1) NOT NULL,
                    customer_id  INT           NOT NULL,
                    code         NVARCHAR(6)   NOT NULL,
                    expires_at   DATETIME2     NOT NULL,
                    attempts     INT           NOT NULL DEFAULT 0,
                    used         BIT           NOT NULL DEFAULT 0,
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_withdrawal_otps PRIMARY KEY (id),
                    CONSTRAINT FK_wotp_customer FOREIGN KEY (customer_id)
                        REFERENCES customers(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IX_wotp_customer ON withdrawal_otps (customer_id, used, expires_at)")

        # ── v18: brokers.learn_more_url ────────────────────────────────────────
        if not _col_exists("brokers", "learn_more_url"):
            conn.execute(
                "ALTER TABLE brokers ADD learn_more_url NVARCHAR(500) NULL"
            )

        # ── v20: brokers.transfer_guide_url ────────────────────────────────────
        if not _col_exists("brokers", "transfer_guide_url"):
            conn.execute(
                "ALTER TABLE brokers ADD transfer_guide_url NVARCHAR(500) NULL"
            )

        # ── v19: brokers.rebate_sequence ──────────────────────────────────────
        if not _col_exists("brokers", "rebate_sequence"):
            conn.execute(
                "ALTER TABLE brokers ADD rebate_sequence NVARCHAR(20) NOT NULL DEFAULT 'monthly'"
            )

        # ── v20: faq_items bilingual columns ──────────────────────────────────
        if not _col_exists("faq_items", "question_en"):
            conn.execute(
                "ALTER TABLE faq_items ADD question_en NVARCHAR(500) NULL"
            )
        if not _col_exists("faq_items", "answer_en"):
            conn.execute(
                "ALTER TABLE faq_items ADD answer_en NVARCHAR(MAX) NULL"
            )

        # ── v21: cms_articles bilingual columns (English) ─────────────────────
        if not _col_exists("cms_articles", "title_en"):
            conn.execute("ALTER TABLE cms_articles ADD title_en NVARCHAR(500) NULL")
        if not _col_exists("cms_articles", "excerpt_en"):
            conn.execute("ALTER TABLE cms_articles ADD excerpt_en NVARCHAR(MAX) NULL")
        if not _col_exists("cms_articles", "content_en"):
            conn.execute("ALTER TABLE cms_articles ADD content_en NVARCHAR(MAX) NULL")
        if not _col_exists("cms_articles", "seo_title_en"):
            conn.execute("ALTER TABLE cms_articles ADD seo_title_en NVARCHAR(255) NULL")
        if not _col_exists("cms_articles", "seo_desc_en"):
            conn.execute("ALTER TABLE cms_articles ADD seo_desc_en NVARCHAR(500) NULL")
        if not _col_exists("cms_articles", "cover_image_id_en"):
            conn.execute("ALTER TABLE cms_articles ADD cover_image_id_en INT NULL")

        # ── v22: brokers — full profile columns for public /brokers page ─────
        _broker_cols = {
            "logo_url":         "NVARCHAR(500) NULL",
            "logo_color":       "NVARCHAR(20) NULL",
            "rating":           "DECIMAL(2,1) NULL",
            "licenses":         "NVARCHAR(500) NULL",
            "leverage":         "NVARCHAR(100) NULL",
            "features":         "NVARCHAR(MAX) NULL",
            "features_en":      "NVARCHAR(MAX) NULL",
            "assets_count":     "NVARCHAR(50) NULL",
            "min_deposit":      "NVARCHAR(50) NULL",
            "visit_url":        "NVARCHAR(500) NULL",
            "review_url":       "NVARCHAR(500) NULL",
            "review_article_slug": "NVARCHAR(200) NULL",
            "status":           "NVARCHAR(20) NOT NULL DEFAULT 'active'",
            "badge_text":       "NVARCHAR(50) NULL",
            "extra_stat_label": "NVARCHAR(50) NULL",
            "extra_stat_value": "NVARCHAR(50) NULL",
            "show_on_brokers_page": "BIT NOT NULL DEFAULT 0",
            "logo_font_size":   "INT NULL",
        }
        for col, typedef in _broker_cols.items():
            if not _col_exists("brokers", col):
                conn.execute(f"ALTER TABLE brokers ADD {col} {typedef}")

        # One-time backfill: copy the most common non-empty program leverage
        # into brokers.leverage so legacy data benefits from the card fallback
        # without manual re-entry per broker.
        conn.execute(
            """UPDATE b
               SET b.leverage = src.leverage
               FROM brokers b
               CROSS APPLY (
                   SELECT TOP 1 p.leverage
                   FROM programs p
                   JOIN program_brokers pb ON pb.program_id = p.id
                   WHERE pb.broker_id = b.id
                     AND p.leverage IS NOT NULL
                     AND LTRIM(RTRIM(p.leverage)) <> ''
                   GROUP BY p.leverage
                   ORDER BY COUNT(*) DESC
               ) src
               WHERE b.leverage IS NULL OR LTRIM(RTRIM(b.leverage)) = ''"""
        )

        # Hide brokers without a profile from the public /brokers page.
        # Only the 12 profiled brokers should be visible; rest default to hidden.
        _profiled = (
            'vantage','exness','fxpro','pepperstone','multibank','fpmarkets',
            'icmarkets','titanfx','iux','mitrade','ec','vtmarket',
        )
        ph = ",".join("?" * len(_profiled))
        conn.execute(
            f"UPDATE brokers SET show_on_brokers_page=0 WHERE slug NOT IN ({ph})",
            _profiled,
        )

        # ── v23: FK_rr_tier → SET NULL (allow tier replacement) ──────────
        fk = conn.execute(
            "SELECT delete_referential_action_desc FROM sys.foreign_keys WHERE name='FK_rr_tier'"
        ).fetchone()
        if fk and fk['delete_referential_action_desc'] == 'NO_ACTION':
            conn.execute("ALTER TABLE rebate_records DROP CONSTRAINT FK_rr_tier")
            conn.execute(
                "ALTER TABLE rebate_records ADD CONSTRAINT FK_rr_tier "
                "FOREIGN KEY (program_tier_id) REFERENCES program_tiers(id) ON DELETE SET NULL"
            )

        # ── v24: UNIQUE broker_email per broker + FK program_id ────────
        # One email per broker — prevents duplicate accounts
        if not conn.execute(
            "SELECT 1 FROM sys.indexes WHERE name='UQ_ca_broker_email'"
        ).fetchone():
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX UQ_ca_broker_email "
                    "ON customer_accounts (broker_id, broker_email) "
                    "WHERE broker_email <> ''"
                )
            except Exception:
                pass  # may fail if duplicates already exist

        # FK: program_id → programs(id)
        if not conn.execute(
            "SELECT 1 FROM sys.foreign_keys WHERE name='FK_ca_program'"
        ).fetchone():
            try:
                conn.execute(
                    "ALTER TABLE customer_accounts ADD CONSTRAINT FK_ca_program "
                    "FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE SET NULL"
                )
            except Exception:
                pass

        # ── v25a: TOTP secret for admin MFA ──────────────────────────────
        if not _col_exists("users", "totp_secret"):
            conn.execute(
                "ALTER TABLE users ADD totp_secret NVARCHAR(100) NULL"
            )

        # ── v25b: Customer account locking ────────────────────────────────
        if not _col_exists("customers", "is_locked"):
            conn.execute(
                "ALTER TABLE customers ADD is_locked BIT NOT NULL DEFAULT 0"
            )

        # ── v25: Leads system — import, store, and track campaign sends ──
        if not _tbl("lead_imports"):
            conn.execute("""
                CREATE TABLE lead_imports (
                    id          INT IDENTITY(1,1) NOT NULL,
                    file_name   NVARCHAR(255) NOT NULL DEFAULT '',
                    total_rows  INT           NOT NULL DEFAULT 0,
                    new_rows    INT           NOT NULL DEFAULT 0,
                    updated_rows INT          NOT NULL DEFAULT 0,
                    skipped_rows INT          NOT NULL DEFAULT 0,
                    imported_by NVARCHAR(100) NOT NULL DEFAULT '',
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_lead_imports PRIMARY KEY (id)
                )
            """)

        if not _tbl("leads"):
            conn.execute("""
                CREATE TABLE leads (
                    id          INT IDENTITY(1,1) NOT NULL,
                    email       NVARCHAR(255) NOT NULL,
                    name        NVARCHAR(255) NOT NULL DEFAULT '',
                    country     NVARCHAR(100) NOT NULL DEFAULT '',
                    mobile      NVARCHAR(100) NOT NULL DEFAULT '',
                    user_id     NVARCHAR(100) NOT NULL DEFAULT '',
                    sales       NVARCHAR(100) NOT NULL DEFAULT '',
                    affid       NVARCHAR(100) NOT NULL DEFAULT '',
                    leads_type  NVARCHAR(100) NOT NULL DEFAULT '',
                    source      NVARCHAR(255) NOT NULL DEFAULT '',
                    extra_data  NVARCHAR(MAX) NOT NULL DEFAULT '{}',
                    import_id   INT           NULL,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_leads PRIMARY KEY (id),
                    CONSTRAINT UQ_leads_email UNIQUE (email),
                    CONSTRAINT FK_leads_import FOREIGN KEY (import_id)
                        REFERENCES lead_imports(id) ON DELETE SET NULL
                )
            """)
            conn.execute("CREATE INDEX IX_leads_country ON leads (country)")
            conn.execute("CREATE INDEX IX_leads_source  ON leads (source)")
            conn.execute("CREATE INDEX IX_leads_created ON leads (created_at DESC)")

        if not _tbl("lead_campaign_status"):
            conn.execute("""
                CREATE TABLE lead_campaign_status (
                    id          INT IDENTITY(1,1) NOT NULL,
                    lead_id     INT           NOT NULL,
                    campaign_id INT           NOT NULL,
                    status      NVARCHAR(20)  NOT NULL DEFAULT 'pending',
                    error_msg   NVARCHAR(500) NULL,
                    sent_at     DATETIME2     NULL,
                    CONSTRAINT PK_lcs PRIMARY KEY (id),
                    CONSTRAINT FK_lcs_lead FOREIGN KEY (lead_id)
                        REFERENCES leads(id) ON DELETE CASCADE,
                    CONSTRAINT FK_lcs_campaign FOREIGN KEY (campaign_id)
                        REFERENCES campaigns(id) ON DELETE CASCADE,
                    CONSTRAINT UQ_lcs_lead_campaign UNIQUE (lead_id, campaign_id)
                )
            """)
            conn.execute("CREATE INDEX IX_lcs_campaign ON lead_campaign_status (campaign_id, status)")

        # ══════════════════════════════════════════════════════════════════════
        # v30: ADMIN 100% CONTROL — scheduling, permissions, analytics, segmentation
        # ══════════════════════════════════════════════════════════════════════

        # ── v30a: Program scheduling (start/end dates) ────────────────────────
        if not _col_exists("programs", "starts_at"):
            conn.execute("ALTER TABLE programs ADD starts_at DATETIME2 NULL")
        if not _col_exists("programs", "ends_at"):
            conn.execute("ALTER TABLE programs ADD ends_at DATETIME2 NULL")
        if not _col_exists("programs", "description"):
            conn.execute("ALTER TABLE programs ADD description NVARCHAR(MAX) NULL")
        if not _col_exists("programs", "description_en"):
            conn.execute("ALTER TABLE programs ADD description_en NVARCHAR(MAX) NULL")
        if not _col_exists("programs", "name_en"):
            conn.execute("ALTER TABLE programs ADD name_en NVARCHAR(255) NULL")
        if not _col_exists("programs", "geo_targets"):
            conn.execute(
                "ALTER TABLE programs ADD geo_targets NVARCHAR(500) NULL"
            )  # comma-separated country codes, NULL = all

        # ── v30b: Campaign scheduling ─────────────────────────────────────────
        if not _col_exists("campaigns", "scheduled_at"):
            conn.execute("ALTER TABLE campaigns ADD scheduled_at DATETIME2 NULL")

        # ── v30c: CMS article scheduled publish ──────────────────────────────
        if not _col_exists("cms_articles", "scheduled_at"):
            conn.execute("ALTER TABLE cms_articles ADD scheduled_at DATETIME2 NULL")

        # ── v30d: Granular role-based permissions ─────────────────────────────
        if not _tbl("admin_roles"):
            conn.execute("""
                CREATE TABLE admin_roles (
                    id          INT IDENTITY(1,1) NOT NULL,
                    name        NVARCHAR(50)  NOT NULL,
                    permissions NVARCHAR(MAX) NOT NULL DEFAULT '[]',
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_admin_roles PRIMARY KEY (id),
                    CONSTRAINT UQ_admin_roles_name UNIQUE (name)
                )
            """)
            # Seed default roles
            conn.execute(
                "INSERT INTO admin_roles (name, permissions) VALUES "
                "('admin', '[\"*\"]'), "
                "('editor', '[\"cms.*\",\"media.*\"]'), "
                "('marketing', '[\"campaigns.*\",\"leads.*\",\"templates.*\",\"emails.*\"]'), "
                "('finance', '[\"rebate.*\",\"wallet.*\",\"payment.*\"]'), "
                "('support', '[\"customers.*\",\"enrollments.*\",\"faq.*\"]')"
            )
        # Link users to roles
        if not _col_exists("users", "role_id"):
            conn.execute("ALTER TABLE users ADD role_id INT NULL")
            # FK won't work if admin_roles is empty, but we seeded above
            if not conn.execute(
                "SELECT 1 FROM sys.foreign_keys WHERE name='FK_users_role'"
            ).fetchone():
                try:
                    conn.execute(
                        "ALTER TABLE users ADD CONSTRAINT FK_users_role "
                        "FOREIGN KEY (role_id) REFERENCES admin_roles(id) ON DELETE SET NULL"
                    )
                except Exception:
                    pass

        # ── v30e: Customer segments ───────────────────────────────────────────
        if not _tbl("customer_segments"):
            conn.execute("""
                CREATE TABLE customer_segments (
                    id          INT IDENTITY(1,1) NOT NULL,
                    name        NVARCHAR(100) NOT NULL,
                    description NVARCHAR(500) NOT NULL DEFAULT '',
                    rules_json  NVARCHAR(MAX) NOT NULL DEFAULT '{}',
                    is_dynamic  BIT           NOT NULL DEFAULT 1,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_customer_segments PRIMARY KEY (id),
                    CONSTRAINT UQ_customer_segments_name UNIQUE (name)
                )
            """)

        if not _tbl("customer_segment_members"):
            conn.execute("""
                CREATE TABLE customer_segment_members (
                    segment_id  INT NOT NULL,
                    customer_id INT NOT NULL,
                    added_at    DATETIME2 NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_csm PRIMARY KEY (segment_id, customer_id),
                    CONSTRAINT FK_csm_segment FOREIGN KEY (segment_id)
                        REFERENCES customer_segments(id) ON DELETE CASCADE,
                    CONSTRAINT FK_csm_customer FOREIGN KEY (customer_id)
                        REFERENCES customers(id) ON DELETE CASCADE
                )
            """)

        # ── v30f: Content versioning ──────────────────────────────────────────
        if not _tbl("content_versions"):
            conn.execute("""
                CREATE TABLE content_versions (
                    id          INT IDENTITY(1,1) NOT NULL,
                    entity_type NVARCHAR(50)  NOT NULL,
                    entity_id   INT           NOT NULL,
                    version_num INT           NOT NULL DEFAULT 1,
                    data_json   NVARCHAR(MAX) NOT NULL,
                    created_by  NVARCHAR(100) NOT NULL DEFAULT '',
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_content_versions PRIMARY KEY (id)
                )
            """)
            conn.execute(
                "CREATE INDEX IX_cv_entity ON content_versions (entity_type, entity_id, version_num DESC)"
            )

        # ── v30g: Auto-credit tracking ────────────────────────────────────────
        if not _col_exists("rebate_batches", "auto_credited"):
            conn.execute(
                "ALTER TABLE rebate_batches ADD auto_credited BIT NOT NULL DEFAULT 0"
            )
        if not _col_exists("rebate_batches", "broker"):
            conn.execute(
                "ALTER TABLE rebate_batches ADD broker NVARCHAR(50) NOT NULL DEFAULT 'vantage'"
            )

        # ── v30h: Notification preferences ────────────────────────────────────
        if not _tbl("notification_rules"):
            conn.execute("""
                CREATE TABLE notification_rules (
                    id           INT IDENTITY(1,1) NOT NULL,
                    event_type   NVARCHAR(50)  NOT NULL,
                    channel      NVARCHAR(20)  NOT NULL DEFAULT 'email',
                    is_enabled   BIT           NOT NULL DEFAULT 1,
                    config_json  NVARCHAR(MAX) NOT NULL DEFAULT '{}',
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_notification_rules PRIMARY KEY (id),
                    CONSTRAINT UQ_nr_event_channel UNIQUE (event_type, channel)
                )
            """)
            # Seed default notification rules
            conn.execute("""
                INSERT INTO notification_rules (event_type, channel, is_enabled) VALUES
                ('enrollment.new', 'email', 1),
                ('enrollment.new', 'telegram', 1),
                ('withdrawal.new', 'email', 1),
                ('withdrawal.new', 'telegram', 1),
                ('customer.registered', 'email', 1),
                ('rebate.imported', 'telegram', 1)
            """)

# ── Step 1: Ensure database ────────────────────────────────────────────────────

def _ensure_database() -> None:
    if not re.match(r'^[A-Za-z0-9_]+$', DATABASE):
        raise ValueError(f"Invalid DATABASE name: {DATABASE!r}")
    # Retry connection to SQL Server — it may not be ready yet at container start
    import time
    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            conn = pyodbc.connect(MASTER_CONN_STR, autocommit=True, timeout=15)
            break
        except pyodbc.Error as e:
            if attempt == max_retries:
                raise RuntimeError(
                    f"Cannot connect to SQL Server after {max_retries} attempts: {e}"
                ) from e
            print(f"[DB] Waiting for SQL Server... attempt {attempt}/{max_retries}")
            time.sleep(2)
    try:
        conn.execute(
            f"IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name='{DATABASE}') "
            f"CREATE DATABASE [{DATABASE}]"
        )
    finally:
        conn.close()


# ── Step 2: Drop legacy tables ─────────────────────────────────────────────────

_LEGACY_TABLES = [
    # ── Old architecture ───────────────────────────────────────────────────────
    "enrollment_voucher_events",
    "enrollments",
    "rebate_daily",
    "rebate_summary",
    "rebate_history",
    "customer_broker_accounts",
    "customer_broker_emails",
    "bonus_progress",
    "promotion_commission_rates",
    "promotion_tiers",
    "broker_ib_configs",
    "bonus_tiers",
    "promotions",
    "mt5_accounts",
    "trading_data",
    "account_owners",
    "account_type_map",
    # ── clients removed — data now lives in customer_accounts ──────────────────
    "clients",
]


def _drop_legacy_tables() -> None:
    """Remove old-architecture tables.

    Two-pass strategy:
      Pass 1 — drop every FK constraint that touches a legacy table (either as
               parent or child) so we never hit a referential-integrity error.
      Pass 2 — drop the tables themselves.
    """
    conn = pyodbc.connect(_CONN_STR, autocommit=True, timeout=15)
    try:
        cur = conn.cursor()
        ph = ",".join("?" * len(_LEGACY_TABLES))

        # Pass 1: collect and drop FK constraints
        cur.execute(
            f"""
            SELECT fk.name, OBJECT_NAME(fk.parent_object_id)
            FROM   sys.foreign_keys fk
            WHERE  OBJECT_NAME(fk.parent_object_id)    IN ({ph})
               OR  OBJECT_NAME(fk.referenced_object_id) IN ({ph})
            """,
            list(_LEGACY_TABLES) + list(_LEGACY_TABLES),
        )
        for fk_name, tbl in cur.fetchall():
            try:
                cur.execute(f"ALTER TABLE [{tbl}] DROP CONSTRAINT [{fk_name}]")
            except Exception:
                pass  # already gone

        # Pass 2: drop tables
        for table in _LEGACY_TABLES:
            if _table_exists(cur, table):
                cur.execute(f"DROP TABLE [{table}]")

    finally:
        conn.close()


# ── Step 3: Create schema ──────────────────────────────────────────────────────

def _create_schema() -> None:
    conn = pyodbc.connect(_CONN_STR, autocommit=True, timeout=15)
    try:
        cur = conn.cursor()

        # ── 1. brokers ─────────────────────────────────────────────────────────
        if not _table_exists(cur, "brokers"):
            cur.execute("""
                CREATE TABLE brokers (
                    id            INT IDENTITY(1,1) NOT NULL,
                    name          NVARCHAR(255) NOT NULL,
                    slug          NVARCHAR(100) NOT NULL,
                    is_active     BIT           NOT NULL DEFAULT 1,
                    display_order INT           NOT NULL DEFAULT 0,
                    CONSTRAINT PK_brokers      PRIMARY KEY (id),
                    CONSTRAINT UQ_brokers_slug UNIQUE (slug)
                )
            """)

        # ── 2. ibs ─────────────────────────────────────────────────────────────
        #
        # One row per (IB, broker) pair.
        # use_id       — broker-assigned User ID for this IB account
        # ib_number    — the IB's own trading account number (link key in
        #                client / trading_account exports)
        if not _table_exists(cur, "ibs"):
            cur.execute("""
                CREATE TABLE ibs (
                    id           INT IDENTITY(1,1) NOT NULL,
                    broker_id    INT           NOT NULL,
                    use_id       NVARCHAR(50)  NOT NULL DEFAULT '',
                    ib_name      NVARCHAR(255) NOT NULL DEFAULT '',
                    ib_number    NVARCHAR(50)  NOT NULL DEFAULT '',
                    email        NVARCHAR(255) NOT NULL DEFAULT '',
                    country      NVARCHAR(100) NOT NULL DEFAULT '',
                    reff_link    NVARCHAR(MAX) NOT NULL DEFAULT '',
                    link_spread  FLOAT         NULL,
                    ib_type      NVARCHAR(20)  NOT NULL DEFAULT 'IB',
                    is_active    BIT           NOT NULL DEFAULT 1,
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_ibs        PRIMARY KEY (id),
                    CONSTRAINT FK_ibs_broker FOREIGN KEY (broker_id) REFERENCES brokers(id)
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX UQ_ibs_use_id
                ON ibs (broker_id, use_id)
                WHERE use_id <> ''
            """)
            cur.execute("CREATE INDEX IX_ibs_broker   ON ibs (broker_id)")
            cur.execute("CREATE INDEX IX_ibs_number   ON ibs (ib_number)")
        else:
            # Migration: rename platform_uid → use_id if old schema
            if _col_exists(cur, "ibs", "platform_uid") and not _col_exists(cur, "ibs", "use_id"):
                # Drop any indexes referencing platform_uid first
                cur.execute("""
                    DECLARE @idx NVARCHAR(255)
                    SELECT @idx = i.name
                    FROM sys.indexes i
                    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                    WHERE OBJECT_NAME(i.object_id) = 'ibs' AND c.name = 'platform_uid' AND i.is_primary_key = 0
                    IF @idx IS NOT NULL EXEC('DROP INDEX [' + @idx + '] ON ibs')
                """)
                cur.execute("EXEC sp_rename 'ibs.platform_uid', 'use_id', 'COLUMN'")
                # Recreate the unique index
                try:
                    cur.execute("""
                        CREATE UNIQUE INDEX UQ_ibs_use_id ON ibs (broker_id, use_id)
                        WHERE use_id <> ''
                    """)
                except Exception:
                    pass

        # ── 3. programs ────────────────────────────────────────────────────────
        #
        # type = 'backcom'          monthly % of commission returned
        #        'bonus_milestone'  one-time USD cash bonus at cumulative lot target
        if not _table_exists(cur, "programs"):
            cur.execute("""
                CREATE TABLE programs (
                    id            INT IDENTITY(1,1) NOT NULL,
                    name          NVARCHAR(255) NOT NULL,
                    type          NVARCHAR(20)  NOT NULL DEFAULT 'backcom',
                    is_active     BIT           NOT NULL DEFAULT 1,
                    display_order INT           NOT NULL DEFAULT 0,
                    rebate_pct    DECIMAL(5,2)  NOT NULL DEFAULT 80,
                    CONSTRAINT PK_programs PRIMARY KEY (id)
                )
            """)

        # Migration: add rebate_usd_per_lot to programs if not present
        if not _col_exists(cur, "programs", "rebate_usd_per_lot"):
            cur.execute("ALTER TABLE programs ADD rebate_usd_per_lot FLOAT NULL")
        # Migration: card template + broker info fields
        if not _col_exists(cur, "programs", "card_template"):
            cur.execute("ALTER TABLE programs ADD card_template NVARCHAR(30) NOT NULL DEFAULT 'default'")
        if not _col_exists(cur, "programs", "is_recommended"):
            cur.execute("ALTER TABLE programs ADD is_recommended BIT NOT NULL DEFAULT 0")
        if not _col_exists(cur, "programs", "licenses"):
            cur.execute("ALTER TABLE programs ADD licenses NVARCHAR(200) NULL")
        if not _col_exists(cur, "programs", "leverage"):
            cur.execute("ALTER TABLE programs ADD leverage NVARCHAR(100) NULL")
        if not _col_exists(cur, "programs", "features"):
            cur.execute("ALTER TABLE programs ADD features NVARCHAR(500) NULL")
        if not _col_exists(cur, "programs", "rebate_xau_label"):
            cur.execute("ALTER TABLE programs ADD rebate_xau_label NVARCHAR(100) NULL")
        # Migration: rebate frequency (daily / weekly / monthly)
        if not _col_exists(cur, "programs", "rebate_frequency"):
            cur.execute("ALTER TABLE programs ADD rebate_frequency NVARCHAR(20) NOT NULL DEFAULT 'daily'")

        # ── 4. program_brokers ─────────────────────────────────────────────────
        if not _table_exists(cur, "program_brokers"):
            cur.execute("""
                CREATE TABLE program_brokers (
                    program_id INT NOT NULL,
                    broker_id  INT NOT NULL,
                    CONSTRAINT PK_program_brokers         PRIMARY KEY (program_id, broker_id),
                    CONSTRAINT FK_program_brokers_program FOREIGN KEY (program_id) REFERENCES programs(id),
                    CONSTRAINT FK_program_brokers_broker  FOREIGN KEY (broker_id)  REFERENCES brokers(id)
                )
            """)

        # ── 5. program_tiers ───────────────────────────────────────────────────
        #
        # target_lot   — minimum cumulative lots to reach this tier (from Excel)
        # reward_type = 'backcom_pct'  reward_value is a fraction (0.6 = 60 %)
        #               'bonus_usd'    reward_value is a USD amount (100 = $100)
        if not _table_exists(cur, "program_tiers"):
            cur.execute("""
                CREATE TABLE program_tiers (
                    id           INT IDENTITY(1,1) NOT NULL,
                    program_id   INT           NOT NULL,
                    tier_number  INT           NOT NULL,
                    target_lot   FLOAT         NOT NULL DEFAULT 0,
                    reward_value FLOAT         NOT NULL DEFAULT 0,
                    reward_type  NVARCHAR(20)  NOT NULL DEFAULT 'backcom_pct',
                    label        NVARCHAR(100) NOT NULL DEFAULT '',
                    CONSTRAINT PK_program_tiers      PRIMARY KEY (id),
                    CONSTRAINT FK_program_tiers_prog FOREIGN KEY (program_id) REFERENCES programs(id),
                    CONSTRAINT UQ_program_tier        UNIQUE (program_id, tier_number)
                )
            """)

        # ── 6. customers ───────────────────────────────────────────────────────
        #
        # Pure authentication / identity record.
        # login_email  — web portal login (may differ from broker email).
        # All broker-specific data lives in customer_accounts.
        if not _table_exists(cur, "customers"):
            cur.execute("""
                CREATE TABLE customers (
                    id                   INT IDENTITY(1,1) NOT NULL,
                    login_email          NVARCHAR(255) NOT NULL,
                    name                 NVARCHAR(255) NOT NULL DEFAULT '',
                    password_hash        NVARCHAR(500) NOT NULL,
                    must_change_password BIT           NOT NULL DEFAULT 1,
                    reset_token          NVARCHAR(100) NULL,
                    reset_token_expires  DATETIME2     NULL,
                    is_verified          BIT           NOT NULL DEFAULT 0,
                    verify_token         NVARCHAR(100) NULL,
                    unsubscribed         BIT           NOT NULL DEFAULT 0,
                    customer_type        NVARCHAR(10)  NOT NULL DEFAULT 'client',
                    created_at           DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_customers       PRIMARY KEY (id),
                    CONSTRAINT UQ_customers_email UNIQUE (login_email)
                )
            """)
            cur.execute("CREATE INDEX IX_customers_verify ON customers (verify_token)")
            cur.execute("CREATE INDEX IX_customers_date   ON customers (created_at)")

        # ── 7. customer_accounts ───────────────────────────────────────────────
        #
        # One row per (customer, broker) pair — the customer's account at that broker.
        #
        # customer_id  NULL when the row is a "lead" (data imported from broker
        #              before the person registers on the web portal).
        # use_id       broker-platform User ID (from client.csv "User ID").
        #              Unique within a broker when set.
        # ib_number    IB's trading account number managing this client.
        #              NULL for leads / pending. Required when status = 'active'.
        # broker_email email used at broker — may differ from customers.login_email.
        # client_name  name on broker platform (from client.csv "Client_Name").
        #
        # client_status:
        #   'lead'              data imported, person has not registered on portal
        #   'pending_data'      registered (new_account), waiting for broker registration
        #   'pending_transfer'  existing account, waiting for IB transfer
        #   'active'            fully linked and rebate-eligible (ib_number required)
        #   'suspended'         paused by admin
        if not _table_exists(cur, "customer_accounts"):
            cur.execute("""
                CREATE TABLE customer_accounts (
                    id            INT IDENTITY(1,1) NOT NULL,
                    customer_id   INT           NULL,
                    broker_id     INT           NOT NULL,
                    use_id        NVARCHAR(50)  NULL,
                    ib_number     NVARCHAR(50)  NULL,
                    broker_email  NVARCHAR(255) NOT NULL DEFAULT '',
                    client_name   NVARCHAR(255) NOT NULL DEFAULT '',
                    country       NVARCHAR(100) NOT NULL DEFAULT '',
                    client_status NVARCHAR(20)  NOT NULL DEFAULT 'lead',
                    program_id    INT           NULL,
                    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_customer_accounts  PRIMARY KEY (id),
                    CONSTRAINT FK_ca_customer FOREIGN KEY (customer_id)
                        REFERENCES customers(id) ON DELETE CASCADE,
                    CONSTRAINT FK_ca_broker   FOREIGN KEY (broker_id)  REFERENCES brokers(id),
                    CONSTRAINT FK_ca_program  FOREIGN KEY (program_id) REFERENCES programs(id)
                )
            """)
            # use_id unique per broker when set
            cur.execute("""
                CREATE UNIQUE INDEX UQ_ca_use_id
                ON customer_accounts (broker_id, use_id)
                WHERE use_id IS NOT NULL
            """)
            # one portal account per broker when customer_id is set
            cur.execute("""
                CREATE UNIQUE INDEX UQ_ca_customer_broker
                ON customer_accounts (customer_id, broker_id)
                WHERE customer_id IS NOT NULL
            """)
            cur.execute("CREATE INDEX IX_ca_customer_id ON customer_accounts (customer_id)")
            cur.execute("CREATE INDEX IX_ca_status      ON customer_accounts (client_status)")
            cur.execute("CREATE INDEX IX_ca_ib_number   ON customer_accounts (ib_number)")

        # ── 8. trading_accounts ────────────────────────────────────────────────
        #
        # MT5 / trading accounts. One customer_account can have many.
        # trading_account — the MT5 account number (from Excel "trading_account").
        # account_type    — account type string (from Excel "acount_type").
        if not _table_exists(cur, "trading_accounts"):
            cur.execute("""
                CREATE TABLE trading_accounts (
                    id                  INT IDENTITY(1,1) NOT NULL,
                    customer_account_id INT           NOT NULL,
                    trading_account     NVARCHAR(50)  NOT NULL,
                    account_type        NVARCHAR(100) NOT NULL DEFAULT '',
                    is_active           BIT           NOT NULL DEFAULT 1,
                    created_at          DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_trading_accounts            PRIMARY KEY (id),
                    CONSTRAINT FK_ta_customer_account FOREIGN KEY (customer_account_id)
                        REFERENCES customer_accounts(id),
                    CONSTRAINT UQ_trading_account     UNIQUE (trading_account)
                )
            """)
            cur.execute("CREATE INDEX IX_ta_customer_account ON trading_accounts (customer_account_id)")

        # ── 9. rebate_batches ──────────────────────────────────────────────────
        #
        # One batch per import period (typically monthly).
        # status: 'draft' → 'confirmed' → 'exported'
        if not _table_exists(cur, "rebate_batches"):
            cur.execute("""
                CREATE TABLE rebate_batches (
                    id           INT IDENTITY(1,1) NOT NULL,
                    period_date  DATE          NOT NULL,
                    created_by   NVARCHAR(100) NOT NULL DEFAULT '',
                    status       NVARCHAR(20)  NOT NULL DEFAULT 'draft',
                    total_rows   INT           NOT NULL DEFAULT 0,
                    total_amount FLOAT         NOT NULL DEFAULT 0,
                    notes        NVARCHAR(MAX) NOT NULL DEFAULT '',
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_rebate_batches PRIMARY KEY (id)
                )
            """)
            cur.execute("CREATE INDEX IX_rb_period ON rebate_batches (period_date)")

        # ── 10. commission_records ─────────────────────────────────────────────
        #
        # Raw broker export — one row per trading_account per batch.
        # Column names match the Excel export format (record_commission.xlsx):
        #   use_id          — client User ID (from broker platform)
        #   trading_account — MT5 account number
        #   total_volume    — total lots traded
        #   total_commission— total commission earned
        #   hang_hoa_*      — commodities (gold, oil, silver…)
        if not _table_exists(cur, "commission_records"):
            cur.execute("""
                CREATE TABLE commission_records (
                    id              INT IDENTITY(1,1) NOT NULL,
                    batch_id        INT          NOT NULL,
                    use_id          NVARCHAR(50) NOT NULL DEFAULT '',
                    trading_account NVARCHAR(50) NOT NULL DEFAULT '',
                    lots_type       NVARCHAR(20) NOT NULL DEFAULT 'Standard',
                    -- totals
                    total_volume     FLOAT NOT NULL DEFAULT 0,
                    total_commission FLOAT NOT NULL DEFAULT 0,
                    -- forex
                    fx_lot           FLOAT NOT NULL DEFAULT 0,
                    fx_commission    FLOAT NOT NULL DEFAULT 0,
                    -- commodities (gold, oil, silver…)
                    hang_hoa_lot        FLOAT NOT NULL DEFAULT 0,
                    hang_hoa_commission FLOAT NOT NULL DEFAULT 0,
                    -- indices
                    index_lot        FLOAT NOT NULL DEFAULT 0,
                    index_commission FLOAT NOT NULL DEFAULT 0,
                    -- crypto
                    crypto_lot        FLOAT NOT NULL DEFAULT 0,
                    crypto_commission FLOAT NOT NULL DEFAULT 0,
                    -- share CFDs
                    sharecfd_lot        FLOAT NOT NULL DEFAULT 0,
                    sharecfd_commission FLOAT NOT NULL DEFAULT 0,
                    -- bonds
                    bond_lot        FLOAT NOT NULL DEFAULT 0,
                    bond_commission FLOAT NOT NULL DEFAULT 0,
                    -- synthetic / composite
                    synthetic_lot        FLOAT NOT NULL DEFAULT 0,
                    synthetic_commission FLOAT NOT NULL DEFAULT 0,
                    uploaded_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_commission_records PRIMARY KEY (id),
                    CONSTRAINT FK_cr_batch FOREIGN KEY (batch_id)
                        REFERENCES rebate_batches(id),
                    CONSTRAINT UQ_commission_records UNIQUE (batch_id, trading_account, lots_type)
                )
            """)
            cur.execute("CREATE INDEX IX_cr_batch   ON commission_records (batch_id)")
            cur.execute("CREATE INDEX IX_cr_use_id  ON commission_records (use_id)")
            cur.execute("CREATE INDEX IX_cr_account ON commission_records (trading_account)")
        else:
            # Migration: add lots_type if missing
            if not _col_exists(cur, "commission_records", "lots_type"):
                cur.execute(
                    "ALTER TABLE commission_records ADD lots_type NVARCHAR(20) NOT NULL DEFAULT 'Standard'"
                )
                # Rebuild unique constraint to include lots_type
                try:
                    cur.execute("ALTER TABLE commission_records DROP CONSTRAINT UQ_commission_records")
                except Exception:
                    pass
                cur.execute(
                    "ALTER TABLE commission_records ADD CONSTRAINT UQ_commission_records "
                    "UNIQUE (batch_id, trading_account, lots_type)"
                )
            # Migration: add uploaded_at if missing
            if not _col_exists(cur, "commission_records", "uploaded_at"):
                cur.execute(
                    "ALTER TABLE commission_records ADD uploaded_at DATETIME2 NOT NULL DEFAULT GETDATE()"
                )

        # ── 11. rebate_records ─────────────────────────────────────────────────
        #
        # Aggregated per customer_account per batch — final payout record.
        # Same column names as commission_records (sums of all trading_accounts).
        if not _table_exists(cur, "rebate_records"):
            cur.execute("""
                CREATE TABLE rebate_records (
                    id                  INT IDENTITY(1,1) NOT NULL,
                    batch_id            INT NOT NULL,
                    customer_account_id INT NOT NULL,
                    program_tier_id     INT NOT NULL,
                    -- aggregated totals
                    total_volume         FLOAT NOT NULL DEFAULT 0,
                    total_commission     FLOAT NOT NULL DEFAULT 0,
                    -- per-instrument
                    fx_lot               FLOAT NOT NULL DEFAULT 0,
                    fx_commission        FLOAT NOT NULL DEFAULT 0,
                    hang_hoa_lot         FLOAT NOT NULL DEFAULT 0,
                    hang_hoa_commission  FLOAT NOT NULL DEFAULT 0,
                    index_lot            FLOAT NOT NULL DEFAULT 0,
                    index_commission     FLOAT NOT NULL DEFAULT 0,
                    crypto_lot           FLOAT NOT NULL DEFAULT 0,
                    crypto_commission    FLOAT NOT NULL DEFAULT 0,
                    sharecfd_lot         FLOAT NOT NULL DEFAULT 0,
                    sharecfd_commission  FLOAT NOT NULL DEFAULT 0,
                    bond_lot             FLOAT NOT NULL DEFAULT 0,
                    bond_commission      FLOAT NOT NULL DEFAULT 0,
                    synthetic_lot        FLOAT NOT NULL DEFAULT 0,
                    synthetic_commission FLOAT NOT NULL DEFAULT 0,
                    -- result
                    rebate_amount FLOAT        NOT NULL DEFAULT 0,
                    status        NVARCHAR(20) NOT NULL DEFAULT 'pending',
                    CONSTRAINT PK_rebate_records PRIMARY KEY (id),
                    CONSTRAINT FK_rr_batch   FOREIGN KEY (batch_id)
                        REFERENCES rebate_batches(id),
                    CONSTRAINT FK_rr_ca      FOREIGN KEY (customer_account_id)
                        REFERENCES customer_accounts(id),
                    CONSTRAINT FK_rr_tier    FOREIGN KEY (program_tier_id)
                        REFERENCES program_tiers(id),
                    CONSTRAINT UQ_rebate_records UNIQUE (batch_id, customer_account_id)
                )
            """)
            cur.execute("CREATE INDEX IX_rr_ca     ON rebate_records (customer_account_id)")
            cur.execute("CREATE INDEX IX_rr_status ON rebate_records (status, batch_id)")

        # ── 12. program_events ─────────────────────────────────────────────────
        #
        # Bonus milestone history — prevents double-paying the same tier.
        # event_type: 'bonus_paid' | 'bonus_reset'
        if not _table_exists(cur, "program_events"):
            cur.execute("""
                CREATE TABLE program_events (
                    id                  INT IDENTITY(1,1) NOT NULL,
                    customer_account_id INT           NOT NULL,
                    program_tier_id     INT           NOT NULL,
                    batch_id            INT           NULL,
                    event_type          NVARCHAR(20)  NOT NULL DEFAULT 'bonus_paid',
                    lots_at_event       FLOAT         NOT NULL DEFAULT 0,
                    amount_usd          FLOAT         NOT NULL DEFAULT 0,
                    period_date         DATE          NULL,
                    note                NVARCHAR(500) NOT NULL DEFAULT '',
                    created_at          DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_program_events PRIMARY KEY (id),
                    CONSTRAINT FK_pe_ca    FOREIGN KEY (customer_account_id)
                        REFERENCES customer_accounts(id),
                    CONSTRAINT FK_pe_tier  FOREIGN KEY (program_tier_id)
                        REFERENCES program_tiers(id),
                    CONSTRAINT FK_pe_batch FOREIGN KEY (batch_id)
                        REFERENCES rebate_batches(id)
                )
            """)
            cur.execute("CREATE INDEX IX_pe_ca ON program_events (customer_account_id, program_tier_id)")

        # ── 13. users ──────────────────────────────────────────────────────────
        if not _table_exists(cur, "users"):
            cur.execute("""
                CREATE TABLE users (
                    id            INT IDENTITY(1,1) NOT NULL,
                    username      NVARCHAR(100) NOT NULL,
                    password_hash NVARCHAR(500) NOT NULL,
                    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_users          PRIMARY KEY (id),
                    CONSTRAINT UQ_users_username UNIQUE (username)
                )
            """)

        # ── 14. sessions ───────────────────────────────────────────────────────
        if not _table_exists(cur, "sessions"):
            cur.execute("""
                CREATE TABLE sessions (
                    session_id NVARCHAR(64)  NOT NULL,
                    data_json  NVARCHAR(MAX) NOT NULL DEFAULT '{}',
                    created_at DATETIME2     NOT NULL DEFAULT GETDATE(),
                    expires_at DATETIME2     NOT NULL,
                    CONSTRAINT PK_sessions PRIMARY KEY (session_id)
                )
            """)
            cur.execute("CREATE INDEX IX_sessions_expires ON sessions (expires_at)")

        # ── 15. login_attempts ─────────────────────────────────────────────────
        if not _table_exists(cur, "login_attempts"):
            cur.execute("""
                CREATE TABLE login_attempts (
                    id           INT IDENTITY(1,1) NOT NULL,
                    identifier   NVARCHAR(255) NOT NULL,
                    user_type    NVARCHAR(20)  NOT NULL,
                    attempted_at DATETIME2     NOT NULL DEFAULT GETDATE(),
                    ip_address   NVARCHAR(100) NULL,
                    CONSTRAINT PK_login_attempts PRIMARY KEY (id)
                )
            """)
            cur.execute(
                "CREATE INDEX IX_login_attempts ON login_attempts (identifier, attempted_at)"
            )

        # ── 16. smtp_config (singleton) ────────────────────────────────────────
        if not _table_exists(cur, "smtp_config"):
            cur.execute("""
                CREATE TABLE smtp_config (
                    id         INT           NOT NULL DEFAULT 1,
                    host       NVARCHAR(255) NOT NULL DEFAULT 'localhost',
                    port       INT           NOT NULL DEFAULT 25,
                    username   NVARCHAR(255) NOT NULL DEFAULT '',
                    password   NVARCHAR(MAX) NOT NULL DEFAULT '',
                    from_email NVARCHAR(255) NOT NULL DEFAULT '',
                    from_name  NVARCHAR(255) NOT NULL DEFAULT '',
                    use_tls    BIT           NOT NULL DEFAULT 0,
                    use_ssl    BIT           NOT NULL DEFAULT 0,
                    CONSTRAINT PK_smtp_config           PRIMARY KEY (id),
                    CONSTRAINT CK_smtp_config_singleton CHECK (id = 1)
                )
            """)

        # ── 17. templates ──────────────────────────────────────────────────────
        if not _table_exists(cur, "templates"):
            cur.execute("""
                CREATE TABLE templates (
                    id           INT IDENTITY(1,1) NOT NULL,
                    name         NVARCHAR(255) NOT NULL,
                    html_content NVARCHAR(MAX) NOT NULL,
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_templates PRIMARY KEY (id)
                )
            """)

        # ── 18. campaigns ──────────────────────────────────────────────────────
        if not _table_exists(cur, "campaigns"):
            cur.execute("""
                CREATE TABLE campaigns (
                    id          INT IDENTITY(1,1) NOT NULL,
                    name        NVARCHAR(255) NOT NULL,
                    template_id INT           NULL,
                    subject     NVARCHAR(500) NOT NULL DEFAULT '',
                    status      NVARCHAR(50)  NOT NULL DEFAULT 'draft',
                    total       INT           NOT NULL DEFAULT 0,
                    sent        INT           NOT NULL DEFAULT 0,
                    failed      INT           NOT NULL DEFAULT 0,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_campaigns          PRIMARY KEY (id),
                    CONSTRAINT FK_campaigns_template FOREIGN KEY (template_id) REFERENCES templates(id)
                )
            """)
            cur.execute("CREATE INDEX IX_campaigns_status ON campaigns (status)")

        # ── 19. emails ─────────────────────────────────────────────────────────
        #
        # id = UUID used as tracking pixel ID.
        if not _table_exists(cur, "emails"):
            cur.execute("""
                CREATE TABLE emails (
                    id              NVARCHAR(36)  NOT NULL,
                    recipient_name  NVARCHAR(500) NOT NULL DEFAULT '',
                    recipient_email NVARCHAR(255) NOT NULL DEFAULT '',
                    subject         NVARCHAR(500) NOT NULL DEFAULT '',
                    html_content    NVARCHAR(MAX) NOT NULL DEFAULT '',
                    campaign_id     INT           NULL,
                    created_at      DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_emails          PRIMARY KEY (id),
                    CONSTRAINT FK_emails_campaign FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            """)
            cur.execute("CREATE INDEX IX_emails_campaign   ON emails (campaign_id)")
            cur.execute("CREATE INDEX IX_emails_created_at ON emails (created_at)")
            cur.execute("CREATE INDEX IX_emails_recipient  ON emails (recipient_email)")

        # ── 20. opens ──────────────────────────────────────────────────────────
        if not _table_exists(cur, "opens"):
            cur.execute("""
                CREATE TABLE opens (
                    id           INT IDENTITY(1,1) NOT NULL,
                    tracking_id  NVARCHAR(36)  NOT NULL,
                    opened_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    ip_address   NVARCHAR(100) NULL,
                    user_agent   NVARCHAR(500) NULL,
                    device_type  NVARCHAR(50)  NULL,
                    os           NVARCHAR(100) NULL,
                    email_client NVARCHAR(100) NULL,
                    CONSTRAINT PK_opens        PRIMARY KEY (id),
                    CONSTRAINT FK_opens_emails FOREIGN KEY (tracking_id) REFERENCES emails(id)
                )
            """)
            cur.execute("CREATE INDEX IX_opens_tracking_id ON opens (tracking_id)")
            cur.execute("CREATE INDEX IX_opens_opened_at   ON opens (opened_at)")

        # ── 20b. clicks ────────────────────────────────────────────────────────
        if not _table_exists(cur, "clicks"):
            cur.execute("""
                CREATE TABLE clicks (
                    id              INT IDENTITY(1,1) NOT NULL,
                    tracking_id     NVARCHAR(36)   NOT NULL,
                    clicked_at      DATETIME2      NOT NULL DEFAULT GETDATE(),
                    ip_address      NVARCHAR(100)  NULL,
                    user_agent      NVARCHAR(500)  NULL,
                    device_type     NVARCHAR(50)   NULL,
                    os              NVARCHAR(100)  NULL,
                    destination_url NVARCHAR(2000) NOT NULL DEFAULT '',
                    link_label      NVARCHAR(255)  NULL,
                    CONSTRAINT PK_clicks        PRIMARY KEY (id),
                    CONSTRAINT FK_clicks_emails FOREIGN KEY (tracking_id) REFERENCES emails(id)
                )
            """)
            cur.execute("CREATE INDEX IX_clicks_tracking_id ON clicks (tracking_id)")
            cur.execute("CREATE INDEX IX_clicks_clicked_at  ON clicks (clicked_at)")

        # ── 21. job_queue ──────────────────────────────────────────────────────
        if not _table_exists(cur, "job_queue"):
            cur.execute("""
                CREATE TABLE job_queue (
                    id           INT IDENTITY(1,1) NOT NULL,
                    job_type     NVARCHAR(50)  NOT NULL DEFAULT 'campaign',
                    payload_json NVARCHAR(MAX) NOT NULL DEFAULT '{}',
                    status       NVARCHAR(20)  NOT NULL DEFAULT 'pending',
                    created_at   DATETIME2     NOT NULL DEFAULT GETDATE(),
                    started_at   DATETIME2     NULL,
                    finished_at  DATETIME2     NULL,
                    error_msg    NVARCHAR(MAX) NULL,
                    retry_count  INT           NOT NULL DEFAULT 0,
                    CONSTRAINT PK_job_queue PRIMARY KEY (id)
                )
            """)
            cur.execute("CREATE INDEX IX_job_queue_status ON job_queue (status, created_at)")

        # ── 22. audit_log ──────────────────────────────────────────────────────
        if not _table_exists(cur, "audit_log"):
            cur.execute("""
                CREATE TABLE audit_log (
                    id          INT IDENTITY(1,1) NOT NULL,
                    actor       NVARCHAR(255) NOT NULL,
                    action      NVARCHAR(100) NOT NULL,
                    entity_type NVARCHAR(100) NULL,
                    entity_id   NVARCHAR(100) NULL,
                    detail_json NVARCHAR(MAX) NULL,
                    ip_address  NVARCHAR(100) NULL,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_audit_log PRIMARY KEY (id)
                )
            """)
            cur.execute("CREATE INDEX IX_audit_log_actor  ON audit_log (actor)")
            cur.execute("CREATE INDEX IX_audit_log_action ON audit_log (action, created_at)")

        # ── 23. portal_settings ────────────────────────────────────────────────
        if not _table_exists(cur, "portal_settings"):
            cur.execute("""
                CREATE TABLE portal_settings (
                    [key]  NVARCHAR(100) NOT NULL,
                    value  NVARCHAR(MAX) NOT NULL DEFAULT '',
                    CONSTRAINT PK_portal_settings PRIMARY KEY ([key])
                )
            """)

        # ── 24. google_oauth_config (singleton) ────────────────────────────────
        if not _table_exists(cur, "google_oauth_config"):
            cur.execute("""
                CREATE TABLE google_oauth_config (
                    id            INT           NOT NULL DEFAULT 1,
                    client_id     NVARCHAR(500) NOT NULL DEFAULT '',
                    client_secret NVARCHAR(MAX) NOT NULL DEFAULT '',
                    site_url      NVARCHAR(500) NOT NULL DEFAULT '',
                    CONSTRAINT PK_google_oauth_config   PRIMARY KEY (id),
                    CONSTRAINT CK_google_oauth_singleton CHECK (id = 1)
                )
            """)

        # ── 25. gmail_send_tokens ──────────────────────────────────────────────
        if not _table_exists(cur, "gmail_send_tokens"):
            cur.execute("""
                CREATE TABLE gmail_send_tokens (
                    google_email  NVARCHAR(255) NOT NULL,
                    refresh_token NVARCHAR(MAX) NOT NULL,
                    created_at    DATETIME2     NOT NULL DEFAULT GETDATE(),
                    last_used     DATETIME2     NULL,
                    CONSTRAINT PK_gmail_send_tokens PRIMARY KEY (google_email)
                )
            """)

        # ── 26. faq_items ──────────────────────────────────────────────────────
        if not _table_exists(cur, "faq_items"):
            cur.execute("""
                CREATE TABLE faq_items (
                    id            INT IDENTITY(1,1) NOT NULL,
                    question      NVARCHAR(500) NOT NULL,
                    answer        NVARCHAR(MAX) NOT NULL,
                    broker_id     INT           NULL,
                    display_order INT           NOT NULL DEFAULT 0,
                    is_active     BIT           NOT NULL DEFAULT 1,
                    CONSTRAINT PK_faq_items        PRIMARY KEY (id),
                    CONSTRAINT FK_faq_items_broker FOREIGN KEY (broker_id) REFERENCES brokers(id)
                )
            """)

        # ── 27. contact_requests ───────────────────────────────────────────────
        if not _table_exists(cur, "contact_requests"):
            cur.execute("""
                CREATE TABLE contact_requests (
                    id         INT IDENTITY(1,1) NOT NULL,
                    name       NVARCHAR(255) NOT NULL DEFAULT '',
                    email      NVARCHAR(255) NOT NULL DEFAULT '',
                    phone      NVARCHAR(100) NOT NULL DEFAULT '',
                    message    NVARCHAR(MAX) NOT NULL DEFAULT '',
                    created_at DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_contact_requests PRIMARY KEY (id)
                )
            """)

        # ── 29. promo_bar_templates ────────────────────────────────────────────
        if not _table_exists(cur, "promo_bar_templates"):
            cur.execute("""
                CREATE TABLE promo_bar_templates (
                    id          INT IDENTITY(1,1) NOT NULL,
                    name        NVARCHAR(255) NOT NULL,
                    html        NVARCHAR(MAX) NOT NULL DEFAULT '',
                    css         NVARCHAR(MAX) NOT NULL DEFAULT '',
                    is_active   BIT           NOT NULL DEFAULT 0,
                    created_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    updated_at  DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_promo_bar_templates PRIMARY KEY (id)
                )
            """)

        # ── 28. page_content ───────────────────────────────────────────────────
        if not _table_exists(cur, "page_content"):
            cur.execute("""
                CREATE TABLE page_content (
                    [key]      NVARCHAR(100) NOT NULL,
                    lang       NVARCHAR(10)  NOT NULL DEFAULT 'vi',
                    value      NVARCHAR(MAX) NOT NULL DEFAULT '',
                    updated_at DATETIME2     NOT NULL DEFAULT GETDATE(),
                    CONSTRAINT PK_page_content PRIMARY KEY ([key], lang)
                )
            """)

    finally:
        conn.close()


# ── Step 4: Seed data ──────────────────────────────────────────────────────────

def _seed_data() -> None:
    with get_conn() as conn:
        _seed_brokers(conn)
        _seed_programs(conn)
        _seed_admin_user(conn)
        _seed_singletons(conn)
        _seed_page_content(conn)
        _seed_promo_bar(conn)


def _seed_brokers(conn) -> None:
    for name, slug, is_active, order in [
        ("Vantage",      "vantage",      1, 1),
        ("Exness",       "exness",       0, 2),
        ("FxPro",        "fxpro",        0, 3),
        ("Pepperstone",  "pepperstone",  0, 4),
        ("MultiBank",    "multibank",    0, 5),
        ("FP Markets",   "fpmarkets",    0, 6),
        ("IC Markets",   "icmarkets",    0, 7),
        ("Titan FX",     "titanfx",      0, 8),
        ("IUX",          "iux",          0, 9),
        ("Mitrade",      "mitrade",      0, 10),
        ("EC Markets",   "ec",           0, 11),
        ("VT Market",    "vtmarket",     0, 12),
        ("Dupoin",       "dupoin",       0, 13),
        ("Ultima",       "ultima",       1, 14),
        # Backcom.io brokers — inactive
        ("Binance",      "binance",      0, 15),
        ("Bybit",        "bybit",        0, 16),
        ("OKX",          "okx",          0, 17),
        ("KuCoin",       "kucoin",       0, 18),
        ("MEXC",         "mexc",         0, 19),
        ("BingX",        "bingx",        0, 20),
        ("Bitget",       "bitget",       0, 21),
        ("HTX",          "htx",          0, 22),
        ("Gate.io",      "gateio",       0, 23),
        ("ProBit Global","probit",       0, 24),
        ("XM",           "xm",           0, 25),
        ("FBS",          "fbs",          0, 26),
        ("FXTM",         "fxtm",         0, 27),
        ("Tickmill",     "tickmill",     0, 28),
    ]:
        if not conn.execute("SELECT 1 FROM brokers WHERE slug=?", (slug,)).fetchone():
            conn.execute(
                "INSERT INTO brokers (name, slug, is_active, display_order) VALUES (?,?,?,?)",
                (name, slug, is_active, order),
            )
    _backfill_broker_profiles(conn)


def _backfill_broker_profiles(conn) -> None:
    """One-time backfill: populate broker profile columns from hardcoded data."""
    # Only run if Vantage has no logo_color yet
    row = conn.execute(
        "SELECT logo_color FROM brokers WHERE slug='vantage'"
    ).fetchone()
    if row and row["logo_color"]:
        return  # already backfilled

    _PROFILES = {
        "vantage": {
            "logo_color": "#c9a227", "rating": 4.8,
            "licenses": "ASIC,FCA,VFSC",
            "features": "World-leading ECN broker, established 2009\nLow spreads from 0.0 pips, no requotes\nMT4, MT5, ProTrader & TradingView platforms\nFlexible leverage up to 1:500\nVND deposit/withdrawal support, fast processing\nIntegrated Copy trading & Social trading",
            "features_en": "World-leading ECN broker, established 2009\nLow spreads from 0.0 pips, no requotes\nMT4, MT5, ProTrader & TradingView platforms\nFlexible leverage up to 1:500\nVND deposit/withdrawal support, fast processing\nIntegrated Copy trading & Social trading",
            "assets_count": "1.000+", "min_deposit": "$50",
            "visit_url": "https://www.vantagemarkets.com",
            "status": "active", "badge_text": "Cashback",
            "extra_stat_label": "speed", "extra_stat_value": "< 40ms",
            "show_on_brokers_page": 1, "logo_font_size": 17,
        },
        "exness": {
            "logo_color": "#00c47a", "rating": 4.9,
            "licenses": "FCA,CySEC,FSA",
            "features": "Five diverse account types for every need\nMinimum deposit from just $10\nLow and stable spreads\n70+ MetaTrader servers worldwide\nUnlimited customizable leverage",
            "features_en": "Five diverse account types for every need\nMinimum deposit from just $10\nLow and stable spreads\n70+ MetaTrader servers worldwide\nUnlimited customizable leverage",
            "assets_count": "100+", "min_deposit": "$10",
            "status": "coming_soon",
            "extra_stat_label": "neg_bal", "extra_stat_value": "Yes",
            "show_on_brokers_page": 1, "logo_font_size": 17,
        },
        "fxpro": {
            "logo_color": "#e63946", "rating": 4.7,
            "licenses": "FCA,CySEC,DFSA",
            "features": "4 diverse account types\n2,100+ tradable assets\nRegulated by top-tier authorities\nAdvanced trading tools available",
            "features_en": "4 diverse account types\n2,100+ tradable assets\nRegulated by top-tier authorities\nAdvanced trading tools available",
            "assets_count": "2.100+", "min_deposit": "$100",
            "visit_url": "https://www.fxpro.com",
            "review_url": "https://vn.investing.com/brokers/reviews/fxpro/",
            "status": "active", "badge_text": "Trusted",
            "show_on_brokers_page": 1, "logo_font_size": 14,
        },
        "pepperstone": {
            "logo_color": "#00a878", "rating": 4.7,
            "licenses": "ASIC,FCA,CySEC",
            "features": "World-class liquidity and pricing\nLicensed in 8 jurisdictions\n1,350+ CFD instruments available\nMT4, MT5, cTrader & TradingView",
            "features_en": "World-class liquidity and pricing\nLicensed in 8 jurisdictions\n1,350+ CFD instruments available\nMT4, MT5, cTrader & TradingView",
            "assets_count": "1.350+", "min_deposit": "$0",
            "visit_url": "https://www.pepperstone.com",
            "review_url": "https://vn.investing.com/brokers/reviews/pepperstone/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 12,
        },
        "multibank": {
            "logo_color": "#4d9fff", "rating": 4.7,
            "licenses": "ASIC,FCA,BaFin",
            "features": "$322M paid-up capital\nSpreads from 0.0 pips (ECN)\nLeverage up to 500:1\n20,000+ diverse tradable assets",
            "features_en": "$322M paid-up capital\nSpreads from 0.0 pips (ECN)\nLeverage up to 500:1\n20,000+ diverse tradable assets",
            "assets_count": "20.000+", "min_deposit": "$50",
            "visit_url": "https://www.multibankfx.com",
            "review_url": "https://vn.investing.com/brokers/reviews/multibank/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 11,
        },
        "fpmarkets": {
            "logo_color": "#5b9cf6", "rating": 4.6,
            "licenses": "ASIC,CySEC",
            "features": "Tight raw spreads from 0.0 pips\nMT4, MT5, cTrader, TradingView platforms\nMultilingual customer support 24/7\n50+ global industry awards",
            "features_en": "Tight raw spreads from 0.0 pips\nMT4, MT5, cTrader, TradingView platforms\nMultilingual customer support 24/7\n50+ global industry awards",
            "assets_count": "10.000+", "min_deposit": "$100",
            "visit_url": "https://www.fpmarkets.com",
            "review_url": "https://vn.investing.com/brokers/reviews/fp-markets/",
            "status": "active", "badge_text": "Trusted",
            "show_on_brokers_page": 1, "logo_font_size": 11,
        },
        "icmarkets": {
            "logo_color": "#7ec8ff", "rating": 4.6,
            "licenses": "ASIC,CySEC,FSA",
            "features": "Three flexible account types\n2,250+ diverse tradable assets\nSpreads from 0.0 pips, deep liquidity\nMT4, MT5 & cTrader",
            "features_en": "Three flexible account types\n2,250+ diverse tradable assets\nSpreads from 0.0 pips, deep liquidity\nMT4, MT5 & cTrader",
            "assets_count": "2.250+", "min_deposit": "$200",
            "visit_url": "https://www.icmarkets.com",
            "review_url": "https://vn.investing.com/brokers/reviews/ic-markets/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 11,
        },
        "titanfx": {
            "logo_color": "#ccc", "rating": 4.6,
            "licenses": "VFSC,FSA",
            "features": "Multilingual customer support 24/7\nUltra-tight spreads on major pairs\nECN-style fast execution\n300+ trading instruments",
            "features_en": "Multilingual customer support 24/7\nUltra-tight spreads on major pairs\nECN-style fast execution\n300+ trading instruments",
            "assets_count": "300+", "min_deposit": "$0",
            "visit_url": "https://www.titanfx.com",
            "review_url": "https://vn.investing.com/brokers/reviews/titan-fx/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 13,
        },
        "iux": {
            "logo_color": "#a78bfa", "rating": 4.6,
            "licenses": "FSA,VFSC",
            "features": "Advanced trading technology\nDedicated customer support 24/5\nComprehensive financial services\n138 tradable assets",
            "features_en": "Advanced trading technology\nDedicated customer support 24/5\nComprehensive financial services\n138 tradable assets",
            "assets_count": "138", "min_deposit": "$30",
            "visit_url": "https://www.iux.com",
            "review_url": "https://vn.investing.com/brokers/reviews/iux/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 14,
        },
        "mitrade": {
            "logo_color": "#fb923c", "rating": 4.5,
            "licenses": "ASIC,CySEC,FSA",
            "features": "Authorized broker with 4 licenses\n800+ diverse CFD instruments\nZero commission, tight spreads\nUser-friendly interface",
            "features_en": "Authorized broker with 4 licenses\n800+ diverse CFD instruments\nZero commission, tight spreads\nUser-friendly interface",
            "assets_count": "800+", "min_deposit": "$20",
            "visit_url": "https://www.mitrade.com",
            "review_url": "https://vn.investing.com/brokers/reviews/mitrade/",
            "status": "active",
            "show_on_brokers_page": 1, "logo_font_size": 13,
        },
        "ec": {
            "logo_color": "#5b9cf6", "rating": 4.3,
            "licenses": "ASIC,FSA",
            "features": "Specialized broker for Asian markets\nCompetitive spreads from 0.0 pips\nMT4 & MT5 with custom indicators\nVietnamese support 24/5\nFast deposit/withdrawal via local banks",
            "features_en": "Specialized broker for Asian markets\nCompetitive spreads from 0.0 pips\nMT4 & MT5 with custom indicators\nVietnamese support 24/5\nFast deposit/withdrawal via local banks",
            "assets_count": "200+", "min_deposit": "$200",
            "status": "coming_soon",
            "show_on_brokers_page": 1, "logo_font_size": 14,
        },
        "vtmarket": {
            "logo_color": "#e85d4a", "rating": 4.2,
            "licenses": "ASIC,CIMA",
            "features": "Long-established trusted brand in Southeast Asia\nDiverse STP & ECN accounts\nMT4, MT5 & WebTrader\nAttractive welcome bonus for new traders\nDeep liquidity from top-tier providers",
            "features_en": "Long-established trusted brand in Southeast Asia\nDiverse STP & ECN accounts\nMT4, MT5 & WebTrader\nAttractive welcome bonus for new traders\nDeep liquidity from top-tier providers",
            "assets_count": "500+", "min_deposit": "$100",
            "status": "coming_soon",
            "show_on_brokers_page": 1, "logo_font_size": 14,
        },
    }

    # Hide all brokers from public page first, then enable only profiled ones
    profile_slugs = list(_PROFILES.keys())
    conn.execute("UPDATE brokers SET show_on_brokers_page=0 WHERE slug NOT IN (%s)"
                 % ",".join("?" * len(profile_slugs)), profile_slugs)

    for slug, profile in _PROFILES.items():
        cols = ", ".join(f"{k}=?" for k in profile)
        vals = list(profile.values())
        vals.append(slug)
        conn.execute(f"UPDATE brokers SET {cols} WHERE slug=?", vals)


def _seed_programs(conn) -> None:
    # Seed one backcom 80% program per broker (skip if any programs already exist)
    if conn.execute("SELECT 1 FROM programs").fetchone():
        return
    brokers = conn.execute(
        "SELECT id, name FROM brokers WHERE is_active=1 ORDER BY display_order"
    ).fetchall()
    for i, b in enumerate(brokers):
        row = conn.execute(
            "INSERT INTO programs (name, type, is_active, display_order, rebate_pct) "
            "OUTPUT INSERTED.id VALUES (?,?,?,?,?)",
            (f"Backcom {b['name']} 80%", "backcom", 1, i + 1, 80),
        ).fetchone()
        conn.execute(
            "INSERT INTO program_brokers (program_id, broker_id) VALUES (?,?)",
            (row["id"], b["id"]),
        )


def _seed_admin_user(conn) -> None:
    if not conn.execute("SELECT 1 FROM users WHERE username=?", ("admin",)).fetchone():
        from app.services.auth import hash_pw
        pw_hash = hash_pw("admin123")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?,?)",
            ("admin", pw_hash),
        )


def _seed_singletons(conn) -> None:
    if not conn.execute("SELECT 1 FROM smtp_config WHERE id=1").fetchone():
        conn.execute("INSERT INTO smtp_config (id) VALUES (1)")
    if not conn.execute("SELECT 1 FROM google_oauth_config WHERE id=1").fetchone():
        conn.execute("INSERT INTO google_oauth_config (id) VALUES (1)")


def _seed_page_content(conn) -> None:
    defaults = [
        ("hero_eyebrow",       "vi", "🏆 Smart Rebate — Earn up to $10 per lot"),
        ("hero_title_line1",   "vi", "Trade Forex & Gold"),
        ("hero_title_accent",  "vi", "Get cashback on every trade"),
        ("hero_sub",           "vi", "Trade as usual and earn rebates on every lot.\nAutomatic daily payouts directly to your account."),
        ("hero_btn_primary",   "vi", "Get cashback now"),
        ("hero_btn_secondary", "vi", "See how it works ↓"),
        ("hero_stat1_val",     "vi", "$10"),
        ("hero_stat1_label",   "vi", "Max cashback / lot"),
        ("hero_stat2_val",     "vi", "$2,000"),
        ("hero_stat2_label",   "vi", "Gold Trader Bonus"),
        ("hero_stat3_val",     "vi", "Daily"),
        ("hero_stat3_label",   "vi", "Automatic payout"),
        ("benefits_tag",       "vi", "Benefits"),
        ("benefits_title",     "vi", "Why traders choose TradingBonusHub"),
        ("benefits_sub",       "vi", "Trade as usual — earn extra cashback every day"),
        ("site_title",         "vi", "Trading Bonus Hub | Daily Cashback & Forex Bonus for Traders"),
        ("site_description",   "vi", "Best trading bonus program for traders — earn cashback & forex bonus up to $2,000/month from Forex & Gold trading. Sign up free, daily payouts."),
        # English defaults
        ("hero_eyebrow",       "en", "🏆 Smart Rebate — Earn up to $10 per lot"),
        ("hero_title_line1",   "en", "Trade Forex & Gold"),
        ("hero_title_accent",  "en", "Get cashback on every trade"),
        ("hero_sub",           "en", "Trade as usual and earn rebates on every lot.\nAutomatic daily payouts directly to your account."),
        ("hero_btn_primary",   "en", "Get cashback now"),
        ("hero_btn_secondary", "en", "See how it works ↓"),
        ("hero_stat1_val",     "en", "$10"),
        ("hero_stat1_label",   "en", "Max cashback / lot"),
        ("hero_stat2_val",     "en", "$2,000"),
        ("hero_stat2_label",   "en", "Gold Trader Bonus"),
        ("hero_stat3_val",     "en", "Daily"),
        ("hero_stat3_label",   "en", "Automatic payout"),
        ("benefits_tag",       "en", "Benefits"),
        ("benefits_title",     "en", "Why traders choose TradingBonusHub"),
        ("benefits_sub",       "en", "Trade as usual — earn extra cashback every day"),
        ("site_title",         "en", "Trading Bonus Hub | Daily Cashback & Forex Bonus for Traders"),
        ("site_description",   "en", "Best trading bonus program — earn cashback & forex bonus up to $2,000/month from Forex & Gold trading. Free registration, daily payouts."),
        # Hero highlights
        ("hero_hl1", "vi", "Cashback per trade"),
        ("hero_hl2", "vi", "No spread impact"),
        ("hero_hl3", "vi", "MT4 / MT5 supported"),
        ("hero_hl4", "vi", "Global traders"),
        ("hero_hl1", "en", "Cashback per trade"),
        ("hero_hl2", "en", "No spread impact"),
        ("hero_hl3", "en", "MT4 / MT5 supported"),
        ("hero_hl4", "en", "Global traders"),
        # Broker marquee
        ("marquee_label", "vi", "Our partners"),
        ("marquee_label", "en", "Our partners"),
        # Benefits cards
        ("b1_icon", "vi", "💰"), ("b1_title", "vi", "Attractive cashback"), ("b1_big", "vi", "Rebate\nper lot"), ("b1_desc", "vi", "Applies to Gold, Silver, Oil and Forex"),
        ("b2_icon", "vi", "🏆"), ("b2_title", "vi", "Gold Trader Bonus"), ("b2_big", "vi", "$2,000/month"), ("b2_desc", "vi", "Extra bonus when reaching high trading volume"),
        ("b3_icon", "vi", "⚡"), ("b3_title", "vi", "Automatic payouts"), ("b3_big", "vi", "Daily payout"), ("b3_desc", "vi", "Cashback is calculated and paid automatically every day"),
        ("b4_icon", "vi", "🤝"), ("b4_title", "vi", "Direct broker partner support"), ("b4_big", "vi", "Official broker partner"), ("b4_desc", "vi", "Dedicated support to quickly resolve account and trading issues."),
        ("b1_icon", "en", "💰"), ("b1_title", "en", "Attractive cashback"), ("b1_big", "en", "Rebate\nper lot"), ("b1_desc", "en", "Applies to Gold, Silver, Oil and Forex"),
        ("b2_icon", "en", "🏆"), ("b2_title", "en", "Gold Trader Bonus"), ("b2_big", "en", "$2,000/month"), ("b2_desc", "en", "Extra bonus when reaching high trading volume"),
        ("b3_icon", "en", "⚡"), ("b3_title", "en", "Automatic payouts"), ("b3_big", "en", "Daily payout"), ("b3_desc", "en", "Cashback is calculated and paid automatically every day"),
        ("b4_icon", "en", "🤝"), ("b4_title", "en", "Direct broker partner support"), ("b4_big", "en", "Official broker partner"), ("b4_desc", "en", "Dedicated support to quickly resolve account and trading issues."),
        # Gold Bonus section
        ("gold_tag",    "vi", "🏆 Gold Trader Bonus Program"),
        ("gold_h3_l1",  "vi", "Trade Gold / Silver / Oil"),
        ("gold_h3_l2",  "vi", "Earn extra Cash Bonus"),
        ("gold_h3_hl",  "vi", "up to $2,000"),
        ("gold_h3_sfx", "vi", "per month"),
        ("gold_p",      "vi", "In addition to daily cashback, traders in Gold, Silver or Oil can also earn extra cash bonus based on monthly volume."),
        ("gold_note",   "vi", "Cash bonus will be paid automatically the following month."),
        ("gold_btn",    "vi", "Sign Up Now →"),
        ("gold_col1",   "vi", "Monthly Volume (Gold / Silver / Oil)"),
        ("gold_col2",   "vi", "Cash Bonus"),
        ("gold_tag",    "en", "🏆 Gold Trader Bonus Program"),
        ("gold_h3_l1",  "en", "Trade Gold / Silver / Oil"),
        ("gold_h3_l2",  "en", "Earn extra Cash Bonus"),
        ("gold_h3_hl",  "en", "up to $2,000"),
        ("gold_h3_sfx", "en", "per month"),
        ("gold_p",      "en", "In addition to daily cashback, traders in Gold, Silver or Oil can also earn extra cash bonus based on monthly volume."),
        ("gold_note",   "en", "Cash bonus will be paid automatically the following month."),
        ("gold_btn",    "en", "Register now →"),
        ("gold_col1",   "en", "Monthly Volume (Gold / Silver / Oil)"),
        ("gold_col2",   "en", "Cash Bonus"),
        # Calculator
        ("calc_brokers_label","vi", "the best offers for you"),
        ("calc_tag",          "vi", "🧮 Calculator"),
        ("calc_title",        "vi", "How much can you earn?"),
        ("calc_sub",          "vi", "Drag the slider to see estimated rebate + bonus per month"),
        ("calc_slider_title", "vi", "Gold volume / month"),
        ("calc_rebate_label", "vi", "Estimated rebate"),
        ("calc_bonus_label",  "vi", "Gold Bonus"),
        ("calc_total_label",  "vi", "Total"),
        ("calc_note",         "vi", "⚡ Estimate based on actual rebate rates. Actual amount may vary by trade timing."),
        ("calc_brokers_label","en", "the best offers for you"),
        ("calc_tag",          "en", "🧮 Calculator"),
        ("calc_title",        "en", "How much can you earn?"),
        ("calc_sub",          "en", "Drag the slider to see estimated rebate + bonus per month"),
        ("calc_slider_title", "en", "Gold volume / month"),
        ("calc_rebate_label", "en", "Estimated rebate"),
        ("calc_bonus_label",  "en", "Gold Bonus"),
        ("calc_total_label",  "en", "Total"),
        ("calc_note",         "en", "⚡ Estimate based on actual rebate rates. Actual amount may vary by trade timing."),
        # Real example
        ("ex_tag",        "vi", "Real income example"),
        ("ex_title",      "vi", "How much does a trader earn with 200 lots of Gold per month?"),
        ("ex_sub",        "vi", "Trade as usual — earn an extra $1,600 per month"),
        ("ex_head_label", "vi", "Trader A — Vantage Markets"),
        ("ex_head_vol",   "vi", "Trading volume: 200 lots Gold"),
        ("ex_head_period","vi", "March 2026"),
        ("ex_total_label","vi", "Total cashback received this month"),
        ("ex_total_val",  "vi", "$1,600"),
        ("ex_r1_k", "vi", "Trading volume"),   ("ex_r1_v", "vi", "200 lots XAUUSD"),
        ("ex_r2_k", "vi", "Cashback from trading"), ("ex_r2_v", "vi", "$1,000"),
        ("ex_r3_k", "vi", "Gold Trader Bonus (200 lot milestone)"), ("ex_r3_v", "vi", "$600"),
        ("ex_r4_k", "vi", "Does spread change?"), ("ex_r4_v", "vi", "✓ No — completely unchanged"),
        ("ex_foot_label", "vi", "Total cashback received this month"),
        ("ex_foot_val",   "vi", "$1,600"),
        ("ex_tag",        "en", "Real income example"),
        ("ex_title",      "en", "How much does a trader earn with 200 lots of Gold per month?"),
        ("ex_sub",        "en", "Trade as usual — earn an extra $1,600 per month"),
        ("ex_head_label", "en", "Trader A — Vantage Markets"),
        ("ex_head_vol",   "en", "Trading volume: 200 lots Gold"),
        ("ex_head_period","en", "March 2026"),
        ("ex_total_label","en", "Total cashback received this month"),
        ("ex_total_val",  "en", "$1,600"),
        ("ex_r1_k", "en", "Trading volume"),   ("ex_r1_v", "en", "200 lots XAUUSD"),
        ("ex_r2_k", "en", "Cashback from trading"), ("ex_r2_v", "en", "$1,000"),
        ("ex_r3_k", "en", "Gold Trader Bonus (200 lot milestone)"), ("ex_r3_v", "en", "$600"),
        ("ex_r4_k", "en", "Does spread change?"), ("ex_r4_v", "en", "✓ No — completely unchanged"),
        ("ex_foot_label", "en", "Total cashback received this month"),
        ("ex_foot_val",   "en", "$1,600"),
        # Leaderboard
        ("lb_tag",   "vi", "🏆 Top Gold Traders This Month"),
        ("lb_title", "vi", "Top Gold Traders Leaderboard"),
        ("lb_sub",   "vi", "Top traders with highest cashback in March 2026 · Updated monthly"),
        ("lb_col1",  "vi", "Rank"), ("lb_col2", "vi", "Trader"), ("lb_col3", "vi", "Gold Volume (lot)"), ("lb_col4", "vi", "Total Cashback"),
        ("lb_r1_name", "vi", "Trader***21"), ("lb_r1_vol", "vi", "520 lot"), ("lb_r1_reward", "vi", "$4,600"),
        ("lb_r2_name", "vi", "Gold***Pro"), ("lb_r2_vol", "vi", "480 lot"), ("lb_r2_reward", "vi", "$4,400"),
        ("lb_r3_name", "vi", "FX***King"),  ("lb_r3_vol", "vi", "430 lot"), ("lb_r3_reward", "vi", "$4,150"),
        ("lb_r4_name", "vi", "VN***Trader"),("lb_r4_vol", "vi", "210 lot"), ("lb_r4_reward", "vi", "$1,650"),
        ("lb_r5_name", "vi", "Pro***FX"),   ("lb_r5_vol", "vi", "160 lot"), ("lb_r5_reward", "vi", "$1,050"),
        ("lb_foot",      "vi", "You can appear on this leaderboard too."),
        ("lb_foot_link", "vi", "Start earning cashback now →"),
        ("lb_tag",   "en", "🏆 Top Gold Traders This Month"),
        ("lb_title", "en", "Top Gold Traders Leaderboard"),
        ("lb_sub",   "en", "Top traders with highest cashback in March 2026 · Updated monthly"),
        ("lb_col1",  "en", "Rank"), ("lb_col2", "en", "Trader"), ("lb_col3", "en", "Gold Volume (lot)"), ("lb_col4", "en", "Total Cashback"),
        ("lb_r1_name", "en", "Trader***21"), ("lb_r1_vol", "en", "520 lot"), ("lb_r1_reward", "en", "$4,600"),
        ("lb_r2_name", "en", "Gold***Pro"), ("lb_r2_vol", "en", "480 lot"), ("lb_r2_reward", "en", "$4,400"),
        ("lb_r3_name", "en", "FX***King"),  ("lb_r3_vol", "en", "430 lot"), ("lb_r3_reward", "en", "$4,150"),
        ("lb_r4_name", "en", "VN***Trader"),("lb_r4_vol", "en", "210 lot"), ("lb_r4_reward", "en", "$1,650"),
        ("lb_r5_name", "en", "Pro***FX"),   ("lb_r5_vol", "en", "160 lot"), ("lb_r5_reward", "en", "$1,050"),
        ("lb_foot",      "en", "You can appear on this leaderboard too."),
        ("lb_foot_link", "en", "Start earning cashback now →"),
        # How it works
        ("how_tag",    "vi", "How it works"),
        ("how_title",  "vi", "Start earning cashback in just 4 steps"),
        ("how_sub",    "vi", "Takes just a few minutes to set up — then earn cashback on every trade"),
        ("step1_title","vi", "Create an account"),
        ("step1_desc", "vi", "Register a free TradingBonusHub account"),
        ("step2_title","vi", "Transfer account to rebate system"),
        ("step2_desc", "vi", "The process may vary per broker. We will guide you in detail."),
        ("step3_title","vi", "Enroll in a program"),
        ("step3_desc", "vi", "Choose the right program and click enroll."),
        ("step4_title","vi", "Trade & earn cashback"),
        ("step4_desc", "vi", "Continue trading as usual. Cashback is automatically calculated based on your trading volume."),
        ("how_tag",    "en", "How it works"),
        ("how_title",  "en", "Start earning cashback in just 4 steps"),
        ("how_sub",    "en", "Takes just a few minutes to set up — then earn cashback on every trade"),
        ("step1_title","en", "Create an account"),
        ("step1_desc", "en", "Register a free TradingBonusHub account"),
        ("step2_title","en", "Transfer account to rebate system"),
        ("step2_desc", "en", "The process may vary per broker. We will guide you in detail."),
        ("step3_title","en", "Enroll in a program"),
        ("step3_desc", "en", "Choose the right program and click enroll."),
        ("step4_title","en", "Trade & earn cashback"),
        ("step4_desc", "en", "Continue trading as usual. Cashback is automatically calculated based on your trading volume."),
        # FAQ header
        ("faq_tag",   "vi", "Q&A"),
        ("faq_title", "vi", "Frequently asked questions"),
        ("faq_tag",   "en", "Q&A"),
        ("faq_title", "en", "Frequently asked questions"),
        # Final CTA
        ("final_title", "vi", "Start earning rebate today"),
        ("final_sub",   "vi", "Thousands of traders are reducing trading costs with TradingBonusHub.\nFree registration — earn from day one."),
        ("final_btn",   "vi", "Sign Up Now →"),
        ("final_chip1", "vi", "Free registration"),
        ("final_chip2", "vi", "No spread changes"),
        ("final_chip3", "vi", "MT4 & MT5"),
        ("final_chip4", "vi", "Daily payouts"),
        ("final_title", "en", "Start earning rebate today"),
        ("final_sub",   "en", "Thousands of traders are reducing trading costs with TradingBonusHub.\nFree registration — earn from day one."),
        ("final_btn",   "en", "Register now →"),
        ("final_chip1", "en", "Free registration"),
        ("final_chip2", "en", "No spread changes"),
        ("final_chip3", "en", "MT4 & MT5"),
        ("final_chip4", "en", "Daily payouts"),
        # Footer
        ("footer_tagline", "vi", "Trading rebate system for Forex & Gold traders"),
        ("footer_copy",    "vi", "© 2026 TradingBonusHub — support@tradingbonushub.com"),
        ("footer_tagline", "en", "Trading rebate system for Forex & Gold traders"),
        ("footer_copy",    "en", "© 2026 TradingBonusHub — support@tradingbonushub.com"),
    ]
    for key, lang, value in defaults:
        if not conn.execute(
            "SELECT 1 FROM page_content WHERE [key]=? AND lang=?", (key, lang)
        ).fetchone():
            conn.execute(
                "INSERT INTO page_content ([key], lang, value) VALUES (?,?,?)",
                (key, lang, value),
            )


def _seed_promo_bar(conn) -> None:
    """Seed default promo bar template if none exists."""
    if conn.execute("SELECT 1 FROM promo_bar_templates").fetchone():
        return
    default_html = """\
<section class="hero-promo" id="heroPromo">
  <div class="promo-inner">
    <div class="promo-left">
      <div class="promo-badge">Vantage customers only</div>
      <h2 class="promo-title">Sign up for the first time \u2014 get <em>100% exclusive for Vantage customers</em></h2>
      <p class="promo-sub">100% refund exclusively for Vantage customers for your first 30 days. No hidden conditions, no order limits.</p>
      <ul class="promo-perks">
        <li>Applies from your very first trade</li>
        <li>No trading volume limits</li>
        <li>Withdraw rebate anytime</li>
      </ul>
      <div class="promo-cta-wrap">
        <a class="promo-cta" href="/portal/login">Sign up for offer \u2192</a>
        <a class="promo-cta-ghost" href="#calculator">See how rebate is calculated</a>
      </div>
    </div>
    <div class="promo-right">
      <div class="promo-big">
        <div class="promo-number">100%</div>
        <div class="promo-number-label">Exclusive for Vantage customers</div>
        <div class="promo-countdown" id="promoCountdown">
          <div class="promo-cd-item"><div class="promo-cd-val" id="cdDays">18</div><div class="promo-cd-lbl">Days</div></div>
          <div class="promo-cd-item"><div class="promo-cd-val" id="cdHours">05</div><div class="promo-cd-lbl">Hours</div></div>
          <div class="promo-cd-item"><div class="promo-cd-val" id="cdMins">13</div><div class="promo-cd-lbl">Mins</div></div>
          <div class="promo-cd-item"><div class="promo-cd-val" id="cdSecs">04</div><div class="promo-cd-lbl">Secs</div></div>
        </div>
        <div class="promo-social"><strong id="traderCount">1,234</strong> traders have claimed this offer</div>
      </div>
    </div>
  </div>
</section>"""
    conn.execute(
        "INSERT INTO promo_bar_templates (name, html, css, is_active) VALUES (?,?,?,?)",
        ("100% exclusive for Vantage customers (original template)", default_html, "", 0),
    )

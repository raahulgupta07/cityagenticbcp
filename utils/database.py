"""
CityBCPAgent v1 — SQLite Database Layer (WAL mode)
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from config.settings import DB_PATH, DATA_DIR

# ─── Connection ──────────────────────────────────────────────────────────────

def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
    _ensure_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ─── Schema ──────────────────────────────────────────────────────────────────

SCHEMA = """
-- 1. Sectors
CREATE TABLE IF NOT EXISTS sectors (
    sector_id   TEXT PRIMARY KEY,
    sector_name TEXT NOT NULL,
    region      TEXT
);

-- 2. Sites
CREATE TABLE IF NOT EXISTS sites (
    site_id             TEXT PRIMARY KEY,
    site_name           TEXT NOT NULL,
    sector_id           TEXT NOT NULL REFERENCES sectors(sector_id),
    site_type           TEXT DEFAULT 'Regular',
    cost_center_code    TEXT,
    region              TEXT,
    business_sector     TEXT,
    company             TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- 3. Generators
CREATE TABLE IF NOT EXISTS generators (
    generator_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id             TEXT NOT NULL REFERENCES sites(site_id),
    model_name          TEXT NOT NULL,
    model_name_raw      TEXT,
    power_kva           REAL,
    consumption_per_hour REAL,
    fuel_type           TEXT,
    supplier            TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- 4. Daily Operations (per-generator per-day fact table)
CREATE TABLE IF NOT EXISTS daily_operations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    generator_id        INTEGER NOT NULL REFERENCES generators(generator_id),
    site_id             TEXT NOT NULL REFERENCES sites(site_id),
    date                TEXT NOT NULL,
    gen_run_hr          REAL,
    daily_used_liters   REAL,
    spare_tank_balance  REAL,
    blackout_hr         REAL,
    source              TEXT DEFAULT 'excel',
    upload_batch_id     INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(generator_id, date)
);

-- 5. Fuel Purchases
CREATE TABLE IF NOT EXISTS fuel_purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_id       TEXT NOT NULL REFERENCES sectors(sector_id),
    date            TEXT NOT NULL,
    region          TEXT,
    supplier        TEXT,
    fuel_type       TEXT,
    quantity_liters REAL,
    price_per_liter REAL,
    source          TEXT DEFAULT 'excel',
    upload_batch_id INTEGER,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 6. Daily Site Summary (materialized view)
CREATE TABLE IF NOT EXISTS daily_site_summary (
    site_id                 TEXT NOT NULL REFERENCES sites(site_id),
    date                    TEXT NOT NULL,
    total_gen_run_hr        REAL DEFAULT 0,
    total_daily_used        REAL DEFAULT 0,
    spare_tank_balance      REAL,
    blackout_hr             REAL,
    days_of_buffer          REAL,
    num_generators_active   INTEGER DEFAULT 0,
    PRIMARY KEY (site_id, date)
);

-- 7. Generator Name Map (canonical resolution)
CREATE TABLE IF NOT EXISTS generator_name_map (
    raw_name        TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    auto_mapped     INTEGER DEFAULT 1
);

-- 8. Upload History
CREATE TABLE IF NOT EXISTS upload_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    filename            TEXT NOT NULL,
    file_type           TEXT NOT NULL,
    sector_id           TEXT,
    rows_parsed         INTEGER DEFAULT 0,
    rows_accepted       INTEGER DEFAULT 0,
    rows_rejected       INTEGER DEFAULT 0,
    date_range_start    TEXT,
    date_range_end      TEXT,
    validation_errors   TEXT,
    uploaded_at         TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 9. Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type          TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'INFO',
    site_id             TEXT,
    sector_id           TEXT,
    message             TEXT NOT NULL,
    metric_value        REAL,
    threshold           REAL,
    is_acknowledged     INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- 10. Incidents (manual logging)
CREATE TABLE IF NOT EXISTS incidents (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id                 TEXT REFERENCES sites(site_id),
    incident_type           TEXT NOT NULL,
    start_time              TEXT,
    end_time                TEXT,
    duration_hours          REAL,
    response_time_minutes   REAL,
    estimated_loss_mmk      REAL,
    actions_taken           TEXT,
    lessons_learned         TEXT,
    logged_by               TEXT,
    created_at              TEXT DEFAULT (datetime('now'))
);

-- 11. Users (authentication + roles)
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    email           TEXT,
    role            TEXT NOT NULL DEFAULT 'user',
    sectors         TEXT,
    is_active       INTEGER DEFAULT 1,
    last_login      TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 12. App Settings (SMTP, preferences — configured via UI)
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- 12. Alert Recipients
CREATE TABLE IF NOT EXISTS alert_recipients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    role        TEXT DEFAULT 'viewer',
    sectors     TEXT,
    severity_filter TEXT DEFAULT 'CRITICAL,WARNING',
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 13. Email Log
CREATE TABLE IF NOT EXISTS email_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient   TEXT NOT NULL,
    subject     TEXT NOT NULL,
    alert_count INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'sent',
    error       TEXT,
    sent_at     TEXT DEFAULT (datetime('now'))
);

-- 14. AI Insights Cache (persists across sessions)
CREATE TABLE IF NOT EXISTS ai_insights_cache (
    insight_key         TEXT PRIMARY KEY,
    insight_type        TEXT NOT NULL,
    insight_text        TEXT NOT NULL,
    data_date           TEXT,
    generated_at        TEXT DEFAULT (datetime('now'))
);

-- 15. Store Master (sales system reference)
CREATE TABLE IF NOT EXISTS store_master (
    gold_code           TEXT PRIMARY KEY,
    pos_code            TEXT,
    store_name          TEXT,
    cost_center_code    TEXT,
    cost_center_name    TEXT,
    segment_id          INTEGER,
    segment_name        TEXT,
    company_code        TEXT,
    legal_entity        TEXT,
    channel             TEXT,
    address_state       TEXT,
    address_township    TEXT,
    latitude            REAL,
    longitude           REAL,
    store_size          TEXT,
    open_date           TEXT,
    closed_date         TEXT,
    sector_id           TEXT REFERENCES sectors(sector_id),
    created_at          TEXT DEFAULT (datetime('now'))
);

-- 16. Site-Sales Mapping (maps sales Site Name → BCP site_id)
CREATE TABLE IF NOT EXISTS site_sales_map (
    sales_site_name TEXT PRIMARY KEY,
    site_id         TEXT REFERENCES sites(site_id),
    sector_id       TEXT REFERENCES sectors(sector_id),
    gold_code       TEXT,
    match_method    TEXT DEFAULT 'auto',
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 17. Daily Sales (aggregated per site per day)
CREATE TABLE IF NOT EXISTS daily_sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_site_name TEXT NOT NULL,
    site_id         TEXT,
    sector_id       TEXT,
    date            TEXT NOT NULL,
    brand           TEXT,
    sales_amt       REAL DEFAULT 0,
    margin          REAL DEFAULT 0,
    source          TEXT DEFAULT 'excel',
    upload_batch_id INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(sales_site_name, date, brand)
);

-- 18. Hourly Sales (per site per hour per day)
CREATE TABLE IF NOT EXISTS hourly_sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sales_site_name TEXT NOT NULL,
    site_id         TEXT,
    sector_id       TEXT,
    date            TEXT NOT NULL,
    hour            INTEGER NOT NULL,
    brand           TEXT,
    sales_amt       REAL DEFAULT 0,
    trans_cnt       INTEGER DEFAULT 0,
    source          TEXT DEFAULT 'excel',
    upload_batch_id INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(sales_site_name, date, hour, brand)
);

-- 20. Diesel Expense Last Year (historical baseline for comparison)
CREATE TABLE IF NOT EXISTS diesel_expense_ly (
    cost_center_code    TEXT PRIMARY KEY,
    sector_id           TEXT,
    cost_center_name    TEXT,
    yearly_expense_mmk_mil REAL,
    daily_avg_expense_mmk  REAL,
    pct_on_sales        REAL
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_daily_ops_site_date ON daily_operations(site_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_ops_date ON daily_operations(date);
CREATE INDEX IF NOT EXISTS idx_fuel_purchases_date ON fuel_purchases(date);
CREATE INDEX IF NOT EXISTS idx_fuel_purchases_sector ON fuel_purchases(sector_id, date);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, is_acknowledged);
CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_site_summary(date);
CREATE INDEX IF NOT EXISTS idx_daily_sales_date ON daily_sales(date);
CREATE INDEX IF NOT EXISTS idx_daily_sales_site ON daily_sales(sales_site_name, date);
CREATE INDEX IF NOT EXISTS idx_hourly_sales_date ON hourly_sales(date);
CREATE INDEX IF NOT EXISTS idx_hourly_sales_site ON hourly_sales(sales_site_name, date);
CREATE INDEX IF NOT EXISTS idx_store_master_sector ON store_master(sector_id);
"""

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Seed sectors if empty
        existing = conn.execute("SELECT COUNT(*) FROM sectors").fetchone()[0]
        if existing == 0:
            from config.settings import SECTORS
            for sid, info in SECTORS.items():
                conn.execute(
                    "INSERT INTO sectors (sector_id, sector_name) VALUES (?, ?)",
                    (sid, info["name"]),
                )
        # Seed super admin from environment variables
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            import hashlib, os
            sa_user = os.environ.get("SUPER_ADMIN_USER", "admin")
            sa_pass = os.environ.get("SUPER_ADMIN_PASS", "admin123")
            sa_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
            sa_hash = hashlib.sha256(sa_pass.encode()).hexdigest()
            conn.execute("""
                INSERT INTO users (username, password_hash, display_name, email, role, created_by)
                VALUES (?, ?, 'Super Admin', ?, 'super_admin', 'system')
            """, (sa_user, sa_hash, sa_email))

        # Migrate: add missing columns to existing tables
        for tbl, col, col_type in [
            ("daily_sales", "site_id", "TEXT"),
            ("hourly_sales", "site_id", "TEXT"),
            ("sites", "cost_center_code", "TEXT"),
            ("sites", "region", "TEXT"),
            ("sites", "business_sector", "TEXT"),
            ("sites", "company", "TEXT"),
            ("sites", "address", "TEXT"),
            ("sites", "address_state", "TEXT"),
            ("sites", "address_township", "TEXT"),
            ("sites", "latitude", "REAL"),
            ("sites", "longitude", "REAL"),
            ("sites", "store_size", "TEXT"),
            ("sites", "channel", "TEXT"),
            ("sites", "manager", "TEXT"),
            ("sites", "gold_code", "TEXT"),
            ("sites", "open_date", "TEXT"),
            ("sites", "closed_date", "TEXT"),
            ("sites", "segment_name", "TEXT"),
            ("sites", "cost_center_description", "TEXT"),
        ]:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if col not in cols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")

        # Create indexes that depend on migrated columns (site_id)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_sales_site_id ON daily_sales(site_id, date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hourly_sales_site_id ON hourly_sales(site_id, date)")

        # Seed diesel expense LY from file if table is empty
        ly_count = conn.execute("SELECT COUNT(*) FROM diesel_expense_ly").fetchone()[0]
        if ly_count == 0:
            _seed_diesel_expense_ly(conn)


def _seed_diesel_expense_ly(conn):
    """Auto-load LY diesel expense data from Excel if file exists."""
    from config.settings import EXCEL_DATA_DIR, PROJECT_ROOT
    # Check multiple locations for the LY file
    candidates = [
        EXCEL_DATA_DIR / "Daily Avg Diesel Expense LY.xlsx",
        PROJECT_ROOT.parent / "Data" / "Daily Avg Diesel Expense LY.xlsx",
    ]
    ly_file = None
    for c in candidates:
        if c.exists():
            ly_file = c
            break
    if ly_file is None:
        return
    try:
        from parsers.diesel_expense_parser import parse_diesel_expense_file
        result = parse_diesel_expense_file(str(ly_file))
        for r in result["records"]:
            conn.execute("""
                INSERT OR REPLACE INTO diesel_expense_ly
                    (cost_center_code, sector_id, cost_center_name,
                     yearly_expense_mmk_mil, daily_avg_expense_mmk, pct_on_sales)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (r["cost_center_code"], r["sector_id"], r["cost_center_name"],
                  r["yearly_expense_mmk_mil"], r["daily_avg_expense_mmk"], r["pct_on_sales"]))
    except Exception:
        pass  # silently skip if file is malformed


# ─── CRUD Helpers ────────────────────────────────────────────────────────────

def upsert_site(conn, site_id, site_name, sector_id, site_type="Regular",
                cost_center_code=None, business_sector=None, company=None, site_code=None):
    conn.execute("""
        INSERT INTO sites (site_id, site_name, sector_id, site_type, cost_center_code, business_sector, company, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_id) DO UPDATE SET
            site_name = excluded.site_name,
            cost_center_code = COALESCE(excluded.cost_center_code, sites.cost_center_code),
            business_sector = COALESCE(excluded.business_sector, sites.business_sector),
            company = COALESCE(excluded.company, sites.company),
            region = COALESCE(excluded.region, sites.region),
            updated_at = datetime('now')
    """, (site_id, site_name, sector_id, site_type, cost_center_code, business_sector, company, site_code))


def enrich_sites_from_store_master(conn):
    """Enrich sites table with store master data (address, lat/long, segment, description, etc.)

    Join: sites.site_id = store_master.cost_center_code (since site_id IS cost_center_code now)
    Also tries: sites.cost_center_code = store_master.cost_center_code (backward compat)
    """
    conn.execute("""
        UPDATE sites SET
            address = COALESCE(sites.address, sm.address),
            address_state = COALESCE(sites.address_state, sm.address_state),
            address_township = COALESCE(sites.address_township, sm.address_township),
            latitude = COALESCE(sites.latitude, sm.latitude),
            longitude = COALESCE(sites.longitude, sm.longitude),
            store_size = COALESCE(sites.store_size, sm.store_size),
            channel = COALESCE(sites.channel, sm.channel),
            gold_code = COALESCE(sites.gold_code, sm.gold_code),
            open_date = COALESCE(sites.open_date, sm.open_date),
            closed_date = COALESCE(sites.closed_date, sm.closed_date),
            segment_name = COALESCE(sites.segment_name, sm.segment_name),
            cost_center_description = COALESCE(sites.cost_center_description, sm.cost_center_name)
        FROM store_master sm
        WHERE (sites.site_id = sm.cost_center_code OR sites.cost_center_code = sm.cost_center_code)
          AND sm.cost_center_code IS NOT NULL
    """)

def upsert_generator(conn, site_id, model_name, model_name_raw, power_kva,
                      consumption_per_hour, fuel_type=None, supplier=None):
    # Check if generator already exists for this site + raw name
    row = conn.execute("""
        SELECT generator_id FROM generators
        WHERE site_id = ? AND model_name_raw = ?
    """, (site_id, model_name_raw)).fetchone()
    if row:
        return row["generator_id"]
    cur = conn.execute("""
        INSERT INTO generators (site_id, model_name, model_name_raw, power_kva,
                                consumption_per_hour, fuel_type, supplier)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (site_id, model_name, model_name_raw, power_kva,
          consumption_per_hour, fuel_type, supplier))
    return cur.lastrowid

def upsert_daily_operation(conn, generator_id, site_id, date, gen_run_hr,
                            daily_used_liters, spare_tank_balance, blackout_hr,
                            source="excel", upload_batch_id=None):
    conn.execute("""
        INSERT INTO daily_operations
            (generator_id, site_id, date, gen_run_hr, daily_used_liters,
             spare_tank_balance, blackout_hr, source, upload_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(generator_id, date) DO UPDATE SET
            gen_run_hr = excluded.gen_run_hr,
            daily_used_liters = excluded.daily_used_liters,
            spare_tank_balance = excluded.spare_tank_balance,
            blackout_hr = excluded.blackout_hr,
            source = excluded.source,
            upload_batch_id = excluded.upload_batch_id
    """, (generator_id, site_id, date, gen_run_hr, daily_used_liters,
          spare_tank_balance, blackout_hr, source, upload_batch_id))

def insert_fuel_purchase(conn, sector_id, date, region, supplier, fuel_type,
                          quantity_liters, price_per_liter, source="excel",
                          upload_batch_id=None):
    conn.execute("""
        INSERT INTO fuel_purchases
            (sector_id, date, region, supplier, fuel_type, quantity_liters,
             price_per_liter, source, upload_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sector_id, date, region, supplier, fuel_type,
          quantity_liters, price_per_liter, source, upload_batch_id))

def refresh_site_summary(conn, site_id, date):
    """Recompute daily_site_summary for a site+date from daily_operations."""
    row = conn.execute("""
        SELECT
            COALESCE(SUM(gen_run_hr), 0) AS total_gen_run_hr,
            COALESCE(SUM(daily_used_liters), 0) AS total_daily_used,
            COALESCE(SUM(spare_tank_balance), 0) AS spare_tank_balance,
            COALESCE(SUM(blackout_hr), 0) AS blackout_hr,
            COUNT(CASE WHEN gen_run_hr > 0 THEN 1 END) AS num_generators_active
        FROM daily_operations
        WHERE site_id = ? AND date = ?
    """, (site_id, date)).fetchone()

    total_used = row["total_daily_used"] or 0
    balance = row["spare_tank_balance"]
    days_of_buffer = None
    if balance is not None and total_used > 0:
        days_of_buffer = round(balance / total_used, 2)

    conn.execute("""
        INSERT INTO daily_site_summary
            (site_id, date, total_gen_run_hr, total_daily_used,
             spare_tank_balance, blackout_hr, days_of_buffer, num_generators_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(site_id, date) DO UPDATE SET
            total_gen_run_hr = excluded.total_gen_run_hr,
            total_daily_used = excluded.total_daily_used,
            spare_tank_balance = excluded.spare_tank_balance,
            blackout_hr = excluded.blackout_hr,
            days_of_buffer = excluded.days_of_buffer,
            num_generators_active = excluded.num_generators_active
    """, (site_id, date, row["total_gen_run_hr"], total_used,
          balance, row["blackout_hr"], days_of_buffer,
          row["num_generators_active"]))

def log_upload(conn, filename, file_type, sector_id, rows_parsed,
               rows_accepted, rows_rejected, date_start, date_end,
               validation_errors=None):
    errors_json = json.dumps(validation_errors) if validation_errors else None
    cur = conn.execute("""
        INSERT INTO upload_history
            (filename, file_type, sector_id, rows_parsed, rows_accepted,
             rows_rejected, date_range_start, date_range_end, validation_errors)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (filename, file_type, sector_id, rows_parsed, rows_accepted,
          rows_rejected, date_start, date_end, errors_json))
    return cur.lastrowid

def upsert_store_master(conn, gold_code, pos_code, store_name, segment_id,
                        segment_name, company_code, legal_entity, channel,
                        address_state, address_township, latitude, longitude,
                        store_size, open_date, closed_date, sector_id,
                        cost_center_code=None, cost_center_name=None):
    conn.execute("""
        INSERT INTO store_master
            (gold_code, pos_code, store_name, cost_center_code, cost_center_name,
             segment_id, segment_name, company_code, legal_entity, channel,
             address_state, address_township, latitude, longitude, store_size,
             open_date, closed_date, sector_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(gold_code) DO UPDATE SET
            store_name = excluded.store_name,
            cost_center_code = COALESCE(excluded.cost_center_code, store_master.cost_center_code),
            cost_center_name = COALESCE(excluded.cost_center_name, store_master.cost_center_name),
            segment_name = excluded.segment_name,
            sector_id = excluded.sector_id
    """, (gold_code, pos_code, store_name, cost_center_code, cost_center_name,
          segment_id, segment_name, company_code, legal_entity, channel,
          address_state, address_township, latitude, longitude, store_size,
          open_date, closed_date, sector_id))


def upsert_daily_sale(conn, sales_site_name, sector_id, date, brand,
                      sales_amt, margin, source="excel", upload_batch_id=None,
                      site_id=None):
    conn.execute("""
        INSERT INTO daily_sales
            (sales_site_name, site_id, sector_id, date, brand, sales_amt, margin,
             source, upload_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sales_site_name, date, brand) DO UPDATE SET
            sales_amt = excluded.sales_amt,
            margin = excluded.margin,
            site_id = COALESCE(excluded.site_id, daily_sales.site_id),
            sector_id = excluded.sector_id,
            source = excluded.source,
            upload_batch_id = excluded.upload_batch_id
    """, (sales_site_name, site_id, sector_id, date, brand, sales_amt, margin,
          source, upload_batch_id))


def upsert_hourly_sale(conn, sales_site_name, sector_id, date, hour, brand,
                       sales_amt, trans_cnt, source="excel", upload_batch_id=None,
                       site_id=None):
    conn.execute("""
        INSERT INTO hourly_sales
            (sales_site_name, site_id, sector_id, date, hour, brand, sales_amt,
             trans_cnt, source, upload_batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sales_site_name, date, hour, brand) DO UPDATE SET
            sales_amt = excluded.sales_amt,
            trans_cnt = excluded.trans_cnt,
            site_id = COALESCE(excluded.site_id, hourly_sales.site_id),
            sector_id = excluded.sector_id,
            source = excluded.source,
            upload_batch_id = excluded.upload_batch_id
    """, (sales_site_name, site_id, sector_id, date, hour, brand, sales_amt,
          trans_cnt, source, upload_batch_id))


def upsert_site_sales_map(conn, sales_site_name, site_id, sector_id,
                          gold_code=None, match_method="auto"):
    conn.execute("""
        INSERT INTO site_sales_map (sales_site_name, site_id, sector_id, gold_code, match_method)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sales_site_name) DO UPDATE SET
            site_id = excluded.site_id,
            sector_id = excluded.sector_id,
            gold_code = excluded.gold_code
    """, (sales_site_name, site_id, sector_id, gold_code, match_method))


def upsert_diesel_expense_ly(conn, cost_center_code, sector_id, cost_center_name,
                              yearly_expense_mmk_mil, daily_avg_expense_mmk, pct_on_sales):
    conn.execute("""
        INSERT INTO diesel_expense_ly (cost_center_code, sector_id, cost_center_name,
                                       yearly_expense_mmk_mil, daily_avg_expense_mmk, pct_on_sales)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(cost_center_code) DO UPDATE SET
            sector_id = excluded.sector_id,
            cost_center_name = excluded.cost_center_name,
            yearly_expense_mmk_mil = excluded.yearly_expense_mmk_mil,
            daily_avg_expense_mmk = excluded.daily_avg_expense_mmk,
            pct_on_sales = excluded.pct_on_sales
    """, (cost_center_code, sector_id, cost_center_name,
          yearly_expense_mmk_mil, daily_avg_expense_mmk, pct_on_sales))


def create_alert(conn, alert_type, severity, message, site_id=None,
                  sector_id=None, metric_value=None, threshold=None):
    conn.execute("""
        INSERT INTO alerts (alert_type, severity, site_id, sector_id,
                            message, metric_value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (alert_type, severity, site_id, sector_id, message,
          metric_value, threshold))

# ─── Settings Helpers ────────────────────────────────────────────────────────

def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')
        """, (key, str(value)))

def get_all_settings(prefix=None):
    with get_db() as conn:
        if prefix:
            rows = conn.execute("SELECT key, value FROM app_settings WHERE key LIKE ?",
                                (f"{prefix}%",)).fetchall()
        else:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}

# ─── Initialize on import ───────────────────────────────────────────────────
init_db()

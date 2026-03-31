"""
CityBCPAgent v1 — SQLite Database Layer (WAL mode)
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

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
    site_id     TEXT PRIMARY KEY,
    site_name   TEXT NOT NULL,
    sector_id   TEXT NOT NULL REFERENCES sectors(sector_id),
    site_type   TEXT DEFAULT 'Regular',
    region      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
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
    uploaded_at         TEXT DEFAULT (datetime('now'))
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

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_daily_ops_site_date ON daily_operations(site_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_ops_date ON daily_operations(date);
CREATE INDEX IF NOT EXISTS idx_fuel_purchases_date ON fuel_purchases(date);
CREATE INDEX IF NOT EXISTS idx_fuel_purchases_sector ON fuel_purchases(sector_id, date);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity, is_acknowledged);
CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_site_summary(date);
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

# ─── CRUD Helpers ────────────────────────────────────────────────────────────

def upsert_site(conn, site_id, site_name, sector_id, site_type="Regular"):
    conn.execute("""
        INSERT INTO sites (site_id, site_name, sector_id, site_type)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(site_id) DO UPDATE SET
            site_name = excluded.site_name,
            updated_at = datetime('now')
    """, (site_id, site_name, sector_id, site_type))

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
            MAX(spare_tank_balance) AS spare_tank_balance,
            MAX(blackout_hr) AS blackout_hr,
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

def create_alert(conn, alert_type, severity, message, site_id=None,
                  sector_id=None, metric_value=None, threshold=None):
    conn.execute("""
        INSERT INTO alerts (alert_type, severity, site_id, sector_id,
                            message, metric_value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (alert_type, severity, site_id, sector_id, message,
          metric_value, threshold))

# ─── Initialize on import ───────────────────────────────────────────────────
init_db()

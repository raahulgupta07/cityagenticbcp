"""Settings router — users, SMTP, recipients, email log, data quality, system."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import pandas as pd

from utils.database import get_db, get_setting, set_setting
from utils.auth import (
    create_user, list_users, update_user, delete_user, hash_password, ROLES,
)
from utils.email_sender import get_smtp_config, send_test_email, send_alert_email, is_email_configured
from alerts.alert_engine import get_active_alerts
from config.settings import SECTORS
from backend.routers.auth import require_super_admin, require_admin

router = APIRouter()


def _df_to_json(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


# ═══════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════

class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str
    email: str = ""
    role: str = "user"
    sectors: List[str] = []


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[int] = None
    sectors: Optional[List[str]] = None


@router.get("/users")
def get_users(user: dict = Depends(require_super_admin)):
    df = list_users()
    return _df_to_json(df)


@router.post("/users")
def create_new_user(req: CreateUserRequest, user: dict = Depends(require_super_admin)):
    if not req.username or not req.password or not req.display_name:
        raise HTTPException(status_code=400, detail="Username, password, and display name are required")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if req.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be admin or user")

    success, error = create_user(
        req.username, req.password, req.display_name, req.email,
        req.role, req.sectors or None, user["username"]
    )
    if not success:
        raise HTTPException(status_code=409, detail=error)
    return {"ok": True, "message": f"User '{req.username}' created"}


@router.put("/users/{user_id}")
def update_existing_user(user_id: int, req: UpdateUserRequest, user: dict = Depends(require_super_admin)):
    kwargs = {}
    if req.display_name is not None:
        kwargs["display_name"] = req.display_name
    if req.email is not None:
        kwargs["email"] = req.email
    if req.role is not None:
        if req.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Role must be admin or user")
        kwargs["role"] = req.role
    if req.password is not None:
        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        kwargs["password"] = req.password
    if req.is_active is not None:
        kwargs["is_active"] = req.is_active
    if req.sectors is not None:
        kwargs["sectors"] = ",".join(req.sectors) if req.sectors else None

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_user(user_id, **kwargs)
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_existing_user(user_id: int, user: dict = Depends(require_super_admin)):
    delete_user(user_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# SMTP / EMAIL SETUP (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════

class SmtpConfigRequest(BaseModel):
    server: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    sender_name: str = "CityBCPAgent"
    sender_email: str = ""
    use_tls: bool = True
    enabled: bool = False
    provider: str = "Custom"


class TestEmailRequest(BaseModel):
    to: str


@router.get("/smtp")
def get_smtp(user: dict = Depends(require_super_admin)):
    config = get_smtp_config()
    # Mask password
    if config.get("password"):
        config["password"] = "••••••••"
    config["provider"] = get_setting("smtp_provider", "Custom")
    config["is_configured"] = is_email_configured()
    return config


@router.put("/smtp")
def save_smtp(req: SmtpConfigRequest, user: dict = Depends(require_super_admin)):
    set_setting("smtp_server", req.server)
    set_setting("smtp_port", str(req.port))
    set_setting("smtp_username", req.username)
    # Only update password if not masked
    if req.password and req.password != "••••••••":
        set_setting("smtp_password", req.password)
    set_setting("smtp_sender_name", req.sender_name)
    set_setting("smtp_sender_email", req.sender_email or req.username)
    set_setting("smtp_use_tls", "true" if req.use_tls else "false")
    set_setting("smtp_enabled", "true" if req.enabled else "false")
    set_setting("smtp_provider", req.provider)
    return {"ok": True, "message": f"Email settings saved. Provider: {req.provider}"}


@router.post("/smtp/test")
def test_smtp(req: TestEmailRequest, user: dict = Depends(require_super_admin)):
    if not req.to:
        raise HTTPException(status_code=400, detail="Email address required")
    ok, err = send_test_email(req.to)
    if ok:
        return {"ok": True, "message": f"Test email sent to {req.to}"}
    raise HTTPException(status_code=500, detail=err or "Failed to send test email")


# ═══════════════════════════════════════════════════════════════════════════
# ALERT RECIPIENTS (Admin + Super Admin)
# ═══════════════════════════════════════════════════════════════════════════

class CreateRecipientRequest(BaseModel):
    name: str
    email: str
    role: str = "Manager"
    sectors: Optional[str] = None
    severity_filter: str = "CRITICAL,WARNING"


@router.get("/recipients")
def get_recipients(user: dict = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM alert_recipients ORDER BY is_active DESC, name"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/recipients")
def create_recipient(req: CreateRecipientRequest, user: dict = Depends(require_admin)):
    if not req.name or not req.email:
        raise HTTPException(status_code=400, detail="Name and email are required")
    with get_db() as conn:
        conn.execute(
            "INSERT INTO alert_recipients (name, email, role, sectors, severity_filter) VALUES (?, ?, ?, ?, ?)",
            (req.name, req.email, req.role, req.sectors, req.severity_filter)
        )
    return {"ok": True, "message": f"Recipient '{req.name}' added"}


@router.put("/recipients/{recipient_id}")
def toggle_recipient(recipient_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        conn.execute(
            "UPDATE alert_recipients SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?",
            (recipient_id,)
        )
    return {"ok": True}


@router.delete("/recipients/{recipient_id}")
def delete_recipient(recipient_id: int, user: dict = Depends(require_admin)):
    with get_db() as conn:
        conn.execute("DELETE FROM alert_recipients WHERE id=?", (recipient_id,))
    return {"ok": True}


@router.post("/alerts/send")
def send_alerts_now(user: dict = Depends(require_admin)):
    if not is_email_configured():
        raise HTTPException(status_code=400, detail="Email not configured. Ask Super Admin to set up SMTP.")
    alerts = get_active_alerts()
    if alerts.empty:
        return {"ok": True, "sent": 0, "message": "No active alerts"}
    sent, errors = send_alert_email(alerts)
    return {"ok": True, "sent": sent, "errors": errors}


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL LOG (Admin + Super Admin)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/email-log")
def get_email_log(user: dict = Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM email_log ORDER BY sent_at DESC LIMIT 50"
        ).fetchall()
        sent_count = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='sent'").fetchone()[0]
        failed_count = conn.execute("SELECT COUNT(*) FROM email_log WHERE status='failed'").fetchone()[0]
    return {
        "logs": [dict(r) for r in rows],
        "sent_count": sent_count,
        "failed_count": failed_count,
    }


# ═══════════════════════════════════════════════════════════════════════════
# DATA QUALITY (Admin + Super Admin)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/data-quality")
def get_data_quality(user: dict = Depends(require_admin)):
    result = {"spec_deviation": [], "reporting_gaps": [], "missing_specs": []}

    with get_db() as conn:
        # Check 1: Generator specs vs actual consumption
        try:
            spec_rows = conn.execute("""
                SELECT g.site_id, s.sector_id, g.model_name, g.power_kva,
                       g.consumption_per_hour as rated,
                       AVG(do.daily_used_liters / NULLIF(do.gen_run_hr, 0)) as actual_per_hr,
                       COUNT(do.date) as data_days
                FROM generators g
                JOIN sites s ON g.site_id = s.site_id
                LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
                    AND do.gen_run_hr > 0 AND do.daily_used_liters > 0
                WHERE g.is_active = 1
                GROUP BY g.generator_id
                HAVING actual_per_hr IS NOT NULL
            """).fetchall()
            for r in spec_rows:
                row = dict(r)
                if row["rated"] and row["rated"] > 0:
                    deviation = round((row["actual_per_hr"] - row["rated"]) / row["rated"] * 100, 1)
                    if abs(deviation) > 20:
                        row["actual_per_hr"] = round(row["actual_per_hr"], 1)
                        row["deviation"] = deviation
                        row["status"] = "HIGH" if abs(deviation) > 50 else "MEDIUM"
                        result["spec_deviation"].append(row)
        except Exception:
            pass

        # Check 2: Reporting gaps
        try:
            gap_rows = conn.execute("""
                SELECT s.site_id, s.sector_id,
                       COUNT(DISTINCT dss.date) as days_reported,
                       MIN(dss.date) as first_report,
                       MAX(dss.date) as last_report
                FROM sites s
                LEFT JOIN daily_site_summary dss ON s.site_id = dss.site_id
                GROUP BY s.site_id
                ORDER BY days_reported ASC
            """).fetchall()
            for r in gap_rows:
                row = dict(r)
                if row["days_reported"] < 3:
                    result["reporting_gaps"].append(row)
        except Exception:
            pass

        # Check 3: Generators missing specs
        try:
            null_rows = conn.execute("""
                SELECT g.site_id, s.sector_id, g.model_name, g.power_kva, g.consumption_per_hour
                FROM generators g
                JOIN sites s ON g.site_id = s.site_id
                WHERE g.is_active = 1 AND (g.consumption_per_hour IS NULL OR g.consumption_per_hour = 0)
            """).fetchall()
            result["missing_specs"] = [dict(r) for r in null_rows]
        except Exception:
            pass

    return result


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM (Super Admin only)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/system/stats")
def get_system_stats(user: dict = Depends(require_super_admin)):
    tables = {}
    table_names = [
        "users", "sectors", "sites", "generators", "daily_operations",
        "fuel_purchases", "daily_site_summary", "alerts",
        "alert_recipients", "email_log", "ai_insights_cache", "app_settings", "upload_history"
    ]
    with get_db() as conn:
        for t in table_names:
            try:
                tables[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                tables[t] = 0
    return tables


# ═══════════════════════════════════════════════════════════════════════════
# FORMULA ENGINE (Admin + Super Admin)
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_FORMULAS = {
    "lookback_days": 3,
    "rolling_window": 3,
    "buffer_target_days": 7,
    "formulas": {
        "buffer": {"numerator": "last_day_tank", "denominator": "avg_burn", "days": 3},
        "blackout": {"method": "avg", "field": "blackout_hr", "days": 3},
        "burn": {"method": "avg", "field": "daily_used", "days": 3},
        "cost": {"burn": "avg_burn", "price": "latest_price"},
        "exp_pct": {"cost": "diesel_cost", "sales": "avg_sales", "days": 3},
        "efficiency": {"numerator": "total_used", "denominator": "total_gen_hr"},
        "needed": {"target_days": 7, "burn": "avg_burn", "tank": "last_day_tank"},
        "variance": {"actual": "actual_used", "expected": "gen_hr * rated_lhr"},
    },
    "thresholds": {
        "buffer_critical": 3,
        "buffer_warning": 7,
        "exp_open": 5,
        "exp_monitor": 15,
        "exp_reduce": 30,
        "exp_close": 60,
    },
    "heatmap": {
        "price": [3500, 5000, 8000],
        "blackout": [4, 8, 12],
        "exp_pct": [0.9, 1.5, 3],
        "buffer": [7, 5, 3],
    },
}


@router.get("/formulas")
def get_formulas(user: dict = Depends(require_admin)):
    import json
    raw = get_setting("formula_engine", None)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return DEFAULT_FORMULAS


@router.put("/formulas")
def save_formulas(body: dict, user: dict = Depends(require_admin)):
    import json
    set_setting("formula_engine", json.dumps(body))
    return {"ok": True, "message": "Formula settings saved"}


@router.post("/formulas/reset")
def reset_formulas(user: dict = Depends(require_admin)):
    import json
    set_setting("formula_engine", json.dumps(DEFAULT_FORMULAS))
    return {"ok": True, "message": "Formulas reset to defaults"}


@router.post("/system/clear/{target}")
def clear_system_data(target: str, user: dict = Depends(require_super_admin)):
    allowed = {
        "ai_cache": "DELETE FROM ai_insights_cache",
        "alerts": "DELETE FROM alerts",
        "email_log": "DELETE FROM email_log",
    }
    if target not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid target. Allowed: {', '.join(allowed.keys())}")
    with get_db() as conn:
        conn.execute(allowed[target])
    return {"ok": True, "message": f"Cleared {target}"}

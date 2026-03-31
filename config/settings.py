"""
CityBCPAgent v1 — Configuration & Settings
"""
import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "bcp.db"
UPLOADS_DIR = DATA_DIR / "uploads"
# Excel data: check local Data/ first (Docker), then ../Data (local dev)
_local_data = PROJECT_ROOT / "Data"
_parent_data = PROJECT_ROOT.parent / "Data"
EXCEL_DATA_DIR = _local_data if _local_data.exists() else _parent_data

# ─── Sectors ─────────────────────────────────────────────────────────────────
SECTORS = {
    "CP": {
        "name": "City Pharmacy",
        "color": "#2196F3",
        "has_blackout_data": True,
    },
    "CMHL": {
        "name": "City Mart Holdings Ltd",
        "color": "#FF9800",
        "has_blackout_data": False,  # CMHL sheets lack blackout hr column
    },
    "CFC": {
        "name": "City Food Chain (Factory)",
        "color": "#4CAF50",
        "has_blackout_data": True,
    },
    "PG": {
        "name": "PG Sector",
        "color": "#9C27B0",
        "has_blackout_data": False,
    },
}

# ─── Suppliers ───────────────────────────────────────────────────────────────
SUPPLIERS = ["Denko", "Moon Sun"]

# ─── Fuel Types ──────────────────────────────────────────────────────────────
FUEL_TYPES = ["PD", "HSD"]

# ─── Regions ─────────────────────────────────────────────────────────────────
REGIONS = ["YGN", "MDY"]

# ─── Excel File Mapping ─────────────────────────────────────────────────────
EXCEL_FILES = {
    "blackout_cp": {
        "filename": "Blackout Hr_ CP.xlsx",
        "sheet": "CP",
        "sector_id": "CP",
        "site_col_name": "Center Name",
    },
    "blackout_cmhl": {
        "filename": "Blackout Hr_ CMHL.xlsx",
        "sheet": "CMHL",
        "sector_id": "CMHL",
        "site_col_name": "Location",
    },
    "blackout_cfc": {
        "filename": "Blackout Hr_ CFC.xlsx",
        "sheet": "CFC",
        "sector_id": "CFC",
        "site_col_name": "Store Name",
    },
    "fuel_price": {
        "filename": "Daily Fuel Price.xlsx",
        "sheets": ["CMHL", "CP", "CFC", "PG"],
    },
}

# ─── Validation Thresholds ───────────────────────────────────────────────────
VALIDATION = {
    "gen_run_hr": {"min": 0, "max": 24, "action": "reject"},
    "daily_used_liters": {"min": 0, "max": 5000, "warn_above": 2000},
    "spare_tank_balance": {"min": 0, "max": 50000, "warn_above": 20000},
    "blackout_hr": {"min": 0, "max": 24, "action": "reject"},
    "price_per_liter": {"min": 1000, "max": 20000},
    "quantity_liters": {"min": 0, "max": 50000, "warn_above": 20000},
}

# ─── Alert Thresholds ───────────────────────────────────────────────────────
ALERTS = {
    "buffer_critical_days": 3,
    "buffer_warning_days": 7,
    "price_spike_pct": 10,
    "price_surge_pct": 20,
    "high_blackout_hr": 8,
    "generator_idle_days": 3,
    "efficiency_high": 1.5,
    "efficiency_low": 0.5,
    "missing_data_days": 2,
    "sector_buffer_low_days": 5,
    "predicted_stockout_days": 5,
}

# ─── BCP Score Weights ──────────────────────────────────────────────────────
BCP_WEIGHTS = {
    "fuel_reserve": 0.35,
    "generator_coverage": 0.30,
    "power_capacity": 0.20,
    "operational_resilience": 0.15,
}

BCP_GRADES = {
    "A": {"min": 80, "label": "RESILIENT", "color": "#16a34a"},
    "B": {"min": 60, "label": "ADEQUATE", "color": "#2196F3"},
    "C": {"min": 40, "label": "AT RISK", "color": "#d97706"},
    "D": {"min": 20, "label": "VULNERABLE", "color": "#ea580c"},
    "F": {"min": 0, "label": "CRITICAL", "color": "#dc2626"},
}

# ─── Dashboard ───────────────────────────────────────────────────────────────
DASHBOARD = {
    "page_title": "City BCP Agent",
    "page_icon": "🛡️",
    "layout": "wide",
    "theme_primary": "#1976D2",
    "theme_secondary": "#FF6F00",
}

# ─── Agent Config ────────────────────────────────────────────────────────────
AGENT_CONFIG = {
    "enabled": os.environ.get("BCP_AGENT_ENABLED", "true").lower() == "true",
    "api_key_env": "OPENROUTER_API_KEY",
    "models": {
        "reasoning": "anthropic/claude-haiku-4.5",
        "fast": "anthropic/claude-haiku-4.5",
    },
    "max_turns": 10,
    "max_tokens": 4096,
    "temperature": 0.3,
}

"""
CityBCPAgent v1 — Configuration & Settings
"""
import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "db"
DB_PATH = DATA_DIR / "bcp.db"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
# Excel data: check local Data/ first (Docker), then ../Data (local dev)
_local_data = PROJECT_ROOT / "Data"
_parent_data = PROJECT_ROOT.parent / "Data"
EXCEL_DATA_DIR = _local_data if _local_data.exists() else _parent_data

# ─── Sectors ─────────────────────────────────────────────────────────────────
SECTORS = {
    "CP": {
        "name": "City Properties",
        "color": "#2196F3",
        "has_blackout_data": True,
    },
    "CMHL": {
        "name": "City Mart Holdings Ltd",
        "color": "#FF9800",
        "has_blackout_data": True,
    },
    "CFC": {
        "name": "City Food Concept",
        "color": "#4CAF50",
        "has_blackout_data": True,
    },
    "PG": {
        "name": "PG Sector",
        "color": "#9C27B0",
        "has_blackout_data": True,
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
    "blackout_pg": {
        "filename": "Blackout Hr_ PG.xlsx",
        "sheet": "PG",
        "sector_id": "PG",
        "site_col_name": "Site",
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

# ─── Energy Cost vs Sales Thresholds ──────────────────────────────────────
ENERGY_COST = {
    "healthy_pct": 5,       # < 5% of sales = green
    "warning_pct": 15,      # 5-15% = yellow
    "critical_pct": 30,     # 15-30% = red
    "close_pct": 60,        # > 60% = recommend CLOSE (losing money)
}

# ─── Heat Map Thresholds (4-color: Green / Yellow / Amber / Red) ─────────
HEATMAP_THRESHOLDS = {
    "diesel_price": {
        "label": "Diesel Price (MMK/L)",
        "green_max": 3500,      # < 3,501 = green
        "yellow_max": 5000,     # 3,501–5,000 = yellow
        "amber_max": 8000,      # 5,001–8,000 = amber
        # > 8,000 = red
        "reverse": False,       # higher = worse
    },
    "blackout_hr": {
        "label": "Blackout Hr",
        "green_max": 4,         # < 4 = green
        "yellow_max": 8,        # 4–8 = yellow
        "amber_max": 12,        # 8–12 = amber
        # > 12 = red
        "reverse": False,
    },
    "expense_pct": {
        "label": "Expense % on Sale",
        "green_max": 0.9,       # < 0.9% = green
        "yellow_max": 1.5,      # 0.9–1.5% = yellow
        "amber_max": 3.0,       # 1.5–3% = amber
        # > 3% = red
        "reverse": False,
    },
    "buffer_days": {
        "label": "Buffer Stock Days",
        "green_min": 7,         # >= 7 = green
        "yellow_min": 5,        # 5–7 = yellow
        "amber_min": 3,         # 3–5 = amber
        # < 3 = red
        "reverse": True,        # lower = worse (opposite of others)
    },
}

HEATMAP_COLORS = {
    "green":  "#22c55e",
    "yellow": "#eab308",
    "amber":  "#f97316",
    "red":    "#ef4444",
    "gray":   "#9ca3af",   # no data
}

# ─── Energy Decision Matrix (sector-level store open/close thresholds) ────
ENERGY_DECISION = {
    "full_max_pct": 5,       # <5% = FULL OPERATIONS
    "monitor_max_pct": 15,   # 5-15% = MONITOR
    "reduce_max_pct": 30,    # 15-30% = REDUCE HOURS
    "critical_max_pct": 60,  # 30-60% = CRITICAL
    # >60% = CLOSE RECOMMENDATION
}

# ─── Segment → Sector Mapping (storemaster segments to BCP sectors) ──────
SEGMENT_SECTOR_MAP = {
    "City Care": "CP",
    "City Express Convenience Store": "CP",
    "City Express Convinence Store": "CP",  # typo variant in data
    "City Express Franchise Stores": "CP",
    "City Mart": "CMHL",
    "Ocean": "CMHL",
    "Market Place": "CMHL",
    "miniCityMart (MNC)": "CMHL",
    "City Baby Club": "CMHL",
    "City Book & Music": "CMHL",
    "Popular": "CMHL",
    "Safari": "CMHL",
    "E COMMERCE": "CMHL",
    "Canteen": "CFC",
}

# ─── Brand → Sector Mapping (sales brand names to BCP sectors) ───────────
BRAND_SECTOR_MAP = {
    "CITY CARE": "CP",
    "CITY EXPRESS": "CP",
    "CE FRANCHISE": "CP",
    "YGN CITY EXPRESS": "CP",
    "CITYMART": "CMHL",
    "OCEAN": "CMHL",
    "E COMMERCE OCEAN": "CMHL",
    "CITY BABY CLUB": "CMHL",
    "CITY BOOKS AND MUSIC": "CMHL",
    "MARKET PLACE": "CMHL",
    "MINI CITY MART": "CMHL",
    "SAFARI": "CMHL",
    "POPULAR": "CMHL",
    "CANTEEN": "CFC",
}

# ─── Sales Excel File Config ─────────────────────────────────────────────
SALES_FILES = {
    "daily_sales": {
        "sheet": "daily sales",
        "cols": {
            "date": "SALES_DATE",
            "site": "Site Name",
            "brand": "Brand",
            "amount": "SALES_AMT",
            "margin": "MARGIN",
        },
    },
    "hourly_sales": {
        "sheet": "hourly sales",
        "cols": {
            "date": "DocumentDate",
            "site": "Site Name",
            "brand": "Brand",
            "hour": "SALES_HR",
            "amount": "SALES_AMT",
            "trans_cnt": "TRANS_CNT",
        },
    },
    "store_master": {
        "sheet": "STORE MASTER",
    },
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
        "reasoning": "google/gemini-3.1-flash-lite-preview",
        "fast": "google/gemini-3.1-flash-lite-preview",
        "insight": "google/gemini-3.1-flash-lite-preview",
    },
    "max_turns": 10,
    "max_tokens": 4096,
    "temperature": 0.3,
}

"""
Page 0: Raw Data Browser -- View all data tables in the system
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db

st.set_page_config(page_title="Raw Data", page_icon="🗄️", layout="wide")
st.title("🗄️ Raw Data Browser")

ui.alert(
    title="🗄️ Database Browser",
    description="Browse all raw data tables stored in the system. Data was imported from 4 Excel files: 3 Blackout Hour files (CP, CMHL, CFC) and 1 Daily Fuel Price file.",
    key="alert_raw",
)

# ─── Table definitions ───────────────────────────────────────────────────────
TABLES = {
    "Sites": """
        SELECT s.site_id, s.sector_id, s.site_type, s.site_name
        FROM sites s
        ORDER BY sector_id, site_id
    """,
    "Generators": """
        SELECT g.generator_id, g.site_id, s.sector_id, g.model_name,
               g.model_name_raw, g.power_kva, g.consumption_per_hour,
               g.fuel_type, g.supplier
        FROM generators g
        JOIN sites s ON g.site_id = s.site_id
        ORDER BY s.sector_id, g.site_id, g.model_name
    """,
    "Daily Ops": """
        SELECT do.date, do.site_id, s.sector_id, g.model_name,
               do.gen_run_hr, do.daily_used_liters, do.spare_tank_balance,
               do.blackout_hr, do.source
        FROM daily_operations do
        JOIN generators g ON do.generator_id = g.generator_id
        JOIN sites s ON do.site_id = s.site_id
        ORDER BY do.date DESC, do.site_id
        LIMIT 500
    """,
    "Site Summary": """
        SELECT dss.date, dss.site_id, s.sector_id,
               dss.total_gen_run_hr, dss.total_daily_used,
               dss.spare_tank_balance, dss.blackout_hr,
               dss.days_of_buffer, dss.num_generators_active
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        ORDER BY dss.date DESC, dss.site_id
        LIMIT 500
    """,
    "Fuel Purchases": """
        SELECT * FROM fuel_purchases
        ORDER BY date DESC
        LIMIT 200
    """,
    "Alerts": """
        SELECT * FROM alerts
        ORDER BY created_at DESC
        LIMIT 200
    """,
    "Incidents": """
        SELECT * FROM incidents
        ORDER BY created_at DESC
        LIMIT 100
    """,
    "Uploads": """
        SELECT * FROM upload_history
        ORDER BY uploaded_at DESC
    """,
    "Name Map": """
        SELECT * FROM generator_name_map
        ORDER BY raw_name
    """,
}

TABLE_DESCRIPTIONS = {
    "Sites": "57 sites across 3 sectors (CP: 25, CMHL: 30, CFC: 2)",
    "Generators": "86 generators with model, KVA, consumption rate",
    "Daily Ops": "Per-generator per-day: run hours, fuel used, tank balance, blackout hours",
    "Site Summary": "Aggregated per-site per-day: totals, buffer days calculation",
    "Fuel Purchases": "Diesel purchase prices from Denko & Moon Sun suppliers",
    "Alerts": "Auto-generated alerts for buffer, price, blackout, efficiency thresholds",
    "Incidents": "Logged incidents and events",
    "Uploads": "History of file uploads and data imports",
    "Name Map": "Generator raw name to standardized name mapping",
}

# ─── Load all tables ─────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def load_table(query):
    try:
        with get_db() as conn:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        return pd.DataFrame({"Error": [str(e)]})


# ─── Tabs ────────────────────────────────────────────────────────────────────
tab_names = list(TABLES.keys())
selected_table = ui.tabs(
    options=tab_names,
    default_value="Sites",
    key="table_tabs",
)

# Get the query for the selected table
query = TABLES.get(selected_table, TABLES["Sites"])
df = load_table(query)

# Row count metric
ui.metric_card(
    title=f"{selected_table} Rows",
    content=str(len(df)),
    description=TABLE_DESCRIPTIONS.get(selected_table, ""),
    key=f"metric_{selected_table}",
)

# Search / filter
search = st.text_input(
    "Filter rows (searches all columns)",
    key=f"search_{selected_table}",
    placeholder="Type to filter...",
)

if search and not df.empty:
    mask = df.astype(str).apply(
        lambda col: col.str.contains(search, case=False, na=False)
    ).any(axis=1)
    filtered_df = df[mask]
else:
    filtered_df = df

if filtered_df.empty:
    st.info("No data found." if not search else "No rows match the filter.")
else:
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

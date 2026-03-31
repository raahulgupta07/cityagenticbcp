"""
Page 5: Power Backup Monitor — Track generator usage as a proxy for blackout events
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.charts import bar_chart, multi_line, horizontal_bar, apply_layout, STATUS_COLORS
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary
from config.settings import SECTORS, ALERTS

from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
st.set_page_config(page_title="Power Backup Monitor", page_icon="⚡", layout="wide")
require_login()
render_sidebar_user()

render_page_header("⚡", "Power Backup Monitor", "Generator run hours as backup power indicator — higher hours = more grid outages")

ui.alert(
    title="🔌 Power Backup Monitor",
    description="Blackout hours are rarely recorded numerically in the Excel files (most entries are text notes like 'G1 test run' or '66kV system breakdown'). Generator run hours are the best indicator of when backup power was needed. Higher gen run hours = more time on backup power = likely grid outage.",
    key="alert_blackout",
)

# ─── Load all sectors (not just blackout-capable) ────────────────────────────
with get_db() as conn:
    available = [r[0] for r in conn.execute(
        "SELECT DISTINCT sector_id FROM sites ORDER BY sector_id"
    ).fetchall()]

if not available:
    st.info("No sectors found in the database.")
    st.stop()

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_backup_data(sector_id):
    with get_db() as conn:
        all_data = pd.read_sql_query("""
            SELECT dss.site_id, dss.date, dss.blackout_hr,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE s.sector_id = ?
            ORDER BY dss.date, dss.site_id
        """, conn, params=(sector_id,))

        # Check for any text warnings/notes in the raw data
        warnings = pd.read_sql_query("""
            SELECT DISTINCT wi.field_name, wi.original_value, wi.site_id, wi.date
            FROM warnings_ingestion wi
            JOIN sites s ON wi.site_id = s.site_id
            WHERE s.sector_id = ?
              AND (wi.field_name LIKE '%blackout%' OR wi.field_name LIKE '%remark%'
                   OR wi.field_name LIKE '%note%' OR wi.field_name LIKE '%warning%')
            ORDER BY wi.date DESC
            LIMIT 20
        """, conn, params=(sector_id,))

    return all_data, warnings

@st.cache_data(ttl=300)
def load_backup_data_no_warnings(sector_id):
    """Fallback if warnings_ingestion table doesn't exist."""
    with get_db() as conn:
        all_data = pd.read_sql_query("""
            SELECT dss.site_id, dss.date, dss.blackout_hr,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE s.sector_id = ?
            ORDER BY dss.date, dss.site_id
        """, conn, params=(sector_id,))
    return all_data, pd.DataFrame()


# ─── Page-level AI Summary ───────────────────────────────────────────────────
render_page_summary("Power Backup Monitor", {"sectors_monitored": available})

# ─── Sector Tabs ─────────────────────────────────────────────────────────────
selected = ui.tabs(options=available, default_value=available[0], key="blackout_tabs")

# Find which sector is selected
sector = selected if selected in available else available[0]

try:
    all_data_df, warnings_df = load_backup_data(sector)
except Exception:
    all_data_df, warnings_df = load_backup_data_no_warnings(sector)

if all_data_df.empty:
    st.info(f"No data available for {sector}.")
    st.stop()

# ─── KPI Cards ───────────────────────────────────────────────────────────────
st.markdown("### Power Backup Summary")
st.caption("Generator run hours indicate when backup power was needed. Higher hours suggest the site experienced grid power issues.")

total_gen_hr = all_data_df["total_gen_run_hr"].sum()
sites_count = all_data_df["site_id"].nunique()
avg_gen_hr = all_data_df.groupby("site_id")["total_gen_run_hr"].sum().mean()
total_fuel_for_backup = all_data_df["total_daily_used"].sum()

# Find site with highest generator usage
site_gen_totals = all_data_df.groupby("site_id")["total_gen_run_hr"].sum().sort_values(ascending=False)
top_site = site_gen_totals.index[0] if not site_gen_totals.empty else "N/A"
top_site_hrs = site_gen_totals.iloc[0] if not site_gen_totals.empty else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.metric_card(
        title="Total Gen Run Hours",
        content=f"{total_gen_hr:,.1f}",
        description="Total hours generators ran (backup power)",
        key=f"metric_total_gen_{sector}",
    )
with c2:
    ui.metric_card(
        title="Sites Monitored",
        content=str(sites_count),
        description=f"Sites in {sector}",
        key=f"metric_sites_{sector}",
    )
with c3:
    ui.metric_card(
        title="Avg Gen Hr/Site",
        content=f"{avg_gen_hr:,.1f}",
        description="Average total gen hours per site",
        key=f"metric_avg_gen_{sector}",
    )
with c4:
    ui.metric_card(
        title=f"Highest Usage: {top_site}",
        content=f"{top_site_hrs:,.1f} hrs",
        description="Site with most generator usage",
        key=f"metric_top_site_{sector}",
    )

# Check if any actual numeric blackout data exists
has_numeric_blackout = (
    all_data_df["blackout_hr"].notna().sum() > 0
    and all_data_df["blackout_hr"].sum() > 0
)

if has_numeric_blackout:
    ui.badges(
        badge_list=[
            ("Numeric blackout data available", "default"),
            (f"Total blackout hrs: {all_data_df['blackout_hr'].sum():,.1f}", "destructive"),
        ],
        key=f"badges_blackout_avail_{sector}",
    )
else:
    ui.badges(
        badge_list=[
            ("No numeric blackout hours recorded", "outline"),
            ("Using generator run hours as proxy", "default"),
        ],
        key=f"badges_blackout_avail_{sector}",
    )

st.markdown("---")

# ─── Chart 1: Generator Run Hours Trend ──────────────────────────────────────
st.markdown("### Generator Run Hours Trend")
st.caption("This chart shows total generator run hours per day. Spikes indicate days when backup power was heavily used, likely due to grid outages.")

daily_gen = all_data_df.groupby("date", as_index=False)["total_gen_run_hr"].sum()
daily_gen["total_gen_run_hr"] = daily_gen["total_gen_run_hr"].round(1)

if not daily_gen.empty:
    fig1 = bar_chart(daily_gen, "date", "total_gen_run_hr",
                      title="Daily Total Generator Run Hours")
    st.plotly_chart(fig1, use_container_width=True, key=f"gen_trend_chart_{sector}")
    render_insight_panel(
        f"Generator run hours trend for {sector} (proxy for power outages)",
        daily_gen,
        f"gen_trend_{sector}",
    )

# ─── Chart 2: Sites with Highest Generator Usage ────────────────────────────
st.markdown("### Sites with Highest Generator Usage")
st.caption("Sites that use generators the most are likely experiencing the most frequent or longest power outages. These sites should be prioritized for grid reliability improvements.")

site_gen = all_data_df.groupby("site_id", as_index=False)["total_gen_run_hr"].sum()
site_gen = site_gen.sort_values("total_gen_run_hr", ascending=True)
top_n = min(15, len(site_gen))
site_gen_top = site_gen.tail(top_n)

if not site_gen_top.empty:
    # Color by usage level
    high_threshold = site_gen_top["total_gen_run_hr"].quantile(0.75)
    med_threshold = site_gen_top["total_gen_run_hr"].quantile(0.5)
    site_gen_top["Usage Level"] = site_gen_top["total_gen_run_hr"].apply(
        lambda x: "CRITICAL" if x >= high_threshold else "WARNING" if x >= med_threshold else "HEALTHY"
    )
    fig2 = horizontal_bar(site_gen_top, "total_gen_run_hr", "site_id", "Usage Level", STATUS_COLORS,
                           title=f"Top {top_n} Sites by Generator Run Hours")
    st.plotly_chart(fig2, use_container_width=True, key=f"site_gen_chart_{sector}")
    render_insight_panel(
        f"Sites with highest generator usage in {sector} (higher = more backup power needed)",
        site_gen_top[["site_id", "total_gen_run_hr"]],
        f"site_gen_{sector}",
    )

# ─── Chart 3: Gen Run Hours per Site Over Time ──────────────────────────────
st.markdown("### Generator Run Hours per Site Over Time")
st.caption("This shows how each site's generator usage changed over time. Look for sites with increasing trends -- they may be facing worsening power reliability.")

# Pick top 5 sites by total gen hours for readability
top5_sites = site_gen_totals.head(5).index.tolist() if len(site_gen_totals) >= 1 else []
if top5_sites:
    site_trend_df = all_data_df[all_data_df["site_id"].isin(top5_sites)].copy()
    site_daily = site_trend_df.groupby(["date", "site_id"], as_index=False)["total_gen_run_hr"].sum()
    site_daily["total_gen_run_hr"] = site_daily["total_gen_run_hr"].round(1)
    if not site_daily.empty:
        fig3 = multi_line(site_daily, "date", "total_gen_run_hr", "site_id",
                           title="Gen Run Hours Trend (Top 5 Sites)")
        st.plotly_chart(fig3, use_container_width=True, key=f"site_trend_chart_{sector}")
        render_insight_panel(
            f"Generator run hours trend for top 5 sites in {sector}",
            site_daily,
            f"site_trend_{sector}",
        )

# ─── Smart Table: Site Backup Power Summary ──────────────────────────────────
st.markdown("### Site Backup Power Summary")
st.caption("Complete breakdown per site showing total generator hours, fuel used for backup, and current buffer days.")

site_summary = all_data_df.groupby("site_id", as_index=False).agg(
    total_gen_hr=("total_gen_run_hr", "sum"),
    total_fuel_used=("total_daily_used", "sum"),
    avg_buffer=("days_of_buffer", "mean"),
    reporting_days=("date", "nunique"),
).round(1)
site_summary = site_summary.sort_values("total_gen_hr", ascending=False)
site_summary.columns = ["Site", "Total Gen Hr", "Total Fuel Used (L)", "Avg Buffer Days", "Reporting Days"]
site_summary["Status"] = site_summary["Total Gen Hr"].apply(
    lambda x: "CRITICAL" if x > site_summary["Total Gen Hr"].quantile(0.75) else
              "WARNING" if x > site_summary["Total Gen Hr"].quantile(0.5) else "HEALTHY"
)

render_smart_table(
    site_summary, title="Site Backup Power Usage",
    severity_col="Status",
    highlight_cols={
        "Total Gen Hr": {"good": "low", "thresholds": [50, 100]},
        "Avg Buffer Days": {"good": "high", "thresholds": [7, 3]},
    },
)
render_insight_panel(
    f"Site backup power summary for {sector}",
    site_summary,
    f"backup_table_{sector}",
)

# ─── Text Notes/Warnings from Excel ─────────────────────────────────────────
if not warnings_df.empty:
    st.markdown("---")
    st.markdown("### Blackout Notes from Excel Files")
    st.caption("These are the text entries found in blackout-related columns. They describe specific events like equipment tests or grid failures.")
    render_smart_table(warnings_df, title="Blackout Notes")
    render_insight_panel(
        f"Blackout text notes for {sector}",
        warnings_df,
        f"blackout_notes_{sector}",
    )


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

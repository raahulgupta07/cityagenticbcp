"""
Page 4: Fuel Buffer & Stockout Risk -- Identify sites at risk of fuel stockout
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.charts import horizontal_bar, heatmap, STATUS_COLORS
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary
from config.settings import SECTORS, ALERTS

from utils.auth import require_login, render_sidebar_user
st.set_page_config(page_title="Buffer & Stockout Risk", page_icon="🔋", layout="wide")
require_login()
render_sidebar_user()

st.title("🔋 Fuel Buffer & Stockout Risk")

ui.alert(
    title="🛢️ Buffer & Stockout Risk",
    description="Days of Buffer = Spare Tank Balance (L) / Daily Fuel Consumption (L). Critical: <3 days (immediate resupply needed). Warning: <7 days (plan resupply). Sites are ranked by urgency.",
    key="alert_buffer",
)

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_buffer_data():
    with get_db() as conn:
        sectors = [r[0] for r in conn.execute(
            "SELECT DISTINCT sector_id FROM sites ORDER BY sector_id"
        ).fetchall()]

        latest = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.days_of_buffer, dss.total_daily_used,
                   dss.spare_tank_balance, dss.num_generators_active
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT MAX(d2.date) FROM daily_site_summary d2
                              WHERE d2.site_id = dss.site_id)
            ORDER BY dss.days_of_buffer ASC
        """, conn)

        ts = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.date, dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            ORDER BY dss.date, dss.site_id
        """, conn)

    return sectors, latest, ts

all_sectors, all_latest_df, all_ts_df = load_buffer_data()

if not all_sectors:
    st.info("No site data available.")
    st.stop()

if all_latest_df.empty:
    st.info("No buffer data available.")
    st.stop()

# ─── Page-level AI Summary ───────────────────────────────────────────────────
crit_days = ALERTS["buffer_critical_days"]
warn_days = ALERTS["buffer_warning_days"]

kpi_dict = {
    "total_sites": len(all_latest_df),
    "critical_count": int(len(all_latest_df[all_latest_df["days_of_buffer"].fillna(0) < crit_days])),
    "avg_buffer": float(all_latest_df["days_of_buffer"].fillna(0).mean()),
}
render_page_summary("Buffer & Stockout Risk", kpi_dict)

# ─── Sector Tabs ─────────────────────────────────────────────────────────────
selected = ui.tabs(
    options=["All"] + all_sectors,
    default_value="All",
    key="buffer_tabs",
)

if selected == "All":
    sector_filter = None
    tab_key = "buffer_all"
else:
    sector_filter = selected
    tab_key = f"buffer_{selected}"


def render_buffer_content(sector_filter, tab_key):
    """Render buffer risk content for a sector filter."""
    if sector_filter is None:
        latest_df = all_latest_df.copy()
        ts_df = all_ts_df.copy()
    else:
        latest_df = all_latest_df[all_latest_df["sector_id"] == sector_filter].copy()
        ts_df = all_ts_df[all_ts_df["sector_id"] == sector_filter].copy()

    if latest_df.empty:
        st.info(f"No buffer data available for {sector_filter or 'any sector'}.")
        return

    # ─── KPI Cards ───────────────────────────────────────────────────────
    st.markdown("### Buffer Status Summary")
    critical_count = len(latest_df[latest_df["days_of_buffer"].fillna(0) < crit_days])
    warning_count = len(latest_df[
        (latest_df["days_of_buffer"].fillna(0) >= crit_days) &
        (latest_df["days_of_buffer"].fillna(0) < warn_days)
    ])
    healthy_count = len(latest_df[latest_df["days_of_buffer"].fillna(0) >= warn_days])

    kc1, kc2, kc3 = st.columns(3)
    with kc1:
        ui.metric_card(
            title=f"CRITICAL (< {crit_days} Days)",
            content=str(critical_count),
            description="Immediate resupply needed",
            key=f"metric_critical_{tab_key}",
        )
    with kc2:
        ui.metric_card(
            title=f"WARNING ({crit_days}-{warn_days} Days)",
            content=str(warning_count),
            description="Plan resupply soon",
            key=f"metric_warning_{tab_key}",
        )
    with kc3:
        ui.metric_card(
            title=f"HEALTHY (> {warn_days} Days)",
            content=str(healthy_count),
            description="Sufficient buffer",
            key=f"metric_healthy_{tab_key}",
        )

    ui.badges(
        badge_list=[
            (f"{critical_count} critical", "destructive"),
            (f"{warning_count} warning", "outline"),
            (f"{healthy_count} healthy", "default"),
        ],
        key=f"status_badges_{tab_key}",
    )

    st.markdown("---")

    # ─── Chart 1: Days of Buffer by Site (Horizontal Bar) ────────────────
    st.markdown("### Days of Buffer by Site (Most Critical First)")
    bar_df = latest_df[["site_id", "days_of_buffer"]].copy()
    bar_df["days_of_buffer"] = bar_df["days_of_buffer"].fillna(0)
    bar_df = bar_df.sort_values("days_of_buffer", ascending=True)
    bar_df["Status"] = bar_df["days_of_buffer"].apply(
        lambda x: "CRITICAL" if x < crit_days else "WARNING" if x < warn_days else "HEALTHY"
    )

    fig1 = horizontal_bar(bar_df, "days_of_buffer", "site_id", "Status", STATUS_COLORS,
                           title="Days of Buffer by Site")
    st.plotly_chart(fig1, use_container_width=True, key=f"buffer_bar_chart_{tab_key}")
    render_insight_panel(
        f"Buffer days by site{' for ' + sector_filter if sector_filter else ''}",
        bar_df,
        f"buffer_bar_{tab_key}",
    )

    # ─── Chart 2: Heatmap — Buffer over Time ────────────────────────────
    st.markdown("### Buffer Heatmap (Date vs Site)")
    if not ts_df.empty:
        pivot = ts_df.pivot_table(index="site_id", columns="date", values="days_of_buffer",
                                   aggfunc="mean")
        pivot = pivot.loc[pivot.mean(axis=1).sort_values().index]

        fig2 = heatmap(pivot, title="Days of Buffer Over Time", colorscale="RdYlGn")
        st.plotly_chart(fig2, use_container_width=True, key=f"buffer_heatmap_chart_{tab_key}")
        render_insight_panel(
            f"Buffer heatmap over time{' for ' + sector_filter if sector_filter else ''}",
            bar_df[["site_id", "days_of_buffer"]],
            f"buffer_heatmap_{tab_key}",
        )
    else:
        st.info("Not enough time-series data for heatmap.")

    # ─── Smart Table: Stockout Risk ──────────────────────────────────────
    st.markdown("### Stockout Risk Table")
    table_df = latest_df[["site_id", "sector_id", "date", "days_of_buffer",
                           "total_daily_used", "spare_tank_balance",
                           "num_generators_active"]].copy()
    table_df.columns = ["Site", "Sector", "Date", "Days of Buffer",
                         "Daily Used (L)", "Tank Balance (L)", "Active Gens"]
    table_df["Risk"] = table_df["Days of Buffer"].apply(
        lambda x: "CRITICAL" if (x is None or pd.isna(x) or x < crit_days) else "WARNING" if x < warn_days else "HEALTHY"
    )
    render_smart_table(
        table_df, title="Stockout Risk Assessment",
        severity_col="Risk",
        highlight_cols={"Days of Buffer": {"good": "high", "thresholds": [7, 3]}},
    )
    render_insight_panel(
        f"Stockout risk assessment{' for ' + sector_filter if sector_filter else ''}",
        table_df,
        f"stockout_table_{tab_key}",
    )


# Render content for the selected tab
render_buffer_content(sector_filter, tab_key)


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

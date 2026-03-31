"""
Page 1: Sector Overview -- Compare CP vs CMHL vs CFC at a glance
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.charts import (
from utils.auth import require_login, render_sidebar_user
    stacked_bar_by_sector, buffer_trend_with_thresholds,
    horizontal_bar, bar_chart, STATUS_COLORS, apply_layout,
)
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary, render_forecast_insight
from models.buffer_predictor import predict_buffer_depletion, get_critical_sites
from config.settings import SECTORS, ALERTS

st.set_page_config(page_title="Sector Overview", page_icon="📊", layout="wide")
require_login()
render_sidebar_user()

st.title("📊 Sector Overview")

ui.alert(
    title="📊 Sector Overview",
    description="Comparing CP (City Pharmacy, 25 sites), CMHL (City Mart Holdings, 30 sites), and CFC (City Food Chain, 2 factories). Data from weekly Blackout Hour Excel files covering generator operations and fuel inventory.",
    key="alert_sector",
)

# ─── Load dates ──────────────────────────────────────────────────────────────
with get_db() as conn:
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM daily_site_summary ORDER BY date"
    ).fetchall()]

if not dates:
    st.info("No data available. Please seed the database first.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    date_start = st.selectbox("From", dates, index=0)
with col2:
    date_end = st.selectbox("To", dates, index=len(dates) - 1)

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sector_data(d_start, d_end):
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.date, s.sector_id,
                   COUNT(DISTINCT dss.site_id) as sites_reporting,
                   ROUND(AVG(dss.total_gen_run_hr), 1) as avg_gen_hr,
                   ROUND(SUM(dss.total_daily_used), 0) as total_fuel_used,
                   ROUND(AVG(dss.days_of_buffer), 1) as avg_buffer_days,
                   SUM(CASE WHEN dss.days_of_buffer < ? THEN 1 ELSE 0 END) as critical_sites,
                   SUM(CASE WHEN dss.days_of_buffer >= ? AND dss.days_of_buffer < ? THEN 1 ELSE 0 END) as warning_sites,
                   SUM(CASE WHEN dss.days_of_buffer >= ? THEN 1 ELSE 0 END) as healthy_sites
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date BETWEEN ? AND ?
            GROUP BY dss.date, s.sector_id
            ORDER BY dss.date, s.sector_id
        """, conn, params=(
            ALERTS["buffer_critical_days"], ALERTS["buffer_critical_days"],
            ALERTS["buffer_warning_days"], ALERTS["buffer_warning_days"],
            d_start, d_end,
        ))
    return df

df = load_sector_data(date_start, date_end)

if df.empty:
    st.info("No data in selected date range.")
    st.stop()

latest = df["date"].max()
latest_df = df[df["date"] == latest]

# ─── Page-level AI Summary ───────────────────────────────────────────────────
kpi_dict = {}
for _, row in latest_df.iterrows():
    kpi_dict[row["sector_id"]] = {
        "sites": int(row["sites_reporting"]),
        "avg_buffer_days": float(row["avg_buffer_days"] or 0),
        "total_fuel_used": float(row["total_fuel_used"] or 0),
        "critical_sites": int(row["critical_sites"] or 0),
    }
render_page_summary("Sector Overview", kpi_dict)

# ─── Sector Tabs ─────────────────────────────────────────────────────────────
sectors = sorted(df["sector_id"].unique().tolist())
selected = ui.tabs(
    options=["All"] + sectors,
    default_value="All",
    key="sector_tabs",
)

# Determine sector filter based on selected tab
if selected == "All":
    sector_filter = None
    tab_key = "sector_all"
else:
    sector_filter = selected
    tab_key = f"sector_{selected}"


def render_sector_content(sector_filter, tab_key):
    """Render KPI cards, charts, and table for a given sector filter."""
    if sector_filter is None:
        filtered_df = df.copy()
        filtered_latest = latest_df.copy()
    else:
        filtered_df = df[df["sector_id"] == sector_filter].copy()
        filtered_latest = latest_df[latest_df["sector_id"] == sector_filter].copy()

    if filtered_df.empty:
        st.info(f"No data available for {sector_filter or 'any sector'}.")
        return

    # ─── KPI Cards ───────────────────────────────────────────────────────
    st.markdown("### Sector KPIs (Latest Date)")
    for idx, (_, row) in enumerate(filtered_latest.iterrows()):
        buf = row["avg_buffer_days"] or 0
        crit = int(row["critical_sites"] or 0)
        warn = int(row["warning_sites"] or 0)
        healthy = int(row["healthy_sites"] or 0)

        ui.metric_card(
            title=f"{row['sector_id']} - {int(row['sites_reporting'])} Sites",
            content=f"{buf:.1f} days buffer",
            description=f"Avg Gen Hr: {row['avg_gen_hr']} | Fuel Used: {row['total_fuel_used']:,.0f} L",
            key=f"kpi_{tab_key}_{idx}",
        )

        ui.badges(
            badge_list=[
                (f"{crit} critical", "destructive"),
                (f"{warn} warning", "outline"),
                (f"{healthy} healthy", "default"),
            ],
            key=f"badges_{tab_key}_{idx}",
        )

    # ─── Chart 1: Daily Fuel Consumption by Sector ───────────────────────
    st.markdown("### Daily Fuel Consumption by Sector")
    st.caption("This chart shows how many liters of fuel were used each day, broken down by sector. Taller bars mean more fuel was consumed that day.")
    fig1 = stacked_bar_by_sector(filtered_df, "date", "total_fuel_used", title="Total Fuel Used (Liters)")
    st.plotly_chart(fig1, use_container_width=True, key=f"fuel_consumption_{tab_key}")
    render_insight_panel(
        f"Daily fuel consumption trend{' for ' + sector_filter if sector_filter else ' across all sectors'}",
        filtered_df[["date", "sector_id", "total_fuel_used"]],
        f"fuel_consumption_{tab_key}",
    )

    # ─── Chart 2: Buffer Trend ───────────────────────────────────────────
    st.markdown("### Days of Buffer Trend")
    st.caption("This shows how many days of fuel each sector has left over time. If the line drops below the red dashed line (3 days), that sector is in critical danger of running out.")
    fig2 = buffer_trend_with_thresholds(filtered_df, "date", "avg_buffer_days", "sector_id",
                                         title="Average Days of Buffer by Sector")
    st.plotly_chart(fig2, use_container_width=True, key=f"buffer_trend_{tab_key}")
    render_insight_panel(
        f"Buffer days trend{' for ' + sector_filter if sector_filter else ' across all sectors'}",
        filtered_df[["date", "sector_id", "avg_buffer_days"]],
        f"buffer_trend_{tab_key}",
    )

    # ─── Chart 3: Site Health Distribution ────────────────────────────────
    st.markdown("### Site Health Distribution (Latest Date)")
    st.caption("This bar chart shows the number of sites in each health category per sector. Critical means less than 3 days of fuel left, Warning means 3-7 days, and Healthy means more than 7 days.")
    status_data = []
    for _, row in filtered_latest.iterrows():
        for status, count_col in [("CRITICAL", "critical_sites"), ("WARNING", "warning_sites"), ("HEALTHY", "healthy_sites")]:
            status_data.append({
                "sector_id": row["sector_id"],
                "Status": status,
                "Count": int(row[count_col] or 0),
            })
    status_df = pd.DataFrame(status_data)
    if not status_df.empty:
        fig3 = horizontal_bar(status_df, "Count", "sector_id", "Status", STATUS_COLORS,
                               title="Sites by Buffer Status")
        st.plotly_chart(fig3, use_container_width=True, key=f"health_dist_{tab_key}")
        render_insight_panel(
            f"Site health distribution{' for ' + sector_filter if sector_filter else ' across all sectors'}",
            status_df,
            f"health_dist_{tab_key}",
        )

    # ─── Smart Table: Sector Summary ─────────────────────────────────────
    st.markdown("### Sector Summary Table")
    st.caption("A summary of each sector showing the number of sites, average generator hours, total fuel used, and average buffer days. Red rows need urgent attention.")
    table_df = filtered_latest[["sector_id", "sites_reporting", "avg_gen_hr", "total_fuel_used", "avg_buffer_days"]].copy()
    table_df.columns = ["Sector", "Sites", "Avg Gen Hr", "Fuel Used (L)", "Avg Buffer Days"]
    table_df["Status"] = table_df["Avg Buffer Days"].apply(
        lambda x: "CRITICAL" if x and x < 3 else "WARNING" if x and x < 7 else "HEALTHY"
    )
    render_smart_table(
        table_df, title="Sector Summary",
        severity_col="Status",
        highlight_cols={"Avg Buffer Days": {"good": "high", "thresholds": [7, 3]}},
    )
    render_insight_panel(
        f"Sector summary table{' for ' + sector_filter if sector_filter else ' across all sectors'}",
        table_df,
        f"summary_table_{tab_key}",
    )


# Render content for the selected tab
render_sector_content(sector_filter, tab_key)

# ─── Forecasting: Next Week Projection ──────────────────────────────────────
st.markdown("---")
st.markdown("## Next Week Projection")
st.caption("Using recent fuel consumption trends, this section predicts which sites may run out of fuel in the next 7 days. Sites listed here should be prioritized for resupply.")

try:
    critical_sites_df = get_critical_sites(threshold_days=7)
    if not critical_sites_df.empty:
        st.markdown("### Sites Projected to Run Low Within 7 Days")
        display_cols = ["site_id", "sector_id", "current_balance", "smoothed_daily_used",
                        "days_until_stockout", "projected_stockout_date", "trend", "confidence"]
        avail_cols = [c for c in display_cols if c in critical_sites_df.columns]
        crit_display = critical_sites_df[avail_cols].copy()
        crit_display.columns = [c.replace("_", " ").title() for c in avail_cols]
        render_smart_table(crit_display, title="Critical Sites Forecast")
        render_insight_panel(
            "Sites projected to deplete fuel buffer within 7 days",
            crit_display,
            "forecast_critical_sites",
        )
    else:
        st.success("No sites are projected to run out of fuel within the next 7 days.")

    # Full buffer prediction overview
    all_predictions = predict_buffer_depletion()
    if not all_predictions.empty:
        st.markdown("### Buffer Depletion Forecast by Sector")
        st.caption("Average projected days until fuel runs out, grouped by sector. Lower bars mean the sector needs fuel sooner.")
        sector_forecast = all_predictions.groupby("sector_id", as_index=False).agg(
            avg_days=("days_until_stockout", "mean"),
            min_days=("days_until_stockout", "min"),
            sites=("site_id", "count"),
        ).round(1)
        if not sector_forecast.empty:
            fig_fc = bar_chart(sector_forecast, "sector_id", "avg_days",
                               title="Avg Projected Days Until Stockout by Sector")
            st.plotly_chart(fig_fc, use_container_width=True, key="forecast_sector_bar")
            render_insight_panel(
                "Buffer depletion forecast by sector",
                sector_forecast,
                "forecast_sector_overview",
            )
            render_forecast_insight(
                "Buffer Predictor",
                {
                    "sectors": sector_forecast.to_dict(orient="records"),
                    "critical_count": len(critical_sites_df) if not critical_sites_df.empty else 0,
                },
                "buffer_forecast_summary",
            )

except Exception as e:
    st.warning(f"Forecast model could not run: {e}")


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

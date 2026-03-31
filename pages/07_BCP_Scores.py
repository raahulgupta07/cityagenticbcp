"""
Page 7: BCP Command Center — Complete Business Continuity overview across ALL sectors
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import plotly.graph_objects as go
from utils.database import get_db
from utils.charts import horizontal_bar, bar_chart, apply_layout, SECTOR_COLORS, STATUS_COLORS
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary, render_forecast_insight
from config.settings import SECTORS, ALERTS, BCP_WEIGHTS, BCP_GRADES
from models.bcp_engine import compute_bcp_scores
from models.buffer_predictor import predict_buffer_depletion, get_critical_sites
from models.fuel_price_forecast import forecast_fuel_price
from models.efficiency_scorer import get_fleet_efficiency_summary, get_anomalies
from alerts.alert_engine import run_all_checks, get_active_alerts

st.set_page_config(page_title="BCP Command Center", page_icon="🛡️", layout="wide")
st.title("🛡️ BCP Command Center")

ui.alert(
    title="🛡️ Complete Business Continuity Overview",
    description="This page combines ALL analysis across all sectors: fuel status, generator health, price outlook, risk scores, predictions, and alerts — everything in one place for decision makers.",
    key="alert_bcp",
)

# ═══════════════════════════════════════════════════════════════════════════
# LOAD ALL DATA
# ═══════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_all_bcp_data():
    with get_db() as conn:
        # Latest date with most data
        best_date = conn.execute("""
            SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1
        """).fetchone()[0]

        # Site summaries
        sites = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.spare_tank_balance, dss.blackout_hr, dss.days_of_buffer,
                   dss.num_generators_active
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = ?
        """, conn, params=(best_date,))

        # Sector summary
        sector_summary = pd.read_sql_query("""
            SELECT s.sector_id,
                   COUNT(DISTINCT dss.site_id) as sites,
                   ROUND(SUM(dss.total_daily_used), 0) as total_fuel_used,
                   ROUND(AVG(dss.days_of_buffer), 1) as avg_buffer,
                   ROUND(MIN(dss.days_of_buffer), 1) as min_buffer,
                   SUM(CASE WHEN dss.days_of_buffer < 3 THEN 1 ELSE 0 END) as critical_count,
                   SUM(CASE WHEN dss.days_of_buffer >= 3 AND dss.days_of_buffer < 7 THEN 1 ELSE 0 END) as warning_count,
                   SUM(CASE WHEN dss.days_of_buffer >= 7 THEN 1 ELSE 0 END) as healthy_count
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = ?
            GROUP BY s.sector_id
        """, conn, params=(best_date,))

        # Fuel prices (latest)
        fuel = pd.read_sql_query("""
            SELECT sector_id, supplier, fuel_type,
                   ROUND(AVG(price_per_liter), 0) as avg_price,
                   ROUND(SUM(quantity_liters), 0) as total_qty
            FROM fuel_purchases
            WHERE date >= date(?, '-7 days') AND price_per_liter IS NOT NULL
            GROUP BY sector_id, supplier
        """, conn, params=(best_date,))

        # Generator stats
        gen_stats = pd.read_sql_query("""
            SELECT s.sector_id,
                   COUNT(DISTINCT g.generator_id) as total_gens,
                   ROUND(SUM(g.power_kva), 0) as total_kva,
                   COUNT(DISTINCT g.site_id) as sites_with_gens
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            WHERE g.is_active = 1
            GROUP BY s.sector_id
        """, conn)

        # Active alerts
        alerts = pd.read_sql_query("""
            SELECT severity, COUNT(*) as count
            FROM alerts WHERE is_acknowledged = 0
            GROUP BY severity
        """, conn)

        total_sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        total_gens = conn.execute("SELECT COUNT(*) FROM generators WHERE is_active = 1").fetchone()[0]

    return best_date, sites, sector_summary, fuel, gen_stats, alerts, total_sites, total_gens

best_date, sites_df, sector_df, fuel_df, gen_df, alerts_df, total_sites, total_gens = load_all_bcp_data()

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: OVERALL STATUS (combined all sectors)
# ═══════════════════════════════════════════════════════════════════════════
# AI Summary
total_critical = int(sector_df["critical_count"].sum()) if not sector_df.empty else 0
total_warning = int(sector_df["warning_count"].sum()) if not sector_df.empty else 0
total_healthy = int(sector_df["healthy_count"].sum()) if not sector_df.empty else 0
overall_buffer = round(sector_df["avg_buffer"].mean(), 1) if not sector_df.empty else 0
alert_counts = {r["severity"]: r["count"] for _, r in alerts_df.iterrows()} if not alerts_df.empty else {}

render_page_summary("BCP Command Center", {
    "date": best_date,
    "total_sites": total_sites,
    "critical_sites": total_critical,
    "warning_sites": total_warning,
    "healthy_sites": total_healthy,
    "avg_buffer_days": overall_buffer,
    "alerts_critical": alert_counts.get("CRITICAL", 0),
    "alerts_warning": alert_counts.get("WARNING", 0),
})

# ─── Top KPI Row ─────────────────────────────────────────────────────────
st.markdown(f"### Overall Status — {best_date}")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    ui.metric_card(title="Total Sites", content=str(total_sites), description=f"{len(sector_df)} sectors", key="bcp_mc_sites")
with c2:
    ui.metric_card(title="Generators", content=str(total_gens), description="active", key="bcp_mc_gens")
with c3:
    ui.metric_card(title="Avg Buffer", content=f"{overall_buffer} days", description="all sectors", key="bcp_mc_buffer")
with c4:
    ui.metric_card(title="🔴 Critical", content=str(total_critical), description="<3 days fuel", key="bcp_mc_crit")
with c5:
    ui.metric_card(title="🟡 Warning", content=str(total_warning), description="3-7 days fuel", key="bcp_mc_warn")
with c6:
    ui.metric_card(title="🟢 Healthy", content=str(total_healthy), description=">7 days fuel", key="bcp_mc_healthy")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: SECTOR COMPARISON
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### Sector-by-Sector Comparison")
st.caption("How each sector is performing across all key metrics")

if not sector_df.empty:
    # Merge gen stats
    combined = sector_df.merge(gen_df, on="sector_id", how="left")

    table_data = combined[["sector_id", "sites", "total_gens", "total_kva",
                            "total_fuel_used", "avg_buffer", "min_buffer",
                            "critical_count", "warning_count", "healthy_count"]].copy()
    table_data.columns = ["Sector", "Sites", "Generators", "Total KVA",
                           "Fuel Used (L)", "Avg Buffer", "Min Buffer",
                           "Critical", "Warning", "Healthy"]
    table_data["Status"] = table_data["Avg Buffer"].apply(
        lambda x: "CRITICAL" if pd.notna(x) and x < 3 else "WARNING" if pd.notna(x) and x < 7 else "HEALTHY"
    )

    render_smart_table(table_data, title="Sector Comparison", severity_col="Status",
                       highlight_cols={"Avg Buffer": {"good": "high", "thresholds": [7, 3]},
                                       "Min Buffer": {"good": "high", "thresholds": [7, 3]}})

    render_insight_panel(
        "Sector comparison across all key BCP metrics — sites, generators, fuel, buffer days",
        table_data, "bcp_sector_comparison"
    )

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: FUEL STATUS — ALL SECTORS COMBINED
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### Fuel Buffer Status — All Sites Combined")
st.caption("Sites ranked by urgency — lowest fuel buffer first. Red = needs immediate resupply.")

if not sites_df.empty:
    buffer_df = sites_df[sites_df["days_of_buffer"].notna()][["site_id", "sector_id", "days_of_buffer",
                                                                "spare_tank_balance", "total_daily_used"]].copy()
    buffer_df = buffer_df.sort_values("days_of_buffer")
    buffer_df["status"] = buffer_df["days_of_buffer"].apply(
        lambda x: "CRITICAL" if x < 3 else "WARNING" if x < 7 else "HEALTHY"
    )

    # Bar chart — ALL sites sorted by buffer
    fig = horizontal_bar(buffer_df.head(20), "days_of_buffer", "site_id", "status", STATUS_COLORS,
                          title="Top 20 Sites by Urgency (lowest buffer first)")
    st.plotly_chart(fig, use_container_width=True, key="bcp_buffer_bar")

    render_insight_panel(
        "Sites ranked by fuel buffer urgency across all sectors",
        buffer_df.head(20), "bcp_buffer_urgency"
    )

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: BCP SCORES — ALL SITES
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### BCP Risk Scores — All Sites")
st.caption("Composite score (0-100): Fuel Reserve 35% + Generator Coverage 30% + Power Capacity 20% + Resilience 15%")

bcp_df = compute_bcp_scores(best_date)
if not bcp_df.empty:
    # Grade distribution
    grade_counts = bcp_df["grade"].value_counts().reindex(["A", "B", "C", "D", "F"], fill_value=0)
    gc1, gc2, gc3, gc4, gc5 = st.columns(5)
    for i, (grade, count) in enumerate(grade_counts.items()):
        with [gc1, gc2, gc3, gc4, gc5][i]:
            label = BCP_GRADES.get(grade, {}).get("label", "")
            ui.metric_card(title=f"Grade {grade}", content=str(count),
                           description=label, key=f"bcp_grade_{grade}")

    # Score bar chart
    chart_df = bcp_df[["site_id", "sector_id", "bcp_score", "grade"]].sort_values("bcp_score")
    grade_colors = {g: info["color"] for g, info in BCP_GRADES.items()}
    fig2 = horizontal_bar(chart_df, "bcp_score", "site_id", "grade", grade_colors,
                           title="BCP Score by Site (0-100)")
    fig2.update_xaxes(range=[0, 100])
    st.plotly_chart(fig2, use_container_width=True, key="bcp_score_bar")

    render_insight_panel(
        "BCP risk scores across all sites — identifying most vulnerable locations",
        bcp_df[["site_id", "sector_id", "bcp_score", "grade", "fuel_score", "coverage_score"]],
        "bcp_scores_all"
    )

    # Detail table
    detail = bcp_df[["site_id", "sector_id", "bcp_score", "grade", "fuel_score",
                      "coverage_score", "power_score", "resilience_score", "days_of_buffer"]].copy()
    detail.columns = ["Site", "Sector", "BCP Score", "Grade", "Fuel (35%)",
                       "Coverage (30%)", "Power (20%)", "Resilience (15%)", "Buffer Days"]
    render_smart_table(detail, title="BCP Score Breakdown", severity_col="Grade",
                       highlight_cols={"BCP Score": {"good": "high", "thresholds": [60, 40]},
                                       "Buffer Days": {"good": "high", "thresholds": [7, 3]}})

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5A: STOCKOUT PREDICTIONS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🛢️ Stockout Predictions")
st.caption("Which sites will run out of fuel and when — based on current consumption trends using exponential smoothing")

all_predictions = predict_buffer_depletion()
critical = get_critical_sites(threshold_days=14)

if not all_predictions.empty:
    # KPI cards
    sc1, sc2, sc3, sc4 = st.columns(4)
    crit_count = len(all_predictions[all_predictions["days_until_stockout"].notna() & (all_predictions["days_until_stockout"] < 3)])
    warn_count = len(all_predictions[all_predictions["days_until_stockout"].notna() & (all_predictions["days_until_stockout"] >= 3) & (all_predictions["days_until_stockout"] < 7)])
    safe_count = len(all_predictions[all_predictions["days_until_stockout"].notna() & (all_predictions["days_until_stockout"] >= 7)])
    inc_count = len(all_predictions[all_predictions["trend"] == "increasing"])

    with sc1:
        ui.metric_card(title="🔴 Critical (<3 days)", content=str(crit_count),
                       description="immediate resupply", key="bcp_so_crit")
    with sc2:
        ui.metric_card(title="🟡 Warning (3-7 days)", content=str(warn_count),
                       description="plan resupply", key="bcp_so_warn")
    with sc3:
        ui.metric_card(title="🟢 Safe (>7 days)", content=str(safe_count),
                       description="adequate fuel", key="bcp_so_safe")
    with sc4:
        ui.metric_card(title="📈 Rising Usage", content=str(inc_count),
                       description="consumption increasing", key="bcp_so_trend")

    # Chart: Days until stockout per site (horizontal bar)
    chart_pred = all_predictions[all_predictions["days_until_stockout"].notna()].copy()
    chart_pred = chart_pred.sort_values("days_until_stockout").head(25)
    chart_pred["status"] = chart_pred["days_until_stockout"].apply(
        lambda x: "CRITICAL" if x < 3 else "WARNING" if x < 7 else "HEALTHY"
    )

    if not chart_pred.empty:
        fig_so = horizontal_bar(chart_pred, "days_until_stockout", "site_id", "status", STATUS_COLORS,
                                 title="Projected Days Until Fuel Runs Out")
        st.plotly_chart(fig_so, use_container_width=True, key="bcp_stockout_chart")

    # Detail table
    if not critical.empty:
        display = critical[["site_id", "sector_id", "current_balance", "avg_daily_used",
                             "smoothed_daily_used", "days_until_stockout",
                             "projected_stockout_date", "trend", "confidence"]].copy()
        display.columns = ["Site", "Sector", "Balance (L)", "Avg Daily Use (L)",
                            "Smoothed Use (L)", "Days Left", "Stockout Date", "Trend", "Confidence"]
        render_smart_table(display, title="Sites at Risk (within 14 days)",
                           severity_col="Trend",
                           highlight_cols={"Days Left": {"good": "high", "thresholds": [7, 3]}})

    render_insight_panel(
        "Fuel stockout predictions across all sectors — which sites run out first and when",
        all_predictions[["site_id", "sector_id", "days_until_stockout", "trend", "confidence"]].head(15),
        "bcp_stockout_detail"
    )
else:
    st.success("No stockout risks detected.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5B: FUEL PRICE OUTLOOK
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### ⛽ Fuel Price Outlook")
st.caption("7-day diesel price forecast based on last 4 weeks of purchase data — using Ridge regression with trend analysis")

# Forecast per sector
forecast_sectors = ["CMHL", "CP"]  # sectors with enough price data
for fc_sector in forecast_sectors:
    forecast = forecast_fuel_price(sector_id=fc_sector, fuel_type="PD", days_ahead=7)

    st.markdown(f"#### {fc_sector} — {SECTORS.get(fc_sector, {}).get('name', fc_sector)}")

    if forecast["error"]:
        st.info(f"{fc_sector}: {forecast['error']}")
        continue

    history = forecast["history"]
    fc_df = forecast["forecast"]

    if fc_df is None or fc_df.empty:
        continue

    # KPIs
    fc1, fc2, fc3, fc4 = st.columns(4)
    latest_price = history["price"].iloc[-1] if history is not None and not history.empty else 0
    forecast_price = fc_df["predicted_price"].iloc[-1]
    change_pct = ((forecast_price - latest_price) / latest_price * 100) if latest_price > 0 else 0

    with fc1:
        ui.metric_card(title="Current Price", content=f"{latest_price:,.0f} MMK",
                       description="latest recorded", key=f"bcp_fp_current_{fc_sector}")
    with fc2:
        ui.metric_card(title="7-Day Forecast", content=f"{forecast_price:,.0f} MMK",
                       description=f"{'↑' if change_pct > 0 else '↓'} {abs(change_pct):.1f}%",
                       key=f"bcp_fp_forecast_{fc_sector}")
    with fc3:
        trend_label = forecast["trend"].upper()
        ui.metric_card(title="Trend", content=trend_label,
                       description=f"R² = {forecast['r_squared']}", key=f"bcp_fp_trend_{fc_sector}")
    with fc4:
        daily_change = forecast["avg_daily_change"]
        ui.metric_card(title="Daily Change", content=f"{daily_change:+,.0f} MMK",
                       description="per day average", key=f"bcp_fp_daily_{fc_sector}")

    # Chart: Historical + Forecast line
    fig_fp = go.Figure()

    # Historical prices
    if history is not None and not history.empty:
        fig_fp.add_trace(go.Scatter(
            x=history["date"], y=history["price"],
            mode="lines+markers", name="Actual Price",
            line=dict(color="#2196F3", width=2),
            marker=dict(size=6),
        ))

    # Forecast line
    fig_fp.add_trace(go.Scatter(
        x=fc_df["date"], y=fc_df["predicted_price"],
        mode="lines+markers", name="Forecast",
        line=dict(color="#ef4444", width=2, dash="dash"),
        marker=dict(size=6, symbol="diamond"),
    ))

    # Confidence band
    fig_fp.add_trace(go.Scatter(
        x=pd.concat([fc_df["date"], fc_df["date"][::-1]]),
        y=pd.concat([fc_df["upper_bound"], fc_df["lower_bound"][::-1]]),
        fill="toself", fillcolor="rgba(239,68,68,0.1)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% Confidence",
        showlegend=True,
    ))

    fig_fp.update_layout(
        title=f"{fc_sector} Diesel Price — Actual vs Forecast (MMK/L)",
        xaxis_title="Date", yaxis_title="Price (MMK/L)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12), height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis=dict(gridcolor="#e5e7eb"), yaxis=dict(gridcolor="#e5e7eb"),
    )
    st.plotly_chart(fig_fp, use_container_width=True, key=f"bcp_fp_chart_{fc_sector}")

    # Forecast table
    fc_display = fc_df.copy()
    fc_display["date"] = fc_display["date"].dt.strftime("%Y-%m-%d")
    fc_display.columns = ["Date", "Predicted (MMK)", "Lower Bound", "Upper Bound"]
    st.dataframe(fc_display, use_container_width=True, hide_index=True)

    render_forecast_insight(f"Fuel Price for {fc_sector}", {
        "sector": fc_sector,
        "trend": forecast["trend"],
        "current_price": latest_price,
        "forecast_7day_end": forecast_price,
        "change_pct": round(change_pct, 1),
        "daily_change": daily_change,
    }, f"bcp_fp_{fc_sector}")

# Overall price insight
render_insight_panel(
    "Fuel price outlook across all sectors — cost trends and procurement strategy",
    {"sectors_forecasted": forecast_sectors}, "bcp_price_outlook"
)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: GENERATOR HEALTH
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### Generator Health — Efficiency & Anomalies")
st.caption("Generators that are consuming more or less fuel than expected")

eff_summary = get_fleet_efficiency_summary()
anomalies = get_anomalies()

ec1, ec2, ec3 = st.columns(3)
with ec1:
    ui.metric_card(title="Generator Models", content=str(len(eff_summary)),
                   description="active models", key="bcp_eff_models")
with ec2:
    anomaly_count = len(anomalies) if not anomalies.empty else 0
    ui.metric_card(title="Anomalies", content=str(anomaly_count),
                   description="unusual efficiency", key="bcp_eff_anomalies")
with ec3:
    avg_eff = eff_summary["avg_efficiency"].mean() if not eff_summary.empty else 0
    ui.metric_card(title="Avg Efficiency", content=f"{avg_eff:.0%}",
                   description="target: 80-120%", key="bcp_eff_avg")

if not anomalies.empty:
    top_anomalies = anomalies.head(10)[["site_id", "sector_id", "model_name", "date",
                                         "efficiency_ratio", "status"]].copy()
    top_anomalies.columns = ["Site", "Sector", "Generator", "Date", "Efficiency", "Status"]
    render_smart_table(top_anomalies, title="Top Anomalies", severity_col="Status")

render_insight_panel(
    "Generator fleet efficiency overview — anomalies and health across all sectors",
    eff_summary if not eff_summary.empty else {"status": "no data"},
    "bcp_gen_health"
)

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: ACTIVE ALERTS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### Active Alerts")

active = get_active_alerts()
if not active.empty:
    ac1, ac2, ac3 = st.columns(3)
    crit_count = len(active[active["severity"] == "CRITICAL"])
    warn_count = len(active[active["severity"] == "WARNING"])
    info_count = len(active[active["severity"] == "INFO"])
    with ac1:
        ui.metric_card(title="🔴 Critical", content=str(crit_count), description="immediate action", key="bcp_alert_crit")
    with ac2:
        ui.metric_card(title="🟡 Warning", content=str(warn_count), description="attention needed", key="bcp_alert_warn")
    with ac3:
        ui.metric_card(title="🔵 Info", content=str(info_count), description="informational", key="bcp_alert_info")

    alert_display = active[["alert_type", "severity", "site_id", "sector_id", "message"]].head(20).copy()
    alert_display.columns = ["Type", "Severity", "Site", "Sector", "Message"]
    render_smart_table(alert_display, title="Active Alerts", severity_col="Severity")

    render_insight_panel(
        "Active alerts across all sectors — buffer, efficiency, idle generators",
        alert_display, "bcp_alerts"
    )
else:
    st.success("No active alerts. All systems within normal thresholds.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### AI Recommendations")

# Collect all key data points for a comprehensive recommendation
rec_data = {
    "critical_sites": total_critical,
    "warning_sites": total_warning,
    "avg_buffer": overall_buffer,
    "total_fuel_used": int(sector_df["total_fuel_used"].sum()) if not sector_df.empty else 0,
    "anomaly_generators": len(anomalies) if not anomalies.empty else 0,
    "fuel_trend": forecast.get("trend", "unknown") if forecast else "unknown",
    "worst_sites": sites_df.nsmallest(3, "days_of_buffer")[["site_id", "days_of_buffer"]].to_dict(orient="records") if not sites_df.empty and "days_of_buffer" in sites_df.columns else [],
}
render_insight_panel(
    "Complete BCP situation analysis — generate actionable recommendations for management covering fuel, generators, prices, and risks across all sectors",
    rec_data, "bcp_recommendations"
)


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

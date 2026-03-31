"""
Page 0: Daily Decision Board — THE command view for daily operations.
Answers: What mode for each site? Where to send fuel? How much will it cost?
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary, finish_page
from utils.charts import horizontal_bar, bar_chart, STATUS_COLORS, apply_layout
from utils.kpi_card import render_kpi, render_chart_source
from models.decision_engine import (
    get_operating_modes, get_delivery_queue, get_cost_per_hour,
    get_weekly_budget_forecast, get_supplier_buy_signal,
    get_generator_failure_risk, get_consumption_anomalies,
    get_site_criticality_ranking, run_what_if,
    get_resource_sharing_opportunities, get_load_optimization,
    get_price_elasticity, get_recovery_time_estimate,
)

st.set_page_config(page_title="Decision Board", page_icon="🎯", layout="wide")
require_login()
render_sidebar_user()
render_page_header("🎯", "Daily Decision Board",
    "What to do today — operating modes, fuel delivery, costs, risks, and AI recommendations")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: OPERATING MODES — The #1 Decision
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("### 1. Site Operating Modes")
st.caption("Should each outlet run full, reduce hours, or close today?")

modes_df = get_operating_modes()
if not modes_df.empty:
    # Summary cards
    mode_counts = modes_df["mode"].value_counts()
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1:
        render_kpi("🟢 FULL", mode_counts.get("FULL", 0),
                   "Sites where Days of Buffer ≥ 7. Buffer = Tank Balance ÷ Daily Usage",
                   "daily_site_summary (latest date with most data)", "mc_mode_full", ">7 days fuel")
    with mc2:
        render_kpi("🟡 REDUCED", mode_counts.get("REDUCED", 0),
                   "Sites where 3 ≤ Buffer < 7 days. Reduce operating hours to conserve fuel",
                   "daily_site_summary", "mc_mode_reduced", "3-7 days")
    with mc3:
        render_kpi("🟠 GEN ONLY", mode_counts.get("GENERATOR_ONLY", 0),
                   "Sites where 1 ≤ Buffer < 3 days. Essential services only",
                   "daily_site_summary", "mc_mode_gen", "1-3 days")
    with mc4:
        render_kpi("🔴 CLOSE", mode_counts.get("CLOSE", 0),
                   "Sites where Buffer < 1 day. Recommend temporary closure",
                   "daily_site_summary", "mc_mode_close", "<1 day fuel")
    with mc5:
        total_daily_cost = modes_df["daily_fuel_cost"].sum()
        render_kpi("💰 Daily Cost", f"{total_daily_cost:,.0f} MMK",
                   "SUM(Daily Usage × Latest Fuel Price) for each site. Price from fuel_purchases table",
                   "daily_site_summary × fuel_purchases (latest price per sector)", "mc_daily_cost")

    # Mode table
    display = modes_df[["site_id", "sector_id", "mode", "days_of_buffer",
                         "spare_tank_balance", "total_daily_used", "daily_fuel_cost", "reason"]].copy()
    display.columns = ["Site", "Sector", "Mode", "Buffer Days", "Tank (L)", "Daily Use (L)", "Daily Cost (MMK)", "Action"]
    render_smart_table(display, title="Operating Mode Recommendations", severity_col="Mode",
                       highlight_cols={"Buffer Days": {"good": "high", "thresholds": [7, 3]}})
    render_chart_source("Operating Modes",
                        "Mode = FULL if buffer≥7, REDUCED if 3-7, GEN_ONLY if 1-3, CLOSE if <1. Daily Cost = Daily Usage × Latest Sector Fuel Price",
                        "Tables: daily_site_summary, generators, fuel_purchases | Engine: models/decision_engine.py → get_operating_modes()")

    render_insight_panel("Site operating mode recommendations — which outlets to run, reduce, or close today", display, "decision_modes")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: FUEL DELIVERY PRIORITY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 2. Fuel Delivery Priority Queue")
st.caption("Where to send the fuel truck first — exact liters needed and deadline")

queue_df = get_delivery_queue()
if not queue_df.empty:
    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        ui.metric_card(title="Sites Needing Fuel", content=str(len(queue_df)),
                       description="below 7-day buffer", key="mc_q_count")
    with qc2:
        total_liters = queue_df["liters_needed"].sum()
        ui.metric_card(title="Total Liters Needed", content=f"{total_liters:,.0f}",
                       description="to reach 7-day buffer", key="mc_q_liters")
    with qc3:
        total_cost = queue_df["est_cost"].sum()
        ui.metric_card(title="Delivery Cost", content=f"{total_cost:,.0f}",
                       description="MMK estimated", key="mc_q_cost")

    q_display = queue_df[["site_id", "sector_id", "urgency", "days_of_buffer",
                           "spare_tank_balance", "liters_needed", "delivery_by", "est_cost"]].copy()
    q_display.columns = ["Site", "Sector", "Urgency", "Buffer Days", "Current (L)",
                          "Need (L)", "Deliver By", "Cost (MMK)"]
    render_smart_table(q_display, title="Delivery Queue", severity_col="Urgency",
                       highlight_cols={"Buffer Days": {"good": "high", "thresholds": [3, 1]}})
    render_chart_source("Delivery Queue",
                        "Need (L) = (7 × Daily Usage) - Current Balance. Urgency: IMMEDIATE if <1 day, TODAY if <2, TOMORROW if <3. Cost = Need × Latest Price",
                        "Tables: daily_site_summary, fuel_purchases | Engine: get_delivery_queue()")

    render_insight_panel("Fuel delivery priority queue — where to send trucks first", q_display, "decision_delivery")
else:
    st.success("All sites have 7+ days of fuel. No deliveries needed today.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: COST & BUDGET
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 3. Cost & Weekly Budget Forecast")

budget = get_weekly_budget_forecast()
if budget:
    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        ui.metric_card(title="Weekly Fuel Need", content=f"{budget['total_weekly_liters']:,.0f} L",
                       description="all sectors combined", key="mc_b_liters")
    with bc2:
        ui.metric_card(title="Weekly Budget", content=f"{budget['total_weekly_cost_mmk']:,.0f}",
                       description="MMK estimated", key="mc_b_cost")
    with bc3:
        ui.metric_card(title="Daily Avg Cost", content=f"{budget['total_daily_cost_mmk']:,.0f}",
                       description="MMK per day", key="mc_b_daily")

    if budget["sectors"]:
        budget_df = pd.DataFrame(budget["sectors"])
        budget_df.columns = ["Sector", "Daily (L)", "Weekly (L)", "Price/L", "Weekly Cost (MMK)"]
        render_smart_table(budget_df, title="Budget by Sector")

    render_insight_panel("Weekly fuel budget forecast — how much to spend next week", budget, "decision_budget")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: SUPPLIER BUY SIGNAL
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 4. Supplier Buy Signal")

signal = get_supplier_buy_signal()
if signal and signal.get("signals"):
    for s in signal["signals"]:
        color = "#16a34a" if s["recommendation"] == "BUY NOW" else "#d97706" if s["recommendation"] == "WAIT" else "#3b82f6"
        st.markdown(f"""
        <div style="background:white;border:1px solid #e5e7eb;border-left:4px solid {color};
                    border-radius:0 10px 10px 0;padding:16px;margin:8px 0">
            <strong>{s['supplier']}</strong> — {s['current_price']:,.0f} MMK/L
            (avg: {s['avg_price']:,.0f}) — Trend: {s['trend']}
            → <strong style="color:{color}">{s['recommendation']}</strong>
        </div>
        """, unsafe_allow_html=True)

    if signal.get("savings_pct", 0) > 0:
        st.info(f"💡 **{signal['cheapest']}** is {signal['savings_pct']}% cheaper right now.")

    render_insight_panel("Supplier comparison and buy/wait signal", signal, "decision_supplier")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: GENERATOR HEALTH & MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 5. Generator Maintenance Alerts")
st.caption("Based on cumulative run hours — service intervals at 500hr, 2000hr, 4000hr")

failure_df = get_generator_failure_risk()
if not failure_df.empty:
    at_risk = failure_df[failure_df["risk_level"].isin(["HIGH", "MEDIUM"])]
    if not at_risk.empty:
        f_display = at_risk[["site_id", "sector_id", "model_name", "total_hours",
                              "risk_level", "next_service_at", "hours_until_service",
                              "days_until_service", "maintenance_note"]].head(15).copy()
        f_display.columns = ["Site", "Sector", "Generator", "Total Hrs", "Risk",
                              "Service At", "Hrs Left", "Days Left", "Note"]
        render_smart_table(f_display, title="Generators Needing Maintenance", severity_col="Risk")

    render_insight_panel("Generator failure risk based on cumulative run hours", failure_df.head(20), "decision_gen_health")
else:
    st.success("All generators within safe run-hour limits.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: CONSUMPTION ANOMALIES
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 6. Consumption Anomalies")
st.caption("Sites using 30%+ more fuel than their 7-day average — possible leaks or extended outages")

anomalies = get_consumption_anomalies()
if not anomalies.empty:
    a_display = anomalies[["site_id", "sector_id", "total_daily_used", "avg_7d",
                            "pct_above_avg", "excess_liters", "possible_cause"]].copy()
    a_display.columns = ["Site", "Sector", "Today (L)", "7-Day Avg (L)", "% Above", "Excess (L)", "Possible Cause"]
    render_smart_table(a_display, title="Consumption Anomalies",
                       highlight_cols={"% Above": {"good": "low", "thresholds": [50, 100]}})
    render_insight_panel("Sites with abnormal fuel consumption", a_display, "decision_anomalies")
else:
    st.success("No consumption anomalies detected — all sites within normal range.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: RESOURCE SHARING
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 7. Cross-Sector Fuel Sharing")
st.caption("Sites with excess fuel (>14 days) that could transfer to critical sites (<3 days)")

transfers = get_resource_sharing_opportunities()
if transfers:
    t_df = pd.DataFrame(transfers)
    t_df.columns = ["From Site", "From Sector", "From Buffer", "To Site", "To Sector",
                     "To Buffer", "Transfer (L)", "Saves Delivery"]
    render_smart_table(t_df, title="Recommended Fuel Transfers")
    render_insight_panel("Cross-sector fuel sharing opportunities to avoid emergency deliveries", t_df, "decision_sharing")
else:
    st.info("No transfer opportunities — no sites have enough excess fuel to share.")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: LOAD OPTIMIZATION
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 8. Generator Load Optimization")
st.caption("For multi-generator sites — which generator to run for best fuel efficiency")

load_df = get_load_optimization()
if not load_df.empty:
    l_display = load_df[["site_id", "model_name", "power_kva", "consumption_per_hour",
                          "kva_per_liter", "rank", "recommendation", "savings_per_hour_liters"]].copy()
    l_display.columns = ["Site", "Generator", "KVA", "L/hr", "KVA per L", "Rank", "Use As", "Save L/hr"]
    render_smart_table(l_display, title="Generator Efficiency Ranking")
    render_insight_panel("Generator load optimization — which gen to run at each multi-generator site", l_display, "decision_load")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: RECOVERY TIME
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 9. Recovery Time Estimates")
st.caption("How fast each site can resume operations after grid power returns")

recovery_df = get_recovery_time_estimate()
if not recovery_df.empty:
    r_display = recovery_df[["site_id", "sector_id", "spare_tank_balance", "speed", "est_time", "note"]].copy()
    r_display.columns = ["Site", "Sector", "Tank (L)", "Speed", "Est. Time", "Status"]
    render_smart_table(r_display, title="Recovery Time", severity_col="Speed")
    render_insight_panel("Recovery time after grid power returns — based on fuel levels", r_display, "decision_recovery")

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 10: WHAT-IF SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 10. What-If Simulator")
st.caption("See how cost changes with different fuel prices or consumption levels")

wc1, wc2 = st.columns(2)
with wc1:
    price_change = st.slider("Fuel Price Change %", -30, 50, 0, 5, key="whatif_price")
with wc2:
    consumption_change = st.slider("Consumption Change %", -30, 50, 0, 5, key="whatif_consumption")

whatif = run_what_if(price_change, consumption_change)
if whatif:
    wrc1, wrc2, wrc3 = st.columns(3)
    with wrc1:
        ui.metric_card(title="Current Weekly Cost", content=f"{whatif['base_cost']:,.0f}",
                       description="MMK", key="mc_wi_base")
    with wrc2:
        color = "#dc2626" if whatif["new_cost"] > whatif["base_cost"] else "#16a34a"
        ui.metric_card(title="Projected Cost", content=f"{whatif['new_cost']:,.0f}",
                       description=f"{'↑' if whatif['pct_change'] > 0 else '↓'} {abs(whatif['pct_change'])}%",
                       key="mc_wi_new")
    with wrc3:
        diff = whatif["difference"]
        ui.metric_card(title="Impact", content=f"{'+' if diff > 0 else ''}{diff:,.0f}",
                       description="MMK savings/cost", key="mc_wi_diff")

# ═══════════════════════════════════════════════════════════════════════════
# AI INSIGHTS BUTTON
# ═══════════════════════════════════════════════════════════════════════════
finish_page()

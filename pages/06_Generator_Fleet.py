"""
Page 6: Generator Fleet Analytics — Monitor generator utilization and efficiency
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import plotly.graph_objects as go
from utils.database import get_db
from utils.charts import bar_chart, apply_layout
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary
from config.settings import SECTORS

from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
st.set_page_config(page_title="Generator Fleet", page_icon="🔧", layout="wide")
require_login()
render_sidebar_user()

render_page_header("⚙️", "Generator Fleet", "Efficiency scoring, anomaly detection, utilization across 86 generators")

ui.alert(
    title="⚙️ Generator Fleet Analytics",
    description="Monitors 86 generators across all sites. Efficiency = Actual Fuel Used / (Rated Consumption x Run Hours). Normal range: 80-120%. Values above 150% or below 50% indicate anomalies (possible fuel leak, theft, or metering error).",
    key="alert_fleet",
)

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_all_fleet_data():
    with get_db() as conn:
        sectors = [r[0] for r in conn.execute(
            "SELECT DISTINCT sector_id FROM sites ORDER BY sector_id"
        ).fetchall()]

        gens = pd.read_sql_query("""
            SELECT g.generator_id, g.site_id, s.sector_id, g.model_name, g.power_kva,
                   g.consumption_per_hour, g.fuel_type, g.supplier
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            WHERE g.is_active = 1
            ORDER BY s.sector_id, g.site_id, g.model_name
        """, conn)

        ops = pd.DataFrame()
        if not gens.empty:
            gen_ids = gens["generator_id"].tolist()
            placeholders = ",".join("?" for _ in gen_ids)
            ops = pd.read_sql_query(f"""
                SELECT do.generator_id, g.model_name, g.consumption_per_hour,
                       g.site_id, s.sector_id,
                       SUM(do.gen_run_hr) as total_run_hr,
                       SUM(do.daily_used_liters) as total_used,
                       COUNT(DISTINCT do.date) as days_active
                FROM daily_operations do
                JOIN generators g ON do.generator_id = g.generator_id
                JOIN sites s ON g.site_id = s.site_id
                WHERE do.generator_id IN ({placeholders})
                GROUP BY do.generator_id
            """, conn, params=gen_ids)

    return sectors, gens, ops

all_sectors, all_gens_df, all_ops_df = load_all_fleet_data()

if not all_sectors:
    st.info("No site data available.")
    st.stop()

# ─── Page-level AI Summary ───────────────────────────────────────────────────
kpi_dict = {
    "total_generators": len(all_gens_df),
    "avg_kva": float(all_gens_df["power_kva"].mean()) if not all_gens_df.empty else 0,
    "total_run_hrs": float(all_ops_df["total_run_hr"].sum()) if not all_ops_df.empty else 0,
}
render_page_summary("Generator Fleet Analytics", kpi_dict)

# ─── Sector Tabs ─────────────────────────────────────────────────────────────
tab_options = ["All"] + all_sectors
selected = ui.tabs(options=tab_options, default_value="All", key="fleet_tabs")


def render_fleet_content(sector_filter, tab_key):
    """Render fleet content for a sector filter."""
    if sector_filter is None:
        gens_df = all_gens_df.copy()
        ops_df = all_ops_df.copy()
    else:
        gens_df = all_gens_df[all_gens_df["sector_id"] == sector_filter].copy()
        gen_ids = gens_df["generator_id"].tolist()
        ops_df = all_ops_df[all_ops_df["generator_id"].isin(gen_ids)].copy() if not all_ops_df.empty else pd.DataFrame()

    if gens_df.empty:
        st.info(f"No generators found for {sector_filter or 'any sector'}.")
        return

    # ─── KPI Cards ───────────────────────────────────────────────────────
    st.markdown("### Fleet Summary")
    total_gens = len(gens_df)
    avg_kva = gens_df["power_kva"].mean() if not gens_df.empty else 0

    if not ops_df.empty:
        avg_utilization = ops_df["total_run_hr"].mean() / max(ops_df["days_active"].mean(), 1) / 24 * 100
    else:
        avg_utilization = 0

    total_run = ops_df["total_run_hr"].sum() if not ops_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card(
            title="Total Generators",
            content=str(total_gens),
            key=f"metric_total_gens_{tab_key}",
        )
    with c2:
        ui.metric_card(
            title="Avg Power (KVA)",
            content=f"{avg_kva:,.0f}" if pd.notna(avg_kva) else "N/A",
            key=f"metric_avg_kva_{tab_key}",
        )
    with c3:
        ui.metric_card(
            title="Avg Utilization",
            content=f"{avg_utilization:.1f}%",
            key=f"metric_avg_util_{tab_key}",
        )
    with c4:
        ui.metric_card(
            title="Total Run Hours",
            content=f"{total_run:,.0f}",
            key=f"metric_total_run_{tab_key}",
        )

    st.markdown("---")

    # ─── Chart 1: Run Hours by Generator Model ──────────────────────────
    st.markdown("### Run Hours by Generator Model")
    st.caption("This bar chart shows total run hours for each generator model. Models with more run hours are used more frequently for backup power.")
    if not ops_df.empty:
        model_hrs = ops_df.groupby("model_name", as_index=False)["total_run_hr"].sum()
        model_hrs = model_hrs.sort_values("total_run_hr", ascending=False)
        fig1 = bar_chart(model_hrs, "model_name", "total_run_hr",
                          title="Total Run Hours by Generator Model")
        st.plotly_chart(fig1, use_container_width=True, key=f"run_hours_chart_{tab_key}")
        render_insight_panel(
            f"Run hours by generator model{' for ' + sector_filter if sector_filter else ''}",
            model_hrs,
            f"run_hours_{tab_key}",
        )
    else:
        st.info("No operational data available.")

    # ─── Chart 2: Average Efficiency by Generator Model (Grouped Bar) ────
    st.markdown("### Generator Efficiency by Model")
    st.caption("This shows how efficiently each generator uses fuel compared to its rated consumption. Green bars (80-120%) are normal. Yellow means slightly off. Red means there may be a fuel leak, theft, or metering problem.")
    if not ops_df.empty:
        eff_df = ops_df[
            ops_df["consumption_per_hour"].notna()
            & (ops_df["total_run_hr"] > 0)
            & (ops_df["total_used"] > 0)
        ].copy()

        if not eff_df.empty:
            # Calculate efficiency % per generator
            eff_df["efficiency_pct"] = (
                (eff_df["consumption_per_hour"] * eff_df["total_run_hr"])
                / eff_df["total_used"] * 100
            ).round(1)

            # Group by model -- average efficiency
            model_eff = eff_df.groupby("model_name", as_index=False)["efficiency_pct"].mean().round(1)
            model_eff = model_eff.sort_values("efficiency_pct", ascending=False)

            # Assign color category
            def classify_efficiency(pct):
                if 80 <= pct <= 120:
                    return "Normal (80-120%)"
                elif 50 <= pct < 80 or 120 < pct <= 150:
                    return "Warning"
                else:
                    return "Anomaly"

            model_eff["Status"] = model_eff["efficiency_pct"].apply(classify_efficiency)

            # Efficiency badges
            anomaly_count = int((model_eff["Status"] == "Anomaly").sum())
            warning_count = int((model_eff["Status"] == "Warning").sum())
            normal_count = int((model_eff["Status"] == "Normal (80-120%)").sum())
            badge_list = []
            if anomaly_count > 0:
                badge_list.append((f"ANOMALY: {anomaly_count} models", "destructive"))
            if warning_count > 0:
                badge_list.append((f"WARNING: {warning_count} models", "outline"))
            badge_list.append((f"NORMAL: {normal_count} models", "default"))
            ui.badges(badge_list=badge_list, key=f"badges_efficiency_{tab_key}")

            # Build grouped bar chart with color coding
            eff_colors = {
                "Normal (80-120%)": "#16a34a",
                "Warning": "#d97706",
                "Anomaly": "#dc2626",
            }

            fig2 = go.Figure()
            for status, color in eff_colors.items():
                subset = model_eff[model_eff["Status"] == status]
                if not subset.empty:
                    fig2.add_trace(go.Bar(
                        x=subset["model_name"],
                        y=subset["efficiency_pct"],
                        name=status,
                        marker_color=color,
                        text=subset["efficiency_pct"].apply(lambda x: f"{x:.0f}%"),
                        textposition="outside",
                    ))

            # Add reference lines
            fig2.add_hline(y=100, line_dash="dash", line_color="#9ca3af",
                           annotation_text="100% = Perfect", annotation_position="top right")
            fig2.add_hline(y=80, line_dash="dot", line_color="#16a34a",
                           annotation_text="80%", annotation_position="bottom right")
            fig2.add_hline(y=120, line_dash="dot", line_color="#16a34a",
                           annotation_text="120%", annotation_position="top right")

            fig2 = apply_layout(fig2, title="Average Efficiency % by Generator Model")
            fig2.update_xaxes(title_text="Generator Model")
            fig2.update_yaxes(title_text="Efficiency %")
            st.plotly_chart(fig2, use_container_width=True, key=f"efficiency_bar_chart_{tab_key}")

            render_insight_panel(
                f"Generator efficiency by model{' for ' + sector_filter if sector_filter else ''}: "
                f"Normal (80-120%) means fuel use matches rated specs. Below 80% or above 120% needs investigation.",
                model_eff[["model_name", "efficiency_pct", "Status"]],
                f"efficiency_bar_{tab_key}",
            )
        else:
            st.info("Not enough data for efficiency comparison.")
    else:
        st.info("No operational data available.")

    # ─── Chart 3: Efficiency by Site (simple bar) ────────────────────────
    st.markdown("### Average Efficiency by Site")
    st.caption("This groups generator efficiency by site, making it easy to spot which locations have equipment that may need maintenance or investigation.")
    if not ops_df.empty:
        site_col = "site_id" if "site_id" in ops_df.columns else None
        if site_col:
            site_eff = ops_df[
                ops_df["consumption_per_hour"].notna()
                & (ops_df["total_run_hr"] > 0)
                & (ops_df["total_used"] > 0)
            ].copy()
            if not site_eff.empty:
                site_eff["efficiency_pct"] = (
                    (site_eff["consumption_per_hour"] * site_eff["total_run_hr"])
                    / site_eff["total_used"] * 100
                ).round(1)
                site_avg = site_eff.groupby("site_id", as_index=False)["efficiency_pct"].mean().round(1)
                site_avg = site_avg.sort_values("efficiency_pct", ascending=False).head(15)

                site_avg["Status"] = site_avg["efficiency_pct"].apply(classify_efficiency)

                fig3 = go.Figure()
                for status, color in eff_colors.items():
                    subset = site_avg[site_avg["Status"] == status]
                    if not subset.empty:
                        fig3.add_trace(go.Bar(
                            x=subset["site_id"],
                            y=subset["efficiency_pct"],
                            name=status,
                            marker_color=color,
                            text=subset["efficiency_pct"].apply(lambda x: f"{x:.0f}%"),
                            textposition="outside",
                        ))
                fig3.add_hline(y=100, line_dash="dash", line_color="#9ca3af")
                fig3 = apply_layout(fig3, title="Average Efficiency % by Site")
                fig3.update_xaxes(title_text="Site")
                fig3.update_yaxes(title_text="Efficiency %")
                st.plotly_chart(fig3, use_container_width=True, key=f"site_efficiency_chart_{tab_key}")

                render_insight_panel(
                    f"Generator efficiency by site{' for ' + sector_filter if sector_filter else ''}",
                    site_avg[["site_id", "efficiency_pct", "Status"]],
                    f"site_efficiency_{tab_key}",
                )

    # ─── Smart Table: Fleet with Efficiency % ────────────────────────────
    st.markdown("### Generator Fleet Detail")
    st.caption("Complete list of all generators with their rated specs, actual usage, and efficiency percentage. Sort by Efficiency % to find outliers.")
    if not ops_df.empty:
        fleet_df = gens_df.merge(
            ops_df[["generator_id", "total_run_hr", "total_used", "days_active"]],
            on="generator_id", how="left",
        )
    else:
        fleet_df = gens_df.copy()
        fleet_df["total_run_hr"] = None
        fleet_df["total_used"] = None
        fleet_df["days_active"] = None

    fleet_df["efficiency_pct"] = fleet_df.apply(
        lambda r: round(
            (r["consumption_per_hour"] * r["total_run_hr"]) / r["total_used"] * 100, 1
        ) if (pd.notna(r.get("consumption_per_hour")) and
              pd.notna(r.get("total_run_hr")) and
              pd.notna(r.get("total_used")) and
              r.get("total_used", 0) > 0 and
              r.get("total_run_hr", 0) > 0)
        else None,
        axis=1,
    )

    display_df = fleet_df[["site_id", "model_name", "power_kva", "consumption_per_hour",
                            "total_run_hr", "total_used", "days_active", "efficiency_pct"]].copy()
    display_df.columns = ["Site", "Model", "KVA", "Rated L/hr",
                           "Total Run Hr", "Total Used (L)", "Days Active", "Efficiency %"]

    render_smart_table(
        display_df, title="Generator Fleet",
        bar_col="Efficiency %",
        highlight_cols={"KVA": {"good": "high", "thresholds": [200, 100]}},
    )
    render_insight_panel(
        f"Generator fleet detail{' for ' + sector_filter if sector_filter else ''}",
        display_df,
        f"fleet_table_{tab_key}",
    )


# Render content based on selected tab
if selected == "All":
    render_fleet_content(None, "fleet_all")
else:
    render_fleet_content(selected, f"fleet_{selected}")


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

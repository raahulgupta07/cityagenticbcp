"""
Page 2: Site Detail -- Deep dive into a single site's generators & fuel
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.charts import multi_line, dual_axis_bar_line, bar_chart, apply_layout
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary
from config.settings import SECTORS

st.set_page_config(page_title="Site Detail", page_icon="🏢", layout="wide")
st.title("🏢 Site Detail")

ui.alert(
    title="🏢 Site Detail",
    description="Deep dive into individual site generator performance. Each site has 1-4 generators with different KVA ratings and fuel consumption profiles.",
    key="alert_site",
)

# ─── Load sector/site data ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_sectors_and_sites():
    with get_db() as conn:
        sectors = [r[0] for r in conn.execute(
            "SELECT DISTINCT sector_id FROM sites ORDER BY sector_id"
        ).fetchall()]
        sites_map = {}
        for s in sectors:
            sites_map[s] = [r[0] for r in conn.execute(
                "SELECT site_id FROM sites WHERE sector_id = ? ORDER BY site_id", (s,)
            ).fetchall()]
    return sectors, sites_map

sectors, sites_map = load_sectors_and_sites()

if not sectors:
    st.info("No data available.")
    st.stop()

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_site_data(site_id):
    with get_db() as conn:
        gens = pd.read_sql_query("""
            SELECT generator_id, model_name, model_name_raw, power_kva,
                   consumption_per_hour, fuel_type, supplier
            FROM generators WHERE site_id = ? AND is_active = 1
            ORDER BY model_name
        """, conn, params=(site_id,))

        ops = pd.read_sql_query("""
            SELECT do.date, do.generator_id, g.model_name,
                   do.gen_run_hr, do.daily_used_liters,
                   do.spare_tank_balance, do.blackout_hr
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            WHERE do.site_id = ?
            ORDER BY do.date, g.model_name
        """, conn, params=(site_id,))

        summary = pd.read_sql_query("""
            SELECT date, total_gen_run_hr, total_daily_used,
                   spare_tank_balance, blackout_hr, days_of_buffer,
                   num_generators_active
            FROM daily_site_summary
            WHERE site_id = ?
            ORDER BY date
        """, conn, params=(site_id,))

    return gens, ops, summary


# ─── Sector selection via tabs ───────────────────────────────────────────────
selected_sector = ui.tabs(
    options=sectors,
    default_value=sectors[0],
    key="sector_tabs",
)

sector_sites = sites_map.get(selected_sector, [])
if not sector_sites:
    st.info(f"No sites found for {selected_sector}.")
    st.stop()

# ─── Site selection via tabs ─────────────────────────────────────────────────
selected_site = ui.tabs(
    options=sector_sites,
    default_value=sector_sites[0],
    key=f"site_tabs_{selected_sector}",
)

tab_key = f"{selected_sector}_{selected_site}"

# ─── Render Site Detail ─────────────────────────────────────────────────────
gens_df, ops_df, summary_df = load_site_data(selected_site)

# ─── KPI Cards ───────────────────────────────────────────────────────
if not summary_df.empty:
    latest_row = summary_df.iloc[-1]
    kpi_dict = {
        "site": selected_site,
        "generators": len(gens_df),
        "avg_daily_use": float(summary_df["total_daily_used"].mean()),
        "buffer_days": float(latest_row["days_of_buffer"]) if pd.notna(latest_row["days_of_buffer"]) else 0,
    }
    render_page_summary(f"Site Detail - {selected_site}", kpi_dict)

    total_kva = gens_df["power_kva"].sum() if not gens_df.empty else 0
    bal = latest_row["spare_tank_balance"]
    buf = latest_row["days_of_buffer"]
    bo = latest_row["blackout_hr"]

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        ui.metric_card(
            title="Generators",
            content=str(len(gens_df)),
            description=f"Total KVA: {total_kva:,.0f}",
            key=f"metric_gens_{tab_key}",
        )
    with mc2:
        ui.metric_card(
            title="Avg Daily Use (L)",
            content=f"{summary_df['total_daily_used'].mean():,.0f}",
            description=f"Tank Balance: {bal:,.0f} L" if pd.notna(bal) else "Tank Balance: N/A",
            key=f"metric_fuel_{tab_key}",
        )
    with mc3:
        buf_str = f"{buf:.1f}" if pd.notna(buf) else "N/A"
        bo_str = f"{bo:.1f}" if pd.notna(bo) else "0.0"
        ui.metric_card(
            title="Days of Buffer",
            content=buf_str,
            description=f"Blackout Hrs: {bo_str}",
            key=f"metric_buffer_{tab_key}",
        )

    st.markdown("---")
else:
    st.info(f"No summary data available for {selected_site}.")
    st.stop()

# ─── Chart 1: Generator Run Hours ────────────────────────────────────
if not ops_df.empty:
    st.markdown("### Generator Run Hours by Day")
    fig1 = multi_line(ops_df, "date", "gen_run_hr", "model_name",
                       title="Generator Run Hours")
    st.plotly_chart(fig1, use_container_width=True, key=f"gen_run_hr_chart_{tab_key}")
    render_insight_panel(
        f"Generator run hours trend for site {selected_site}",
        ops_df[["date", "model_name", "gen_run_hr"]],
        f"gen_run_hr_{tab_key}",
    )

# ─── Chart 2: Fuel Consumption vs Tank Balance ───────────────────────
if not summary_df.empty:
    st.markdown("### Fuel Consumption vs Tank Balance")
    fig2 = dual_axis_bar_line(
        summary_df, "date", "total_daily_used", "spare_tank_balance",
        title="Daily Used (L) vs Tank Balance (L)",
    )
    st.plotly_chart(fig2, use_container_width=True, key=f"fuel_vs_balance_chart_{tab_key}")
    render_insight_panel(
        f"Fuel consumption vs tank balance for site {selected_site}",
        summary_df[["date", "total_daily_used", "spare_tank_balance"]],
        f"fuel_vs_balance_{tab_key}",
    )

# ─── Chart 3: Blackout Hours ─────────────────────────────────────────
has_blackout = SECTORS.get(selected_sector, {}).get("has_blackout_data", False)
if has_blackout and not summary_df.empty:
    blackout_df = summary_df[summary_df["blackout_hr"].notna()].copy()
    if not blackout_df.empty and blackout_df["blackout_hr"].sum() > 0:
        st.markdown("### Blackout Hours")
        blackout_df["color"] = blackout_df["blackout_hr"].apply(
            lambda x: "CRITICAL" if x > 8 else "WARNING" if x > 4 else "HEALTHY"
        )
        fig3 = bar_chart(blackout_df, "date", "blackout_hr", "color",
                          {"CRITICAL": "#dc2626", "WARNING": "#d97706", "HEALTHY": "#16a34a"},
                          title="Daily Blackout Hours")
        st.plotly_chart(fig3, use_container_width=True, key=f"blackout_chart_{tab_key}")
        render_insight_panel(
            f"Blackout hours for site {selected_site}",
            blackout_df[["date", "blackout_hr"]],
            f"blackout_{tab_key}",
        )
    elif has_blackout:
        st.info("No blackout events recorded for this site during this period.")

# ─── Generator Detail Table ──────────────────────────────────────────
st.markdown("### Generator Fleet")
if not gens_df.empty:
    table_df = gens_df[["model_name", "power_kva", "consumption_per_hour", "fuel_type", "supplier"]].copy()
    table_df.columns = ["Generator", "KVA", "Consumption/Hr (L)", "Fuel Type", "Supplier"]

    if not ops_df.empty:
        latest_date = ops_df["date"].max()
        latest_ops = ops_df[ops_df["date"] == latest_date][["generator_id", "gen_run_hr", "daily_used_liters"]].copy()
        gen_map = dict(zip(gens_df["generator_id"], gens_df["model_name"]))
        latest_ops["Generator"] = latest_ops["generator_id"].map(gen_map)
        latest_ops = latest_ops[["Generator", "gen_run_hr", "daily_used_liters"]]
        latest_ops.columns = ["Generator", "Run Hr (Latest)", "Used L (Latest)"]
        table_df = table_df.merge(latest_ops, on="Generator", how="left")

    render_smart_table(table_df, title=f"Generators at {selected_site}")
    render_insight_panel(
        f"Generator fleet for site {selected_site}",
        table_df,
        f"gen_table_{tab_key}",
    )
else:
    st.info("No generators found for this site.")


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

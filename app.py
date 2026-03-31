"""
CityBCPAgent v1 — Home Page & Navigation
"""
import os
import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from config.settings import DASHBOARD, SECTORS, DB_PATH
from utils.database import get_db

st.set_page_config(
    page_title=DASHBOARD["page_title"],
    page_icon=DASHBOARD["page_icon"],
    layout=DASHBOARD["layout"],
    initial_sidebar_state="expanded",
)

# ─── Global CSS ──────────────────────────────────────────────────────────────
st.html("""
<style>
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label { color: #94a3b8 !important; }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1e293b 100%);
        border-radius: 12px;
        padding: 32px;
        margin-bottom: 24px;
        color: white;
    }
    .hero-banner h1 { margin: 0; font-size: 28px; font-weight: 700; }
    .hero-banner p { margin: 8px 0 0; opacity: 0.8; font-size: 14px; }
    .hero-stats { margin-top: 12px; font-size: 12px; opacity: 0.6; }
</style>
""")


# ─── Data Loaders ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_home_kpis():
    with get_db() as conn:
        # Latest date with data
        latest = conn.execute(
            "SELECT MAX(date) as d FROM daily_site_summary"
        ).fetchone()["d"]

        if not latest:
            return {}

        # Sites reporting
        total_sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        reporting = conn.execute(
            "SELECT COUNT(DISTINCT site_id) FROM daily_site_summary WHERE date = ?",
            (latest,)
        ).fetchone()[0]

        # Avg buffer
        buf = conn.execute(
            "SELECT AVG(days_of_buffer) FROM daily_site_summary WHERE date = ? AND days_of_buffer IS NOT NULL",
            (latest,)
        ).fetchone()[0]

        # Total fuel used
        fuel = conn.execute(
            "SELECT SUM(total_daily_used) FROM daily_site_summary WHERE date = ?",
            (latest,)
        ).fetchone()[0]

        # Active alerts
        alerts_count = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE is_acknowledged = 0"
        ).fetchone()[0]

        # Sectors with sites
        sectors = conn.execute("""
            SELECT s.sector_id, COUNT(DISTINCT si.site_id) as sites,
                   COUNT(DISTINCT g.generator_id) as gens
            FROM sectors s
            LEFT JOIN sites si ON s.sector_id = si.sector_id
            LEFT JOIN generators g ON si.site_id = g.site_id
            GROUP BY s.sector_id
        """).fetchall()

        return {
            "latest_date": latest,
            "total_sites": total_sites,
            "reporting": reporting,
            "avg_buffer": round(buf, 1) if buf else 0,
            "total_fuel": round(fuel, 0) if fuel else 0,
            "alerts": alerts_count,
            "sectors": {r["sector_id"]: {"sites": r["sites"], "gens": r["gens"]} for r in sectors},
        }


# ─── Welcome Alert ───────────────────────────────────────────────────────────
ui.alert(
    title="Welcome to CityBCPAgent",
    description="Business Continuity Planning dashboard for generator and fuel management. Use the navigation below to explore sectors, sites, and AI-powered insights.",
    key="welcome",
)

# ─── Hero Banner ─────────────────────────────────────────────────────────────
kpis = load_home_kpis()

sector_summary = " | ".join(
    f"{sid}: {info['sites']} sites, {info['gens']} gens"
    for sid, info in kpis.get("sectors", {}).items() if info["sites"] > 0
)

st.html(f"""
<div class="hero-banner">
    <h1>{DASHBOARD["page_icon"]} City BCP Agent</h1>
    <p>Business Continuity Planning — Generator & Fuel Management Dashboard</p>
    <div class="hero-stats">
        {kpis.get('total_sites', 0)} Sites | {sum(s['gens'] for s in kpis.get('sectors', {}).values())} Generators |
        {len([s for s in kpis.get('sectors', {}).values() if s['sites'] > 0])} Active Sectors |
        Data through {kpis.get('latest_date', 'N/A')}
    </div>
</div>
""")

# ─── KPI Cards (shadcn metric_card) ─────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    reporting = kpis.get("reporting", 0)
    total_sites = max(kpis.get("total_sites", 1), 1)
    pct = round(reporting / total_sites * 100)
    ui.metric_card(
        title="Sites Reporting",
        content=f"{reporting}/{kpis.get('total_sites', 0)}",
        description=f"{pct}% coverage on {kpis.get('latest_date', 'N/A')}",
        key="mc_sites",
    )

with c2:
    buf = kpis.get("avg_buffer", 0)
    ui.metric_card(
        title="Avg Days of Buffer",
        content=f"{buf:.1f}",
        description="Weighted average across all sites",
        key="mc_buffer",
    )

with c3:
    fuel = kpis.get("total_fuel", 0)
    ui.metric_card(
        title="Total Fuel Used",
        content=f"{fuel:,.0f} L",
        description="Latest reporting date",
        key="mc_fuel",
    )

with c4:
    alerts = kpis.get("alerts", 0)
    ui.metric_card(
        title="Active Alerts",
        content=str(alerts),
        description="Unacknowledged alerts",
        key="mc_alerts",
    )

# ─── Navigation Grid (shadcn buttons) ───────────────────────────────────────
st.markdown("---")
st.markdown("### Dashboard Pages")

NAV_ITEMS = [
    {"icon": "📊", "title": "Sector Overview", "desc": "Compare CP vs CMHL vs CFC at a glance", "page": "pages/01_Sector_Overview.py"},
    {"icon": "🏢", "title": "Site Detail", "desc": "Deep dive into any site's generators & fuel", "page": "pages/02_Site_Detail.py"},
    {"icon": "⛽", "title": "Fuel Price", "desc": "Price trends, supplier comparison, forecasts", "page": "pages/03_Fuel_Price.py"},
    {"icon": "🛢️", "title": "Buffer & Stockout Risk", "desc": "Which sites are running low on fuel", "page": "pages/04_Buffer_Risk.py"},
    {"icon": "🔌", "title": "Blackout Monitor", "desc": "Power outage patterns & generator coverage", "page": "pages/05_Blackout_Monitor.py"},
    {"icon": "⚙️", "title": "Generator Fleet", "desc": "Utilization, efficiency & anomaly detection", "page": "pages/06_Generator_Fleet.py"},
    {"icon": "🛡️", "title": "BCP Scores", "desc": "Business continuity risk scores per site", "page": "pages/07_BCP_Scores.py"},
    {"icon": "🧠", "title": "AI Insights", "desc": "AI briefing, chat agent & alerts center", "page": "pages/08_AI_Insights.py"},
    {"icon": "📤", "title": "Data Entry", "desc": "Manual data entry forms for daily operations", "page": "pages/09_Data_Entry.py"},
]

rows = [NAV_ITEMS[i:i+3] for i in range(0, len(NAV_ITEMS), 3)]
for row in rows:
    cols = st.columns(3)
    for idx, item in enumerate(row):
        with cols[idx]:
            if ui.button(
                text=f"{item['icon']} {item['title']} — {item['desc']}",
                variant="outline",
                key=f"nav_{item['title']}",
            ):
                st.switch_page(item["page"])

# ─── System Status (shadcn badges) ──────────────────────────────────────────
st.markdown("---")
st.markdown("### System Status")

s1, s2, s3 = st.columns(3)

with s1:
    db_exists = DB_PATH.exists()
    size = f"{DB_PATH.stat().st_size / 1024:.0f} KB" if db_exists else "N/A"
    ui.badges(
        badge_list=[
            ("Database", "default" if db_exists else "destructive"),
            (f"SQLite WAL | {size}", "secondary"),
        ],
        key="badge_db",
    )

with s2:
    has_key = bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
    label = "Connected" if has_key else "No API key"
    ui.badges(
        badge_list=[
            ("LLM API", "default" if has_key else "outline"),
            (label, "secondary" if has_key else "destructive"),
        ],
        key="badge_llm",
    )

with s3:
    date_str = kpis.get("latest_date", "N/A")
    fresh = date_str != "N/A"
    ui.badges(
        badge_list=[
            ("Data Freshness", "default" if fresh else "destructive"),
            (f"Latest: {date_str}", "secondary"),
        ],
        key="badge_data",
    )

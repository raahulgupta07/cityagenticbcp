"""
Sector Economics v2 — Group > Sector > Company > Site
Tabs for Group/Sector/Company. Dropdown for Site detail.
Hierarchy from Excel: business_sector, company, site_id, cost_center_name.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import numpy as np
from utils.database import get_db
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from utils.echarts import (
    grouped_bar, stacked_bar, line_chart as ec_line,
    dual_axis_chart, pie_chart as ec_pie, horizontal_bar as ec_hbar,
    bar_chart as ec_bar, SECTOR_COLORS, PALETTE,
)
from config.settings import SECTORS, HEATMAP_COLORS
from utils.charts import _get_heatmap_color, _get_heatmap_label
from utils.smart_table import render_smart_table, _render_download
from models.energy_cost import get_store_economics, get_generator_detail, get_trends
from models.decision_engine import (
    get_operating_modes, get_delivery_queue,
    get_weekly_budget_forecast, get_supplier_buy_signal, run_what_if,
    get_generator_failure_risk, get_consumption_anomalies,
    get_load_optimization, get_resource_sharing_opportunities,
)
from models.bcp_engine import compute_bcp_scores
from models.buffer_predictor import get_critical_sites
from models.fuel_price_forecast import forecast_fuel_price
from utils.ai_agent import morning_briefing, kpi_insight, table_insight, site_insight, render_insight_box
from models.energy_cost import get_mapping_status
from alerts.alert_engine import get_active_alerts
from config.settings import SECTORS as SECTOR_CFG

st.set_page_config(page_title="BCP Command Center", page_icon="🛡️", layout="wide")
require_login()
render_sidebar_user()
render_page_header("🛡️", "BCP Command Center", "Group > Sector > Company > Site drill-down")


def _chart_guide(formula: str, sources: list, reading: list, explain: str):
    """Render chart guide card with 4 sections: Formula, Source table, Reading, Explain.

    Args:
        formula: Plain English formula with example. Use <c> for column names,
                 <f> for file names, <b> for bold/numbers, <g> for gold badges.
        sources: List of dicts: [{"data": "Diesel Used", "file": "Blackout Hr Excel",
                 "col": "Daily Used", "method": "SUM"}]
        reading: List of tuples: [("green", "Above 7 days = Safe, no action"),
                 ("amber", "3-7 days = Warning"), ("red", "Below 3 = CRITICAL")]
        explain: Plain English analogy. Use <g> green, <a> amber, <r> red, <b> bold.
    """
    # Color tag replacements
    def _t(s):
        return (s.replace("<c>", '<span style="color:#22d3ee">').replace("</c>", "</span>")
                 .replace("<f>", '<span style="color:#4ade80">').replace("</f>", "</span>")
                 .replace("<b>", '<span style="color:#fff;font-weight:700">').replace("</b>", "</span>")
                 .replace("<g>", '<span style="color:#22c55e;font-weight:600">').replace("</g>", "</span>")
                 .replace("<a>", '<span style="color:#f59e0b;font-weight:600">').replace("</a>", "</span>")
                 .replace("<r>", '<span style="color:#ef4444;font-weight:600">').replace("</r>", "</span>")
                 .replace("<badge>", '<span style="background:#fbbf24;color:#0a0a0a;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700">')
                 .replace("<badge-avg>", '<span style="background:#a78bfa;color:#0a0a0a;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700">')
                 .replace("<badge-latest>", '<span style="background:#fb923c;color:#0a0a0a;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700">')
                 .replace("</badge>", "</span>").replace("</badge-avg>", "</span>").replace("</badge-latest>", "</span>"))

    # Reading icon colors
    _rc = {"green": "#22c55e", "amber": "#f59e0b", "red": "#ef4444", "blue": "#60a5fa", "orange": "#f97316"}

    # Source rows using div grid (Streamlit strips <table> tags)
    src_rows = ""
    for s in sources:
        m = s.get("method", "SUM")
        badge_bg = "#a78bfa" if "AVG" in m.upper() else ("#fb923c" if "LATEST" in m.upper() else "#fbbf24")
        src_rows += f'''<div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:4px;padding:3px 0;border-bottom:1px solid #1e293b;align-items:center">
            <span style="color:#22d3ee;font-size:11px">{s["data"]}</span>
            <span style="color:#4ade80;font-size:11px">{s["file"]}</span>
            <span style="color:#22d3ee;font-size:11px">"{s["col"]}"</span>
            <span style="background:{badge_bg};color:#0a0a0a;border-radius:3px;padding:1px 6px;font-size:10px;font-weight:700">{m}</span>
        </div>'''

    # Reading lines
    read_html = ""
    for color, text in reading:
        c = _rc.get(color, "#94a3b8")
        read_html += f'<div style="color:{c};padding:2px 0">{text}</div>'

    html = f'''<div style="background:#0a0a0a;border:1px solid #1a3a2a;border-radius:10px;padding:16px 20px;
        margin:4px 0 14px;font-size:11.5px;line-height:1.7;font-family:system-ui,-apple-system,sans-serif">

        <div style="color:#60a5fa;font-weight:700;font-size:12px;margin-bottom:4px">Formula</div>
        <div style="color:#cbd5e1;padding-left:12px;margin-bottom:10px">{_t(formula)}</div>

        <div style="color:#34d399;font-weight:700;font-size:12px;margin-bottom:4px">Data Source</div>
        <div style="margin:0 0 10px 12px;font-size:11px">
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:4px;padding:3px 0;border-bottom:1px solid #334155">
                <span style="color:#64748b;font-weight:600;font-size:10px">Data</span>
                <span style="color:#64748b;font-weight:600;font-size:10px">File</span>
                <span style="color:#64748b;font-weight:600;font-size:10px">Column</span>
                <span style="color:#64748b;font-weight:600;font-size:10px">Method</span>
            </div>
            {src_rows}
        </div>

        <div style="color:#fbbf24;font-weight:700;font-size:12px;margin-bottom:4px">How to Read</div>
        <div style="padding-left:12px;margin-bottom:10px">{read_html}</div>

        <div style="color:#f472b6;font-weight:700;font-size:12px;margin-bottom:4px">Simple Explanation</div>
        <div style="color:#cbd5e1;padding-left:12px">{_t(explain)}</div>
    </div>'''
    import streamlit.components.v1 as components
    full = f'<html><body style="margin:0;padding:0;background:transparent">{html}</body></html>'
    est_h = 140 + len(sources) * 32 + len(reading) * 22 + 70
    components.html(full, height=est_h, scrolling=False)


def _chart_info(what: str, source: str, reading: str):
    """Legacy wrapper — kept for any remaining calls during migration."""
    st.markdown(f"""<div style="background:#0d1117;border-radius:8px;padding:10px 14px;margin:2px 0 10px;
        font-size:11px;line-height:1.7;border:1px solid #1e293b">
        <span style="color:#60a5fa;font-weight:600">📐 What it shows:</span> <span style="color:#e2e8f0">{what}</span><br>
        <span style="color:#34d399;font-weight:600">📁 Data from:</span> <span style="color:#94a3b8">{source}</span><br>
        <span style="color:#fbbf24;font-weight:600">💡 How to read:</span> <span style="color:#94a3b8">{reading}</span>
    </div>""", unsafe_allow_html=True)

# ─── Data check ──────────────────────────────────────────────────────────
with get_db() as conn:
    if not conn.execute("SELECT COUNT(*) FROM daily_site_summary").fetchone()[0]:
        st.warning("No diesel data. Upload blackout Excel files via **Data Entry**.")
        st.stop()

# ─── Filters: Quick Date + Date Range + Site Type ────────────────────────
from datetime import datetime, timedelta

with get_db() as conn:
    dr = conn.execute("SELECT MIN(date), MAX(date) FROM daily_site_summary").fetchone()
    _all_types = [r[0] for r in conn.execute("SELECT DISTINCT site_type FROM sites WHERE site_type IS NOT NULL ORDER BY site_type").fetchall()]
_db_min = dr[0] if dr and dr[0] else None
_db_max = dr[1] if dr and dr[1] else None
_max_date = datetime.strptime(_db_max, "%Y-%m-%d").date() if _db_max else datetime.now().date()
_min_date = datetime.strptime(_db_min, "%Y-%m-%d").date() if _db_min else _max_date - timedelta(days=60)
_default_from = max(_min_date, _max_date - timedelta(days=59))  # default 60 days

# Quick filter buttons
def _set_dates(from_d, to_d):
    """Set date filter and rerun."""
    st.session_state["v2_from"] = max(from_d, _min_date)
    st.session_state["v2_to"] = min(to_d, _max_date)

qf1, qf2, qf3, qf4, qf5, qf6, qf7 = st.columns(7)
with qf1:
    if st.button("Yesterday", key="qf_1d", use_container_width=True):
        _set_dates(_max_date, _max_date); st.rerun()
with qf2:
    if st.button("Last 3 Days", key="qf_3d", use_container_width=True):
        _set_dates(_max_date - timedelta(days=2), _max_date); st.rerun()
with qf3:
    if st.button("Last 7 Days", key="qf_7d", use_container_width=True):
        _set_dates(_max_date - timedelta(days=6), _max_date); st.rerun()
with qf4:
    if st.button("Last 14 Days", key="qf_14d", use_container_width=True):
        _set_dates(_max_date - timedelta(days=13), _max_date); st.rerun()
with qf5:
    if st.button("Last 30 Days", key="qf_30d", use_container_width=True):
        _set_dates(_max_date - timedelta(days=29), _max_date); st.rerun()
with qf6:
    if st.button("Last 60 Days", key="qf_60d", use_container_width=True):
        _set_dates(_max_date - timedelta(days=59), _max_date); st.rerun()
with qf7:
    if st.button("All Data", key="qf_all", use_container_width=True):
        _set_dates(_min_date, _max_date); st.rerun()

# Initialize defaults (60 days) on first load
if "v2_from" not in st.session_state:
    st.session_state["v2_from"] = _default_from
if "v2_to" not in st.session_state:
    st.session_state["v2_to"] = _max_date

# Date inputs + Type filter
fc1, fc2, fc3 = st.columns([2, 2, 1])
with fc1:
    d_from = st.date_input("From", min_value=_min_date, max_value=_max_date, key="v2_from")
with fc2:
    d_to = st.date_input("To", min_value=_min_date, max_value=_max_date, key="v2_to")
with fc3:
    _type_options = ["All"] + _all_types
    _type_sel = st.selectbox("Site Type", _type_options, key="v2_type_filter")

str_from = str(d_from)
str_to = str(d_to)

# ─── Load data ───────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def _load(sf, st_):
    e = get_store_economics(date_from=sf, date_to=st_)
    if e.empty: return e, 0
    with get_db() as conn:
        # Date-specific price: for each sector, list of (date, price) sorted by date
        # price_on_date(sector, date) returns the most recent price on or before that date
        _price_history = {}
        _ph_rows = conn.execute("""
            SELECT sector_id, date, AVG(price_per_liter) as price
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id, date ORDER BY sector_id, date
        """).fetchall()
        for r in _ph_rows:
            _price_history.setdefault(r[0], []).append((r[1], r[2]))
        # Latest price per sector (fallback)
        pm = {}
        for sid, prices in _price_history.items():
            pm[sid] = prices[-1][1]  # last entry = latest date
        # Global latest
        fp = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL ORDER BY date DESC LIMIT 1").fetchone()
        fp = fp[0] if fp else 0
        ly = pd.read_sql_query("SELECT s.site_id, de.pct_on_sales as ly_diesel_pct FROM sites s JOIN diesel_expense_ly de ON s.cost_center_code = de.cost_center_code", conn)
        # Blackout = SUM(blackout_hr) ÷ number_of_days per site
        # (blackout_hr is site-level, stored on first generator row only, so MAX per date)
        bo_q = """SELECT site_id,
                   SUM(max_bo) * 1.0 / COUNT(DISTINCT date) as blackout_hr
            FROM (
                SELECT do.site_id, do.date, MAX(do.blackout_hr) as max_bo
                FROM daily_operations do
                WHERE do.blackout_hr IS NOT NULL"""
        bp = []
        if sf: bo_q += " AND do.date >= ?"; bp.append(sf)
        if st_: bo_q += " AND do.date <= ?"; bp.append(st_)
        bo_q += " GROUP BY do.site_id, do.date) sub GROUP BY site_id"
        bo = pd.read_sql_query(bo_q, conn, params=bp)
        # Site hierarchy + type
        hier = pd.read_sql_query("SELECT site_id, business_sector, company, site_type FROM sites", conn)
        # Per-site price
        ss = pd.read_sql_query("SELECT g.site_id, s.sector_id, g.supplier, g.fuel_type FROM generators g JOIN sites s ON g.site_id = s.site_id WHERE g.is_active = 1 AND g.supplier IS NOT NULL GROUP BY g.site_id", conn)
        pq = "SELECT sector_id, supplier, fuel_type, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL"
        pp = []
        if sf: pq += " AND date >= ?"; pp.append(sf)
        if st_: pq += " AND date <= ?"; pp.append(st_)
        ap = pd.read_sql_query(pq + " ORDER BY date DESC", conn, params=pp)
    pl, sa = {}, {}
    if not ap.empty:
        for _, p in ap.groupby(["sector_id","supplier","fuel_type"]).first().reset_index().iterrows():
            pl[(p["sector_id"],p["supplier"],p["fuel_type"])] = p["price_per_liter"]
        sa = dict(ap.groupby("sector_id")["price_per_liter"].first())  # latest price (data is ORDER BY date DESC)
    spm = {}
    for _, r in ss.iterrows():
        k = (r["sector_id"],r["supplier"],r["fuel_type"])
        px = pl.get(k)
        if px is None:
            for kk,vv in pl.items():
                if kk[0]==r["sector_id"] and kk[1]==r["supplier"]: px=vv; break
        spm[r["site_id"]] = px or sa.get(r["sector_id"],0)
    e["margin_pct"] = np.where(e["total_sales"].notna()&(e["total_sales"]>0),(e["total_margin"]/e["total_sales"]*100),None)
    e["daily_diesel_cost"] = e.apply(lambda r:(r["avg_daily_liters"] or 0)*pm.get(r["sector_id"],fp),axis=1)
    e["avg_daily_sales"] = np.where(e["total_sales"].notna()&(e["energy_days"]>0),e["total_sales"]/e["energy_days"],None)
    e["diesel_price"] = e["site_id"].map(spm)
    e["diesel_price"] = e.apply(lambda r:r["diesel_price"] if pd.notna(r["diesel_price"]) else sa.get(r["sector_id"],0),axis=1)
    if not ly.empty: e = e.merge(ly,on="site_id",how="left")
    else: e["ly_diesel_pct"] = None
    if not bo.empty: e = e.merge(bo,on="site_id",how="left")
    else: e["blackout_hr"] = None
    if not hier.empty: e = e.merge(hier,on="site_id",how="left")
    else: e["business_sector"]=None; e["company"]=None; e["site_type"]=None
    return e, fp, _price_history

econ, fuel_price, _price_history = _load(str_from, str_to)

def _price_on_date(sector_id, date_str):
    """Get the most recent fuel price for a sector on or before a given date."""
    prices = _price_history.get(sector_id, [])
    if not prices:
        return fuel_price  # global fallback
    # prices is sorted by date ascending: [(date, price), ...]
    result = prices[0][1]  # earliest price as default
    for d, p in prices:
        if d <= date_str:
            result = p
        else:
            break
    return result
if econ.empty:
    st.warning("No data.")
    st.stop()

# ─── Apply type filter ───────────────────────────────────────────────────
def _date_sql(col="date", prefix="AND"):
    """Return SQL date filter clause + params based on str_from/str_to."""
    sql, params = "", []
    if str_from:
        sql += f" {prefix} {col} >= ?"
        params.append(str_from)
    if str_to:
        sql += f" AND {col} <= ?"
        params.append(str_to)
    return sql, params

if _type_sel != "All" and "site_type" in econ.columns:
    econ = econ[econ["site_type"] == _type_sel]
    if econ.empty:
        st.warning(f"No sites with type '{_type_sel}'.")
        st.stop()

# ─── Helpers ─────────────────────────────────────────────────────────────
def _cc(v,m):
    l=_get_heatmap_label(v,m)
    return f'<td style="text-align:center;padding:6px 8px;font-weight:600;font-size:12px;border-bottom:1px solid #e5e7eb">{l}</td>'
def _td(v,f=""):
    if v is None or (isinstance(v,float) and v!=v): return '<td style="text-align:center;padding:6px 8px;color:#9ca3af;font-size:12px">—</td>'
    if f=="M": return f'<td style="text-align:right;padding:6px 8px;font-size:12px">{v/1e6:,.1f}M</td>'
    if f=="M2": return f'<td style="text-align:right;padding:6px 8px;font-size:12px">{v/1e6:,.2f}M</td>'
    if f=="pct1": return f'<td style="text-align:center;padding:6px 8px;font-size:12px">{v:.1f}%</td>'
    if f=="int": return f'<td style="text-align:right;padding:6px 8px;font-size:12px">{v:,.0f}</td>'
    return f'<td style="text-align:center;padding:6px 8px;font-size:12px">{v}</td>'
DR={"Diesel Price":"diesel_price","Blackout Hr":"blackout_hr","Exp% of Sale":"expense_pct","Buffer Day":"buffer_days"}


def _type_comparison(df, key_prefix="grp"):
    """Regular vs LNG side-by-side comparison cards + charts."""
    if "site_type" not in df.columns or df["site_type"].nunique() < 2:
        return

    types = sorted(df["site_type"].dropna().unique())
    if len(types) < 2:
        return

    st.markdown("## ⚡ Regular vs LNG Comparison")

    # Build stats per type
    stats = []
    for t in types:
        td = df[df["site_type"] == t]
        n = len(td)
        ab = td[(td["avg_daily_liters"].notna()) & (td["avg_daily_liters"] > 0)]
        hb = ab[(ab["diesel_available"].notna()) & (ab["diesel_available"] > 0)]
        tank = hb["diesel_available"].sum() if not hb.empty else 0
        burn = ab["avg_daily_liters"].sum() if not ab.empty else 0
        buf = (tank / burn) if burn > 0 else None
        cost = td["energy_cost"].sum()
        ma = td[td["has_sales"] == True]
        sales = ma["total_sales"].sum() if not ma.empty else 0
        epct = (cost / sales * 100) if sales > 0 else 0
        crit = len(hb[hb["latest_buffer_days"] < 3]) if not hb.empty else 0
        warn = len(hb[(hb["latest_buffer_days"] >= 3) & (hb["latest_buffer_days"] < 7)]) if not hb.empty else 0
        safe = len(hb[hb["latest_buffer_days"] >= 7]) if not hb.empty else 0
        avg_eff = (td["total_liters"].sum() / max(td["total_gen_hours"].sum(), 1)) if td["total_gen_hours"].sum() > 0 else 0
        stats.append({"type": t, "sites": n, "tank": tank, "burn": burn, "buffer": buf,
                       "cost": cost, "sales": sales, "diesel_pct": epct,
                       "critical": crit, "warning": warn, "safe": safe, "efficiency": avg_eff})

    # Side-by-side cards
    cols = st.columns(len(types))
    for i, s in enumerate(stats):
        t = s["type"]
        buf_c = "#dc2626" if s["buffer"] and s["buffer"] < 3 else "#d97706" if s["buffer"] and s["buffer"] < 7 else "#16a34a" if s["buffer"] else "#6b7280"
        icon = "⛽" if t == "Regular" else "🔋"
        with cols[i]:
            st.markdown(f"""
            <div style="background:#0f172a;color:white;border-radius:12px;padding:16px;border-left:4px solid {buf_c}">
                <div style="font-size:16px;font-weight:700;margin-bottom:10px">{icon} {t} ({s['sites']} sites)</div>
                <div style="display:flex;flex-wrap:wrap;gap:8px">
                    <div style="flex:1;min-width:80px;background:{buf_c};border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{f"{s['buffer']:.1f}" if s['buffer'] else '—'}</div>
                        <div style="font-size:10px;opacity:0.9">Buffer Days</div>
                    </div>
                    <div style="flex:1;min-width:80px;background:#1e293b;border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{s['tank']:,.0f}</div>
                        <div style="font-size:10px;opacity:0.8">Tank (L)</div>
                    </div>
                    <div style="flex:1;min-width:80px;background:#1e293b;border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{s['burn']:,.0f}</div>
                        <div style="font-size:10px;opacity:0.8">Burn/Day (L)</div>
                    </div>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
                    <div style="flex:1;min-width:80px;background:#1e293b;border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{s['cost']/1e6:,.1f}M</div>
                        <div style="font-size:10px;opacity:0.8">Diesel Cost</div>
                    </div>
                    <div style="flex:1;min-width:80px;background:#1e293b;border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{s['sales']/1e6:,.1f}M</div>
                        <div style="font-size:10px;opacity:0.8">Sales</div>
                    </div>
                    <div style="flex:1;min-width:80px;background:#0f766e;border-radius:8px;padding:10px;text-align:center">
                        <div style="font-size:22px;font-weight:700">{s['diesel_pct']:.2f}%</div>
                        <div style="font-size:10px;opacity:0.8">Diesel %</div>
                    </div>
                </div>
                <div style="display:flex;gap:6px;margin-top:8px">
                    <div style="flex:1;background:#dc2626;border-radius:6px;padding:6px;text-align:center;font-size:12px;font-weight:600">🔴 {s['critical']}</div>
                    <div style="flex:1;background:#d97706;border-radius:6px;padding:6px;text-align:center;font-size:12px;font-weight:600">🟡 {s['warning']}</div>
                    <div style="flex:1;background:#16a34a;border-radius:6px;padding:6px;text-align:center;font-size:12px;font-weight:600">🟢 {s['safe']}</div>
                </div>
                <div style="font-size:11px;opacity:0.5;margin-top:8px">Efficiency: {s['efficiency']:.1f} L/Hr</div>
            </div>""", unsafe_allow_html=True)

    # Comparison charts
    type_names = [s["type"] for s in stats]
    c1, c2 = st.columns(2)
    with c1:
        grouped_bar(type_names, [
            {"name": "Tank (L)", "data": [s["tank"] for s in stats], "color": "#3b82f6"},
            {"name": "Burn/Day (L)", "data": [s["burn"] for s in stats], "color": "#ef4444"},
        ], title="Tank & Burn — Regular vs LNG", height=350, key=f"tc_tank_{key_prefix}")
    with c2:
        grouped_bar(type_names, [
            {"name": "Diesel Cost (MMK)", "data": [round(s["cost"]) for s in stats], "color": "#ef4444"},
            {"name": "Sales (MMK)", "data": [round(s["sales"]) for s in stats], "color": "#3b82f6"},
        ], title="Cost vs Sales — Regular vs LNG", height=350, key=f"tc_cost_{key_prefix}")

    c3, c4 = st.columns(2)
    with c3:
        buf_vals = [round(s["buffer"], 1) if s["buffer"] else 0 for s in stats]
        ec_bar(type_names, buf_vals, title="Buffer Days — Regular vs LNG", color="#3b82f6", height=300, key=f"tc_buf_{key_prefix}")
    with c4:
        eff_vals = [round(s["efficiency"], 1) for s in stats]
        ec_bar(type_names, eff_vals, title="Efficiency L/Hr — Regular vs LNG", color="#8b5cf6", height=300, key=f"tc_eff_{key_prefix}")

    # Trend by type (daily)
    with get_db() as conn:
        site_ids = df["site_id"].tolist()
        if site_ids:
            ph = ",".join(["?"] * len(site_ids))
            _dsql, _dp = _date_sql("dss.date")
            trend_df = pd.read_sql_query(f"""
                SELECT dss.date, s.site_type,
                       SUM(dss.total_daily_used) as liters,
                       SUM(dss.spare_tank_balance) as tank,
                       SUM(dss.total_gen_run_hr) as hours
                FROM daily_site_summary dss
                JOIN sites s ON dss.site_id = s.site_id
                WHERE dss.site_id IN ({ph}) AND s.site_type IS NOT NULL{_dsql}
                GROUP BY dss.date, s.site_type ORDER BY dss.date
            """, conn, params=site_ids + _dp)

            if not trend_df.empty and len(trend_df["date"].unique()) >= 3:
                dates = sorted(trend_df["date"].unique())
                tc1, tc2 = st.columns(2)
                with tc1:
                    lines = []
                    for i, t in enumerate(types):
                        tdata = [round(trend_df[(trend_df["date"]==d)&(trend_df["site_type"]==t)]["liters"].sum())
                                 if not trend_df[(trend_df["date"]==d)&(trend_df["site_type"]==t)].empty else 0 for d in dates]
                        lines.append({"name": t, "data": tdata, "color": PALETTE[i % len(PALETTE)]})
                    ec_line(dates, lines, title="Daily Fuel Burn — Regular vs LNG", height=350, key=f"tc_trend_burn_{key_prefix}")
                    _chart_guide(
                        "Total diesel liters used each day, one line per generator type (Regular vs LNG).\nExample: Regular <b>2,500L/day</b> vs LNG <b>800L/day</b>.",
                        [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per type per day"}],
                        [("green", "✅ LNG line lower = LNG generators are more fuel efficient"),
                         ("amber", "⚠️ Lines converging = LNG losing its efficiency advantage"),
                         ("red", "🔴 LNG higher than Regular = Something wrong with LNG units")],
                        "Compares <b>two types of generators</b> — like comparing petrol vs diesel cars. <b>Regular</b> uses standard diesel. <b>LNG</b> uses natural gas and typically burns <g>less fuel</g>. If LNG suddenly uses <r>more than Regular</r>, something needs checking."
                    )
                with tc2:
                    lines2 = []
                    for i, t in enumerate(types):
                        tdata = []
                        for d in dates:
                            sub = trend_df[(trend_df["date"]==d)&(trend_df["site_type"]==t)]
                            tk = sub["tank"].sum() if not sub.empty else 0
                            li = sub["liters"].sum() if not sub.empty else 0
                            tdata.append(round(tk / li, 1) if li > 0 else 0)
                        lines2.append({"name": t, "data": tdata, "color": PALETTE[i % len(PALETTE)]})
                    ec_line(dates, lines2, title="Buffer Days Trend — Regular vs LNG", height=350,
                            mark_lines=[{"value": 7, "label": "Safe", "color": "#16a34a"},
                                        {"value": 3, "label": "Critical", "color": "#dc2626"}],
                            key=f"tc_trend_buf_{key_prefix}")
                    _chart_guide(
                        "Days of fuel remaining, one line per generator type.\nExample: Regular at <b>5 days</b> vs LNG at <b>12 days</b>.",
                        [{"data": "Tank Balance", "file": "Blackout Hr Excel", "col": "Spare Tank Balance", "method": "SUM per type"},
                         {"data": "Daily Burn", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per type"}],
                        [("green", "🟢 Both above green line (7 days) = Both types have enough fuel"),
                         ("amber", "🟡 One type dropping below 7 = That type needs fuel delivery soon"),
                         ("red", "🔴 Below red line (3 days) = Critical, send fuel to those generators NOW")],
                        "Compares how many <b>days of fuel</b> each generator type has left. Like comparing <b>two phone batteries</b> — one might last 2 days, the other 5. If Regular is at <r>3 days</r> but LNG is at <g>12 days</g>, focus fuel delivery on Regular generators first."
                    )


def _kpis(df):
    """Render KPI rows: Total Period, Last Day, Last 3 Days."""
    site_ids = df["site_id"].tolist()

    # Query daily data filtered by date range
    with get_db() as conn:
        placeholders = ",".join(["?"] * len(site_ids))
        date_filter = ""
        date_params = list(site_ids)
        if str_from:
            date_filter += " AND date >= ?"
            date_params.append(str_from)
        if str_to:
            date_filter += " AND date <= ?"
            date_params.append(str_to)

        dates_q = f"SELECT DISTINCT date FROM daily_site_summary WHERE site_id IN ({placeholders}){date_filter} ORDER BY date DESC LIMIT 5"
        dates_rows = conn.execute(dates_q, date_params).fetchall()
        last_dates = [r[0] for r in dates_rows]
        # All dates in filtered range
        all_dates_q = f"SELECT DISTINCT date FROM daily_site_summary WHERE site_id IN ({placeholders}){date_filter} ORDER BY date"
        all_dates_rows = conn.execute(all_dates_q, date_params).fetchall()
        all_dates_list = [r[0] for r in all_dates_rows]
        first_date_str = all_dates_list[0] if all_dates_list else "—"

        daily_df = pd.DataFrame()
        if last_dates:
            dp = ",".join(["?"] * len(last_dates))
            daily_df = pd.read_sql_query(f"""
                SELECT dss.site_id, dss.date, dss.total_daily_used, dss.spare_tank_balance,
                       dss.days_of_buffer, dss.total_gen_run_hr
                FROM daily_site_summary dss
                WHERE dss.site_id IN ({placeholders}) AND dss.date IN ({dp})
            """, conn, params=site_ids + last_dates)

        # Sales per period
        def _get_sales(dates_list):
            if not dates_list: return 0
            dp2 = ",".join(["?"] * len(dates_list))
            r = conn.execute(f"SELECT SUM(sales_amt) FROM daily_sales WHERE site_id IN ({placeholders}) AND date IN ({dp2})",
                              site_ids + dates_list).fetchone()
            return (r[0] or 0) / len(dates_list) if r else 0

        sales_1d = _get_sales(last_dates[:1])
        sales_3d = _get_sales(last_dates[:3])
        sales_5d = _get_sales(last_dates[:5])

    last_date_str = last_dates[0] if last_dates else "—"
    last3_dates = last_dates[:3]
    last5_dates = last_dates[:5]

    def _calc(subset_df):
        if subset_df.empty:
            return {"tank": 0, "burn": 0, "days": None, "crit": 0, "warn": 0, "safe": 0, "sites": 0, "hours": 0}
        tank = subset_df["spare_tank_balance"].sum() or 0
        burn = subset_df["total_daily_used"].sum() or 0
        hours = subset_df["total_gen_run_hr"].sum() or 0
        days = (tank / burn) if burn > 0 else None
        buf = subset_df["days_of_buffer"]
        crit = len(buf[buf < 3].dropna())
        warn = len(buf[(buf >= 3) & (buf < 7)].dropna())
        safe = len(buf[buf >= 7].dropna())
        return {"tank": tank, "burn": burn, "days": days, "crit": crit, "warn": warn, "safe": safe, "sites": len(subset_df), "hours": hours}

    def _calc_avg(dates_subset):
        if not dates_subset or daily_df.empty: return _calc(pd.DataFrame())
        sub = daily_df[daily_df["date"].isin(dates_subset)]
        if sub.empty: return _calc(pd.DataFrame())
        avg = sub.groupby("site_id").agg(
            spare_tank_balance=("spare_tank_balance", "last"),
            total_daily_used=("total_daily_used", "mean"),
            days_of_buffer=("days_of_buffer", "last"),
            total_gen_run_hr=("total_gen_run_hr", "mean"),
        ).reset_index()
        return _calc(avg)

    # Total period (from econ)
    # ALL sites with burn data
    ab = df[(df["avg_daily_liters"].notna()) & (df["avg_daily_liters"] > 0)]
    # Sites with tank data
    hb = ab[(ab["diesel_available"].notna()) & (ab["diesel_available"] > 0)]
    t_tank = hb["diesel_available"].sum() if not hb.empty else 0
    t_burn = ab["avg_daily_liters"].sum() if not ab.empty else 0
    # Buffer = Tank ÷ estimated daily burn (from blackout × rated L/hr)
    # Use est_daily_burn_bo if available, fallback to avg_daily_liters
    t_est_burn = ab["est_daily_burn_bo"].sum() if "est_daily_burn_bo" in ab.columns and ab["est_daily_burn_bo"].sum() > 0 else t_burn
    t_days = (t_tank / t_est_burn) if t_est_burn > 0 else None
    # Critical/Warning/Safe based on blackout-based buffer
    buf_col = "latest_buffer_days"
    sites_with_buf = hb[hb[buf_col].notna()] if buf_col in hb.columns else hb
    t_crit = len(sites_with_buf[sites_with_buf[buf_col] < 3]) if not sites_with_buf.empty else 0
    t_warn = len(sites_with_buf[(sites_with_buf[buf_col] >= 3) & (sites_with_buf[buf_col] < 7)]) if not sites_with_buf.empty else 0
    t_safe = len(sites_with_buf[sites_with_buf[buf_col] >= 7]) if not sites_with_buf.empty else 0
    t_nodata = len(ab) - len(sites_with_buf)  # sites with burn but no buffer calculated
    ma = df[df["has_sales"] == True]
    t_sales = ma["total_sales"].sum() if not ma.empty else 0
    t_diesel = df["energy_cost"].sum()
    t_epct = ma["energy_pct"].mean() if not ma.empty else 0

    # Per-period calcs
    d1 = _calc(daily_df[daily_df["date"] == last_dates[0]]) if last_dates and not daily_df.empty else _calc(pd.DataFrame())
    d1_diesel = d1["burn"] * fuel_price
    d3 = _calc_avg(last3_dates); d3_diesel = d3["burn"] * fuel_price
    d5 = _calc_avg(last5_dates); d5_diesel = d5["burn"] * fuel_price

    _s = "font-size:9px;opacity:0.65;margin-top:4px;line-height:1.3"
    _src = "font-size:8px;opacity:0.5;margin-top:3px;border-top:1px solid rgba(255,255,255,0.15);padding-top:3px"

    def _render_kpi_block(title, days, tank, burn, diesel, sales, crit, warn, safe, epct, n_sites, note, nodata=0):
        dc = "#dc2626" if days and days < 3 else "#d97706" if days and days < 7 else "#16a34a"
        dn = max(0, 7 * burn - tank) if burn > 0 else 0
        dn_cost = dn * fuel_price
        if days and days < 3: badge_bg = "#dc2626"; badge_txt = "CRITICAL"
        elif days and days < 7: badge_bg = "#d97706"; badge_txt = "WARNING"
        elif days: badge_bg = "#16a34a"; badge_txt = "SAFE"
        else: badge_bg = "#6b7280"; badge_txt = "NO DATA"
        _c = "border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:16px;text-align:center"
        st.markdown(f"""
        <div style="background:#0f172a;color:white;border-radius:14px;padding:20px;margin-top:16px">
            <!-- Header -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                <div>
                    <span style="font-size:20px;font-weight:800">{title}</span>
                    <span style="opacity:0.5;margin-left:12px;font-size:12px">{note}</span>
                </div>
                <div style="background:{badge_bg};padding:6px 18px;border-radius:20px;font-weight:700;font-size:14px">{badge_txt}: {f'{days:.1f}' if days else '—'} days</div>
            </div>
            <div style="font-size:10px;opacity:0.35;margin-bottom:14px">Source: Tank=Closing Balance | Burn=SUM(Used)÷Days | Buffer=Tank÷(7d Avg Blackout×Rated L/Hr) | Cost=Liters×Date-Specific Price</div>
            <!-- Row 1: Main KPIs -->
            <div style="display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap">
                <div style="flex:1;min-width:145px;background:{dc};{_c}">
                    <div style="font-size:36px;font-weight:800">{f'{days:.1f}' if days else '—'}</div>
                    <div style="font-size:13px;font-weight:600;opacity:0.9">Days of Diesel Left</div>
                    <div style="{_s}">= Tank ÷ (7d Avg BO × Rated L/Hr)</div>
                    <div style="{_src}">Blackout Hr + Gen Specs</div>
                </div>
                <div style="flex:1;min-width:145px;background:#1e293b;{_c}">
                    <div style="font-size:36px;font-weight:800">{tank:,.0f}</div>
                    <div style="font-size:13px;font-weight:600;opacity:0.9">Total Tank (L)</div>
                    <div style="{_s}">= Closing balance last date<br>{n_sites} sites</div>
                    <div style="{_src}">Blackout Hr Excel</div>
                </div>
                <div style="flex:1;min-width:145px;background:#1e293b;{_c}">
                    <div style="font-size:36px;font-weight:800">{burn:,.0f}</div>
                    <div style="font-size:13px;font-weight:600;opacity:0.9">Daily Burn (L)</div>
                    <div style="{_s}">= SUM(Daily Used) ÷ Days<br>= {burn*fuel_price:,.0f} MMK/day</div>
                    <div style="{_src}">Blackout Hr Excel</div>
                </div>
                <div style="flex:1;min-width:145px;background:#7c3aed;{_c}">
                    <div style="font-size:36px;font-weight:800">{dn:,.0f}</div>
                    <div style="font-size:13px;font-weight:600;opacity:0.9">Diesel Needed (L)</div>
                    <div style="{_s}">= 7×Burn − Tank<br>Cost: {dn_cost/1e6:,.2f}M</div>
                    <div style="{_src}">Blackout + Fuel Price</div>
                </div>
            </div>
            <!-- Row 2: Status + Financials -->
            <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
                <div style="flex:1;min-width:100px;background:#dc2626;{_c}">
                    <div style="font-size:28px;font-weight:700">{crit}</div>
                    <div style="font-size:11px;font-weight:600">Critical Sites</div>
                    <div style="font-size:9px;opacity:0.7">Buffer &lt; 3 days</div>
                </div>
                <div style="flex:1;min-width:100px;background:#d97706;{_c}">
                    <div style="font-size:28px;font-weight:700">{warn}</div>
                    <div style="font-size:11px;font-weight:600">Warning Sites</div>
                    <div style="font-size:9px;opacity:0.7">Buffer 3–7 days</div>
                </div>
                <div style="flex:1;min-width:100px;background:#16a34a;{_c}">
                    <div style="font-size:28px;font-weight:700">{safe}</div>
                    <div style="font-size:11px;font-weight:600">Safe Sites</div>
                    <div style="font-size:9px;opacity:0.7">Buffer &gt; 7 days</div>
                </div>
                <div style="flex:1;min-width:80px;background:#6b7280;{_c}">
                    <div style="font-size:28px;font-weight:700">{nodata}</div>
                    <div style="font-size:11px;font-weight:600">No Data</div>
                    <div style="font-size:9px;opacity:0.7">No tank/blackout</div>
                </div>
                <div style="flex:1;min-width:120px;background:#1e293b;{_c}">
                    <div style="font-size:28px;font-weight:700">{sales/1e6:,.1f}M</div>
                    <div style="font-size:11px;font-weight:600">Total Sales</div>
                    <div style="font-size:9px;opacity:0.7">SALES_AMT</div>
                </div>
                <div style="flex:1;min-width:120px;background:#1e293b;{_c}">
                    <div style="font-size:28px;font-weight:700">{diesel/1e6:,.1f}M</div>
                    <div style="font-size:11px;font-weight:600">Diesel Cost</div>
                    <div style="font-size:9px;opacity:0.7">Liters × Price</div>
                </div>
                <div style="flex:1;min-width:110px;background:#0f766e;{_c}">
                    <div style="font-size:28px;font-weight:700">{epct:.2f}%</div>
                    <div style="font-size:11px;font-weight:600">Diesel % of Sales</div>
                    <div style="font-size:9px;opacity:0.7">Cost ÷ Sales</div>
                </div>
            </div>
            <!-- Quick Reference -->
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:12px 16px">
                <div style="font-size:12px;font-weight:700;color:#94a3b8;margin-bottom:6px">📖 Quick Reference</div>
                <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:11px;line-height:1.7">
                    <div style="flex:1;min-width:180px">
                        <div style="color:#64748b;font-weight:600;margin-bottom:3px">Buffer Status</div>
                        <div><span style="color:#dc2626;font-weight:700">● CRITICAL</span> — &lt; 3 days → Send fuel NOW</div>
                        <div><span style="color:#d97706;font-weight:700">● WARNING</span> — 3–7 days → Plan delivery</div>
                        <div><span style="color:#16a34a;font-weight:700">● SAFE</span> — &gt; 7 days → Normal ops</div>
                    </div>
                    <div style="flex:1;min-width:180px">
                        <div style="color:#64748b;font-weight:600;margin-bottom:3px">Operating Mode</div>
                        <div><span style="color:#16a34a;font-weight:700">● OPEN</span> — Diesel &lt; 5% of Sales</div>
                        <div><span style="color:#d97706;font-weight:700">● MONITOR</span> — 5–15%</div>
                        <div><span style="color:#ea580c;font-weight:700">● REDUCE</span> — 15–30%</div>
                        <div><span style="color:#dc2626;font-weight:700">● CLOSE</span> — &gt; 60%</div>
                    </div>
                    <div style="flex:1;min-width:180px">
                        <div style="color:#64748b;font-weight:600;margin-bottom:3px">Heatmap Thresholds</div>
                        <div><span style="color:#22c55e;font-weight:700">● Green</span> Price &lt;3.5K | BO &lt;4h | Exp &lt;0.9% | Buf 7+d</div>
                        <div><span style="color:#eab308;font-weight:700">● Yellow</span> 3.5–5K | 4–8h | 0.9–1.5% | 5–7d</div>
                        <div><span style="color:#f97316;font-weight:700">● Amber</span> 5–8K | 8–12h | 1.5–3% | 3–5d</div>
                        <div><span style="color:#ef4444;font-weight:700">● Red</span> &gt;8K | &gt;12h | &gt;3% | &lt;3d</div>
                    </div>
                    <div style="flex:1;min-width:180px">
                        <div style="color:#64748b;font-weight:600;margin-bottom:3px">Key Formulas</div>
                        <div style="color:#cbd5e1">Buffer = Tank ÷ (7d Avg Blackout × Rated L/Hr)</div>
                        <div style="color:#cbd5e1">Needed = 7 × Burn − Tank</div>
                        <div style="color:#cbd5e1">Diesel% = (L × Price) ÷ Sales × 100</div>
                        <div style="color:#cbd5e1">Variance = Actual − (Rated × Hours)</div>
                    </div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    d1_epct = (d1_diesel / sales_1d * 100) if sales_1d > 0 else 0
    d3_epct = (d3_diesel / sales_3d * 100) if sales_3d > 0 else 0
    d5_epct = (d5_diesel / sales_5d * 100) if sales_5d > 0 else 0

    _render_kpi_block("TOTAL PERIOD", t_days, t_tank, t_burn, t_diesel, t_sales, t_crit, t_warn, t_safe, t_epct, len(ab),
                      f"{first_date_str} → {last_date_str} | {len(all_dates_list)} days | {len(df)} sites",
                      nodata=t_nodata)

    # AI KPI Insight (only on button click from morning briefing)
    if st.session_state.get("_show_briefing"):
        _kpi_data = {"buffer": t_days, "tank": t_tank, "burn": t_burn, "critical": t_crit,
                     "warning": t_warn, "safe": t_safe, "diesel_cost": f"{t_diesel/1e6:,.1f}M",
                     "sales": f"{t_sales/1e6:,.1f}M", "diesel_pct": f"{t_epct:.2f}%",
                     "sites": len(ab), "date_range": f"{first_date_str} → {last_date_str}"}
        _kpi_ai = kpi_insight(_kpi_data)
        render_insight_box(_kpi_ai, "🧠 KPI Insight")

    # ─── TOTAL PERIOD TREND CHARTS (10 charts in 5 rows) ────────────
    with get_db() as conn:
        # Daily data by sector for the full period
        tp_q = f"""
            SELECT dss.date, s.sector_id,
                   SUM(dss.total_daily_used) as liters,
                   SUM(dss.total_gen_run_hr) as hours,
                   SUM(dss.spare_tank_balance) as tank,
                   COUNT(DISTINCT dss.site_id) as sites,
                   SUM(CASE WHEN dss.days_of_buffer < 3 AND dss.days_of_buffer IS NOT NULL THEN 1 ELSE 0 END) as critical_cnt
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.site_id IN ({",".join(["?"]*len(site_ids))})
        """
        tp_p = list(site_ids)
        if str_from: tp_q += " AND dss.date >= ?"; tp_p.append(str_from)
        if str_to: tp_q += " AND dss.date <= ?"; tp_p.append(str_to)
        tp_q += " GROUP BY dss.date, s.sector_id ORDER BY dss.date"
        tp_df = pd.read_sql_query(tp_q, conn, params=tp_p)

        # Daily sales
        ts_q = f"SELECT date, SUM(sales_amt) as sales FROM daily_sales WHERE site_id IN ({','.join(['?']*len(site_ids))})"
        ts_p = list(site_ids)
        if str_from: ts_q += " AND date >= ?"; ts_p.append(str_from)
        if str_to: ts_q += " AND date <= ?"; ts_p.append(str_to)
        ts_q += " GROUP BY date ORDER BY date"
        ts_df = pd.read_sql_query(ts_q, conn, params=ts_p)

        # Blackout hours (with site count for averaging)
        bo_q = f"""
            SELECT do.date, s.sector_id,
                   SUM(do.blackout_hr) as blackout_hrs,
                   AVG(do.blackout_hr) as avg_blackout_hr,
                   SUM(do.daily_used_liters) as bo_liters,
                   AVG(do.daily_used_liters) as avg_bo_liters,
                   COUNT(DISTINCT do.site_id) as bo_sites
            FROM daily_operations do
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.blackout_hr IS NOT NULL AND do.site_id IN ({",".join(["?"]*len(site_ids))})
        """
        bo_p = list(site_ids)
        if str_from: bo_q += " AND do.date >= ?"; bo_p.append(str_from)
        if str_to: bo_q += " AND do.date <= ?"; bo_p.append(str_to)
        bo_q += " GROUP BY do.date, s.sector_id ORDER BY do.date"
        bo_df = pd.read_sql_query(bo_q, conn, params=bo_p)

    if not tp_df.empty and len(tp_df["date"].unique()) >= 3:
        all_dates = sorted(tp_df["date"].unique())
        all_sectors = sorted(tp_df["sector_id"].unique())
        # Price per sector for cost calc
        with get_db() as _pc:
            _pm = dict(_pc.execute("""
                SELECT sector_id, price_per_liter FROM fuel_purchases
                WHERE price_per_liter IS NOT NULL AND date = (
                    SELECT MAX(date) FROM fuel_purchases fp2
                    WHERE fp2.sector_id = fuel_purchases.sector_id AND fp2.price_per_liter IS NOT NULL
                ) GROUP BY sector_id
            """).fetchall())
        pm = {s: _pm.get(s, fuel_price) for s in all_sectors}

        # Sites reporting per day (for flagging incomplete days)
        sites_per_day = {d: int(tp_df[tp_df["date"]==d]["sites"].sum()) for d in all_dates}
        max_sites = max(sites_per_day.values()) if sites_per_day else 1
        low_days = [d for d, n in sites_per_day.items() if n < max_sites * 0.7]

        with st.expander("📈 Total Period Trend Charts (click to expand)", expanded=True):
            # Sites reporting indicator
            if low_days:
                st.warning(f"⚠️ **Incomplete reporting days detected:** {', '.join(low_days)} — fewer sites reported, which may distort totals/averages.")
            sites_line = [sites_per_day.get(d, 0) for d in all_dates]
            ec_bar(all_dates, sites_line, title="Sites Reporting per Day", color="#64748b", height=200, key="tp_sites_day")
            _chart_guide(
                f"Count of sites that submitted data each day. Maximum = <b>{max_sites} sites</b>.",
                [{"data": "Site count", "file": "Blackout Hr Excel", "col": "all sites with data on each date", "method": "COUNT"}],
                [("green", f"✅ Full bar ({max_sites} sites) = All sites reported, data is complete"),
                 ("amber", f"⚠️ Short bar (below {int(max_sites*0.7)} sites) = Some sites missing, totals understated"),
                 ("red", "🔴 Very short bar = Most sites didn't report, treat that day's numbers with caution")],
                f"Think of it like <b>attendance</b>. If only half the class shows up, the class average is unreliable. Same here — if only {int(max_sites*0.7)} out of {max_sites} sites reported, the totals for that day are <a>lower than reality</a>. Always check this chart first before trusting a dip in other charts."
            )

            # ── Row 0: Total Gen Hours vs Fuel (all sites combined) | Overall Efficiency ──
            st.markdown("#### Overall — All Sites Combined")
            r0c1, r0c2 = st.columns(2)
            with r0c1:
                total_hrs = [round(tp_df[tp_df["date"]==d]["hours"].sum()) for d in all_dates]
                total_lts = [round(tp_df[tp_df["date"]==d]["liters"].sum()) for d in all_dates]
                dual_axis_chart(all_dates, total_hrs, total_lts,
                                title="Generator Hours vs Fuel Consumption (Total)",
                                bar_name="Gen Hours (hr)", line_name="Fuel Used (L)",
                                bar_color="#3b82f6", line_color="#ef4444", height=380, key="tp_total_hv")
                _chart_guide(
                    "Blue bars = total hours all generators ran. Red line = total diesel liters used across all sites.\nExample: <b>120 hours</b> of generator runtime used <b>1,800 liters</b> of diesel.",
                    [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM all sites"},
                     {"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM all sites"}],
                    [("green", "✅ Both move together = Normal, generators using fuel as expected"),
                     ("amber", "⚠️ Red line rises but bars stay flat = Generators burning too much fuel per hour (waste)"),
                     ("red", "🔴 Red line spikes suddenly = Possible fuel theft or data error, investigate that day")],
                    "Imagine you're tracking a <b>delivery truck</b>. Blue bars = how many hours it drove. Red line = how much petrol it used. Both should go up and down together — more driving = more fuel. If the truck suddenly uses <r>twice the fuel</r> for the same hours, something is wrong: maybe a <r>fuel leak</r>, or someone <r>siphoned fuel</r>. Same logic applies to generators."
                )
            with r0c2:
                overall_eff = [round(tp_df[tp_df["date"]==d]["liters"].sum() / max(tp_df[tp_df["date"]==d]["hours"].sum(), 1), 1) for d in all_dates]
                ec_line(all_dates, [{"name": "Liters per Hour", "data": overall_eff, "color": "#8b5cf6"}],
                        title="Overall Efficiency — Liters per Gen Hour", height=380, key="tp_total_eff")
                _chart_guide(
                    "Total diesel liters ÷ Total generator hours = <b>Liters consumed per hour</b>.\nExample: <b>1,800L</b> ÷ <b>120 hours</b> = <b>15.0 L/Hr</b>.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM all sites"},
                     {"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM all sites"}],
                    [("green", "✅ Flat line (15-20 L/Hr) = Normal, generators are healthy"),
                     ("amber", "⚠️ Spike up (e.g. 15 → 28 L/Hr) = Generators wasting fuel or possible theft"),
                     ("blue", "📉 Drop down = Efficiency improving or lighter load")],
                    "Think of it like your <b>car's km/liter</b>. This shows how many liters of diesel each generator burns per hour. If your car suddenly uses <a>2x more fuel</a> for the same distance — something is wrong. A <g>flat line</g> means generators are <g>healthy</g>. If the line <a>jumps up</a> — either someone is <r>stealing fuel</r>, or a generator needs <a>servicing</a>."
                )

            st.markdown("---")

            # ── Row 1: Daily Fuel (sector lines + total) | Avg Gen Hours per Site ──
            st.markdown("#### By Sector Breakdown")
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                # Fuel as LINE chart per sector + total (cleaner than stacked bar with broken total line)
                fuel_lines = []
                for i, s in enumerate(all_sectors):
                    fdata = [round(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum())
                             if not tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)].empty else 0 for d in all_dates]
                    fuel_lines.append({"name": s, "data": fdata, "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                totals = [round(tp_df[tp_df["date"]==d]["liters"].sum()) for d in all_dates]
                ec_line(all_dates, fuel_lines, title="Daily Fuel Consumption (L) — by Sector", height=380, key="tp_fuel_sec")
                _chart_guide(
                    "Total diesel liters used per day, one line for each sector (CMHL, CFC, CP, PG).\nExample: CMHL uses <b>3,200L/day</b> vs CFC at <b>800L/day</b>.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per sector per day"}],
                    [("green", "✅ Stable lines = Fuel consumption is predictable"),
                     ("amber", "⚠️ One sector rising sharply = More blackouts or waste in that area"),
                     ("red", "🔴 Sudden spike in one sector = Investigate that sector immediately")],
                    "Each colored line is a <b>business sector</b> (like CMHL = City Mart, CFC = restaurants). The <a>highest line</a> is the biggest fuel consumer. If one line suddenly <r>shoots up</r> while others stay flat, that sector had a <r>bad blackout day</r> or is <r>wasting fuel</r>."
                )
            with r1c2:
                # AVG gen hours per site — skip sectors with < 3 sites
                avg_hr_lines = []
                for i, s in enumerate(all_sectors):
                    adata = []
                    for d in all_dates:
                        row = tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]
                        h = row["hours"].sum() if not row.empty else 0
                        n = int(row["sites"].sum()) if not row.empty else 0
                        adata.append(round(h / max(n, 1), 1) if n >= 2 else None)
                    # Replace None with 0 for chart (but shows gap)
                    avg_hr_lines.append({"name": f"{s} (avg)", "data": [v if v is not None else 0 for v in adata],
                                         "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                total_avg = [round(tp_df[tp_df["date"]==d]["hours"].sum() / max(tp_df[tp_df["date"]==d]["sites"].sum(), 1), 1) for d in all_dates]
                # ALL avg line removed — clutters chart
                ec_line(all_dates, avg_hr_lines, title="Avg Generator Hours per Site per Day", height=380, key="tp_hrs_avg")
                _chart_guide(
                    "Total generator hours ÷ Number of sites = <b>Average hours per site per day</b>.\nExample: <b>240 hours</b> across <b>30 sites</b> = <b>8.0 hours/site</b>.",
                    [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM per sector"},
                     {"data": "Site Count", "file": "Blackout Hr Excel", "col": "sites with data", "method": "COUNT per sector"}],
                    [("green", "✅ Low hours (2-4 hr/site) = Light blackout day, manageable"),
                     ("amber", "⚠️ High hours (8+ hr/site) = Heavy blackout day, high fuel burn"),
                     ("red", "🔴 Very high (12+ hr/site) = Severe outage, generators running nearly all day")],
                    "This shows <b>how long each site's generator ran on average</b>. If a sector shows <b>8 hours</b>, it means each store in that sector had their generator running for about 8 hours that day. <a>Higher = worse blackouts</a> in that area. Sectors with less than 2 sites show 0 because the data isn't reliable enough."
                )

            # ── Row 2: Efficiency L/Hr | Diesel Cost Trend (in millions) ──
            st.markdown("#### Efficiency & Cost")
            r2c1, r2c2 = st.columns(2)
            with r2c1:
                # Efficiency — skip 0-hour days to avoid spikes
                eff_lines = []
                for i, s in enumerate(all_sectors):
                    edata = []
                    for d in all_dates:
                        row = tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]
                        h = row["hours"].sum() if not row.empty else 0
                        l = row["liters"].sum() if not row.empty else 0
                        n = int(row["sites"].sum()) if not row.empty else 0
                        # Only show if enough hours and sites to be meaningful
                        edata.append(round(l/h, 1) if h > 10 and n >= 2 else 0)
                    eff_lines.append({"name": s, "data": edata, "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                total_eff = []
                for d in all_dates:
                    th = tp_df[tp_df["date"]==d]["hours"].sum()
                    tl = tp_df[tp_df["date"]==d]["liters"].sum()
                    total_eff.append(round(tl/th, 1) if th > 10 else 0)
                # ALL line removed — clutters chart
                ec_line(all_dates, eff_lines, title="Efficiency — Liters per Gen Hour", height=380, key="tp_eff")
                _chart_guide(
                    "Diesel liters ÷ Generator hours = <b>Liters per hour</b>, one line per sector.\nExample: <b>900L</b> ÷ <b>50 hours</b> = <b>18.0 L/Hr</b>. Zero means not enough data that day.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per sector"},
                     {"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM per sector"}],
                    [("green", "✅ Flat line = Generators in that sector are running efficiently"),
                     ("amber", "⚠️ Rising line = That sector's generators are using more fuel per hour (waste)"),
                     ("red", "🔴 Sudden spike = Possible fuel theft or generator breakdown in that sector")],
                    "Each line shows how <b>efficiently</b> each sector's generators use fuel. Like comparing <b>fuel economy</b> of different car fleets. A <g>flat line</g> means things are normal. If one sector's line <a>starts climbing</a>, those generators are <r>burning more fuel than they should</r> — could be a maintenance issue or theft."
                )
            with r2c2:
                # Diesel cost in MILLIONS for readability
                cost_lines = []
                for i, s in enumerate(all_sectors):
                    cdata = [round(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum() * _price_on_date(s, d) / 1e6, 2)
                             if not tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)].empty else 0 for d in all_dates]
                    cost_lines.append({"name": s, "data": cdata, "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                total_cost = [round(sum(cl["data"][j] for cl in cost_lines), 2) for j in range(len(all_dates))]
                # TOTAL line removed — clutters chart
                ec_line(all_dates, cost_lines, title="Daily Diesel Cost Trend (Million MMK)", height=380, key="tp_cost_trend")
                _chart_guide(
                    "Diesel liters used × Fuel price on that date = <b>Daily diesel cost in millions MMK</b>.\nExample: <b>1,041L</b> × <b>7,085 MMK/L</b> = <b>7.38M MMK</b>.\nNote: Uses the <b>latest purchase price</b> on each date, not an average of all past purchases.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per sector"},
                     {"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "LATEST on date"}],
                    [("green", "✅ Flat or falling = Costs stable or improving"),
                     ("amber", "⚠️ Rising = Either more fuel used OR price went up"),
                     ("red", "🔴 Sharp spike = Check fuel price chart to see which caused it")],
                    "This is your <b>daily fuel bill</b>. Like checking your daily spending — how much money went to diesel today? If the bill <a>suddenly jumps</a>, two possible reasons: stores used <a>more fuel</a> (longer blackout), or the <r>fuel price went up</r>. Compare with the Fuel Price chart to see which one caused the spike."
                )

            # ── Row 3: Sales vs Diesel Cost | Diesel % of Sales ──
            if not ts_df.empty and len(ts_df) >= 3:
                st.markdown("#### Sales & Profitability")
                merged_d = sorted(set(all_dates) & set(ts_df["date"].tolist()))
                if len(merged_d) >= 3:
                    r3c1, r3c2 = st.columns(2)
                    sv_raw = [round(ts_df[ts_df["date"]==d]["sales"].sum()) for d in merged_d]
                    dv_raw = [round(sum(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum() * _price_on_date(s, d) for s in all_sectors)) for d in merged_d]
                    sv = [round(v/1e6, 1) for v in sv_raw]
                    dv = [round(v/1e6, 2) for v in dv_raw]
                    with r3c1:
                        dual_axis_chart(merged_d, sv, dv, title="Sales vs Diesel Cost — Daily (Millions)",
                                        bar_name="Sales (M)", line_name="Diesel (M)",
                                        bar_color="#3b82f6", line_color="#ef4444", height=380, key="tp_svd")
                        _chart_guide(
                            "Blue bars = daily <b>sales revenue</b> (millions). Red line = daily <b>diesel cost</b> (millions).\nExample: Sales <b>200M</b> vs Diesel <b>7.38M</b> = diesel is only 3.7% of sales.",
                            [{"data": "Sales Revenue", "file": "Sales Excel", "col": "SALES_AMT", "method": "SUM per day"},
                             {"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per day"},
                             {"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "LATEST on date"}],
                            [("green", "✅ Big gap between blue and red = Healthy, fuel cost is small vs revenue"),
                             ("amber", "⚠️ Gap shrinking = Fuel is eating into profits, monitor closely"),
                             ("red", "🔴 Red line touching blue bars = Store is losing money on fuel")],
                            "<b>Blue bars = money coming IN</b> (sales). <b>Red line = money going OUT</b> (diesel). The <g>gap between them is your profit</g>. If the red line <a>gets close to the blue bars</a> — the store is barely breaking even on fuel. If red <r>touches or passes blue</r> — you're <r>losing money</r> keeping that store open during blackouts."
                        )
                    with r3c2:
                        dpv = [round(d/s*100, 2) if s > 0 else 0 for s, d in zip(sv_raw, dv_raw)]
                        ec_line(merged_d, [{"name": "Diesel % of Sales", "data": dpv, "color": "#ef4444"}],
                                title="Diesel % of Sales — Daily Trend", height=380, key="tp_dpct")
                        _chart_guide(
                            "Diesel cost ÷ Sales revenue × 100 = <b>Diesel % of Sales</b>.\nExample: <b>7.38M</b> diesel ÷ <b>200M</b> sales × 100 = <b>3.7%</b>.",
                            [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per day"},
                             {"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "LATEST on date"},
                             {"data": "Sales Revenue", "file": "Sales Excel", "col": "SALES_AMT", "method": "SUM per day"}],
                            [("green", "🟢 Below 0.9% = Healthy, diesel cost is tiny compared to revenue"),
                             ("amber", "🟡 0.9% – 1.5% = Watch, fuel starting to eat into margins"),
                             ("orange", "🟠 1.5% – 3% = Reduce hours, fuel cost getting heavy"),
                             ("red", "🔴 Above 3% = Losing money, consider closing during blackouts")],
                            "Out of every <b>100 MMK of sales</b>, how much goes to diesel? If this shows <b>3%</b>, then <a>3 MMK out of every 100 goes to fuel</a>. Under <g>1% is great</g> — diesel is barely noticeable. Over <r>3% means diesel is eating too much profit</r> — consider reducing store hours during blackouts, or the store will <r>lose money</r> just by staying open."
                        )

            # ── Row 4: Buffer Days Trend | Critical Sites Count ──
            # Buffer = Tank ÷ (Blackout Hr × Rated L/hr) per sector per day
            st.markdown("#### Buffer & Risk")
            # Get rated L/hr per sector
            with get_db() as _bc:
                _rated = dict(_bc.execute("""
                    SELECT s.sector_id, SUM(g.consumption_per_hour) as rated
                    FROM generators g JOIN sites s ON g.site_id = s.site_id
                    WHERE g.is_active = 1 GROUP BY s.sector_id
                """).fetchall())
            r4c1, r4c2 = st.columns(2)
            with r4c1:
                buf_lines = []
                for i, s in enumerate(all_sectors):
                    rated_lph = _rated.get(s, 0)
                    bdata = []
                    for d in all_dates:
                        row = tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]
                        tk_d = row["tank"].sum() if not row.empty else 0
                        # Get blackout for this sector on this date
                        bo_row = bo_df[(bo_df["date"]==d)&(bo_df["sector_id"]==s)] if not bo_df.empty else pd.DataFrame()
                        bo_hr = bo_row["avg_blackout_hr"].mean() if not bo_row.empty and pd.notna(bo_row["avg_blackout_hr"].mean()) else 0
                        est_burn = bo_hr * rated_lph
                        bdata.append(round(tk_d / est_burn, 1) if est_burn > 0 else 0)
                    buf_lines.append({"name": s, "data": bdata, "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                ec_line(all_dates, buf_lines, title="Buffer Days Trend by Sector", height=380,
                        mark_lines=[{"value": 7, "label": "Safe", "color": "#16a34a"},
                                    {"value": 3, "label": "Critical", "color": "#dc2626"}],
                        key="tp_buf")
                _chart_guide(
                    "Tank balance ÷ (Average blackout hours × Generator consumption rate) = <b>Days of fuel remaining</b>.\nExample: <b>10,000L</b> ÷ (<b>8 hr</b> × <b>175 L/hr</b>) = <b>7.1 days</b>.",
                    [{"data": "Tank Balance", "file": "Blackout Hr Excel", "col": "Spare Tank Balance", "method": "SUM per sector"},
                     {"data": "Blackout Hours", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "AVG last 7 days"},
                     {"data": "Consumption Rate", "file": "Blackout Hr Excel", "col": "Consumption Per Hour", "method": "SUM all generators"}],
                    [("green", "🟢 Above 7 days (green line) = Safe, no action needed"),
                     ("amber", "🟡 3–7 days = Warning, plan fuel delivery this week"),
                     ("red", "🔴 Below 3 days (red line) = CRITICAL, send fuel NOW")],
                    "Like your <b>phone battery</b>. This shows how many <b>days of fuel</b> each sector has before generators stop. We take the fuel left in tank and divide by how much is burned each day. Below <r>3 days</r> is like <r>5% battery</r> — you MUST refuel immediately or the store <r>goes dark</r>. Above <g>7 days</g> = <g>fully charged</g>, no rush."
                )
            with r4c2:
                crit_data = [round(tp_df[tp_df["date"]==d]["critical_cnt"].sum()) for d in all_dates]
                ec_bar(all_dates, crit_data, title="Critical Sites Count (< 3 days buffer)", color="#dc2626", height=380, key="tp_crit")
                _chart_guide(
                    "Count of sites where fuel will run out in less than <b>3 days</b>.\nExample: <b>4 critical sites</b> on 28-Mar means 4 stores need urgent fuel delivery.",
                    [{"data": "Buffer Days", "file": "Blackout Hr Excel", "col": "Spare Tank Balance ÷ Daily Used", "method": "COUNT where < 3 days"}],
                    [("green", "✅ Zero or low bars = No sites in immediate danger"),
                     ("amber", "⚠️ Rising bars = More sites running low, delivery needed"),
                     ("red", "🔴 High bars = Many sites about to run out, emergency fuel run required")],
                    "Think of it like a <b>warning dashboard in a car fleet</b>. Each bar shows how many vehicles have their <r>fuel light on</r> that day. You want this number to be <g>zero</g>. If it's going up, you need to send the fuel truck to more and more locations."
                )

            # ── Row 5: Avg Blackout Hours vs Avg Fuel | Avg Blackout by Sector ──
            if not bo_df.empty and len(bo_df) >= 3:
                st.markdown("#### Blackout Impact (Averages per Site)")
                bo_dates = sorted(bo_df["date"].unique())
                bo_sectors = sorted(bo_df["sector_id"].unique())
                r5c1, r5c2 = st.columns(2)
                with r5c1:
                    # Average blackout hours and fuel per site per day
                    def _safe(v, dp=0): return round(v, dp) if pd.notna(v) else 0
                    avg_bo_hrs = [_safe(bo_df[bo_df["date"]==d]["avg_blackout_hr"].mean(), 1) if not bo_df[bo_df["date"]==d].empty else 0 for d in bo_dates]
                    avg_bo_lit = [_safe(bo_df[bo_df["date"]==d]["avg_bo_liters"].mean()) if not bo_df[bo_df["date"]==d].empty else 0 for d in bo_dates]
                    dual_axis_chart(bo_dates, avg_bo_hrs, avg_bo_lit,
                                    title="Avg Blackout Hours vs Avg Fuel per Site",
                                    bar_name="Avg Blackout Hr/site", line_name="Avg Fuel L/site",
                                    bar_color="#d97706", line_color="#ef4444", height=380, key="tp_bovf")
                    _chart_guide(
                        "Amber bars = average hours of power outage per site. Red line = average diesel liters used per site.\nExample: <b>8 hr</b> blackout per site, <b>150L</b> diesel per site.",
                        [{"data": "Blackout Hours", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "AVG per site per day"},
                         {"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "AVG per site per day"}],
                        [("green", "✅ Both low = Light blackout day, manageable fuel use"),
                         ("amber", "⚠️ Both rising = Grid situation worsening, more fuel needed"),
                         ("red", "🔴 High blackout but low fuel = Generators may not be running (check site)")],
                        "This shows the <b>average impact on each store</b>. Bars = how many hours the <a>power was out</a>. Red line = how much <a>fuel each store used</a>. If both go up together, it means <r>blackouts are getting worse</r> across the network."
                    )
                with r5c2:
                    # Average blackout hours per site by sector (line chart)
                    bo_lines = []
                    for i, s in enumerate(bo_sectors):
                        bdata = [_safe(bo_df[(bo_df["date"]==d)&(bo_df["sector_id"]==s)]["avg_blackout_hr"].mean(), 1)
                                 if not bo_df[(bo_df["date"]==d)&(bo_df["sector_id"]==s)].empty else 0 for d in bo_dates]
                        bo_lines.append({"name": s, "data": bdata, "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                    # Total avg
                    total_avg_bo = [_safe(bo_df[bo_df["date"]==d]["avg_blackout_hr"].mean(), 1) if not bo_df[bo_df["date"]==d].empty else 0 for d in bo_dates]
                    # ALL line removed — clutters chart
                    ec_line(bo_dates, bo_lines, title="Avg Blackout Hours per Site by Sector", height=380, key="tp_bo_sec")
                    _chart_guide(
                        "Average blackout hours per site, one line for each sector.\nExample: CFC at <b>12 hr</b> vs CMHL at <b>6 hr</b> means CFC area has worse power outages.",
                        [{"data": "Blackout Hours", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "AVG per site per sector"}],
                        [("green", "✅ Lines going down = Grid improving in that area"),
                         ("amber", "⚠️ Lines going up = Power outages getting longer in that sector"),
                         ("red", "🔴 One sector much higher than others = That area has worst power supply")],
                        "Each colored line represents a <b>business sector</b> (area of the city). The <a>highest line</a> has the <r>worst power supply</r>. If one line is climbing while others stay flat, that area's <r>electricity grid is deteriorating</r>. This helps you decide <b>where to stockpile more fuel</b>."
                    )

    # ─── Helper: render FULL trend charts for a rolling window ─────
    def _render_period_charts(dates_subset, title_suffix, chart_key, window=3):
        """Full trend charts matching TOTAL PERIOD style, using rolling N-day averages over ALL dates."""
        if tp_df.empty or len(tp_df["date"].unique()) < window:
            return

        p_dates = sorted(tp_df["date"].unique())

        # Build daily totals across all sectors
        d_liters = [round(tp_df[tp_df["date"]==d]["liters"].sum()) for d in p_dates]
        d_hours = [round(tp_df[tp_df["date"]==d]["hours"].sum()) for d in p_dates]
        d_tank = [round(tp_df[tp_df["date"]==d]["tank"].sum()) for d in p_dates]
        d_crit = [round(tp_df[tp_df["date"]==d]["critical_cnt"].sum()) for d in p_dates]

        # Rolling averages
        def _rolling(vals, w):
            out = []
            for i in range(len(vals)):
                if i < w - 1:
                    out.append(round(sum(vals[:i+1]) / (i+1)))
                else:
                    out.append(round(sum(vals[i-w+1:i+1]) / w))
            return out

        r_liters = _rolling(d_liters, window)
        r_hours = _rolling(d_hours, window)
        r_eff = [round(l/h, 1) if h > 0 else 0 for l, h in zip(r_liters, r_hours)]
        d_eff = [round(l/h, 1) if h > 0 else 0 for l, h in zip(d_liters, d_hours)]
        r_buf = [round(t / max(l, 1), 1) for t, l in zip(d_tank, r_liters)]
        d_buf = [round(t / max(l, 1), 1) for t, l in zip(d_tank, d_liters)]

        # Cost (date-specific pricing)
        d_cost = [round(sum(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum() * _price_on_date(s, d) for s in all_sectors)) for d in p_dates]
        r_cost = _rolling(d_cost, window)

        wlabel = f"{window}-Day Avg"

        with st.expander(f"📈 Charts — {title_suffix} (Daily + {wlabel} Rolling)", expanded=True):
            # ── Rolling Average Trend Lines (dedicated) ─────────
            st.markdown(f"#### 📊 {wlabel} Rolling Average Trends")
            ra1, ra2 = st.columns(2)
            with ra1:
                ec_line(p_dates, [
                    {"name": "Daily Fuel Burn (L)", "data": d_liters, "color": "#fca5a5"},
                    {"name": f"{wlabel} Fuel Burn", "data": r_liters, "color": "#ef4444"},
                ], title=f"Fuel Burn — Daily vs {wlabel}", height=350, key=f"ch_fburn_{chart_key}")
                _chart_guide(
                    f"Light red = daily total diesel used · Dark red = {wlabel} smoothed average.\nExample: daily jumps <b>800→1,200→600</b> but {wlabel} shows steady <b>867L</b>.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": f"SUM all sites + {wlabel} rolling"}],
                    [("green", f"✅ Flat {wlabel} line = Consumption is stable"),
                     ("amber", f"⚠️ Rising {wlabel} line = Fuel consumption trending up"),
                     ("red", f"🔴 Sharp rise in {wlabel} = Urgent, consumption accelerating")],
                    f"Daily numbers bounce around like <b>daily weather</b>. The {wlabel} line is like a <b>weather forecast</b> — it smooths out the noise to show the real trend. If the smooth line is <a>climbing</a>, fuel use is truly increasing (not just a one-day spike). If it's <g>flat</g>, things are <g>stable</g> despite daily ups and downs."
                )
            with ra2:
                ec_line(p_dates, [
                    {"name": "Daily Buffer", "data": d_buf, "color": "#93c5fd"},
                    {"name": f"{wlabel} Buffer", "data": r_buf, "color": "#3b82f6"},
                ], title=f"Buffer Days — Daily vs {wlabel}", height=350,
                   mark_lines=[{"value": 7, "label": "Safe (7d)", "color": "#16a34a"},
                               {"value": 3, "label": "Critical (3d)", "color": "#dc2626"}],
                   key=f"ch_rbuf_{chart_key}")
                _chart_guide(
                    f"Light blue = daily buffer days · Dark blue = {wlabel} smoothed buffer.\nGreen line = <b>7 days</b> (safe) · Red line = <b>3 days</b> (critical).",
                    [{"data": "Buffer Days", "file": "Blackout Hr Excel", "col": "Spare Tank Balance ÷ Daily Used", "method": f"DIV per site + {wlabel} rolling"}],
                    [("green", f"✅ {wlabel} line above 7 days = Comfortable fuel reserves"),
                     ("amber", f"⚠️ {wlabel} line between 3-7 days = Plan a fuel delivery soon"),
                     ("red", f"🔴 {wlabel} line below 3 days = Emergency, order fuel immediately")],
                    f"Think of buffer days like your <b>phone battery percentage</b>. Above <g>7 days</g> is like having <g>70%+ battery</g> — you're fine. Between <a>3-7 days</a> is like <a>30% battery</a> — start looking for a charger. Below <r>3 days</r> is <r>red battery warning</r> — plug in now or you'll go dark."
                )

            ra3, ra4 = st.columns(2)
            with ra3:
                ec_line(p_dates, [
                    {"name": "Daily Gen Hours", "data": d_hours, "color": "#93c5fd"},
                    {"name": f"{wlabel} Gen Hours", "data": r_hours, "color": "#3b82f6"},
                ], title=f"Gen Hours — Daily vs {wlabel}", height=350, key=f"ch_rghr_{chart_key}")
                _chart_guide(
                    f"Light blue = daily total generator hours · Dark blue = {wlabel} smoothed average.\nExample: daily <b>80→120→90</b> but {wlabel} shows steady <b>97 hrs</b>.",
                    [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": f"SUM all sites + {wlabel} rolling"}],
                    [("green", f"✅ Flat {wlabel} line = Generator usage is stable"),
                     ("amber", f"⚠️ Rising {wlabel} line = Generators running longer (more blackouts)"),
                     ("red", f"🔴 Sharp upward {wlabel} = Grid is failing, heavy generator dependency")],
                    f"Generator hours are like a <b>taxi meter</b> — the longer it runs, the more fuel you burn. If the {wlabel} line is <a>climbing</a>, it means blackouts are getting longer or more frequent. A <g>flat line</g> means the grid situation is <g>stable</g>, even if individual days bounce around."
                )
            with ra4:
                ec_line(p_dates, [
                    {"name": "Daily L/Hr", "data": d_eff, "color": "#c4b5fd"},
                    {"name": f"{wlabel} L/Hr", "data": r_eff, "color": "#8b5cf6"},
                ], title=f"Efficiency L/Hr — Daily vs {wlabel}", height=350,
                   mark_lines=[{"value": 1.5, "label": "Waste threshold", "color": "#dc2626"}],
                   key=f"ch_reff_{chart_key}")
                _chart_guide(
                    f"Light purple = daily L/Hr · Dark purple = {wlabel} smoothed efficiency.\nRed line = <b>1.5 L/Hr</b> waste threshold.",
                    [{"data": "Efficiency", "file": "Blackout Hr Excel", "col": "Daily Used ÷ Gen Run Hr", "method": f"DIV totals + {wlabel} rolling"}],
                    [("green", f"✅ {wlabel} line below 1.5 = Generators running efficiently"),
                     ("amber", f"⚠️ {wlabel} line approaching 1.5 = Efficiency declining, monitor closely"),
                     ("red", f"🔴 {wlabel} line above 1.5 = Fuel waste — investigate theft or breakdown")],
                    f"Efficiency is like your car's <b>miles per gallon</b>. A steady number means the engine is healthy. If it suddenly takes <a>more fuel per hour</a>, something is wrong — like a car getting worse mileage. Above <r>1.5 L/Hr</r> is the red flag: generators are <r>guzzling fuel</r>. Could be a mechanical issue, overloaded generator, or even theft."
                )

            ra5, ra6 = st.columns(2)
            with ra5:
                ec_line(p_dates, [
                    {"name": "Daily Cost (MMK)", "data": d_cost, "color": "#fca5a5"},
                    {"name": f"{wlabel} Cost", "data": r_cost, "color": "#ef4444"},
                ], title=f"Diesel Cost — Daily vs {wlabel}", height=350, key=f"ch_rcost_{chart_key}")
                _chart_guide(
                    f"Light red = daily diesel cost in MMK · Dark red = {wlabel} smoothed cost.\nRising cost could be <b>more fuel</b> or <b>higher prices</b> — check fuel price chart to tell which.",
                    [{"data": "Diesel Cost", "file": "Blackout Hr Excel + Fuel Price Excel", "col": "Daily Used × Price per Liter", "method": f"SUM all sites + {wlabel} rolling"}],
                    [("green", f"✅ Flat {wlabel} line = Spending is stable"),
                     ("amber", f"⚠️ Rising {wlabel} line = Fuel bill increasing"),
                     ("red", f"🔴 Sharp spike in {wlabel} = Urgent cost escalation, check cause")],
                    f"This is your <b>daily fuel bill</b>. Think of it like your <b>electricity bill at home</b> — it can go up because you used more power OR because the rate increased. If the {wlabel} line is <a>rising</a>, check the fuel price chart: if prices are flat, you're <r>burning more fuel</r>. If prices jumped, that's the cause."
                )
            with ra6:
                if not ts_df.empty:
                    m_dates = sorted(set(p_dates) & set(ts_df["date"].tolist()))
                    if len(m_dates) >= 3:
                        _sv_r = [round(ts_df[ts_df["date"]==d]["sales"].sum()) if not ts_df[ts_df["date"]==d].empty else 0 for d in m_dates]
                        _dv_r = [round(tp_df[tp_df["date"]==d]["liters"].sum() * fuel_price) for d in m_dates]
                        _dpv_r = [round(d/s*100, 2) if s > 0 else 0 for s, d in zip(_sv_r, _dv_r)]
                        _rdpv = _rolling(_dpv_r, window)
                        ec_line(m_dates, [
                            {"name": "Daily Diesel %", "data": _dpv_r, "color": "#fca5a5"},
                            {"name": f"{wlabel} Diesel %", "data": _rdpv, "color": "#ef4444"},
                        ], title=f"Diesel % of Sales — Daily vs {wlabel}", height=350, key=f"ch_rdpct_{chart_key}")
                        _chart_guide(
                            f"Light red = daily diesel % of sales · Dark red = {wlabel} smoothed trend.\nExample: <b>1.2% → 2.8%</b> over 2 weeks = <r>urgent</r>.",
                            [{"data": "Diesel % of Sales", "file": "Blackout Hr + Fuel Price + Sales Excel", "col": "(Daily Used × Price) ÷ SALES_AMT × 100", "method": f"CALC per day + {wlabel} rolling"}],
                            [("green", f"✅ {wlabel} line below 0.9% = Fuel cost is a small fraction of revenue"),
                             ("amber", f"⚠️ {wlabel} line 0.9-1.5% = Fuel costs rising relative to sales"),
                             ("red", f"🔴 {wlabel} line above 3% = Fuel is eating heavily into profit margins")],
                            f"Imagine for every <b>100 kyats</b> you earn in sales, this shows how many kyats go to diesel. At <g>0.9%</g>, that's less than <g>1 kyat per 100</g> — barely noticeable. At <r>3%+</r>, you're spending <r>3 kyats of every 100</r> just on fuel — that's real money off your bottom line."
                        )
                    else:
                        st.info("Not enough sales data for Diesel % trend.")
                else:
                    st.info("No sales data for Diesel % trend.")

            st.markdown("---")

            # ── Sector Breakdown Charts ─────────────────────────
            st.markdown(f"#### By Sector — {wlabel}")
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                dual_axis_chart(p_dates, r_hours, r_liters,
                    title=f"Gen Hours vs Fuel ({wlabel})",
                    bar_name=f"Gen Hours ({wlabel})", line_name=f"Fuel ({wlabel})",
                    bar_color="#3b82f6", line_color="#ef4444", height=350, key=f"ch_hvr_{chart_key}")
                _chart_guide(
                    f"Blue bars = {wlabel} avg generator hours · Red line = {wlabel} avg diesel used.\nBoth should move together. If red rises faster than blue → <r>efficiency problem</r>.",
                    [{"data": "Gen Hours + Fuel", "file": "Blackout Hr Excel", "col": "Gen Run Hr (bars) + Daily Used (line)", "method": f"{wlabel} rolling AVG"}],
                    [("green", f"✅ Both lines move in sync = Generators are efficient"),
                     ("amber", f"⚠️ Red line rising faster than blue = Fuel consumption per hour increasing"),
                     ("red", f"🔴 Red line far above blue = Serious waste — possible theft or breakdown")],
                    f"Think of this like <b>driving a car</b>: blue bars are <b>hours driven</b>, red line is <b>fuel used</b>. They should move together. If you drove the same hours but used <a>way more fuel</a>, something is wrong with the engine. Same here — if the red line <r>pulls away</r> from the blue bars, generators are <r>wasting fuel</r>."
                )
            with r1c2:
                ec_line(p_dates, [
                    {"name": "Daily L/Hr", "data": d_eff, "color": "#c4b5fd"},
                    {"name": f"{wlabel} L/Hr", "data": r_eff, "color": "#8b5cf6"},
                ], title=f"Efficiency — Daily vs {wlabel}", height=350, key=f"ch_efr_{chart_key}")
                _chart_guide(
                    f"Light purple = daily L/Hr · Dark purple = {wlabel} smoothed.\n<g>Flat</g> = healthy. <a>Rising</a> = fuel waste or generator wearing out.",
                    [{"data": "Efficiency L/Hr", "file": "Blackout Hr Excel", "col": "Daily Used ÷ Gen Run Hr", "method": f"DIV totals + {wlabel} rolling"}],
                    [("green", f"✅ Flat {wlabel} line = Generators running at normal efficiency"),
                     ("amber", f"⚠️ Gradually rising = Generators may need maintenance"),
                     ("red", f"🔴 Sudden spike = Possible fuel theft, leak, or mechanical failure")],
                    f"This is your generator fleet's <b>fuel report card</b>. Like checking if your car's fuel economy is getting worse over time. A <g>steady line</g> means everything is running <g>normally</g>. A <a>rising line</a> means generators are getting <a>thirstier</a> — time for maintenance. A <r>sudden jump</r> is like your car suddenly using twice the fuel — something is <r>very wrong</r>."
                )

            # Row 2: Fuel by Sector | Diesel Cost
            st.markdown("#### Fuel & Cost")
            r2c1, r2c2 = st.columns(2)
            with r2c1:
                fuel_lines = []
                for i, s in enumerate(all_sectors):
                    sdata = [round(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum()) for d in p_dates]
                    fuel_lines.append({"name": s, "data": _rolling(sdata, window), "color": SECTOR_COLORS.get(s, PALETTE[i%len(PALETTE)])})
                # TOTAL line removed — clutters chart
                ec_line(p_dates, fuel_lines, title=f"Fuel by Sector ({wlabel})", height=350, key=f"ch_fsr_{chart_key}")
                _chart_guide(
                    f"Each line = {wlabel} smoothed diesel usage for one sector (CMHL, CFC, CP, PG).\nHighest line = biggest fuel consumer.",
                    [{"data": "Fuel by Sector", "file": "Blackout Hr Excel", "col": "Daily Used", "method": f"SUM per sector + {wlabel} rolling"}],
                    [("green", "✅ All lines flat or declining = Fuel use under control across sectors"),
                     ("amber", "⚠️ One line rising while others flat = That sector needs attention"),
                     ("red", "🔴 Multiple lines rising = Company-wide fuel consumption increasing")],
                    f"Think of each line as a <b>department's electricity bill</b>. You can instantly see which department is the <b>biggest spender</b> and whether anyone is <a>trending up</a>. If CMHL is at <b>3,000L/day</b> and CFC is at <b>800L/day</b>, CMHL is using almost <r>4 times</r> more fuel — but they also have more sites, so check per-site numbers too."
                )
            with r2c2:
                ec_line(p_dates, [
                    {"name": "Daily Cost", "data": d_cost, "color": "#fca5a5"},
                    {"name": f"{wlabel} Cost", "data": r_cost, "color": "#ef4444"},
                ], title=f"Diesel Cost ({wlabel})", height=350, key=f"ch_costr_{chart_key}")
                _chart_guide(
                    f"Light red = daily diesel cost · Dark red = {wlabel} smoothed cost.\nRising = either <a>more fuel used</a> or <a>fuel price went up</a>.",
                    [{"data": "Diesel Cost", "file": "Blackout Hr + Fuel Price Excel", "col": "Daily Used × Price per Liter", "method": f"SUM all sites + {wlabel} rolling"}],
                    [("green", f"✅ Flat {wlabel} line = Fuel spending is stable"),
                     ("amber", f"⚠️ Rising {wlabel} line = Costs increasing, check fuel price vs volume"),
                     ("red", f"🔴 Sharp rise in {wlabel} = Costs accelerating, immediate review needed")],
                    f"This is the <b>total fuel bill</b> smoothed over time. Like watching your <b>monthly grocery spending</b> — if the line goes up, either you're buying <a>more groceries</a> or <a>prices went up</a>. Check the fuel price chart separately to figure out which one is driving the increase."
                )

            # Row 3: Buffer Days | Critical Sites
            st.markdown("#### Buffer & Risk")
            r3c1, r3c2 = st.columns(2)
            with r3c1:
                ec_line(p_dates, [
                    {"name": "Daily Buffer", "data": d_buf, "color": "#93c5fd"},
                    {"name": f"{wlabel} Buffer", "data": r_buf, "color": "#3b82f6"},
                ], title=f"Buffer Days — Daily vs {wlabel}", height=350,
                   mark_lines=[{"value": 7, "label": "Safe (7d)", "color": "#16a34a"},
                               {"value": 3, "label": "Critical (3d)", "color": "#dc2626"}],
                   key=f"ch_bufr_{chart_key}")
                _chart_guide(
                    f"Light blue = daily buffer days · Dark blue = {wlabel} smoothed buffer.\nGreen line = <b>7 days</b> safe · Red line = <b>3 days</b> critical. Steady decline = <r>fuel running out</r>.",
                    [{"data": "Buffer Days", "file": "Blackout Hr Excel", "col": "Spare Tank Balance ÷ Daily Used", "method": f"DIV per site + {wlabel} rolling"}],
                    [("green", f"✅ {wlabel} line above 7 days = Fuel reserves are healthy"),
                     ("amber", f"⚠️ {wlabel} line dropping toward 3 days = Schedule fuel delivery"),
                     ("red", f"🔴 {wlabel} line below 3 days = Emergency — sites may run out of fuel")],
                    f"Buffer days are like the <b>fuel gauge in your car</b>. Above <g>7 days</g> is a <g>full tank</g> — no worries. Dropping toward <a>3 days</a> is like the <a>low fuel light</a> coming on. Below <r>3 days</r> means you might <r>run out on the road</r>. A steady downward slope means you're burning through reserves without refueling."
                )
            with r3c2:
                r_crit = _rolling(d_crit, window)
                ec_line(p_dates, [
                    {"name": "Daily Critical", "data": d_crit, "color": "#fca5a5"},
                    {"name": f"{wlabel} Critical", "data": r_crit, "color": "#dc2626"},
                ], title=f"Critical Sites (<3d buffer) — {wlabel}", height=350, key=f"ch_critr_{chart_key}")
                _chart_guide(
                    f"Light red = daily count of danger sites · Dark red = {wlabel} smoothed count.\n<g>Zero</g> = no emergencies. <r>Rising</r> = more sites entering danger zone.",
                    [{"data": "Critical Site Count", "file": "Blackout Hr Excel", "col": "COUNT where buffer < 3 days", "method": f"COUNT per day + {wlabel} rolling"}],
                    [("green", f"✅ {wlabel} line at zero = No sites in danger"),
                     ("amber", f"⚠️ {wlabel} line 1-3 = A few sites need fuel deliveries"),
                     ("red", f"🔴 {wlabel} line above 5 = Multiple sites at risk of running dry")],
                    f"Think of this as a <b>hospital emergency board</b> — each number is a site in the <r>danger zone</r> (less than 3 days of fuel). <g>Zero</g> means the <g>ER is empty</g> — great news. A <a>rising number</a> means more patients are arriving — you need more <a>fuel deliveries</a> scheduled. A <r>spike</r> means a <r>mass emergency</r> — all hands on deck."
                )

            # Row 4: Sales vs Diesel | Diesel %
            if not ts_df.empty:
                merged_d = sorted(set(p_dates) & set(ts_df["date"].tolist()))
                if len(merged_d) >= 3:
                    st.markdown("#### Sales & Profitability")
                    sv_raw = [round(ts_df[ts_df["date"]==d]["sales"].sum()) if not ts_df[ts_df["date"]==d].empty else 0 for d in merged_d]
                    dv_raw = [round(sum(tp_df[(tp_df["date"]==d)&(tp_df["sector_id"]==s)]["liters"].sum() * _price_on_date(s, d) for s in all_sectors)) for d in merged_d]
                    r_sv = [round(v/1e6, 1) for v in _rolling(sv_raw, window)]
                    r_dv = [round(v/1e6, 2) for v in _rolling(dv_raw, window)]
                    dpv = [round(d/s*100, 2) if s > 0 else 0 for s, d in zip(sv_raw, dv_raw)]
                    r_dpv = _rolling(dpv, window)
                    r4c1, r4c2 = st.columns(2)
                    with r4c1:
                        dual_axis_chart(merged_d, r_sv, r_dv,
                            title=f"Sales vs Diesel (M MMK, {wlabel})",
                            bar_name=f"Sales M ({wlabel})", line_name=f"Diesel M ({wlabel})",
                            bar_color="#3b82f6", line_color="#ef4444", height=350, key=f"ch_svdr_{chart_key}")
                        _chart_guide(
                            f"Blue bars = {wlabel} avg sales (millions MMK) · Red line = {wlabel} avg diesel cost (millions MMK).\nGap between them = <g>profit buffer</g>. If red rises toward blue → <r>margins shrinking</r>.",
                            [{"data": "Sales Revenue", "file": "Sales Excel", "col": "SALES_AMT", "method": f"SUM per day + {wlabel} rolling ÷ 1M"},
                             {"data": "Diesel Cost", "file": "Blackout Hr + Fuel Price Excel", "col": "Daily Used × Price per Liter", "method": f"SUM per day + {wlabel} rolling ÷ 1M"}],
                            [("green", f"✅ Wide gap between bars and line = Fuel cost is small relative to sales"),
                             ("amber", f"⚠️ Gap narrowing = Diesel costs eating into revenue"),
                             ("red", f"🔴 Red line approaching blue bars = Fuel costs threatening profitability")],
                            f"Imagine blue bars as your <b>monthly salary</b> and the red line as your <b>rent payment</b>. The bigger the gap, the more <g>money you keep</g>. If rent keeps rising toward your salary, you're getting <a>squeezed</a>. If they ever meet, you're <r>breaking even</r> — no money left for anything else."
                        )
                    with r4c2:
                        ec_line(merged_d, [
                            {"name": "Daily Diesel %", "data": dpv, "color": "#fca5a5"},
                            {"name": f"{wlabel} Diesel %", "data": r_dpv, "color": "#ef4444"},
                        ], title=f"Diesel % of Sales — {wlabel}", height=350, key=f"ch_dpctr_{chart_key}")
                        _chart_guide(
                            f"Light red = daily diesel % · Dark red = {wlabel} smoothed diesel %.\nThresholds: <g>&lt;0.9%</g> · <a>&lt;1.5%</a> · <b>&lt;3%</b> · <r>&gt;3%</r>.",
                            [{"data": "Diesel % of Sales", "file": "Blackout Hr + Fuel Price + Sales Excel", "col": "Diesel Cost ÷ Sales Revenue × 100", "method": f"CALC per day + {wlabel} rolling"}],
                            [("green", f"✅ {wlabel} line below 0.9% = Fuel cost is negligible"),
                             ("amber", f"⚠️ {wlabel} line 0.9-1.5% = Fuel starting to impact margins"),
                             ("orange", f"🟠 {wlabel} line 1.5-3% = Significant fuel cost burden"),
                             ("red", f"🔴 {wlabel} line above 3% = Fuel is a major profit drain")],
                            f"This percentage is like a <b>tax on your sales</b>. At <g>0.9%</g>, it's a tiny tax — barely feel it. At <a>1.5%</a>, it starts to <a>pinch</a>. At <r>3%+</r>, it's like paying a <r>hefty surcharge</r> on every sale. The {wlabel} smoothing helps you see if this tax is <a>growing</a> or <g>staying manageable</g>."
                        )

            # Row 5: Blackout
            if not bo_df.empty:
                bo_dates_p = sorted(bo_df["date"].unique())
                if len(bo_dates_p) >= 3:
                    st.markdown("#### Blackout")
                    avg_bo = [_safe(bo_df[bo_df["date"]==d]["avg_blackout_hr"].mean(), 1) if not bo_df[bo_df["date"]==d].empty else 0 for d in bo_dates_p]
                    r_bo = _rolling(avg_bo, window)
                    ec_line(bo_dates_p, [
                        {"name": "Daily Avg Blackout", "data": avg_bo, "color": "#fcd34d"},
                        {"name": f"{wlabel} Blackout", "data": r_bo, "color": "#d97706"},
                    ], title=f"Avg Blackout Hours per Site — {wlabel}", height=350, key=f"ch_bor_{chart_key}")
                    _chart_guide(
                        f"Light amber = daily avg blackout hours · Dark amber = {wlabel} smoothed.\nExample: <b>6hr → 10hr</b> over a week = <r>grid worsening</r>.",
                        [{"data": "Blackout Hours", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": f"AVG per site per day + {wlabel} rolling"}],
                        [("green", f"✅ {wlabel} line flat or declining = Power grid is stable or improving"),
                         ("amber", f"⚠️ {wlabel} line rising = Blackouts getting longer, prepare more fuel"),
                         ("red", f"🔴 {wlabel} line above 10 hrs = Severe grid failure, heavy generator reliance")],
                        f"Blackout hours are like <b>how long the water is shut off</b> each day. A <g>flat line</g> means the situation is <g>predictable</g> — you can plan around it. A <a>rising line</a> means outages are getting <a>longer</a> — you'll need more fuel for generators. If it hits <r>10+ hours</r>, that's nearly half the day without power — <r>emergency planning</r> is needed."
                    )

    # ─── LAST DAY ─────────────────────────────────────────────────
    _render_kpi_block("LAST DAY", d1["days"], d1["tank"], d1["burn"], d1_diesel, sales_1d, d1["crit"], d1["warn"], d1["safe"], d1_epct, d1["sites"],
                      f"{last_date_str} | {d1['sites']} sites | Gen Hours: {d1['hours']:,.0f}hr")
    # Single day — no multi-day chart, but show gen hours vs fuel as bar
    if d1["hours"] > 0:
        with st.expander(f"📊 Last Day Breakdown — {last_date_str}", expanded=True):
            if last_dates and not daily_df.empty:
                day1 = daily_df[daily_df["date"] == last_dates[0]].sort_values("total_daily_used", ascending=False)
                if not day1.empty:
                    top_sites = day1.head(15)
                    ec_hbar(top_sites["site_id"].tolist(),
                            [round(v) for v in top_sites["total_daily_used"].tolist()],
                            title=f"Top Sites by Fuel Used — {last_date_str}",
                            key="ch_d1_top")
                    _chart_guide(
                        "Diesel liters used by each site on this single day, ranked highest to lowest.",
                        [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "per site, this day only"}],
                        [("green", "✅ Short bars = Low fuel usage, manageable"),
                         ("amber", "⚠️ Long bars = High consumers, check if sales justify the fuel"),
                         ("red", "🔴 Extremely long bar = Investigate why this site used so much")],
                        "Shows which <b>stores used the most diesel today</b>. Like a <b>leaderboard</b> — the longest bar is the biggest fuel consumer. Ask: does that store make enough <b>sales revenue</b> to justify spending that much on fuel? If not, consider <r>reducing its hours</r>."
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        ec_hbar(top_sites["site_id"].tolist(),
                                [round(v) for v in top_sites["total_gen_run_hr"].tolist()],
                                title=f"Gen Hours by Site — {last_date_str}", key="ch_d1_hrs")
                        _chart_guide(
                            "Hours each site's generator ran today, ranked highest to lowest.",
                            [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "per site, this day only"}],
                            [("green", "✅ Short bars (2-4 hr) = Light blackout day for that site"),
                             ("amber", "⚠️ Medium bars (6-10 hr) = Significant blackout"),
                             ("red", "🔴 Long bars (12+ hr) = Generator ran almost all day, heavy impact")],
                            "Shows which <b>stores had their generators running the longest today</b>. Longer bar = <a>more hours without grid power</a>. These sites are <r>burning the most fuel</r> and may need priority fuel delivery."
                        )
                    with c2:
                        eff1 = [round(l/h, 1) if h > 0 else 0 for h, l in zip(top_sites["total_gen_run_hr"], top_sites["total_daily_used"])]
                        ec_hbar(top_sites["site_id"].tolist(), eff1,
                                title=f"Efficiency L/Hr by Site — {last_date_str}", key="ch_d1_eff")
                        _chart_guide(
                            "Diesel liters ÷ Generator hours = <b>Liters per hour</b> for each site today.",
                            [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "per site"},
                             {"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "per site"}],
                            [("green", "✅ Similar bar lengths = All generators running at similar efficiency"),
                             ("amber", "⚠️ One bar much longer = That site's generator is using more fuel per hour"),
                             ("red", "🔴 Extremely long bar = Possible fuel theft or generator malfunction at that site")],
                            "Like comparing <b>fuel economy across a car fleet</b>. Most cars do 15 L/Hr. If one car suddenly shows <r>30 L/Hr</r>, something is wrong with that car — or someone is <r>stealing fuel</r> from it. Same idea here."
                        )

    # ─── LAST 3 DAYS AVG ─────────────────────────────────────────
    d3_start = last3_dates[-1] if last3_dates else "—"
    d3_end = last3_dates[0] if last3_dates else "—"
    _render_kpi_block("LAST 3 DAYS AVG", d3["days"], d3["tank"], d3["burn"], d3_diesel, sales_3d, d3["crit"], d3["warn"], d3["safe"], d3_epct, d3["sites"],
                      f"{d3_start} → {d3_end} | {len(last3_dates)} days | Gen Hours: {d3['hours']:,.0f}hr avg")
    _render_period_charts(last3_dates, f"Last 3 Days ({d3_start} → {d3_end})", "d3", window=3)

    # ─── COMPARISON: Yesterday vs 3-Day Avg ──────────────────────────
    def _cmp(v1, v3, label, fmt="num", good="low"):
        """Return comparison card HTML."""
        if v3 == 0 or v1 is None or v3 is None:
            return f'<div style="flex:1;min-width:130px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:14px;text-align:center"><div style="font-size:18px;font-weight:700;color:#9ca3af">—</div><div style="font-size:11px;font-weight:600;color:#64748b">{label}</div><div style="font-size:10px;color:#9ca3af">No data</div></div>'
        diff = v1 - v3
        pct = (diff / v3 * 100) if v3 != 0 else 0
        arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
        # For "low is good" metrics (burn, diesel, cost), up = worse
        # For "high is good" metrics (buffer, sales), up = better
        if good == "low":
            color = "#dc2626" if pct > 5 else "#d97706" if pct > 0 else "#16a34a"
            badge = "🔴 WORSE" if pct > 5 else "🟡 WATCH" if pct > 0 else "🟢 BETTER"
        else:
            color = "#16a34a" if pct > 5 else "#d97706" if pct > 0 else "#dc2626"
            badge = "🟢 BETTER" if pct > 5 else "🟡 WATCH" if pct > 0 else "🔴 WORSE"
        if fmt == "M":
            v1s = f"{v1/1e6:,.2f}M"; v3s = f"{v3/1e6:,.2f}M"
        elif fmt == "pct":
            v1s = f"{v1:.2f}%"; v3s = f"{v3:.2f}%"
        elif fmt == "d":
            v1s = f"{v1:.1f}d"; v3s = f"{v3:.1f}d"
        else:
            v1s = f"{v1:,.0f}"; v3s = f"{v3:,.0f}"
        return f'''<div style="flex:1;min-width:130px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;padding:14px;text-align:center">
            <div style="font-size:20px;font-weight:800;color:{color}">{arrow} {abs(pct):.1f}%</div>
            <div style="font-size:11px;font-weight:600;color:#1f2937">{label}</div>
            <div style="font-size:10px;color:#64748b;margin-top:4px">{v1s} vs {v3s}</div>
            <div style="font-size:10px;margin-top:2px">{badge}</div>
        </div>'''

    if d1["burn"] > 0 and d3["burn"] > 0:
        st.markdown(f"""
<div style="background:#0f172a;color:white;border-radius:12px 12px 0 0;padding:10px 16px;margin-top:16px;font-weight:700;font-size:15px">
    YESTERDAY vs 3-DAY AVERAGE <span style="font-size:11px;font-weight:400;opacity:0.6;margin-left:12px">{last_date_str} vs last {len(last_dates)} days</span>
</div>
<div style="display:flex;gap:10px;padding:12px;background:#f8fafc;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;flex-wrap:wrap">
    {_cmp(d1["burn"], d3["burn"], "Burn Rate (L/day)", "num", "low")}
    {_cmp(d1["days"], d3["days"], "Buffer Days", "d", "high") if d1["days"] and d3["days"] else _cmp(None, None, "Buffer Days")}
    {_cmp(d1_diesel, d3_diesel, "Diesel Cost (MMK)", "M", "low")}
    {_cmp(sales_1d, sales_3d, "Sales (MMK)", "M", "high") if sales_1d > 0 else _cmp(None, None, "Sales")}
    {_cmp(d1_epct, d3_epct, "Diesel % of Sales", "pct", "low") if d1_epct > 0 else _cmp(None, None, "Diesel %")}
</div>""", unsafe_allow_html=True)

    # ─── TREND CHARTS: Gen Hours vs Fuel ─────────────
    with get_db() as conn:
        _dsql2, _dp2 = _date_sql("dss.date")
        trend_q = f"""
            SELECT dss.date,
                   SUM(dss.total_gen_run_hr) as total_hours,
                   SUM(dss.total_daily_used) as total_liters,
                   COUNT(DISTINCT dss.site_id) as sites
            FROM daily_site_summary dss
            WHERE dss.site_id IN ({",".join(["?"]*len(site_ids))}){_dsql2}
            GROUP BY dss.date ORDER BY dss.date
        """
        trend_df = pd.read_sql_query(trend_q, conn, params=site_ids + _dp2)
        _dsql3, _dp3 = _date_sql("date")
        sales_trend_q = f"""
            SELECT date, SUM(sales_amt) as sales
            FROM daily_sales WHERE site_id IN ({",".join(["?"]*len(site_ids))}){_dsql3}
            GROUP BY date ORDER BY date
        """
        sales_trend = pd.read_sql_query(sales_trend_q, conn, params=site_ids + _dp3)

    if not trend_df.empty and len(trend_df) >= 3:
        trend_df = trend_df.sort_values("date")
        dates_t = trend_df["date"].tolist()
        hours_t = [round(v) if pd.notna(v) else 0 for v in trend_df["total_hours"]]
        liters_t = [round(v) if pd.notna(v) else 0 for v in trend_df["total_liters"]]
        # Efficiency: L per hour
        eff_t = [round(l / h, 1) if h > 0 else 0 for h, l in zip(hours_t, liters_t)]

        st.markdown("---")

        tc1, tc2 = st.columns(2)
        with tc1:
            # Gen Hours vs Fuel Consumption (dual axis)
            dual_axis_chart(dates_t, hours_t, liters_t,
                            title="Generator Hours vs Fuel Consumption",
                            bar_name="Gen Hours (hr)", line_name="Fuel Used (L)",
                            bar_color="#3b82f6", line_color="#ef4444",
                            height=350, key="kpi_trend_hv")
        with tc2:
            # Efficiency trend (L per hour)
            ec_line(dates_t,
                    [{"name": "Liters per Hour", "data": eff_t, "color": "#8b5cf6"}],
                    title="Efficiency — Liters per Gen Hour",
                    height=350, key="kpi_trend_eff")
            _chart_guide(
                "Total diesel liters ÷ Total generator hours = <b>Liters per hour</b>, all sites combined.\nExample: <b>1,800L</b> ÷ <b>120 hours</b> = <b>15.0 L/Hr</b>.",
                [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM all sites"},
                 {"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM all sites"}],
                [("green", "✅ Flat line (15-20 L/Hr) = Generators are healthy and efficient"),
                 ("amber", "⚠️ Spike up = Generators wasting fuel or possible theft"),
                 ("blue", "📉 Drop = Efficiency improving or lighter load")],
                "Like your <b>car's fuel economy</b>. A healthy car does the same km/liter every week. If it suddenly drops, you check the mechanic. Same with generators — a <g>flat line</g> means <g>healthy</g>. A <a>spike up</a> means something changed: <r>fuel theft</r>, a <a>worn-out generator</a>, or extra load."
            )

        # Sales vs Diesel Cost trend
        if not sales_trend.empty and len(sales_trend) >= 3:
            sales_trend = sales_trend.sort_values("date")
            merged_dates = sorted(set(dates_t) & set(sales_trend["date"].tolist()))
            if len(merged_dates) >= 3:
                sv_raw = [round(sales_trend[sales_trend["date"]==d]["sales"].sum()) for d in merged_dates]
                dv_raw = [round(sum(trend_df[trend_df["date"]==d]["total_liters"].sum() * _price_on_date(s, d) for s in econ["sector_id"].dropna().unique())) for d in merged_dates]
                dpv = [round(d/s*100, 2) if s > 0 else 0 for s, d in zip(sv_raw, dv_raw)]
                sv = [round(v/1e6, 1) for v in sv_raw]
                dv = [round(v/1e6, 2) for v in dv_raw]

                tc3, tc4 = st.columns(2)
                with tc3:
                    dual_axis_chart(merged_dates, sv, dv,
                                    title="Sales vs Diesel Cost (Millions)",
                                    bar_name="Sales (M)", line_name="Diesel (M)",
                                    bar_color="#3b82f6", line_color="#ef4444",
                                    height=350, key="kpi_trend_svd")
                with tc4:
                    ec_line(merged_dates,
                            [{"name": "Diesel % of Sales", "data": dpv, "color": "#ef4444"}],
                            title="Diesel % of Sales — Daily Trend",
                            height=350, key="kpi_trend_dpct")

    # ─── RECOMMENDATIONS ─────────────────────────────────────────────
    recs = []
    # Critical sites
    crit_sites = df[df["latest_buffer_days"].notna() & (df["latest_buffer_days"] < 3)]
    if len(crit_sites) > 0:
        sites_list = ", ".join(f"{r['site_id']} ({r['latest_buffer_days']:.1f}d)" for _, r in crit_sites.head(5).iterrows())
        recs.append(("🔴", f"**{len(crit_sites)} sites have < 3 days diesel** — send fuel NOW: {sites_list}"))

    # Burn rate spike
    if d1["burn"] > 0 and d3["burn"] > 0 and d1["burn"] > d3["burn"] * 1.15:
        pct_up = ((d1["burn"] - d3["burn"]) / d3["burn"] * 100)
        recs.append(("🟡", f"**Burn rate up {pct_up:.0f}%** yesterday vs 3-day avg — check for extended blackouts or unauthorized usage"))

    # Diesel% rising
    if d1_epct > 0 and d3_epct > 0 and d1_epct > d3_epct + 0.5:
        recs.append(("🟡", f"**Diesel cost rising faster than sales** — diesel% yesterday {d1_epct:.2f}% vs 3-day avg {d3_epct:.2f}%"))

    # Sites with high diesel%
    high_diesel = df[(df["energy_pct"].notna()) & (df["energy_pct"] > 3)]
    if len(high_diesel) > 0:
        hl = ", ".join(f"{r['site_id']} ({r['energy_pct']:.1f}%)" for _, r in high_diesel.head(5).iterrows())
        recs.append(("🟠", f"**{len(high_diesel)} sites with diesel > 3% of sales** — reduce gen hours: {hl}"))

    # Sales drop
    if sales_1d > 0 and sales_3d > 0 and sales_1d < sales_3d * 0.9:
        drop = ((sales_3d - sales_1d) / sales_3d * 100)
        recs.append(("⚡", f"**Sales dropped {drop:.0f}%** yesterday vs 3-day avg — review operating hours"))

    # Buffer improving
    if d1["days"] and d3["days"] and d1["days"] > d3["days"]:
        recs.append(("🟢", f"**Buffer improving** — {d1['days']:.1f} days yesterday vs {d3['days']:.1f} avg"))

    # All safe
    if t_crit == 0 and len(recs) == 0:
        recs.append(("✅", "**All sites healthy** — no immediate action needed"))

    if recs:
        recs_html = "".join(f'<div style="border-left:4px solid {"#dc2626" if i=="🔴" else "#d97706" if i=="🟡" else "#f97316" if i=="🟠" else "#3b82f6" if i=="⚡" else "#16a34a"};padding:8px 14px;margin:6px 0;font-size:13px;background:#f8fafc;border-radius:0 8px 8px 0">{i} {m}</div>' for i, m in recs)
        st.markdown(f"""
<div style="background:#0f172a;color:white;border-radius:12px 12px 0 0;padding:10px 16px;margin-top:16px;font-weight:700;font-size:15px">
    RECOMMENDATIONS
</div>
<div style="border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;padding:8px">
    {recs_html}
</div>""", unsafe_allow_html=True)

def _peak_hours_heatmap(sector_filter=None, site_filter=None, key_prefix="grp"):
    """Peak Hours Heatmap — Hour × Day of Week, colored by profitability vs diesel cost."""
    with get_db() as conn:
        # Build query with join chain: hourly_sales → store_master → sites
        q = """
            SELECT h.hour,
                   CASE CAST(strftime('%w', h.date) AS INTEGER)
                       WHEN 0 THEN 'SUN' WHEN 1 THEN 'MON' WHEN 2 THEN 'TUE'
                       WHEN 3 THEN 'WED' WHEN 4 THEN 'THU' WHEN 5 THEN 'FRI' WHEN 6 THEN 'SAT'
                   END as dow,
                   CAST(strftime('%w', h.date) AS INTEGER) as dow_num,
                   SUM(h.sales_amt) as total_sales,
                   COUNT(DISTINCT h.date) as days_count,
                   COUNT(*) as trans_count
            FROM hourly_sales h
            JOIN store_master sm ON h.sales_site_name = sm.gold_code
            JOIN sites s ON sm.cost_center_code = s.cost_center_code
            WHERE h.sales_amt IS NOT NULL
        """
        params = []
        if site_filter:
            q += " AND s.site_id = ?"
            params.append(site_filter)
        elif sector_filter:
            q += " AND s.sector_id = ?"
            params.append(sector_filter)
        if str_from:
            q += " AND h.date >= ?"
            params.append(str_from)
        if str_to:
            q += " AND h.date <= ?"
            params.append(str_to)
        q += " GROUP BY h.hour, dow ORDER BY h.hour, dow_num"
        hdata = pd.read_sql_query(q, conn, params=params)

        # Get avg diesel cost per hour (estimate from daily data)
        dq = "SELECT AVG(fp.price_per_liter) as price FROM fuel_purchases fp WHERE fp.price_per_liter IS NOT NULL"
        dp = []
        if sector_filter:
            dq += " AND fp.sector_id = ?"
            dp.append(sector_filter)
        avg_price = conn.execute(dq, dp).fetchone()[0] or 0

        # Avg hourly fuel cost = total daily diesel ÷ operating hours
        bq = "SELECT AVG(dss.total_daily_used) as avg_daily, AVG(dss.total_gen_run_hr) as avg_hrs FROM daily_site_summary dss"
        if site_filter:
            bq += " JOIN sites s ON dss.site_id = s.site_id WHERE dss.site_id = ?"
            bp = [site_filter]
        elif sector_filter:
            bq += " JOIN sites s ON dss.site_id = s.site_id WHERE s.sector_id = ?"
            bp = [sector_filter]
        else:
            bp = []
        burn = conn.execute(bq, bp).fetchone()
        avg_daily_liters = burn[0] if burn and burn[0] else 0
        avg_gen_hours = burn[1] if burn and burn[1] else 12
        hourly_diesel_cost = (avg_daily_liters / max(avg_gen_hours, 1)) * avg_price if avg_price > 0 else 0

    if hdata.empty:
        return

    # Pivot: rows=hour, cols=dow
    days_order = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    hours = sorted(hdata["hour"].unique())
    if not hours:
        return

    # Build avg sales per hour per day
    pivot = {}
    for _, r in hdata.iterrows():
        h = r["hour"]
        d = r["dow"]
        avg_sales = r["total_sales"] / max(r["days_count"], 1)
        pivot[(h, d)] = avg_sales

    # Determine icon (no background color)
    def _cell(val):
        if val is None or val == 0:
            return "⚪", "NO DATA"
        ratio = val / max(hourly_diesel_cost, 1) if hourly_diesel_cost > 0 else 999
        if ratio >= 3:
            return "🟢", "PEAK"
        elif ratio >= 1.5:
            return "🟡", "PROFITABLE"
        elif ratio >= 1:
            return "🟠", "MARGINAL"
        else:
            return "🔴", "LOSING"

    # Build HTML table — no background colors, only icons
    header = "".join(f'<th style="padding:8px 10px;text-align:center;font-size:12px">{d}</th>' for d in days_order)
    rows_html = ""
    peak_hours = []
    lose_hours = []
    for h in hours:
        h_label = f"{h}:00–{h+1}:00"
        cells = ""
        for d in days_order:
            val = pivot.get((h, d), 0)
            icon, status = _cell(val)
            val_str = f"{val/1e3:,.0f}K" if val >= 1000 else f"{val:,.0f}" if val > 0 else "—"
            cells += f'<td style="text-align:center;padding:6px 8px;font-size:11px;font-weight:600;border-bottom:1px solid #e5e7eb">{icon} {val_str}</td>'
            if status == "PEAK":
                peak_hours.append((h, d))
            elif status == "LOSING":
                lose_hours.append((h, d))
        rows_html += f'<tr><td style="padding:6px 10px;font-weight:600;font-size:12px;white-space:nowrap;background:#0f172a;color:#e2e8f0">{h_label}</td>{cells}</tr>'

    scope = site_filter or sector_filter or "All Sites"
    st.markdown(f"""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:14px 16px;border-radius:12px 12px 0 0">
    <div style="font-weight:700;font-size:16px">🕐 Peak Hours Heatmap — {scope}</div>
    <div style="font-size:12px;opacity:0.7;margin-top:4px">Avg hourly sales vs estimated diesel cost per hour ({hourly_diesel_cost:,.0f} MMK/hr). Answers: <strong>"Which hours should this store be open?"</strong></div>
</div>
<table style="width:100%;border-collapse:collapse">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:8px 10px;text-align:left;font-size:12px">Hour</th>{header}
</tr></thead>
<tbody>{rows_html}</tbody>
</table>
<div style="background:#f8fafc;padding:12px 16px;border-top:1px solid #e5e7eb">
    <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:12px;margin-bottom:8px">
        <span><strong>🟢 PEAK</strong> — Sales &gt; 3× diesel cost (highly profitable)</span>
        <span><strong>🟡 PROFITABLE</strong> — Sales 1.5–3× diesel (covers fuel + good margin)</span>
        <span><strong>🟠 MARGINAL</strong> — Sales 1–1.5× diesel (barely covers fuel)</span>
        <span><strong>🔴 LOSING</strong> — Sales &lt; diesel cost (store loses money this hour)</span>
    </div>
    <div style="font-size:11px;color:#64748b;border-top:1px solid #e5e7eb;padding-top:8px">
        <strong>How to use:</strong> If a cell is 🔴 every day → recommend closing during that hour. If 🟠 on weekdays but 🟢 on weekends → keep open weekends only.<br>
        <strong>Formula:</strong> Avg Hourly Sales (from hourly_sales Excel) ÷ Estimated Diesel Cost/Hr ({hourly_diesel_cost:,.0f} MMK = {avg_daily_liters:,.0f}L/day ÷ {avg_gen_hours:,.0f}hrs × {avg_price:,.0f} MMK/L)<br>
        <strong>Source:</strong> hourly sales sheet from Sales Excel + daily_site_summary + fuel_purchases
    </div>
</div>
</div>""", unsafe_allow_html=True)

    # Auto-recommendation
    if lose_hours:
        lose_by_hour = {}
        for h, d in lose_hours:
            lose_by_hour.setdefault(h, []).append(d)
        always_lose = [f"{h}:00" for h, days in lose_by_hour.items() if len(days) >= 5]
        if always_lose:
            st.markdown(f"""<div style="background:#fef2f2;border-left:4px solid #dc2626;padding:10px 14px;margin:8px 0;border-radius:0 8px 8px 0;font-size:13px">
            🔴 <strong>Recommend closing during:</strong> {', '.join(always_lose)} — losing money on diesel 5+ days/week
            </div>""", unsafe_allow_html=True)
    if peak_hours:
        peak_by_hour = {}
        for h, d in peak_hours:
            peak_by_hour.setdefault(h, []).append(d)
        always_peak = [f"{h}:00" for h, days in peak_by_hour.items() if len(days) >= 5]
        if always_peak:
            st.markdown(f"""<div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:10px 14px;margin:8px 0;border-radius:0 8px 8px 0;font-size:13px">
            🟢 <strong>Best hours:</strong> {', '.join(always_peak)} — peak revenue every day
            </div>""", unsafe_allow_html=True)


def _agg_heatmap(df, group_col, title):
    """Aggregated heatmap: one row per group (sector or company)."""
    rows=""; data=[]
    for g in sorted(df[group_col].dropna().unique()):
        gd=df[df[group_col]==g]; n=len(gd); m=gd[gd["has_sales"]==True]
        ap=gd["diesel_price"].mean(); ab=gd["blackout_hr"].mean() if gd["blackout_hr"].notna().any() else None
        ts=m["total_sales"].sum() if not m.empty else None; te=gd["energy_cost"].sum()
        ep=(te/ts*100) if ts and ts>0 else None
        _ab=gd[(gd["avg_daily_liters"].notna())&(gd["avg_daily_liters"]>0)]
        hb=_ab[(_ab["diesel_available"].notna())&(_ab["diesel_available"]>0)]
        _total_burn=_ab["avg_daily_liters"].sum() if not _ab.empty else 0
        bd=(hb["diesel_available"].sum()/_total_burn) if _total_burn>0 else None
        nc=len(hb[hb["latest_buffer_days"]<3]) if not hb.empty else 0
        data.append({group_col:g,"Sites":n,"Diesel Price":ap,"Blackout Hr":ab,"Exp% of Sale":ep,"Buffer Day":bd,"Sales":ts,"Diesel Cost":te,"Critical":nc})
        rows+=f'<tr><td style="padding:6px 8px;font-weight:700;font-size:13px">{g}</td><td style="text-align:center;padding:6px 8px;font-size:12px">{n}</td>{_cc(ap,"diesel_price")}{_cc(ab,"blackout_hr")}{_cc(ep,"expense_pct")}{_cc(bd,"buffer_days")}{_td(ts,"M")}{_td(te,"M2")}<td style="text-align:center;padding:6px 8px;font-weight:600;color:{"#dc2626" if nc>0 else "#16a34a"}">{nc}</td></tr>'
    st.markdown(f"""<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:8px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">{title}</div>
<table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:8px;text-align:left">{group_col.replace('_',' ').title()}</th><th style="padding:8px;text-align:center">Sites</th>
<th style="padding:8px;text-align:center;background:#334155">Price/L</th><th style="padding:8px;text-align:center;background:#334155">Blackout Hr</th>
<th style="padding:8px;text-align:center;background:#334155">Exp% of Sale</th><th style="padding:8px;text-align:center;background:#334155">Buffer Day</th>
<th style="padding:8px;text-align:center">Sales</th><th style="padding:8px;text-align:center">Diesel</th><th style="padding:8px;text-align:center">Critical</th>
</tr></thead><tbody>{rows}</tbody></table></div>""",unsafe_allow_html=True)
    if data: _render_download(pd.DataFrame(data),title,color_rules=DR)

def _site_table(df, title):
    """Per-site heatmap table."""
    rows=""
    for _,r in df.iterrows():
        ly=r.get("ly_diesel_pct"); lyc=f'<td style="text-align:center;padding:6px 8px;font-size:12px">{ly:.2f}%</td>' if pd.notna(ly) else _td(None)
        rows+=f'<tr><td style="padding:6px 8px;font-weight:600;white-space:nowrap;font-size:12px">{r["site_id"]}</td>{_cc(r.get("diesel_price"),"diesel_price")}{_cc(r.get("blackout_hr"),"blackout_hr")}{_cc(r.get("energy_pct"),"expense_pct")}{_cc(r.get("latest_buffer_days"),"buffer_days")}{_td(r.get("total_sales"),"M")}{_td(r.get("avg_daily_sales"),"M")}{_td(r.get("energy_cost"),"M2")}{_td(r.get("daily_diesel_cost"),"M2")}{_td(r.get("margin_pct"),"pct1")}{lyc}{_td(r.get("diesel_available"),"int")}{_td(r.get("avg_daily_liters"),"int")}{_td(r.get("recommendation"))}</tr>'
    st.markdown(f"""<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:8px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">{title}</div>
<table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:8px;text-align:left" rowspan="2">Site</th>
<th style="padding:8px;text-align:center;background:#334155" colspan="4">Threshold Indicators</th>
<th style="padding:8px;text-align:center" colspan="2">Sales</th><th style="padding:8px;text-align:center" colspan="2">Diesel Cost</th>
<th style="padding:8px;text-align:center">Gross Margin</th><th style="padding:8px;text-align:center">LY</th>
<th style="padding:8px;text-align:center" colspan="2">Tank</th><th style="padding:8px;text-align:center">Action</th>
</tr><tr style="background:#1e293b;color:#94a3b8;font-size:10px">
<th style="padding:4px 8px;background:#334155">Price/L</th><th style="padding:4px 8px;background:#334155">Blackout Hr</th>
<th style="padding:4px 8px;background:#334155">Exp% of Sale</th><th style="padding:4px 8px;background:#334155">Buffer Day</th>
<th style="padding:4px 8px">Total</th><th style="padding:4px 8px">Per Day</th><th style="padding:4px 8px">Total</th><th style="padding:4px 8px">Per Day</th>
<th style="padding:4px 8px">%</th><th style="padding:4px 8px">of Sales</th><th style="padding:4px 8px">Balance(L)</th><th style="padding:4px 8px">Burn/day</th><th style="padding:4px 8px"></th>
</tr></thead><tbody>{rows}</tbody></table></div>""",unsafe_allow_html=True)
    dc=[c for c in ["site_id","diesel_price","blackout_hr","energy_pct","latest_buffer_days","total_sales","avg_daily_sales","energy_cost","daily_diesel_cost","margin_pct","recommendation"] if c in df.columns]
    dl=df[dc].copy(); dl.columns=["Site","Diesel Price","Blackout Hr","Exp% of Sale","Buffer Day","Total Sales","Sales/Day","Total Diesel Cost","Diesel Cost/Day","Gross Margin","Recommendation"][:len(dc)]
    _render_download(dl,title,color_rules=DR)

def _site_detail(sid, tk, period="Daily"):
    """Generator detail + multi-period variance + trends for one site."""
    gf=get_generator_detail(sid); sr=econ[econ["site_id"]==sid].iloc[0] if sid in econ["site_id"].values else None
    if gf.empty: st.info(f"No generator data for {sid}"); return

    # Get rated consumption per hour (sum of all generators)
    rated_per_hr = gf["consumption_per_hour"].sum()
    tg=len(gf); rn=len(gf[gf["total_run_hrs"]>0])
    tn=sr["diesel_available"] if sr is not None and pd.notna(sr["diesel_available"]) else 0
    es=sr["energy_start"] if sr is not None else "—"; ee=sr["energy_end"] if sr is not None else "—"
    ed=int(sr["energy_days"]) if sr is not None and pd.notna(sr["energy_days"]) else 0

    # Total period variance (from generator detail — full period)
    cp_total=(gf["consumption_per_hour"]*gf["total_run_hrs"]).sum(); ac_total=gf["total_liters"].sum()
    vr_total=ac_total-cp_total if cp_total>0 else 0; vp_total=(vr_total/cp_total*100) if cp_total>0 else 0

    # Query daily data for this site (date filtered)
    with get_db() as conn:
        _dsql, _dp = _date_sql("date")
        site_dates = conn.execute(f"SELECT DISTINCT date FROM daily_site_summary WHERE site_id = ?{_dsql} ORDER BY date DESC LIMIT 5", [sid] + _dp).fetchall()
        site_last_dates = [r[0] for r in site_dates]
        all_site_dates = conn.execute(f"SELECT DISTINCT date FROM daily_site_summary WHERE site_id = ?{_dsql} ORDER BY date", [sid] + _dp).fetchall()
        all_sd = [r[0] for r in all_site_dates]

        site_daily = pd.DataFrame()
        if site_last_dates:
            dp = ",".join(["?"]*len(site_last_dates))
            site_daily = pd.read_sql_query(f"""
                SELECT do.date, SUM(do.gen_run_hr) as hours, SUM(do.daily_used_liters) as liters
                FROM daily_operations do
                WHERE do.site_id = ? AND do.date IN ({dp})
                GROUP BY do.date
            """, conn, params=[sid] + site_last_dates)

    def _var_card(title, expected, actual, tank, period_note, key_suffix):
        vr = actual - expected if expected > 0 else 0
        vp = (vr / expected * 100) if expected > 0 else 0
        vc = "#dc2626" if vp > 20 else "#d97706" if vp > 10 else "#16a34a" if expected > 0 else "#6b7280"
        status = "OVER — using more than rated" if vp > 20 else "UNDER — efficient" if vp < -20 else "NORMAL" if expected > 0 else "NO DATA"
        st.markdown(f"""<div style="background:#1e293b;color:white;border-radius:12px;padding:14px;margin:6px 0">
<div style="display:flex;justify-content:space-between;align-items:center">
    <div><span style="font-size:14px;font-weight:700">{title}</span><span style="opacity:0.7;margin-left:8px;font-size:12px">{rn}/{tg} generators</span></div>
    <div style="background:{vc};padding:4px 12px;border-radius:16px;font-weight:600;font-size:13px">Variance: {vp:+.0f}%</div>
</div>
<div style="display:flex;gap:20px;margin-top:10px;font-size:13px">
    <div>Tank: <strong>{tank:,.0f}L</strong></div>
    <div>Expected: <strong>{expected:,.0f}L</strong></div>
    <div>Actual: <strong>{actual:,.0f}L</strong></div>
    <div>Variance: <strong style="color:{'#ef4444' if vr>0 else '#22c55e'}">{vr:+,.0f}L</strong></div>
    <div>Status: <strong>{status}</strong></div>
</div>
<div style="font-size:11px;opacity:0.6;margin-top:6px">{period_note}</div>
<div style="font-size:10px;opacity:0.5;margin-top:2px">Formula: Variance = Actual − (Rated L/hr × Run Hours) | Source: Gen Run Hr + Daily Used + Consumption Per Hour from Blackout Hr Excel</div>
</div>""", unsafe_allow_html=True)

    # Calculate per-period variance
    def _period_var(dates_list):
        if not dates_list or site_daily.empty:
            return 0, 0
        sub = site_daily[site_daily["date"].isin(dates_list)]
        if sub.empty:
            return 0, 0
        hrs = sub["hours"].sum()
        lts = sub["liters"].sum()
        expected = rated_per_hr * hrs
        return expected, lts

    # Render all 4 variance cards
    _var_card(f"TOTAL PERIOD — {sid}", cp_total, ac_total, tn,
              f"{es} → {ee} ({ed} days) | {tg} generators", "total")

    st.markdown("---")

    # Generator detail table (total period)
    gd=gf.copy(); gd["expected_liters"]=gd["consumption_per_hour"]*gd["total_run_hrs"]
    gd["variance_L"]=gd["total_liters"]-gd["expected_liters"]
    gd["variance_pct"]=np.where(gd["expected_liters"]>0,(gd["variance_L"]/gd["expected_liters"]*100),0)
    gd["status"]=gd.apply(lambda r:"OVER" if r["variance_pct"]>20 else "UNDER" if r["variance_pct"]<-20 else "NORMAL" if r["expected_liters"]>0 else "NOT RUNNING",axis=1)
    dd=gd[["model_name","power_kva","consumption_per_hour","days_tracked","total_run_hrs","expected_liters","total_liters","variance_L","variance_pct","energy_cost","status"]].copy()
    dd["variance_pct"]=dd["variance_pct"].apply(lambda x:f"{x:+.0f}%"); dd["variance_L"]=dd["variance_L"].apply(lambda x:f"{x:+,.0f}" if pd.notna(x) and x!=0 else "—")
    dd["expected_liters"]=dd["expected_liters"].apply(lambda x:f"{x:,.0f}" if pd.notna(x) and x>0 else "—"); dd["energy_cost"]=dd["energy_cost"].apply(lambda x:f"{x:,.0f}")
    dd.columns=["Machine","KVA","Rated L/hr","Days","Run Hrs","Expected(L)","Actual(L)","Variance(L)","Var%","Cost(MMK)","Status"]
    render_smart_table(dd,title=f"Generator Detail — {sid}")
    if len(gf)>1:
        c1,c2=st.columns(2)
        with c1: grouped_bar(gd["model_name"].tolist(),[{"name":"Expected","data":[round(v) if pd.notna(v) else 0 for v in gd["expected_liters"]],"color":"#3b82f6"},{"name":"Actual","data":[round(v) for v in gd["total_liters"]],"color":"#ef4444"}],title="Expected vs Actual",height=350,key=f"gv_{tk}")
        with c2: ec_pie([{"name":r["model_name"],"value":round(r["energy_cost"])} for _,r in gf.iterrows()],title="Cost Split",key=f"gp_{tk}")
    st.markdown("---"); st.markdown(f"### 📈 Trends — {sid} ({period})")
    per=period
    t=get_trends(site_id=sid,period=per.lower(),date_from=str_from,date_to=str_to); ef,sf2=t["energy"],t["sales"]
    if not ef.empty:
        dt=ef["date"].tolist()
        if not sf2.empty:
            md=sorted(set(dt)&set(sf2["date"].tolist()))
            if md:
                sv_raw=[round(sf2[sf2["date"]==d]["sales_amt"].sum()) if not sf2[sf2["date"]==d].empty else 0 for d in md]
                dv_raw=[round(ef[ef["date"]==d]["energy_cost"].sum()) if not ef[ef["date"]==d].empty else 0 for d in md]
                sv_m=[round(v/1e6,1) for v in sv_raw]; dv_m=[round(v/1e6,2) for v in dv_raw]
                dual_axis_chart(md,sv_m,dv_m,title=f"Sales vs Diesel (M) — {per}",bar_name="Sales (M)",line_name="Diesel (M)",bar_color="#3b82f6",line_color="#ef4444",height=400,key=f"td_{tk}")
                mv=[round(sf2[sf2["date"]==d]["margin"].sum()) if not sf2[sf2["date"]==d].empty else 0 for d in md]
                mpv=[round(m/s*100,1) if s>0 else 0 for s,m in zip(sv_raw,mv)]; dpv=[round(d/s*100,2) if s>0 else 0 for s,d in zip(sv_raw,dv_raw)]
                ec_line(md,[{"name":"Diesel%","data":dpv,"color":"#ef4444"},{"name":"Margin%","data":mpv,"color":"#22c55e"}],title="Diesel% vs Margin%",height=350,key=f"tc_{tk}")
        else: ec_bar(dt,[round(v) if pd.notna(v) else 0 for v in ef["daily_used_liters"]],title=f"Diesel(L) — {per}",color="#ef4444",key=f"tb_{tk}")
        gt=get_trends(site_id=sid,period=per.lower(),date_from=str_from,date_to=str_to,view="generator"); gdf=gt["energy"]
        if not gdf.empty and "model_name" in gdf.columns:
            gn=sorted(gdf["model_name"].unique()); dg=sorted(gdf["date"].unique())
            sl=[{"name":n,"data":[round(gdf[(gdf["model_name"]==n)&(gdf["date"]==d)]["daily_used_liters"].sum()) if not gdf[(gdf["model_name"]==n)&(gdf["date"]==d)].empty else 0 for d in dg],"color":PALETTE[i%len(PALETTE)]} for i,n in enumerate(gn)]
            stacked_bar(dg,sl,title=f"Diesel by Generator — {per}",height=400,key=f"tg_{tk}")
        with st.expander("View data"): render_smart_table(ef,title=f"Trend Data — {sid}")
    else: st.info("No trend data.")


# ═══════════════════════════════════════════════════════════════════════════
# NEW SECTIONS: Threshold, Rankings, Fuel Price, Operations, Site Charts
# ═══════════════════════════════════════════════════════════════════════════

def _threshold_legend():
    """Render the 4-metric threshold reference table — icons only, no background colors."""
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Threshold Reference</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:left">Metric</th>
<th style="padding:10px 12px;text-align:center">🟢 Green</th>
<th style="padding:10px 12px;text-align:center">🟡 Yellow</th>
<th style="padding:10px 12px;text-align:center">🟠 Amber</th>
<th style="padding:10px 12px;text-align:center">🔴 Red</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;font-weight:600">Diesel Price (MMK/L)</td>
<td style="padding:8px 12px;text-align:center">🟢 &lt; 3,501</td>
<td style="padding:8px 12px;text-align:center">🟡 3,501 – 5,000</td>
<td style="padding:8px 12px;text-align:center">🟠 5,001 – 8,000</td>
<td style="padding:8px 12px;text-align:center">🔴 &gt; 8,000</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Blackout Hr</td>
<td style="padding:8px 12px;text-align:center">🟢 &lt; 4</td>
<td style="padding:8px 12px;text-align:center">🟡 4 – 8</td>
<td style="padding:8px 12px;text-align:center">🟠 8 – 12</td>
<td style="padding:8px 12px;text-align:center">🔴 &gt; 12</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Expense % on Sale</td>
<td style="padding:8px 12px;text-align:center">🟢 &lt; 0.9%</td>
<td style="padding:8px 12px;text-align:center">🟡 0.9% – 1.5%</td>
<td style="padding:8px 12px;text-align:center">🟠 1.5% – 3%</td>
<td style="padding:8px 12px;text-align:center">🔴 &gt; 3%</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Buffer Stock Days</td>
<td style="padding:8px 12px;text-align:center">🟢 7+</td>
<td style="padding:8px 12px;text-align:center">🟡 5 – 7</td>
<td style="padding:8px 12px;text-align:center">🟠 3 – 5</td>
<td style="padding:8px 12px;text-align:center">🔴 &lt; 3</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)


def _predictions_section(df, sector_filter=None, key_prefix="grp"):
    """All 15 predictions: fuel forecast, buffer depletion, blackout, theft, delivery, etc."""
    st.markdown("## 🔮 Predictions & Forecasts")

    site_ids = df["site_id"].tolist()
    if not site_ids:
        st.info("No sites for predictions.")
        return

    with get_db() as conn:
        ph = ",".join(["?"] * len(site_ids))
        _dsql, _dp = _date_sql("dss.date")
        # Daily data for forecasting
        hist = pd.read_sql_query(f"""
            SELECT dss.date, dss.site_id, dss.total_daily_used, dss.spare_tank_balance,
                   dss.total_gen_run_hr, dss.days_of_buffer, dss.blackout_hr
            FROM daily_site_summary dss
            WHERE dss.site_id IN ({ph}){_dsql} ORDER BY dss.date
        """, conn, params=site_ids + _dp)

        # Aggregate daily
        if hist.empty:
            st.info("Not enough data for predictions.")
            return

        daily_agg = hist.groupby("date").agg(
            total_used=("total_daily_used", "sum"),
            total_tank=("spare_tank_balance", "sum"),
            total_hours=("total_gen_run_hr", "sum"),
            avg_buffer=("days_of_buffer", "mean"),
            avg_blackout=("blackout_hr", "mean"),
            sites=("site_id", "nunique"),
        ).reset_index().sort_values("date")

        dates = daily_agg["date"].tolist()
        if len(dates) < 3:
            st.info("Need at least 3 days of data for predictions.")
            return

        # Fuel price
        fp_avg = conn.execute("SELECT AVG(price_per_liter) FROM fuel_purchases WHERE price_per_liter IS NOT NULL").fetchone()[0] or 0

    # ── Helper: simple linear forecast ──────────────────────────
    def _forecast(values, days=7):
        """Simple linear regression forecast."""
        n = len(values)
        if n < 3:
            return [], []
        x = list(range(n))
        y = values
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        num = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        forecast = [round(max(0, slope * (n + i) + intercept)) for i in range(days)]
        conf = [round(max(0, f * 0.85)) for f in forecast]  # lower bound
        return forecast, conf

    used_vals = daily_agg["total_used"].tolist()
    tank_vals = daily_agg["total_tank"].tolist()
    hours_vals = daily_agg["total_hours"].tolist()
    buffer_vals = [v if pd.notna(v) else 0 for v in daily_agg["avg_buffer"].tolist()]
    blackout_vals = [v if pd.notna(v) else 0 for v in daily_agg["avg_blackout"].tolist()]

    # Generate forecast dates
    from datetime import datetime, timedelta
    last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    fc_dates = [(last_date + timedelta(days=i+1)).strftime("%Y-%m-%d") for i in range(7)]
    all_dates_fc = dates + fc_dates

    # ── 1. Daily Fuel Consumption Forecast (7-day) ──────────────
    fc_used, fc_used_low = _forecast(used_vals)
    if fc_used:
        st.markdown("#### 1. Daily Fuel Consumption Forecast (7-Day)")
        hist_line = used_vals + [0] * 7
        fc_line = [0] * len(dates) + fc_used
        fc_low_line = [0] * len(dates) + fc_used_low
        ec_line(all_dates_fc, [
            {"name": "Historical", "data": hist_line, "color": "#3b82f6"},
            {"name": "Forecast", "data": fc_line, "color": "#ef4444"},
            {"name": "Lower Bound", "data": fc_low_line, "color": "#fca5a5"},
        ], title="Fuel Consumption Forecast (L/day)", height=350, key=f"pred_fuel_{key_prefix}")
        avg_fc = round(sum(fc_used) / len(fc_used))
        total_fc = sum(fc_used)
        st.caption(f"Predicted avg: {avg_fc:,} L/day | Total 7-day: {total_fc:,} L | Cost: {round(total_fc * fp_avg):,} MMK")

    # ── 2. Buffer Depletion Timeline ────────────────────────────
    st.markdown("#### 2. Buffer Depletion Timeline")
    with get_db() as conn:
        _dsql_b, _dp_b = _date_sql("d2.date")
        site_buf = pd.read_sql_query(f"""
            SELECT dss.site_id, dss.spare_tank_balance as tank, dss.total_daily_used as burn,
                   dss.days_of_buffer as buffer
            FROM daily_site_summary dss
            WHERE dss.site_id IN ({ph})
              AND dss.date = (SELECT MAX(d2.date) FROM daily_site_summary d2 WHERE d2.site_id = dss.site_id{_dsql_b})
        """, conn, params=site_ids + _dp_b)

    if not site_buf.empty:
        site_buf = site_buf.sort_values("buffer", na_position="last")
        critical = site_buf[site_buf["buffer"].notna() & (site_buf["buffer"] < 7)].head(15)
        if not critical.empty:
            sites_b = critical["site_id"].tolist()
            buf_v = [round(v, 1) if pd.notna(v) else 0 for v in critical["buffer"].tolist()]
            ec_hbar(sites_b, buf_v, title="Sites Running Out Soonest (days of buffer)",
                    colors=["#dc2626" if v < 3 else "#d97706" if v < 7 else "#16a34a" for v in buf_v],
                    key=f"pred_depl_{key_prefix}")
            _chart_guide(
                "Days of fuel remaining per site, ranked from <b>lowest to highest</b> (most urgent first).\nExample: Site CP-CCMDY has only <b>0.9 days</b> of fuel left.",
                [{"data": "Tank Balance", "file": "Blackout Hr Excel", "col": "Spare Tank Balance", "method": "Latest value per site"},
                 {"data": "Daily Burn", "file": "Blackout Hr Excel", "col": "Blackout Hr × Consumption/Hr", "method": "AVG last 7 days"}],
                [("green", "🟢 Long bars (7+ days) = Safe, no rush"),
                 ("amber", "🟡 Medium bars (3-7 days) = Plan delivery this week"),
                 ("red", "🔴 Short bars (< 3 days) = URGENT, send fuel truck TODAY")],
                "Shows which stores will <b>run out of fuel first</b>. Like a <b>priority queue for fuel delivery</b>. The shortest bars are the most urgent — those stores have less than <r>3 days of fuel</r> and will <r>go dark</r> if not refueled. Start the fuel truck with the shortest bars first."
            )
        else:
            st.success("All sites have 7+ days buffer.")

    # ── 3. Weekly Budget Forecast ───────────────────────────────
    st.markdown("#### 3. Weekly Budget Forecast")
    if fc_used:
        weekly_liters = sum(fc_used)
        weekly_cost = round(weekly_liters * fp_avg)
        daily_cost = round(weekly_cost / 7)
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.metric_card(title="Next 7 Days Fuel", content=f"{weekly_liters:,} L", key=f"pred_wl_{key_prefix}")
        with c2:
            ui.metric_card(title="Weekly Cost", content=f"{weekly_cost:,} MMK", description=f"@ {fp_avg:,.0f}/L", key=f"pred_wc_{key_prefix}")
        with c3:
            ui.metric_card(title="Daily Avg Cost", content=f"{daily_cost:,} MMK", key=f"pred_dc_{key_prefix}")

    # ── 4. Blackout Duration Forecast ───────────────────────────
    if any(v > 0 for v in blackout_vals):
        fc_bo, _ = _forecast(blackout_vals)
        if fc_bo:
            st.markdown("#### 4. Blackout Duration Forecast")
            hist_bo = blackout_vals + [0] * 7
            fc_bo_line = [0] * len(dates) + [round(v, 1) for v in fc_bo]
            ec_line(all_dates_fc, [
                {"name": "Historical Avg", "data": [round(v, 1) for v in blackout_vals] + [0]*7, "color": "#d97706"},
                {"name": "Forecast", "data": fc_bo_line, "color": "#ef4444"},
            ], title="Avg Blackout Hours Forecast", height=300, key=f"pred_bo_{key_prefix}")
            st.caption(f"Predicted avg blackout: {round(sum(fc_bo)/7, 1)} hrs/day next week")

    # ── 5. Sales Impact Forecast ────────────────────────────────
    with get_db() as conn:
        _dsql_s, _dp_s = _date_sql("date")
        sales_daily = pd.read_sql_query(f"""
            SELECT date, SUM(sales_amt) as sales FROM daily_sales
            WHERE site_id IN ({ph}){_dsql_s} GROUP BY date ORDER BY date
        """, conn, params=site_ids + _dp_s)

    if not sales_daily.empty and len(sales_daily) >= 3 and any(v > 0 for v in blackout_vals):
        st.markdown("#### 5. Sales Impact — Blackout Correlation")
        merged = sorted(set(dates) & set(sales_daily["date"].tolist()))
        if len(merged) >= 3:
            s_vals = [round(sales_daily[sales_daily["date"]==d]["sales"].sum()/1e6, 1) if not sales_daily[sales_daily["date"]==d].empty else 0 for d in merged]
            b_vals = [round(daily_agg[daily_agg["date"]==d]["avg_blackout"].mean(), 1) if not daily_agg[daily_agg["date"]==d].empty else 0 for d in merged]
            dual_axis_chart(merged, s_vals, b_vals,
                            title="Sales (M) vs Blackout Hours",
                            bar_name="Sales (M)", line_name="Blackout Hr",
                            bar_color="#3b82f6", line_color="#d97706", height=300, key=f"pred_si_{key_prefix}")
            st.caption("If higher blackout = lower sales → blackout is costing revenue")

    # ── 6. Generator Failure Risk ───────────────────────────────
    try:
        maint = get_generator_failure_risk()
        if not maint.empty:
            if sector_filter:
                maint = maint[maint["sector_id"] == sector_filter]
            high = maint[maint["risk_level"].isin(["HIGH", "MEDIUM"])]
            if not high.empty:
                st.markdown("#### 6. Generator Failure Risk")
                risk_counts = high["risk_level"].value_counts()
                c1, c2 = st.columns(2)
                with c1:
                    ui.metric_card(title="🔴 HIGH Risk", content=str(risk_counts.get("HIGH", 0)),
                                   description="generators need service", key=f"pred_rh_{key_prefix}")
                with c2:
                    ui.metric_card(title="🟡 MEDIUM Risk", content=str(risk_counts.get("MEDIUM", 0)),
                                   description="approaching service interval", key=f"pred_rm_{key_prefix}")
                rd = high[["site_id", "model_name", "total_hours", "risk_level", "maintenance_note"]].head(10).copy()
                rd["total_hours"] = rd["total_hours"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                rd.columns = ["Site", "Generator", "Total Hours", "Risk", "Note"]
                render_smart_table(rd, title="At-Risk Generators", severity_col="Risk")
    except Exception:
        pass

    # ── 7. Optimal Delivery Schedule ────────────────────────────
    st.markdown("#### 7. Optimal Delivery Schedule")
    if not site_buf.empty:
        need_fuel = site_buf[(site_buf["buffer"].notna()) & (site_buf["buffer"] < 7) & (site_buf["burn"] > 0)].copy()
        if not need_fuel.empty:
            need_fuel["liters_needed"] = need_fuel.apply(lambda r: max(0, round(7 * r["burn"] - r["tank"])), axis=1)
            need_fuel["days_until_empty"] = need_fuel["buffer"].round(1)
            need_fuel["deliver_by"] = need_fuel["buffer"].apply(
                lambda d: (last_date + timedelta(days=max(0, int(d) - 1))).strftime("%Y-%m-%d") if pd.notna(d) else "ASAP")
            need_fuel["urgency"] = need_fuel["buffer"].apply(
                lambda d: "🔴 IMMEDIATE" if d < 1 else "🔴 TODAY" if d < 2 else "🟠 TOMORROW" if d < 3 else "🟡 THIS WEEK")
            nd = need_fuel[["site_id", "urgency", "days_until_empty", "tank", "burn", "liters_needed", "deliver_by"]].copy()
            nd["tank"] = nd["tank"].apply(lambda x: f"{x:,.0f}")
            nd["burn"] = nd["burn"].apply(lambda x: f"{x:,.0f}")
            nd["liters_needed"] = nd["liters_needed"].apply(lambda x: f"{x:,.0f}")
            nd.columns = ["Site", "Urgency", "Days Left", "Tank (L)", "Burn/Day", "Need (L)", "Deliver By"]
            render_smart_table(nd.sort_values("Days Left"), title=f"Delivery Schedule ({len(need_fuel)} sites need fuel)")
            total_needed = need_fuel["liters_needed"].sum()
            st.caption(f"Total diesel needed: {total_needed:,.0f} L | Est. cost: {round(total_needed * fp_avg):,} MMK")
        else:
            st.success("All sites have 7+ days — no deliveries needed this week.")

    # ── 8. Diesel Price Alert ───────────────────────────────────
    try:
        fc_price = forecast_fuel_price()
        if fc_price and not fc_price.get("error") and not fc_price["forecast"].empty:
            st.markdown("#### 8. Diesel Price Alert")
            fcast = fc_price["forecast"]
            max_pred = fcast["predicted_price"].max()
            current = fc_price["history"]["price"].iloc[-1] if not fc_price["history"].empty else 0
            trend = fc_price.get("trend", "stable")
            if trend == "rising":
                st.warning(f"⚠️ **Price RISING** — current: {current:,.0f} MMK/L → predicted max: {max_pred:,.0f} MMK/L next 7 days")
            elif trend == "falling":
                st.success(f"✅ **Price FALLING** — current: {current:,.0f} MMK/L → good time to buy")
            else:
                st.info(f"Price STABLE around {current:,.0f} MMK/L")
            if max_pred > 8000:
                st.error(f"🔴 **ALERT: Price may exceed 8,000 MMK/L** — predicted peak: {max_pred:,.0f}")
    except Exception:
        pass

    # ── 9. Store Open/Close Recommendation ──────────────────────
    st.markdown("#### 9. Store Open/Close Prediction")
    matched = df[df["has_sales"] == True].copy() if "has_sales" in df.columns else pd.DataFrame()
    if not matched.empty and "energy_pct" in matched.columns:
        # Predict trend: if diesel% is rising, more stores will need to close
        close_now = matched[matched["energy_pct"] > 30]
        reduce_now = matched[(matched["energy_pct"] > 15) & (matched["energy_pct"] <= 30)]
        monitor_now = matched[(matched["energy_pct"] > 5) & (matched["energy_pct"] <= 15)]
        open_now = matched[matched["energy_pct"] <= 5]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div style="text-align:center;padding:10px;border:1px solid #e5e7eb;border-radius:8px"><div style="font-size:24px;font-weight:700;color:#16a34a">{len(open_now)}</div><div style="font-size:11px">🟢 OPEN</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="text-align:center;padding:10px;border:1px solid #e5e7eb;border-radius:8px"><div style="font-size:24px;font-weight:700;color:#d97706">{len(monitor_now)}</div><div style="font-size:11px">🟡 MONITOR</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="text-align:center;padding:10px;border:1px solid #e5e7eb;border-radius:8px"><div style="font-size:24px;font-weight:700;color:#ea580c">{len(reduce_now)}</div><div style="font-size:11px">🟠 REDUCE</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div style="text-align:center;padding:10px;border:1px solid #e5e7eb;border-radius:8px"><div style="font-size:24px;font-weight:700;color:#dc2626">{len(close_now)}</div><div style="font-size:11px">🔴 CLOSE</div></div>', unsafe_allow_html=True)

        if not close_now.empty:
            cl = close_now[["site_id", "energy_pct", "total_sales", "energy_cost"]].head(10).copy()
            cl["energy_pct"] = cl["energy_pct"].apply(lambda x: f"{x:.1f}%")
            cl["total_sales"] = cl["total_sales"].apply(lambda x: f"{x/1e6:,.1f}M")
            cl["energy_cost"] = cl["energy_cost"].apply(lambda x: f"{x/1e6:,.2f}M")
            cl.columns = ["Site", "Diesel %", "Sales", "Diesel Cost"]
            render_smart_table(cl, title="🔴 Recommend CLOSE — Diesel > 30% of Sales")

    # ── 10. Fuel Theft Probability ──────────────────────────────
    st.markdown("#### 10. Fuel Theft / Waste Detection")
    try:
        anomalies = get_consumption_anomalies()
        if not anomalies.empty:
            if sector_filter:
                anomalies = anomalies[anomalies["sector_id"] == sector_filter]
            if not anomalies.empty:
                # Score: higher % above avg = higher theft probability
                anomalies["theft_score"] = anomalies["pct_above_avg"].clip(0, 100)
                top_theft = anomalies.sort_values("theft_score", ascending=False).head(10)
                ec_hbar(top_theft["site_id"].tolist(),
                        [round(v) for v in top_theft["theft_score"].tolist()],
                        title="Theft/Waste Probability Score (% above 7d avg)",
                        colors=["#dc2626" if v > 50 else "#d97706" if v > 30 else "#3b82f6" for v in top_theft["theft_score"]],
                        key=f"pred_theft_{key_prefix}")
                st.caption("Red >50% above avg = high theft risk | Amber >30% = investigate | Blue = normal spike")
            else:
                st.success("No consumption anomalies detected.")
    except Exception:
        st.success("No anomaly data available.")

    # ── 11. Efficiency Forecast ─────────────────────────────────
    eff_vals = [round(u / max(h, 1), 1) for u, h in zip(used_vals, hours_vals)]
    if len(eff_vals) >= 3:
        fc_eff, _ = _forecast(eff_vals)
        if fc_eff:
            st.markdown("#### 11. Efficiency Forecast (L/Hr)")
            ec_line(all_dates_fc, [
                {"name": "Historical", "data": [round(v, 1) for v in eff_vals] + [0]*7, "color": "#8b5cf6"},
                {"name": "Forecast", "data": [0]*len(dates) + [round(v, 1) for v in fc_eff], "color": "#ef4444"},
            ], title="Efficiency L/Hr — 7 Day Forecast", height=300, key=f"pred_eff_{key_prefix}")
            avg_eff_fc = round(sum(fc_eff) / 7, 1)
            avg_eff_hist = round(sum(eff_vals) / len(eff_vals), 1)
            if avg_eff_fc > avg_eff_hist * 1.15:
                st.warning(f"⚠️ Efficiency worsening: {avg_eff_hist} → {avg_eff_fc} L/Hr (waste increasing)")
            else:
                st.caption(f"Predicted: {avg_eff_fc} L/Hr | Historical avg: {avg_eff_hist} L/Hr")

    # ── 12. Buffer Days Forecast ────────────────────────────────
    if len(buffer_vals) >= 3:
        fc_buf, _ = _forecast(buffer_vals)
        if fc_buf:
            st.markdown("#### 12. Buffer Days Forecast")
            ec_line(all_dates_fc, [
                {"name": "Historical", "data": [round(v, 1) for v in buffer_vals] + [0]*7, "color": "#3b82f6"},
                {"name": "Forecast", "data": [0]*len(dates) + [round(v, 1) for v in fc_buf], "color": "#ef4444"},
            ], title="Avg Buffer Days — 7 Day Forecast", height=300,
               mark_lines=[{"value": 7, "label": "Safe", "color": "#16a34a"},
                           {"value": 3, "label": "Critical", "color": "#dc2626"}],
               key=f"pred_buf_{key_prefix}")
            if any(v < 3 for v in fc_buf):
                st.error("🔴 **Buffer predicted to drop below CRITICAL (3 days) next week!**")
            elif any(v < 7 for v in fc_buf):
                st.warning("⚠️ Buffer predicted to drop below safe threshold (7 days)")

    # ── 13. Gen Hours Forecast ──────────────────────────────────
    if len(hours_vals) >= 3:
        fc_hrs, _ = _forecast(hours_vals)
        if fc_hrs:
            st.markdown("#### 13. Generator Hours Forecast")
            ec_line(all_dates_fc, [
                {"name": "Historical", "data": [round(v) for v in hours_vals] + [0]*7, "color": "#3b82f6"},
                {"name": "Forecast", "data": [0]*len(dates) + fc_hrs, "color": "#ef4444"},
            ], title="Total Gen Hours — 7 Day Forecast", height=300, key=f"pred_hrs_{key_prefix}")

    # ── 14. Cost Trend Forecast ─────────────────────────────────
    cost_vals = [round(u * fp_avg / 1e6, 2) for u in used_vals]
    if len(cost_vals) >= 3:
        fc_cost, _ = _forecast(cost_vals)
        if fc_cost:
            st.markdown("#### 14. Diesel Cost Forecast (M MMK)")
            ec_line(all_dates_fc, [
                {"name": "Historical", "data": cost_vals + [0]*7, "color": "#ef4444"},
                {"name": "Forecast", "data": [0]*len(dates) + [round(v, 2) for v in fc_cost], "color": "#dc2626"},
            ], title="Daily Diesel Cost Forecast (M MMK)", height=300, key=f"pred_cost_{key_prefix}")
            weekly_cost_fc = round(sum(fc_cost), 1)
            st.caption(f"Predicted weekly diesel cost: {weekly_cost_fc}M MMK")

    # ── 15. Cross-Site Resource Sharing ─────────────────────────
    try:
        transfers = get_resource_sharing_opportunities()
        if transfers:
            if sector_filter:
                transfers = [t for t in transfers if t.get("from_sector") == sector_filter or t.get("to_sector") == sector_filter]
            if transfers:
                st.markdown("#### 15. Cross-Site Fuel Transfer Opportunities")
                total_save = sum(t.get("transfer_liters", 0) for t in transfers)
                st.info(f"💡 **{len(transfers)} transfer opportunities** — could redistribute {total_save:,.0f} L without new purchases")
                tf_df = pd.DataFrame(transfers[:10])
                if not tf_df.empty:
                    td = tf_df[["from_site", "from_buffer", "to_site", "to_buffer", "transfer_liters"]].copy()
                    td["from_buffer"] = td["from_buffer"].apply(lambda x: f"{x:.1f}d" if pd.notna(x) else "—")
                    td["to_buffer"] = td["to_buffer"].apply(lambda x: f"{x:.1f}d" if pd.notna(x) else "—")
                    td["transfer_liters"] = td["transfer_liters"].apply(lambda x: f"{x:,.0f} L")
                    td.columns = ["From (surplus)", "Buffer", "To (critical)", "Buffer", "Transfer"]
                    render_smart_table(td, title="Recommended Transfers")
    except Exception:
        pass


def _top15_charts(df, key_prefix="grp"):
    """Top 15 by Diesel % of Sales + Top 15 by Diesel Cost."""
    matched = df[(df["has_sales"] == True) & (df["energy_pct"].notna())].copy() if "has_sales" in df.columns and "energy_pct" in df.columns else pd.DataFrame()
    c1, c2 = st.columns(2)
    with c1:
        if not matched.empty and len(matched) > 0:
            top = matched.sort_values("energy_pct", ascending=False).head(15)
            if len(top) > 0:
                rc = {"OPEN": "#16a34a", "MONITOR": "#d97706", "REDUCE": "#ea580c", "CLOSE": "#dc2626"}
                cats = top["site_id"].tolist()
                vals = [round(v, 2) if pd.notna(v) else 0 for v in top["energy_pct"].tolist()]
                clrs = [rc.get(str(r.get("recommendation", "")), "#ef4444") for _, r in top.iterrows()]
                ec_hbar(cats, vals,
                        title="Top 15 — Diesel % of Sales (worst first)",
                        colors=clrs, key=f"top15pct_{key_prefix}")
                _chart_guide(
                    "Diesel cost as a percentage of sales, ranked from <b>worst to best</b> (highest % first).\nExample: A site at <b>8.5%</b> means 8.5 MMK of every 100 MMK sales goes to diesel.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per site"},
                     {"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "LATEST on date"},
                     {"data": "Sales Revenue", "file": "Sales Excel", "col": "SALES_AMT", "method": "SUM per site"}],
                    [("green", "🟢 OPEN (< 5%) = Healthy, fuel cost is small vs revenue"),
                     ("amber", "🟡 MONITOR (5-15%) = Fuel starting to eat profits"),
                     ("orange", "🟠 REDUCE (15-30%) = Reduce store hours during blackouts"),
                     ("red", "🔴 CLOSE (> 30%) = Store losing money, consider closing during outages")],
                    "Shows which stores are <b>losing the most money to fuel</b>. Like checking which of your shops has the <b>highest electricity bill relative to sales</b>. A store at <r>30%</r> means <r>almost a third</r> of its revenue goes just to diesel — it may be cheaper to <r>close during blackouts</r> than keep it open."
                )
        else:
            st.info("No sales-matched data for ranking.")
    with c2:
        cost_df = df[df["energy_cost"].notna() & (df["energy_cost"] > 0)].copy() if "energy_cost" in df.columns else pd.DataFrame()
        if not cost_df.empty:
            cost_top = cost_df.sort_values("energy_cost", ascending=False).head(15)
            if len(cost_top) > 0:
                ec_hbar(cost_top["site_id"].tolist(),
                        [round(v) if pd.notna(v) else 0 for v in cost_top["energy_cost"].tolist()],
                        title="Top 15 — Diesel Cost (MMK)",
                        key=f"top15cost_{key_prefix}")
                _chart_guide(
                    "Total diesel cost in MMK per site, ranked <b>highest to lowest</b>.\nExample: Top site spent <b>12.5M MMK</b> on diesel in this period.",
                    [{"data": "Diesel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per site"},
                     {"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "LATEST on date"}],
                    [("green", "✅ Short bars = Low cost sites, efficient"),
                     ("amber", "⚠️ Long bars = Expensive to power, check if sales justify it"),
                     ("red", "🔴 Very long bars = Most expensive sites, may need operational changes")],
                    "Shows which stores have the <b>biggest fuel bill</b>. Like ranking your <b>company vehicles by monthly fuel spend</b>. The longest bar = most expensive site to keep running. Ask: does this store make <b>enough revenue</b> to justify this fuel cost? If not, consider <r>reducing hours</r>."
                )
        else:
            st.info("No diesel cost data.")


def _mapped_unmapped(df, key_prefix="grp"):
    """Mapped vs Unmapped sites tables + decision summary."""
    matched = df[df["has_sales"] == True].copy() if "has_sales" in df.columns else pd.DataFrame()
    unmatched = df[df["has_sales"] != True].copy() if "has_sales" in df.columns else pd.DataFrame()

    if not matched.empty:
        tot_sales = matched["total_sales"].sum()
        tot_energy = matched["energy_cost"].sum()
        pct = (tot_energy / tot_sales * 100) if tot_sales > 0 else 0
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            ui.metric_card(title="Mapped Sites Sales", content=f"{tot_sales/1e6:,.1f}M MMK",
                           description=f"{len(matched)} sites", key=f"ms_sales_{key_prefix}")
        with mc2:
            ui.metric_card(title="Mapped Diesel Cost", content=f"{tot_energy/1e6:,.1f}M MMK",
                           description=f"across {len(matched)} sites", key=f"ms_diesel_{key_prefix}")
        with mc3:
            ui.metric_card(title="Avg Diesel %", content=f"{pct:.2f}%",
                           description="cost ÷ sales", key=f"ms_pct_{key_prefix}")

        md = matched[["site_id", "diesel_available", "energy_cost", "total_sales",
                       "energy_pct", "energy_days", "recommendation"]].copy()
        md["energy_cost"] = md["energy_cost"].apply(lambda x: f"{x:,.0f}")
        md["total_sales"] = md["total_sales"].apply(lambda x: f"{x:,.0f}")
        md["energy_pct"] = md["energy_pct"].apply(lambda x: f"{x:.2f}%")
        md["diesel_available"] = md["diesel_available"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
        md.columns = ["Store", "Tank (L)", "Diesel Cost", "Sales", "Diesel %", "E.Days", "Decision"]
        render_smart_table(md, title="Mapped Sites (with Sales)", severity_col="Decision")
    else:
        st.info("No stores mapped to sales data.")

    if not unmatched.empty:
        with st.expander(f"⚡ {len(unmatched)} sites without sales data"):
            cols = [c for c in ["site_id", "sector_id", "num_generators", "diesel_available", "total_liters", "energy_cost"] if c in unmatched.columns]
            ud = unmatched[cols].copy()
            if "diesel_available" in ud.columns:
                ud["diesel_available"] = ud["diesel_available"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
            if "energy_cost" in ud.columns:
                ud["energy_cost"] = ud["energy_cost"].apply(lambda x: f"{x:,.0f}")
            if "total_liters" in ud.columns:
                ud["total_liters"] = ud["total_liters"].apply(lambda x: f"{x:,.0f}")
            names = ["Store", "Sector", "Gens", "Tank (L)", "Diesel Used", "Diesel Cost"][:len(cols)]
            ud.columns = names
            render_smart_table(ud, title="Unmapped Sites")


def _fuel_price_section(key_prefix="grp"):
    """Fuel price trend, purchase log, 7-day forecast."""
    st.markdown("## ⛽ Fuel Price Intelligence")

    with get_db() as conn:
        _dsql, _dp = _date_sql("date")
        fp_df = pd.read_sql_query(f"""
            SELECT date, sector_id, region, supplier, fuel_type, quantity_liters, price_per_liter
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL{_dsql} ORDER BY date DESC
        """, conn, params=_dp)

    if fp_df.empty:
        st.info("No fuel purchase data. Upload Daily Fuel Price Excel via Data Entry.")
        return

    # KPIs
    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        ui.metric_card(title="Total Purchases", content=str(len(fp_df)), key=f"fp_cnt_{key_prefix}")
    with kc2:
        ui.metric_card(title="Total Volume", content=f"{fp_df['quantity_liters'].sum():,.0f} L", key=f"fp_vol_{key_prefix}")
    with kc3:
        ui.metric_card(title="Avg Price/L", content=f"{fp_df['price_per_liter'].mean():,.0f} MMK", key=f"fp_avg_{key_prefix}")
    with kc4:
        ui.metric_card(title="Max Price/L", content=f"{fp_df['price_per_liter'].max():,.0f} MMK", key=f"fp_max_{key_prefix}")

    # Daily price trend by supplier
    c1, c2 = st.columns(2)
    with c1:
        trend_data = fp_df.groupby(["date", "supplier"])["price_per_liter"].mean().reset_index()
        if not trend_data.empty:
            suppliers = sorted(trend_data["supplier"].dropna().unique())
            dates = sorted(trend_data["date"].unique())
            if suppliers and dates:
                lines = []
                for i, s in enumerate(suppliers):
                    sdata = []
                    for d in dates:
                        sub = trend_data[(trend_data["date"]==d)&(trend_data["supplier"]==s)]
                        sdata.append(round(sub["price_per_liter"].mean()) if not sub.empty and pd.notna(sub["price_per_liter"].mean()) else 0)
                    lines.append({"name": s, "data": sdata, "color": PALETTE[i % len(PALETTE)]})
                ec_line(dates, lines, title="Daily Price Trend by Supplier", height=380, key=f"fp_trend_{key_prefix}")
                _chart_guide(
                    "Fuel price per liter (MMK) each day, one line for each supplier.\nExample: Denko at <b>7,085 MMK/L</b> vs Moon Sun at <b>6,900 MMK/L</b>.",
                    [{"data": "Fuel Price", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "AVG per supplier per date"}],
                    [("green", "✅ Flat or falling lines = Fuel prices stable or decreasing"),
                     ("amber", "⚠️ Rising lines = Market prices going up, budget impact coming"),
                     ("red", "🔴 Sharp spike = Major price increase, consider bulk buying before next hike")],
                    "Like checking <b>petrol station prices</b> every day. Each line is a different <b>supplier</b>. The <g>lower line</g> is the <g>cheaper option</g> — buy from them. If both lines are <a>rising</a>, fuel is getting more expensive everywhere and your <r>diesel budget will increase</r>."
                )

    with c2:
        vol_data = fp_df.groupby("supplier")["quantity_liters"].sum().reset_index().sort_values("quantity_liters", ascending=False)
        if not vol_data.empty and len(vol_data) > 0:
            ec_hbar(vol_data["supplier"].tolist(),
                    [round(v) if pd.notna(v) else 0 for v in vol_data["quantity_liters"].tolist()],
                    title="Purchase Volume by Supplier", key=f"fp_vol_bar_{key_prefix}")
            _chart_guide(
                "Total diesel liters purchased from each supplier in this period.",
                [{"data": "Purchase Volume", "file": "Daily Fuel Price Excel", "col": "Quantity (Liters)", "method": "SUM per supplier"}],
                [("green", "✅ Balanced bars = Buying from multiple suppliers (good diversification)"),
                 ("amber", "⚠️ One bar much longer = Heavily dependent on one supplier"),
                 ("blue", "💡 Longer bar = More volume = Stronger negotiating position with that supplier")],
                "Shows <b>who we buy the most fuel from</b>. Like checking which <b>grocery store you spend the most at</b>. The longest bar is your <b>main supplier</b>. Use this for <b>price negotiation</b> — if you buy 80% from one supplier, you have leverage to ask for a <g>better price</g>."
            )

    # 7-Day Forecast
    try:
        fc = forecast_fuel_price()
        if fc and not fc.get("error") and not fc["forecast"].empty and not fc["history"].empty:
            hist = fc["history"]
            fcast = fc["forecast"]
            # Use only historical dates for history line, only forecast dates for forecast line
            hist_dates = hist["date"].tolist()
            fcast_dates = fcast["date"].tolist()
            hist_vals = [round(v) if pd.notna(v) else 0 for v in hist["price"].tolist()]
            pred_vals = [round(v) if pd.notna(v) else 0 for v in fcast["predicted_price"].tolist()]
            upper_vals = [round(v) if pd.notna(v) else 0 for v in fcast["upper_bound"].tolist()]
            lower_vals = [round(v) if pd.notna(v) else 0 for v in fcast["lower_bound"].tolist()]
            # Combine into continuous arrays (0 padding for gaps)
            all_dates = hist_dates + fcast_dates
            hist_full = hist_vals + [0] * len(fcast_dates)
            pred_full = [0] * len(hist_dates) + pred_vals
            upper_full = [0] * len(hist_dates) + upper_vals
            lower_full = [0] * len(hist_dates) + lower_vals
            if all_dates:
                lines_fc = [
                    {"name": "Historical", "data": hist_full, "color": "#3b82f6"},
                    {"name": "Forecast", "data": pred_full, "color": "#ef4444"},
                    {"name": "Upper 95%", "data": upper_full, "color": "#fca5a5"},
                    {"name": "Lower 95%", "data": lower_full, "color": "#93c5fd"},
                ]
                r2 = fc.get("r_squared", 0) or 0
                trend_lbl = (fc.get("trend") or "stable").upper()
                ec_line(all_dates, lines_fc, title=f"7-Day Price Forecast (Trend: {trend_lbl}, R²: {r2:.2f})",
                        height=380, key=f"fp_forecast_{key_prefix}")
                _chart_guide(
                    "Machine learning predicts fuel prices for the <b>next 7 days</b> based on purchase history.\nR² score shows prediction reliability (closer to <b>1.0</b> = more accurate).",
                    [{"data": "Historical Prices", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "All historical data"},
                     {"data": "Prediction", "file": "ML Model", "col": "Ridge Regression output", "method": "7-day forecast"}],
                    [("blue", "🔵 Blue line = Actual past prices (what we really paid)"),
                     ("red", "🔴 Red line = Predicted future prices (ML forecast)"),
                     ("amber", "🟡 Light bands = 95% confidence range (price likely falls within this)")],
                    "Like a <b>weather forecast for fuel prices</b>. Blue = what actually happened. Red = what the computer <b>predicts will happen</b> next week. The light bands show the <a>range of uncertainty</a>. If the red line is <r>rising</r>, consider <b>buying fuel now</b> before prices go up more. R² close to 1.0 = <g>reliable forecast</g>."
                )
    except Exception:
        pass

    # Purchase Log
    with st.expander("📋 Purchase Log"):
        log = fp_df.head(100).copy()
        log["quantity_liters"] = log["quantity_liters"].apply(lambda x: f"{x:,.0f}")
        log["price_per_liter"] = log["price_per_liter"].apply(lambda x: f"{x:,.0f}")
        log.columns = ["Date", "Sector", "Region", "Supplier", "Fuel Type", "Quantity (L)", "Price/L (MMK)"]
        render_smart_table(log, title="Recent Purchases (last 100)")


def _operations_section(sector_filter=None, key_prefix="grp"):
    """Generator fleet status, cross-site transfer, maintenance, blackout monitor, anomalies."""
    st.markdown("## ⚙️ Operations & Fleet")

    # Generator Fleet Status KPIs
    with get_db() as conn:
        gen_q = "SELECT g.site_id, s.sector_id, g.model_name, g.power_kva, g.is_active FROM generators g JOIN sites s ON g.site_id = s.site_id WHERE g.is_active = 1"
        gens = pd.read_sql_query(gen_q, conn)
        _dsql_o, _dp_o = _date_sql("date")
        ops_q = f"SELECT DISTINCT site_id FROM daily_operations WHERE gen_run_hr > 0{_dsql_o}"
        running_sites = set(r[0] for r in conn.execute(ops_q, _dp_o).fetchall())

    if sector_filter:
        gens = gens[gens["sector_id"] == sector_filter]

    if not gens.empty:
        total_gens = len(gens)
        running = len(gens[gens["site_id"].isin(running_sites)])
        idle = total_gens - running
        total_kva = gens["power_kva"].sum()

        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            ui.metric_card(title="Total Generators", content=str(total_gens), key=f"gf_total_{key_prefix}")
        with gc2:
            ui.metric_card(title="Running", content=str(running), description="have logged hours", key=f"gf_run_{key_prefix}")
        with gc3:
            ui.metric_card(title="Idle", content=str(idle), description="0 hours logged", key=f"gf_idle_{key_prefix}")
        with gc4:
            ui.metric_card(title="Total Capacity", content=f"{total_kva:,.0f} KVA", key=f"gf_kva_{key_prefix}")

    # Cross-Site Fuel Transfer
    try:
        transfers = get_resource_sharing_opportunities()
        if transfers:
            if sector_filter:
                transfers = [t for t in transfers if t.get("from_sector") == sector_filter or t.get("to_sector") == sector_filter]
            if transfers:
                st.markdown("#### 🔄 Cross-Site Fuel Transfer Recommendations")
                tf_df = pd.DataFrame(transfers)
                tf_display = tf_df[["from_site", "from_buffer", "to_site", "to_buffer", "transfer_liters"]].copy()
                tf_display["from_buffer"] = tf_display["from_buffer"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
                tf_display["to_buffer"] = tf_display["to_buffer"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
                tf_display["transfer_liters"] = tf_display["transfer_liters"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                tf_display.columns = ["From Site", "From Buffer (days)", "To Site", "To Buffer (days)", "Transfer (L)"]
                render_smart_table(tf_display, title="Recommended Transfers")
    except Exception:
        pass

    # Load Optimization
    try:
        load_df = get_load_optimization()
        if not load_df.empty:
            if sector_filter:
                load_df = load_df[load_df["sector_id"] == sector_filter]
            if not load_df.empty:
                with st.expander("🔩 Generator Load Optimization"):
                    ld = load_df[["site_id", "model_name", "power_kva", "consumption_per_hour",
                                   "avg_run_hr", "kva_per_liter", "recommendation"]].copy()
                    ld["power_kva"] = ld["power_kva"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                    ld["consumption_per_hour"] = ld["consumption_per_hour"].apply(lambda x: f"{x:,.1f}" if pd.notna(x) else "—")
                    ld["avg_run_hr"] = ld["avg_run_hr"].apply(lambda x: f"{x:,.1f}" if pd.notna(x) else "—")
                    ld["kva_per_liter"] = ld["kva_per_liter"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
                    ld.columns = ["Site", "Generator", "KVA", "L/hr", "Avg Run Hr", "KVA/L", "Role"]
                    render_smart_table(ld, title="Load Optimization Ranking", severity_col="Role")
    except Exception:
        pass

    # Maintenance Schedule
    try:
        maint_df = get_generator_failure_risk()
        if not maint_df.empty:
            if sector_filter:
                maint_df = maint_df[maint_df["sector_id"] == sector_filter]
            high_risk = maint_df[maint_df["risk_level"].isin(["HIGH", "MEDIUM"])]
            if not high_risk.empty:
                st.markdown("#### 🔧 Maintenance Alerts")
                md = high_risk[["site_id", "model_name", "total_hours", "risk_level", "maintenance_note"]].copy()
                md["total_hours"] = md["total_hours"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                md.columns = ["Site", "Generator", "Total Hours", "Risk", "Note"]
                render_smart_table(md, title=f"Maintenance Attention ({len(high_risk)} generators)", severity_col="Risk")
            else:
                st.success("All generators within safe service intervals.")
    except Exception:
        pass

    # Blackout Monitor (top 15 by run hours)
    with get_db() as conn:
        _dsql_bo, _dp_bo = _date_sql("do.date")
        bo_q = f"""
            SELECT do.site_id, s.sector_id, SUM(do.gen_run_hr) as total_hours, COUNT(DISTINCT do.date) as days
            FROM daily_operations do JOIN sites s ON do.site_id = s.site_id
            WHERE do.gen_run_hr > 0{_dsql_bo}
        """
        bp = list(_dp_bo)
        if sector_filter:
            bo_q += " AND s.sector_id = ?"
            bp.append(sector_filter)
        bo_q += " GROUP BY do.site_id ORDER BY total_hours DESC LIMIT 15"
        bo_top = pd.read_sql_query(bo_q, conn, params=bp)

    if not bo_top.empty:
        st.markdown("#### 🔌 Top 15 Sites by Generator Run Hours")
        ec_hbar(bo_top["site_id"].tolist(),
                [round(v) for v in bo_top["total_hours"].tolist()],
                title="Generator Run Hours (proxy for blackout duration)",
                key=f"bo_top15_{key_prefix}")
        _chart_guide(
            "Total generator hours per site, <b>top 15</b> ranked highest to lowest.\nHigher = more blackout impact at that location.",
            [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM per site, all dates"}],
            [("green", "✅ Short bars = Sites with minimal blackout impact"),
             ("amber", "⚠️ Long bars = Heavy generator usage, high fuel consumption"),
             ("red", "🔴 Very long bars = Most affected sites, prioritize maintenance + fuel delivery")],
            "Shows which <b>stores had the most blackouts</b> (measured by how long generators ran). Like ranking <b>employees by overtime hours</b> — the longest bars worked the hardest. These sites <r>consume the most fuel</r> and their generators need <a>priority maintenance</a> to avoid breakdowns."
        )

    # Anomaly Detection
    try:
        anomaly_df = get_consumption_anomalies()
        if not anomaly_df.empty:
            if sector_filter:
                anomaly_df = anomaly_df[anomaly_df["sector_id"] == sector_filter]
            if not anomaly_df.empty:
                st.markdown("#### 🚩 Consumption Anomalies")
                st.warning(f"**{len(anomaly_df)} anomalies detected** — sites consuming 30%+ above their 7-day average")
                ad = anomaly_df[["site_id", "date", "total_daily_used", "avg_7d", "pct_above_avg", "possible_cause"]].head(20).copy()
                ad["pct_above_avg"] = ad["pct_above_avg"].apply(lambda x: f"+{x:.0f}%")
                ad["total_daily_used"] = ad["total_daily_used"].apply(lambda x: f"{x:,.0f}")
                ad["avg_7d"] = ad["avg_7d"].apply(lambda x: f"{x:,.0f}")
                ad.columns = ["Site", "Date", "Actual (L)", "7d Avg (L)", "Above Avg", "Possible Cause"]
                render_smart_table(ad, title="Consumption Anomalies")
    except Exception:
        pass


def _site_extra_charts(sid, tk, period="Daily"):
    """Comprehensive site-level: KPI card, fleet, 11 trend charts, anomalies."""
    sr = econ[econ["site_id"] == sid].iloc[0] if sid in econ["site_id"].values else None

    with get_db() as conn:
        _dsql_e, _dp_e = _date_sql("do.date")
        _dsql_d, _dp_d = _date_sql("date")

        # Generator fleet specs (not date-filtered)
        gens_df = pd.read_sql_query("""
            SELECT g.generator_id, g.model_name, g.power_kva, g.consumption_per_hour, g.fuel_type, g.supplier
            FROM generators g WHERE g.site_id = ? AND g.is_active = 1
        """, conn, params=[sid])

        # Daily ops per generator
        ops_df = pd.read_sql_query(f"""
            SELECT do.date, do.generator_id, g.model_name, do.gen_run_hr, do.daily_used_liters
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            WHERE do.site_id = ?{_dsql_e} ORDER BY do.date
        """, conn, params=[sid] + _dp_e)

        # Site summary
        summary_raw = pd.read_sql_query(f"""
            SELECT date, total_daily_used, spare_tank_balance, blackout_hr,
                   total_gen_run_hr, days_of_buffer, num_generators_active
            FROM daily_site_summary WHERE site_id = ?{_dsql_d} ORDER BY date
        """, conn, params=[sid] + _dp_d)

        # Sales for this site
        sales_raw = pd.read_sql_query(f"""
            SELECT date, SUM(sales_amt) as sales, SUM(margin) as margin
            FROM daily_sales WHERE site_id = ?{_dsql_d} GROUP BY date ORDER BY date
        """, conn, params=[sid] + _dp_d)

        # Fuel price for this site's supplier
        site_sector = conn.execute("SELECT sector_id FROM sites WHERE site_id = ?", (sid,)).fetchone()
        sector_id = site_sector[0] if site_sector else None
        price_raw = pd.DataFrame()
        if sector_id:
            price_raw = pd.read_sql_query(f"""
                SELECT date, AVG(price_per_liter) as price
                FROM fuel_purchases WHERE sector_id = ? AND price_per_liter IS NOT NULL{_dsql_d}
                GROUP BY date ORDER BY date
            """, conn, params=[sector_id] + _dp_d)

    if summary_raw.empty:
        return

    # ── Aggregate by period ───────────────────────────────────────
    def _add_period_col(df):
        if df.empty or "date" not in df.columns:
            return df
        df = df.copy()
        df["_date"] = pd.to_datetime(df["date"])
        if period == "Weekly":
            df["_period"] = df["_date"].dt.to_period("W").apply(lambda x: str(x.start_time.date()))
        elif period == "Monthly":
            df["_period"] = df["_date"].dt.to_period("M").apply(lambda x: str(x.start_time.date()))
        else:
            df["_period"] = df["date"]
        return df

    def _agg_summary(df):
        if df.empty:
            return df
        df = _add_period_col(df)
        return df.groupby("_period").agg(
            total_daily_used=("total_daily_used", "mean"),
            spare_tank_balance=("spare_tank_balance", "last"),
            blackout_hr=("blackout_hr", "mean"),
            total_gen_run_hr=("total_gen_run_hr", "mean"),
            days_of_buffer=("days_of_buffer", "last"),
        ).reset_index().rename(columns={"_period": "date"}).sort_values("date")

    def _agg_sales(df):
        if df.empty:
            return df
        df = _add_period_col(df)
        return df.groupby("_period").agg(
            sales=("sales", "sum"),
            margin=("margin", "sum"),
        ).reset_index().rename(columns={"_period": "date"}).sort_values("date")

    def _agg_price(df):
        if df.empty:
            return df
        df = _add_period_col(df)
        return df.groupby("_period").agg(
            price=("price", "mean"),
        ).reset_index().rename(columns={"_period": "date"}).sort_values("date")

    def _agg_ops(df):
        if df.empty:
            return df
        df = _add_period_col(df)
        return df.groupby(["_period", "model_name"]).agg(
            gen_run_hr=("gen_run_hr", "mean"),
            daily_used_liters=("daily_used_liters", "mean"),
        ).reset_index().rename(columns={"_period": "date"}).sort_values("date")

    summary_df = _agg_summary(summary_raw) if period != "Daily" else summary_raw.copy()
    sales_df = _agg_sales(sales_raw) if period != "Daily" else sales_raw.copy()
    price_df = _agg_price(price_raw) if period != "Daily" else price_raw.copy()
    ops_agg = _agg_ops(ops_df) if period != "Daily" else ops_df.copy()

    dates_all = summary_df["date"].tolist()
    per_label = period

    # ── 1. Site KPI Summary Card ──────────────────────────────────
    buf = sr["latest_buffer_days"] if sr is not None and pd.notna(sr.get("latest_buffer_days")) else None
    tank_val = sr["diesel_available"] if sr is not None and pd.notna(sr.get("diesel_available")) else 0
    burn_val = sr["avg_daily_liters"] if sr is not None and pd.notna(sr.get("avg_daily_liters")) else 0
    cost_val = sr["energy_cost"] if sr is not None and pd.notna(sr.get("energy_cost")) else 0
    sales_val = sr["total_sales"] if sr is not None and pd.notna(sr.get("total_sales")) else 0
    epct_val = sr["energy_pct"] if sr is not None and pd.notna(sr.get("energy_pct")) else 0
    n_gens = len(gens_df)
    total_kva = gens_df["power_kva"].sum() if not gens_df.empty else 0
    rec = sr["recommendation"] if sr is not None else "—"
    rec_color = {"OPEN": "#16a34a", "MONITOR": "#d97706", "REDUCE": "#ea580c", "CLOSE": "#dc2626"}.get(str(rec), "#6b7280")
    buf_color = "#dc2626" if buf and buf < 3 else "#d97706" if buf and buf < 7 else "#16a34a" if buf else "#6b7280"
    buf_txt = "CRITICAL" if buf and buf < 3 else "WARNING" if buf and buf < 7 else "SAFE" if buf else "NO DATA"

    _cs = "border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px;text-align:center"
    st.markdown(f"""
    <div style="background:#0f172a;color:white;border-radius:14px;padding:18px;margin-top:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div>
                <span style="font-size:18px;font-weight:800">📍 {sid}</span>
                <span style="opacity:0.5;margin-left:10px;font-size:12px">{n_gens} generators | {total_kva:,.0f} KVA | {len(dates_all)} days of data</span>
            </div>
            <div style="display:flex;gap:8px">
                <div style="background:{buf_color};padding:5px 14px;border-radius:16px;font-weight:600;font-size:12px">{buf_txt}: {f'{buf:.1f}' if buf else '—'}d</div>
                <div style="background:{rec_color};padding:5px 14px;border-radius:16px;font-weight:600;font-size:12px">{rec}</div>
            </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
            <div style="flex:1;min-width:100px;background:{buf_color};{_cs}">
                <div style="font-size:24px;font-weight:700">{f'{buf:.1f}' if buf else '—'}</div>
                <div style="font-size:10px;font-weight:600">Buffer Days</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;{_cs}">
                <div style="font-size:24px;font-weight:700">{tank_val:,.0f}</div>
                <div style="font-size:10px;font-weight:600">Tank (L)</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;{_cs}">
                <div style="font-size:24px;font-weight:700">{burn_val:,.0f}</div>
                <div style="font-size:10px;font-weight:600">Burn/Day (L)</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;{_cs}">
                <div style="font-size:24px;font-weight:700">{cost_val/1e6:,.2f}M</div>
                <div style="font-size:10px;font-weight:600">Diesel Cost</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;{_cs}">
                <div style="font-size:24px;font-weight:700">{sales_val/1e6:,.1f}M</div>
                <div style="font-size:10px;font-weight:600">Sales</div>
            </div>
            <div style="flex:1;min-width:100px;background:#0f766e;{_cs}">
                <div style="font-size:24px;font-weight:700">{epct_val:.2f}%</div>
                <div style="font-size:10px;font-weight:600">Diesel %</div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── AI Site Insight ─────────────────────────────────────────
    _site_ai_data = {
        "site_id": sid, "buffer": buf, "tank": tank_val, "burn_per_day": burn_val,
        "diesel_cost": f"{cost_val/1e6:,.2f}M", "sales": f"{sales_val/1e6:,.1f}M",
        "diesel_pct": f"{epct_val:.2f}%", "generators": n_gens, "total_kva": total_kva,
        "recommendation": rec,
    }
    if st.button(f"🧠 Get AI Analysis — {sid}", key=f"btn_ai_{tk}"):
        _site_ai = site_insight(_site_ai_data, force_refresh=True)
        render_insight_box(_site_ai, f"🧠 {sid} Analysis")

    # ── 2. Generator Fleet Table ──────────────────────────────────
    if not gens_df.empty:
        st.markdown(f"### 🔧 Generator Fleet — {sid}")
        fleet = gens_df[["model_name", "power_kva", "consumption_per_hour", "fuel_type", "supplier"]].copy()
        fleet.columns = ["Generator", "KVA", "Rated L/hr", "Fuel Type", "Supplier"]
        if not ops_df.empty:
            latest_date = ops_df["date"].max()
            latest_ops = ops_df[ops_df["date"] == latest_date][["generator_id", "gen_run_hr", "daily_used_liters"]].copy()
            gen_map = dict(zip(gens_df["generator_id"], gens_df["model_name"]))
            latest_ops["Generator"] = latest_ops["generator_id"].map(gen_map)
            latest_ops = latest_ops[["Generator", "gen_run_hr", "daily_used_liters"]]
            latest_ops.columns = ["Generator", "Run Hr (Latest)", "Used L (Latest)"]
            fleet = fleet.merge(latest_ops, on="Generator", how="left")
        render_smart_table(fleet, title=f"Generator Fleet — {sid}")

    if len(dates_all) < 2:
        st.info("Need at least 2 data points for trend charts.")
        return

    st.markdown(f"### 📈 All Trends — {sid} ({per_label} | {len(dates_all)} periods)")

    # Helper for safe values
    def _sv(series):
        return [round(v, 1) if pd.notna(v) else 0 for v in series]

    used = _sv(summary_df["total_daily_used"])
    tank_s = _sv(summary_df["spare_tank_balance"])
    hours = _sv(summary_df["total_gen_run_hr"])
    buffer_s = _sv(summary_df["days_of_buffer"])
    bo_s = _sv(summary_df["blackout_hr"])

    # ── 3. Buffer Days Trend ──────────────────────────────────────
    # ── 4. Efficiency Trend (L/Hr) ────────────────────────────────
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        ec_line(dates_all, [{"name": "Buffer Days", "data": buffer_s, "color": "#3b82f6"}],
                title="Buffer Days Trend", height=350,
                mark_lines=[{"value": 7, "label": "Safe (7d)", "color": "#16a34a"},
                            {"value": 3, "label": "Critical (3d)", "color": "#dc2626"}],
                key=f"st_buf_{tk}")
        _chart_guide(
            formula="<c>Buffer Days</c> = <c>Spare Tank Balance</c> ÷ <c>Estimated Daily Consumption</c>",
            sources=[
                {"data": "Spare Tank Balance", "file": "Blackout Hr Excel", "col": "Spare Tank Balance", "method": "Last value per period for this site"},
                {"data": "Daily Consumption", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Average liters per day"},
            ],
            reading=[
                ("green", "Above 7 days — safe fuel reserve"),
                ("amber", "3-7 days — schedule delivery soon"),
                ("red", "Below 3 days — order fuel NOW"),
                ("blue", "Falling trend — fuel depleting faster than refills"),
            ],
            explain="Like your <b>phone battery</b> — shows <b>days until fuel runs out</b>. <g>Green line (7d)</g> = comfortably charged. <r>Red line (3d)</r> = plug in NOW or it dies.",
        )
    with r1c2:
        eff = [round(u / h, 1) if h > 0 else 0 for u, h in zip(used, hours)]
        ec_line(dates_all, [{"name": "L/Hr", "data": eff, "color": "#8b5cf6"}],
                title="Efficiency — Liters per Gen Hour", height=350,
                mark_lines=[{"value": 1.5, "label": "Waste threshold", "color": "#dc2626"}],
                key=f"st_eff_{tk}")
        _chart_guide(
            formula="<c>Efficiency (L/Hr)</c> = <c>Daily Used</c> ÷ <c>Gen Run Hr</c>",
            sources=[
                {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Sum of liters used per day"},
                {"data": "Gen Run Hr", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "Sum of generator hours per day"},
            ],
            reading=[
                ("green", "Flat and stable — generator running efficiently"),
                ("amber", "Gradual rise — monitor for degradation"),
                ("red", "Spike up — possible fuel theft or generator fault"),
                ("blue", "Red waste-threshold line at 1.5 L/Hr"),
            ],
            explain="Like a car's <b>km/liter</b> — flat is healthy, <r>spike up is waste</r>. If it jumps from 18 to 32 L/hr, something is wrong — check the generator or fuel logs.",
        )

    # ── 5. Gen Hours vs Fuel (dual axis) ──────────────────────────
    # ── 6. Fuel vs Tank Balance ───────────────────────────────────
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        dual_axis_chart(dates_all, [round(v) for v in hours], [round(v) for v in used],
                        title="Gen Hours vs Fuel Consumption",
                        bar_name="Gen Hours (hr)", line_name="Fuel Used (L)",
                        bar_color="#3b82f6", line_color="#ef4444", height=350, key=f"st_hvf_{tk}")
        _chart_guide(
            formula="<c>Blue bars</c> = <c>Gen Run Hr</c> · <c>Red line</c> = <c>Daily Used (L)</c>",
            sources=[
                {"data": "Gen Run Hr", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "Sum of hours per day for this site"},
                {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Sum of liters per day for this site"},
            ],
            reading=[
                ("green", "Bars and line move together — normal correlation"),
                ("red", "Red line rises but bars stay flat — fuel waste or theft"),
                ("amber", "Bars rise but red stays flat — generator running on low fuel"),
            ],
            explain="Like <b>pedalling a bike</b> — the harder you pedal (hours), the further you go (fuel used). If fuel goes up but hours don't, someone is <r>draining the tank</r>.",
        )
    with r2c2:
        dual_axis_chart(dates_all, [round(v) for v in used], [round(v) for v in tank_s],
                        title="Daily Used vs Tank Balance",
                        bar_name="Daily Used (L)", line_name="Tank Balance (L)",
                        bar_color="#ef4444", line_color="#3b82f6", height=350, key=f"st_fvt_{tk}")
        _chart_guide(
            formula="<c>Red bars</c> = <c>Daily Used (L)</c> · <c>Blue line</c> = <c>Spare Tank Balance (L)</c>",
            sources=[
                {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Sum of liters consumed per day"},
                {"data": "Tank Balance", "file": "Blackout Hr Excel", "col": "Spare Tank Balance", "method": "End-of-day tank reading"},
            ],
            reading=[
                ("green", "Blue line stable or rising — tank being refilled on time"),
                ("amber", "Blue line slowly dropping — fuel consumed faster than refilled"),
                ("red", "Blue line plummeting — tank emptying, delivery urgently needed"),
                ("blue", "Sudden jump up in blue line — fuel refill was received"),
            ],
            explain="Like a <b>bathtub with the tap on</b> — red bars are water draining out, blue line is the water level. If the line keeps dropping, <r>turn on the tap</r> (order fuel).",
        )

    # ── 7. Cumulative Fuel Consumed ───────────────────────────────
    # ── 8. Daily Diesel Cost ──────────────────────────────────────
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        cumul = []
        total = 0
        for v in used:
            total += v
            cumul.append(round(total))
        ec_line(dates_all, [{"name": "Cumulative Fuel (L)", "data": cumul, "color": "#f59e0b"}],
                title="Cumulative Fuel Consumed", height=350, key=f"st_cumul_{tk}")
        _chart_guide(
            formula="<c>Cumulative Fuel</c> = running sum of <c>Daily Used</c> from first day to each date",
            sources=[
                {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Accumulated day by day for this site"},
            ],
            reading=[
                ("green", "Gentle slope — moderate, steady consumption"),
                ("amber", "Steep slope — high consumption rate"),
                ("red", "Near-vertical — burning through fuel extremely fast"),
                ("blue", "Flat section — no usage (site closed or no blackout)"),
            ],
            explain="Like a <b>car odometer</b> — it only goes up. <a>Steeper slope</a> = driving faster (burning more fuel). <b>Flat section</b> = car was parked (site not using fuel).",
        )
    with r3c2:
        # Get avg price for this site
        site_price = 0
        if sr is not None and pd.notna(sr.get("diesel_price")):
            site_price = sr["diesel_price"]
        elif not price_df.empty:
            site_price = price_df["price"].mean()
        daily_cost = [round(v * _price_on_date(sector_id or "", d)) for v, d in zip(used, dates_all)]
        ec_bar(dates_all, daily_cost, title="Daily Diesel Cost (MMK)", color="#ef4444", height=350, key=f"st_dcost_{tk}")
        _chart_guide(
            formula="<c>Daily Cost (MMK)</c> = <c>Daily Used (L)</c> x <c>Price per Liter</c> on that date",
            sources=[
                {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Liters consumed per day"},
                {"data": "Price per Liter", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "Latest price active on each date"},
            ],
            reading=[
                ("green", "Low or stable bars — fuel cost under control"),
                ("amber", "Rising bars — cost increasing (check if volume or price)"),
                ("red", "Large spike — either heavy usage day or price jump"),
            ],
            explain="Like your <b>daily coffee spend</b> — cost = cups bought x price per cup. If your bill spikes, check: did you drink more, or did the price go up? Same logic here.",
        )

    # ── 9. Blackout vs Fuel (dual axis) ───────────────────────────
    # ── 10. Blackout Hours severity bar ───────────────────────────
    has_bo = any(v > 0 for v in bo_s)
    if has_bo:
        r4c1, r4c2 = st.columns(2)
        with r4c1:
            dual_axis_chart(dates_all, bo_s, [round(v) for v in used],
                            title="Blackout Hours vs Fuel Used",
                            bar_name="Blackout Hr", line_name="Fuel (L)",
                            bar_color="#d97706", line_color="#ef4444", height=350, key=f"st_bovf_{tk}")
            _chart_guide(
                formula="<c>Amber bars</c> = <c>Blackout Hr</c> · <c>Red line</c> = <c>Daily Used (L)</c>",
                sources=[
                    {"data": "Blackout Hr", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "Hours of power outage per day"},
                    {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Liters consumed per day"},
                ],
                reading=[
                    ("green", "Bars and line move together — fuel usage matches blackout hours"),
                    ("red", "Red line rises without amber bars — fuel waste or theft"),
                    ("amber", "Amber bars rise without red line — generator did not run during outage"),
                ],
                explain="Like <b>rain and umbrella usage</b> — more rain (blackout) should mean more umbrellas (fuel). If fuel goes up on sunny days, <r>someone is wasting fuel</r>.",
            )
        with r4c2:
            ec_bar(dates_all, bo_s, title="Daily Blackout Hours (Red >8, Amber 4-8, Green <4)",
                   color="#d97706", height=350, key=f"st_bo_{tk}")
            _chart_guide(
                formula="<c>Blackout Hours</c> = hours without grid electricity each day",
                sources=[
                    {"data": "Blackout Hr", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "Direct reading per day for this site"},
                ],
                reading=[
                    ("green", "Below 4 hours — manageable outage"),
                    ("amber", "4-8 hours — significant outage"),
                    ("red", "Above 8 hours — severe day, heavy generator dependency"),
                    ("blue", "Improving trend — grid getting more reliable"),
                ],
                explain="Like a <b>weather report for power</b> — tells you how many hours the lights were off. <r>8+ hours</r> = a very bad day. Watch the trend: improving = grid getting better.",
            )

    # ── 11. Diesel % of Sales Daily ───────────────────────────────
    if not sales_df.empty and not price_df.empty:
        merged_dates = sorted(set(dates_all) & set(sales_df["date"].tolist()))
        if len(merged_dates) >= 2:
            sv_raw = [round(sales_df[sales_df["date"]==d]["sales"].sum()) if not sales_df[sales_df["date"]==d].empty else 0 for d in merged_dates]
            dv_raw = [round(summary_df[summary_df["date"]==d]["total_daily_used"].sum() * _price_on_date(sector_id or "", d)) if not summary_df[summary_df["date"]==d].empty else 0 for d in merged_dates]
            dpv = [round(d/s*100, 2) if s > 0 else 0 for s, d in zip(sv_raw, dv_raw)]
            mv = [round(sales_df[sales_df["date"]==d]["margin"].sum()) if not sales_df[sales_df["date"]==d].empty else 0 for d in merged_dates]
            mpv = [round(m/s*100, 1) if s > 0 else 0 for s, m in zip(sv_raw, mv)]
            sv = [round(v/1e6, 1) for v in sv_raw]
            dv = [round(v/1e6, 2) for v in dv_raw]

            r5c1, r5c2 = st.columns(2)
            with r5c1:
                dual_axis_chart(merged_dates, sv, dv,
                                title="Sales vs Diesel Cost (Millions)",
                                bar_name="Sales (M)", line_name="Diesel (M)",
                                bar_color="#3b82f6", line_color="#ef4444", height=350, key=f"st_svd_{tk}")
                _chart_guide(
                    formula="<c>Blue bars</c> = <c>Sales (M)</c> · <c>Red line</c> = <c>Daily Used</c> x <c>Price/L</c> ÷ 1M",
                    sources=[
                        {"data": "Sales", "file": "Sales Excel", "col": "SALES_AMT", "method": "Sum of daily sales for this site"},
                        {"data": "Diesel Cost", "file": "Blackout Hr Excel + Fuel Price Excel", "col": "Daily Used x Price per Liter", "method": "Liters x price, converted to millions"},
                    ],
                    reading=[
                        ("green", "Wide gap between blue and red — healthy profit after fuel"),
                        ("amber", "Gap narrowing — fuel cost eating into profit"),
                        ("red", "Red line near or above blue — fuel cost exceeds revenue"),
                    ],
                    explain="Like comparing your <b>salary vs rent</b> — blue = what you earn, red = what fuel costs. The bigger the gap, the healthier the site. <r>Gap closing = trouble</r>.",
                )
            with r5c2:
                ec_line(merged_dates, [
                    {"name": "Diesel %", "data": dpv, "color": "#ef4444"},
                    {"name": "Margin %", "data": mpv, "color": "#22c55e"},
                ], title="Diesel % vs Margin % — Daily", height=350,
                   mark_lines=[{"value": 3, "label": "Red threshold (3%)", "color": "#dc2626"}],
                   key=f"st_dpct_{tk}")
                _chart_guide(
                    formula="<c>Diesel %</c> = (<c>Daily Used</c> x <c>Price/L</c>) ÷ <c>Sales</c> x 100 · <c>Margin %</c> = <c>Margin</c> ÷ <c>Sales</c> x 100",
                    sources=[
                        {"data": "Sales", "file": "Sales Excel", "col": "SALES_AMT", "method": "Daily total for this site"},
                        {"data": "Margin", "file": "Sales Excel", "col": "MARGIN", "method": "Daily total for this site"},
                        {"data": "Fuel Cost", "file": "Blackout Hr + Fuel Price Excel", "col": "Daily Used x Price per Liter", "method": "Liters x price per day"},
                    ],
                    reading=[
                        ("green", "Red line well below green — fuel cost is small vs profit"),
                        ("amber", "Red line approaching green — fuel cost threatening margins"),
                        ("red", "Red crosses above green — fuel cost exceeds profit margin, site losing money"),
                        ("orange", "Red above 3% threshold — consider reducing generator hours"),
                    ],
                    explain="Two runners on a track: <g>green</g> = your profit margin, <r>red</r> = your fuel cost. Green should always be ahead. If red overtakes green, <r>you are losing money on fuel</r>.",
                )

    # ── 12. Fuel Price Trend ──────────────────────────────────────
    if not price_df.empty and len(price_df) >= 2:
        st.markdown(f"#### ⛽ Fuel Price Trend — {sector_id or 'sector'}")
        ec_line(price_df["date"].tolist(),
                [{"name": "Price/L (MMK)", "data": _sv(price_df["price"]), "color": "#f59e0b"}],
                title="Fuel Price per Liter Over Time", height=300, key=f"st_fprice_{tk}")
        _chart_guide(
            formula="<c>Price/L (MMK)</c> = average <c>Price per Liter</c> from fuel purchases for this sector",
            sources=[
                {"data": "Price per Liter", "file": "Daily Fuel Price Excel", "col": "Price per Liter", "method": "Average price per day for this sector"},
            ],
            reading=[
                ("green", "Flat or falling — stable or improving fuel costs"),
                ("amber", "Gradual rise — budget pressure building"),
                ("red", "Sudden jump — new purchase at higher market price"),
            ],
            explain="Like watching <b>petrol station prices</b> on your commute. Flat = predictable budget. <r>Sudden jump</r> = market moved, your fuel bill just went up.",
        )

    # ── 13. Gen Run Hours (per generator multi-line) ────────────
    if not ops_agg.empty and "model_name" in ops_agg.columns and len(ops_agg["date"].unique()) >= 2:
        st.markdown(f"#### 🔧 Generator Run Hours ({per_label})")
        models = sorted(ops_agg["model_name"].dropna().unique())
        dates_ops = sorted(ops_agg["date"].unique())
        if models and dates_ops:
            lines = []
            for i, m in enumerate(models):
                mdata = []
                for d in dates_ops:
                    sub = ops_agg[(ops_agg["date"]==d)&(ops_agg["model_name"]==m)]
                    mdata.append(round(sub["gen_run_hr"].sum(), 1) if not sub.empty else 0)
                lines.append({"name": m, "data": mdata, "color": PALETTE[i % len(PALETTE)]})
            ec_line(dates_ops, lines, title=f"Gen Run Hours ({per_label}, by Generator)", height=350, key=f"st_genhr_{tk}")
            _chart_guide(
                formula=f"Each line = <c>Gen Run Hr</c> for one generator model at this site ({per_label})",
                sources=[
                    {"data": "Gen Run Hr", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "Hours per generator model per day"},
                ],
                reading=[
                    ("green", "Lines balanced — load shared evenly across generators"),
                    ("amber", "One line much higher — uneven load distribution"),
                    ("red", "A line drops to zero — generator may need maintenance"),
                    ("blue", "All lines rising together — increasing power demand"),
                ],
                explain=f"Like <b>runners in a relay</b> — each line is one generator. They should share the load. If one runs all the time and another stops, <r>check if it broke down</r>.",
            )

    # ── 14. Anomaly Detection (always daily) ─────────────────────
    if len(summary_raw) >= 7:
        st.markdown(f"#### 🚩 Anomaly Detection — {sid} (Daily)")
        anom_df = summary_raw.copy()
        anom_df["avg_7d"] = anom_df["total_daily_used"].rolling(7, min_periods=3).mean()
        anom_df["pct_above"] = np.where(anom_df["avg_7d"] > 0,
                                         (anom_df["total_daily_used"] - anom_df["avg_7d"]) / anom_df["avg_7d"] * 100, 0)
        anomalies = anom_df[anom_df["pct_above"] > 30]
        if not anomalies.empty:
            st.warning(f"**{len(anomalies)} days** where fuel used was 30%+ above 7-day average")
            # Chart: actual vs 7d avg with anomaly markers
            anom_dates = anom_df["date"].tolist()
            ec_line(anom_dates, [
                {"name": "Actual (L)", "data": _sv(anom_df["total_daily_used"]), "color": "#ef4444"},
                {"name": "7-Day Avg", "data": _sv(anom_df["avg_7d"]), "color": "#3b82f6"},
            ], title="Fuel Used vs 7-Day Moving Average", height=350, key=f"st_anom_{tk}")
            _chart_guide(
                formula="<r>Red line</r> = <c>Daily Used (L)</c> actual · <b>Blue line</b> = 7-day rolling average of <c>Daily Used</c>. Flagged when red > 30% above blue.",
                sources=[
                    {"data": "Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "Actual liters per day"},
                    {"data": "7-Day Avg", "file": "Calculated", "col": "Daily Used (rolling 7-day mean)", "method": "Rolling average with min 3 days"},
                ],
                reading=[
                    ("green", "Red stays near blue — consumption is normal and predictable"),
                    ("amber", "Red occasionally above blue — minor variation, likely OK"),
                    ("red", "Red spikes 30%+ above blue — anomaly flagged, investigate"),
                    ("blue", "Blue line = what this site normally uses"),
                ],
                explain="<b>Blue line</b> = what this site <b>normally</b> uses. <r>Red</r> = what it <b>actually</b> used. Big gap = something unusual — could be unexpected blackout, fuel theft, or data entry error.",
            )
            # Table of anomalies
            ad = anomalies[["date", "total_daily_used", "avg_7d", "pct_above"]].copy()
            ad["total_daily_used"] = ad["total_daily_used"].apply(lambda x: f"{x:,.0f}")
            ad["avg_7d"] = ad["avg_7d"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
            ad["pct_above"] = ad["pct_above"].apply(lambda x: f"+{x:.0f}%")
            ad.columns = ["Date", "Actual (L)", "7d Avg (L)", "Above Avg"]
            render_smart_table(ad, title="Anomaly Days (30%+ above average)")
        else:
            st.success("No anomalies — consumption within normal range for all days.")

    # ── 15. Site vs Sector Average Comparison ─────────────────────
    if sector_id:
        with get_db() as conn:
            _dsql_sc, _dp_sc = _date_sql("dss.date")
            sec_avg_raw = pd.read_sql_query(f"""
                SELECT dss.date, AVG(dss.total_daily_used) as sec_avg_used, AVG(dss.total_gen_run_hr) as sec_avg_hr,
                       AVG(dss.days_of_buffer) as sec_avg_buf
                FROM daily_site_summary dss
                JOIN sites s ON dss.site_id = s.site_id
                WHERE s.sector_id = ?{_dsql_sc}
                GROUP BY dss.date ORDER BY dss.date
            """, conn, params=[sector_id] + _dp_sc)
        if not sec_avg_raw.empty:
            # Aggregate sector avg by period
            if period != "Daily":
                sa = _add_period_col(sec_avg_raw)
                sec_avg = sa.groupby("_period").agg(
                    sec_avg_used=("sec_avg_used", "mean"),
                    sec_avg_buf=("sec_avg_buf", "mean"),
                ).reset_index().rename(columns={"_period": "date"}).sort_values("date")
            else:
                sec_avg = sec_avg_raw
            if len(sec_avg) >= 2:
                merged = sorted(set(dates_all) & set(sec_avg["date"].tolist()))
                if len(merged) >= 2:
                    st.markdown(f"#### 📊 {sid} vs {sector_id} Sector Average ({per_label})")
                    site_vals = [round(summary_df[summary_df["date"]==d]["total_daily_used"].sum()) if not summary_df[summary_df["date"]==d].empty else 0 for d in merged]
                    sec_vals = [round(sec_avg[sec_avg["date"]==d]["sec_avg_used"].mean()) if not sec_avg[sec_avg["date"]==d].empty else 0 for d in merged]
                    r6c1, r6c2 = st.columns(2)
                    with r6c1:
                        ec_line(merged, [
                            {"name": f"{sid}", "data": site_vals, "color": "#ef4444"},
                            {"name": f"{sector_id} Avg", "data": sec_vals, "color": "#3b82f6"},
                        ], title=f"Fuel Used — Site vs Sector Avg ({per_label})", height=350, key=f"st_comp_fuel_{tk}")
                        _chart_guide(
                            formula=f"<r>Red line</r> = this site's <c>Daily Used</c> · <b>Blue line</b> = average <c>Daily Used</c> of all {sector_id} sites ({per_label})",
                            sources=[
                                {"data": "Site Daily Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": f"This site's daily consumption"},
                                {"data": "Sector Average", "file": "Blackout Hr Excel", "col": "Daily Used", "method": f"Average of all {sector_id} sites per day"},
                            ],
                            reading=[
                                ("green", "Red near or below blue — this site uses average or less fuel"),
                                ("amber", "Red occasionally above blue — slightly higher than peers"),
                                ("red", "Red consistently above blue — this site is a heavy consumer, investigate"),
                            ],
                            explain=f"Like comparing your <b>electricity bill to your neighbours</b>. <r>Red</r> = your usage, <b>blue</b> = the street average. Consistently above = you are the outlier.",
                        )
                    with r6c2:
                        site_buf = [round(summary_df[summary_df["date"]==d]["days_of_buffer"].mean(), 1) if not summary_df[summary_df["date"]==d].empty else 0 for d in merged]
                        sec_buf = [round(sec_avg[sec_avg["date"]==d]["sec_avg_buf"].mean(), 1) if not sec_avg[sec_avg["date"]==d].empty else 0 for d in merged]
                        ec_line(merged, [
                            {"name": f"{sid}", "data": site_buf, "color": "#ef4444"},
                            {"name": f"{sector_id} Avg", "data": sec_buf, "color": "#3b82f6"},
                        ], title=f"Buffer — Site vs Sector Avg ({per_label})", height=350, key=f"st_comp_buf_{tk}")
                        _chart_guide(
                            formula=f"<r>Red line</r> = this site's <c>Buffer Days</c> · <b>Blue line</b> = average buffer of all {sector_id} sites ({per_label})",
                            sources=[
                                {"data": "Site Buffer", "file": "Blackout Hr Excel", "col": "Spare Tank Balance / burn", "method": "This site's buffer days"},
                                {"data": "Sector Buffer", "file": "Blackout Hr Excel", "col": "Spare Tank Balance / burn", "method": f"Average buffer of all {sector_id} sites"},
                            ],
                            reading=[
                                ("green", "Red near or above blue — this site has average or better fuel reserves"),
                                ("amber", "Red occasionally below blue — slightly riskier than peers"),
                                ("red", "Red consistently below blue — this site needs priority fuel delivery"),
                            ],
                            explain=f"Like comparing <b>savings accounts</b> — <r>red</r> = your rainy-day fund, <b>blue</b> = your peers' average. If yours is always lower, <r>you run out first in a crisis</r>.",
                        )


# ═══════════════════════════════════════════════════════════════════════════
# DATA & ANALYTICS — NEW FEATURES
# ═══════════════════════════════════════════════════════════════════════════

def _week_over_week(key_prefix="grp"):
    """Week-over-Week comparison — 6 metric cards with ▲▼ arrows."""
    with get_db() as conn:
        _dsql, _dp = _date_sql("date")
        max_d = conn.execute(f"SELECT MAX(date) FROM daily_site_summary WHERE 1=1{_dsql}", _dp).fetchone()[0]
        if not max_d:
            return
    from datetime import datetime, timedelta
    max_dt = datetime.strptime(max_d, "%Y-%m-%d").date()
    tw_from = (max_dt - timedelta(days=6)).strftime("%Y-%m-%d")
    tw_to = max_d
    lw_from = (max_dt - timedelta(days=13)).strftime("%Y-%m-%d")
    lw_to = (max_dt - timedelta(days=7)).strftime("%Y-%m-%d")

    with get_db() as conn:
        def _week(f, t):
            r = conn.execute("""
                SELECT SUM(total_daily_used) as fuel, SUM(spare_tank_balance) as tank,
                       COUNT(DISTINCT date) as days, SUM(total_daily_used)*1.0/MAX(COUNT(DISTINCT date),1) as burn,
                       SUM(CASE WHEN days_of_buffer < 3 THEN 1 ELSE 0 END) as crit
                FROM daily_site_summary WHERE date BETWEEN ? AND ?
            """, (f, t)).fetchone()
            bo = conn.execute("SELECT AVG(blackout_hr) FROM daily_operations WHERE date BETWEEN ? AND ? AND blackout_hr IS NOT NULL", (f, t)).fetchone()
            return {"fuel": r[0] or 0, "tank": r[1] or 0, "days": r[2] or 1, "burn": r[3] or 0,
                    "crit": r[4] or 0, "bo": round(bo[0], 1) if bo and bo[0] else 0}
        tw = _week(tw_from, tw_to)
        lw = _week(lw_from, lw_to)

        # Diesel cost
        tw_cost = 0; lw_cost = 0
        for row in conn.execute("SELECT date, SUM(total_daily_used) as liters FROM daily_site_summary WHERE date BETWEEN ? AND ? GROUP BY date", (tw_from, tw_to)):
            tw_cost += (row[1] or 0) * _price_on_date("", row[0])
        for row in conn.execute("SELECT date, SUM(total_daily_used) as liters FROM daily_site_summary WHERE date BETWEEN ? AND ? GROUP BY date", (lw_from, lw_to)):
            lw_cost += (row[1] or 0) * _price_on_date("", row[0])

        # Buffer
        tw_buf = round(tw["tank"] / max(tw["burn"], 1), 1) if tw["burn"] > 0 else 0
        lw_buf = round(lw["tank"] / max(lw["burn"], 1), 1) if lw["burn"] > 0 else 0

    metrics = [
        ("Fuel Used (L)", tw["fuel"], lw["fuel"], "low", "num"),
        ("Diesel Cost", tw_cost, lw_cost, "low", "M"),
        ("Buffer Days", tw_buf, lw_buf, "high", "d"),
        ("Blackout Hr", tw["bo"], lw["bo"], "low", "num"),
        ("Critical Sites", tw["crit"], lw["crit"], "low", "num"),
        ("Daily Burn (L)", tw["burn"], lw["burn"], "low", "num"),
    ]

    cards = []
    for label, tw_v, lw_v, good, fmt in metrics:
        if lw_v == 0 and tw_v == 0:
            cards.append(f'<div style="flex:1;min-width:140px;background:#111827;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center"><div style="font-size:11px;color:#64748b">{label}</div><div style="font-size:16px;color:#475569">—</div></div>')
            continue
        pct = ((tw_v - lw_v) / max(lw_v, 1)) * 100
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else "→"
        if good == "low":
            color = "#ef4444" if pct > 5 else "#f59e0b" if pct > 0 else "#22c55e"
        else:
            color = "#22c55e" if pct > 5 else "#f59e0b" if pct > 0 else "#ef4444"
        if fmt == "M":
            tw_s = f"{tw_v/1e6:,.1f}M"; lw_s = f"{lw_v/1e6:,.1f}M"
        elif fmt == "d":
            tw_s = f"{tw_v:.1f}d"; lw_s = f"{lw_v:.1f}d"
        else:
            tw_s = f"{tw_v:,.0f}"; lw_s = f"{lw_v:,.0f}"
        cards.append(f'''<div style="flex:1;min-width:140px;background:#111827;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:11px;color:#64748b;margin-bottom:4px">{label}</div>
            <div style="font-size:22px;font-weight:800;color:{color}">{arrow} {abs(pct):.0f}%</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px">{tw_s} <span style="color:#475569">vs</span> {lw_s}</div>
        </div>''')

    st.markdown(f"""
    <div style="background:#0f172a;border-radius:12px 12px 0 0;padding:10px 16px;font-weight:700;font-size:14px;color:white">
        📅 WEEK OVER WEEK <span style="font-size:11px;font-weight:400;opacity:0.5;margin-left:8px">{tw_from} → {tw_to} vs {lw_from} → {lw_to}</span>
    </div>
    <div style="display:flex;gap:8px;padding:12px;background:#0a0a0a;border:1px solid #1e293b;border-top:none;border-radius:0 0 12px 12px;flex-wrap:wrap">
        {''.join(cards)}
    </div>""", unsafe_allow_html=True)


def _day_of_week_patterns(key_prefix="grp"):
    """Bar charts showing average metrics by day of week."""
    with get_db() as conn:
        _dsql, _dp = _date_sql("dss.date")
        _dsql_do, _dp_do = _date_sql("do.date")
        dow_df = pd.read_sql_query(f"""
            SELECT CASE CAST(strftime('%w', dss.date) AS INTEGER)
                WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
                WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' END as day_name,
                CAST(strftime('%w', dss.date) AS INTEGER) as day_num,
                AVG(dss.total_daily_used) as avg_fuel,
                AVG(dss.total_gen_run_hr) as avg_hours
            FROM daily_site_summary dss WHERE 1=1{_dsql}
            GROUP BY day_num ORDER BY day_num
        """, conn, params=_dp)
        bo_dow = pd.read_sql_query(f"""
            SELECT CASE CAST(strftime('%w', do.date) AS INTEGER)
                WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
                WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' END as day_name,
                CAST(strftime('%w', do.date) AS INTEGER) as day_num,
                AVG(do.blackout_hr) as avg_bo
            FROM daily_operations do WHERE do.blackout_hr IS NOT NULL{_dsql_do}
            GROUP BY day_num ORDER BY day_num
        """, conn, params=_dp_do)

    if dow_df.empty:
        return

    # Reorder Mon-Sun
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_df = dow_df.set_index("day_name").reindex(order).reset_index()
    days = dow_df["day_name"].tolist()
    fuel = [round(v) if pd.notna(v) else 0 for v in dow_df["avg_fuel"]]
    hours = [round(v, 1) if pd.notna(v) else 0 for v in dow_df["avg_hours"]]

    bo_vals = [0] * 7
    if not bo_dow.empty:
        bo_dow = bo_dow.set_index("day_name").reindex(order).reset_index()
        bo_vals = [round(v, 1) if pd.notna(v) else 0 for v in bo_dow["avg_bo"]]

    with st.expander("📅 Day-of-Week Patterns", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            ec_bar(days, bo_vals, title="Avg Blackout Hours by Day", color="#d97706", height=300, key=f"dow_bo_{key_prefix}")
        with c2:
            ec_bar(days, fuel, title="Avg Fuel Used (L) by Day", color="#ef4444", height=300, key=f"dow_fuel_{key_prefix}")
        with c3:
            ec_bar(days, hours, title="Avg Gen Hours by Day", color="#3b82f6", height=300, key=f"dow_hrs_{key_prefix}")
        worst = days[bo_vals.index(max(bo_vals))] if max(bo_vals) > 0 else "—"
        best = days[bo_vals.index(min(bo_vals))] if min(bo_vals) < max(bo_vals) else "—"
        st.markdown(f"""<div style="background:#0d1117;border-left:4px solid #d97706;padding:10px 14px;border-radius:0 8px 8px 0;font-size:12px;color:#cbd5e1">
            💡 <b>{worst}</b> has the worst blackouts ({max(bo_vals):.1f} hr avg). <b>{best}</b> is the best ({min(bo_vals):.1f} hr avg).
            Weekend fuel use is typically lower — consider adjusting delivery schedules accordingly.
        </div>""", unsafe_allow_html=True)


def _generator_utilization(sector_filter=None, key_prefix="grp"):
    """Generator utilization rate — hours run vs available."""
    with get_db() as conn:
        _dsql, _dp = _date_sql("do.date")
        q = f"""
            SELECT do.site_id, do.generator_id, g.model_name,
                   SUM(do.gen_run_hr) as total_hrs,
                   COUNT(DISTINCT do.date) as days,
                   s.sector_id
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.gen_run_hr > 0{_dsql}
        """
        params = list(_dp)
        if sector_filter:
            q += " AND s.sector_id = ?"
            params.append(sector_filter)
        q += " GROUP BY do.site_id, do.generator_id ORDER BY total_hrs DESC LIMIT 20"
        util_df = pd.read_sql_query(q, conn, params=params)

    if util_df.empty:
        return

    util_df["available"] = util_df["days"] * 24
    util_df["util_pct"] = round(util_df["total_hrs"] / util_df["available"] * 100, 1)
    util_df["icon"] = util_df["util_pct"].apply(
        lambda x: "🔴" if x > 80 else "🟠" if x > 60 else "🟡" if x > 30 else "🟢" if x > 10 else "⚪")

    st.markdown("#### ⚡ Generator Utilization Rate")
    cats = [f"{r['site_id']} ({r['model_name'] or '?'})" for _, r in util_df.iterrows()]
    vals = util_df["util_pct"].tolist()
    colors = ["#ef4444" if v > 80 else "#f97316" if v > 60 else "#eab308" if v > 30 else "#22c55e" if v > 10 else "#6b7280" for v in vals]
    ec_hbar(cats, vals, title="Utilization % (Hours Run ÷ 24h × Days)", colors=colors, height=max(300, len(cats)*25), key=f"gen_util_{key_prefix}")
    _chart_guide(
        "Hours generator ran ÷ (24 hours × number of days) × 100 = <b>Utilization %</b>.\nExample: <b>186 hrs</b> ÷ <b>216 available hrs</b> (9 days × 24h) = <b>86%</b>.",
        [{"data": "Generator Hours", "file": "Blackout Hr Excel", "col": "Gen Run Hr", "method": "SUM per generator"},
         {"data": "Days", "file": "Blackout Hr Excel", "col": "dates with data", "method": "COUNT × 24"}],
        [("red", "🔴 Above 80% = Overworked, high risk of breakdown, needs backup generator"),
         ("orange", "🟠 60-80% = Heavy use, schedule maintenance soon"),
         ("amber", "🟡 30-60% = Normal workload"),
         ("green", "🟢 10-30% = Light use"),
         ("blue", "⚪ Below 10% = Nearly idle, check if this generator is needed")],
        "Like checking how many hours each <b>employee works per week</b>. At <r>86%</r> (20+ hours/day), the generator is <r>overworked</r> and will break down soon. At <g>19%</g>, it's barely used. Balance the load or get backup for overworked units."
    )


def _fuel_wastage_report(sector_filter=None, key_prefix="grp"):
    """Fuel wastage report — actual vs expected consumption."""
    with get_db() as conn:
        _dsql, _dp = _date_sql("do.date")
        q = f"""
            SELECT do.site_id, s.sector_id,
                   SUM(do.daily_used_liters) as actual,
                   SUM(do.gen_run_hr * g.consumption_per_hour) as expected,
                   SUM(do.gen_run_hr) as total_hrs
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.gen_run_hr > 0 AND do.daily_used_liters > 0
                  AND g.consumption_per_hour > 0{_dsql}
        """
        params = list(_dp)
        if sector_filter:
            q += " AND s.sector_id = ?"
            params.append(sector_filter)
        q += " GROUP BY do.site_id HAVING expected > 0 ORDER BY (actual - expected) DESC LIMIT 20"
        w_df = pd.read_sql_query(q, conn, params=params)

    if w_df.empty:
        return

    w_df["waste_l"] = w_df["actual"] - w_df["expected"]
    w_df["waste_pct"] = round(w_df["waste_l"] / w_df["expected"] * 100, 1)
    # Get price for cost estimate
    avg_price = fuel_price if fuel_price > 0 else 5000
    w_df["waste_mmk"] = round(w_df["waste_l"] * avg_price)

    st.markdown("## 🚨 Fuel Wastage Report")
    total_waste = w_df[w_df["waste_l"] > 0]["waste_l"].sum()
    total_cost = w_df[w_df["waste_l"] > 0]["waste_mmk"].sum()

    if total_waste > 0:
        wc1, wc2, wc3 = st.columns(3)
        with wc1:
            ui.metric_card(title="Total Waste", content=f"{total_waste:,.0f} L", description="above expected consumption", key=f"waste_l_{key_prefix}")
        with wc2:
            ui.metric_card(title="Waste Cost", content=f"{total_cost/1e6:,.1f}M MMK", description="money potentially wasted", key=f"waste_mmk_{key_prefix}")
        with wc3:
            waste_sites = len(w_df[w_df["waste_l"] > 0])
            ui.metric_card(title="Sites Wasting", content=str(waste_sites), description=f"out of {len(w_df)} sites", key=f"waste_n_{key_prefix}")

    # Table
    display = w_df[["site_id", "sector_id", "actual", "expected", "waste_l", "waste_pct", "waste_mmk"]].copy()
    display["actual"] = display["actual"].apply(lambda x: f"{x:,.0f}")
    display["expected"] = display["expected"].apply(lambda x: f"{x:,.0f}")
    display["waste_l"] = display["waste_l"].apply(lambda x: f"{'🔴 ' if x > 0 else '🟢 '}{x:,.0f}")
    display["waste_pct"] = display["waste_pct"].apply(lambda x: f"{x:+.1f}%")
    display["waste_mmk"] = display["waste_mmk"].apply(lambda x: f"{x:,.0f}")
    display.columns = ["Site", "Sector", "Actual (L)", "Expected (L)", "Waste (L)", "Waste %", "Waste (MMK)"]
    render_smart_table(display, title="Fuel Wastage by Site (worst first)")

    _chart_guide(
        "Waste = Actual diesel used − Expected use (Rated L/Hr × Generator Hours).\nExample: Actual <b>4,200L</b> − Expected <b>3,150L</b> = <b>1,050L wasted</b> = <b>7.44M MMK</b>.",
        [{"data": "Actual Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "SUM per site"},
         {"data": "Expected Use", "file": "Blackout Hr Excel", "col": "Consumption/Hr × Gen Run Hr", "method": "SUM per generator"}],
        [("green", "🟢 Negative waste = Site is MORE efficient than rated (good!)"),
         ("amber", "⚠️ 0-20% waste = Normal tolerance, minor variance"),
         ("red", "🔴 20%+ waste = Significant overconsumption, investigate fuel theft or generator issues")],
        "Every generator has a <b>rated consumption</b> — how much fuel it SHOULD use per hour. We compare that to how much it ACTUALLY used. If actual is <r>much higher</r>, either the generator is <r>broken</r>, someone is <r>stealing fuel</r>, or the data entry is wrong. This report shows where <b>money is being wasted</b>."
    )


def _break_even_calc(df, key_prefix="grp"):
    """Break-even calculator — minimum sales needed to justify diesel cost."""
    matched = df[(df.get("has_sales", pd.Series([False])) == True) & df["energy_cost"].notna() & df["avg_daily_sales"].notna()].copy() if "has_sales" in df.columns and "energy_cost" in df.columns and "avg_daily_sales" in df.columns else pd.DataFrame()
    if matched.empty or len(matched) < 2:
        return

    from config.settings import ENERGY_COST
    threshold = ENERGY_COST.get("healthy_pct", 5) / 100  # 5% = break-even threshold

    matched["diesel_per_day"] = matched["energy_cost"] / matched.get("num_days", pd.Series([1])).clip(lower=1)
    matched["min_sales"] = matched["diesel_per_day"] / threshold
    matched["actual_sales"] = matched["avg_daily_sales"]
    matched["ok"] = matched["actual_sales"] >= matched["min_sales"]

    st.markdown("## 💰 Break-Even Calculator")
    st.markdown(f'<div style="font-size:12px;color:#94a3b8;margin-bottom:8px">Minimum daily sales needed so diesel stays below <b>{int(threshold*100)}%</b> of revenue</div>', unsafe_allow_html=True)

    ok_count = matched["ok"].sum()
    not_ok = len(matched) - ok_count
    bc1, bc2 = st.columns(2)
    with bc1:
        ui.metric_card(title="Above Break-Even", content=f"🟢 {ok_count}", description="sites making enough sales", key=f"be_ok_{key_prefix}")
    with bc2:
        ui.metric_card(title="Below Break-Even", content=f"🔴 {not_ok}", description="sites losing money on fuel", key=f"be_bad_{key_prefix}")

    display = matched.sort_values("ok")[["site_id", "sector_id", "diesel_per_day", "min_sales", "actual_sales", "ok"]].head(20).copy()
    display["diesel_per_day"] = display["diesel_per_day"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    display["min_sales"] = display["min_sales"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    display["actual_sales"] = display["actual_sales"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    display["ok"] = display["ok"].apply(lambda x: "🟢 OK" if x else "🔴 Below")
    display.columns = ["Site", "Sector", "Diesel/Day (MMK)", "Min Sales Needed", "Actual Sales/Day", "Status"]
    render_smart_table(display, title="Break-Even Analysis", severity_col="Status")

    _chart_guide(
        "Min Sales Needed = Daily Diesel Cost ÷ 5% threshold.\nExample: Diesel <b>1.2M/day</b> ÷ 0.05 = Min sales <b>24M/day</b>.",
        [{"data": "Diesel Cost", "file": "Blackout Hr Excel + Fuel Price", "col": "Daily Used × Price", "method": "AVG per day per site"},
         {"data": "Sales Revenue", "file": "Sales Excel", "col": "SALES_AMT", "method": "AVG per day per site"}],
        [("green", "🟢 OK = Actual sales exceed minimum, store is profitable despite fuel"),
         ("red", "🔴 Below = Sales don't justify the fuel cost, consider reducing hours or closing")],
        "If diesel is <b>5% or more</b> of sales, the store is spending too much on fuel. This calculates the <b>minimum sales needed</b> to keep diesel below 5%. If a store sells <r>less than that minimum</r>, it's <r>losing money</r> by staying open during blackouts."
    )


def _sector_radar(df, key_prefix="grp"):
    """Sector comparison — grouped bar chart showing normalized scores (0-100) on 5 metrics."""
    sectors = sorted(df["sector_id"].dropna().unique())
    if len(sectors) < 2:
        return

    # Compute metrics per sector
    data = {}
    for s in sectors:
        sd = df[df["sector_id"] == s]
        buf = sd["latest_buffer_days"].mean() if "latest_buffer_days" in sd.columns else 0
        eff = sd["avg_daily_liters"].sum() / max(sd["total_gen_hours"].sum(), 1) if "total_gen_hours" in sd.columns and "avg_daily_liters" in sd.columns else 0
        fuel = sd["avg_daily_liters"].mean() if "avg_daily_liters" in sd.columns else 0
        epct = sd["energy_pct"].mean() if "energy_pct" in sd.columns and sd["energy_pct"].notna().any() else 0
        data[s] = {"buffer": buf if pd.notna(buf) else 0, "efficiency": eff if pd.notna(eff) else 0,
                   "fuel": fuel if pd.notna(fuel) else 0, "diesel_pct": epct if pd.notna(epct) else 0}

    # Get blackout avg per sector
    with get_db() as conn:
        _dsql, _dp = _date_sql("do.date")
        bo_sec = dict(conn.execute(f"""
            SELECT s.sector_id, AVG(do.blackout_hr) FROM daily_operations do
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.blackout_hr IS NOT NULL{_dsql}
            GROUP BY s.sector_id
        """, _dp).fetchall())
    for s in sectors:
        data[s]["blackout"] = round(bo_sec.get(s, 0), 1) if bo_sec.get(s) else 0

    # Normalize 0-100 (higher = better for all)
    def _norm(vals, higher_better=True):
        clean = [float(v) if pd.notna(v) and v is not None else 0.0 for v in vals]
        mn, mx = min(clean), max(clean)
        if mx == mn:
            return [50] * len(clean)
        if higher_better:
            return [round((v - mn) / (mx - mn) * 100) for v in clean]
        return [round((mx - v) / (mx - mn) * 100) for v in clean]

    try:
        bufs = _norm([data[s]["buffer"] for s in sectors], higher_better=True)
        effs = _norm([data[s]["efficiency"] for s in sectors], higher_better=False)
        fuels = _norm([data[s]["fuel"] for s in sectors], higher_better=False)
        bos = _norm([data[s]["blackout"] for s in sectors], higher_better=False)
        dpcts = _norm([data[s]["diesel_pct"] for s in sectors], higher_better=False)
    except Exception:
        return

    st.markdown("### 📊 Sector Comparison — Scorecard")

    # Use grouped bar chart (radar not supported by this streamlit-echarts version)
    metrics = ["Buffer", "Efficiency", "Low Fuel", "Low Blackout", "Low Diesel%"]
    bar_series = []
    for i, s in enumerate(sectors):
        bar_series.append({
            "name": s,
            "data": [bufs[i], effs[i], fuels[i], bos[i], dpcts[i]],
            "color": SECTOR_COLORS.get(s, PALETTE[i % len(PALETTE)]),
        })
    grouped_bar(metrics, bar_series, title="Sector Scores (0-100, higher = better)", height=400, key=f"radar_{key_prefix}")

    _chart_guide(
        "5 metrics normalized to 0-100 scale. <b>Higher = better</b> on all metrics.\nBuffer (more days = better), Efficiency (lower L/Hr = better, inverted), Low Fuel Use, Low Blackout, Low Diesel%.",
        [{"data": "Buffer Days", "file": "Blackout Hr Excel", "col": "Spare Tank Balance ÷ burn", "method": "AVG per sector"},
         {"data": "Efficiency", "file": "Blackout Hr Excel", "col": "Daily Used ÷ Gen Run Hr", "method": "AVG per sector"},
         {"data": "Fuel Used", "file": "Blackout Hr Excel", "col": "Daily Used", "method": "AVG per sector"},
         {"data": "Blackout Hr", "file": "Blackout Hr Excel", "col": "Blackout Hr", "method": "AVG per sector"},
         {"data": "Diesel %", "file": "Sales + Fuel Price", "col": "cost ÷ sales × 100", "method": "AVG per sector"}],
        [("green", "✅ Tall bars (80-100) = Sector performing well on that metric"),
         ("amber", "⚠️ Medium bars (40-60) = Average, room for improvement"),
         ("red", "🔴 Short bars (0-20) = Sector is weak on that metric, needs attention")],
        "Like a <b>report card</b> for each sector. Each group of bars is a different metric. The <g>tallest bar</g> in each group is the <g>best-performing sector</g> for that metric. If one sector has <r>short bars everywhere</r>, it needs <r>attention on all fronts</r>."
    )


def _monthly_summary(key_prefix="grp"):
    """Monthly summary rollup cards."""
    with get_db() as conn:
        _dsql, _dp = _date_sql("date")
        months_df = pd.read_sql_query(f"""
            SELECT strftime('%Y-%m', date) as month,
                   SUM(total_daily_used) as fuel, COUNT(DISTINCT date) as days,
                   COUNT(DISTINCT site_id) as sites,
                   SUM(spare_tank_balance) as tank,
                   SUM(CASE WHEN days_of_buffer < 3 THEN 1 ELSE 0 END) as crit_days
            FROM daily_site_summary WHERE 1=1{_dsql}
            GROUP BY month ORDER BY month DESC LIMIT 6
        """, conn, params=_dp)

        bo_months = pd.read_sql_query(f"""
            SELECT strftime('%Y-%m', do.date) as month, AVG(do.blackout_hr) as avg_bo
            FROM daily_operations do WHERE do.blackout_hr IS NOT NULL
            AND do.date IN (SELECT DISTINCT date FROM daily_site_summary WHERE 1=1{_dsql})
            GROUP BY month
        """, conn, params=_dp)

    if months_df.empty:
        return

    bo_map = dict(zip(bo_months["month"], bo_months["avg_bo"])) if not bo_months.empty else {}

    st.markdown("## 📋 Monthly Summary")
    cols = st.columns(min(len(months_df), 3))
    for i, (_, row) in enumerate(months_df.iterrows()):
        with cols[i % len(cols)]:
            m = row["month"]
            fuel = row["fuel"] or 0
            days = row["days"] or 1
            burn = fuel / days
            bo = round(bo_map.get(m, 0), 1)
            tank = row["tank"] or 0
            buf = round(tank / max(burn, 1), 1)
            grade = "A" if buf > 10 else "B" if buf > 7 else "C" if buf > 5 else "D" if buf > 3 else "F"
            grade_color = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#f97316", "F": "#ef4444"}[grade]

            st.markdown(f"""<div style="background:#0a0a0a;border:1px solid #1e293b;border-radius:12px;padding:16px;margin-bottom:8px">
                <div style="font-size:16px;font-weight:700;color:white;margin-bottom:8px">📅 {m}</div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="color:#94a3b8;font-size:11px">Total Fuel</span>
                    <span style="color:#e2e8f0;font-size:12px;font-weight:600">{fuel:,.0f} L</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="color:#94a3b8;font-size:11px">Avg Burn/Day</span>
                    <span style="color:#e2e8f0;font-size:12px;font-weight:600">{burn:,.0f} L</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="color:#94a3b8;font-size:11px">Avg Blackout</span>
                    <span style="color:#e2e8f0;font-size:12px;font-weight:600">{bo} hr</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="color:#94a3b8;font-size:11px">Buffer</span>
                    <span style="color:#e2e8f0;font-size:12px;font-weight:600">{buf} days</span>
                </div>
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="color:#94a3b8;font-size:11px">Days Reported</span>
                    <span style="color:#e2e8f0;font-size:12px;font-weight:600">{int(days)} days</span>
                </div>
                <div style="text-align:center;margin-top:8px">
                    <span style="background:{grade_color};color:white;padding:4px 16px;border-radius:6px;font-weight:700;font-size:14px">Grade: {grade}</span>
                </div>
            </div>""", unsafe_allow_html=True)


def _blackout_calendar(key_prefix="grp"):
    """Blackout heatmap calendar — GitHub-style grid."""
    import calendar
    with get_db() as conn:
        _dsql, _dp = _date_sql("do.date")
        cal_df = pd.read_sql_query(f"""
            SELECT do.date, AVG(do.blackout_hr) as avg_bo
            FROM daily_operations do
            WHERE do.blackout_hr IS NOT NULL{_dsql}
            GROUP BY do.date ORDER BY do.date
        """, conn, params=_dp)

    if cal_df.empty:
        return

    st.markdown("## 📅 Blackout Calendar")

    # Group by month
    cal_df["month"] = cal_df["date"].str[:7]
    months = sorted(cal_df["month"].unique(), reverse=True)[:3]  # last 3 months

    for month in months:
        mdata = cal_df[cal_df["month"] == month]
        year, mon = int(month[:4]), int(month[5:7])
        month_name = calendar.month_name[mon]
        _, num_days = calendar.monthrange(year, mon)
        first_dow = calendar.weekday(year, mon, 1)  # 0=Mon

        # Build day→value map
        day_vals = {}
        for _, r in mdata.iterrows():
            d = int(r["date"][8:10])
            day_vals[d] = round(r["avg_bo"], 1)

        # Build grid HTML
        cells = ""
        # Header
        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            cells += f'<div style="text-align:center;font-size:10px;color:#475569;font-weight:600">{dow}</div>'
        # Empty cells before first day
        for _ in range(first_dow):
            cells += '<div></div>'
        # Days
        for d in range(1, num_days + 1):
            v = day_vals.get(d)
            if v is None:
                bg = "#1e293b"; icon = ""; tip = "No data"
            elif v < 4:
                bg = "#166534"; icon = ""; tip = f"{v}hr"
            elif v < 8:
                bg = "#854d0e"; icon = ""; tip = f"{v}hr"
            elif v < 12:
                bg = "#9a3412"; icon = ""; tip = f"{v}hr"
            else:
                bg = "#991b1b"; icon = ""; tip = f"{v}hr"
            cells += f'<div style="background:{bg};border-radius:4px;text-align:center;padding:4px 0;font-size:10px;color:#e2e8f0;cursor:default" title="{tip}">{d}</div>'

        st.markdown(f"""<div style="margin-bottom:12px">
            <div style="font-weight:600;color:#e2e8f0;font-size:13px;margin-bottom:6px">{month_name} {year}</div>
            <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:3px;max-width:350px">{cells}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("""<div style="font-size:11px;color:#64748b;margin-top:4px">
        <span style="background:#166534;padding:2px 8px;border-radius:3px;color:white">🟢 &lt;4hr</span>
        <span style="background:#854d0e;padding:2px 8px;border-radius:3px;color:white;margin-left:4px">🟡 4-8hr</span>
        <span style="background:#9a3412;padding:2px 8px;border-radius:3px;color:white;margin-left:4px">🟠 8-12hr</span>
        <span style="background:#991b1b;padding:2px 8px;border-radius:3px;color:white;margin-left:4px">🔴 12hr+</span>
        <span style="background:#1e293b;padding:2px 8px;border-radius:3px;color:white;margin-left:4px">⚪ No data</span>
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND CENTER SECTIONS (shared helper)
# ═══════════════════════════════════════════════════════════════════════════
def _render_command_sections(sector_filter=None, key_prefix="grp"):
    """Render Operating Modes, Delivery Queue, BCP Scores, Stockout Forecast,
    Supplier Signal, Weekly Budget, Alerts, and What-If.
    sector_filter: None=all, else filter by sector_id."""

    # ── 1. Operating Modes ──────────────────────────────────────────
    st.markdown("## 🎯 Operating Modes")
    st.caption("Should each store run full, reduce hours, or close today?")
    modes_df = get_operating_modes()
    if not modes_df.empty:
        if sector_filter:
            modes_df = modes_df[modes_df["sector_id"] == sector_filter]
        if not modes_df.empty:
            display = modes_df[["site_id", "sector_id", "mode", "days_of_buffer",
                                "spare_tank_balance", "total_daily_used", "daily_fuel_cost", "reason"]].copy()
            display.columns = ["Site", "Sector", "Mode", "Buffer Days", "Tank (L)", "Daily Use (L)", "Daily Cost (MMK)", "Action"]
            render_smart_table(display, title=f"Operating Mode Recommendations ({len(modes_df)} sites)",
                               severity_col="Mode",
                               highlight_cols={"Buffer Days": {"good": "high", "thresholds": [7, 3]}})
        else:
            st.success("All sites in this sector are operating normally.")
    else:
        st.info("No operating mode data.")

    st.markdown("---")

    # ── 2. Delivery Queue ───────────────────────────────────────────
    st.markdown("## 🚛 Fuel Delivery Queue")
    st.caption("Where to send the truck — sorted by urgency")
    queue_df = get_delivery_queue()
    if not queue_df.empty:
        if sector_filter:
            queue_df = queue_df[queue_df["sector_id"] == sector_filter]
        if not queue_df.empty:
            c1, c2, c3 = st.columns(3)
            with c1:
                ui.metric_card(title="Sites Need Fuel", content=str(len(queue_df)),
                               description="below 7-day buffer", key=f"dq_cnt_{key_prefix}")
            with c2:
                ui.metric_card(title="Total Needed", content=f"{queue_df['liters_needed'].sum():,.0f} L",
                               description="to reach 7-day buffer", key=f"dq_lit_{key_prefix}")
            with c3:
                ui.metric_card(title="Delivery Cost", content=f"{queue_df['est_cost'].sum():,.0f} MMK",
                               description="estimated", key=f"dq_cost_{key_prefix}")
            q_display = queue_df[["site_id", "sector_id", "urgency", "days_of_buffer",
                                   "spare_tank_balance", "liters_needed", "delivery_by", "est_cost"]].copy()
            q_display.columns = ["Site", "Sector", "Urgency", "Days Left", "Tank (L)",
                                  "Need (L)", "Deliver By", "Cost (MMK)"]
            render_smart_table(q_display, title="Delivery Queue", severity_col="Urgency")
        else:
            st.success("All sites have 7+ days of fuel. No deliveries needed.")
    else:
        st.success("All sites have 7+ days of fuel. No deliveries needed.")

    st.markdown("---")

    # ── 3. BCP Risk Scores ──────────────────────────────────────────
    st.markdown("## 🛡️ BCP Risk Scores")
    st.caption("A-F grades: Fuel Reserve (35%) + Generator Coverage (30%) + Power Capacity (20%) + Resilience (15%)")
    with get_db() as conn:
        _dsql_bcp, _dp_bcp = _date_sql("date")
        best_date = conn.execute(f"SELECT date FROM daily_site_summary WHERE 1=1{_dsql_bcp} GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1", _dp_bcp).fetchone()
        best_date = best_date[0] if best_date else None
    if best_date:
        bcp_df = compute_bcp_scores(best_date)
        if not bcp_df.empty:
            if sector_filter:
                bcp_df = bcp_df[bcp_df["sector_id"] == sector_filter]
            if not bcp_df.empty:
                grades = bcp_df["grade"].value_counts().to_dict()
                gc1, gc2, gc3, gc4, gc5 = st.columns(5)
                for col, (grade, color) in zip([gc1, gc2, gc3, gc4, gc5],
                    [("A", "#16a34a"), ("B", "#2196F3"), ("C", "#d97706"), ("D", "#ea580c"), ("F", "#dc2626")]):
                    with col:
                        cnt = grades.get(grade, 0)
                        st.markdown(f'<div style="background:{color};color:white;border-radius:8px;padding:10px;text-align:center">'
                                    f'<span style="font-size:22px;font-weight:700">{grade}: {cnt}</span></div>',
                                    unsafe_allow_html=True)
                bcp_display = bcp_df[["site_id", "sector_id", "bcp_score", "grade"]].sort_values("bcp_score").copy()
                bcp_display.columns = ["Site", "Sector", "Score", "Grade"]
                render_smart_table(bcp_display, title="BCP Scores (worst first)", severity_col="Grade")

    st.markdown("---")

    # ── 4. 7-Day Stockout Forecast ──────────────────────────────────
    st.markdown("## ⏰ 7-Day Stockout Forecast")
    st.caption("Sites projected to run out of diesel within 7 days")
    try:
        critical_df = get_critical_sites(threshold_days=7)
        if not critical_df.empty:
            if sector_filter:
                critical_df = critical_df[critical_df["sector_id"] == sector_filter]
            if not critical_df.empty:
                st.warning(f"**{len(critical_df)} sites** projected to run low within 7 days")
                cs_display = critical_df[["site_id", "sector_id", "current_balance", "smoothed_daily_used",
                                           "days_until_stockout", "projected_stockout_date", "trend", "confidence"]].copy()
                cs_display["current_balance"] = cs_display["current_balance"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                cs_display["smoothed_daily_used"] = cs_display["smoothed_daily_used"].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
                cs_display["days_until_stockout"] = cs_display["days_until_stockout"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
                cs_display.columns = ["Site", "Sector", "Tank (L)", "Daily Burn (smoothed)", "Days Left",
                                       "Stockout Date", "Trend", "Confidence"]
                render_smart_table(cs_display, title="Critical Stockout Forecast")
            else:
                st.success("No sites in this sector projected to run out within 7 days.")
        else:
            st.success("No sites projected to run out within 7 days.")
    except Exception as e:
        st.info(f"Forecast model needs more data: {e}")

    st.markdown("---")

    # ── 5. Supplier Buy Signal ──────────────────────────────────────
    # ── 6. Weekly Budget ────────────────────────────────────────────
    st.markdown("## 💰 Fuel Price & Weekly Budget")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Supplier Buy Signal")
        signal = get_supplier_buy_signal()
        if signal and signal.get("signals"):
            for s in signal["signals"]:
                color = "#16a34a" if s["recommendation"] == "BUY NOW" else "#d97706" if s["recommendation"] == "WAIT" else "#3b82f6"
                st.markdown(f"""
                <div style="background:white;border:1px solid #e5e7eb;border-left:4px solid {color};
                            border-radius:0 10px 10px 0;padding:14px;margin:6px 0">
                    <strong>{s['supplier']}</strong> — {s['current_price']:,.0f} MMK/L
                    → <strong style="color:{color}">{s['recommendation']}</strong>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No supplier price data.")
    with col2:
        st.markdown("#### Weekly Budget")
        budget = get_weekly_budget_forecast()
        if budget:
            ui.metric_card(title="Weekly Budget", content=f"{budget['total_weekly_cost_mmk']:,.0f} MMK",
                           description=f"{budget['total_weekly_liters']:,.0f} L needed", key=f"wb_{key_prefix}")
            if budget["sectors"]:
                budget_df = pd.DataFrame(budget["sectors"])
                if sector_filter:
                    budget_df = budget_df[budget_df["sector_id"] == sector_filter]
                if not budget_df.empty:
                    budget_df.columns = ["Sector", "Daily (L)", "Weekly (L)", "Price/L", "Weekly Cost"]
                    render_smart_table(budget_df, title="Weekly Budget by Sector")

    st.markdown("---")

    # ── 7. Active Alerts ────────────────────────────────────────────
    st.markdown("## 🚨 Active Alerts")
    alerts_df = get_active_alerts(sector_id=sector_filter)
    if not alerts_df.empty:
        for severity, color in [("CRITICAL", "#dc2626"), ("WARNING", "#d97706"), ("INFO", "#3b82f6")]:
            sev_df = alerts_df[alerts_df["severity"] == severity]
            if not sev_df.empty:
                st.markdown(f"**{severity}** ({len(sev_df)})")
                for _, a in sev_df.head(10).iterrows():
                    site = a.get("site_id") or a.get("sector_id") or ""
                    st.markdown(f'<div style="border-left:3px solid {color};padding:6px 12px;margin:4px 0;font-size:13px">'
                                f'<strong>{site}</strong> — {a["message"]}</div>', unsafe_allow_html=True)
    else:
        st.success("No active alerts.")

    st.markdown("---")

    # ── 8. What-If Simulator ────────────────────────────────────────
    st.markdown("## 🔮 What-If Simulator")
    st.caption("See how cost changes with different fuel prices or consumption levels")
    wc1, wc2 = st.columns(2)
    with wc1:
        price_change = st.slider("Fuel Price Change %", -30, 50, 0, 5, key=f"wi_price_{key_prefix}")
    with wc2:
        consumption_change = st.slider("Consumption Change %", -30, 50, 0, 5, key=f"wi_consumption_{key_prefix}")
    whatif = run_what_if(price_change, consumption_change)
    if whatif:
        wrc1, wrc2, wrc3 = st.columns(3)
        with wrc1:
            ui.metric_card(title="Current Weekly", content=f"{whatif['base_cost']:,.0f} MMK", key=f"wi_base_{key_prefix}")
        with wrc2:
            ui.metric_card(title="Projected", content=f"{whatif['new_cost']:,.0f} MMK",
                           description=f"{'↑' if whatif['pct_change'] > 0 else '↓'} {abs(whatif['pct_change'])}%", key=f"wi_new_{key_prefix}")
        with wrc3:
            ui.metric_card(title="Impact", content=f"{'+' if whatif['difference'] > 0 else ''}{whatif['difference']:,.0f} MMK", key=f"wi_diff_{key_prefix}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ═══════════════════════════════════════════════════════════════════════════
grp_col = "business_sector" if "business_sector" in econ.columns and econ["business_sector"].notna().any() else "sector_id"
# Get ALL sectors from DB (not filtered econ) so tabs always show
with get_db() as conn:
    if grp_col == "business_sector":
        _all_sectors = sorted(set(r[0] for r in conn.execute("SELECT DISTINCT business_sector FROM sites WHERE business_sector IS NOT NULL").fetchall()))
    else:
        _all_sectors = sorted(set(r[0] for r in conn.execute("SELECT DISTINCT sector_id FROM sites").fetchall()))
sectors = _all_sectors if _all_sectors else sorted(econ[grp_col].dropna().unique())
if not sectors:
    st.info("No sector data.")
    st.stop()

# Single level of tabs: Group + each sector + Dictionary
sec_sel = ui.tabs(options=["Group"] + sectors + ["Dictionary"], default_value="Group", key="v2_sec")

# ─── Morning Briefing (AI-generated, top of page) ────────────────────
if sec_sel != "Dictionary":
    # Build briefing data from econ
    _ab = econ[(econ["avg_daily_liters"].notna()) & (econ["avg_daily_liters"] > 0)]
    _hb = _ab[(econ["diesel_available"].notna()) & (econ["diesel_available"] > 0)] if "diesel_available" in _ab.columns else _ab
    _buf_sites = _hb[_hb["latest_buffer_days"].notna()] if "latest_buffer_days" in _hb.columns else _hb
    _crit = _buf_sites[_buf_sites["latest_buffer_days"] < 3] if not _buf_sites.empty else pd.DataFrame()
    _warn_s = _buf_sites[(_buf_sites["latest_buffer_days"] >= 3) & (_buf_sites["latest_buffer_days"] < 7)] if not _buf_sites.empty else pd.DataFrame()
    _worst = _crit.sort_values("latest_buffer_days").head(5) if not _crit.empty else pd.DataFrame()
    _worst_str = ", ".join(f"{r['site_id']} ({r['latest_buffer_days']:.1f}d)" for _, r in _worst.iterrows()) if not _worst.empty else "none"

    _briefing_data = {
        "date_range": f"{str_from} → {str_to}",
        "total_sites": len(econ),
        "buffer_days": round(_hb["diesel_available"].sum() / max(_ab["avg_daily_liters"].sum(), 1), 1) if not _ab.empty else 0,
        "critical_sites": len(_crit),
        "warning_sites": len(_warn_s),
        "safe_sites": len(_buf_sites[_buf_sites["latest_buffer_days"] >= 7]) if not _buf_sites.empty else 0,
        "total_tank": round(_hb["diesel_available"].sum()) if not _hb.empty else 0,
        "daily_burn": round(_ab["avg_daily_liters"].sum()) if not _ab.empty else 0,
        "diesel_cost_daily": f"{_ab['avg_daily_liters'].sum() * fuel_price / 1e6:,.1f}M MMK" if not _ab.empty else "0",
        "fuel_price": f"{fuel_price:,.0f} MMK/L",
        "worst_sites": _worst_str,
        "anomalies": 0,
        "sectors": ", ".join(f"{s}: {len(econ[econ[grp_col]==s])} sites" for s in sectors if s in econ[grp_col].values),
    }

    if st.button("🤖 Get AI Insights", key="btn_briefing", use_container_width=True):
        st.session_state["_show_briefing"] = True
        st.session_state["_briefing_data"] = _briefing_data

    if st.session_state.get("_show_briefing"):
        _bd = st.session_state.get("_briefing_data", _briefing_data)
        _briefing = morning_briefing(_bd, force_refresh=True)
        st.markdown(f"""
        <div style="background:#0f172a;border-left:4px solid #00ff41;border-radius:0 12px 12px 0;
                    padding:16px 20px;margin:8px 0;color:#e0e0e0;font-size:13px;line-height:1.8">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-weight:700;color:#00ff41;font-size:15px">🤖 Morning Briefing</span>
                <span style="font-size:11px;opacity:0.5">{str_to} | Gemini 3.1 Flash</span>
            </div>
            <div style="white-space:pre-line">{_briefing}</div>
        </div>""", unsafe_allow_html=True)

if sec_sel == "Dictionary":
    # ── Dictionary Tab ──────────────────────────────────────────────
    st.markdown("## 📖 Dictionary — KPI Definitions & Thresholds")

    _threshold_legend()

    st.markdown("---")

    # KPI Definitions (expanded with new KPIs)
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">KPI Definitions & Formulas</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:left">KPI</th>
<th style="padding:10px 12px;text-align:left">Formula</th>
<th style="padding:10px 12px;text-align:left">Source</th>
<th style="padding:10px 12px;text-align:left">Unit</th>
<th style="padding:10px 12px;text-align:left">Where Used</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;font-weight:600">Days of Diesel Left</td>
<td style="padding:8px 12px">Closing Tank Balance ÷ (7-Day Avg Blackout Hr × Rated L/Hr)</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Days</td>
<td style="padding:8px 12px">Group, Sector, Site KPI cards</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Total Tank Balance</td>
<td style="padding:8px 12px">Closing balance of last date in range (SUM across sites with tank data)</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Liters</td>
<td style="padding:8px 12px">Group, Sector KPI cards</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Daily Burn Rate</td>
<td style="padding:8px 12px">SUM(Total Daily Used) ÷ Number of Days (all sites with data)</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Liters/day</td>
<td style="padding:8px 12px">KPI cards, Trend charts</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Diesel Needed</td>
<td style="padding:8px 12px">SUM(7 × Avg Burn − Tank) for sites below 7 days</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Liters</td>
<td style="padding:8px 12px">KPI cards, Delivery Queue</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Daily Diesel Cost</td>
<td style="padding:8px 12px">Daily Used (L) × Date-Specific Price (most recent purchase on/before that date)</td>
<td style="padding:8px 12px">Blackout Hr + Fuel Price Excel</td>
<td style="padding:8px 12px">MMK</td>
<td style="padding:8px 12px">KPI cards, Cost trends</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Diesel % of Sales</td>
<td style="padding:8px 12px">(Liters × Price) ÷ Sales Amount × 100</td>
<td style="padding:8px 12px">All Excel files</td>
<td style="padding:8px 12px">%</td>
<td style="padding:8px 12px">KPI cards, Heatmap, Operating Mode</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Buffer Days (per site)</td>
<td style="padding:8px 12px">Closing Tank Balance ÷ (7-Day Avg Blackout Hr × Rated L/Hr). If blackout = 0, no fuel consumed.</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Days</td>
<td style="padding:8px 12px">Heatmap, Site KPI, Trend</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Efficiency (L/Hr)</td>
<td style="padding:8px 12px">Actual Liters Used ÷ Generator Run Hours</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">L/Hr</td>
<td style="padding:8px 12px">Site trend charts, Anomaly detection</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Variance</td>
<td style="padding:8px 12px">Actual Used − (Rated L/hr × Run Hours)</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Liters / %</td>
<td style="padding:8px 12px">Site generator detail</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">BCP Score</td>
<td style="padding:8px 12px">Fuel Reserve 35% + Gen Coverage 30% + Power Capacity 20% + Resilience 15%</td>
<td style="padding:8px 12px">All data sources</td>
<td style="padding:8px 12px">0–100 (A–F)</td>
<td style="padding:8px 12px">BCP Risk Scores section</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Margin %</td>
<td style="padding:8px 12px">MARGIN ÷ SALES_AMT × 100</td>
<td style="padding:8px 12px">Sales Excel</td>
<td style="padding:8px 12px">%</td>
<td style="padding:8px 12px">Heatmap table, Site trends</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Rolling 3-Day Average</td>
<td style="padding:8px 12px">AVG(value for day N, N-1, N-2)</td>
<td style="padding:8px 12px">Calculated from daily data</td>
<td style="padding:8px 12px">Same as metric</td>
<td style="padding:8px 12px">Last 3 Days trend charts</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Cumulative Fuel</td>
<td style="padding:8px 12px">Running SUM(Daily Used) from first date</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Liters</td>
<td style="padding:8px 12px">Site trend charts</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Anomaly Detection</td>
<td style="padding:8px 12px">Daily Used &gt; 7-Day Rolling Average × 1.3 (30%+ above)</td>
<td style="padding:8px 12px">Blackout Hr Excel</td>
<td style="padding:8px 12px">Flag</td>
<td style="padding:8px 12px">Site anomaly section, Operations</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Peak Hours Profitability</td>
<td style="padding:8px 12px">Avg Hourly Sales ÷ Estimated Diesel Cost per Hour</td>
<td style="padding:8px 12px">Hourly Sales + Fuel Price Excel</td>
<td style="padding:8px 12px">Ratio</td>
<td style="padding:8px 12px">Peak Hours Heatmap</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Diesel Cost per Hour</td>
<td style="padding:8px 12px">(Avg Daily Liters ÷ Avg Gen Hours) × Price per Liter</td>
<td style="padding:8px 12px">Blackout Hr + Fuel Price Excel</td>
<td style="padding:8px 12px">MMK/hr</td>
<td style="padding:8px 12px">Peak Hours Heatmap</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Operating Mode Definitions
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Operating Mode Definitions</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:left">Mode</th>
<th style="padding:10px 12px;text-align:left">Diesel % of Sales</th>
<th style="padding:10px 12px;text-align:left">Action</th>
<th style="padding:10px 12px;text-align:center">Color</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;font-weight:600">FULL OPERATIONS</td>
<td style="padding:8px 12px">&lt; 5%</td>
<td style="padding:8px 12px">Normal operations, all hours</td>
<td style="padding:8px 12px;text-align:center"><span style="background:#16a34a;color:white;padding:3px 10px;border-radius:8px">Green</span></td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">MONITOR</td>
<td style="padding:8px 12px">5% – 15%</td>
<td style="padding:8px 12px">Watch trends, optimize generator usage</td>
<td style="padding:8px 12px;text-align:center"><span style="background:#d97706;color:white;padding:3px 10px;border-radius:8px">Amber</span></td></tr>
<tr><td style="padding:8px 12px;font-weight:600">REDUCE HOURS</td>
<td style="padding:8px 12px">15% – 30%</td>
<td style="padding:8px 12px">Cut operating hours, prioritize high-margin periods</td>
<td style="padding:8px 12px;text-align:center"><span style="background:#ea580c;color:white;padding:3px 10px;border-radius:8px">Orange</span></td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">CRITICAL</td>
<td style="padding:8px 12px">30% – 60%</td>
<td style="padding:8px 12px">Minimum staffing, essential operations only</td>
<td style="padding:8px 12px;text-align:center"><span style="background:#dc2626;color:white;padding:3px 10px;border-radius:8px">Red</span></td></tr>
<tr><td style="padding:8px 12px;font-weight:600">CLOSE</td>
<td style="padding:8px 12px">&gt; 60%</td>
<td style="padding:8px 12px">Recommend temporary closure — losing money</td>
<td style="padding:8px 12px;text-align:center"><span style="background:#7f1d1d;color:white;padding:3px 10px;border-radius:8px">Dark Red</span></td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # BCP Grade Definitions
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">BCP Risk Grades</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:center">Grade</th>
<th style="padding:10px 12px;text-align:left">Score Range</th>
<th style="padding:10px 12px;text-align:left">Label</th>
<th style="padding:10px 12px;text-align:left">Meaning</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;text-align:center"><span style="background:#16a34a;color:white;padding:3px 12px;border-radius:8px;font-weight:700">A</span></td>
<td style="padding:8px 12px">80 – 100</td><td style="padding:8px 12px;font-weight:600">RESILIENT</td>
<td style="padding:8px 12px">Excellent fuel reserves, full generator coverage, strong capacity</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center"><span style="background:#2196F3;color:white;padding:3px 12px;border-radius:8px;font-weight:700">B</span></td>
<td style="padding:8px 12px">60 – 79</td><td style="padding:8px 12px;font-weight:600">ADEQUATE</td>
<td style="padding:8px 12px">Sufficient reserves, minor gaps in coverage</td></tr>
<tr><td style="padding:8px 12px;text-align:center"><span style="background:#d97706;color:white;padding:3px 12px;border-radius:8px;font-weight:700">C</span></td>
<td style="padding:8px 12px">40 – 59</td><td style="padding:8px 12px;font-weight:600">AT RISK</td>
<td style="padding:8px 12px">Low fuel buffer, some generators underperforming</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center"><span style="background:#ea580c;color:white;padding:3px 12px;border-radius:8px;font-weight:700">D</span></td>
<td style="padding:8px 12px">20 – 39</td><td style="padding:8px 12px;font-weight:600">VULNERABLE</td>
<td style="padding:8px 12px">Critical fuel shortage, limited generator capacity</td></tr>
<tr><td style="padding:8px 12px;text-align:center"><span style="background:#dc2626;color:white;padding:3px 12px;border-radius:8px;font-weight:700">F</span></td>
<td style="padding:8px 12px">0 – 19</td><td style="padding:8px 12px;font-weight:600">CRITICAL</td>
<td style="padding:8px 12px">Imminent stockout risk, immediate action required</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Alert Severity Definitions
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Alert Severity Levels</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:center">Severity</th>
<th style="padding:10px 12px;text-align:left">Trigger Conditions</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;text-align:center"><span style="background:#dc2626;color:white;padding:3px 10px;border-radius:8px;font-weight:600">CRITICAL</span></td>
<td style="padding:8px 12px">Buffer &lt; 3 days | Diesel % &gt; 30% | Price surge &gt; 20% | Stockout predicted within 5 days</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center"><span style="background:#d97706;color:white;padding:3px 10px;border-radius:8px;font-weight:600">WARNING</span></td>
<td style="padding:8px 12px">Buffer 3–7 days | Diesel % 15–30% | Price spike 10–20% | Generator idle &gt; 3 days</td></tr>
<tr><td style="padding:8px 12px;text-align:center"><span style="background:#3b82f6;color:white;padding:3px 10px;border-radius:8px;font-weight:600">INFO</span></td>
<td style="padding:8px 12px">Missing data &gt; 2 days | Efficiency outside 0.5–1.5 range | Sector buffer &lt; 5 days</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Variance Status Definitions
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Variance Status (Generator Level)</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:center">Status</th>
<th style="padding:10px 12px;text-align:left">Variance %</th>
<th style="padding:10px 12px;text-align:left">Meaning</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;text-align:center"><span style="color:#dc2626;font-weight:700">🔴 OVER</span></td>
<td style="padding:8px 12px">&gt; +20%</td>
<td style="padding:8px 12px">Using significantly more than rated — possible theft, leak, or engine issue</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center"><span style="color:#16a34a;font-weight:700">🟢 NORMAL</span></td>
<td style="padding:8px 12px">−20% to +20%</td>
<td style="padding:8px 12px">Within expected range based on rated consumption</td></tr>
<tr><td style="padding:8px 12px;text-align:center"><span style="color:#d97706;font-weight:700">🟡 UNDER</span></td>
<td style="padding:8px 12px">&lt; −20%</td>
<td style="padding:8px 12px">Using less than rated — running below capacity or intermittent use</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center"><span style="color:#6b7280;font-weight:700">⚪ NOT RUNNING</span></td>
<td style="padding:8px 12px">N/A</td>
<td style="padding:8px 12px">Generator has 0 recorded run hours</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Data Source Reference
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Data Sources</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:left">Excel File</th>
<th style="padding:10px 12px;text-align:left">Sheets</th>
<th style="padding:10px 12px;text-align:left">Key Columns Used</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;font-weight:600">Blackout Hr_ CP/CMHL/CFC/PG.xlsx</td>
<td style="padding:8px 12px">CP, CMHL, CFC, PG</td>
<td style="padding:8px 12px">Site, Gen Run Hr, Daily Used, Spare Tank Balance, Blackout Hr, Sector, Company</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Daily Fuel Price.xlsx</td>
<td style="padding:8px 12px">CMHL, CP, CFC, PG</td>
<td style="padding:8px 12px">Date, Supplier, Fuel Type, Quantity, Price per Liter</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">CMHL_DAILY_SALES.xlsx</td>
<td style="padding:8px 12px">daily sales, hourly sales, STORE MASTER</td>
<td style="padding:8px 12px">SALES_DATE, CostCenter, SALES_AMT, MARGIN, GOLD_CODE</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Diesel Expense LY.xlsx</td>
<td style="padding:8px 12px">—</td>
<td style="padding:8px 12px">CostCenter, Diesel % on Sales (last year baseline)</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Peak Hours Heatmap Definition
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">🕐 Peak Hours Heatmap — How to Read</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:center">Icon</th>
<th style="padding:10px 12px;text-align:left">Status</th>
<th style="padding:10px 12px;text-align:left">Sales vs Diesel Cost Ratio</th>
<th style="padding:10px 12px;text-align:left">Action</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;text-align:center;font-size:18px">🟢</td>
<td style="padding:8px 12px;font-weight:600">PEAK</td>
<td style="padding:8px 12px">Hourly Sales &gt; 3× Diesel Cost/Hr</td>
<td style="padding:8px 12px">Maximum staffing — highest profit hours</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center;font-size:18px">🟡</td>
<td style="padding:8px 12px;font-weight:600">PROFITABLE</td>
<td style="padding:8px 12px">Hourly Sales 1.5–3× Diesel Cost/Hr</td>
<td style="padding:8px 12px">Keep open — covers fuel with good margin</td></tr>
<tr><td style="padding:8px 12px;text-align:center;font-size:18px">🟠</td>
<td style="padding:8px 12px;font-weight:600">MARGINAL</td>
<td style="padding:8px 12px">Hourly Sales 1–1.5× Diesel Cost/Hr</td>
<td style="padding:8px 12px">Review — barely covers diesel cost</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center;font-size:18px">🔴</td>
<td style="padding:8px 12px;font-weight:600">LOSING</td>
<td style="padding:8px 12px">Hourly Sales &lt; Diesel Cost/Hr</td>
<td style="padding:8px 12px">Close during this hour — store loses money on diesel</td></tr>
<tr><td style="padding:8px 12px;text-align:center;font-size:18px">⚪</td>
<td style="padding:8px 12px;font-weight:600">NO DATA</td>
<td style="padding:8px 12px">No hourly sales recorded</td>
<td style="padding:8px 12px">Store closed or no data for this hour</td></tr>
</tbody></table>
<div style="padding:10px 12px;font-size:12px;color:#64748b;background:#f8fafc;border-top:1px solid #e5e7eb">
<strong>How it works:</strong> Each cell = average hourly sales for that time slot ÷ estimated diesel cost per generator hour.
Diesel Cost/Hr = (Avg Daily Liters ÷ Avg Gen Hours) × Fuel Price per Liter.<br>
<strong>Use case:</strong> If 21:00–22:00 shows 🔴 every day of week → recommend closing at 9pm. If weekdays 🔴 but Saturday 🟢 → stay open weekends only.<br>
<strong>Data:</strong> Only available for sectors with hourly sales data (CMHL, CP). CFC and PG need hourly sales upload.
</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Icon Reference (used across all tables)
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">Icon Reference (Used Across All Tables)</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:center">Icon</th>
<th style="padding:10px 12px;text-align:left">Meaning in Heatmap Tables</th>
<th style="padding:10px 12px;text-align:left">Meaning in Peak Hours</th>
<th style="padding:10px 12px;text-align:left">Meaning in Alerts</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;text-align:center;font-size:20px">🟢</td>
<td style="padding:8px 12px">Within safe threshold (Green zone)</td>
<td style="padding:8px 12px">Peak profitability (&gt;3× diesel)</td>
<td style="padding:8px 12px">Safe / Healthy / BETTER</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center;font-size:20px">🟡</td>
<td style="padding:8px 12px">Approaching threshold (Yellow zone)</td>
<td style="padding:8px 12px">Profitable (1.5–3× diesel)</td>
<td style="padding:8px 12px">Watch / Monitor</td></tr>
<tr><td style="padding:8px 12px;text-align:center;font-size:20px">🟠</td>
<td style="padding:8px 12px">Warning level (Amber zone)</td>
<td style="padding:8px 12px">Marginal (1–1.5× diesel)</td>
<td style="padding:8px 12px">Warning / Attention needed</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;text-align:center;font-size:20px">🔴</td>
<td style="padding:8px 12px">Critical level (Red zone)</td>
<td style="padding:8px 12px">Losing money (&lt;1× diesel)</td>
<td style="padding:8px 12px">Critical / Immediate action</td></tr>
<tr><td style="padding:8px 12px;text-align:center;font-size:20px">⚪</td>
<td style="padding:8px 12px">No data / N/A</td>
<td style="padding:8px 12px">No sales data for this hour</td>
<td style="padding:8px 12px">—</td></tr>
</tbody></table>
<div style="padding:10px 12px;font-size:12px;color:#64748b;background:#f8fafc;border-top:1px solid #e5e7eb">
<strong>Why icons?</strong> Icons are preserved in Excel downloads even when background colors are lost. Every colored cell shows both the icon and the background color for double clarity.
</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Dashboard Navigation Guide
    st.markdown("""
<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:12px;margin:12px 0">
<div style="background:#0f172a;color:white;padding:10px 16px;border-radius:12px 12px 0 0;font-weight:700;font-size:15px">📍 Dashboard Navigation Guide</div>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#1e293b;color:#cbd5e1">
<th style="padding:10px 12px;text-align:left">Tab</th>
<th style="padding:10px 12px;text-align:left">Level</th>
<th style="padding:10px 12px;text-align:left">What You See</th>
<th style="padding:10px 12px;text-align:left">Key Decision</th>
</tr></thead>
<tbody>
<tr><td style="padding:8px 12px;font-weight:600">Group</td>
<td style="padding:8px 12px">All sectors combined</td>
<td style="padding:8px 12px">KPIs (Total/Last Day/3 Day), Sector Heatmap, Rankings, Operating Modes, Delivery Queue, BCP Scores, Stockout Forecast, Budget, Alerts, Fuel Price, Operations, Peak Hours</td>
<td style="padding:8px 12px">"How is the whole business doing?"</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">CFC / CMHL / CP / PG</td>
<td style="padding:8px 12px">Sector level</td>
<td style="padding:8px 12px"><strong>All tab:</strong> Sector KPIs, Site Heatmap Table, Rankings, Operating Modes, Alerts (filtered to sector), Peak Hours<br><strong>Site tab:</strong> Dropdown → individual site deep-dive</td>
<td style="padding:8px 12px">"Which sites in this sector need attention?"</td></tr>
<tr><td style="padding:8px 12px;font-weight:600">Site (dropdown)</td>
<td style="padding:8px 12px">Individual store</td>
<td style="padding:8px 12px">Site KPI Card, Generator Variance, Generator Fleet, 15+ Trend Charts (Daily/Weekly/Monthly), Anomaly Detection, Site vs Sector Comparison, Peak Hours</td>
<td style="padding:8px 12px">"Should this store stay open? When? Is there theft?"</td></tr>
<tr style="background:#f8fafc"><td style="padding:8px 12px;font-weight:600">Dictionary</td>
<td style="padding:8px 12px">Reference</td>
<td style="padding:8px 12px">All KPI definitions, formulas, thresholds, icon meanings, data sources</td>
<td style="padding:8px 12px">"What does this number mean?"</td></tr>
</tbody></table></div>""", unsafe_allow_html=True)

elif sec_sel == "Group":
    _kpis(econ)
    st.markdown("---")
    # Week-over-Week Comparison (after KPIs)
    _week_over_week(key_prefix="grp")
    st.markdown("---")
    _agg_heatmap(econ, grp_col, f"Group Overview — {econ[grp_col].nunique()} Sectors")
    # AI Table Insight (only on button click)
    if st.session_state.get("_show_briefing"):
        _tbl_summary = " | ".join(f"{g}: {len(econ[econ[grp_col]==g])} sites, buffer {econ[econ[grp_col]==g]['latest_buffer_days'].mean():.1f}d"
                                   for g in econ[grp_col].dropna().unique() if not econ[econ[grp_col]==g].empty)
        _tbl_ai = table_insight(_tbl_summary, "sector")
        render_insight_box(_tbl_ai, "🧠 Sector Analysis")
    # Sector Radar Chart (after heatmap)
    _sector_radar(econ, key_prefix="grp")
    st.markdown("---")
    # Break-Even Calculator
    _break_even_calc(econ, key_prefix="grp")
    st.markdown("---")
    # Type comparison
    _type_comparison(econ, key_prefix="grp")
    st.markdown("---")
    # Fuel Wastage Report (after type comparison)
    _fuel_wastage_report(key_prefix="grp")
    st.markdown("---")
    # Top 15 rankings
    st.markdown("## 📊 Site Rankings")
    _top15_charts(econ, key_prefix="grp")
    st.markdown("---")
    # Mapped vs Unmapped
    st.markdown("## 🔗 Sales-Mapped Sites")
    _mapped_unmapped(econ, key_prefix="grp")
    st.markdown("---")
    # Command Center sections (Operating Modes, Delivery, BCP, Stockout, Budget, Alerts, What-If)
    _render_command_sections(sector_filter=None, key_prefix="grp")
    st.markdown("---")
    # Fuel Price Intelligence
    _fuel_price_section(key_prefix="grp")
    st.markdown("---")
    # Operations & Fleet (includes Generator Utilization)
    _operations_section(sector_filter=None, key_prefix="grp")
    _generator_utilization(key_prefix="grp")
    st.markdown("---")
    # Day-of-Week Patterns
    _day_of_week_patterns(key_prefix="grp")
    st.markdown("---")
    # Peak Hours Heatmap
    _peak_hours_heatmap(key_prefix="grp")
    st.markdown("---")
    # Blackout Calendar
    _blackout_calendar(key_prefix="grp")
    st.markdown("---")
    # Predictions
    _predictions_section(econ, key_prefix="grp")
    st.markdown("---")
    # Monthly Summary (last section)
    _monthly_summary(key_prefix="grp")
else:
    sec_df = econ[econ[grp_col] == sec_sel]
    if sec_df.empty:
        st.info(f"No data for **{sec_sel}** in selected date range ({str_from} → {str_to}). Select a wider date range or click 'All Data'.")
        st.stop()
    _sec_ids = sec_df["sector_id"].dropna().unique().tolist()
    _sec_filter = _sec_ids[0] if len(_sec_ids) == 1 else None

    # Build flat tabs: All + each company + Site — get ALL companies from DB
    with get_db() as conn:
        if _sec_filter:
            _all_companies = sorted(set(r[0] for r in conn.execute("SELECT DISTINCT company FROM sites WHERE sector_id = ? AND company IS NOT NULL", (_sec_filter,)).fetchall()))
        else:
            # Try mapping sec_sel (business_sector name) to sector_id
            _sec_map = dict(conn.execute("SELECT DISTINCT business_sector, sector_id FROM sites WHERE business_sector IS NOT NULL").fetchall())
            _mapped_sid = _sec_map.get(sec_sel)
            if _mapped_sid:
                _all_companies = sorted(set(r[0] for r in conn.execute("SELECT DISTINCT company FROM sites WHERE sector_id = ? AND company IS NOT NULL", (_mapped_sid,)).fetchall()))
            else:
                _all_companies = []
    comp_col = "company" if "company" in sec_df.columns and sec_df["company"].notna().any() else None
    companies = _all_companies if _all_companies else (sorted(sec_df[comp_col].dropna().unique()) if comp_col else [])
    sec_tab_opts = ["All"] + companies + ["Site"]
    sec_tab_sel = ui.tabs(options=sec_tab_opts, default_value="All", key="v2_sec_view")

    if sec_tab_sel == "All":
        _kpis(sec_df)
        st.markdown("---")
        sec_sorted = sec_df.sort_values("energy_pct", ascending=False, na_position="last")
        _site_table(sec_sorted, f"{sec_sel} — {len(sec_df)} sites")
        st.markdown("---")
        _type_comparison(sec_df, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        st.markdown("## 📊 Site Rankings")
        _top15_charts(sec_df, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        st.markdown("## 🔗 Sales-Mapped Sites")
        _mapped_unmapped(sec_df, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        _render_command_sections(sector_filter=_sec_filter, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        _operations_section(sector_filter=_sec_filter, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        _peak_hours_heatmap(sector_filter=_sec_filter, key_prefix=f"sec_{sec_sel}")
        st.markdown("---")
        _predictions_section(sec_df, sector_filter=_sec_filter, key_prefix=f"sec_{sec_sel}")

    elif sec_tab_sel == "Site":
        sec_sorted = sec_df.sort_values("site_id")
        opts = [f"{r['site_id']} — {r['site_name']}" for _, r in sec_sorted.iterrows()]
        if opts:
            sc1, sc2 = st.columns([3, 1])
            with sc1:
                sel_multi = st.multiselect("Select Sites", ["All"] + opts, default=["All"], key="v2_sec_site_dd")
            with sc2:
                site_period = st.selectbox("Period", ["Daily", "Weekly", "Monthly"], key="v2_site_period")

            # Resolve selected sites
            if "All" in sel_multi or not sel_multi:
                selected_ids = [r['site_id'] for _, r in sec_sorted.iterrows()]
                _show_all = True
            else:
                selected_ids = [s.split(" — ")[0] for s in sel_multi if s != "All"]
                _show_all = False

            if len(selected_ids) == 1:
                # Single site — full detail view
                sel_id = selected_ids[0]
                _site_extra_charts(sel_id, "sec_extra", period=site_period)
                st.markdown("---")
                _site_detail(sel_id, "sec", period=site_period)
                st.markdown("---")
                _peak_hours_heatmap(site_filter=sel_id, key_prefix=f"site_{sel_id}")
            else:
                # Multiple sites — show filtered heatmap table + KPIs
                multi_df = sec_df[sec_df["site_id"].isin(selected_ids)]
                _kpis(multi_df)
                st.markdown("---")
                multi_sorted = multi_df.sort_values("energy_pct", ascending=False, na_position="last")
                label = "All Sites" if _show_all else f"{len(selected_ids)} Selected Sites"
                _site_table(multi_sorted, f"{sec_sel} — {label}")
                st.markdown("---")
                _top15_charts(multi_df, key_prefix=f"multi_{sec_sel}")
                # Individual site details in expanders
                if not _show_all and len(selected_ids) <= 5:
                    for sid in selected_ids:
                        with st.expander(f"📍 {sid}", expanded=True):
                            _site_extra_charts(sid, f"m_{sid}", period=site_period)
                            st.markdown("---")
                            _site_detail(sid, f"m_{sid}", period=site_period)
        else:
            st.info(f"No sites in {sec_sel}")

    else:
        # Company selected
        comp_df = sec_df[sec_df[comp_col] == sec_tab_sel] if comp_col else sec_df
        if comp_df.empty:
            st.warning(f"No data for **{sec_tab_sel}** in selected date range ({str_from} → {str_to}).")
            st.stop()
        _kpis(comp_df)
        st.markdown("---")
        comp_sorted = comp_df.sort_values("energy_pct", ascending=False, na_position="last")
        _site_table(comp_sorted, f"{sec_tab_sel} — {len(comp_df)} sites")
        st.markdown("---")
        _type_comparison(comp_df, key_prefix=f"comp_{sec_tab_sel}")
        st.markdown("---")
        st.markdown(f"## 📊 Site Rankings — {sec_tab_sel}")
        _top15_charts(comp_df, key_prefix=f"comp_{sec_tab_sel}")
        st.markdown("---")
        st.markdown(f"## 🔗 Sales-Mapped — {sec_tab_sel}")
        _mapped_unmapped(comp_df, key_prefix=f"comp_{sec_tab_sel}")
        st.markdown("---")
        _operations_section(sector_filter=_sec_filter, key_prefix=f"comp_{sec_tab_sel}")
        st.markdown("---")
        _peak_hours_heatmap(sector_filter=_sec_filter, key_prefix=f"comp_{sec_tab_sel}")
        st.markdown("---")
        _predictions_section(comp_df, sector_filter=_sec_filter, key_prefix=f"comp_{sec_tab_sel}")


# ═══════════════════════════════════════════════════════════════════════════
# COMPANY — kept for backward compat but hidden from tabs
# ═══════════════════════════════════════════════════════════════════════════
if False and "Company" == "never":
    grp_col = "business_sector" if "business_sector" in econ.columns and econ["business_sector"].notna().any() else "sector_id"
    sectors = sorted(econ[grp_col].dropna().unique())
    if not sectors:
        st.info("No sector data.")
        st.stop()
    sec_sel = ui.tabs(options=sectors, default_value=sectors[0], key="v2_csec")
    sec_df = econ[econ[grp_col] == sec_sel]

    comp_col = "company" if "company" in sec_df.columns and sec_df["company"].notna().any() else None
    if not comp_col:
        st.info(f"No company data for {sec_sel}. Upload new Blackout Excel files with Company column.")
        _site_table(sec_df.sort_values("energy_pct", ascending=False, na_position="last"),
                    f"{sec_sel} — {len(sec_df)} sites")
    else:
        companies = sorted(sec_df[comp_col].dropna().unique())
        comp_sel = ui.tabs(options=companies, default_value=companies[0], key="v2_comp")
        comp_df = sec_df[sec_df[comp_col] == comp_sel].sort_values("energy_pct", ascending=False, na_position="last")

        _kpis(comp_df)
        st.markdown("---")
        _site_table(comp_df, f"{comp_sel} — {len(comp_df)} sites")


# ═══════════════════════════════════════════════════════════════════════════
# SITE — kept for backward compat but hidden from tabs
# ═══════════════════════════════════════════════════════════════════════════
if False and "Site" == "never":
    grp_col = "business_sector" if "business_sector" in econ.columns and econ["business_sector"].notna().any() else "sector_id"
    comp_col = "company" if "company" in econ.columns and econ["company"].notna().any() else None

    c1, c2, c3 = st.columns(3)
    with c1:
        sectors = sorted(econ[grp_col].dropna().unique())
        sec_sel = st.selectbox("Sector", sectors, key="v2_ssec")
    sec_df = econ[econ[grp_col] == sec_sel]

    with c2:
        if comp_col and sec_df[comp_col].notna().any():
            companies = ["All"] + sorted(sec_df[comp_col].dropna().unique())
            comp_sel = st.selectbox("Company", companies, key="v2_scomp")
            if comp_sel != "All":
                sec_df = sec_df[sec_df[comp_col] == comp_sel]
        else:
            st.selectbox("Company", ["All"], key="v2_scomp_na", disabled=True)

    with c3:
        sec_df_sorted = sec_df.sort_values("energy_pct", ascending=False, na_position="last")
        opts = [f"{r['site_id']} — {r['site_name']}" for _, r in sec_df_sorted.iterrows()]
        if opts:
            site_sel = st.selectbox("Site", opts, key="v2_ssite")
            sel_id = site_sel.split(" — ")[0]
        else:
            st.selectbox("Site", ["No sites"], key="v2_ssite_na", disabled=True)
            sel_id = None

    if sel_id:
        _site_detail(sel_id, "site")

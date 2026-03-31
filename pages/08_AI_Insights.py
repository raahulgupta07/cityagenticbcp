"""
Page 8: AI Insights Hub — Summary stats, AI chat, and alerts
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary
from config.settings import SECTORS, ALERTS

st.set_page_config(page_title="AI Insights Hub", page_icon="🤖", layout="wide")
st.title("🤖 AI Insights Hub")

ui.alert(
    title="🧠 AI Insights Hub",
    description="AI-powered analysis using Claude Haiku 4.5 via OpenRouter. Summary tab shows auto-generated insights. Chat tab lets you ask questions — the AI agent has 12 tools to query data, run ML models, and generate forecasts. Alerts tab shows all system warnings.",
    key="alert_ai",
)

# ─── Load Summary Stats ─────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary_stats():
    with get_db() as conn:
        site_count = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        gen_count = conn.execute("SELECT COUNT(*) FROM generators WHERE is_active = 1").fetchone()[0]
        latest_date = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()[0]

        buffer_stats = pd.read_sql_query("""
            SELECT s.sector_id,
                   COUNT(DISTINCT dss.site_id) as sites,
                   ROUND(AVG(dss.days_of_buffer), 1) as avg_buffer,
                   ROUND(MIN(dss.days_of_buffer), 1) as min_buffer,
                   SUM(CASE WHEN dss.days_of_buffer < ? THEN 1 ELSE 0 END) as critical_sites,
                   ROUND(SUM(dss.total_daily_used), 0) as total_fuel_used,
                   ROUND(AVG(dss.blackout_hr), 1) as avg_blackout
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT MAX(d2.date) FROM daily_site_summary d2
                              WHERE d2.site_id = dss.site_id)
            GROUP BY s.sector_id
            ORDER BY s.sector_id
        """, conn, params=(ALERTS["buffer_critical_days"],))

        fuel_stats = pd.read_sql_query("""
            SELECT sector_id,
                   ROUND(AVG(price_per_liter), 0) as avg_price,
                   ROUND(MAX(price_per_liter), 0) as max_price,
                   COUNT(*) as purchases
            FROM fuel_purchases
            WHERE date >= (SELECT MAX(date) FROM fuel_purchases)
            GROUP BY sector_id
        """, conn)

        alerts_df = pd.read_sql_query("""
            SELECT id, alert_type, severity, site_id, sector_id,
                   message, is_acknowledged, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 100
        """, conn)

    return site_count, gen_count, latest_date, buffer_stats, fuel_stats, alerts_df

site_count, gen_count, latest_date, buffer_stats, fuel_stats, alerts_df = load_summary_stats()

# ─── Page-level AI Summary ───────────────────────────────────────────────────
kpi_dict = {
    "total_sites": site_count,
    "active_generators": gen_count,
    "latest_date": latest_date,
    "total_alerts": len(alerts_df),
    "unacknowledged_alerts": int(len(alerts_df[alerts_df["is_acknowledged"] == 0])) if not alerts_df.empty else 0,
}
render_page_summary("AI Insights Hub", kpi_dict)

# ─── Tabs ────────────────────────────────────────────────────────────────────
selected = ui.tabs(
    options=["📊 Summary", "💬 AI Chat", "🚨 Alerts"],
    default_value="📊 Summary",
    key="ai_tabs",
)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: Summary Insights
# ═══════════════════════════════════════════════════════════════════════════
if selected == "📊 Summary":
    st.markdown("### System Overview")
    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card(
            title="Total Sites",
            content=str(site_count),
            key="metric_total_sites",
        )
    with c2:
        ui.metric_card(
            title="Active Generators",
            content=str(gen_count),
            key="metric_active_gens",
        )
    with c3:
        ui.metric_card(
            title="Latest Data Date",
            content=str(latest_date or "No data"),
            key="metric_latest_date",
        )

    st.markdown("---")

    # Buffer insights
    st.markdown("### Fuel Buffer Insights by Sector")
    if not buffer_stats.empty:
        for _, row in buffer_stats.iterrows():
            sector_name = SECTORS.get(row["sector_id"], {}).get("name", row["sector_id"])
            buf = row["avg_buffer"] if pd.notna(row["avg_buffer"]) else 0
            min_buf = row["min_buffer"] if pd.notna(row["min_buffer"]) else 0
            crit = int(row["critical_sites"]) if pd.notna(row["critical_sites"]) else 0
            fuel = row["total_fuel_used"] if pd.notna(row["total_fuel_used"]) else 0
            bo = row["avg_blackout"] if pd.notna(row["avg_blackout"]) else 0

            buf_status = "CRITICAL" if buf < 3 else "WARNING" if buf < 7 else "HEALTHY"
            status_icon = "🔴" if buf_status == "CRITICAL" else "🟡" if buf_status == "WARNING" else "🟢"

            st.markdown(f"""
            **{status_icon} {sector_name} ({row['sector_id']})**
            - {int(row['sites'])} sites reporting | Avg buffer: **{buf:.1f} days** | Min buffer: **{min_buf:.1f} days**
            - Critical sites (<{ALERTS['buffer_critical_days']} days): **{crit}**
            - Total fuel consumed: **{fuel:,.0f} L** | Avg blackout: **{bo:.1f} hr**
            """)

        render_insight_panel(
            "Fuel buffer insights across all sectors",
            buffer_stats,
            "buffer_insights_summary",
        )
    else:
        st.info("No buffer data available.")

    st.markdown("---")

    # Fuel price insights
    st.markdown("### Fuel Price Insights")
    if not fuel_stats.empty:
        for _, row in fuel_stats.iterrows():
            sector_name = SECTORS.get(row["sector_id"], {}).get("name", row["sector_id"])
            avg_p = row["avg_price"] if pd.notna(row["avg_price"]) else 0
            max_p = row["max_price"] if pd.notna(row["max_price"]) else 0
            st.markdown(
                f"- **{sector_name}**: Avg price **{avg_p:,.0f} MMK/L** | "
                f"Max **{max_p:,.0f} MMK/L** | {int(row['purchases'])} purchases (latest date)"
            )

        render_insight_panel(
            "Fuel price insights across all sectors",
            fuel_stats,
            "fuel_price_insights_summary",
        )
    else:
        st.info("No fuel purchase data available.")

    st.markdown("---")

    # Key recommendations
    st.markdown("### Key Recommendations")
    if not buffer_stats.empty:
        total_crit = buffer_stats["critical_sites"].sum()
        if total_crit > 0:
            st.warning(
                f"**{int(total_crit)} sites** are below the critical buffer threshold "
                f"of {ALERTS['buffer_critical_days']} days. Immediate fuel resupply recommended."
            )
        min_buf_sector = buffer_stats.loc[buffer_stats["avg_buffer"].idxmin()]
        st.info(
            f"**{min_buf_sector['sector_id']}** has the lowest average buffer at "
            f"**{min_buf_sector['avg_buffer']:.1f} days**. Prioritize fuel allocation here."
        )
    else:
        st.info("Load data to see recommendations.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: AI Chat
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "💬 AI Chat":
    from utils.llm_client import is_llm_available, get_active_model
    from agents.chat_agent import chat

    st.markdown("### AI-Powered BCP Assistant")

    # Status
    if is_llm_available():
        st.success(f"AI Agent connected — Model: `{get_active_model()}`")
    else:
        st.warning("No API key configured. Using rule-based fallback. Set `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY` for full AI.")

    # Example questions
    st.markdown("**Try asking:**")
    example_cols = st.columns(3)
    examples = [
        "Which sites have less than 3 days of fuel?",
        "Compare Denko vs Moon Sun prices",
        "What are the BCP scores for CMHL sector?",
        "Forecast fuel prices for next week",
        "Which generators are inefficient?",
        "Give me a sector summary",
    ]
    for i, ex in enumerate(examples):
        with example_cols[i % 3]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state["ai_chat_input"] = ex

    st.markdown("---")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["content"])
        else:
            st.chat_message("assistant").markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask about your BCP data...")

    if "ai_chat_input" in st.session_state and st.session_state["ai_chat_input"]:
        user_input = st.session_state.pop("ai_chat_input")

    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        st.chat_message("user").markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = chat(user_input, st.session_state["chat_history"][:-1])

            if result["error"]:
                st.error(f"Error: {result['error']}")
                response_text = f"Sorry, I encountered an error: {result['error']}"
            else:
                response_text = result["response"] or "I couldn't generate a response."

            st.markdown(response_text)

            if result["tool_calls"]:
                with st.expander(f"Tools used ({len(result['tool_calls'])})"):
                    for tc in result["tool_calls"]:
                        st.caption(f"**{tc['tool']}** — {tc['result_preview'][:100]}...")

        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: Alerts
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "🚨 Alerts":
    st.markdown("### System Alerts")

    if alerts_df.empty:
        st.info("No alerts recorded. Alerts will appear here when buffer, price, or blackout thresholds are breached.")
    else:
        # Summary counts
        unacked = alerts_df[alerts_df["is_acknowledged"] == 0]
        crit_count = len(alerts_df[alerts_df["severity"] == "CRITICAL"])
        warn_count = len(alerts_df[alerts_df["severity"] == "WARNING"])

        c1, c2, c3 = st.columns(3)
        with c1:
            ui.metric_card(
                title="Total Alerts",
                content=str(len(alerts_df)),
                key="metric_total_alerts",
            )
        with c2:
            ui.metric_card(
                title="Unacknowledged",
                content=str(len(unacked)),
                key="metric_unacked_alerts",
            )
        with c3:
            ui.metric_card(
                title="Critical",
                content=str(crit_count),
                key="metric_critical_alerts",
            )

        # Alert severity badges
        badge_list = []
        if crit_count > 0:
            badge_list.append((f"CRITICAL: {crit_count}", "destructive"))
        if warn_count > 0:
            badge_list.append((f"WARNING: {warn_count}", "outline"))
        info_count = len(alerts_df) - crit_count - warn_count
        if info_count > 0:
            badge_list.append((f"INFO: {info_count}", "default"))
        if badge_list:
            ui.badges(badge_list=badge_list, key="badges_alert_severity")

        st.markdown("---")

        # Filter
        severity_filter = st.multiselect(
            "Filter by Severity",
            alerts_df["severity"].unique().tolist(),
            default=alerts_df["severity"].unique().tolist(),
        )
        filtered = alerts_df[alerts_df["severity"].isin(severity_filter)]

        display_df = filtered[["created_at", "alert_type", "severity", "sector_id",
                                "site_id", "message", "is_acknowledged"]].copy()
        display_df.columns = ["Time", "Type", "Severity", "Sector", "Site",
                               "Message", "Ack"]
        display_df["Ack"] = display_df["Ack"].apply(lambda x: "Yes" if x else "No")

        render_smart_table(
            display_df, title="Alert Log",
            severity_col="Severity",
        )
        render_insight_panel(
            "System alerts summary — highlighting critical patterns and trends",
            display_df,
            "alerts_ai_summary",
        )


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

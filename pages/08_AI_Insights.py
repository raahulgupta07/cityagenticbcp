"""
Page 8: AI Insights Hub — Modern chat UI + summary + alerts
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary, finish_page
from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
from config.settings import SECTORS, ALERTS

st.set_page_config(page_title="AI Insights Hub", page_icon="🧠", layout="wide")
require_login()
render_sidebar_user()

# ─── Custom CSS for modern chat ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Chat container */
    .chat-container {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        margin: 16px 0;
        max-height: 500px;
        overflow-y: auto;
    }
    .chat-msg {
        display: flex; gap: 12px; margin-bottom: 16px;
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .chat-avatar {
        width: 36px; height: 36px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px; flex-shrink: 0;
    }
    .chat-avatar-user { background: #3b82f6; color: white; }
    .chat-avatar-ai { background: linear-gradient(135deg, #0f172a, #1e3a5f); color: white; }
    .chat-bubble {
        padding: 12px 16px; border-radius: 12px; font-size: 14px;
        line-height: 1.6; max-width: 85%;
    }
    .chat-bubble-user { background: #3b82f6; color: white; border-bottom-right-radius: 4px; margin-left: auto; }
    .chat-bubble-ai { background: white; color: #1e293b; border: 1px solid #e2e8f0; border-bottom-left-radius: 4px; }
    .chat-tools { font-size: 11px; color: #94a3b8; margin-top: 6px; }

    /* Suggested questions */
    .suggestions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
</style>
""", unsafe_allow_html=True)

render_page_header("🧠", "AI Insights Hub", "AI-powered analysis, chat agent, and system alerts")

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_summary():
    with get_db() as conn:
        sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        gens = conn.execute("SELECT COUNT(*) FROM generators WHERE is_active = 1").fetchone()[0]
        latest = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()[0]

        buffer_stats = pd.read_sql_query("""
            SELECT s.sector_id,
                   COUNT(DISTINCT dss.site_id) as sites,
                   ROUND(AVG(dss.days_of_buffer), 1) as avg_buffer,
                   SUM(CASE WHEN dss.days_of_buffer < 3 THEN 1 ELSE 0 END) as critical
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT MAX(d2.date) FROM daily_site_summary d2 WHERE d2.site_id = dss.site_id)
            GROUP BY s.sector_id
        """, conn)

        alerts_df = pd.read_sql_query("""
            SELECT id, alert_type, severity, site_id, sector_id, message, is_acknowledged, created_at
            FROM alerts ORDER BY created_at DESC LIMIT 100
        """, conn)

    return sites, gens, latest, buffer_stats, alerts_df

sites, gens, latest, buffer_stats, alerts_df = load_summary()

# ─── Tabs ────────────────────────────────────────────────────────────────────
selected = ui.tabs(
    options=["💬 AI Chat", "📊 Summary", "🚨 Alerts"],
    default_value="💬 AI Chat",
    key="ai_tabs",
)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: AI Chat
# ═══════════════════════════════════════════════════════════════════════════
if selected == "💬 AI Chat":
    from utils.llm_client import is_llm_available, get_active_model
    from agents.chat_agent import chat

    # Status
    if is_llm_available():
        st.caption(f"🟢 Connected to `{get_active_model()}` — Ask anything about your BCP data")
    else:
        st.caption("🟡 No API key — using rule-based responses. Set `OPENROUTER_API_KEY` for full AI.")

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Suggested questions (show only when no history)
    if not st.session_state["chat_history"]:
        st.markdown("#### Ask me anything about your BCP data:")
        suggestions = [
            "Which sites have less than 3 days of fuel?",
            "Compare fuel efficiency across all sectors",
            "What will diesel prices be next week?",
            "Give me a BCP risk summary",
            "Which generators are underperforming?",
            "What are the top 5 most urgent sites?",
        ]
        cols = st.columns(3)
        for i, q in enumerate(suggestions):
            with cols[i % 3]:
                if st.button(q, key=f"suggest_{i}", use_container_width=True):
                    st.session_state["_pending_question"] = q
                    st.rerun()

    # Display chat history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🛡️"):
            st.markdown(msg["content"])
            if msg.get("tools"):
                with st.expander(f"🔧 {len(msg['tools'])} tools used"):
                    for t in msg["tools"]:
                        st.caption(f"**{t['tool']}** → {t['result_preview'][:80]}...")

    # Chat input
    user_input = st.chat_input("Ask about fuel, generators, blackouts, prices, BCP scores...")

    # Check for suggestion click
    if "_pending_question" in st.session_state:
        user_input = st.session_state.pop("_pending_question")

    if user_input:
        # Add user message
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # AI response
        with st.chat_message("assistant", avatar="🛡️"):
            with st.spinner("🧠 Thinking..."):
                result = chat(user_input, st.session_state["chat_history"][:-1])

            if result["error"]:
                st.error(f"Error: {result['error']}")
                response = f"Sorry, I encountered an error: {result['error']}"
            else:
                response = result["response"] or "I couldn't generate a response."

            st.markdown(response)

            if result["tool_calls"]:
                with st.expander(f"🔧 {len(result['tool_calls'])} tools used"):
                    for tc in result["tool_calls"]:
                        st.caption(f"**{tc['tool']}** → {tc['result_preview'][:80]}...")

        st.session_state["chat_history"].append({
            "role": "assistant", "content": response,
            "tools": result.get("tool_calls", []),
        })

    # Clear chat
    if st.session_state["chat_history"]:
        if st.button("🗑️ Clear Chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: Summary
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "📊 Summary":
    render_page_summary("AI Insights", {
        "sites": sites, "generators": gens, "latest_date": latest,
        "total_alerts": len(alerts_df),
    })

    c1, c2, c3 = st.columns(3)
    with c1:
        ui.metric_card(title="Sites", content=str(sites), description=f"{gens} generators", key="mc_ai_sites")
    with c2:
        ui.metric_card(title="Data Through", content=str(latest or "N/A"), description="latest date", key="mc_ai_date")
    with c3:
        unacked = len(alerts_df[alerts_df["is_acknowledged"] == 0]) if not alerts_df.empty else 0
        ui.metric_card(title="Active Alerts", content=str(unacked), description="unacknowledged", key="mc_ai_alerts")

    if not buffer_stats.empty:
        st.markdown("#### Sector Status")
        for _, row in buffer_stats.iterrows():
            sector_name = SECTORS.get(row["sector_id"], {}).get("name", row["sector_id"])
            buf = row["avg_buffer"] if pd.notna(row["avg_buffer"]) else 0
            crit = int(row["critical"]) if pd.notna(row["critical"]) else 0
            icon = "🔴" if buf < 3 else "🟡" if buf < 7 else "🟢"
            st.markdown(f"{icon} **{sector_name}** — {int(row['sites'])} sites | Buffer: **{buf:.1f} days** | Critical: **{crit}**")

        render_insight_panel("Sector buffer status overview", buffer_stats, "ai_sector_status")

    finish_page()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: Alerts
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "🚨 Alerts":
    st.markdown("### Active Alerts")

    if alerts_df.empty:
        st.info("No alerts. Alerts are generated when you upload data.")
    else:
        unacked = alerts_df[alerts_df["is_acknowledged"] == 0]
        c1, c2, c3 = st.columns(3)
        with c1:
            crit = len(unacked[unacked["severity"] == "CRITICAL"])
            ui.metric_card(title="🔴 Critical", content=str(crit), description="immediate action", key="mc_alert_c")
        with c2:
            warn = len(unacked[unacked["severity"] == "WARNING"])
            ui.metric_card(title="🟡 Warning", content=str(warn), description="attention needed", key="mc_alert_w")
        with c3:
            info_c = len(unacked[unacked["severity"] == "INFO"])
            ui.metric_card(title="🔵 Info", content=str(info_c), description="informational", key="mc_alert_i")

        # Filter
        sev_filter = st.multiselect("Filter", ["CRITICAL", "WARNING", "INFO"],
                                     default=["CRITICAL", "WARNING"], key="alert_filter")
        filtered = alerts_df[alerts_df["severity"].isin(sev_filter)]

        if not filtered.empty:
            display = filtered[["severity", "site_id", "sector_id", "message", "created_at"]].head(30).copy()
            display.columns = ["Severity", "Site", "Sector", "Message", "Time"]
            render_smart_table(display, title="Alerts", severity_col="Severity")

        render_insight_panel("Active system alerts", filtered.head(20) if not filtered.empty else {"status": "no alerts"}, "ai_alerts")
        finish_page()

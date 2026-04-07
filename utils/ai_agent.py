"""
Agentic AI Insights — generates contextual analysis using Gemini 3.1 Flash Lite.
Cached in DB to avoid repeated API calls for same data.
"""
from __future__ import annotations
import os
import json
import hashlib
import requests
from datetime import datetime
from utils.database import get_db
from config.settings import AGENT_CONFIG


def _get_cache_key(context: str, prompt_type: str) -> str:
    """Generate a hash key for caching."""
    raw = f"{prompt_type}:{context}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(cache_key: str) -> str | None:
    """Check if insight is cached and fresh (< 6 hours)."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT content, created_at FROM ai_insights_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            if row:
                created = datetime.strptime(row[1][:19], "%Y-%m-%d %H:%M:%S")
                age_hours = (datetime.now() - created).total_seconds() / 3600
                if age_hours < 6:
                    return row[0]
    except Exception:
        pass
    return None


def _set_cache(cache_key: str, content: str, prompt_type: str):
    """Store insight in cache."""
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_insights_cache (cache_key, page_key, context, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (cache_key, prompt_type, prompt_type, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
    except Exception:
        pass


def _call_llm(prompt: str, max_tokens: int = 1024) -> str:
    """Call Gemini via OpenRouter."""
    api_key = os.environ.get(AGENT_CONFIG["api_key_env"], "")
    if not api_key:
        return "⚠️ No API key configured. Set OPENROUTER_API_KEY environment variable."

    model = AGENT_CONFIG["models"].get("insight", "google/gemini-3.1-flash-lite-preview")

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            return f"⚠️ API error: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"⚠️ Connection error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API — call these from the dashboard
# ═══════════════════════════════════════════════════════════════════════════

def morning_briefing(data: dict, force_refresh: bool = False) -> str:
    """Generate morning briefing from KPI data.

    data = {
        "date_range": "2026-03-25 → 2026-04-02",
        "total_sites": 60,
        "buffer_days": 7.1,
        "critical_sites": 4,
        "warning_sites": 13,
        "safe_sites": 22,
        "total_tank": 118684,
        "daily_burn": 6541,
        "diesel_cost_daily": "46.3M",
        "fuel_price_trend": "rising (5,960 → 7,085)",
        "worst_sites": "CP-CCMDY (0.9d), CFC-SBFTY (2.1d), CMHL-CMATMTN (1.4d)",
        "anomalies": 3,
        "sectors": "CFC: 1.9d buffer, CMHL: 5.8d, CP: 12.3d, PG: 14.2d",
    }
    """
    context = json.dumps(data, default=str)
    cache_key = _get_cache_key(context, "morning_briefing")

    if not force_refresh:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    prompt = f"""You are a BCP (Business Continuity Planning) operations analyst for City Holdings Myanmar.
You monitor 60+ retail/F&B stores that use diesel generators during power blackouts.

Analyze this data and give a morning briefing. Use EXACTLY this format:

🔴 URGENT
• [specific site name + specific number + specific action]
• [max 3 items]

🟡 WATCH
• [trend + impact + what to monitor]
• [max 3 items]

🟢 POSITIVE
• [good news with specific numbers]
• [max 2 items]

Rules:
- Use actual site names and numbers from the data
- Each bullet = 1-2 lines max
- Recommend specific actions (send fuel, reduce hours, check generator)
- Mention costs in MMK where relevant
- Be direct, no fluff

DATA:
{context}"""

    result = _call_llm(prompt, max_tokens=800)
    _set_cache(cache_key, result, "morning_briefing")
    return result


def kpi_insight(data: dict, force_refresh: bool = False) -> str:
    """Generate insight for KPI cards.

    data = {"buffer": 7.1, "tank": 118684, "burn": 6541, "critical": 4, "warning": 13, ...}
    """
    context = json.dumps(data, default=str)
    cache_key = _get_cache_key(context, "kpi_insight")

    if not force_refresh:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    prompt = f"""You are a BCP analyst. In exactly 3 short sentences, explain what these KPIs mean for operations.
Focus on: Is the situation safe or dangerous? What's hidden behind the averages? What action is needed?

KPI DATA: {context}

Write 3 sentences. Be specific with numbers. No headers or bullets."""

    result = _call_llm(prompt, max_tokens=300)
    _set_cache(cache_key, result, "kpi_insight")
    return result


def table_insight(table_summary: str, table_type: str = "sector", force_refresh: bool = False) -> str:
    """Generate insight for heatmap table data.

    table_summary = "CFC: 2 sites, buffer 1.9d, blackout 8.9hr | CMHL: 31 sites, buffer 5.8d..."
    """
    cache_key = _get_cache_key(table_summary, f"table_{table_type}")

    if not force_refresh:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    prompt = f"""You are a BCP analyst looking at a {table_type} summary table.
In 3 short sentences: Which {table_type} needs attention? Why? What should the manager do?

TABLE DATA: {table_summary}

Be specific with names and numbers. No headers or bullets. 3 sentences only."""

    result = _call_llm(prompt, max_tokens=300)
    _set_cache(cache_key, result, f"table_{table_type}")
    return result


def site_insight(site_data: dict, force_refresh: bool = False) -> str:
    """Generate insight for a specific site.

    site_data = {"site_id": "CMHL-CM50BTH", "buffer": 5.5, "tank": 1463, "burn": 158, ...}
    """
    context = json.dumps(site_data, default=str)
    cache_key = _get_cache_key(context, "site_insight")

    if not force_refresh:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    prompt = f"""You are a BCP analyst reviewing one specific site.
Give a 4-line analysis:
Line 1: Buffer status — is it safe, warning, or critical? Why?
Line 2: Generator efficiency — normal or abnormal? Any waste?
Line 3: Cost vs sales — is this site profitable enough to keep open?
Line 4: Recommendation — specific action for this site.

SITE DATA: {context}

Be specific. Use numbers. 4 lines only."""

    result = _call_llm(prompt, max_tokens=400)
    _set_cache(cache_key, result, "site_insight")
    return result


def render_insight_box(content: str, title: str = "🧠 AI Insight"):
    """Render an insight box in Streamlit."""
    import streamlit as st
    st.markdown(f"""
    <div style="background:#0f172a;border-left:4px solid #00ff41;border-radius:0 10px 10px 0;
                padding:14px 18px;margin:12px 0;color:#e0e0e0;font-size:13px;line-height:1.7">
        <div style="font-weight:700;color:#00ff41;margin-bottom:6px;font-size:14px">{title}</div>
        <div style="white-space:pre-line">{content}</div>
    </div>""", unsafe_allow_html=True)

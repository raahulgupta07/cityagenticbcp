"""
AI Insights — Persisted in database. Shows timestamp. Refresh button replaces old.
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
from utils.llm_client import call_llm_simple, is_llm_available
from utils.database import get_db


# ─── DB Cache Operations ────────────────────────────────────────────────────

def _get_cached(key):
    """Get insight from DB. Returns (text, generated_at) or (None, None)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT insight_text, generated_at FROM ai_insights_cache WHERE insight_key = ?",
            (key,)
        ).fetchone()
    if row:
        return row["insight_text"], row["generated_at"]
    return None, None


def _save_cache(key, insight_type, text, data_date=None):
    """Save insight to DB."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO ai_insights_cache (insight_key, insight_type, insight_text, data_date, generated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(insight_key) DO UPDATE SET
                insight_text = excluded.insight_text,
                data_date = excluded.data_date,
                generated_at = datetime('now')
        """, (key, insight_type, text, data_date))


def _delete_cache(key):
    """Delete a cached insight."""
    with get_db() as conn:
        conn.execute("DELETE FROM ai_insights_cache WHERE insight_key = ?", (key,))


def _get_last_upload_date():
    """Get the latest data upload timestamp."""
    with get_db() as conn:
        row = conn.execute("SELECT MAX(uploaded_at) as d FROM upload_history").fetchone()
        return row["d"] if row and row["d"] else None


def _get_latest_data_date():
    """Get the latest date in the data."""
    with get_db() as conn:
        row = conn.execute("SELECT MAX(date) as d FROM daily_site_summary").fetchone()
        return row["d"] if row and row["d"] else None


# ─── Pending Queue ───────────────────────────────────────────────────────

def _ensure_pending():
    if "_pending_insights" not in st.session_state:
        st.session_state["_pending_insights"] = []

_ensure_pending()


# ─── LLM Call ────────────────────────────────────────────────────────────

def _generate(prompt, max_tokens=500):
    if not is_llm_available():
        return None
    response, error = call_llm_simple(prompt, max_tokens=max_tokens)
    return response if not error else None


def _prepare_data(data, max_rows=50):
    """Convert data to detailed string — send ALL numbers to LLM."""
    if isinstance(data, pd.DataFrame):
        if data.empty:
            return "No data available"
        info = f"DataFrame: {len(data)} rows x {len(data.columns)} columns\n"
        info += f"Columns: {', '.join(data.columns)}\n\n"
        numeric = data.select_dtypes(include="number")
        if not numeric.empty:
            info += "Statistics:\n"
            for col in numeric.columns:
                info += f"  {col}: min={numeric[col].min():.2f}, max={numeric[col].max():.2f}, avg={numeric[col].mean():.2f}, sum={numeric[col].sum():.2f}\n"
            info += "\n"
        rows_to_send = min(max_rows, len(data))
        info += f"Data ({rows_to_send} rows):\n"
        info += data.head(rows_to_send).to_string(index=False)
        return info
    elif isinstance(data, dict):
        return json.dumps(data, default=str, indent=2)
    return str(data)


# ─── Public API ──────────────────────────────────────────────────────────

def render_data_timestamp():
    """Show when data was last uploaded and latest data date."""
    upload_date = _get_last_upload_date()
    data_date = _get_latest_data_date()
    parts = []
    if data_date:
        parts.append(f"Data through: **{data_date}**")
    if upload_date:
        parts.append(f"Last upload: **{upload_date[:16]}**")
    if parts:
        st.caption(" | ".join(parts))


def render_insight_panel(context, data, key):
    """Show DB-cached insight or queue for generation."""
    cache_key = f"ai_{key}"
    text, generated_at = _get_cached(cache_key)

    if text:
        _show_insight(text, generated_at)
    else:
        _ensure_pending()
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "context": context,
            "data": data, "type": "insight",
        })


def render_page_summary(page_name, kpi_data, charts_data=None):
    cache_key = f"summary_{page_name}"
    text, generated_at = _get_cached(cache_key)

    if text:
        _show_summary(text, generated_at)
    else:
        _ensure_pending()
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "kpi_data": kpi_data,
            "charts_data": charts_data, "page_name": page_name,
            "type": "summary",
        })


def render_forecast_insight(model_name, forecast_data, key):
    cache_key = f"fc_{key}"
    text, generated_at = _get_cached(cache_key)

    if text:
        _show_forecast(text, generated_at)
    else:
        _ensure_pending()
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "model_name": model_name,
            "forecast_data": forecast_data, "type": "forecast",
        })


def finish_page():
    """
    Call at END of every page.
    Shows data timestamp + Generate button + Refresh button.
    """
    _ensure_pending()
    pending = [p for p in st.session_state.get("_pending_insights", [])
               if _get_cached(p["cache_key"])[0] is None]
    st.session_state["_pending_insights"] = []

    st.markdown("---")

    # Data timestamp
    render_data_timestamp()

    if not is_llm_available():
        st.caption("Set OPENROUTER_API_KEY for AI insights.")
        return

    col1, col2 = st.columns(2)

    # Generate new insights (for uncached) — streams one by one
    with col1:
        if pending:
            if st.button(f"🧠 Generate AI Analysis ({len(pending)} sections)", key="btn_ai_gen",
                         type="primary", use_container_width=True):
                _run_generation_streaming(pending)
        else:
            st.success("✅ All AI insights are up to date.")

    # Refresh ALL insights (delete old, regenerate)
    with col2:
        if st.button("🔄 Refresh All Analysis (new data)", key="btn_ai_refresh",
                     use_container_width=True):
            with get_db() as conn:
                conn.execute("DELETE FROM ai_insights_cache")
            # Clear only insight-related keys, keep auth/user session
            keys_to_remove = [k for k in st.session_state if k.startswith(("ai_", "summary_", "fc_", "_pending"))]
            for k in keys_to_remove:
                del st.session_state[k]
            st.rerun()


def _run_generation_streaming(pending):
    """Generate insights one-by-one, showing each result as it completes."""
    data_date = _get_latest_data_date()
    completed = 0

    for i, item in enumerate(pending):
        label = item.get("context", item.get("page_name", ""))[:60]

        with st.status(f"🧠 Analyzing {i+1}/{len(pending)}: {label}...", expanded=True) as status:
            try:
                if item["type"] == "insight":
                    result = _gen_deep_insight(item["context"], item["data"])
                elif item["type"] == "summary":
                    result = _gen_deep_summary(item["page_name"], item["kpi_data"], item.get("charts_data"))
                elif item["type"] == "forecast":
                    result = _gen_deep_forecast(item["model_name"], item["forecast_data"])
                else:
                    result = None

                if result:
                    _save_cache(item["cache_key"], item["type"], result, data_date)
                    st.markdown(result)
                    status.update(label=f"✅ {i+1}/{len(pending)}: {label}", state="complete", expanded=False)
                    completed += 1
                else:
                    status.update(label=f"⚠️ {i+1}/{len(pending)}: No result", state="error", expanded=False)
            except Exception as e:
                status.update(label=f"❌ {i+1}/{len(pending)}: Error", state="error", expanded=False)

    if completed > 0:
        st.success(f"✅ {completed} insights generated! Click below to see them in place.")
        if st.button("🔄 Refresh Page", key="btn_refresh_after"):
            st.rerun()


# ─── Deep Analysis Generators ───────────────────────────────────────────

def _gen_deep_insight(context, data):
    data_str = _prepare_data(data)
    return _generate(f"""You are a senior BCP analyst. Analyze this data deeply.

CONTEXT: {context}

FULL DATA:
{data_str}

Provide analysis in this format:

**Key Finding:** Most important pattern. Compare highs vs lows. Name specific sites and numbers.

**Risk Assessment:** What's dangerous? Which sites/generators at risk? Quantify with numbers.

**Root Cause:** Why might this be happening?

**Action Required:** Exactly what should be done, by whom, by when? Be specific — "Deliver 500L to CMZWN by tomorrow" not "increase fuel."

Use actual numbers from the data. Name sites. Be direct.""", 500)


def _gen_deep_summary(page_name, kpi_data, charts_data):
    combined = _prepare_data(kpi_data)
    if charts_data is not None and isinstance(charts_data, pd.DataFrame):
        combined += "\n\nAdditional data:\n" + _prepare_data(charts_data, 20)

    return _generate(f"""Write a 3-sentence executive summary for {page_name}.

DATA:
{combined}

Sentence 1: 🟢 🟡 or 🔴 status + KEY number.
Sentence 2: Biggest RISK with site names and numbers.
Sentence 3: ONE action leadership should take today.""", 200)


def _gen_deep_forecast(model_name, forecast_data):
    data_str = _prepare_data(forecast_data)
    return _generate(f"""Analyze this {model_name} forecast for managers.

FORECAST DATA:
{data_str}

**What's happening:** Direction, exact % change, today vs 7 days.
**Business impact:** How much more/less will fuel cost in MMK?
**Action:** Buy now or wait? Switch supplier? Be specific with timing.""", 300)


# ─── Display Helpers ─────────────────────────────────────────────────────

def _show_insight(text, generated_at):
    ts = _format_ts(generated_at)
    st.markdown(f"""<div style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:14px 18px;
        border-radius:0 8px 8px 0;margin:8px 0 16px 0;font-size:14px;color:#1e3a5f;line-height:1.6">
        <strong>💡 Deep Insight</strong> <span style="font-size:11px;color:#94a3b8">Generated: {ts}</span><br>{text}</div>""",
        unsafe_allow_html=True)

def _show_summary(text, generated_at):
    ts = _format_ts(generated_at)
    st.markdown(f"""<div style="background:linear-gradient(135deg,#eff6ff,#f0fdf4);border:1px solid #bfdbfe;
        border-radius:10px;padding:18px;margin-bottom:16px;font-size:15px;line-height:1.6">
        <strong>🧠 Executive Summary</strong> <span style="font-size:11px;color:#94a3b8">Generated: {ts}</span><br>{text}</div>""",
        unsafe_allow_html=True)

def _show_forecast(text, generated_at):
    ts = _format_ts(generated_at)
    st.markdown(f"""<div style="background:#fefce8;border-left:4px solid #eab308;padding:14px 18px;
        border-radius:0 8px 8px 0;margin:8px 0 16px 0;font-size:14px;color:#713f12;line-height:1.6">
        <strong>🔮 Forecast Analysis</strong> <span style="font-size:11px;color:#94a3b8">Generated: {ts}</span><br>{text}</div>""",
        unsafe_allow_html=True)

def _format_ts(ts):
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return ts[:16]

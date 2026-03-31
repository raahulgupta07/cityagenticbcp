"""
AI Insights — Sends FULL chart/table data to LLM for deep analysis.
One button per page generates all insights with actual numbers.
"""
import streamlit as st
import pandas as pd
import json
from utils.llm_client import call_llm_simple, is_llm_available

if "_pending_insights" not in st.session_state:
    st.session_state["_pending_insights"] = []


def _generate(prompt, max_tokens=500):
    if not is_llm_available():
        return None
    response, error = call_llm_simple(prompt, max_tokens=max_tokens)
    return response if not error else None


def _prepare_data(data, max_rows=50):
    """Convert data to detailed string for LLM — send ALL the numbers."""
    if isinstance(data, pd.DataFrame):
        if data.empty:
            return "No data available"
        info = f"DataFrame: {len(data)} rows x {len(data.columns)} columns\n"
        info += f"Columns: {', '.join(data.columns)}\n\n"

        # Send stats for numeric columns
        numeric = data.select_dtypes(include="number")
        if not numeric.empty:
            info += "Statistics:\n"
            for col in numeric.columns:
                info += f"  {col}: min={numeric[col].min():.2f}, max={numeric[col].max():.2f}, avg={numeric[col].mean():.2f}, sum={numeric[col].sum():.2f}\n"
            info += "\n"

        # Send actual rows
        rows_to_send = min(max_rows, len(data))
        info += f"Data ({rows_to_send} rows):\n"
        info += data.head(rows_to_send).to_string(index=False)
        return info

    elif isinstance(data, dict):
        return json.dumps(data, default=str, indent=2)
    else:
        return str(data)


def render_insight_panel(context, data, key):
    """Queue insight with FULL data for deep analysis."""
    cache_key = f"ai_{key}"
    if cache_key in st.session_state:
        _show_insight(st.session_state[cache_key])
    else:
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "context": context,
            "data": data, "type": "insight",
        })


def render_page_summary(page_name, kpi_data, charts_data=None):
    cache_key = f"summary_{page_name}"
    if cache_key in st.session_state:
        _show_summary(st.session_state[cache_key])
    else:
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "kpi_data": kpi_data,
            "charts_data": charts_data, "page_name": page_name,
            "type": "summary",
        })


def render_forecast_insight(model_name, forecast_data, key):
    cache_key = f"fc_{key}"
    if cache_key in st.session_state:
        _show_forecast(st.session_state[cache_key])
    else:
        st.session_state["_pending_insights"].append({
            "cache_key": cache_key, "model_name": model_name,
            "forecast_data": forecast_data, "type": "forecast",
        })


def finish_page():
    """Call at END of every page. Shows one button to generate ALL insights."""
    pending = [p for p in st.session_state.get("_pending_insights", [])
               if p["cache_key"] not in st.session_state]
    st.session_state["_pending_insights"] = []

    if not pending or not is_llm_available():
        return

    st.markdown("---")
    if st.button(f"🧠 Generate Deep AI Analysis ({len(pending)} sections)", key="btn_ai_all",
                 type="primary", use_container_width=True):
        progress = st.progress(0, text="🧠 Analyzing data...")

        for i, item in enumerate(pending):
            progress.progress((i + 1) / len(pending),
                              text=f"🧠 Deep analysis {i+1}/{len(pending)}: {item.get('context', item.get('page_name', ''))[:50]}...")
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
                    st.session_state[item["cache_key"]] = result
            except Exception:
                pass

        progress.empty()
        st.rerun()


# ─── Deep Analysis Generators (send FULL data) ──────────────────────────

def _gen_deep_insight(context, data):
    data_str = _prepare_data(data)

    return _generate(f"""You are a senior BCP analyst. Analyze this data deeply and give actionable insights.

CONTEXT: {context}

FULL DATA:
{data_str}

Provide a DEEP analysis in this format:

**Key Finding:** What is the most important pattern or number? Compare highs vs lows. Name specific sites.

**Risk Assessment:** What's dangerous? Which sites/generators are at risk? Quantify the risk with numbers.

**Root Cause:** Why might this be happening? (fuel delivery delays? generator overuse? price spikes?)

**Action Required:** Exactly what should be done, by whom, and by when? Be specific — "Deliver 500L to CMZWN by tomorrow" not just "increase fuel."

Use actual numbers from the data. Name specific sites. Be direct — this is for managers who need to make decisions NOW.""", 500)


def _gen_deep_summary(page_name, kpi_data, charts_data):
    combined = _prepare_data(kpi_data)
    if charts_data is not None and isinstance(charts_data, pd.DataFrame):
        combined += "\n\nAdditional data:\n" + _prepare_data(charts_data, 20)

    return _generate(f"""Write a 3-sentence executive summary for the {page_name} page.

DATA:
{combined}

Sentence 1: Start with 🟢 🟡 or 🔴 status + the KEY number that matters most.
Sentence 2: The biggest RISK right now with specific site names and numbers.
Sentence 3: The ONE action the leadership team should take today.

Use actual numbers. Name sites. Be specific and direct.""", 200)


def _gen_deep_forecast(model_name, forecast_data):
    data_str = _prepare_data(forecast_data)

    return _generate(f"""Analyze this {model_name} forecast for non-technical managers.

FORECAST DATA:
{data_str}

Provide:
**What's happening:** Price/consumption direction, exact % change, compare today vs 7 days from now.
**Business impact:** How much more/less will fuel cost? Estimate MMK impact across all sites.
**Recommended action:** Buy now or wait? Lock in price? Switch supplier? Be specific with timing.""", 300)


# ─── Display ─────────────────────────────────────────────────────────────

def _show_insight(text):
    st.markdown(f"""<div style="background:#f0f9ff;border-left:4px solid #3b82f6;padding:14px 18px;
        border-radius:0 8px 8px 0;margin:8px 0 16px 0;font-size:14px;color:#1e3a5f;line-height:1.6">
        <strong>💡 Deep Insight:</strong><br>{text}</div>""", unsafe_allow_html=True)

def _show_summary(text):
    st.markdown(f"""<div style="background:linear-gradient(135deg,#eff6ff,#f0fdf4);border:1px solid #bfdbfe;
        border-radius:10px;padding:18px;margin-bottom:16px;font-size:15px;line-height:1.6">
        <strong>🧠 Executive Summary:</strong><br>{text}</div>""", unsafe_allow_html=True)

def _show_forecast(text):
    st.markdown(f"""<div style="background:#fefce8;border-left:4px solid #eab308;padding:14px 18px;
        border-radius:0 8px 8px 0;margin:8px 0 16px 0;font-size:14px;color:#713f12;line-height:1.6">
        <strong>🔮 Forecast Analysis:</strong><br>{text}</div>""", unsafe_allow_html=True)

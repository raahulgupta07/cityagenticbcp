"""
KPI Card with calculation method and data source — transparent analytics.
Every number shows HOW it was calculated and WHERE the data came from.
"""
import streamlit as st
import streamlit_shadcn_ui as ui


def render_kpi(title, value, method, source, key, description=None):
    """
    Render a KPI metric card with calculation transparency.

    Args:
        title: KPI name (e.g., "Avg Buffer Days")
        value: Display value (e.g., "93.2")
        method: How it's calculated (e.g., "Tank Balance ÷ Daily Usage, averaged across all sites")
        source: Data source (e.g., "daily_site_summary table | Data: 2026-03-25 to 2026-03-31")
        key: Unique key for streamlit
        description: Optional extra line below value
    """
    ui.metric_card(title=title, content=str(value),
                   description=description or "", key=key)

    # Hover-style tooltip with calculation + source
    st.markdown(f"""
    <details style="margin:-12px 0 12px 0;font-size:11px;color:#94a3b8">
        <summary style="cursor:pointer;user-select:none">ℹ️ How is this calculated?</summary>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px 12px;margin-top:4px">
            <div><strong>Method:</strong> {method}</div>
            <div><strong>Source:</strong> {source}</div>
        </div>
    </details>
    """, unsafe_allow_html=True)


def render_chart_source(chart_title, method, source, date_range=None):
    """
    Render source info below a chart.
    """
    date_info = f" | Period: {date_range}" if date_range else ""
    st.markdown(f"""
    <div style="font-size:11px;color:#94a3b8;margin:-8px 0 16px 0;padding:6px 12px;
                background:#f8fafc;border-radius:6px;border:1px solid #f1f5f9">
        📊 <strong>{chart_title}</strong> — {method}{date_info}<br>
        📁 Source: {source}
    </div>
    """, unsafe_allow_html=True)

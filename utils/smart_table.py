"""
HTML Smart Tables with severity badges, conditional coloring, and progress bars.
"""
import pandas as pd
import streamlit as st


def render_smart_table(df, title=None, severity_col=None, highlight_cols=None,
                       max_height=500, bar_col=None):
    """
    Render a styled HTML table in Streamlit.

    Args:
        df: DataFrame to render
        title: Optional table title
        severity_col: Column name containing severity values (CRITICAL/WARNING/etc.)
        highlight_cols: Dict of {col_name: {"good": "high"|"low", "thresholds": [warn, crit]}}
        max_height: Max table height in px
        bar_col: Column name to show as progress bar (0-100)
    """
    if df is None or df.empty:
        st.info("No data available")
        return

    rows_html = []
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            style = ""
            content = _format_value(val)

            # Severity badge
            if col == severity_col and val:
                content = _severity_badge(str(val).upper())

            # Threshold coloring
            elif highlight_cols and col in highlight_cols:
                style = _threshold_style(val, highlight_cols[col])

            # Progress bar
            elif col == bar_col and val is not None:
                content = _progress_bar(val)

            cells.append(f'<td style="{style}">{content}</td>')

        rows_html.append(f'<tr>{"".join(cells)}</tr>')

    headers = "".join(f"<th>{col}</th>" for col in df.columns)
    title_html = f'<div class="table-title">{title} <span class="row-count">({len(df)} rows)</span></div>' if title else ""

    html = f"""
    <style>
    .smart-table-wrap {{
        max-height: {max_height}px;
        overflow-y: auto;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
    }}
    .table-title {{
        padding: 10px 16px;
        font-weight: 600;
        font-size: 14px;
        color: #1f2937;
        background: #f9fafb;
        border-bottom: 1px solid #e5e7eb;
    }}
    .row-count {{
        font-weight: 400;
        color: #6b7280;
        font-size: 12px;
    }}
    .smart-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }}
    .smart-table th {{
        position: sticky;
        top: 0;
        background: #f3f4f6;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        color: #374151;
        border-bottom: 2px solid #e5e7eb;
        white-space: nowrap;
    }}
    .smart-table td {{
        padding: 6px 12px;
        border-bottom: 1px solid #f3f4f6;
        color: #374151;
    }}
    .smart-table tr:nth-child(even) {{
        background: #fafbfc;
    }}
    .smart-table tr:hover {{
        background: #eff6ff;
    }}
    .severity-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }}
    .progress-bar-wrap {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .progress-bar {{
        height: 8px;
        border-radius: 4px;
        flex: 1;
        background: #e5e7eb;
    }}
    .progress-bar-fill {{
        height: 100%;
        border-radius: 4px;
    }}
    </style>
    {title_html}
    <div class="smart-table-wrap">
        <table class="smart-table">
            <thead><tr>{headers}</tr></thead>
            <tbody>{"".join(rows_html)}</tbody>
        </table>
    </div>
    """
    st.html(html)


# ─── Helpers ─────────────────────────────────────────────────────────────────

SEVERITY_STYLES = {
    "CRITICAL": {"bg": "#fef2f2", "color": "#dc2626"},
    "HIGH": {"bg": "#fff7ed", "color": "#ea580c"},
    "WARNING": {"bg": "#fffbeb", "color": "#d97706"},
    "MEDIUM": {"bg": "#fffbeb", "color": "#d97706"},
    "LOW": {"bg": "#f0fdf4", "color": "#16a34a"},
    "SAFE": {"bg": "#f0fdf4", "color": "#16a34a"},
    "HEALTHY": {"bg": "#f0fdf4", "color": "#16a34a"},
    "NORMAL": {"bg": "#f0fdf4", "color": "#16a34a"},
    "INFO": {"bg": "#eff6ff", "color": "#2563eb"},
    "A": {"bg": "#f0fdf4", "color": "#16a34a"},
    "B": {"bg": "#eff6ff", "color": "#2563eb"},
    "C": {"bg": "#fffbeb", "color": "#d97706"},
    "D": {"bg": "#fff7ed", "color": "#ea580c"},
    "F": {"bg": "#fef2f2", "color": "#dc2626"},
}


def _severity_badge(value):
    style = SEVERITY_STYLES.get(value, {"bg": "#f3f4f6", "color": "#6b7280"})
    return (
        f'<span class="severity-badge" '
        f'style="background:{style["bg"]};color:{style["color"]}">'
        f'{value}</span>'
    )


def _threshold_style(value, config):
    if value is None or not isinstance(value, (int, float)):
        return ""
    good = config.get("good", "high")
    thresholds = config.get("thresholds", [])
    if len(thresholds) < 2:
        return ""

    warn, crit = thresholds
    if good == "high":
        if value < crit:
            return "background:#fef2f2;color:#dc2626;font-weight:600;"
        elif value < warn:
            return "background:#fffbeb;color:#d97706;"
        else:
            return "color:#16a34a;"
    else:  # good == "low"
        if value > crit:
            return "background:#fef2f2;color:#dc2626;font-weight:600;"
        elif value > warn:
            return "background:#fffbeb;color:#d97706;"
        else:
            return "color:#16a34a;"


def _progress_bar(value):
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return str(value)

    pct = max(0, min(100, pct))
    if pct >= 80:
        color = "#16a34a"
    elif pct >= 50:
        color = "#d97706"
    else:
        color = "#dc2626"

    return (
        f'<div class="progress-bar-wrap">'
        f'<div class="progress-bar"><div class="progress-bar-fill" '
        f'style="width:{pct}%;background:{color}"></div></div>'
        f'<span style="font-size:11px;min-width:35px">{pct:.0f}%</span>'
        f'</div>'
    )


def _format_value(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return '<span style="color:#9ca3af">—</span>'
    if isinstance(val, float):
        if val >= 1_000_000:
            return f"{val / 1_000_000:.1f}M"
        if val >= 10_000:
            return f"{val:,.0f}"
        if val == int(val):
            return f"{int(val):,}"
        return f"{val:,.1f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)

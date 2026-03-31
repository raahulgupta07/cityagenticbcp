"""
Reusable Plotly chart components for CityBCPAgent.
"""
import plotly.graph_objects as go
import plotly.express as px

from config.settings import SECTORS, ALERTS

# ─── Color Palette ───────────────────────────────────────────────────────────
SECTOR_COLORS = {sid: info["color"] for sid, info in SECTORS.items()}

STATUS_COLORS = {
    "CRITICAL": "#dc2626",
    "WARNING": "#d97706",
    "HEALTHY": "#16a34a",
}

BUFFER_COLORS = [
    [0, "#dc2626"],     # 0 days = red
    [0.15, "#ea580c"],  # ~3 days
    [0.35, "#d97706"],  # ~7 days
    [0.5, "#eab308"],   # ~10 days
    [1, "#16a34a"],     # 20+ days = green
]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=12, color="#374151"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def apply_layout(fig, title=None, height=400):
    fig.update_layout(**CHART_LAYOUT, height=height)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14, color="#1f2937")))
    fig.update_xaxes(gridcolor="#e5e7eb", zeroline=False)
    fig.update_yaxes(gridcolor="#e5e7eb", zeroline=False)
    return fig


# ─── Chart Builders ──────────────────────────────────────────────────────────

def stacked_bar_by_sector(df, x_col, y_col, color_col="sector_id", title=None):
    """Stacked bar chart grouped by sector."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        barmode="stack",
    )
    return apply_layout(fig, title)


def multi_line(df, x_col, y_col, color_col, title=None, height=400):
    """Multi-line chart with optional threshold lines."""
    fig = px.line(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        markers=True,
    )
    return apply_layout(fig, title, height)


def buffer_trend_with_thresholds(df, x_col, y_col, color_col, title=None):
    """Buffer days trend with critical/warning threshold lines."""
    fig = px.line(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
        markers=True,
    )
    # Add threshold lines
    fig.add_hline(
        y=ALERTS["buffer_critical_days"], line_dash="dash",
        line_color="#dc2626", annotation_text="Critical (3 days)",
        annotation_position="top right",
    )
    fig.add_hline(
        y=ALERTS["buffer_warning_days"], line_dash="dash",
        line_color="#d97706", annotation_text="Warning (7 days)",
        annotation_position="top right",
    )
    return apply_layout(fig, title)


def horizontal_bar(df, x_col, y_col, color_col=None, color_map=None, title=None):
    """Horizontal bar chart (e.g., buffer days by site)."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=color_map or SECTOR_COLORS,
        orientation="h",
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    return apply_layout(fig, title, height=max(300, len(df) * 22))


def heatmap(df_pivot, title=None, colorscale="RdYlGn"):
    """Heatmap from a pivoted dataframe (index=sites, columns=dates)."""
    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.values,
        x=df_pivot.columns.tolist(),
        y=df_pivot.index.tolist(),
        colorscale=colorscale,
        colorbar=dict(title="Days"),
        hoverongaps=False,
    ))
    return apply_layout(fig, title, height=max(400, len(df_pivot) * 22))


def dual_axis_bar_line(df, x_col, bar_col, line_col, title=None):
    """Dual-axis: bars (left Y) + line (right Y)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[x_col], y=df[bar_col], name=bar_col,
        marker_color="#3b82f6", opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=df[x_col], y=df[line_col], name=line_col,
        yaxis="y2", mode="lines+markers",
        line=dict(color="#ef4444", width=2),
    ))
    fig.update_layout(
        yaxis=dict(title=bar_col),
        yaxis2=dict(title=line_col, overlaying="y", side="right"),
    )
    return apply_layout(fig, title)


def scatter_chart(df, x_col, y_col, color_col=None, title=None):
    """Scatter plot."""
    fig = px.scatter(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=SECTOR_COLORS,
    )
    return apply_layout(fig, title)


def pie_chart(df, values_col, names_col, title=None):
    """Simple pie/donut chart."""
    fig = px.pie(df, values=values_col, names=names_col, hole=0.4)
    return apply_layout(fig, title, height=350)


def bar_chart(df, x_col, y_col, color_col=None, color_map=None, title=None, barmode="group"):
    """Standard vertical bar chart."""
    fig = px.bar(
        df, x=x_col, y=y_col, color=color_col,
        color_discrete_map=color_map or SECTOR_COLORS,
        barmode=barmode,
    )
    return apply_layout(fig, title)


def treemap(df, path_cols, values_col, color_col=None, title=None):
    """Treemap chart."""
    fig = px.treemap(df, path=path_cols, values=values_col, color=color_col)
    return apply_layout(fig, title, height=500)

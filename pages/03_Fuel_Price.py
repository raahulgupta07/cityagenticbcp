"""
Page 3: Fuel Price Intelligence -- Track fuel costs and purchase volumes by supplier
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import plotly.graph_objects as go
from utils.database import get_db
from utils.charts import multi_line, bar_chart, apply_layout
from utils.smart_table import render_smart_table
from utils.ai_insights import render_insight_panel, render_page_summary, render_forecast_insight
from models.fuel_price_forecast import forecast_fuel_price
from config.settings import SECTORS

from utils.page_header import render_page_header
from utils.auth import require_login, render_sidebar_user
st.set_page_config(page_title="Fuel Price Intelligence", page_icon="⛽", layout="wide")
require_login()
render_sidebar_user()

render_page_header("⛽", "Fuel Price Intelligence", "Diesel purchase prices, supplier comparison, and 7-day price forecast")

ui.alert(
    title="⛽ Fuel Price Intelligence",
    description="Diesel purchase prices from Daily Fuel Price.xlsx. Tracks 2 suppliers (Denko, Moon Sun) across 2 regions (Yangon, Mandalay). Price types: PD (Premium Diesel) and HSD (High-Speed Diesel). Prices in Myanmar Kyat (MMK) per liter.",
    key="alert_fuel",
)

# ─── Load available sectors and dates ────────────────────────────────────────
with get_db() as conn:
    all_sectors = [r[0] for r in conn.execute(
        "SELECT DISTINCT sector_id FROM fuel_purchases ORDER BY sector_id"
    ).fetchall()]
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM fuel_purchases ORDER BY date"
    ).fetchall()]

if not all_sectors or not dates:
    st.info("No fuel purchase data available. Please load data first.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    date_start = st.selectbox("From", dates, index=0)
with col2:
    date_end = st.selectbox("To", dates, index=len(dates) - 1)

# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_fuel_data(d_start, d_end):
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT date, sector_id, region, supplier, fuel_type,
                   quantity_liters, price_per_liter
            FROM fuel_purchases
            WHERE date BETWEEN ? AND ?
            ORDER BY date, supplier
        """, conn, params=(d_start, d_end))
    return df

full_df = load_fuel_data(date_start, date_end)

if full_df.empty:
    st.info("No fuel purchase data in the selected range.")
    st.stop()

# ─── Page-level AI Summary ───────────────────────────────────────────────────
kpi_dict = {
    "total_purchases": len(full_df),
    "total_volume": float(full_df["quantity_liters"].sum()),
    "avg_price_per_liter": float(full_df["price_per_liter"].mean()),
    "sectors": all_sectors,
}
render_page_summary("Fuel Price Intelligence", kpi_dict)

# ─── Sector Tabs ─────────────────────────────────────────────────────────────
selected = ui.tabs(
    options=["All"] + all_sectors,
    default_value="All",
    key="fuel_tabs",
)

if selected == "All":
    sector_filter = None
    tab_key = "fuel_all"
else:
    sector_filter = selected
    tab_key = f"fuel_{selected}"


def render_fuel_content(sector_filter, tab_key):
    """Render fuel price content for a sector filter."""
    if sector_filter is None:
        df = full_df.copy()
    else:
        df = full_df[full_df["sector_id"] == sector_filter].copy()

    if df.empty:
        st.info(f"No fuel purchase data for {sector_filter or 'any sector'}.")
        return

    # ─── KPI Cards ───────────────────────────────────────────────────────
    st.markdown("### Key Metrics")
    total_vol = df["quantity_liters"].sum()
    avg_price = df["price_per_liter"].mean()
    max_price = df["price_per_liter"].max()

    kc1, kc2, kc3, kc4 = st.columns(4)
    with kc1:
        ui.metric_card(
            title="Total Purchases",
            content=f"{len(df):,}",
            description="Number of purchase records",
            key=f"metric_purchases_{tab_key}",
        )
    with kc2:
        ui.metric_card(
            title="Total Volume (L)",
            content=f"{total_vol:,.0f}" if pd.notna(total_vol) else "N/A",
            description="Liters purchased",
            key=f"metric_volume_{tab_key}",
        )
    with kc3:
        ui.metric_card(
            title="Avg Price/L (MMK)",
            content=f"{avg_price:,.0f}" if pd.notna(avg_price) else "N/A",
            description="Average price per liter",
            key=f"metric_avg_price_{tab_key}",
        )
    with kc4:
        ui.metric_card(
            title="Max Price/L (MMK)",
            content=f"{max_price:,.0f}" if pd.notna(max_price) else "N/A",
            description="Peak price per liter",
            key=f"metric_max_price_{tab_key}",
        )

    # ─── Price Trend Badge ───────────────────────────────────────────────
    if len(df) >= 2:
        sorted_prices = df.sort_values("date")
        first_half = sorted_prices.iloc[:len(sorted_prices)//2]["price_per_liter"].mean()
        second_half = sorted_prices.iloc[len(sorted_prices)//2:]["price_per_liter"].mean()
        if second_half > first_half * 1.02:
            trend_label, trend_variant = "Rising", "destructive"
        elif second_half < first_half * 0.98:
            trend_label, trend_variant = "Falling", "default"
        else:
            trend_label, trend_variant = "Stable", "outline"
        ui.badges(
            badge_list=[(f"Price Trend: {trend_label}", trend_variant)],
            key=f"trend_badge_{tab_key}",
        )

    st.markdown("---")

    # ─── Chart 1: Daily Price Trend per Supplier ─────────────────────────
    st.markdown("### Daily Price Trend by Supplier")
    st.caption("This line chart tracks the average diesel price per liter over time for each supplier. Rising lines mean fuel is getting more expensive.")
    price_trend = df.groupby(["date", "supplier"], as_index=False)["price_per_liter"].mean()
    price_trend["price_per_liter"] = price_trend["price_per_liter"].round(1)

    if not price_trend.empty:
        fig1 = multi_line(price_trend, "date", "price_per_liter", "supplier",
                           title="Average Price per Liter (MMK) by Supplier")
        st.plotly_chart(fig1, use_container_width=True, key=f"price_trend_chart_{tab_key}")
        render_insight_panel(
            f"Fuel price trend by supplier{' for ' + sector_filter if sector_filter else ''}",
            price_trend,
            f"price_trend_{tab_key}",
        )
    else:
        st.info("No price trend data available.")

    # ─── Chart 2: Purchase Volume by Supplier ────────────────────────────
    st.markdown("### Purchase Volume by Supplier")
    st.caption("This bar chart compares total liters purchased from each supplier. It helps identify which supplier is used the most.")
    vol_by_supplier = df.groupby(["supplier"], as_index=False)["quantity_liters"].sum()
    vol_by_supplier["quantity_liters"] = vol_by_supplier["quantity_liters"].round(0)

    if not vol_by_supplier.empty:
        fig2 = bar_chart(vol_by_supplier, "supplier", "quantity_liters",
                          title="Total Purchase Volume (Liters) by Supplier")
        st.plotly_chart(fig2, use_container_width=True, key=f"vol_supplier_chart_{tab_key}")
        render_insight_panel(
            f"Purchase volume comparison by supplier{' for ' + sector_filter if sector_filter else ''}",
            vol_by_supplier,
            f"vol_supplier_{tab_key}",
        )
    else:
        st.info("No volume data available.")

    # ─── Smart Table: Purchase Log ───────────────────────────────────────
    st.markdown("### Purchase Log")
    st.caption("Full list of fuel purchases showing date, supplier, fuel type, quantity, and price per liter.")
    table_df = df[["date", "sector_id", "region", "supplier", "fuel_type",
                   "quantity_liters", "price_per_liter"]].copy()
    table_df.columns = ["Date", "Sector", "Region", "Supplier", "Fuel Type",
                         "Quantity (L)", "Price/L (MMK)"]
    render_smart_table(
        table_df, title="Fuel Purchases",
        highlight_cols={"Price/L (MMK)": {"good": "low", "thresholds": [3000, 4000]}},
    )
    render_insight_panel(
        f"Fuel purchase log{' for ' + sector_filter if sector_filter else ''}",
        table_df,
        f"purchase_log_{tab_key}",
    )

    # ─── Fuel Price Forecast ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Fuel Price Forecast (Next 7 Days)")
    st.caption("Based on the last 4 weeks of prices, here's what we expect next week. The shaded area shows the range of uncertainty -- wider means less confidence in the prediction.")

    try:
        forecast_result = forecast_fuel_price(sector_id=sector_filter, fuel_type="PD", days_ahead=7)

        if forecast_result.get("error"):
            st.info(f"Forecast not available: {forecast_result['error']}")
        else:
            history = forecast_result["history"]
            forecast_df = forecast_result["forecast"]

            if history is not None and forecast_df is not None and not forecast_df.empty:
                # Build combined chart: historical + forecast
                fig_fc = go.Figure()

                # Historical prices
                fig_fc.add_trace(go.Scatter(
                    x=history["date"],
                    y=history["price"],
                    mode="lines+markers",
                    name="Historical Price",
                    line=dict(color="#3b82f6", width=2),
                    marker=dict(size=4),
                ))

                # Forecast line
                fig_fc.add_trace(go.Scatter(
                    x=forecast_df["date"],
                    y=forecast_df["predicted_price"],
                    mode="lines+markers",
                    name="Forecast",
                    line=dict(color="#ef4444", width=2, dash="dash"),
                    marker=dict(size=5, symbol="diamond"),
                ))

                # Confidence band
                fig_fc.add_trace(go.Scatter(
                    x=pd.concat([forecast_df["date"], forecast_df["date"][::-1]]),
                    y=pd.concat([forecast_df["upper_bound"], forecast_df["lower_bound"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(239,68,68,0.1)",
                    line=dict(color="rgba(239,68,68,0)"),
                    name="95% Confidence",
                    showlegend=True,
                ))

                fig_fc = apply_layout(fig_fc, title="Diesel Price Forecast (MMK/L)")
                fig_fc.update_xaxes(title_text="Date")
                fig_fc.update_yaxes(title_text="Price per Liter (MMK)")
                st.plotly_chart(fig_fc, use_container_width=True, key=f"forecast_chart_{tab_key}")

                # Trend badge
                trend = forecast_result.get("trend", "stable")
                r2 = forecast_result.get("r_squared", 0)
                trend_map = {"rising": "destructive", "falling": "default", "stable": "outline"}
                ui.badges(
                    badge_list=[
                        (f"Trend: {trend.title()}", trend_map.get(trend, "outline")),
                        (f"Model Fit: {r2:.2f}", "outline"),
                    ],
                    key=f"forecast_badges_{tab_key}",
                )

                # Forecast insight
                render_forecast_insight(
                    "Fuel Price Forecast",
                    {
                        "trend": trend,
                        "current_price": float(history["price"].iloc[-1]),
                        "forecast_avg": float(forecast_df["predicted_price"].mean()),
                        "forecast_min": float(forecast_df["predicted_price"].min()),
                        "forecast_max": float(forecast_df["predicted_price"].max()),
                        "days_ahead": 7,
                    },
                    f"fuel_forecast_{tab_key}",
                )

                render_insight_panel(
                    f"Fuel price forecast{' for ' + sector_filter if sector_filter else ''}",
                    forecast_df[["date", "predicted_price", "lower_bound", "upper_bound"]],
                    f"forecast_insight_{tab_key}",
                )
            else:
                st.info("Not enough historical data to generate a forecast.")

    except Exception as e:
        st.warning(f"Forecast model could not run: {e}")


# Render content for the selected tab
render_fuel_content(sector_filter, tab_key)


# ─── AI Insights Button ────────────────────────────────────────────────────
from utils.ai_insights import finish_page
finish_page()

"""
Agent tools 7-12: ML model invocations and utility tools.
"""
import json
import pandas as pd
from agents.tools.registry import tool
from utils.database import get_db


@tool(
    name="forecast_fuel_price",
    description="Run the fuel price forecaster (M1). Returns 7-day price predictions with confidence intervals and trend.",
    parameters={
        "type": "object",
        "properties": {
            "sector_id": {"type": "string", "description": "Sector to forecast (CMHL, CP, CFC)"},
            "fuel_type": {"type": "string", "description": "PD or HSD (default: PD)"},
            "days_ahead": {"type": "integer", "description": "Days to forecast (default: 7)"},
        },
    },
)
def forecast_fuel_price(sector_id=None, fuel_type="PD", days_ahead=7):
    from models.fuel_price_forecast import forecast_fuel_price as _forecast
    result = _forecast(sector_id, fuel_type, days_ahead)
    return {
        "trend": result["trend"],
        "r_squared": result["r_squared"],
        "avg_daily_change_mmk": result["avg_daily_change"],
        "forecast": result["forecast"].to_dict(orient="records") if result["forecast"] is not None else [],
        "error": result["error"],
    }


@tool(
    name="predict_stockout",
    description="Run the buffer depletion predictor (M2). Returns projected stockout dates per site with confidence levels.",
    parameters={
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "Specific site (omit for all)"},
            "threshold_days": {"type": "number", "description": "Only show sites projected to run out within this many days (default: 14)"},
        },
    },
)
def predict_stockout(site_id=None, threshold_days=14):
    from models.buffer_predictor import predict_buffer_depletion
    df = predict_buffer_depletion(site_id)
    if df.empty:
        return {"error": "No data available for predictions"}
    if threshold_days:
        df = df[(df["days_until_stockout"].notna()) & (df["days_until_stockout"] <= threshold_days)]
    return df.sort_values("days_until_stockout")


@tool(
    name="check_efficiency",
    description="Run the generator efficiency scorer (M3). Returns efficiency ratios and anomaly flags per generator.",
    parameters={
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "Specific site (omit for all)"},
            "only_anomalies": {"type": "boolean", "description": "Only return anomalies (default: false)"},
        },
    },
)
def check_efficiency(site_id=None, only_anomalies=False):
    from models.efficiency_scorer import compute_efficiency, get_anomalies
    if only_anomalies:
        return get_anomalies(site_id)
    return compute_efficiency(site_id)


@tool(
    name="compute_bcp_scores",
    description="Run the BCP score engine (M4). Returns composite BCP scores (0-100) and grades (A-F) per site.",
    parameters={
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Target date (default: latest with most data)"},
            "sector_id": {"type": "string", "description": "Filter by sector"},
        },
    },
)
def compute_bcp_scores(date=None, sector_id=None):
    from models.bcp_engine import compute_bcp_scores as _compute
    # Use a date with good data coverage
    if not date:
        with get_db() as conn:
            row = conn.execute("""
                SELECT date FROM daily_site_summary
                GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1
            """).fetchone()
            date = row[0] if row else None
    df = _compute(date)
    if df.empty:
        return {"error": "No data for BCP scoring"}
    if sector_id:
        df = df[df["sector_id"] == sector_id]
    return df


@tool(
    name="predict_blackout",
    description="Run the blackout predictor (M5). Returns blackout probability per site for tomorrow. Only for CP/CFC sectors.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def predict_blackout():
    from models.blackout_predictor import train_and_predict
    result = train_and_predict()
    return {
        "model_accuracy": result["model_accuracy"],
        "training_samples": result["training_samples"],
        "predictions": result["predictions"].to_dict(orient="records") if not result["predictions"].empty else [],
        "error": result["error"],
    }


@tool(
    name="run_sql",
    description="Execute a read-only SQL SELECT query on the database. Use for custom data queries not covered by other tools.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SQL SELECT query to execute"},
        },
        "required": ["query"],
    },
)
def run_sql(query):
    # Validate: only SELECT allowed
    clean = query.strip().upper()
    if not clean.startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed"}
    for forbidden in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH"]:
        if forbidden in clean:
            return {"error": f"Forbidden keyword: {forbidden}"}

    with get_db() as conn:
        try:
            df = pd.read_sql_query(query, conn)
            if len(df) > 50:
                df = df.head(50)
            return df
        except Exception as e:
            return {"error": str(e)}

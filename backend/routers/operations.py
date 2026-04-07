"""Operations router — modes, delivery, BCP scores, alerts, predictions."""
from typing import Optional
from fastapi import APIRouter, Depends
import pandas as pd
from models.decision_engine import (
    get_operating_modes, get_delivery_queue,
    get_weekly_budget_forecast, get_supplier_buy_signal,
)
from models.bcp_engine import compute_bcp_scores
from models.buffer_predictor import get_critical_sites
from models.fuel_price_forecast import forecast_fuel_price
from alerts.alert_engine import get_active_alerts
from utils.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter()


def _df_to_json(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


@router.get("/operating-modes")
def operating_modes(sector: Optional[str] = None, user: dict = Depends(get_current_user)):
    df = get_operating_modes()
    if not df.empty and sector:
        df = df[df["sector_id"] == sector]
    return _df_to_json(df)


@router.get("/delivery-queue")
def delivery_queue(sector: Optional[str] = None, user: dict = Depends(get_current_user)):
    df = get_delivery_queue()
    if not df.empty and sector:
        df = df[df["sector_id"] == sector]
    return _df_to_json(df)


@router.get("/bcp-scores")
def bcp_scores(user: dict = Depends(get_current_user)):
    with get_db() as conn:
        best_date = conn.execute("SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    if not best_date:
        return []
    df = compute_bcp_scores(best_date[0])
    return _df_to_json(df)


@router.get("/alerts")
def alerts(user: dict = Depends(get_current_user)):
    df = get_active_alerts()
    return _df_to_json(df)


@router.get("/stockout-forecast")
def stockout_forecast(user: dict = Depends(get_current_user)):
    try:
        df = get_critical_sites(threshold_days=7)
        return _df_to_json(df)
    except Exception:
        return []


@router.get("/fuel-forecast")
def fuel_forecast(user: dict = Depends(get_current_user)):
    try:
        fc = forecast_fuel_price()
        if fc and not fc.get("error"):
            return {
                "history": _df_to_json(fc.get("history")),
                "forecast": _df_to_json(fc.get("forecast")),
                "trend": fc.get("trend"),
                "r_squared": fc.get("r_squared"),
            }
    except Exception:
        pass
    return {"history": [], "forecast": [], "trend": "unknown", "r_squared": 0}


@router.get("/budget-forecast")
def budget_forecast(user: dict = Depends(get_current_user)):
    try:
        return get_weekly_budget_forecast() or {}
    except Exception:
        return {}


@router.get("/buy-signal")
def buy_signal(user: dict = Depends(get_current_user)):
    try:
        return get_supplier_buy_signal() or {}
    except Exception:
        return {}

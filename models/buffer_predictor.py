"""
M2: Buffer Depletion Predictor
Exponential smoothing on daily usage to project when each site runs out of fuel.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from utils.database import get_db


def predict_buffer_depletion(site_id=None, alpha=0.3):
    """
    Predict when sites will run out of fuel based on consumption trends.

    Args:
        site_id: Optional specific site (None = all sites)
        alpha: Exponential smoothing factor (0-1, higher = more weight on recent data)

    Returns:
        DataFrame with columns:
            site_id, sector_id, current_balance, avg_daily_used,
            smoothed_daily_used, days_until_stockout, projected_stockout_date,
            trend (increasing/decreasing/stable), confidence (high/medium/low)
    """
    with get_db() as conn:
        query = """
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.total_daily_used > 0 OR dss.spare_tank_balance > 0
        """
        params = []
        if site_id:
            query += " AND dss.site_id = ?"
            params.append(site_id)
        query += " ORDER BY dss.site_id, dss.date"
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return pd.DataFrame()

    results = []
    for sid, group in df.groupby("site_id"):
        group = group.sort_values("date")
        sector = group["sector_id"].iloc[0]

        # Get usage series (non-null values)
        usage = group["total_daily_used"].dropna()
        if len(usage) < 2:
            continue

        # Current balance (latest non-null)
        balance_series = group["spare_tank_balance"].dropna()
        if balance_series.empty:
            continue
        current_balance = balance_series.iloc[-1]

        # Simple average
        avg_daily = usage.mean()

        # Exponential smoothing
        smoothed = usage.iloc[0]
        for val in usage.iloc[1:]:
            smoothed = alpha * val + (1 - alpha) * smoothed

        # Trend detection (last 3 days vs previous 3)
        if len(usage) >= 6:
            recent = usage.iloc[-3:].mean()
            earlier = usage.iloc[-6:-3].mean()
            pct_change = (recent - earlier) / earlier * 100 if earlier > 0 else 0
            if pct_change > 10:
                trend = "increasing"
            elif pct_change < -10:
                trend = "decreasing"
            else:
                trend = "stable"
        elif len(usage) >= 3:
            recent = usage.iloc[-2:].mean()
            earlier = usage.iloc[:-2].mean()
            pct_change = (recent - earlier) / earlier * 100 if earlier > 0 else 0
            trend = "increasing" if pct_change > 10 else "decreasing" if pct_change < -10 else "stable"
        else:
            trend = "stable"

        # Project stockout
        consumption_rate = smoothed if smoothed > 0 else avg_daily
        if consumption_rate > 0:
            days_until = current_balance / consumption_rate
        else:
            days_until = None

        # Confidence based on data quality
        data_points = len(usage)
        usage_variance = usage.std() / usage.mean() if usage.mean() > 0 else 1
        if data_points >= 5 and usage_variance < 0.3:
            confidence = "high"
        elif data_points >= 3:
            confidence = "medium"
        else:
            confidence = "low"

        # Projected date
        latest_date = pd.to_datetime(group["date"].max())
        stockout_date = None
        if days_until is not None and days_until < 365:
            stockout_date = (latest_date + timedelta(days=int(days_until))).strftime("%Y-%m-%d")

        results.append({
            "site_id": sid,
            "sector_id": sector,
            "current_balance": round(current_balance, 0),
            "avg_daily_used": round(avg_daily, 1),
            "smoothed_daily_used": round(smoothed, 1),
            "days_until_stockout": round(days_until, 1) if days_until else None,
            "projected_stockout_date": stockout_date,
            "trend": trend,
            "confidence": confidence,
            "data_points": data_points,
        })

    return pd.DataFrame(results)


def get_critical_sites(threshold_days=7):
    """Get sites projected to run out within threshold_days."""
    df = predict_buffer_depletion()
    if df.empty:
        return df
    critical = df[
        (df["days_until_stockout"].notna()) &
        (df["days_until_stockout"] <= threshold_days)
    ].sort_values("days_until_stockout")
    return critical

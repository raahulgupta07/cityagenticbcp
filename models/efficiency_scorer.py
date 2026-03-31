"""
M3: Generator Efficiency Scorer
Rule-based efficiency ratio + Isolation Forest anomaly detection.
"""
import numpy as np
import pandas as pd
from utils.database import get_db

try:
    from sklearn.ensemble import IsolationForest
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def compute_efficiency(site_id=None, date=None):
    """
    Compute efficiency ratio for each generator-day.

    efficiency = actual_used / (rated_consumption * run_hours)
    Normal range: 0.8 - 1.2
    Anomaly: < 0.5 or > 1.5

    Returns DataFrame with:
        site_id, generator_id, model_name, date, gen_run_hr, daily_used,
        rated_consumption, expected_used, efficiency_ratio, status, is_anomaly
    """
    with get_db() as conn:
        query = """
            SELECT do.site_id, do.generator_id, g.model_name, g.consumption_per_hour,
                   do.date, do.gen_run_hr, do.daily_used_liters,
                   s.sector_id
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.gen_run_hr > 0
              AND do.daily_used_liters > 0
              AND g.consumption_per_hour > 0
        """
        params = []
        if site_id:
            query += " AND do.site_id = ?"
            params.append(site_id)
        if date:
            query += " AND do.date = ?"
            params.append(date)
        query += " ORDER BY do.site_id, do.date"
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return pd.DataFrame()

    # Calculate efficiency
    df["expected_used"] = df["consumption_per_hour"] * df["gen_run_hr"]
    df["efficiency_ratio"] = df["daily_used_liters"] / df["expected_used"]
    df["efficiency_ratio"] = df["efficiency_ratio"].round(2)

    # Rule-based status
    def _status(ratio):
        if ratio > 1.5:
            return "HIGH_CONSUMPTION"
        elif ratio > 1.2:
            return "ABOVE_NORMAL"
        elif ratio < 0.5:
            return "LOW_CONSUMPTION"
        elif ratio < 0.8:
            return "BELOW_NORMAL"
        return "NORMAL"

    df["status"] = df["efficiency_ratio"].apply(_status)

    # Isolation Forest anomaly detection
    df["is_anomaly"] = False
    if HAS_SKLEARN and len(df) >= 10:
        features = df[["gen_run_hr", "daily_used_liters", "efficiency_ratio"]].values
        iso = IsolationForest(contamination=0.1, random_state=42)
        preds = iso.fit_predict(features)
        df["is_anomaly"] = preds == -1

    # Also flag extreme ratios as anomalies
    df.loc[df["efficiency_ratio"] > 1.5, "is_anomaly"] = True
    df.loc[df["efficiency_ratio"] < 0.5, "is_anomaly"] = True

    return df[["site_id", "sector_id", "generator_id", "model_name", "date",
               "gen_run_hr", "daily_used_liters", "consumption_per_hour",
               "expected_used", "efficiency_ratio", "status", "is_anomaly"]]


def get_anomalies(site_id=None):
    """Get all anomalous generator-days."""
    df = compute_efficiency(site_id)
    if df.empty:
        return df
    return df[df["is_anomaly"]].sort_values("efficiency_ratio", ascending=False)


def get_fleet_efficiency_summary():
    """Aggregate efficiency stats per generator model."""
    df = compute_efficiency()
    if df.empty:
        return pd.DataFrame()

    summary = df.groupby(["model_name"]).agg(
        generator_count=("generator_id", "nunique"),
        total_run_hr=("gen_run_hr", "sum"),
        total_used=("daily_used_liters", "sum"),
        avg_efficiency=("efficiency_ratio", "mean"),
        anomaly_count=("is_anomaly", "sum"),
        data_points=("efficiency_ratio", "count"),
    ).round(2).reset_index()

    summary = summary.sort_values("total_run_hr", ascending=False)
    return summary

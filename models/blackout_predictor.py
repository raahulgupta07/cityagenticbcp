"""
M5: Blackout Pattern Detector
GradientBoostingClassifier to predict high-impact blackouts (>4 hours).
Only applicable to sectors with blackout data (CP, CFC).
"""
import numpy as np
import pandas as pd
from utils.database import get_db

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import cross_val_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


def _prepare_training_data():
    """Build feature matrix from historical blackout data."""
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.date,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.spare_tank_balance, dss.blackout_hr,
                   dss.days_of_buffer, dss.num_generators_active
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE s.sector_id IN ('CP', 'CFC')
            ORDER BY dss.site_id, dss.date
        """, conn)

    if df.empty:
        return None, None, None

    df["date_dt"] = pd.to_datetime(df["date"])
    df["day_of_week"] = df["date_dt"].dt.dayofweek

    # Encode site_id
    le_site = LabelEncoder()
    df["site_encoded"] = le_site.fit_transform(df["site_id"])

    le_sector = LabelEncoder()
    df["sector_encoded"] = le_sector.fit_transform(df["sector_id"])

    # Lag features (previous day)
    df = df.sort_values(["site_id", "date"])
    df["prev_gen_hr"] = df.groupby("site_id")["total_gen_run_hr"].shift(1)
    df["prev_used"] = df.groupby("site_id")["total_daily_used"].shift(1)
    df["prev_blackout"] = df.groupby("site_id")["blackout_hr"].shift(1)

    # Target: blackout > 4 hours
    df["high_blackout"] = (df["blackout_hr"].fillna(0) > 4).astype(int)

    # Drop rows with NaN lag
    df = df.dropna(subset=["prev_gen_hr"])

    feature_cols = [
        "day_of_week", "site_encoded", "sector_encoded",
        "prev_gen_hr", "prev_used", "prev_blackout",
        "spare_tank_balance", "days_of_buffer", "num_generators_active",
    ]

    # Fill remaining NaN
    for col in feature_cols:
        df[col] = df[col].fillna(0)

    X = df[feature_cols].values
    y = df["high_blackout"].values

    return X, y, (le_site, le_sector, feature_cols, df)


def train_and_predict():
    """
    Train blackout predictor and return predictions for each site's next day.

    Returns:
        {
            "predictions": DataFrame with site_id, sector_id, probability, risk_level,
            "model_accuracy": float (cross-val),
            "training_samples": int,
            "error": str or None,
        }
    """
    result = {
        "predictions": pd.DataFrame(),
        "model_accuracy": 0,
        "training_samples": 0,
        "error": None,
    }

    if not HAS_SKLEARN:
        result["error"] = "scikit-learn not available"
        return result

    prepared = _prepare_training_data()
    if prepared[0] is None:
        result["error"] = "No blackout data available for training"
        return result

    X, y, (le_site, le_sector, feature_cols, df) = prepared

    if len(X) < 20:
        result["error"] = f"Insufficient training data ({len(X)} samples, need 20+)"
        return result

    result["training_samples"] = len(X)

    # Check class balance
    positive_rate = y.mean()
    if positive_rate == 0:
        # No high-blackout events in history
        result["error"] = "No high-blackout events in training data (all < 4 hrs)"
        # Return all-zero predictions
        with get_db() as conn:
            sites = pd.read_sql_query("""
                SELECT DISTINCT s.site_id, s.sector_id
                FROM sites s WHERE s.sector_id IN ('CP', 'CFC')
            """, conn)
        sites["probability"] = 0.0
        sites["risk_level"] = "LOW"
        result["predictions"] = sites
        return result

    # Train model
    model = GradientBoostingClassifier(
        n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42
    )

    # Cross-validation accuracy
    try:
        cv_scores = cross_val_score(model, X, y, cv=min(3, len(X) // 5 + 1), scoring="accuracy")
        result["model_accuracy"] = round(cv_scores.mean(), 3)
    except Exception:
        result["model_accuracy"] = 0

    # Fit on all data
    model.fit(X, y)

    # Predict for each site using latest data as "previous day"
    latest_per_site = df.sort_values("date").groupby("site_id").tail(1)

    predictions = []
    for _, row in latest_per_site.iterrows():
        # Build feature vector for "next day"
        next_dow = (row["day_of_week"] + 1) % 7
        features = [
            next_dow, row["site_encoded"], row["sector_encoded"],
            row["total_gen_run_hr"] or 0,
            row["total_daily_used"] or 0,
            row["blackout_hr"] or 0,
            row["spare_tank_balance"] or 0,
            row["days_of_buffer"] or 0,
            row["num_generators_active"] or 0,
        ]

        prob = model.predict_proba([features])[0][1]  # P(high_blackout=1)

        if prob > 0.7:
            risk = "CRITICAL"
        elif prob > 0.4:
            risk = "WARNING"
        else:
            risk = "LOW"

        predictions.append({
            "site_id": row["site_id"],
            "sector_id": row["sector_id"],
            "probability": round(prob, 3),
            "risk_level": risk,
        })

    result["predictions"] = pd.DataFrame(predictions).sort_values("probability", ascending=False)
    return result

"""
M1: Fuel Price Forecaster
LinearRegression + polynomial features, 7-day forecast with confidence interval.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from utils.database import get_db


def get_price_history(sector_id=None, fuel_type="PD", min_days=7):
    """Load historical fuel prices from DB."""
    with get_db() as conn:
        query = """
            SELECT date, AVG(price_per_liter) as price,
                   GROUP_CONCAT(DISTINCT supplier) as suppliers
            FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL
        """
        params = []
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        if fuel_type:
            query += " AND fuel_type = ?"
            params.append(fuel_type)
        query += " GROUP BY date ORDER BY date"
        df = pd.read_sql_query(query, conn, params=params)

    if len(df) < min_days:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df


def forecast_fuel_price(sector_id=None, fuel_type="PD", days_ahead=7, degree=2):
    """
    Forecast fuel prices for the next N days.

    Returns:
        {
            "history": DataFrame with date, price columns,
            "forecast": DataFrame with date, predicted_price, lower_bound, upper_bound,
            "trend": "rising" | "falling" | "stable",
            "avg_daily_change": float,
            "r_squared": float,
            "error": str or None,
        }
    """
    result = {
        "history": None, "forecast": None,
        "trend": "stable", "avg_daily_change": 0,
        "r_squared": 0, "error": None,
    }

    df = get_price_history(sector_id, fuel_type)
    if df is None or len(df) < 7:
        result["error"] = f"Insufficient price data (need 7+ days, have {len(df) if df is not None else 0})"
        return result

    result["history"] = df

    # Feature engineering
    df["ordinal"] = (df["date"] - df["date"].min()).dt.days
    df["day_of_week"] = df["date"].dt.dayofweek

    # Lagged features
    df["lag_1"] = df["price"].shift(1)
    df["lag_3"] = df["price"].shift(3)
    df["lag_7"] = df["price"].shift(7)
    df["rolling_mean_3"] = df["price"].rolling(3).mean()
    df["rolling_mean_7"] = df["price"].rolling(7).mean()
    df = df.dropna()

    if len(df) < 5:
        result["error"] = "Not enough data after feature engineering"
        return result

    feature_cols = ["ordinal", "day_of_week", "lag_1", "rolling_mean_3"]
    if "lag_3" in df.columns and df["lag_3"].notna().sum() > 3:
        feature_cols.append("lag_3")

    X = df[feature_cols].values
    y = df["price"].values

    # Scale features for Ridge regression
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train with regularization to prevent overfitting
    model = Ridge(alpha=10.0)
    model.fit(X_scaled, y)

    # R-squared
    y_pred_train = model.predict(X_scaled)
    ss_res = np.sum((y - y_pred_train) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    result["r_squared"] = round(r_squared, 3)

    # Residual std for confidence interval
    residual_std = np.std(y - y_pred_train)

    # Forecast future dates
    last_date = df["date"].max()
    last_ordinal = df["ordinal"].max()
    last_price = df["price"].iloc[-1]
    last_prices = df["price"].tolist()

    forecasts = []
    current_lag_1 = last_price
    current_lag_3 = np.mean(last_prices[-3:]) if len(last_prices) >= 3 else last_price
    current_rm3 = np.mean(last_prices[-3:]) if len(last_prices) >= 3 else last_price

    for i in range(1, days_ahead + 1):
        future_date = last_date + timedelta(days=i)
        ordinal = last_ordinal + i
        dow = future_date.dayofweek

        features = [ordinal, dow, current_lag_1, current_rm3]
        if "lag_3" in feature_cols:
            features.append(current_lag_3)

        X_future = scaler.transform([features])
        pred = model.predict(X_future)[0]
        pred = max(pred, 0)  # no negative prices

        forecasts.append({
            "date": future_date,
            "predicted_price": round(pred, 0),
            "lower_bound": round(max(pred - 1.96 * residual_std, 0), 0),
            "upper_bound": round(pred + 1.96 * residual_std, 0),
        })

        # Update rolling values for next iteration
        current_lag_1 = pred
        recent = last_prices[-2:] + [pred]
        current_lag_3 = np.mean(recent)
        current_rm3 = np.mean(recent[-3:])
        last_prices.append(pred)

    result["forecast"] = pd.DataFrame(forecasts)

    # Trend
    if len(df) >= 3:
        recent_change = df["price"].iloc[-1] - df["price"].iloc[-3]
        pct_change = recent_change / df["price"].iloc[-3] * 100 if df["price"].iloc[-3] > 0 else 0
        result["avg_daily_change"] = round(recent_change / 3, 0)
        if pct_change > 2:
            result["trend"] = "rising"
        elif pct_change < -2:
            result["trend"] = "falling"
        else:
            result["trend"] = "stable"

    return result

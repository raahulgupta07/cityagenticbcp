"""Charts router — all data endpoints needed for the 53 missing frontend charts."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
import numpy as np
from utils.database import get_db
from backend.routers.auth import get_current_user
from backend.routers.data import _dsql
from config.settings import HEATMAP_THRESHOLDS

router = APIRouter()


def _df(df):
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


def _latest_date():
    """Get the date with most site reports."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def _price_map():
    """Sector → latest fuel price."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT sector_id, price_per_liter FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id HAVING date = MAX(date)
        """).fetchall()
        if not rows:
            rows = conn.execute("""
                SELECT sector_id, AVG(price_per_liter) as price_per_liter
                FROM fuel_purchases WHERE price_per_liter IS NOT NULL
                GROUP BY sector_id
            """).fetchall()
    return {r["sector_id"]: r["price_per_liter"] for r in rows}


# ═══════════════════════════════════════════════════════════════════════════
# 1.1  GET /api/sites-summary — per-site latest KPIs
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/sites-summary")
def sites_summary(
    sector: Optional[str] = None,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        dsql, dp = _dsql("dss.date", date_from, date_to)
        q = f"""
            SELECT dss.site_id, s.sector_id, s.site_type, s.site_name,
                   s.cost_center_code, s.region as site_code, s.segment_name,
                   s.cost_center_description, s.address_state, s.store_size,
                   s.latitude, s.longitude,
                   AVG(dss.total_daily_used) as avg_daily_used,
                   AVG(dss.total_gen_run_hr) as avg_gen_hr,
                   MAX(dss.spare_tank_balance) as tank,
                   AVG(dss.days_of_buffer) as buffer_days,
                   AVG(dss.blackout_hr) as avg_blackout,
                   COUNT(DISTINCT dss.date) as data_days,
                   SUM(dss.total_daily_used) as total_liters,
                   SUM(dss.total_gen_run_hr) as total_gen_hr
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1{dsql}
        """
        if sector:
            q += " AND s.sector_id = ?"; dp.append(sector)
        q += " GROUP BY dss.site_id ORDER BY avg_daily_used DESC"
        df = pd.read_sql_query(q, conn, params=dp)

        # Get sales for mapped sites
        sales = pd.read_sql_query(f"""
            SELECT site_id, SUM(sales_amt) as total_sales
            FROM daily_sales WHERE site_id IS NOT NULL
            {"AND date >= ? AND date <= ?" if date_from and date_to else ""}
            GROUP BY site_id
        """, conn, params=[date_from, date_to] if date_from and date_to else [])

    if df.empty:
        return []

    pm = _price_map()
    df["energy_cost"] = df.apply(lambda r: (r["total_liters"] or 0) * pm.get(r["sector_id"], 0), axis=1)
    df["efficiency"] = np.where(df["total_gen_hr"] > 0, df["total_liters"] / df["total_gen_hr"], 0)

    if not sales.empty:
        df = df.merge(sales, on="site_id", how="left")
        df["diesel_pct"] = np.where(
            df["total_sales"].fillna(0) > 0,
            df["energy_cost"] / df["total_sales"] * 100, None
        )
    else:
        df["total_sales"] = None
        df["diesel_pct"] = None

    return _df(df.round(2))


# ═══════════════════════════════════════════════════════════════════════════
# 1.2  GET /api/site/{site_id}/charts — full site chart data
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/site/{site_id}/charts")
def site_charts(
    site_id: str,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    period: str = "daily",
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        # Check site exists
        site = conn.execute("SELECT site_id, sector_id, site_name, site_type FROM sites WHERE site_id = ?", (site_id,)).fetchone()
        if not site:
            raise HTTPException(404, f"Site {site_id} not found")

        dsql, dp = _dsql("dss.date", date_from, date_to)

        # 1. Daily site summary (time series)
        daily = pd.read_sql_query(f"""
            SELECT dss.date, dss.total_gen_run_hr as gen_hr, dss.total_daily_used as fuel,
                   dss.spare_tank_balance as tank, dss.days_of_buffer as buffer,
                   dss.blackout_hr, dss.num_generators_active
            FROM daily_site_summary dss WHERE dss.site_id = ?{dsql}
            ORDER BY dss.date
        """, conn, params=[site_id] + dp)

        # 2. Generators
        gens = pd.read_sql_query("""
            SELECT g.generator_id, g.model_name, g.power_kva, g.consumption_per_hour,
                   MAX(do.gen_run_hr) as latest_run_hr,
                   MAX(do.daily_used_liters) as latest_fuel,
                   SUM(do.gen_run_hr) as total_run_hr,
                   SUM(do.daily_used_liters) as total_fuel
            FROM generators g
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
            WHERE g.site_id = ? AND g.is_active = 1
            GROUP BY g.generator_id
        """, conn, params=[site_id])

        # 3. Per-generator daily (for grouped bar charts)
        gen_daily = pd.read_sql_query(f"""
            SELECT do.date, g.model_name, do.gen_run_hr, do.daily_used_liters,
                   do.spare_tank_balance, do.blackout_hr,
                   g.consumption_per_hour
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            WHERE do.site_id = ?{dsql}
            ORDER BY do.date, g.model_name
        """, conn, params=[site_id] + dp)

        # 4. Sales (if mapped)
        sales_daily = pd.read_sql_query(f"""
            SELECT date, SUM(sales_amt) as sales, SUM(margin) as margin
            FROM daily_sales WHERE site_id = ?
            {"AND date >= ? AND date <= ?" if date_from and date_to else ""}
            GROUP BY date ORDER BY date
        """, conn, params=[site_id] + ([date_from, date_to] if date_from and date_to else []))

        # 5. Fuel price for this sector
        prices = pd.read_sql_query("""
            SELECT date, price_per_liter, supplier FROM fuel_purchases
            WHERE sector_id = ? AND price_per_liter IS NOT NULL
            ORDER BY date
        """, conn, params=[site["sector_id"]])

        # 6. Sector averages (for site vs sector comparison)
        sector_avg = pd.read_sql_query(f"""
            SELECT dss.date,
                   AVG(dss.total_daily_used) as sector_fuel,
                   AVG(dss.total_gen_run_hr) as sector_gen_hr,
                   AVG(dss.days_of_buffer) as sector_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE s.sector_id = ?{dsql}
            GROUP BY dss.date ORDER BY dss.date
        """, conn, params=[site["sector_id"]] + dp)

    # Calculate derived fields
    pm = _price_map()
    price = pm.get(site["sector_id"], 0)

    if not daily.empty:
        daily["cost"] = daily["fuel"].fillna(0) * price
        daily["cumulative_fuel"] = daily["fuel"].fillna(0).cumsum()
        daily["efficiency"] = np.where(daily["gen_hr"] > 0, daily["fuel"] / daily["gen_hr"], 0)
        # 7-day moving average for anomaly detection
        daily["fuel_7d_ma"] = daily["fuel"].rolling(7, min_periods=1).mean()

    if not gen_daily.empty:
        gen_daily["expected"] = gen_daily["consumption_per_hour"].fillna(0) * gen_daily["gen_run_hr"].fillna(0)
        gen_daily["variance"] = gen_daily["daily_used_liters"].fillna(0) - gen_daily["expected"]
        gen_daily["cost"] = gen_daily["daily_used_liters"].fillna(0) * price

    # Aggregate by period (weekly/monthly)
    if period in ("weekly", "monthly") and not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"])
        freq = "W" if period == "weekly" else "ME"
        agg = daily.set_index("date").resample(freq).agg({
            "gen_hr": "sum", "fuel": "sum", "tank": "last", "buffer": "last",
            "blackout_hr": "sum", "num_generators_active": "max",
            "cost": "sum", "cumulative_fuel": "last", "efficiency": "mean", "fuel_7d_ma": "mean"
        }).reset_index()
        agg["date"] = agg["date"].dt.strftime("%Y-%m-%d")
        daily = agg

    if period in ("weekly", "monthly") and not sales_daily.empty:
        sales_daily["date"] = pd.to_datetime(sales_daily["date"])
        freq = "W" if period == "weekly" else "ME"
        sales_daily = sales_daily.set_index("date").resample(freq).agg({
            "sales": "sum", "margin": "sum"
        }).reset_index()
        sales_daily["date"] = sales_daily["date"].dt.strftime("%Y-%m-%d")

    if period in ("weekly", "monthly") and not sector_avg.empty:
        sector_avg["date"] = pd.to_datetime(sector_avg["date"])
        freq = "W" if period == "weekly" else "ME"
        sector_avg = sector_avg.set_index("date").resample(freq).agg({
            "sector_fuel": "mean", "sector_gen_hr": "mean", "sector_buffer": "mean"
        }).reset_index()
        sector_avg["date"] = sector_avg["date"].dt.strftime("%Y-%m-%d")

    # Merge daily + sales for diesel%
    merged = pd.DataFrame()
    if not daily.empty and not sales_daily.empty:
        merged = daily.merge(sales_daily, on="date", how="outer").sort_values("date")
        merged["diesel_pct"] = np.where(
            merged["sales"].fillna(0) > 0,
            merged["cost"].fillna(0) / merged["sales"] * 100, None
        )

    return {
        "site": dict(site),
        "fuel_price": price,
        "daily": _df(daily.round(2)),
        "generators": _df(gens.round(2)),
        "gen_daily": _df(gen_daily.round(2)),
        "sales_daily": _df(sales_daily.round(2)),
        "fuel_prices": _df(prices.round(2)),
        "sector_avg": _df(sector_avg.round(2)),
        "merged": _df(merged.round(2)) if not merged.empty else [],
        "has_sales": len(sales_daily) > 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1.3  GET /api/site/{site_id}/peak-hours
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/site/{site_id}/peak-hours")
def site_peak_hours(
    site_id: str,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        site = conn.execute("SELECT sector_id FROM sites WHERE site_id = ?", (site_id,)).fetchone()
        if not site:
            raise HTTPException(404, f"Site {site_id} not found")

        dsql_h, dp_h = _dsql("hs.date", date_from, date_to)
        hourly = pd.read_sql_query(f"""
            SELECT hs.date, hs.hour, SUM(hs.sales_amt) as sales, SUM(hs.trans_cnt) as transactions
            FROM hourly_sales hs
            WHERE hs.site_id = ?{dsql_h}
            GROUP BY hs.date, hs.hour
        """, conn, params=[site_id] + dp_h)

        # Get avg gen cost per hour for this site
        dsql_d, dp_d = _dsql("dss.date", date_from, date_to)
        gen_cost = conn.execute(f"""
            SELECT AVG(dss.total_daily_used) as avg_daily_fuel,
                   AVG(dss.total_gen_run_hr) as avg_daily_hr
            FROM daily_site_summary dss WHERE dss.site_id = ?{dsql_d}
        """, [site_id] + dp_d).fetchone()

    if hourly.empty:
        return {"heatmap": [], "has_data": False}

    pm = _price_map()
    price = pm.get(site["sector_id"], 0)
    avg_fuel = gen_cost["avg_daily_fuel"] if gen_cost and gen_cost["avg_daily_fuel"] else 0
    avg_hr = gen_cost["avg_daily_hr"] if gen_cost and gen_cost["avg_daily_hr"] else 1
    cost_per_hr = (avg_fuel / max(avg_hr, 1)) * price

    # Build 24x7 grid
    hourly["date_dt"] = pd.to_datetime(hourly["date"])
    hourly["dow"] = hourly["date_dt"].dt.dayofweek  # 0=Mon

    grid = hourly.groupby(["dow", "hour"]).agg(
        avg_sales=("sales", "mean"),
        avg_trans=("transactions", "mean"),
        count=("sales", "count"),
    ).reset_index()

    grid["cost_per_hr"] = cost_per_hr
    grid["profitability"] = np.where(cost_per_hr > 0, grid["avg_sales"] / cost_per_hr, 0)
    grid["status"] = grid["profitability"].apply(
        lambda p: "PEAK" if p > 3 else "PROFITABLE" if p > 1.5 else "MARGINAL" if p > 1 else "LOSING"
    )

    return {
        "heatmap": _df(grid.round(2)),
        "cost_per_hr": round(cost_per_hr, 0),
        "has_data": True,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1.4  GET /api/trends/rolling-sector
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/trends/rolling-sector")
def rolling_sector_trends(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        dsql, dp = _dsql("dss.date", date_from, date_to)
        df = pd.read_sql_query(f"""
            SELECT dss.date, s.sector_id,
                   SUM(dss.total_daily_used) as fuel,
                   SUM(dss.total_gen_run_hr) as gen_hr,
                   AVG(dss.days_of_buffer) as buffer,
                   AVG(dss.blackout_hr) as blackout
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1{dsql}
            GROUP BY dss.date, s.sector_id
            ORDER BY dss.date
        """, conn, params=dp)

        # Sales by date
        sales_q = """
            SELECT ds.date, COALESCE(s.sector_id, ds.sector_id) as sec_id,
                   SUM(ds.sales_amt) as sales
            FROM daily_sales ds
            LEFT JOIN site_sales_map m ON ds.sales_site_name = m.sales_site_name
            LEFT JOIN sites s ON m.site_id = s.site_id
            WHERE 1=1
        """
        sp = []
        if date_from:
            sales_q += " AND ds.date >= ?"; sp.append(date_from)
        if date_to:
            sales_q += " AND ds.date <= ?"; sp.append(date_to)
        sales_q += " GROUP BY ds.date, sec_id ORDER BY ds.date"
        sales = pd.read_sql_query(sales_q, conn, params=sp)
        if not sales.empty:
            sales = sales.rename(columns={"sec_id": "sector_id"})

    if df.empty:
        return {"sectors": {}}

    pm = _price_map()

    result = {}
    for sector in df["sector_id"].unique():
        sdf = df[df["sector_id"] == sector].copy().sort_values("date")
        sdf["efficiency"] = np.where(sdf["gen_hr"] > 0, sdf["fuel"] / sdf["gen_hr"], 0)
        sdf["cost"] = sdf["fuel"] * pm.get(sector, 0)

        # Rolling 3-day averages
        for col in ["fuel", "gen_hr", "buffer", "efficiency", "cost", "blackout"]:
            sdf[f"{col}_roll"] = sdf[col].rolling(3, min_periods=1).mean()

        # Merge sales
        if not sales.empty:
            ssales = sales[sales["sector_id"] == sector].copy()
            if not ssales.empty:
                sdf = sdf.merge(ssales[["date", "sales"]], on="date", how="left")
                sdf["sales_roll"] = sdf["sales"].rolling(3, min_periods=1).mean()
                sdf["diesel_pct"] = np.where(sdf["sales"].fillna(0) > 0, sdf["cost"] / sdf["sales"] * 100, None)
                sdf["diesel_pct_roll"] = sdf["diesel_pct"].rolling(3, min_periods=1).mean()

        result[sector] = _df(sdf.round(2))

    return {"sectors": result}


# ═══════════════════════════════════════════════════════════════════════════
# 1.5  GET /api/trends/lng-comparison
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/trends/lng-comparison")
def lng_comparison(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        dsql, dp = _dsql("dss.date", date_from, date_to)
        df = pd.read_sql_query(f"""
            SELECT s.site_type,
                   AVG(dss.total_gen_run_hr) as avg_gen_hr,
                   AVG(dss.total_daily_used) as avg_fuel,
                   AVG(dss.days_of_buffer) as avg_buffer,
                   AVG(dss.blackout_hr) as avg_blackout,
                   SUM(dss.total_daily_used) as total_fuel,
                   SUM(dss.total_gen_run_hr) as total_gen_hr,
                   COUNT(DISTINCT dss.site_id) as site_count
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1{dsql}
            GROUP BY s.site_type
        """, conn, params=dp)

    if df.empty:
        return []

    pm = _price_map()
    # Use average price across all sectors for comparison
    avg_price = sum(pm.values()) / len(pm) if pm else 0
    df["avg_cost"] = df["avg_fuel"] * avg_price
    df["efficiency"] = np.where(df["total_gen_hr"] > 0, df["total_fuel"] / df["total_gen_hr"], 0)

    return _df(df.round(2))


# ═══════════════════════════════════════════════════════════════════════════
# 1.6  GET /api/rankings/{metric}
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/rankings/{metric}")
def rankings(
    metric: str,
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = 15,
    user: dict = Depends(get_current_user),
):
    allowed = {"diesel_pct", "cost", "fuel_used", "gen_hours", "efficiency"}
    if metric not in allowed:
        raise HTTPException(400, f"Metric must be one of: {', '.join(allowed)}")

    # For last-day metrics (fuel_used, gen_hours, efficiency), use latest date
    latest = _latest_date()
    with get_db() as conn:
        if metric in ("fuel_used", "gen_hours", "efficiency"):
            dsql_d, dp = "", []
            if latest:
                dsql_d = " AND dss.date = ?"; dp = [latest]
            if sector:
                dsql_d += " AND s.sector_id = ?"; dp.append(sector)

            df = pd.read_sql_query(f"""
                SELECT dss.site_id, s.sector_id, s.site_name,
                       s.cost_center_code, s.region as site_code, s.segment_name,
                       s.cost_center_description, s.address_state, s.store_size,
                       s.latitude, s.longitude,
                       SUM(dss.total_daily_used) as fuel_used,
                       SUM(dss.total_gen_run_hr) as gen_hours
                FROM daily_site_summary dss
                JOIN sites s ON dss.site_id = s.site_id
                WHERE 1=1{dsql_d}
                GROUP BY dss.site_id
            """, conn, params=dp)

            if not df.empty:
                df["efficiency"] = np.where(df["gen_hours"] > 0, df["fuel_used"] / df["gen_hours"], 0)

        else:
            # diesel_pct and cost need full period
            dsql, dp = _dsql("dss.date", date_from, date_to)
            if sector:
                dsql += " AND s.sector_id = ?"; dp.append(sector)

            df = pd.read_sql_query(f"""
                SELECT dss.site_id, s.sector_id, s.site_name,
                       s.cost_center_code, s.region as site_code, s.segment_name,
                       s.cost_center_description, s.address_state, s.store_size,
                       s.latitude, s.longitude,
                       SUM(dss.total_daily_used) as total_liters,
                       SUM(dss.total_gen_run_hr) as total_gen_hr
                FROM daily_site_summary dss
                JOIN sites s ON dss.site_id = s.site_id
                WHERE 1=1{dsql}
                GROUP BY dss.site_id
            """, conn, params=dp)

            if not df.empty:
                pm = _price_map()
                df["cost"] = df.apply(lambda r: (r["total_liters"] or 0) * pm.get(r["sector_id"], 0), axis=1)

                # Get sales for diesel_pct
                sales = pd.read_sql_query("""
                    SELECT site_id, SUM(sales_amt) as total_sales
                    FROM daily_sales WHERE site_id IS NOT NULL
                    GROUP BY site_id
                """, conn)
                if not sales.empty:
                    df = df.merge(sales, on="site_id", how="left")
                    df["diesel_pct"] = np.where(
                        df["total_sales"].fillna(0) > 0,
                        df["cost"] / df["total_sales"] * 100, None
                    )
                else:
                    df["diesel_pct"] = None

    if df.empty:
        return []

    # Sort and limit
    sort_col = metric
    df = df.dropna(subset=[sort_col])
    df = df.nlargest(limit, sort_col)

    return _df(df.round(2))


# ═══════════════════════════════════════════════════════════════════════════
# 1.7  GET /api/operations/fleet-stats
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/operations/fleet-stats")
def fleet_stats(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        dsql, dp = _dsql("dss.date", date_from, date_to)

        # DOW patterns
        dow = pd.read_sql_query(f"""
            SELECT CASE CAST(strftime('%w', dss.date) AS INTEGER)
                       WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
                       WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri'
                       WHEN 6 THEN 'Sat' END as dow,
                   CAST(strftime('%w', dss.date) AS INTEGER) as dow_num,
                   AVG(dss.total_daily_used) as avg_fuel,
                   AVG(dss.total_gen_run_hr) as avg_gen_hr,
                   AVG(dss.blackout_hr) as avg_blackout
            FROM daily_site_summary dss
            WHERE 1=1{dsql}
            GROUP BY dow_num ORDER BY dow_num
        """, conn, params=dp)

        # Generator utilization
        utilization = pd.read_sql_query(f"""
            SELECT g.site_id, s.sector_id, g.model_name,
                   SUM(do.gen_run_hr) as total_run_hr,
                   COUNT(DISTINCT do.date) as active_days,
                   COUNT(DISTINCT dss.date) as total_days
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id AND do.gen_run_hr > 0
            LEFT JOIN daily_site_summary dss ON g.site_id = dss.site_id
            WHERE g.is_active = 1
            GROUP BY g.generator_id
            HAVING total_days > 0
        """, conn)

        # Theft/waste scores
        dsql2, dp2 = _dsql("do.date", date_from, date_to)
        waste = pd.read_sql_query(f"""
            SELECT do.site_id, s.sector_id,
                   AVG(do.daily_used_liters / NULLIF(do.gen_run_hr, 0)) as actual_lph,
                   AVG(g.consumption_per_hour) as rated_lph,
                   COUNT(*) as data_points
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            JOIN sites s ON do.site_id = s.site_id
            WHERE do.gen_run_hr > 0 AND do.daily_used_liters > 0
                  AND g.consumption_per_hour > 0{dsql2}
            GROUP BY do.site_id
            HAVING data_points >= 3
        """, conn, params=dp2)

    # Process utilization
    if not utilization.empty:
        utilization["utilization_pct"] = (utilization["active_days"] / utilization["total_days"].clip(lower=1) * 100).round(1)
        utilization = utilization.nlargest(15, "utilization_pct")

    # Process waste scores
    if not waste.empty:
        waste["waste_ratio"] = (waste["actual_lph"] / waste["rated_lph"].clip(lower=0.1)).round(2)
        waste["waste_score"] = ((waste["waste_ratio"] - 1).clip(lower=0) * 100).round(1)
        waste = waste[waste["waste_score"] > 5].nlargest(15, "waste_score")

    return {
        "dow_patterns": _df(dow.round(1)),
        "utilization": _df(utilization.round(1)),
        "waste_scores": _df(waste.round(2)),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1.8  GET /api/predictions/all
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/predictions/all")
def predictions_all(user: dict = Depends(get_current_user)):
    result = {
        "fuel_forecast": [], "efficiency_forecast": [], "buffer_forecast": [],
        "gen_hr_forecast": [], "cost_forecast": [], "blackout_forecast": [],
        "stockout": [], "purchase_volume": [],
    }

    with get_db() as conn:
        # Get last 30 days of daily aggregates for forecasting
        agg = pd.read_sql_query("""
            SELECT dss.date,
                   SUM(dss.total_daily_used) as fuel,
                   AVG(CASE WHEN dss.total_gen_run_hr > 0 THEN dss.total_daily_used / dss.total_gen_run_hr END) as efficiency,
                   AVG(dss.days_of_buffer) as buffer,
                   SUM(dss.total_gen_run_hr) as gen_hr,
                   AVG(dss.blackout_hr) as blackout
            FROM daily_site_summary dss
            GROUP BY dss.date ORDER BY dss.date
        """, conn)

        # Purchase volume by supplier
        purchase_vol = pd.read_sql_query("""
            SELECT supplier, SUM(quantity_liters) as total_liters,
                   COUNT(DISTINCT date) as purchase_days,
                   AVG(price_per_liter) as avg_price
            FROM fuel_purchases
            WHERE supplier IS NOT NULL AND quantity_liters > 0
            GROUP BY supplier ORDER BY total_liters DESC
        """, conn)

    if not agg.empty and len(agg) >= 7:
        pm = _price_map()
        avg_price = sum(pm.values()) / len(pm) if pm else 0

        # Simple 7-day forecast using exponential smoothing
        for col, key in [("fuel", "fuel_forecast"), ("efficiency", "efficiency_forecast"),
                         ("buffer", "buffer_forecast"), ("gen_hr", "gen_hr_forecast"),
                         ("blackout", "blackout_forecast")]:
            series = agg[col].dropna()
            if len(series) < 5:
                continue
            # Exponential smoothing alpha=0.3
            alpha = 0.3
            smoothed = series.iloc[-1]
            trend = (series.iloc[-1] - series.iloc[-4]) / 3 if len(series) >= 4 else 0
            forecasts = []
            last_date = pd.to_datetime(agg["date"].iloc[-1])
            for i in range(1, 8):
                smoothed = alpha * series.iloc[-1] + (1 - alpha) * smoothed
                val = smoothed + trend * i
                forecasts.append({
                    "date": (last_date + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
                    "value": round(max(0, val), 2),
                    "lower": round(max(0, val * 0.85), 2),
                    "upper": round(val * 1.15, 2),
                })
            result[key] = forecasts

        # Cost forecast = fuel forecast × avg price
        if result["fuel_forecast"]:
            result["cost_forecast"] = [
                {**f, "value": round(f["value"] * avg_price, 0),
                 "lower": round(f["lower"] * avg_price, 0),
                 "upper": round(f["upper"] * avg_price, 0)}
                for f in result["fuel_forecast"]
            ]

    # Stockout: sites projected to run out
    try:
        from models.buffer_predictor import get_critical_sites
        stockout_df = get_critical_sites(threshold_days=7)
        result["stockout"] = _df(stockout_df)
    except Exception:
        pass

    result["purchase_volume"] = _df(purchase_vol.round(0))

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 1.9  GET /api/whatif
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/whatif")
def whatif_simulator(
    sales_change_pct: float = Query(0, description="Sales change %"),
    consumption_change_pct: float = Query(0, description="Fuel consumption change %"),
    price_change_pct: float = Query(0, description="Fuel price change %"),
    target_days: int = Query(7, description="Target buffer days"),
    user: dict = Depends(get_current_user),
):
    from models.decision_engine import run_what_if, get_weekly_budget_forecast

    # Run the existing what-if
    wi = run_what_if(
        price_change_pct=price_change_pct,
        consumption_change_pct=consumption_change_pct,
    )

    # Add buffer projection
    with get_db() as conn:
        latest = pd.read_sql_query("""
            SELECT dss.site_id, dss.spare_tank_balance, dss.total_daily_used, dss.days_of_buffer
            FROM daily_site_summary dss
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
        """, conn)

    buffer_result = {"feasible": True, "avg_buffer": 0, "sites_below_target": 0}
    if not latest.empty:
        new_usage = latest["total_daily_used"].fillna(0) * (1 + consumption_change_pct / 100)
        new_buffer = latest["spare_tank_balance"].fillna(0) / new_usage.clip(lower=0.1)
        buffer_result["avg_buffer"] = round(new_buffer.mean(), 1)
        buffer_result["sites_below_target"] = int((new_buffer < target_days).sum())
        buffer_result["feasible"] = buffer_result["sites_below_target"] < len(latest) * 0.3

    wi["buffer_projection"] = buffer_result
    wi["target_days"] = target_days

    return wi


# ═══════════════════════════════════════════════════════════════════════════
# 1.10  GET /api/sector-heatmap
# ═══════════════════════════════════════════════════════════════════════════

def _heatmap_icon(value, metric_key):
    """Return icon based on thresholds."""
    if value is None or pd.isna(value):
        return "⚪"
    cfg = HEATMAP_THRESHOLDS.get(metric_key, {})
    if cfg.get("reverse"):
        # Buffer: higher = better
        if value >= cfg.get("green_min", 7):
            return "🟢"
        if value >= cfg.get("yellow_min", 5):
            return "🟡"
        if value >= cfg.get("amber_min", 3):
            return "🟠"
        return "🔴"
    else:
        green_max = cfg.get("green_max")
        yellow_max = cfg.get("yellow_max")
        amber_max = cfg.get("amber_max")
        if green_max is not None and value <= green_max:
            return "🟢"
        if yellow_max is not None and value <= yellow_max:
            return "🟡"
        if amber_max is not None and value <= amber_max:
            return "🟠"
        return "🔴"


@router.get("/sector-heatmap")
def sector_heatmap(
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        dsql, dp = _dsql("dss.date", date_from, date_to)

        # Find latest date
        max_date_row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
        latest_date = max_date_row[0] if max_date_row else None

        # Per-sector: last day tank + last day stats
        df = pd.read_sql_query(f"""
            SELECT s.sector_id,
                   COUNT(DISTINCT dss.site_id) as total_sites,
                   SUM(dss.total_daily_used) as last_day_fuel,
                   SUM(dss.spare_tank_balance) as last_day_tank,
                   AVG(dss.total_gen_run_hr) as avg_gen_hr,
                   AVG(dss.blackout_hr) as avg_blackout,
                   SUM(CASE WHEN dss.days_of_buffer < 3 THEN 1 ELSE 0 END) as critical_count,
                   SUM(CASE WHEN dss.days_of_buffer >= 3 AND dss.days_of_buffer < 7 THEN 1 ELSE 0 END) as warning_count,
                   SUM(CASE WHEN dss.days_of_buffer >= 7 THEN 1 ELSE 0 END) as safe_count,
                   SUM(CASE WHEN dss.days_of_buffer IS NULL THEN 1 ELSE 0 END) as nodata_count
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = '{latest_date}'{dsql}
            GROUP BY s.sector_id
            ORDER BY s.sector_id
        """, conn, params=dp)

        # 3-day avg fuel per sector (for buffer calculation)
        avg3d_fuel = pd.read_sql_query(f"""
            SELECT s.sector_id,
                   SUM(dss.total_daily_used) / COUNT(DISTINCT dss.date) as avg_fuel_3d
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date >= date('{latest_date}', '-3 days') AND dss.date < '{latest_date}'{dsql}
            GROUP BY s.sector_id
        """, conn, params=dp)
        avg3d_map = {r["sector_id"]: r["avg_fuel_3d"] for _, r in avg3d_fuel.iterrows()} if not avg3d_fuel.empty else {}

        # Compute buffer = last day tank / 3d avg fuel
        if not df.empty:
            df["avg_fuel"] = df["sector_id"].map(avg3d_map).fillna(df["last_day_fuel"])
            df["avg_buffer"] = np.where(df["avg_fuel"].fillna(0) > 0,
                df["last_day_tank"].fillna(0) / df["avg_fuel"], None)

        # Latest fuel price per sector
        prices = pd.read_sql_query("""
            SELECT sector_id, price_per_liter
            FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
            HAVING date = MAX(date)
        """, conn)

        # Diesel % (if sales exist)
        diesel_pct = pd.read_sql_query(f"""
            SELECT s.sector_id,
                   SUM(dss.total_daily_used) as total_fuel,
                   SUM(ds.sales_amt) as total_sales
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            LEFT JOIN daily_sales ds ON dss.site_id = ds.site_id AND dss.date = ds.date
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
            GROUP BY s.sector_id
        """, conn)

    if df.empty:
        return []

    pm = {r["sector_id"]: r["price_per_liter"] for _, r in prices.iterrows()} if not prices.empty else {}
    dp_map = {}
    if not diesel_pct.empty:
        for _, r in diesel_pct.iterrows():
            price = pm.get(r["sector_id"], 0)
            fuel_cost = (r["total_fuel"] or 0) * price
            sales = r["total_sales"] or 0
            dp_map[r["sector_id"]] = round(fuel_cost / sales * 100, 2) if sales > 0 else None

    rows = []
    for _, r in df.iterrows():
        sid = r["sector_id"]
        price = pm.get(sid, 0)
        buffer = r["avg_buffer"]
        blackout = r["avg_blackout"]
        dpct = dp_map.get(sid)

        rows.append({
            "sector_id": sid,
            "total_sites": int(r["total_sites"]),
            "diesel_price": round(price, 0),
            "diesel_price_icon": _heatmap_icon(price, "diesel_price"),
            "blackout_hr": round(blackout, 1) if pd.notna(blackout) else None,
            "blackout_icon": _heatmap_icon(blackout, "blackout_hr"),
            "buffer_days": round(buffer, 1) if pd.notna(buffer) else None,
            "buffer_icon": _heatmap_icon(buffer, "buffer_days"),
            "diesel_pct": dpct,
            "diesel_pct_icon": _heatmap_icon(dpct, "expense_pct"),
            "critical": int(r["critical_count"]),
            "warning": int(r["warning_count"]),
            "safe": int(r["safe_count"]),
            "nodata": int(r["nodata_count"]),
            "avg_fuel": round(r["avg_fuel"], 0) if pd.notna(r["avg_fuel"]) else None,
            "avg_gen_hr": round(r["avg_gen_hr"], 1) if pd.notna(r["avg_gen_hr"]) else None,
        })

    return rows

"""Insights router — operating modes, delivery queue, BCP scores, alerts, fuel intel, recommendations."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
import numpy as np
import pandas as pd
from utils.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter()


def fmtN(v):
    """Format number for narrative: 1.5M, 36.8K, 6,541."""
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.1f}K"
    return f"{v:,.0f}"


def _df(df):
    """Convert a DataFrame (or None) to a list of dicts safe for JSON."""
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    return df.fillna("").to_dict(orient="records")


def _sanitize(obj):
    """Recursively replace NaN/Inf floats with 0 so JSON serialization never fails."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    # numpy scalar
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return 0
        return v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


# ---------- 1. Operating Modes ----------

@router.get("/operating-modes")
def operating_modes(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_operating_modes
        result = get_operating_modes()
        return {"modes": _df(result)}
    except Exception:
        return {"modes": []}


# ---------- 2. Delivery Queue ----------

@router.get("/delivery-queue")
def delivery_queue(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_delivery_queue
        result = get_delivery_queue()
        return {"queue": _df(result)}
    except Exception:
        return {"queue": []}


# ---------- 3. BCP Scores ----------

@router.get("/bcp-scores")
def bcp_scores(user: dict = Depends(get_current_user)):
    try:
        from models.bcp_engine import compute_bcp_scores, get_grade_distribution
        scores = compute_bcp_scores()
        distribution = get_grade_distribution()
        return {"scores": _df(scores), "distribution": distribution}
    except Exception:
        return {"scores": [], "distribution": {}}


# ---------- 4. Stockout Forecast ----------

@router.get("/stockout-forecast")
def stockout_forecast(user: dict = Depends(get_current_user)):
    try:
        from models.buffer_predictor import predict_buffer_depletion, get_critical_sites
        all_sites = predict_buffer_depletion()
        critical = get_critical_sites()
        return {"forecast": _df(all_sites), "critical": _df(critical)}
    except Exception:
        return {"forecast": [], "critical": []}


# ---------- 5. Recommendations ----------

@router.get("/recommendations")
def recommendations(user: dict = Depends(get_current_user)):
    try:
        recs = []
        with get_db() as conn:
            # Critical sites — buffer < 3 days
            crit = pd.read_sql_query(
                """SELECT site_id, buffer_days
                   FROM site_summary
                   WHERE buffer_days IS NOT NULL AND buffer_days < 3
                   ORDER BY buffer_days""",
                conn,
            )
            if not crit.empty:
                recs.append({
                    "type": "critical",
                    "title": "Critical Buffer Sites",
                    "message": f"{len(crit)} site(s) have less than 3 days of fuel buffer remaining.",
                    "sites": crit["site_id"].tolist(),
                })

            # Burn spikes — daily_used > 7-day avg * 1.3
            burn = pd.read_sql_query(
                """SELECT d.site_id, d.total_daily_used,
                          AVG(d2.total_daily_used) AS avg_7d
                   FROM daily_operations d
                   JOIN daily_operations d2
                        ON d2.site_id = d.site_id
                       AND d2.date BETWEEN date(d.date, '-7 days') AND d.date
                   WHERE d.date = (SELECT MAX(date) FROM daily_operations)
                   GROUP BY d.site_id
                   HAVING d.total_daily_used > avg_7d * 1.3""",
                conn,
            )
            if not burn.empty:
                recs.append({
                    "type": "warning",
                    "title": "Burn Rate Spike",
                    "message": f"{len(burn)} site(s) are burning fuel 30%+ above their 7-day average.",
                    "sites": burn["site_id"].tolist(),
                })

            # Rising diesel % sites
            diesel_pct = pd.read_sql_query(
                """SELECT s.site_id,
                          s.diesel_cost, s.total_sales
                   FROM site_summary s
                   WHERE s.total_sales > 0
                     AND (s.diesel_cost / s.total_sales) > 0.10
                   ORDER BY (s.diesel_cost / s.total_sales) DESC""",
                conn,
            )
            if not diesel_pct.empty:
                recs.append({
                    "type": "warning",
                    "title": "Rising Diesel % of Sales",
                    "message": f"{len(diesel_pct)} site(s) have diesel cost exceeding 10% of sales.",
                    "sites": diesel_pct["site_id"].tolist(),
                })

            # Efficiency anomalies
            eff = pd.read_sql_query(
                """SELECT site_id
                   FROM daily_operations
                   WHERE gen_hours > 0
                     AND (total_daily_used / gen_hours) > 50
                   GROUP BY site_id""",
                conn,
            )
            if not eff.empty:
                recs.append({
                    "type": "info",
                    "title": "Efficiency Anomalies",
                    "message": f"{len(eff)} site(s) show unusually high fuel consumption per generator hour.",
                    "sites": eff["site_id"].tolist(),
                })

        return {"recommendations": recs}
    except Exception:
        return {"recommendations": []}


# ---------- 6. Active Alerts ----------

@router.get("/alerts/active")
def active_alerts(
    severity: Optional[str] = Query(None),
    sector_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    try:
        from alerts.alert_engine import get_active_alerts
        result = get_active_alerts(severity=severity, sector_id=sector_id)
        records = _df(result)

        counts = {"critical": 0, "warning": 0, "info": 0}
        if isinstance(result, pd.DataFrame) and not result.empty:
            sev_counts = result["severity"].str.lower().value_counts().to_dict()
            for k in counts:
                counts[k] = sev_counts.get(k, 0)

        return {"alerts": records, "counts": counts}
    except Exception:
        return {"alerts": [], "counts": {"critical": 0, "warning": 0, "info": 0}}


# ---------- 7. Fuel Intel ----------

@router.get("/fuel-intel")
def fuel_intel(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_supplier_buy_signal, get_weekly_budget_forecast
        from models.fuel_price_forecast import forecast_fuel_price

        signal_result = get_supplier_buy_signal()
        budget_result = get_weekly_budget_forecast()

        raw_forecast = forecast_fuel_price()
        # Convert any DataFrames inside forecast result to lists
        forecast_result = {}
        if isinstance(raw_forecast, dict):
            for k, v in raw_forecast.items():
                if isinstance(v, pd.DataFrame):
                    forecast_result[k] = _df(v)
                else:
                    forecast_result[k] = v
        else:
            forecast_result = raw_forecast

        # Purchase log
        log = pd.DataFrame()
        try:
            with get_db() as conn:
                log = pd.read_sql_query(
                    """SELECT date, sector_id, supplier, fuel_type,
                              quantity_liters, price_per_liter
                       FROM fuel_purchases
                       ORDER BY date DESC LIMIT 50""",
                    conn,
                )
        except Exception:
            pass

        return {
            "buy_signal": signal_result,
            "weekly_budget": budget_result,
            "forecast": forecast_result,
            "purchase_log": _df(log),
        }
    except Exception:
        return {
            "buy_signal": {},
            "weekly_budget": {},
            "forecast": {},
            "purchase_log": [],
        }


# ---------- 8. Yesterday Comparison ----------

@router.get("/yesterday-comparison")
def yesterday_comparison(user: dict = Depends(get_current_user)):
    try:
        metrics = []
        with get_db() as conn:
            yesterday = pd.read_sql_query(
                """SELECT
                       SUM(total_daily_used) AS burn,
                       AVG(buffer_days) AS buffer,
                       SUM(total_daily_used * COALESCE(
                           (SELECT fp.price_per_liter
                            FROM fuel_purchases fp
                            WHERE fp.sector_id = d.sector_id
                              AND fp.date <= d.date
                            ORDER BY fp.date DESC LIMIT 1), 0)) AS cost,
                       SUM(blackout_hr) AS blackout_hr
                   FROM daily_operations d
                   WHERE d.date = (SELECT MAX(date) FROM daily_operations)""",
                conn,
            )

            avg_3d = pd.read_sql_query(
                """SELECT
                       SUM(total_daily_used) / COUNT(DISTINCT date) AS burn,
                       AVG(buffer_days) AS buffer,
                       SUM(total_daily_used * COALESCE(
                           (SELECT fp.price_per_liter
                            FROM fuel_purchases fp
                            WHERE fp.sector_id = d.sector_id
                              AND fp.date <= d.date
                            ORDER BY fp.date DESC LIMIT 1), 0))
                       / COUNT(DISTINCT date) AS cost,
                       SUM(blackout_hr) / COUNT(DISTINCT date) AS blackout_hr
                   FROM daily_operations d
                   WHERE d.date >= (
                       SELECT date(MAX(date), '-3 days') FROM daily_operations
                   )""",
                conn,
            )

        for col, label in [("burn", "BURN"), ("buffer", "BUFFER"),
                           ("cost", "COST"), ("blackout_hr", "BLACKOUT_HR")]:
            y_val = float(yesterday[col].iloc[0] or 0)
            a_val = float(avg_3d[col].iloc[0] or 0)
            if a_val:
                pct = round((y_val - a_val) / a_val * 100, 1)
            else:
                pct = 0.0
            direction = "up" if pct > 1 else "down" if pct < -1 else "flat"
            metrics.append({
                "name": label,
                "yesterday": round(y_val, 1),
                "avg_3d": round(a_val, 1),
                "pct_change": pct,
                "direction": direction,
            })

        return {"metrics": metrics}
    except Exception:
        return {"metrics": []}


# ---------- 8b. Period KPIs (Last Day + Last 3 Days) ----------

@router.get("/period-kpis")
def period_kpis(sector: Optional[str] = None, date_to: Optional[str] = None, user: dict = Depends(get_current_user)):
    """Return full KPI blocks for last day and last 3 days avg.
    If date_to is provided, use it as the latest date (from calendar filter).
    """
    try:
        with get_db() as conn:
            sector_sql = f"AND s.sector_id = '{sector}'" if sector else ""
            if date_to:
                # Use the provided end date, but find the actual max date <= date_to
                max_date = conn.execute(f"""
                    SELECT MAX(dss.date) FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id WHERE dss.date <= '{date_to}' {sector_sql}
                """).fetchone()[0]
            else:
                max_date = conn.execute(f"""
                    SELECT MAX(dss.date) FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id WHERE 1=1 {sector_sql}
                """).fetchone()[0]
            if not max_date:
                return {"last_day": None, "last_3d": None, "max_date": None}

            def _build_kpis(date_filter, label):
                df = pd.read_sql_query(f"""
                    SELECT dss.site_id, s.sector_id, dss.date,
                           dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer,
                           dss.total_gen_run_hr, dss.blackout_hr
                    FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id
                    WHERE {date_filter} {sector_sql}
                """, conn)
                if df.empty:
                    return None
                n_days = df["date"].nunique()
                n_sites = df["site_id"].nunique()
                # Generator count for these sites
                site_ids = df["site_id"].unique().tolist()
                if site_ids:
                    placeholders = ','.join(['?' for _ in site_ids])
                    n_gens = conn.execute(f"SELECT COUNT(*) FROM generators WHERE is_active=1 AND site_id IN ({placeholders})", site_ids).fetchone()[0]
                else:
                    n_gens = 0
                # Daily totals per date (for proper averaging)
                daily_totals = df.groupby("date").agg(
                    daily_tank=("spare_tank_balance", lambda x: x.fillna(0).sum()),
                    daily_fuel=("total_daily_used", lambda x: x.fillna(0).sum()),
                    daily_gen_hr=("total_gen_run_hr", lambda x: x.fillna(0).sum()),
                    daily_blackout=("blackout_hr", lambda x: x.fillna(0).sum()),
                ).reset_index()

                # For 1 day: tank = SUM of that day. For multi-day: AVG of daily totals
                tank = float(daily_totals["daily_tank"].mean()) if n_days > 1 else float(daily_totals["daily_tank"].sum())
                total_fuel = float(daily_totals["daily_fuel"].sum())
                burn = total_fuel / max(n_days, 1)
                buffer = tank / burn if burn > 0 else 0
                total_gen_hr = float(daily_totals["daily_gen_hr"].sum())
                gen_hr = total_gen_hr / max(n_days, 1)
                total_blackout = float(daily_totals["daily_blackout"].sum())
                latest = df.sort_values("date").groupby("site_id").last()
                crit = int((latest["days_of_buffer"] < 3).sum())
                warn = int(((latest["days_of_buffer"] >= 3) & (latest["days_of_buffer"] < 7)).sum())
                safe = int((latest["days_of_buffer"] >= 7).sum())
                no_data = n_sites - crit - warn - safe
                needed = latest[latest["days_of_buffer"] < 7].apply(
                    lambda r: max(0, 7 * (r["total_daily_used"] or 0) - (r["spare_tank_balance"] or 0)), axis=1
                ).sum() if not latest.empty else 0
                # Get fuel price
                price_row = conn.execute(
                    "SELECT AVG(price_per_liter) FROM fuel_purchases WHERE price_per_liter IS NOT NULL"
                ).fetchone()
                price = price_row[0] if price_row and price_row[0] else 0
                cost = burn * price
                # Sales
                sales_q = f"SELECT COALESCE(SUM(sales_amt),0) FROM daily_sales WHERE {date_filter.replace('dss.','').replace('s.','')}"
                try:
                    sales = conn.execute(sales_q).fetchone()[0] / max(n_days, 1)
                except Exception:
                    sales = 0
                diesel_pct = (cost / sales * 100) if sales > 0 else 0
                _bo_mean = df["blackout_hr"].mean() if "blackout_hr" in df.columns else 0
                blackout = 0 if (pd.isna(_bo_mean) or _bo_mean is None) else float(_bo_mean)
                # Critical sites list (for cockpit)
                crit_sites = []
                if not latest.empty:
                    crit_df = latest[latest["days_of_buffer"] < 3].sort_values("days_of_buffer")
                    for sid, r in crit_df.iterrows():
                        crit_sites.append({
                            "site_id": sid, "buffer": round(r["days_of_buffer"], 1),
                            "tank": round(r["spare_tank_balance"] or 0),
                            "burn": round(r["total_daily_used"] or 0),
                            "needed": round(max(0, 7 * (r["total_daily_used"] or 0) - (r["spare_tank_balance"] or 0))),
                        })
                # Efficiency
                efficiency = float(burn / gen_hr) if gen_hr > 0 else 0
                if pd.isna(efficiency): efficiency = 0
                # Total sites in system (for data quality)
                total_sites_q = f"SELECT COUNT(*) FROM sites s WHERE 1=1 {sector_sql}"
                total_sites_in_system = conn.execute(total_sites_q).fetchone()[0]
                sites_not_reported = total_sites_in_system - n_sites
                # Sites with missing tank
                tank_missing = int((latest["spare_tank_balance"].fillna(0) == 0).sum()) if not latest.empty else 0

                tank_per_site = round(tank / n_sites, 1) if n_sites > 0 else 0
                fuel_per_site = round(burn / n_sites, 1) if n_sites > 0 else 0
                blackout_per_site = round(total_blackout / n_sites / max(n_days, 1), 1) if n_sites > 0 else 0
                gen_hr_per_site = gen_hr / n_sites if n_sites > 0 else 0

                return {
                    "label": label, "date": max_date, "sites": n_sites, "days": n_days,
                    "generators": n_gens, "total_sites": total_sites_in_system,
                    "buffer": round(buffer, 1), "tank": round(tank), "burn": round(burn),
                    "needed": round(needed), "cost": round(cost), "gen_hr": round(gen_hr),
                    "total_gen_hr": round(total_gen_hr, 1),
                    "gen_hr_per_site": round(gen_hr_per_site, 1),
                    "total_fuel": round(total_fuel),
                    "fuel_per_site": round(fuel_per_site, 1),
                    "tank_per_site": round(tank_per_site),
                    "total_blackout": round(total_blackout, 1),
                    "blackout": round(blackout, 1) if blackout else 0,
                    "blackout_per_site": round(blackout_per_site, 1),
                    "efficiency": round(efficiency, 1),
                    "fuel_price": round(price),
                    "crit": crit, "warn": warn, "safe": safe, "no_data": max(no_data, 0),
                    "sales": round(sales), "diesel_pct": round(diesel_pct, 2),
                    "has_sales": sales > 0,
                    "critical_sites": crit_sites[:10],
                    "sites_not_reported": sites_not_reported,
                    "tank_missing": tank_missing,
                }

            last_day = _build_kpis(f"dss.date = '{max_date}'", "LATEST_DATA")
            last_3d = _build_kpis(f"dss.date >= date('{max_date}', '-3 days') AND dss.date < '{max_date}'", "PRIOR_3_DAYS_AVG")

            # Sector snapshot (for group view)
            sector_snapshot = []
            if not sector:
                try:
                    for sec_row in conn.execute("SELECT sector_id, sector_name FROM sectors ORDER BY sector_id").fetchall():
                        sid = sec_row[0]
                        sec_data = pd.read_sql_query(f"""
                            SELECT dss.site_id, dss.total_daily_used, dss.spare_tank_balance, dss.days_of_buffer, dss.blackout_hr
                            FROM daily_site_summary dss JOIN sites s ON dss.site_id = s.site_id
                            WHERE dss.date = '{max_date}' AND s.sector_id = '{sid}'
                        """, conn)
                        if sec_data.empty:
                            continue
                        s_tank = sec_data["spare_tank_balance"].fillna(0).sum()
                        s_burn = sec_data["total_daily_used"].fillna(0).sum()
                        s_buf = s_tank / s_burn if s_burn > 0 else 0
                        s_crit = int((sec_data["days_of_buffer"].fillna(0) < 3).sum())
                        s_bo = sec_data["blackout_hr"].mean() if "blackout_hr" in sec_data.columns else 0
                        # Get price for sector
                        s_price_row = conn.execute(f"SELECT price_per_liter FROM fuel_purchases WHERE sector_id='{sid}' AND price_per_liter IS NOT NULL ORDER BY date DESC LIMIT 1").fetchone()
                        s_price = s_price_row[0] if s_price_row else 0
                        s_cost = s_burn * s_price
                        # Sales
                        s_sales_row = conn.execute(f"SELECT COALESCE(SUM(sales_amt),0) FROM daily_sales WHERE date='{max_date}' AND sector_id='{sid}'").fetchone()
                        s_sales = s_sales_row[0] if s_sales_row else 0
                        s_dpct = (s_cost / s_sales * 100) if s_sales > 0 else -1
                        status = "🟢" if s_buf >= 7 else "🟡" if s_buf >= 3 else "🔴" if s_burn > 0 else "⚪"
                        sector_snapshot.append({
                            "sector": sid, "sites": len(sec_data), "buffer": round(s_buf, 1),
                            "burn": round(s_burn), "cost": round(s_cost), "blackout": round(s_bo or 0, 1),
                            "diesel_pct": round(s_dpct, 2) if s_dpct >= 0 else None,
                            "crit": s_crit, "status": status,
                        })
                except Exception:
                    pass

            # Operating mode counts
            op_modes = {"OPEN": 0, "MONITOR": 0, "REDUCE": 0, "CLOSE": 0}
            try:
                from models.decision_engine import get_operating_modes
                modes_df = get_operating_modes()
                if modes_df is not None and not modes_df.empty:
                    if sector:
                        modes_df = modes_df[modes_df.get("sector_id", pd.Series()) == sector] if "sector_id" in modes_df.columns else modes_df
                    for m in ["OPEN", "MONITOR", "REDUCE", "CLOSE"]:
                        col = "operating_mode" if "operating_mode" in modes_df.columns else "mode"
                        if col in modes_df.columns:
                            op_modes[m] = int((modes_df[col].str.upper() == m).sum())
            except Exception:
                pass

            # Recent daily totals for sparklines (4 days: 3 prior + latest)
            recent_daily = []
            try:
                rdf = pd.read_sql_query(f"""
                    SELECT dss.date,
                        SUM(dss.total_gen_run_hr) as gen_hr,
                        SUM(dss.total_daily_used) as fuel,
                        SUM(dss.spare_tank_balance) as tank,
                        SUM(dss.blackout_hr) as blackout,
                        COUNT(DISTINCT dss.site_id) as sites
                    FROM daily_site_summary dss
                    JOIN sites s ON dss.site_id = s.site_id
                    WHERE dss.date >= date('{max_date}', '-3 days') {sector_sql}
                    GROUP BY dss.date ORDER BY dss.date
                """, conn)
                for _, r in rdf.iterrows():
                    b = r["fuel"]
                    t = r["tank"] or 0
                    recent_daily.append({
                        "date": r["date"], "gen_hr": round(r["gen_hr"] or 0, 1),
                        "fuel": round(b or 0), "tank": round(t),
                        "blackout": round(r["blackout"] or 0, 1),
                        "buffer": round(t / b, 1) if b and b > 0 else 0,
                        "sites": int(r["sites"]),
                    })
            except Exception:
                pass

            # Story line — auto-generated narrative
            story = []
            if last_day:
                ld = last_day
                story.append(f"On {max_date}, {ld['sites']} sites reported with {fmtN(ld['tank'])}L fuel remaining ({ld['buffer']}d buffer).")
                if last_3d:
                    t3 = last_3d
                    bd = ld['buffer'] - t3['buffer']
                    if bd < -1:
                        story.append(f"Buffer dropped {abs(bd):.1f} days vs prior 3-day average — fuel is depleting faster than resupply.")
                    elif bd > 1:
                        story.append(f"Buffer improved by {bd:.1f} days vs prior 3 days — resupply is outpacing consumption.")
                    else:
                        story.append("Buffer is stable compared to prior 3 days.")
                if ld.get('crit', 0) > 0:
                    story.append(f"{ld['crit']} sites are CRITICAL (<3 days fuel) and need immediate delivery of {fmtN(ld.get('needed',0))}L.")
                if (ld.get('sites_not_reported', 0)) > 0:
                    story.append(f"{ld['sites_not_reported']} sites did not report — data may be incomplete.")
                gen_hr = ld.get('total_gen_hr', 0)
                if gen_hr > 0:
                    story.append(f"Generators ran {fmtN(gen_hr)} hours total, consuming {fmtN(ld.get('total_fuel', ld.get('burn',0)))}L of diesel at {fmtN(ld.get('efficiency',0))} L/Hr efficiency.")

        return _sanitize({
            "last_day": last_day, "last_3d": last_3d, "max_date": max_date,
            "sector_snapshot": sector_snapshot,
            "operating_modes": op_modes,
            "recent_daily": recent_daily,
            "story": story,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"last_day": None, "last_3d": None, "max_date": None}


# ---------- 9. Generator Risk ----------

@router.get("/generator-risk")
def generator_risk(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_generator_failure_risk
        result = get_generator_failure_risk()
        return {"generators": _df(result)}
    except Exception:
        return {"generators": []}


# ---------- 10. Site Mapping ----------

@router.get("/site-mapping")
def site_mapping(user: dict = Depends(get_current_user)):
    try:
        with get_db() as conn:
            mapped = pd.read_sql_query("""
                SELECT DISTINCT s.site_id, s.sector_id, s.site_name, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude,
                       COUNT(DISTINCT ds.date) as sales_days, SUM(ds.sales_amt) as total_sales
                FROM sites s
                JOIN daily_sales ds ON ds.site_id = s.site_id
                GROUP BY s.site_id ORDER BY s.sector_id, s.site_id
            """, conn)
            unmapped = pd.read_sql_query("""
                SELECT s.site_id, s.sector_id, s.site_name, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude
                FROM sites s
                WHERE s.site_id NOT IN (SELECT DISTINCT site_id FROM daily_sales WHERE site_id IS NOT NULL)
                ORDER BY s.sector_id, s.site_id
            """, conn)
        return {"mapped": _df(mapped), "unmapped": _df(unmapped), "mapped_count": len(mapped), "unmapped_count": len(unmapped)}
    except Exception:
        return {"mapped": [], "unmapped": [], "mapped_count": 0, "unmapped_count": 0}


# ---------- 11. Transfers ----------

@router.get("/transfers")
def transfers(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_resource_sharing_opportunities, get_load_optimization
        transfers = get_resource_sharing_opportunities()
        load_opt = get_load_optimization()
        return {"transfers": transfers if isinstance(transfers, list) else _df(transfers), "load_optimization": _df(load_opt)}
    except Exception:
        return {"transfers": [], "load_optimization": []}


# ---------- 12. Anomalies ----------

@router.get("/anomalies")
def anomalies(user: dict = Depends(get_current_user)):
    try:
        from models.decision_engine import get_consumption_anomalies
        anomalies = get_consumption_anomalies()
        return {"anomalies": _df(anomalies)}
    except Exception:
        return {"anomalies": []}


# ---------- 13. Break-Even ----------

@router.get("/break-even")
def break_even(user: dict = Depends(get_current_user)):
    try:
        with get_db() as conn:
            df = pd.read_sql_query("""
                SELECT s.site_id, s.sector_id, s.cost_center_code,
                       s.region as site_code, s.segment_name, s.cost_center_description,
                       s.address_state, s.store_size, s.latitude, s.longitude,
                       COALESCE(AVG(dss.total_daily_used), 0) as avg_daily_fuel,
                       COALESCE(sales.avg_sales, 0) as avg_daily_sales
                FROM sites s
                LEFT JOIN daily_site_summary dss ON s.site_id = dss.site_id
                LEFT JOIN (
                    SELECT site_id, AVG(sales_amt) as avg_sales
                    FROM daily_sales WHERE site_id IS NOT NULL
                    GROUP BY site_id
                ) sales ON s.site_id = sales.site_id
                GROUP BY s.site_id
            """, conn)

            # Get latest fuel price per sector
            prices = {}
            for row in conn.execute("SELECT sector_id, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL ORDER BY date DESC").fetchall():
                if row[0] not in prices:
                    prices[row[0]] = row[1]

        if not df.empty:
            df["fuel_price"] = df["sector_id"].map(prices).fillna(0)
            df["daily_cost"] = df["avg_daily_fuel"] * df["fuel_price"]
            df["diesel_pct"] = np.where(df["avg_daily_sales"] > 0, df["daily_cost"] / df["avg_daily_sales"] * 100, 0)
            df["recommendation"] = df["diesel_pct"].apply(lambda x: "CLOSE" if x > 30 else "REDUCE" if x > 15 else "MONITOR" if x > 5 else "OPEN")
            df = df.sort_values("diesel_pct", ascending=False)

        return {"sites": _df(df.round(2))}
    except Exception:
        return {"sites": []}


# ---------- 14. Sector Sites ----------

@router.get("/sector-sites")
def sector_sites(sector: Optional[str] = None, lookback: int = 3, user: dict = Depends(get_current_user)):
    """All sites with threshold indicators using N-day lookback for averages."""
    try:
        # Load formula settings
        import json
        with get_db() as conn:
            raw = conn.execute("SELECT value FROM app_settings WHERE key='formula_engine'").fetchone()
            if raw and raw[0]:
                try:
                    settings = json.loads(raw[0])
                    lookback = settings.get("lookback_days", lookback)
                except Exception:
                    pass

            sector_sql = f"AND s.sector_id = '{sector}'" if sector else ""

            # Get last N days of data (for averages) + last day tank (for buffer)
            df = pd.read_sql_query(f"""
                SELECT s.site_id, s.sector_id, s.site_name, s.site_type, s.company,
                       s.cost_center_code, s.region as site_code, s.segment_name,
                       s.cost_center_description, s.address_state, s.address_township,
                       s.store_size, s.channel, s.latitude, s.longitude,
                       avg_data.avg_fuel as daily_fuel,
                       last_data.spare_tank_balance as tank,
                       last_data.days_of_buffer as buffer_days,
                       avg_data.avg_gen_hr as gen_hr,
                       COALESCE(avg_data.avg_blackout, bo_all.avg_blackout_all) as blackout_hr,
                       avg_data.total_fuel,
                       avg_data.total_gen_hr,
                       avg_data.data_days
                FROM sites s
                LEFT JOIN (
                    SELECT site_id,
                           AVG(total_daily_used) as avg_fuel,
                           AVG(total_gen_run_hr) as avg_gen_hr,
                           AVG(CASE WHEN blackout_hr IS NOT NULL AND blackout_hr != '' THEN blackout_hr END) as avg_blackout,
                           SUM(total_daily_used) as total_fuel,
                           SUM(total_gen_run_hr) as total_gen_hr,
                           COUNT(DISTINCT date) as data_days
                    FROM daily_site_summary
                    WHERE date >= (SELECT date(MAX(date), '-{max(lookback-1, 0)} days') FROM daily_site_summary)
                    GROUP BY site_id
                ) avg_data ON s.site_id = avg_data.site_id
                LEFT JOIN (
                    SELECT site_id,
                           AVG(CASE WHEN blackout_hr IS NOT NULL AND blackout_hr > 0 THEN blackout_hr END) as avg_blackout_all
                    FROM daily_site_summary
                    GROUP BY site_id
                ) bo_all ON s.site_id = bo_all.site_id
                LEFT JOIN (
                    SELECT site_id, spare_tank_balance, days_of_buffer
                    FROM daily_site_summary
                    WHERE date = (SELECT MAX(date) FROM daily_site_summary)
                ) last_data ON s.site_id = last_data.site_id
                WHERE 1=1 {sector_sql}
                ORDER BY s.sector_id, s.site_id
            """, conn)

            # Get fuel prices per sector
            prices = {}
            for row in conn.execute("SELECT sector_id, price_per_liter FROM fuel_purchases WHERE price_per_liter IS NOT NULL ORDER BY date DESC").fetchall():
                if row[0] not in prices:
                    prices[row[0]] = row[1]

            # Get sales per site — total period
            sales = pd.read_sql_query("""
                SELECT site_id, SUM(sales_amt) as total_sales,
                       SUM(sales_amt) / COUNT(DISTINCT date) as daily_sales,
                       SUM(margin) as total_margin,
                       SUM(margin) / NULLIF(SUM(sales_amt), 0) * 100 as margin_pct_calc
                FROM daily_sales WHERE site_id IS NOT NULL
                GROUP BY site_id
            """, conn)

            # Get last day sales per site
            max_sales_date = conn.execute("SELECT MAX(date) FROM daily_sales WHERE site_id IS NOT NULL").fetchone()[0]
            last_day_sales = pd.DataFrame()
            avg3d_sales = pd.DataFrame()
            if max_sales_date:
                last_day_sales = pd.read_sql_query(f"""
                    SELECT site_id, sales_amt as last_day_sales, margin as last_day_margin
                    FROM daily_sales WHERE date = '{max_sales_date}' AND site_id IS NOT NULL
                """, conn)
                # 3D avg sales (3 days before last sales date)
                avg3d_sales = pd.read_sql_query(f"""
                    SELECT site_id,
                           AVG(sales_amt) as avg3d_sales,
                           AVG(margin) as avg3d_margin
                    FROM daily_sales
                    WHERE date >= date('{max_sales_date}', '-3 days') AND date < '{max_sales_date}'
                      AND site_id IS NOT NULL
                    GROUP BY site_id
                """, conn)

            # Get LY expense per site
            ly = pd.read_sql_query("SELECT cost_center_code, pct_on_sales FROM diesel_expense_ly", conn)

            # Load thresholds from settings
            thresholds = {"exp_open": 5, "exp_monitor": 15, "exp_reduce": 30, "exp_close": 60}
            if raw and raw[0]:
                try:
                    thresholds.update(json.loads(raw[0]).get("thresholds", {}))
                except Exception:
                    pass

            if not df.empty:
                df["price"] = df["sector_id"].map(prices).fillna(0)
                # Buffer = last day tank ÷ avg daily burn (N-day lookback)
                df["buffer_days"] = np.where(df["daily_fuel"].fillna(0) > 0,
                    df["tank"].fillna(0) / df["daily_fuel"], 0)
                df["daily_cost"] = (df["daily_fuel"].fillna(0) * df["price"]).round(0)
                df["total_cost"] = df["daily_cost"]

                if not sales.empty:
                    df = df.merge(sales, on="site_id", how="left")
                else:
                    df["total_sales"] = 0; df["daily_sales"] = 0; df["total_margin"] = 0

                if not last_day_sales.empty:
                    df = df.merge(last_day_sales, on="site_id", how="left")
                else:
                    df["last_day_sales"] = 0; df["last_day_margin"] = 0

                if not avg3d_sales.empty:
                    df = df.merge(avg3d_sales, on="site_id", how="left")
                else:
                    df["avg3d_sales"] = 0; df["avg3d_margin"] = 0

                # Last day fuel cost
                df["last_day_fuel_cost"] = df["daily_fuel"].fillna(0) * df["price"]
                # Avg 3D fuel cost (avg_fuel is already N-day avg from query)
                df["avg3d_fuel_cost"] = df["daily_fuel"].fillna(0) * df["price"]

                # Exp% calculations
                df["exp_pct"] = np.where(df["daily_sales"].fillna(0) > 0,
                    df["daily_cost"] / df["daily_sales"] * 100, 0)
                df["exp_pct_last_day"] = np.where(df["last_day_sales"].fillna(0) > 0,
                    df["last_day_fuel_cost"] / df["last_day_sales"] * 100, 0)
                df["exp_pct_3d"] = np.where(df["avg3d_sales"].fillna(0) > 0,
                    df["avg3d_fuel_cost"] / df["avg3d_sales"] * 100, 0)
                df["exp_pct_total"] = np.where(df["total_sales"].fillna(0) > 0,
                    (df["total_fuel"].fillna(0) * df["price"]) / df["total_sales"] * 100, 0)

                # Margin
                df["margin_pct"] = np.where(df["total_sales"].fillna(0) > 0,
                    df["total_margin"].fillna(0) / df["total_sales"] * 100, 0)
                df["margin_pct_last_day"] = np.where(df["last_day_sales"].fillna(0) > 0,
                    df["last_day_margin"].fillna(0) / df["last_day_sales"] * 100, 0)
                df["margin_pct_3d"] = np.where(df["avg3d_sales"].fillna(0) > 0,
                    df["avg3d_margin"].fillna(0) / df["avg3d_sales"] * 100, 0)

                # Operating mode using configurable thresholds
                t = thresholds
                df["action"] = df["exp_pct"].apply(
                    lambda x: "CLOSE" if x > t.get("exp_close", 60) else "REDUCE" if x > t.get("exp_reduce", 30) else "MONITOR" if x > t.get("exp_monitor", 15) else "OPEN"
                )

                df = df.fillna(0).round(2)

        return {"sites": _df(df), "count": len(df)}
    except Exception as e:
        return {"sites": [], "count": 0}


# ---------- 16. Monthly Summary ----------

@router.get("/monthly-summary")
def monthly_summary(
    sector: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    try:
        with get_db() as conn:
            sq = " AND site_id IN (SELECT site_id FROM sites WHERE sector_id = ?)" if sector else ""
            sp = [sector] if sector else []
            months = pd.read_sql_query(f"""
                SELECT strftime('%Y-%m', date) as month,
                       SUM(total_daily_used) as fuel, COUNT(DISTINCT date) as days,
                       COUNT(DISTINCT site_id) as sites,
                       SUM(spare_tank_balance) as tank,
                       SUM(CASE WHEN days_of_buffer < 3 THEN 1 ELSE 0 END) as crit_days
                FROM daily_site_summary WHERE 1=1{sq}
                GROUP BY month ORDER BY month DESC LIMIT 6
            """, conn, params=sp)

            bo = pd.read_sql_query(f"""
                SELECT strftime('%Y-%m', do.date) as month, AVG(do.blackout_hr) as avg_bo
                FROM daily_operations do
                WHERE do.blackout_hr IS NOT NULL{' AND do.site_id IN (SELECT site_id FROM sites WHERE sector_id = ?)' if sector else ''}
                GROUP BY month
            """, conn, params=sp)

        if months.empty:
            return []

        bo_map = dict(zip(bo["month"], bo["avg_bo"])) if not bo.empty else {}
        result = []
        for _, r in months.iterrows():
            m = r["month"]
            fuel = float(r["fuel"] or 0)
            days = int(r["days"] or 1)
            burn = fuel / days
            tank = float(r["tank"] or 0)
            buf = round(tank / max(burn, 1), 1)
            grade = "A" if buf > 10 else "B" if buf > 7 else "C" if buf > 5 else "D" if buf > 3 else "F"
            result.append({
                "month": m, "fuel": round(fuel), "days": days, "sites": int(r["sites"] or 0),
                "burn_per_day": round(burn), "blackout_hr": round(bo_map.get(m, 0), 1),
                "buffer": buf, "crit_days": int(r["crit_days"] or 0), "grade": grade,
            })
        return result
    except Exception:
        return []


# ---------- 17. Blackout Calendar ----------

@router.get("/blackout-calendar")
def blackout_calendar(
    sector: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    try:
        with get_db() as conn:
            sq = " AND do.site_id IN (SELECT site_id FROM sites WHERE sector_id = ?)" if sector else ""
            sp = [sector] if sector else []
            df = pd.read_sql_query(f"""
                SELECT do.date, AVG(do.blackout_hr) as avg_bo
                FROM daily_operations do
                WHERE do.blackout_hr IS NOT NULL{sq}
                GROUP BY do.date ORDER BY do.date
            """, conn, params=sp)

        if df.empty:
            return {"days": []}

        return {"days": [{"date": r["date"], "avg_bo": round(float(r["avg_bo"]), 1)} for _, r in df.iterrows()]}
    except Exception:
        return {"days": []}


# ---------- 18. Ocean Cost Allocation ----------

@router.get("/ocean-cost-allocation")
def ocean_cost_allocation(user: dict = Depends(get_current_user)):
    """Calculate Ocean store diesel costs using Center data × Store Contribution %.
    Stand Alone: 100% from own data.
    Shopping Center: % of CP center's diesel cost."""
    try:
        import os
        from pathlib import Path

        with get_db() as conn:
            # Load Store Exp % file
            exp_path = None
            for p in [Path("Data/Store Exp Percentage of Center.xlsx"), Path("data/Store Exp Percentage of Center.xlsx")]:
                if p.exists():
                    exp_path = p; break
            if not exp_path:
                # Try parent dirs
                for p in [Path(__file__).parent.parent.parent / "Data" / "Store Exp Percentage of Center.xlsx"]:
                    if p.exists():
                        exp_path = p; break

            store_exp_map = {}
            if exp_path and exp_path.exists():
                se = pd.read_excel(str(exp_path), sheet_name='Sheet1')
                for _, r in se.iterrows():
                    scc = str(int(r["Store's Cost Center Code"])) if pd.notna(r["Store's Cost Center Code"]) and isinstance(r["Store's Cost Center Code"], (int,float)) else ''
                    ccc = str(int(r["Center's Cost Center Code"])) if pd.notna(r["Center's Cost Center Code"]) and isinstance(r["Center's Cost Center Code"], (int,float)) else ''
                    pct = r.get("Store Contribution  (%) to Center Expense", 1)
                    remark = r.get("Remark", "")
                    ccn = r.get("Center's Cost Center Name", "")
                    if scc:
                        store_exp_map[scc] = {"center_cc": ccc, "pct": pct if pd.notna(pct) else 1, "type": str(remark) if pd.notna(remark) else "", "center_name": str(ccn) if pd.notna(ccn) else ""}

            # Get Ocean sites
            ocean_sites = pd.read_sql_query("SELECT site_id, site_name, region as site_code FROM sites WHERE segment_name = 'Ocean'", conn)

            # Get fuel prices
            cmhl_price = 0
            r = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE sector_id='CMHL' AND price_per_liter>0 ORDER BY date DESC LIMIT 1").fetchone()
            if r: cmhl_price = r[0]
            cp_price = 0
            r = conn.execute("SELECT price_per_liter FROM fuel_purchases WHERE sector_id='CP' AND price_per_liter>0 ORDER BY date DESC LIMIT 1").fetchone()
            if r: cp_price = r[0]

            results = []
            for _, oc in ocean_sites.iterrows():
                oid = oc['site_id']
                exp = store_exp_map.get(oid, {})
                center_cc = exp.get("center_cc", "")
                pct = exp.get("pct", 1)
                etype = exp.get("type", "Stand Alone")
                center_name = exp.get("center_name", "")

                if not center_cc or pct >= 1 or etype == "Stand Alone":
                    # Stand alone — use own data
                    own = conn.execute("SELECT COALESCE(SUM(total_daily_used),0), COUNT(DISTINCT date) FROM daily_site_summary WHERE site_id=?", (oid,)).fetchone()
                    fuel = own[0] if own else 0
                    days = own[1] if own else 0
                    cost = fuel * cmhl_price
                    results.append({
                        "ocean_site": oid, "ocean_name": oc['site_name'], "site_code": oc.get('site_code',''),
                        "center_cc": oid, "center_name": oc['site_name'], "type": "Stand Alone",
                        "center_fuel": round(fuel), "center_cost": round(cost),
                        "pct": 1.0, "ocean_cost": round(cost),
                        "days": days, "price": cmhl_price,
                    })
                else:
                    # Shopping center — use CP center data × %
                    ctr = conn.execute("SELECT COALESCE(SUM(total_daily_used),0), COUNT(DISTINCT date) FROM daily_site_summary WHERE site_id=?", (center_cc,)).fetchone()
                    ctr_fuel = ctr[0] if ctr else 0
                    days = ctr[1] if ctr else 0
                    ctr_cost = ctr_fuel * cp_price
                    ocean_cost = ctr_cost * pct
                    results.append({
                        "ocean_site": oid, "ocean_name": oc['site_name'], "site_code": oc.get('site_code',''),
                        "center_cc": center_cc, "center_name": center_name, "type": "Shopping Center",
                        "center_fuel": round(ctr_fuel), "center_cost": round(ctr_cost),
                        "pct": round(pct, 4), "ocean_cost": round(ocean_cost),
                        "days": days, "price": cp_price,
                    })

            total_center = sum(r["center_cost"] for r in results)
            total_ocean = sum(r["ocean_cost"] for r in results)

            return {
                "stores": sorted(results, key=lambda x: x["ocean_cost"], reverse=True),
                "total_center_cost": total_center,
                "total_ocean_share": total_ocean,
                "cmhl_price": cmhl_price,
                "cp_price": cp_price,
            }
    except Exception as e:
        return {"stores": [], "total_center_cost": 0, "total_ocean_share": 0, "error": str(e)}


# ---------- 19. Site Info (enriched) ----------

@router.get("/site-info/{site_id}")
def site_info(site_id: str, user: dict = Depends(get_current_user)):
    """Get enriched site info including store master data."""
    try:
        with get_db() as conn:
            row = conn.execute("""
                SELECT s.*, sm.gold_code as sm_gold_code, sm.store_name as sm_store_name,
                       sm.segment_name as sm_segment, sm.channel as sm_channel,
                       d.yearly_expense_mmk_mil, d.daily_avg_expense_mmk, d.pct_on_sales
                FROM sites s
                LEFT JOIN store_master sm ON s.cost_center_code = sm.cost_center_code
                LEFT JOIN diesel_expense_ly d ON s.cost_center_code = d.cost_center_code
                WHERE s.site_id = ?
            """, (site_id,)).fetchone()
            if not row:
                return {}
            return dict(row)
    except Exception:
        return {}

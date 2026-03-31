"""
Decision Engine — All Tier 1-3 predictions and insights.

Tier 1: Operating Mode, Delivery Queue, Cost/Hr, Weekly Budget, Buy Signal
Tier 2: Generator Failure, Consumption Anomaly, Seasonal, Criticality, What-If
Tier 3: Resource Sharing, Load Optimization, Price Elasticity, Cold Chain, Recovery Time
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from utils.database import get_db
from config.settings import SECTORS, ALERTS


# ═══════════════════════════════════════════════════════════════════════════
# TIER 1 — Critical Daily Decisions
# ═══════════════════════════════════════════════════════════════════════════

def get_operating_modes():
    """
    T1.1: Recommend FULL / REDUCED / GENERATOR-ONLY / CLOSE for each site.
    Based on: buffer days + generator capacity + consumption rate.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.days_of_buffer,
                   dss.spare_tank_balance, dss.total_daily_used,
                   dss.total_gen_run_hr, dss.num_generators_active,
                   g.total_kva, g.total_gens
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            LEFT JOIN (
                SELECT site_id, SUM(power_kva) as total_kva, COUNT(*) as total_gens
                FROM generators WHERE is_active = 1 GROUP BY site_id
            ) g ON dss.site_id = g.site_id
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
        """, conn)

    if df.empty:
        return pd.DataFrame()

    def _mode(row):
        buf = row["days_of_buffer"]
        if buf is None or pd.isna(buf):
            return "UNKNOWN", "No buffer data", "#6b7280"
        if buf >= 7:
            return "FULL", f"{buf:.1f} days fuel — normal operations", "#16a34a"
        if buf >= 3:
            return "REDUCED", f"{buf:.1f} days — reduce operating hours, conserve fuel", "#d97706"
        if buf >= 1:
            return "GENERATOR_ONLY", f"{buf:.1f} days — essential services only, minimize gen usage", "#ea580c"
        return "CLOSE", f"{buf:.1f} days — recommend temporary closure, emergency fuel needed", "#dc2626"

    results = []
    for _, row in df.iterrows():
        mode, reason, color = _mode(row)
        results.append({
            **row.to_dict(),
            "mode": mode, "reason": reason, "color": color,
            "daily_fuel_cost": (row["total_daily_used"] or 0) * _get_latest_price(row["sector_id"]),
        })

    return pd.DataFrame(results).sort_values("days_of_buffer", na_position="last")


def get_delivery_queue():
    """
    T1.2: Prioritized fuel delivery queue with exact quantities needed.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.days_of_buffer,
                   dss.spare_tank_balance, dss.total_daily_used
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
              AND dss.days_of_buffer IS NOT NULL AND dss.days_of_buffer < 7
            ORDER BY dss.days_of_buffer ASC
        """, conn)

    if df.empty:
        return pd.DataFrame()

    target_buffer_days = 7
    df["liters_needed"] = ((target_buffer_days * df["total_daily_used"]) - df["spare_tank_balance"]).clip(lower=0).round(0)
    df["urgency"] = df["days_of_buffer"].apply(
        lambda x: "IMMEDIATE" if x < 1 else "TODAY" if x < 2 else "TOMORROW" if x < 3 else "THIS_WEEK"
    )
    df["delivery_by"] = df["days_of_buffer"].apply(
        lambda x: (datetime.now() + timedelta(days=max(0, x - 0.5))).strftime("%Y-%m-%d %H:%M")
    )
    df["est_cost"] = df.apply(
        lambda r: r["liters_needed"] * _get_latest_price(r["sector_id"]), axis=1
    ).round(0)

    return df


def get_cost_per_hour():
    """
    T1.3: Cost per hour of generator operation per site.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT g.site_id, s.sector_id, g.model_name,
                   g.consumption_per_hour, g.power_kva,
                   do.gen_run_hr, do.daily_used_liters
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
                AND do.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
            WHERE g.is_active = 1 AND g.consumption_per_hour > 0
        """, conn)

    if df.empty:
        return pd.DataFrame()

    df["price_per_liter"] = df["sector_id"].apply(_get_latest_price)
    df["cost_per_hour"] = (df["consumption_per_hour"] * df["price_per_liter"]).round(0)
    df["daily_cost"] = (df["gen_run_hr"].fillna(0) * df["cost_per_hour"]).round(0)

    return df.sort_values("cost_per_hour", ascending=False)


def get_weekly_budget_forecast():
    """
    T1.4: Forecast next week's total fuel cost across all sectors.
    """
    with get_db() as conn:
        # Average daily consumption per sector
        usage = pd.read_sql_query("""
            SELECT s.sector_id, AVG(dss.total_daily_used) as avg_daily_used,
                   SUM(dss.total_daily_used) as total_used, COUNT(DISTINCT dss.date) as days
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.total_daily_used > 0
            GROUP BY s.sector_id
        """, conn)

    if usage.empty:
        return {}

    results = []
    total_liters = 0
    total_cost = 0
    for _, row in usage.iterrows():
        daily_liters = row["avg_daily_used"]
        weekly_liters = daily_liters * 7
        price = _get_latest_price(row["sector_id"])
        weekly_cost = weekly_liters * price
        results.append({
            "sector_id": row["sector_id"],
            "avg_daily_liters": round(daily_liters, 0),
            "weekly_liters": round(weekly_liters, 0),
            "price_per_liter": price,
            "weekly_cost_mmk": round(weekly_cost, 0),
        })
        total_liters += weekly_liters
        total_cost += weekly_cost

    return {
        "sectors": results,
        "total_weekly_liters": round(total_liters, 0),
        "total_weekly_cost_mmk": round(total_cost, 0),
        "total_daily_cost_mmk": round(total_cost / 7, 0),
    }


def get_supplier_buy_signal():
    """
    T1.5: Compare suppliers and recommend buy/wait/switch.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT date, supplier, fuel_type,
                   AVG(price_per_liter) as price
            FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL AND supplier IS NOT NULL
            GROUP BY date, supplier, fuel_type
            ORDER BY date DESC
        """, conn)

    if df.empty:
        return {}

    suppliers = df["supplier"].unique()
    latest = df.groupby("supplier")["price"].first()
    avg_7d = df.groupby("supplier")["price"].mean()

    signals = []
    for sup in suppliers:
        sup_data = df[df["supplier"] == sup]
        current = sup_data["price"].iloc[0] if not sup_data.empty else 0
        avg = sup_data["price"].mean()
        trend = "RISING" if current > avg * 1.05 else "FALLING" if current < avg * 0.95 else "STABLE"

        signals.append({
            "supplier": sup,
            "current_price": round(current, 0),
            "avg_price": round(avg, 0),
            "trend": trend,
            "recommendation": "BUY NOW" if trend == "FALLING" or current < avg else "WAIT" if trend == "RISING" else "HOLD",
        })

    # Find cheapest
    if len(signals) >= 2:
        cheapest = min(signals, key=lambda x: x["current_price"])
        priciest = max(signals, key=lambda x: x["current_price"])
        savings_pct = round((priciest["current_price"] - cheapest["current_price"]) / priciest["current_price"] * 100, 1)
    else:
        cheapest = signals[0] if signals else {}
        savings_pct = 0

    return {"signals": signals, "cheapest": cheapest.get("supplier"), "savings_pct": savings_pct}


# ═══════════════════════════════════════════════════════════════════════════
# TIER 2 — Strategic Insights
# ═══════════════════════════════════════════════════════════════════════════

def get_generator_failure_risk():
    """
    T2.6: Predict generator failure based on cumulative run hours.
    Typical maintenance: every 500hr (minor), 2000hr (major).
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT g.site_id, s.sector_id, g.model_name, g.power_kva,
                   SUM(do.gen_run_hr) as total_hours,
                   COUNT(do.date) as days_tracked,
                   AVG(do.gen_run_hr) as avg_daily_hours
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
            WHERE g.is_active = 1
            GROUP BY g.generator_id
            HAVING total_hours > 0
        """, conn)

    if df.empty:
        return pd.DataFrame()

    def _risk(hours):
        if hours > 4000:
            return "HIGH", "Overdue for major service", "#dc2626"
        if hours > 2000:
            return "MEDIUM", "Major service approaching", "#d97706"
        if hours > 500:
            return "LOW", "Minor service may be due", "#16a34a"
        return "NONE", "Recently serviced", "#22c55e"

    df["risk_level"], df["maintenance_note"], df["color"] = zip(*df["total_hours"].apply(_risk))
    df["next_service_at"] = df["total_hours"].apply(
        lambda h: 500 if h < 500 else 2000 if h < 2000 else 4000 if h < 4000 else 6000
    )
    df["hours_until_service"] = df["next_service_at"] - df["total_hours"]
    df["days_until_service"] = (df["hours_until_service"] / df["avg_daily_hours"].clip(lower=0.1)).round(0)

    return df.sort_values("hours_until_service")


def get_consumption_anomalies():
    """
    T2.7: Sites using significantly more fuel than their 7-day average.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.date, dss.total_daily_used,
                   AVG(dss2.total_daily_used) as avg_7d
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            JOIN daily_site_summary dss2 ON dss.site_id = dss2.site_id
                AND dss2.date BETWEEN date(dss.date, '-7 days') AND dss.date
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
              AND dss.total_daily_used > 0
            GROUP BY dss.site_id
            HAVING dss.total_daily_used > avg_7d * 1.3
        """, conn)

    if df.empty:
        return pd.DataFrame()

    df["pct_above_avg"] = ((df["total_daily_used"] - df["avg_7d"]) / df["avg_7d"] * 100).round(1)
    df["excess_liters"] = (df["total_daily_used"] - df["avg_7d"]).round(0)
    df["possible_cause"] = df["pct_above_avg"].apply(
        lambda p: "Possible fuel leak or unauthorized use" if p > 100
        else "Extended generator run — likely prolonged outage" if p > 50
        else "Above average usage — monitor"
    )

    return df.sort_values("pct_above_avg", ascending=False)


def get_site_criticality_ranking():
    """
    T2.9: Rank sites by operational importance.
    Score = generator capacity (KVA) × usage consistency × buffer risk inverse.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id,
                   AVG(dss.total_daily_used) as avg_daily_used,
                   AVG(dss.total_gen_run_hr) as avg_gen_hours,
                   MIN(dss.days_of_buffer) as min_buffer,
                   g.total_kva, g.total_gens
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            LEFT JOIN (
                SELECT site_id, SUM(power_kva) as total_kva, COUNT(*) as total_gens
                FROM generators WHERE is_active = 1 GROUP BY site_id
            ) g ON dss.site_id = g.site_id
            GROUP BY dss.site_id
        """, conn)

    if df.empty:
        return pd.DataFrame()

    # Criticality score: higher = more critical to protect
    max_kva = df["total_kva"].max() or 1
    max_used = df["avg_daily_used"].max() or 1

    df["capacity_score"] = (df["total_kva"].fillna(0) / max_kva * 40).round(1)
    df["usage_score"] = (df["avg_daily_used"].fillna(0) / max_used * 30).round(1)
    df["risk_score"] = df["min_buffer"].apply(
        lambda b: 30 if b is None or pd.isna(b) or b < 3 else 20 if b < 7 else 10 if b < 14 else 0
    )
    df["criticality_score"] = (df["capacity_score"] + df["usage_score"] + df["risk_score"]).round(1)
    df["priority"] = pd.qcut(df["criticality_score"], q=3, labels=["STANDARD", "HIGH", "CRITICAL"],
                              duplicates="drop")

    return df.sort_values("criticality_score", ascending=False)


def run_what_if(price_change_pct=0, consumption_change_pct=0, close_sites=None):
    """
    T2.10: What-if scenario simulator.
    """
    budget = get_weekly_budget_forecast()
    if not budget:
        return {}

    base_cost = budget["total_weekly_cost_mmk"]
    base_liters = budget["total_weekly_liters"]

    new_liters = base_liters * (1 + consumption_change_pct / 100)
    # Recalculate with price change
    new_cost = 0
    for s in budget["sectors"]:
        new_price = s["price_per_liter"] * (1 + price_change_pct / 100)
        sector_liters = s["weekly_liters"] * (1 + consumption_change_pct / 100)
        new_cost += sector_liters * new_price

    savings = base_cost - new_cost

    return {
        "base_cost": round(base_cost, 0),
        "new_cost": round(new_cost, 0),
        "difference": round(savings, 0),
        "pct_change": round((new_cost - base_cost) / base_cost * 100, 1) if base_cost > 0 else 0,
        "base_liters": round(base_liters, 0),
        "new_liters": round(new_liters, 0),
    }


# ═══════════════════════════════════════════════════════════════════════════
# TIER 3 — Advanced Analytics
# ═══════════════════════════════════════════════════════════════════════════

def get_resource_sharing_opportunities():
    """
    T3.11: Find sites with excess fuel that could transfer to critical sites.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.days_of_buffer,
                   dss.spare_tank_balance, dss.total_daily_used
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
              AND dss.days_of_buffer IS NOT NULL
        """, conn)

    if df.empty:
        return []

    excess = df[df["days_of_buffer"] > 14].copy()  # Sites with >14 days
    critical = df[df["days_of_buffer"] < 3].copy()  # Sites needing fuel

    transfers = []
    for _, c in critical.iterrows():
        needed = max(0, 7 * (c["total_daily_used"] or 0) - (c["spare_tank_balance"] or 0))
        if needed <= 0:
            continue
        for _, e in excess.iterrows():
            transferable = (e["spare_tank_balance"] or 0) - 7 * (e["total_daily_used"] or 0)
            if transferable > 200:
                amount = min(needed, transferable)
                transfers.append({
                    "from_site": e["site_id"], "from_sector": e["sector_id"],
                    "from_buffer": round(e["days_of_buffer"], 1),
                    "to_site": c["site_id"], "to_sector": c["sector_id"],
                    "to_buffer": round(c["days_of_buffer"], 1),
                    "transfer_liters": round(amount, 0),
                    "saves_delivery": True,
                })
                needed -= amount
                if needed <= 0:
                    break

    return transfers


def get_load_optimization():
    """
    T3.12: For multi-generator sites, recommend optimal gen to run.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT g.site_id, s.sector_id, g.model_name, g.power_kva,
                   g.consumption_per_hour, COUNT(do.date) as active_days,
                   AVG(do.gen_run_hr) as avg_run_hr
            FROM generators g
            JOIN sites s ON g.site_id = s.site_id
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id AND do.gen_run_hr > 0
            WHERE g.is_active = 1 AND g.consumption_per_hour > 0
            GROUP BY g.generator_id
        """, conn)

    if df.empty:
        return pd.DataFrame()

    # Sites with multiple generators
    multi = df.groupby("site_id").filter(lambda x: len(x) > 1)
    if multi.empty:
        return pd.DataFrame()

    # For each site, rank gens by efficiency (kva per liter)
    multi["kva_per_liter"] = (multi["power_kva"].fillna(0) / multi["consumption_per_hour"]).round(2)
    multi["rank"] = multi.groupby("site_id")["kva_per_liter"].rank(ascending=False).astype(int)
    multi["recommendation"] = multi["rank"].apply(
        lambda r: "PRIMARY — most efficient" if r == 1 else "BACKUP — use for peak load" if r == 2 else "STANDBY"
    )

    # Calculate potential savings
    multi["savings_per_hour_liters"] = 0.0
    for site_id in multi["site_id"].unique():
        site_gens = multi[multi["site_id"] == site_id]
        rank1 = site_gens[site_gens["rank"] == 1]
        if rank1.empty:
            continue
        best = rank1.iloc[0]["consumption_per_hour"]
        worst = site_gens["consumption_per_hour"].max()
        savings = worst - best
        multi.loc[multi["site_id"] == site_id, "savings_per_hour_liters"] = round(savings, 1)

    return multi.sort_values(["site_id", "rank"])


def get_price_elasticity():
    """
    T3.13: Find the price crossover point between suppliers.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT date, supplier, AVG(price_per_liter) as price
            FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL AND supplier IS NOT NULL
            GROUP BY date, supplier
            ORDER BY date
        """, conn)

    if df.empty or df["supplier"].nunique() < 2:
        return {}

    suppliers = df["supplier"].unique()
    pivoted = df.pivot_table(index="date", columns="supplier", values="price")

    crossover_points = []
    for i in range(1, len(pivoted)):
        for s1 in suppliers:
            for s2 in suppliers:
                if s1 >= s2:
                    continue
                prev = pivoted.iloc[i-1]
                curr = pivoted.iloc[i]
                if pd.notna(prev.get(s1)) and pd.notna(prev.get(s2)) and pd.notna(curr.get(s1)) and pd.notna(curr.get(s2)):
                    if (prev[s1] - prev[s2]) * (curr[s1] - curr[s2]) < 0:
                        crossover_points.append({
                            "date": pivoted.index[i],
                            "suppliers": f"{s1} vs {s2}",
                            "prices": f"{curr[s1]:,.0f} vs {curr[s2]:,.0f}",
                        })

    return {
        "suppliers": {s: {"avg": round(df[df["supplier"]==s]["price"].mean(), 0),
                          "latest": round(df[df["supplier"]==s]["price"].iloc[-1], 0) if not df[df["supplier"]==s].empty else 0}
                      for s in suppliers},
        "crossover_points": crossover_points,
    }


def get_recovery_time_estimate():
    """
    T3.15: Estimate recovery time after power returns based on fuel level.
    """
    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id, dss.spare_tank_balance,
                   dss.total_daily_used, dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT date FROM daily_site_summary GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1)
        """, conn)

    if df.empty:
        return pd.DataFrame()

    def _recovery(row):
        balance = row["spare_tank_balance"] or 0
        if balance > 500:
            return "FAST", "2 hrs", "Enough fuel to restart immediately"
        if balance > 200:
            return "MODERATE", "4 hrs", "Can restart but needs resupply soon"
        if balance > 50:
            return "SLOW", "6-8 hrs", "Minimal fuel — needs delivery before full ops"
        return "DELAYED", "12+ hrs", "No fuel — waiting for emergency delivery"

    df["speed"], df["est_time"], df["note"] = zip(*df.apply(_recovery, axis=1))

    return df.sort_values("spare_tank_balance")


# ═══════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════

def _get_latest_price(sector_id):
    """Get latest fuel price for a sector."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT price_per_liter FROM fuel_purchases
            WHERE sector_id = ? AND price_per_liter IS NOT NULL
            ORDER BY date DESC LIMIT 1
        """, (sector_id,)).fetchone()
    if row:
        return row["price_per_liter"]
    # Fallback: any sector price
    with get_db() as conn:
        row = conn.execute("""
            SELECT AVG(price_per_liter) as p FROM fuel_purchases
            WHERE price_per_liter IS NOT NULL
        """).fetchone()
    return row["p"] if row and row["p"] else 7000  # Default fallback

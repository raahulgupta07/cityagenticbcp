"""
M4: BCP Score Engine
Weighted composite scoring per site.
  Fuel Reserve     35% — days of buffer
  Generator Coverage 30% — gen_run_hr / blackout_hr ratio
  Power Capacity   20% — site KVA vs sector median
  Operational Resilience 15% — consistency (low variance = good)
"""
import numpy as np
import pandas as pd
from utils.database import get_db
from config.settings import BCP_WEIGHTS, BCP_GRADES


def _fuel_score(days_of_buffer):
    """Convert days of buffer to 0-100 score."""
    if days_of_buffer is None or (isinstance(days_of_buffer, float) and np.isnan(days_of_buffer)):
        return 0
    if days_of_buffer <= 0:
        return 0
    if days_of_buffer >= 14:
        return 100
    if days_of_buffer >= 7:
        return 80 + (days_of_buffer - 7) / 7 * 20
    if days_of_buffer >= 5:
        return 60 + (days_of_buffer - 5) / 2 * 20
    if days_of_buffer >= 3:
        return 40 + (days_of_buffer - 3) / 2 * 20
    if days_of_buffer >= 1:
        return 20 + (days_of_buffer - 1) / 2 * 20
    return days_of_buffer / 1 * 20


def _coverage_score(gen_hr, blackout_hr):
    """Generator coverage: how well generators cover blackouts."""
    if blackout_hr is None or blackout_hr <= 0:
        return 80  # No blackout = decent score (can't be 100 without proving coverage)
    if gen_hr is None or gen_hr <= 0:
        return 0
    ratio = gen_hr / blackout_hr
    if ratio >= 1.0:
        return 100
    return min(ratio * 100, 100)


def _power_score(site_kva, sector_median_kva):
    """Power capacity relative to sector median."""
    if site_kva is None or site_kva <= 0:
        return 30  # Unknown = below average
    if sector_median_kva is None or sector_median_kva <= 0:
        return 50
    ratio = site_kva / sector_median_kva
    if ratio >= 1.5:
        return 100
    if ratio >= 1.0:
        return 67 + (ratio - 1.0) / 0.5 * 33
    if ratio >= 0.5:
        return 33 + (ratio - 0.5) / 0.5 * 34
    return ratio / 0.5 * 33


def _resilience_score(usage_values):
    """Operational resilience: consistency of daily usage (low CV = good)."""
    if usage_values is None or len(usage_values) < 2:
        return 50  # Insufficient data
    arr = [v for v in usage_values if v is not None and v > 0]
    if len(arr) < 2:
        return 50
    mean_val = np.mean(arr)
    if mean_val <= 0:
        return 50
    cv = np.std(arr) / mean_val  # Coefficient of variation
    if cv <= 0.15:
        return 100
    if cv <= 0.3:
        return 80
    if cv <= 0.5:
        return 60
    if cv <= 0.8:
        return 40
    return 20


def _grade(score):
    """Convert numeric score to letter grade."""
    for letter, info in sorted(BCP_GRADES.items()):
        if score >= info["min"]:
            result_grade = letter
    # Reverse check (A is highest)
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


def compute_bcp_scores(target_date=None):
    """
    Compute BCP scores for all sites.

    Returns DataFrame with:
        site_id, sector_id, bcp_score, grade, fuel_score, coverage_score,
        power_score, resilience_score, days_of_buffer, total_kva
    """
    with get_db() as conn:
        # Get latest date if not specified
        if not target_date:
            row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
            target_date = row[0] if row else None
        if not target_date:
            return pd.DataFrame()

        # Site summary for target date
        summaries = pd.read_sql_query("""
            SELECT dss.site_id, s.sector_id,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.spare_tank_balance, dss.blackout_hr, dss.days_of_buffer
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = ?
        """, conn, params=(target_date,))

        # Generator KVA per site
        kva = pd.read_sql_query("""
            SELECT site_id, SUM(COALESCE(power_kva, 0)) as total_kva
            FROM generators WHERE is_active = 1
            GROUP BY site_id
        """, conn)

        # Usage history for resilience (last 7 days)
        history = pd.read_sql_query("""
            SELECT site_id, date, total_daily_used
            FROM daily_site_summary
            WHERE date <= ? AND date >= date(?, '-7 days')
            ORDER BY site_id, date
        """, conn, params=(target_date, target_date))

    if summaries.empty:
        return pd.DataFrame()

    # Merge KVA
    summaries = summaries.merge(kva, on="site_id", how="left")
    summaries["total_kva"] = summaries["total_kva"].fillna(0)

    # Sector median KVA
    sector_kva_median = summaries.groupby("sector_id")["total_kva"].median().to_dict()

    # Usage history per site
    usage_by_site = history.groupby("site_id")["total_daily_used"].apply(list).to_dict()

    # Compute scores
    results = []
    for _, row in summaries.iterrows():
        sid = row["site_id"]
        sector = row["sector_id"]

        fuel = _fuel_score(row["days_of_buffer"])
        coverage = _coverage_score(row["total_gen_run_hr"], row["blackout_hr"])
        power = _power_score(row["total_kva"], sector_kva_median.get(sector, 0))
        resilience = _resilience_score(usage_by_site.get(sid, []))

        w = BCP_WEIGHTS
        composite = (
            fuel * w["fuel_reserve"] +
            coverage * w["generator_coverage"] +
            power * w["power_capacity"] +
            resilience * w["operational_resilience"]
        )
        composite = round(composite, 1)

        results.append({
            "site_id": sid,
            "sector_id": sector,
            "bcp_score": composite,
            "grade": _grade(composite),
            "fuel_score": round(fuel, 1),
            "coverage_score": round(coverage, 1),
            "power_score": round(power, 1),
            "resilience_score": round(resilience, 1),
            "days_of_buffer": row["days_of_buffer"],
            "total_kva": row["total_kva"],
        })

    return pd.DataFrame(results).sort_values("bcp_score", ascending=False)


def get_grade_distribution(target_date=None):
    """Count sites per grade."""
    df = compute_bcp_scores(target_date)
    if df.empty:
        return {}
    return df["grade"].value_counts().to_dict()


def get_at_risk_sites(threshold_grade="C", target_date=None):
    """Get sites with grade C or worse."""
    df = compute_bcp_scores(target_date)
    if df.empty:
        return df
    grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
    threshold_val = grade_order.get(threshold_grade, 3)
    return df[df["grade"].map(grade_order) <= threshold_val].sort_values("bcp_score")

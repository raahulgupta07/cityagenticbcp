"""
Alert Engine — 10 alert conditions with escalation rules.
Runs on every data update to generate/update alerts.
"""
import pandas as pd
from utils.database import get_db, create_alert
from config.settings import ALERTS


def run_all_checks(target_date=None):
    """
    Run all alert checks and create alert records.
    Returns dict of {check_name: alerts_created_count}.
    """
    with get_db() as conn:
        if not target_date:
            row = conn.execute("SELECT MAX(date) FROM daily_site_summary").fetchone()
            target_date = row[0] if row else None
        if not target_date:
            return {"error": "No data available"}

        # Clear old unacknowledged alerts for this date (prevent duplicates)
        conn.execute(
            "DELETE FROM alerts WHERE is_acknowledged = 0 AND created_at LIKE ?",
            (target_date + "%",)
        )

        results = {}
        results["buffer_critical"] = _check_buffer_critical(conn, target_date)
        results["buffer_warning"] = _check_buffer_warning(conn, target_date)
        results["price_spike"] = _check_price_spike(conn, target_date)
        results["high_blackout"] = _check_high_blackout(conn, target_date)
        results["generator_idle"] = _check_generator_idle(conn, target_date)
        results["efficiency_anomaly"] = _check_efficiency_anomaly(conn, target_date)
        results["missing_data"] = _check_missing_data(conn, target_date)
        results["sector_buffer_low"] = _check_sector_buffer_low(conn, target_date)

    return results


def _check_buffer_critical(conn, date):
    """A1: sites with < 3 days buffer."""
    threshold = ALERTS["buffer_critical_days"]
    rows = conn.execute("""
        SELECT dss.site_id, s.sector_id, dss.days_of_buffer
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        WHERE dss.date = ? AND dss.days_of_buffer IS NOT NULL
          AND dss.days_of_buffer < ?
    """, (date, threshold)).fetchall()

    for r in rows:
        create_alert(
            conn, "BUFFER_CRITICAL", "CRITICAL",
            f"{r['site_id']} has only {r['days_of_buffer']:.1f} days of fuel remaining",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["days_of_buffer"], threshold=threshold,
        )
    return len(rows)


def _check_buffer_warning(conn, date):
    """A2: sites with 3-7 days buffer."""
    low = ALERTS["buffer_critical_days"]
    high = ALERTS["buffer_warning_days"]
    rows = conn.execute("""
        SELECT dss.site_id, s.sector_id, dss.days_of_buffer
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        WHERE dss.date = ? AND dss.days_of_buffer IS NOT NULL
          AND dss.days_of_buffer >= ? AND dss.days_of_buffer < ?
    """, (date, low, high)).fetchall()

    for r in rows:
        create_alert(
            conn, "BUFFER_WARNING", "WARNING",
            f"{r['site_id']} has {r['days_of_buffer']:.1f} days of fuel — below 7-day threshold",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["days_of_buffer"], threshold=high,
        )
    return len(rows)


def _check_price_spike(conn, date):
    """A3/A4: price change > 10% (warning) or > 20% (critical) in 48hr."""
    rows = conn.execute("""
        SELECT fp1.sector_id, fp1.supplier, fp1.price_per_liter as current_price,
               fp2.price_per_liter as prev_price
        FROM fuel_purchases fp1
        JOIN fuel_purchases fp2
          ON fp1.sector_id = fp2.sector_id AND fp1.supplier = fp2.supplier
             AND fp1.fuel_type = fp2.fuel_type
        WHERE fp1.date = ? AND fp2.date = date(?, '-2 days')
          AND fp1.price_per_liter IS NOT NULL AND fp2.price_per_liter IS NOT NULL
          AND fp2.price_per_liter > 0
    """, (date, date)).fetchall()

    count = 0
    for r in rows:
        pct = (r["current_price"] - r["prev_price"]) / r["prev_price"] * 100
        if abs(pct) > ALERTS["price_surge_pct"]:
            create_alert(
                conn, "PRICE_SURGE", "CRITICAL",
                f"Fuel price surged {pct:+.1f}% in 48hr for {r['supplier']} ({r['sector_id']}): {r['prev_price']:,.0f} -> {r['current_price']:,.0f} MMK",
                sector_id=r["sector_id"],
                metric_value=pct, threshold=ALERTS["price_surge_pct"],
            )
            count += 1
        elif abs(pct) > ALERTS["price_spike_pct"]:
            create_alert(
                conn, "PRICE_SPIKE", "WARNING",
                f"Fuel price changed {pct:+.1f}% in 48hr for {r['supplier']} ({r['sector_id']})",
                sector_id=r["sector_id"],
                metric_value=pct, threshold=ALERTS["price_spike_pct"],
            )
            count += 1
    return count


def _check_high_blackout(conn, date):
    """A5: blackout > 8 hours at any site."""
    threshold = ALERTS["high_blackout_hr"]
    rows = conn.execute("""
        SELECT dss.site_id, s.sector_id, dss.blackout_hr
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        WHERE dss.date = ? AND dss.blackout_hr > ?
    """, (date, threshold)).fetchall()

    for r in rows:
        create_alert(
            conn, "HIGH_BLACKOUT", "CRITICAL",
            f"{r['site_id']} experienced {r['blackout_hr']:.1f} hours of blackout",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["blackout_hr"], threshold=threshold,
        )
    return len(rows)


def _check_generator_idle(conn, date):
    """A6: generators with 0 run hours for 3+ consecutive days."""
    threshold = ALERTS["generator_idle_days"]
    rows = conn.execute("""
        SELECT g.generator_id, g.model_name, g.site_id, s.sector_id,
               COUNT(*) as idle_days
        FROM daily_operations do
        JOIN generators g ON do.generator_id = g.generator_id
        JOIN sites s ON g.site_id = s.site_id
        WHERE do.date > date(?, '-' || ? || ' days')
          AND do.date <= ?
          AND (do.gen_run_hr IS NULL OR do.gen_run_hr = 0)
        GROUP BY g.generator_id
        HAVING idle_days >= ?
    """, (date, str(threshold), date, threshold)).fetchall()

    for r in rows:
        create_alert(
            conn, "GENERATOR_IDLE", "WARNING",
            f"{r['model_name']} at {r['site_id']} has been idle for {r['idle_days']} days",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["idle_days"], threshold=threshold,
        )
    return len(rows)


def _check_efficiency_anomaly(conn, date):
    """A7: efficiency ratio > 1.5 or < 0.5."""
    rows = conn.execute("""
        SELECT do.site_id, s.sector_id, g.model_name,
               do.daily_used_liters, g.consumption_per_hour, do.gen_run_hr,
               do.daily_used_liters / (g.consumption_per_hour * do.gen_run_hr) as ratio
        FROM daily_operations do
        JOIN generators g ON do.generator_id = g.generator_id
        JOIN sites s ON do.site_id = s.site_id
        WHERE do.date = ?
          AND do.gen_run_hr > 0 AND do.daily_used_liters > 0
          AND g.consumption_per_hour > 0
          AND (do.daily_used_liters / (g.consumption_per_hour * do.gen_run_hr) > ?
               OR do.daily_used_liters / (g.consumption_per_hour * do.gen_run_hr) < ?)
    """, (date, ALERTS["efficiency_high"], ALERTS["efficiency_low"])).fetchall()

    for r in rows:
        create_alert(
            conn, "EFFICIENCY_ANOMALY", "WARNING",
            f"{r['model_name']} at {r['site_id']} has abnormal efficiency ratio {r['ratio']:.2f} (expected 0.8-1.2)",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["ratio"],
        )
    return len(rows)


def _check_missing_data(conn, date):
    """A8: sites with no data for 2+ days."""
    threshold = ALERTS["missing_data_days"]
    rows = conn.execute("""
        SELECT s.site_id, s.sector_id,
               MAX(dss.date) as last_report,
               CAST(julianday(?) - julianday(MAX(dss.date)) AS INTEGER) as days_since
        FROM sites s
        LEFT JOIN daily_site_summary dss ON s.site_id = dss.site_id
        GROUP BY s.site_id
        HAVING days_since >= ? OR last_report IS NULL
    """, (date, threshold)).fetchall()

    for r in rows:
        days = r["days_since"] if r["days_since"] else "never"
        create_alert(
            conn, "MISSING_DATA", "INFO",
            f"{r['site_id']} has not reported data for {days} days",
            site_id=r["site_id"], sector_id=r["sector_id"],
            metric_value=r["days_since"],
        )
    return len(rows)


def _check_sector_buffer_low(conn, date):
    """A9: sector average buffer < 5 days."""
    threshold = ALERTS["sector_buffer_low_days"]
    rows = conn.execute("""
        SELECT s.sector_id, AVG(dss.days_of_buffer) as avg_buffer
        FROM daily_site_summary dss
        JOIN sites s ON dss.site_id = s.site_id
        WHERE dss.date = ? AND dss.days_of_buffer IS NOT NULL
        GROUP BY s.sector_id
        HAVING avg_buffer < ?
    """, (date, threshold)).fetchall()

    for r in rows:
        create_alert(
            conn, "SECTOR_BUFFER_LOW", "CRITICAL",
            f"Sector {r['sector_id']} average buffer is only {r['avg_buffer']:.1f} days",
            sector_id=r["sector_id"],
            metric_value=r["avg_buffer"], threshold=threshold,
        )
    return len(rows)


def get_active_alerts(severity=None, sector_id=None, acknowledged=False):
    """Get current alerts, optionally filtered."""
    with get_db() as conn:
        query = "SELECT * FROM alerts WHERE is_acknowledged = ?"
        params = [1 if acknowledged else 0]
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END, created_at DESC"
        return pd.read_sql_query(query, conn, params=params)


def acknowledge_alert(alert_id):
    """Mark an alert as acknowledged."""
    with get_db() as conn:
        conn.execute("UPDATE alerts SET is_acknowledged = 1 WHERE id = ?", (alert_id,))

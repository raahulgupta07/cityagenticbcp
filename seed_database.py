"""
One-time seed script: Parse all 4 Excel files into SQLite database.

Usage:
    cd CityBCPAgentv1
    python seed_database.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import EXCEL_FILES, EXCEL_DATA_DIR, SECTORS
from utils.database import (
    get_db, init_db, upsert_site, upsert_generator,
    upsert_daily_operation, insert_fuel_purchase,
    refresh_site_summary, log_upload,
)
from parsers.blackout_parser import parse_blackout_file
from parsers.fuel_price_parser import parse_fuel_price_file
from parsers.name_normalizer import normalize_generator_name


def seed_blackout_file(file_key, file_config):
    """Parse and seed one blackout file."""
    filepath = EXCEL_DATA_DIR / file_config["filename"]
    sector_id = file_config["sector_id"]

    print(f"\n{'='*60}")
    print(f"Parsing: {file_config['filename']} (Sector: {sector_id})")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  ERROR: File not found: {filepath}")
        return

    result = parse_blackout_file(filepath, sector_id)

    print(f"  Dates found: {result['dates_found']}")
    print(f"  Generators found: {len(result['generators'])}")
    print(f"  Daily data rows: {len(result['daily_data'])}")
    if result["errors"]:
        print(f"  ERRORS ({len(result['errors'])}):")
        for e in result["errors"][:10]:
            print(f"    - {e}")
    if result["warnings"]:
        print(f"  WARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"][:10]:
            print(f"    - {w}")

    # Write to database
    with get_db() as conn:
        # Log the upload
        dates = result["dates_found"]
        batch_id = log_upload(
            conn, file_config["filename"], file_key, sector_id,
            len(result["daily_data"]),
            len(result["daily_data"]) - len(result["errors"]),
            len(result["errors"]),
            min(dates) if dates else None,
            max(dates) if dates else None,
            result["errors"][:50] if result["errors"] else None,
        )

        # Upsert sites and generators
        gen_id_map = {}  # (site_id, model_name_raw) -> generator_id
        for gen in result["generators"]:
            upsert_site(conn, gen["site_id"], gen["site_name"],
                       sector_id, gen["site_type"])
            gen_id = upsert_generator(
                conn, gen["site_id"], gen["model_name"],
                gen["model_name_raw"], gen["power_kva"],
                gen["consumption_per_hour"], gen["fuel_type"], gen["supplier"],
            )
            gen_id_map[(gen["site_id"], gen["model_name_raw"])] = gen_id

        # Store name mappings
        for gen in result["generators"]:
            conn.execute("""
                INSERT OR IGNORE INTO generator_name_map (raw_name, canonical_name, auto_mapped)
                VALUES (?, ?, 1)
            """, (gen["model_name_raw"], gen["model_name"]))

        # Upsert daily operations
        sites_dates = set()
        for row in result["daily_data"]:
            gen_key = (row["site_id"], row["model_name_raw"])
            gen_id = gen_id_map.get(gen_key)
            if gen_id is None:
                continue
            upsert_daily_operation(
                conn, gen_id, row["site_id"], row["date"],
                row["gen_run_hr"], row["daily_used_liters"],
                row["spare_tank_balance"], row["blackout_hr"],
                source="excel", upload_batch_id=batch_id,
            )
            sites_dates.add((row["site_id"], row["date"]))

        # Refresh site summaries
        for site_id, date in sites_dates:
            refresh_site_summary(conn, site_id, date)

    print(f"  Database updated: {len(gen_id_map)} generators, {len(result['daily_data'])} daily rows")
    return result


def seed_fuel_prices():
    """Parse and seed fuel price file."""
    filepath = EXCEL_DATA_DIR / EXCEL_FILES["fuel_price"]["filename"]

    print(f"\n{'='*60}")
    print(f"Parsing: {EXCEL_FILES['fuel_price']['filename']}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  ERROR: File not found: {filepath}")
        return

    result = parse_fuel_price_file(filepath)

    print(f"  Purchase records found: {len(result['purchases'])}")
    if result["errors"]:
        print(f"  ERRORS: {result['errors'][:10]}")
    if result["warnings"]:
        print(f"  WARNINGS: {result['warnings'][:10]}")

    with get_db() as conn:
        # Clear existing fuel purchases from Excel (preserve manual entries)
        conn.execute("DELETE FROM fuel_purchases WHERE source = 'excel'")

        batch_id = log_upload(
            conn, EXCEL_FILES["fuel_price"]["filename"], "fuel_price", None,
            len(result["purchases"]), len(result["purchases"]), 0,
            None, None, None,
        )

        for p in result["purchases"]:
            insert_fuel_purchase(
                conn, p["sector_id"], p["date"], p["region"],
                p["supplier"], p["fuel_type"],
                p["quantity_liters"], p["price_per_liter"],
                source="excel", upload_batch_id=batch_id,
            )

    print(f"  Database updated: {len(result['purchases'])} fuel purchase records")
    return result


def verify_database():
    """Print database summary for verification."""
    print(f"\n{'='*60}")
    print("DATABASE VERIFICATION")
    print(f"{'='*60}")

    with get_db() as conn:
        tables = [
            ("sectors", "SELECT COUNT(*) FROM sectors"),
            ("sites", "SELECT COUNT(*) FROM sites"),
            ("generators", "SELECT COUNT(*) FROM generators"),
            ("daily_operations", "SELECT COUNT(*) FROM daily_operations"),
            ("fuel_purchases", "SELECT COUNT(*) FROM fuel_purchases"),
            ("daily_site_summary", "SELECT COUNT(*) FROM daily_site_summary"),
            ("generator_name_map", "SELECT COUNT(*) FROM generator_name_map"),
            ("upload_history", "SELECT COUNT(*) FROM upload_history"),
        ]
        for name, query in tables:
            count = conn.execute(query).fetchone()[0]
            print(f"  {name:25s} {count:>6d} rows")

        # Sites per sector
        print("\n  Sites per sector:")
        rows = conn.execute("""
            SELECT s.sector_id, COUNT(*) as cnt
            FROM sites s GROUP BY s.sector_id ORDER BY s.sector_id
        """).fetchall()
        for r in rows:
            print(f"    {r['sector_id']:10s} {r['cnt']:>4d} sites")

        # Generators per sector
        print("\n  Generators per sector:")
        rows = conn.execute("""
            SELECT si.sector_id, COUNT(*) as cnt
            FROM generators g JOIN sites si ON g.site_id = si.site_id
            GROUP BY si.sector_id ORDER BY si.sector_id
        """).fetchall()
        for r in rows:
            print(f"    {r['sector_id']:10s} {r['cnt']:>4d} generators")

        # Date range
        print("\n  Daily operations date range:")
        row = conn.execute("""
            SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as days
            FROM daily_operations
        """).fetchone()
        print(f"    {row['min_date']} to {row['max_date']} ({row['days']} days)")

        # Fuel purchases summary
        print("\n  Fuel purchases per sector:")
        rows = conn.execute("""
            SELECT sector_id, COUNT(*) as cnt,
                   MIN(date) as min_date, MAX(date) as max_date
            FROM fuel_purchases
            GROUP BY sector_id ORDER BY sector_id
        """).fetchall()
        for r in rows:
            print(f"    {r['sector_id']:10s} {r['cnt']:>4d} records ({r['min_date']} to {r['max_date']})")

        # Buffer status summary
        print("\n  Buffer status (latest date):")
        rows = conn.execute("""
            SELECT s.sector_id, dss.site_id, dss.days_of_buffer, dss.spare_tank_balance,
                   dss.total_daily_used
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.date = (SELECT MAX(date) FROM daily_site_summary)
            ORDER BY dss.days_of_buffer ASC NULLS LAST
            LIMIT 10
        """).fetchall()
        print(f"    {'Sector':<8} {'Site':<15} {'Buffer Days':>12} {'Tank (L)':>10} {'Used (L)':>10}")
        for r in rows:
            buf = f"{r['days_of_buffer']:.1f}" if r['days_of_buffer'] else "N/A"
            tank = f"{r['spare_tank_balance']:.0f}" if r['spare_tank_balance'] else "N/A"
            used = f"{r['total_daily_used']:.0f}" if r['total_daily_used'] else "0"
            print(f"    {r['sector_id']:<8} {r['site_id']:<15} {buf:>12} {tank:>10} {used:>10}")


def main():
    print("CityBCPAgent v1 — Database Seeding")
    print("=" * 60)

    # Initialize DB
    init_db()

    # Seed blackout files
    for key in ("blackout_cp", "blackout_cmhl", "blackout_cfc"):
        seed_blackout_file(key, EXCEL_FILES[key])

    # Seed fuel prices
    seed_fuel_prices()

    # Verify
    verify_database()

    print("\n" + "=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

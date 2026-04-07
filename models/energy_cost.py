"""
Store Economics Model — BCP sites as BASE, sales as LOOKUP.

Architecture:
    1. Start from 57 BCP sites (blackout Excel = base data)
    2. Calculate energy cost per site: daily_used_liters × fuel_price
    3. LOOKUP sales for matched sites only (site_sales_map)
    4. Calculate energy % of sales ONLY for matched sites

Core formulas:
    energy_cost = daily_used_liters × fuel_price_per_liter
    energy_pct  = (energy_cost / sales_value) × 100  (matched sites only)
"""
import pandas as pd
import numpy as np
from utils.database import get_db
from config.settings import ENERGY_COST, ENERGY_DECISION, SECTORS


# ═══════════════════════════════════════════════════════════════════════════
# CORE: Store Economics (BCP-first)
# ═══════════════════════════════════════════════════════════════════════════

def get_store_economics(date_from=None, date_to=None):
    """
    THE CORE FUNCTION. Starts from all BCP sites (base).
    For each site: energy cost. If mapped to sales: revenue, margin, energy %.

    Returns DataFrame:
        site_id, sector_id, site_name, num_generators,
        total_liters, total_gen_hours, energy_cost,
        energy_days, energy_start, energy_end, diesel_available,
        has_sales, total_sales, total_margin, sales_days, sales_start, sales_end,
        energy_pct (None if no sales), net_margin, date_remark,
        recommendation
    """
    with get_db() as conn:
        # 1. All BCP sites with energy data (BASE) — include date range + tank
        energy_q = """
            SELECT dss.site_id, s.sector_id, s.site_name,
                   s.business_sector, s.company, s.cost_center_code, s.site_type,
                   SUM(dss.total_daily_used) as total_liters,
                   SUM(dss.total_gen_run_hr) as total_gen_hours,
                   COUNT(DISTINCT dss.date) as energy_days,
                   MIN(dss.date) as energy_start,
                   MAX(dss.date) as energy_end,
                   SUM(dss.total_daily_used) * 1.0 / COUNT(DISTINCT dss.date) as avg_daily_liters,
                   MAX(CASE WHEN dss.date = (SELECT MAX(d2.date) FROM daily_site_summary d2 WHERE d2.site_id = dss.site_id)
                       THEN dss.spare_tank_balance END) as diesel_available,
                   -- Buffer placeholder (will be recalculated with blackout-based method)
                   NULL as latest_buffer_days
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1
        """
        params = []
        if date_from:
            energy_q += " AND dss.date >= ?"
            params.append(date_from)
        if date_to:
            energy_q += " AND dss.date <= ?"
            params.append(date_to)
        energy_q += " GROUP BY dss.site_id ORDER BY total_liters DESC"
        df = pd.read_sql_query(energy_q, conn, params=params)

        if df.empty:
            return df

        # Buffer = Tank ÷ (Last 7-day avg blackout hr × Rated L/hr)
        # Get last 7 days avg blackout per site + total rated consumption per site
        buffer_q = """
            SELECT sub.site_id,
                   sub.avg_bo_7d,
                   COALESCE(gc.total_rated_lph, 0) as total_rated_lph,
                   CASE WHEN sub.avg_bo_7d > 0 AND gc.total_rated_lph > 0 THEN
                       sub.avg_bo_7d * gc.total_rated_lph
                   ELSE 0 END as est_daily_burn
            FROM (
                SELECT bo.site_id,
                       SUM(bo.max_bo) * 1.0 / COUNT(DISTINCT bo.date) as avg_bo_7d
                FROM (
                    SELECT site_id, date, MAX(blackout_hr) as max_bo
                    FROM daily_operations
                    WHERE blackout_hr IS NOT NULL
                      AND date >= (SELECT date(MAX(date), '-6 days') FROM daily_site_summary)
                    GROUP BY site_id, date
                ) bo
                GROUP BY bo.site_id
            ) sub
            LEFT JOIN (
                SELECT site_id, SUM(consumption_per_hour) as total_rated_lph
                FROM generators WHERE is_active = 1
                GROUP BY site_id
            ) gc ON sub.site_id = gc.site_id
        """
        buf_df = pd.read_sql_query(buffer_q, conn)
        if not buf_df.empty:
            buf_map = dict(zip(buf_df["site_id"], buf_df["est_daily_burn"]))
            bo_map = dict(zip(buf_df["site_id"], buf_df["avg_bo_7d"]))
            df["est_daily_burn_bo"] = df["site_id"].map(buf_map).fillna(0)
            df["avg_blackout_7d"] = df["site_id"].map(bo_map).fillna(0)
            df["latest_buffer_days"] = df.apply(
                lambda r: round(r["diesel_available"] / r["est_daily_burn_bo"], 1)
                if pd.notna(r["diesel_available"]) and r["est_daily_burn_bo"] > 0
                else None, axis=1)
        else:
            df["est_daily_burn_bo"] = 0
            df["avg_blackout_7d"] = 0

        # 2. Generator count per site
        gen_counts = pd.read_sql_query("""
            SELECT site_id, COUNT(*) as num_generators
            FROM generators WHERE is_active = 1 GROUP BY site_id
        """, conn)

        # 3. Fuel price per sector
        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter)
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
        """).fetchall())

        # 4. Get energy date range (to match sales to same period)
        energy_dates = conn.execute("""
            SELECT MIN(date), MAX(date) FROM daily_site_summary
            WHERE total_daily_used > 0
        """).fetchone()
        e_min_date = energy_dates[0] if energy_dates else None
        e_max_date = energy_dates[1] if energy_dates else None

        # 5. Sales data — directly from daily_sales where site_id is resolved
        sales_q = """
            SELECT site_id,
                   SUM(sales_amt) as total_sales,
                   SUM(margin) as total_margin,
                   COUNT(DISTINCT date) as sales_days,
                   MIN(date) as sales_start,
                   MAX(date) as sales_end
            FROM daily_sales
            WHERE site_id IS NOT NULL
        """
        sales_params = []
        # Use energy date range (not full sales range)
        eff_from = date_from or e_min_date
        eff_to = date_to or e_max_date
        if eff_from:
            sales_q += " AND date >= ?"
            sales_params.append(eff_from)
        if eff_to:
            sales_q += " AND date <= ?"
            sales_params.append(eff_to)
        sales_q += " GROUP BY site_id"
        sales_df = pd.read_sql_query(sales_q, conn, params=sales_params)

    # 5. Merge generator counts
    df = pd.merge(df, gen_counts, on="site_id", how="left")
    df["num_generators"] = df["num_generators"].fillna(1).astype(int)

    # 6. Calculate energy cost
    df["energy_cost"] = df.apply(
        lambda r: (r["total_liters"] or 0) * price_map.get(r["sector_id"], 0), axis=1
    )

    # 7. Merge sales (LEFT JOIN — keeps all BCP sites)
    if not sales_df.empty:
        df = pd.merge(df, sales_df, on="site_id", how="left")
    else:
        df["total_sales"] = None
        df["total_margin"] = None
        df["sales_days"] = None
        df["sales_start"] = None
        df["sales_end"] = None

    # 8. Date mismatch remarks
    def _date_remark(row):
        e_days = row.get("energy_days", 0) or 0
        s_days = row.get("sales_days")
        if pd.isna(s_days) or s_days is None:
            return "No sales data"
        s_days = int(s_days)
        if e_days == s_days:
            return f"OK — {e_days} days aligned"
        elif e_days > s_days:
            return f"Sales missing {e_days - s_days} days"
        else:
            return f"Energy missing {s_days - e_days} days"

    df["date_remark"] = df.apply(_date_remark, axis=1)

    # 9. Calculate energy % (only for sites with sales)
    df["has_sales"] = df["total_sales"].notna() & (df["total_sales"] > 0)
    df["energy_pct"] = np.where(
        df["has_sales"],
        (df["energy_cost"] / df["total_sales"] * 100),
        None
    )
    df["net_margin"] = np.where(
        df["has_sales"],
        df["total_margin"] - df["energy_cost"],
        None
    )

    # 9. Recommendation
    df["recommendation"] = df.apply(_recommend, axis=1)

    return df.sort_values("energy_cost", ascending=False).round(2)


def get_generator_daily(site_id=None, sector_id=None, date_from=None, date_to=None):
    """
    Per-generator per-day detail for all sites or a specific site.
    Returns DataFrame: site_id, sector_id, model_name, power_kva, rated_L_hr,
                       date, gen_run_hr, daily_used_liters, spare_tank_balance, energy_cost
    """
    with get_db() as conn:
        query = """
            SELECT do.site_id, s.sector_id, g.model_name, g.power_kva,
                   g.consumption_per_hour as rated_L_hr,
                   do.date, do.gen_run_hr, do.daily_used_liters,
                   do.spare_tank_balance
            FROM daily_operations do
            JOIN generators g ON do.generator_id = g.generator_id
            JOIN sites s ON do.site_id = s.site_id
            WHERE 1=1
        """
        params = []
        if site_id:
            query += " AND do.site_id = ?"
            params.append(site_id)
        if sector_id:
            query += " AND s.sector_id = ?"
            params.append(sector_id)
        if date_from:
            query += " AND do.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND do.date <= ?"
            params.append(date_to)
        query += " ORDER BY do.site_id, g.model_name, do.date"
        df = pd.read_sql_query(query, conn, params=params)

        # Get fuel price per sector
        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter)
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
        """).fetchall())

    if not df.empty:
        df["energy_cost"] = df.apply(
            lambda r: (r["daily_used_liters"] or 0) * price_map.get(r["sector_id"], 0), axis=1
        )
    return df


def get_site_daily_summary(site_id=None, sector_id=None, date_from=None, date_to=None):
    """
    Aggregated site-level daily summary (all generators summed).
    Returns DataFrame: site_id, sector_id, date, total_gen_run_hr,
                       total_daily_used, spare_tank_balance, days_of_buffer,
                       num_generators_active, energy_cost
    """
    with get_db() as conn:
        query = """
            SELECT dss.site_id, s.sector_id, s.site_name, dss.date,
                   dss.total_gen_run_hr, dss.total_daily_used,
                   dss.spare_tank_balance, dss.days_of_buffer,
                   dss.num_generators_active
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE 1=1
        """
        params = []
        if site_id:
            query += " AND dss.site_id = ?"
            params.append(site_id)
        if sector_id:
            query += " AND s.sector_id = ?"
            params.append(sector_id)
        if date_from:
            query += " AND dss.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND dss.date <= ?"
            params.append(date_to)
        query += " ORDER BY dss.site_id, dss.date"
        df = pd.read_sql_query(query, conn, params=params)

        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter)
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
        """).fetchall())

    if not df.empty:
        df["energy_cost"] = df.apply(
            lambda r: (r["total_daily_used"] or 0) * price_map.get(r["sector_id"], 0), axis=1
        )
    return df


def get_trends(site_id=None, sector_id=None, period="daily",
               date_from=None, date_to=None, view="aggregated"):
    """
    Multi-period trend data for energy (and sales if mapped).

    Args:
        period: "hourly" | "daily" | "weekly" | "monthly"
        view: "aggregated" (site-level) | "generator" (per-machine)

    Returns dict:
        energy: DataFrame with period, values
        sales: DataFrame with period, values (if site is mapped)
        period_label: str for display
    """
    with get_db() as conn:
        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter)
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
        """).fetchall())

        # ─── ENERGY DATA ─────────────────────────────────────────
        if view == "generator":
            eq = """
                SELECT do.site_id, s.sector_id, g.model_name, g.power_kva,
                       do.date, do.gen_run_hr, do.daily_used_liters,
                       do.spare_tank_balance
                FROM daily_operations do
                JOIN generators g ON do.generator_id = g.generator_id
                JOIN sites s ON do.site_id = s.site_id WHERE 1=1
            """
        else:
            eq = """
                SELECT dss.site_id, s.sector_id, dss.date,
                       dss.total_gen_run_hr as gen_run_hr,
                       dss.total_daily_used as daily_used_liters,
                       dss.spare_tank_balance,
                       dss.num_generators_active
                FROM daily_site_summary dss
                JOIN sites s ON dss.site_id = s.site_id WHERE 1=1
            """
        ep = []
        if site_id:
            eq += f" AND {'do' if view == 'generator' else 'dss'}.site_id = ?"
            ep.append(site_id)
        if sector_id:
            eq += " AND s.sector_id = ?"
            ep.append(sector_id)
        if date_from:
            eq += f" AND {'do' if view == 'generator' else 'dss'}.date >= ?"
            ep.append(date_from)
        if date_to:
            eq += f" AND {'do' if view == 'generator' else 'dss'}.date <= ?"
            ep.append(date_to)
        eq += f" ORDER BY {'do' if view == 'generator' else 'dss'}.date"
        energy = pd.read_sql_query(eq, conn, params=ep)

        # ─── SALES DATA (hourly or daily) — direct by site_id ─────
        sales = pd.DataFrame()
        # Build WHERE clause for sales based on site_id directly
        sales_where = "site_id IS NOT NULL"
        sp = []
        if site_id:
            sales_where = "site_id = ?"
            sp = [site_id]
        elif sector_id:
            sales_where = "sector_id = ? AND site_id IS NOT NULL"
            sp = [sector_id]

        if period == "hourly":
            sq = f"""
                SELECT date, hour, SUM(sales_amt) as sales_amt, SUM(margin) as margin,
                       SUM(trans_cnt) as trans_cnt
                FROM hourly_sales
                WHERE {sales_where}
            """
            if date_from:
                sq += " AND date >= ?"
                sp.append(date_from)
            if date_to:
                sq += " AND date <= ?"
                sp.append(date_to)
            sq += " GROUP BY date, hour ORDER BY date, hour"
            sales = pd.read_sql_query(sq, conn, params=sp)
        else:
            sq = f"""
                SELECT date, SUM(sales_amt) as sales_amt, SUM(margin) as margin
                FROM daily_sales
                WHERE {sales_where}
            """
            if date_from:
                sq += " AND date >= ?"
                sp.append(date_from)
            if date_to:
                sq += " AND date <= ?"
                sp.append(date_to)
            sq += " GROUP BY date ORDER BY date"
            sales = pd.read_sql_query(sq, conn, params=sp)

    # ─── CALCULATE ENERGY COST ────────────────────────────────
    if not energy.empty:
        energy["energy_cost"] = energy.apply(
            lambda r: (r["daily_used_liters"] or 0) * price_map.get(r["sector_id"], 0), axis=1
        )

    # ─── AGGREGATE BY PERIOD ──────────────────────────────────
    period_label = period.capitalize()
    if period == "hourly":
        # Energy is daily — can't break down to hourly
        # Return daily energy + hourly sales
        return {
            "energy": energy,
            "sales": sales,
            "period_label": "Hourly (sales) / Daily (energy)",
            "period": period,
        }

    if period in ("weekly", "monthly"):
        if not energy.empty:
            energy["date"] = pd.to_datetime(energy["date"])
            if period == "weekly":
                energy["period"] = energy["date"].dt.to_period("W").apply(lambda x: str(x.start_time.date()))
            else:
                energy["period"] = energy["date"].dt.to_period("M").astype(str)

            if view == "generator":
                group_cols = ["period", "site_id", "sector_id", "model_name", "power_kva"]
                energy = energy.groupby(group_cols).agg(
                    gen_run_hr=("gen_run_hr", "sum"),
                    daily_used_liters=("daily_used_liters", "sum"),
                    spare_tank_balance=("spare_tank_balance", "max"),
                    energy_cost=("energy_cost", "sum"),
                    days=("date", "nunique"),
                ).reset_index()
            else:
                group_cols = ["period", "site_id", "sector_id"]
                extra = {}
                if "num_generators_active" in energy.columns:
                    extra["num_generators_active"] = ("num_generators_active", "max")
                energy = energy.groupby(group_cols).agg(
                    gen_run_hr=("gen_run_hr", "sum"),
                    daily_used_liters=("daily_used_liters", "sum"),
                    spare_tank_balance=("spare_tank_balance", "max"),
                    energy_cost=("energy_cost", "sum"),
                    days=("date", "nunique"),
                    **extra,
                ).reset_index()
            energy = energy.rename(columns={"period": "date"})

        if not sales.empty:
            sales["date"] = pd.to_datetime(sales["date"])
            if period == "weekly":
                sales["period"] = sales["date"].dt.to_period("W").apply(lambda x: str(x.start_time.date()))
            else:
                sales["period"] = sales["date"].dt.to_period("M").astype(str)
            sales = sales.groupby("period").agg(
                sales_amt=("sales_amt", "sum"),
                margin=("margin", "sum"),
                days=("date", "nunique"),
            ).reset_index()
            sales = sales.rename(columns={"period": "date"})

    return {
        "energy": energy.round(2) if not energy.empty else energy,
        "sales": sales.round(2) if not sales.empty else sales,
        "period_label": period_label,
        "period": period,
    }


def get_store_detail(site_id, date_from=None, date_to=None):
    """
    Deep dive for one BCP site:
    - Per-generator breakdown
    - Daily energy cost trend
    - If mapped: daily sales overlay
    """
    with get_db() as conn:
        # Site info
        site = conn.execute(
            "SELECT site_id, sector_id, site_name FROM sites WHERE site_id = ?", (site_id,)
        ).fetchone()
        if not site:
            return {"error": f"Site {site_id} not found"}

        sector = site["sector_id"]

        # Fuel price
        price_row = conn.execute(
            "SELECT AVG(price_per_liter) FROM fuel_purchases WHERE sector_id = ? AND price_per_liter IS NOT NULL",
            (sector,)
        ).fetchone()
        price = price_row[0] if price_row and price_row[0] else 0

        # Daily energy trend
        energy_q = """
            SELECT date, total_daily_used as liters, total_gen_run_hr as gen_hours,
                   spare_tank_balance, days_of_buffer
            FROM daily_site_summary WHERE site_id = ?
        """
        e_params = [site_id]
        if date_from:
            energy_q += " AND date >= ?"
            e_params.append(date_from)
        if date_to:
            energy_q += " AND date <= ?"
            e_params.append(date_to)
        energy_q += " ORDER BY date"
        energy_daily = pd.read_sql_query(energy_q, conn, params=e_params)

        # Check sales directly by site_id (no mapping table needed)
        sales_daily = pd.DataFrame()
        has_sales_check = conn.execute(
            "SELECT COUNT(*) FROM daily_sales WHERE site_id = ?", (site_id,)
        ).fetchone()[0]

        if has_sales_check > 0:
            sales_q = """
                SELECT date, SUM(sales_amt) as sales, SUM(margin) as margin
                FROM daily_sales WHERE site_id = ?
            """
            s_params = [site_id]
            if date_from:
                sales_q += " AND date >= ?"
                s_params.append(date_from)
            if date_to:
                sales_q += " AND date <= ?"
                s_params.append(date_to)
            sales_q += " GROUP BY date ORDER BY date"
            sales_daily = pd.read_sql_query(sales_q, conn, params=s_params)

    # Calculate energy cost in daily trend
    if not energy_daily.empty:
        energy_daily["energy_cost"] = energy_daily["liters"] * price

    # Merge daily if both exist
    daily_merged = pd.DataFrame()
    if not energy_daily.empty and not sales_daily.empty:
        daily_merged = pd.merge(energy_daily, sales_daily, on="date", how="outer").sort_values("date")
        daily_merged["energy_pct"] = np.where(
            daily_merged["sales"] > 0,
            (daily_merged["energy_cost"] / daily_merged["sales"] * 100),
            None
        )

    return {
        "site_id": site_id,
        "sector_id": sector,
        "site_name": site["site_name"],
        "fuel_price": price,
        "has_sales": has_sales_check > 0,
        "sales_site_name": site_id,
        "energy_daily": energy_daily,
        "sales_daily": sales_daily,
        "daily_merged": daily_merged,
    }


def get_store_decision_summary(date_from=None, date_to=None):
    """
    Summary for decision-makers: counts by recommendation.
    Returns dict with counts and lists.
    """
    df = get_store_economics(date_from=date_from, date_to=date_to)
    if df.empty:
        return {"total_sites": 0}

    matched = df[df["has_sales"] == True]
    unmatched = df[df["has_sales"] == False]

    summary = {
        "total_sites": len(df),
        "total_energy_cost": df["energy_cost"].sum(),
        "matched_sites": len(matched),
        "unmatched_sites": len(unmatched),
        "matched_total_sales": matched["total_sales"].sum() if not matched.empty else 0,
        "matched_total_energy": matched["energy_cost"].sum() if not matched.empty else 0,
        "matched_avg_energy_pct": matched["energy_pct"].mean() if not matched.empty else 0,
    }

    # Count by recommendation
    for rec in ["OPEN", "MONITOR", "REDUCE", "CLOSE", "NO SALES DATA"]:
        summary[f"count_{rec.lower().replace(' ', '_')}"] = len(df[df["recommendation"] == rec])

    return summary


# ═══════════════════════════════════════════════════════════════════════════
# MAPPING
# ═══════════════════════════════════════════════════════════════════════════

def auto_map_sites(mapping_file=None):
    """
    Populate site_sales_map using the official 'site location mapping.xlsx'.

    The mapping file has 3 columns:
        Manual Data     = BCP site name (from blackout Excel)
        SAP Cost Center = SAP name (used in sales data)
        SITE_CODE       = numeric code (not used for matching)

    For each row: BCP site_id (Manual Data) → sales_site_name (SAP Cost Center).
    Only maps if BOTH the BCP site exists in sites table AND the SAP name exists in daily_sales.

    Returns (matched_count, unmatched_count, details).
    """
    import os
    from pathlib import Path

    # Find mapping file
    if mapping_file is None:
        # Check common locations
        candidates = [
            Path(__file__).parent.parent / "Data" / "site location mapping.xlsx",
            Path(__file__).parent.parent.parent / "sales data" / "site location mapping.xlsx",
        ]
        for c in candidates:
            if c.exists():
                mapping_file = str(c)
                break

    if not mapping_file or not os.path.exists(mapping_file):
        return 0, 0, [], "Mapping file 'site location mapping.xlsx' not found. Upload it via Data Entry."

    # Read mapping file
    try:
        map_df = pd.read_excel(mapping_file)
    except Exception as e:
        return 0, 0, [], f"Error reading mapping file: {e}"

    # Expected columns: Manual Data, SAP Cost Center
    if "Manual Data" not in map_df.columns or "SAP Cost Center" not in map_df.columns:
        return 0, 0, [], "Mapping file must have 'Manual Data' and 'SAP Cost Center' columns."

    with get_db() as conn:
        # Get existing BCP sites
        bcp_sites = {r["site_id"].upper().strip(): r
                     for r in conn.execute("SELECT site_id, sector_id FROM sites").fetchall()}

        # Get existing sales site names
        sales_sites = {r[0].upper().strip(): r[0]
                       for r in conn.execute("SELECT DISTINCT sales_site_name FROM daily_sales").fetchall()}

        matched = []
        unmatched_rows = []

        for _, row in map_df.iterrows():
            bcp_name = str(row["Manual Data"]).strip()
            sap_name = str(row["SAP Cost Center"]).strip() if pd.notna(row["SAP Cost Center"]) else None
            bcp_upper = bcp_name.upper()

            # Check BCP site exists
            bcp_row = bcp_sites.get(bcp_upper)
            if not bcp_row:
                unmatched_rows.append({"bcp": bcp_name, "sap": sap_name, "reason": "BCP site not in database"})
                continue

            if not sap_name or sap_name == "nan":
                unmatched_rows.append({"bcp": bcp_name, "sap": None, "reason": "No SAP Cost Center in mapping"})
                continue

            # Find sales site name (try SAP name first, then BCP name)
            sales_name = sales_sites.get(sap_name.upper())
            if not sales_name:
                sales_name = sales_sites.get(bcp_upper)
            if not sales_name:
                unmatched_rows.append({"bcp": bcp_name, "sap": sap_name, "reason": "SAP name not in sales data"})
                continue

            # Insert mapping
            conn.execute("""
                INSERT INTO site_sales_map (sales_site_name, site_id, sector_id, match_method)
                VALUES (?, ?, ?, 'official_mapping')
                ON CONFLICT(sales_site_name) DO UPDATE SET
                    site_id = excluded.site_id,
                    sector_id = excluded.sector_id,
                    match_method = 'official_mapping'
            """, (sales_name, bcp_row["site_id"], bcp_row["sector_id"]))
            matched.append({
                "site_id": bcp_row["site_id"],
                "sales_site_name": sales_name,
                "sap_name": sap_name,
                "sector_id": bcp_row["sector_id"],
            })

    return len(matched), len(unmatched_rows), matched, unmatched_rows


def get_mapping_status():
    """Return current mapping status."""
    with get_db() as conn:
        total_bcp = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        total_mapped = conn.execute(
            "SELECT COUNT(*) FROM site_sales_map WHERE site_id IS NOT NULL"
        ).fetchone()[0]
        mappings = pd.read_sql_query("""
            SELECT m.site_id, m.sales_site_name, m.sector_id, m.match_method
            FROM site_sales_map m ORDER BY m.site_id
        """, conn)
    return {
        "total_bcp": total_bcp,
        "total_mapped": total_mapped,
        "total_unmapped": total_bcp - total_mapped,
        "mappings": mappings,
    }


# ═══════════════════════════════════════════════════════════════════════════
# KEPT FROM PREVIOUS (still useful)
# ═══════════════════════════════════════════════════════════════════════════

def get_site_energy_breakdown(sector_id=None, date_from=None, date_to=None):
    """Per-BCP-site energy cost breakdown. Sorted by energy_cost DESC."""
    with get_db() as conn:
        query = """
            SELECT dss.site_id, s.sector_id, s.site_name,
                   SUM(dss.total_daily_used) as total_liters,
                   SUM(dss.total_gen_run_hr) as total_gen_hours,
                   COUNT(DISTINCT dss.date) as days_tracked,
                   SUM(dss.total_daily_used) * 1.0 / COUNT(DISTINCT dss.date) as avg_daily_liters
            FROM daily_site_summary dss
            JOIN sites s ON dss.site_id = s.site_id
            WHERE dss.total_daily_used > 0
        """
        params = []
        if sector_id:
            query += " AND s.sector_id = ?"
            params.append(sector_id)
        if date_from:
            query += " AND dss.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND dss.date <= ?"
            params.append(date_to)
        query += " GROUP BY dss.site_id ORDER BY total_liters DESC"
        df = pd.read_sql_query(query, conn, params=params)
        if df.empty:
            return df
        gen_counts = pd.read_sql_query("""
            SELECT site_id, COUNT(*) as num_generators
            FROM generators WHERE is_active = 1 GROUP BY site_id
        """, conn)
        price_map = dict(conn.execute("""
            SELECT sector_id, AVG(price_per_liter)
            FROM fuel_purchases WHERE price_per_liter IS NOT NULL
            GROUP BY sector_id
        """).fetchall())
    df = pd.merge(df, gen_counts, on="site_id", how="left")
    df["num_generators"] = df["num_generators"].fillna(1).astype(int)
    df["energy_cost"] = df.apply(
        lambda r: (r["total_liters"] or 0) * price_map.get(r["sector_id"], 0), axis=1
    )
    return df.sort_values("energy_cost", ascending=False).round(2)


def get_generator_detail(site_id):
    """Per-generator breakdown for a specific BCP site."""
    with get_db() as conn:
        sector_row = conn.execute(
            "SELECT sector_id FROM sites WHERE site_id = ?", (site_id,)
        ).fetchone()
        sector = sector_row[0] if sector_row else None
        price = 0
        if sector:
            row = conn.execute(
                "SELECT AVG(price_per_liter) FROM fuel_purchases WHERE sector_id = ? AND price_per_liter IS NOT NULL",
                (sector,)
            ).fetchone()
            price = row[0] if row and row[0] else 0
        df = pd.read_sql_query("""
            SELECT g.model_name, g.power_kva, g.consumption_per_hour,
                   COALESCE(SUM(do.gen_run_hr), 0) as total_run_hrs,
                   COALESCE(SUM(do.daily_used_liters), 0) as total_liters,
                   COUNT(DISTINCT do.date) as days_tracked
            FROM generators g
            LEFT JOIN daily_operations do ON g.generator_id = do.generator_id
            WHERE g.site_id = ? AND g.is_active = 1
            GROUP BY g.generator_id, g.model_name, g.power_kva, g.consumption_per_hour
            ORDER BY total_liters DESC
        """, conn, params=(site_id,))
    if df.empty:
        return df
    df["energy_cost"] = df["total_liters"] * price
    df["expected_liters"] = df["consumption_per_hour"] * df["total_run_hrs"]
    df["efficiency_ratio"] = np.where(
        df["expected_liters"] > 0,
        (df["total_liters"] / df["expected_liters"] * 100).round(1), 0
    )
    return df.round(2)


def get_top_sales_sites(sector_id=None, date_from=None, date_to=None, limit=20):
    """Top sales sites by revenue from daily_sales."""
    with get_db() as conn:
        query = """
            SELECT sales_site_name, sector_id,
                   SUM(sales_amt) as total_sales, SUM(margin) as total_margin,
                   COUNT(DISTINCT date) as days
            FROM daily_sales WHERE sector_id IS NOT NULL
        """
        params = []
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        query += f" GROUP BY sales_site_name, sector_id ORDER BY total_sales DESC LIMIT {int(limit)}"
        df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["avg_daily_sales"] = (df["total_sales"] / df["days"]).round(0)
        df["margin_pct"] = np.where(
            df["total_sales"] > 0, (df["total_margin"] / df["total_sales"] * 100).round(1), 0
        )
    return df


def get_sales_summary():
    """Quick overview of sales data in the system."""
    with get_db() as conn:
        daily_count = conn.execute("SELECT COUNT(*) FROM daily_sales").fetchone()[0]
        hourly_count = conn.execute("SELECT COUNT(*) FROM hourly_sales").fetchone()[0]
        store_count = conn.execute("SELECT COUNT(*) FROM store_master").fetchone()[0]
        mapped_count = conn.execute("SELECT COUNT(*) FROM site_sales_map WHERE site_id IS NOT NULL").fetchone()[0]
        daily_range = conn.execute(
            "SELECT MIN(date), MAX(date), COUNT(DISTINCT sales_site_name), COUNT(DISTINCT sector_id) FROM daily_sales"
        ).fetchone()
        hourly_range = conn.execute(
            "SELECT MIN(date), MAX(date), COUNT(DISTINCT sales_site_name) FROM hourly_sales"
        ).fetchone()
        sector_sales = pd.read_sql_query("""
            SELECT sector_id, COUNT(DISTINCT sales_site_name) as sites,
                   SUM(sales_amt) as total_sales, SUM(margin) as total_margin,
                   COUNT(DISTINCT date) as days
            FROM daily_sales WHERE sector_id IS NOT NULL GROUP BY sector_id
        """, conn)
    return {
        "daily_records": daily_count, "hourly_records": hourly_count,
        "store_master_count": store_count, "mapped_sites": mapped_count,
        "daily_date_range": (daily_range[0], daily_range[1]) if daily_range[0] else None,
        "daily_sites": daily_range[2] if daily_range else 0,
        "daily_sectors": daily_range[3] if daily_range else 0,
        "hourly_date_range": (hourly_range[0], hourly_range[1]) if hourly_range and hourly_range[0] else None,
        "hourly_sites": hourly_range[2] if hourly_range else 0,
        "sector_sales": sector_sales,
    }


def get_hourly_sales_pattern(sector_id=None, date_from=None, date_to=None):
    """Hourly sales pattern — avg sales and transactions by hour."""
    with get_db() as conn:
        query = """
            SELECT hour, sector_id, AVG(sales_amt) as avg_sales,
                   SUM(sales_amt) as total_sales, AVG(trans_cnt) as avg_transactions,
                   COUNT(DISTINCT date) as days
            FROM hourly_sales WHERE sector_id IS NOT NULL
        """
        params = []
        if sector_id:
            query += " AND sector_id = ?"
            params.append(sector_id)
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        query += " GROUP BY hour, sector_id ORDER BY hour"
        return pd.read_sql_query(query, conn, params=params)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _recommend(row):
    """Per-store recommendation based on energy % of sales."""
    if not row.get("has_sales"):
        return "NO SALES DATA"
    pct = row.get("energy_pct")
    if pct is None or pd.isna(pct):
        return "NO SALES DATA"
    if pct <= ENERGY_DECISION["full_max_pct"]:
        return "OPEN"
    if pct <= ENERGY_DECISION["monitor_max_pct"]:
        return "MONITOR"
    if pct <= ENERGY_DECISION["reduce_max_pct"]:
        return "REDUCE"
    return "CLOSE"


def _get_status(energy_pct):
    """Return status label based on energy cost percentage."""
    if energy_pct <= ENERGY_COST["healthy_pct"]:
        return "HEALTHY"
    elif energy_pct <= ENERGY_COST["warning_pct"]:
        return "WARNING"
    elif energy_pct <= ENERGY_COST["critical_pct"]:
        return "CRITICAL"
    return "CLOSE"


def _get_status_color(status):
    return {
        "HEALTHY": "#16a34a", "WARNING": "#d97706",
        "CRITICAL": "#ea580c", "CLOSE": "#dc2626",
    }.get(status, "#6b7280")

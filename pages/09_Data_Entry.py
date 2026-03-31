"""
Page 9: Data Entry — Upload all Excel files at once, system auto-detects type
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
import tempfile
import os
from datetime import date
from utils.database import (
    get_db, upsert_site, upsert_generator, upsert_daily_operation,
    insert_fuel_purchase, refresh_site_summary, log_upload,
)
from parsers.blackout_parser import parse_blackout_file
from parsers.fuel_price_parser import parse_fuel_price_file
from alerts.alert_engine import run_all_checks, get_active_alerts
from config.settings import SECTORS

st.set_page_config(page_title="Data Entry", page_icon="📤", layout="wide")
st.title("📤 Data Entry")

ui.alert(
    title="📤 Upload All Your Excel Files At Once",
    description="Drop all 4 files together. The system reads the sheet names inside each file to detect the type — file names don't matter. It handles typos, dashes, blank rows, dynamic columns, and duplicate data automatically.",
    key="alert_entry",
)

selected = ui.tabs(
    options=["📁 Upload Files", "🧹 How AI Cleans Data", "✏️ Quick Edit", "📋 History"],
    default_value="📁 Upload Files",
    key="entry_tabs",
)


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-DETECT: Read sheet names to determine file type
# ═══════════════════════════════════════════════════════════════════════════
def detect_file_type(filepath):
    """
    Detect file type by reading sheet names inside the Excel file.
    Returns (file_type, sector_id) or (None, None) if unknown.
    """
    import openpyxl
    try:
        wb = openpyxl.load_workbook(str(filepath), read_only=True)
        sheets = [s.lower().strip() for s in wb.sheetnames]
        wb.close()

        # Fuel price: has multiple sector sheets (CMHL, CP, CFC, PG)
        if len(sheets) >= 3 and any(s in sheets for s in ["cmhl", "cp", "cfc", "pg"]):
            return "fuel_price", None

        # Blackout files: single sheet named after sector
        if "cp" in sheets:
            return "blackout_cp", "CP"
        if "cmhl" in sheets:
            return "blackout_cmhl", "CMHL"
        if "cfc" in sheets:
            return "blackout_cfc", "CFC"

        # Fallback: check first sheet name
        first = sheets[0] if sheets else ""
        if "cp" in first:
            return "blackout_cp", "CP"
        if "cmhl" in first or "cm" in first:
            return "blackout_cmhl", "CMHL"
        if "cfc" in first:
            return "blackout_cfc", "CFC"

    except Exception:
        pass
    return None, None


def process_file(tmp_path, filename):
    """Process a single uploaded file. Returns dict with results."""
    file_type, sector_id = detect_file_type(tmp_path)

    if file_type is None:
        return {"filename": filename, "status": "❌ Unknown", "type": "?",
                "message": "Could not detect file type from sheet names", "rows": 0}

    if file_type == "fuel_price":
        result = parse_fuel_price_file(tmp_path)
        purchases = result["purchases"]
        if not purchases:
            return {"filename": filename, "status": "⚠️ Empty", "type": "Fuel Price",
                    "message": "No fuel price records found", "rows": 0}

        # Import
        with get_db() as conn:
            batch_id = log_upload(conn, filename, "fuel_price", None,
                                  len(purchases), len(purchases), 0, None, None, None)
            for p in purchases:
                insert_fuel_purchase(
                    conn, p["sector_id"], p["date"], p["region"],
                    p["supplier"], p["fuel_type"],
                    p["quantity_liters"], p["price_per_liter"],
                    source="excel", upload_batch_id=batch_id,
                )

        sectors_found = set(p["sector_id"] for p in purchases)
        return {"filename": filename, "status": "✅ Imported", "type": "Fuel Price",
                "message": f"{len(purchases)} records across {', '.join(sectors_found)}",
                "rows": len(purchases), "data": pd.DataFrame(purchases)}

    else:
        # Blackout file
        sector_name = SECTORS.get(sector_id, {}).get("name", sector_id)
        result = parse_blackout_file(tmp_path, sector_id)
        dates = result["dates_found"]
        gens = result["generators"]
        daily = result["daily_data"]
        errors = result["errors"]

        if not daily:
            return {"filename": filename, "status": "⚠️ Empty", "type": f"Blackout {sector_id}",
                    "message": "No data rows found", "rows": 0}

        # Import
        with get_db() as conn:
            batch_id = log_upload(
                conn, filename, file_type, sector_id,
                len(daily), len(daily) - len(errors), len(errors),
                min(dates) if dates else None, max(dates) if dates else None,
                errors[:50] if errors else None,
            )
            gen_id_map = {}
            for gen in gens:
                upsert_site(conn, gen["site_id"], gen["site_name"], sector_id, gen["site_type"])
                gen_id = upsert_generator(
                    conn, gen["site_id"], gen["model_name"],
                    gen["model_name_raw"], gen["power_kva"],
                    gen["consumption_per_hour"], gen["fuel_type"], gen["supplier"],
                )
                gen_id_map[(gen["site_id"], gen["model_name_raw"])] = gen_id
                conn.execute("INSERT OR IGNORE INTO generator_name_map (raw_name, canonical_name, auto_mapped) VALUES (?, ?, 1)",
                             (gen["model_name_raw"], gen["model_name"]))

            sites_dates = set()
            for row in daily:
                gen_key = (row["site_id"], row["model_name_raw"])
                gen_id = gen_id_map.get(gen_key)
                if gen_id:
                    upsert_daily_operation(
                        conn, gen_id, row["site_id"], row["date"],
                        row["gen_run_hr"], row["daily_used_liters"],
                        row["spare_tank_balance"], row["blackout_hr"],
                        source="excel", upload_batch_id=batch_id,
                    )
                    sites_dates.add((row["site_id"], row["date"]))
            for sid, dt in sites_dates:
                refresh_site_summary(conn, sid, dt)

        date_range = f"{min(dates)} → {max(dates)}" if dates else "?"
        err_msg = f" ({len(errors)} rejected)" if errors else ""
        return {
            "filename": filename, "status": "✅ Imported",
            "type": f"Blackout {sector_id} ({sector_name})",
            "message": f"{len(daily)} rows, {len(gens)} generators, {len(dates)} days ({date_range}){err_msg}",
            "rows": len(daily),
            "errors": errors,
            "data": pd.DataFrame(daily[:20]) if daily else pd.DataFrame(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: Upload Files
# ═══════════════════════════════════════════════════════════════════════════
if selected == "📁 Upload Files":
    st.markdown("### Drop All Your Excel Files Here")
    st.markdown("Upload **1 to 4 files at once**. The system auto-detects each file type by reading the sheet names inside — **file names don't matter**.")

    uploaded_files = st.file_uploader(
        "Drop Excel files here (select multiple)",
        type=["xlsx"],
        accept_multiple_files=True,
        key="multi_upload",
        help="Select all 4 files at once, or upload one by one. File names can be anything — detection is by sheet names inside the Excel.",
    )

    if uploaded_files:
        st.markdown("---")

        # Show selected files
        st.markdown(f"**{len(uploaded_files)} file(s) selected:**")
        for f in uploaded_files:
            st.caption(f"📄 {f.name} ({f.size / 1024:.0f} KB)")

        # Process button — user must click to start
        if st.button(f"🚀 Process & Import {len(uploaded_files)} File(s)", key="btn_process",
                      type="primary", use_container_width=True):

            results = []
            progress = st.progress(0, text="Starting...")

            for i, uploaded in enumerate(uploaded_files):
                progress.progress((i) / len(uploaded_files), text=f"Processing {uploaded.name}...")
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name

                result = process_file(tmp_path, uploaded.name)
                results.append(result)
                os.unlink(tmp_path)

            progress.progress(1.0, text="Done!")

            # Store results in session state so they persist
            st.session_state["upload_results"] = results

        # Show results if available
        if "upload_results" not in st.session_state:
            st.stop()

        results = st.session_state["upload_results"]
        st.markdown("### Results")

        # Summary cards
        total_rows = sum(r["rows"] for r in results)
        success = sum(1 for r in results if "✅" in r["status"])
        failed = sum(1 for r in results if "❌" in r["status"])

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ui.metric_card(title="Files Processed", content=str(len(results)),
                           description=f"{success} success, {failed} failed", key="mc_files")
        with c2:
            ui.metric_card(title="Total Rows", content=f"{total_rows:,}",
                           description="imported into database", key="mc_total_rows")
        with c3:
            types = set(r["type"] for r in results if "✅" in r["status"])
            ui.metric_card(title="Data Types", content=str(len(types)),
                           description=", ".join(types) if types else "none", key="mc_types")
        with c4:
            all_errors = sum(len(r.get("errors", [])) for r in results)
            ui.metric_card(title="Cleaning Actions", content=str(all_errors),
                           description="rows rejected/fixed", key="mc_errors")

        # Per-file results
        for r in results:
            status_color = "🟢" if "✅" in r["status"] else "🔴" if "❌" in r["status"] else "🟡"
            st.markdown(f"""
            **{status_color} {r['filename']}**
            - Type: **{r['type']}**
            - {r['message']}
            """)

            # Show errors if any
            if r.get("errors"):
                with st.expander(f"🧹 {len(r['errors'])} cleaning actions for {r['filename']}"):
                    for e in r["errors"][:10]:
                        st.caption(f"❌ {e}")

            # Show preview if data available
            if "data" in r and isinstance(r["data"], pd.DataFrame) and not r["data"].empty:
                with st.expander(f"📊 Preview data from {r['filename']}"):
                    st.dataframe(r["data"], use_container_width=True, hide_index=True)

        if success > 0:
            st.balloons()
            st.success(f"✅ All done! {total_rows:,} rows imported from {success} file(s). Dashboard data is updated.")

            # ─── Auto-run alert checks ───────────────────────────────────
            st.markdown("---")
            st.markdown("### 🚨 Auto-Alert Check")
            with st.spinner("Running 10 alert checks on new data..."):
                alert_results = run_all_checks()

            total_alerts = sum(v for v in alert_results.values() if isinstance(v, int))
            if total_alerts > 0:
                st.warning(f"**{total_alerts} alerts generated from new data:**")

                # Show alert breakdown
                alert_cols = st.columns(4)
                alert_items = [(k, v) for k, v in alert_results.items() if isinstance(v, int) and v > 0]
                for i, (atype, count) in enumerate(alert_items):
                    with alert_cols[i % 4]:
                        label = atype.replace("_", " ").title()
                        ui.metric_card(title=label, content=str(count),
                                       description="alerts", key=f"mc_alert_{atype}")

                # Show critical alerts detail
                critical = get_active_alerts(severity="CRITICAL")
                if not critical.empty:
                    st.error(f"🔴 **{len(critical)} CRITICAL alerts — immediate action needed:**")
                    for _, a in critical.iterrows():
                        st.markdown(f"- **{a['site_id'] or a['sector_id']}**: {a['message']}")

                warning = get_active_alerts(severity="WARNING")
                if not warning.empty:
                    with st.expander(f"🟡 {len(warning)} WARNING alerts"):
                        for _, a in warning.iterrows():
                            st.markdown(f"- **{a['site_id'] or a['sector_id']}**: {a['message']}")
            else:
                st.success("✅ No alerts — all values within safe thresholds.")

        # Clear button
        st.markdown("---")
        if st.button("🗑️ Clear & Upload New Files", key="btn_clear", use_container_width=True):
            st.session_state.pop("upload_results", None)
            st.session_state.pop("multi_upload", None)
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: How AI Cleans Data
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "🧹 How AI Cleans Data":
    st.markdown("### How the System Handles Messy Excel Data")
    st.markdown("Your Excel files have many inconsistencies. Here's what gets fixed **automatically**:")

    st.markdown("#### 🔍 File Detection (by sheet names, NOT file names)")
    st.markdown("""
    | Sheet Names Inside File | Detected As |
    |---|---|
    | Sheet "CP" | Blackout Hr — City Pharmacy |
    | Sheet "CMHL" | Blackout Hr — City Mart Holdings |
    | Sheet "CFC" | Blackout Hr — City Food Chain |
    | Multiple sheets: CMHL, CP, CFC, PG | Daily Fuel Price |

    **Rename the file to anything** — `data_march.xlsx`, `weekly_report.xlsx` — it still works.
    """)

    st.markdown("#### 🔤 Generator Name Typos → Auto-fixed")
    fixes = pd.DataFrame({
        "In Your Excel": ["KHOLER-550", "KOHLER -550", "HIMONISA-200", "550 KVA - G1", "POWER MAX-150"],
        "System Converts To": ["KOHLER-550", "KOHLER-550", "HIMOINSA-200", "550KVA-G1", "POWERMAX-150"],
    })
    st.dataframe(fixes, use_container_width=True, hide_index=True)

    st.markdown("#### 📊 Dynamic Columns → Auto-detected")
    st.markdown("""
    Each day adds 4-5 new columns to your Excel. The parser:
    1. Scans Row 2 for **all date values** (any number of dates)
    2. Reads 4 sub-columns per date: Run Hr, Used, Balance, Blackout
    3. **No code change needed** when new days are added
    """)

    st.markdown("#### 🧹 Messy Values → Cleaned")
    cleaning = pd.DataFrame({
        "In Your Excel": ["-", "X", "#DIV/0!", "empty cell", "2.2666667", "5614 (blackout)"],
        "System Action": ["→ NULL", "→ NULL", "→ NULL", "→ NULL", "→ 2.27 (kept)", "→ REJECTED (>24 hrs)"],
    })
    st.dataframe(cleaning, use_container_width=True, hide_index=True)

    st.markdown("#### 🔄 Re-upload = Update, Not Duplicate")
    st.markdown("""
    - Same date + same generator → **overwritten** with new values
    - New dates → **added**
    - New sites/generators → **auto-created**
    - Upload the same file 10 times → still only 1 copy in database
    """)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: Quick Edit
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "✏️ Quick Edit":
    st.markdown("### Quick Edit — Fix Individual Values")
    st.caption("For quick corrections only. For bulk data, use Upload Files tab.")

    @st.cache_data(ttl=60)
    def load_edit_data():
        with get_db() as conn:
            sectors = [r[0] for r in conn.execute(
                "SELECT sector_id FROM sectors WHERE sector_id IN (SELECT DISTINCT sector_id FROM sites) ORDER BY sector_id"
            ).fetchall()]
            gens_df = pd.read_sql_query("""
                SELECT g.generator_id, g.site_id, s.sector_id, g.model_name
                FROM generators g JOIN sites s ON g.site_id = s.site_id
                WHERE g.is_active = 1 ORDER BY s.sector_id, g.site_id
            """, conn)
        return sectors, gens_df

    edit_sectors, gens_df = load_edit_data()
    c1, c2 = st.columns(2)
    with c1:
        sector = st.selectbox("Sector", edit_sectors, key="edit_sector")
    with c2:
        edit_date = st.date_input("Date", value=date.today(), key="edit_date")

    date_str = edit_date.strftime("%Y-%m-%d")
    sector_gens = gens_df[gens_df["sector_id"] == sector].copy()

    if not sector_gens.empty:
        with get_db() as conn:
            existing = pd.read_sql_query("""
                SELECT do.generator_id, do.gen_run_hr, do.daily_used_liters,
                       do.spare_tank_balance, do.blackout_hr
                FROM daily_operations do
                WHERE do.date = ? AND do.site_id IN (SELECT site_id FROM sites WHERE sector_id = ?)
            """, conn, params=(date_str, sector))

        sheet = sector_gens[["generator_id", "site_id", "model_name"]].copy()
        sheet = sheet.merge(existing, on="generator_id", how="left")
        for col in ["gen_run_hr", "daily_used_liters", "spare_tank_balance"]:
            sheet[col] = sheet[col].fillna(0.0)
        has_bo = SECTORS.get(sector, {}).get("has_blackout_data", False)
        if has_bo:
            sheet["blackout_hr"] = sheet["blackout_hr"].fillna(0.0)
        else:
            sheet = sheet.drop(columns=["blackout_hr"], errors="ignore")

        edited = st.data_editor(
            sheet,
            column_config={
                "generator_id": None,
                "site_id": st.column_config.TextColumn("Site", disabled=True),
                "model_name": st.column_config.TextColumn("Generator", disabled=True),
                "gen_run_hr": st.column_config.NumberColumn("Run Hr ✏️", min_value=0.0, max_value=24.0, step=0.25),
                "daily_used_liters": st.column_config.NumberColumn("Used (L) ✏️", min_value=0.0, max_value=5000.0, step=10.0),
                "spare_tank_balance": st.column_config.NumberColumn("Tank (L) ✏️", min_value=0.0, max_value=50000.0, step=50.0),
                **({"blackout_hr": st.column_config.NumberColumn("Blackout ✏️", min_value=0.0, max_value=24.0, step=0.25)} if has_bo else {}),
            },
            use_container_width=True, hide_index=True,
            key=f"edit_{sector}_{date_str}",
        )

        if st.button("💾 Save", key="save_edit", type="primary", use_container_width=True):
            saved = 0
            sites_updated = set()
            with get_db() as conn:
                for _, row in edited.iterrows():
                    if any(row[c] > 0 for c in ["gen_run_hr", "daily_used_liters", "spare_tank_balance"]):
                        upsert_daily_operation(
                            conn, int(row["generator_id"]), row["site_id"], date_str,
                            row["gen_run_hr"] or None, row["daily_used_liters"] or None,
                            row["spare_tank_balance"] or None,
                            row.get("blackout_hr", None) or None, source="manual",
                        )
                        sites_updated.add(row["site_id"])
                        saved += 1
                for sid in sites_updated:
                    refresh_site_summary(conn, sid, date_str)
            st.success(f"Saved {saved} records") if saved else st.info("Nothing to save.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: History
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "📋 History":
    st.markdown("### Upload & Database History")
    with get_db() as conn:
        uploads = pd.read_sql_query("""
            SELECT filename, file_type, sector_id, rows_parsed, rows_accepted,
                   rows_rejected, date_range_start, date_range_end, uploaded_at
            FROM upload_history ORDER BY uploaded_at DESC
        """, conn)
        totals = {}
        for t in ["sites", "generators", "daily_operations", "fuel_purchases"]:
            totals[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.metric_card(title="Sites", content=str(totals["sites"]), description="in database", key="mc_h_sites")
    with c2:
        ui.metric_card(title="Generators", content=str(totals["generators"]), description="in database", key="mc_h_gens")
    with c3:
        ui.metric_card(title="Daily Records", content=str(totals["daily_operations"]), description="operations", key="mc_h_ops")
    with c4:
        ui.metric_card(title="Fuel Prices", content=str(totals["fuel_purchases"]), description="purchases", key="mc_h_fuel")

    if not uploads.empty:
        st.dataframe(uploads, use_container_width=True, hide_index=True)
    else:
        st.info("No uploads yet.")

"""
Parser for Blackout Hr_ *.xlsx files (CP, CMHL, CFC).

Handles:
- Dynamic date columns (auto-detects from Row 2)
- Multi-generator per site
- Merged cells, dashes, empty rows
- Sector-specific variations (CMHL has no blackout_hr)
"""
import openpyxl
from datetime import datetime

from parsers.base_parser import clean_numeric, parse_date_from_cell, validate_range
from parsers.name_normalizer import normalize_generator_name
from config.settings import VALIDATION, SECTORS


def parse_blackout_file(filepath, sector_id):
    """
    Parse a Blackout Hr_ Excel file and return structured data.

    Returns:
        {
            "generators": [
                {
                    "site_id": str, "site_name": str, "site_type": str,
                    "model_name": str, "model_name_raw": str,
                    "power_kva": float, "consumption_per_hour": float,
                    "fuel_type": str, "supplier": str,
                }
            ],
            "daily_data": [
                {
                    "site_id": str, "model_name_raw": str,
                    "date": str, "gen_run_hr": float,
                    "daily_used_liters": float, "spare_tank_balance": float,
                    "blackout_hr": float,
                }
            ],
            "errors": [str],
            "warnings": [str],
            "dates_found": [str],
        }
    """
    wb = openpyxl.load_workbook(str(filepath), data_only=True)
    sheet_name = SECTORS[sector_id].get("sheet", sector_id)

    # Try to find the correct sheet
    if sector_id in wb.sheetnames:
        ws = wb[sector_id]
    else:
        ws = wb[wb.sheetnames[0]]

    has_blackout = SECTORS[sector_id]["has_blackout_data"]

    result = {
        "generators": [],
        "daily_data": [],
        "errors": [],
        "warnings": [],
        "dates_found": [],
    }

    # ─── Step 1: Find date columns in Row 2 ──────────────────────────────
    date_columns = []  # [(date_str, col_index_of_first_sub_column)]
    for col_idx in range(1, ws.max_column + 1):
        cell_val = ws.cell(row=2, column=col_idx).value
        date_str = parse_date_from_cell(cell_val)
        if date_str:
            date_columns.append((date_str, col_idx))

    if not date_columns:
        result["errors"].append("No date columns found in Row 2")
        return result

    result["dates_found"] = [d[0] for d in date_columns]

    # ─── Step 2: Determine sub-column layout per date ────────────────────
    # Each date group has: Gen Run Hr, Daily Used, Spare Tank Balance, [Blackout Hr], [blank]
    # Detect by looking at Row 3 headers after first date column
    # Sub-columns per date: typically 5 for CP/CFC, 5 for CMHL (but no blackout data)

    def _detect_cols_per_date():
        """Detect how many columns each date group spans."""
        if len(date_columns) >= 2:
            return date_columns[1][1] - date_columns[0][1]
        # Only one date — estimate from headers in row 3
        # Count non-empty cells after first date col until end or next section
        count = 0
        start = date_columns[0][1]
        for c in range(start, min(start + 7, ws.max_column + 1)):
            val = ws.cell(row=3, column=c).value
            if val and str(val).strip():
                count += 1
        return max(count + 1, 4)  # at least 4 (run hr, used, balance, blank)

    cols_per_date = _detect_cols_per_date()

    # ─── Step 3: Find static column positions ────────────────────────────
    # Columns before the first date: seq#, site_name, type, fuel_type, supplier, machine_power, consumption/hr
    first_date_col = date_columns[0][1]

    # Map static columns (1-based): typically cols 1-7
    # Col 1: Seq #
    # Col 2: Site/Center/Location Name
    # Col 3: Type (Regular/LNG)
    # Col 4: Fuel Type (PD/HSD)
    # Col 5: Supplier
    # Col 6: Machine Power / Model
    # Col 7: Consumption per Hour
    COL_SEQ = 1
    COL_SITE = 2
    COL_TYPE = 3
    COL_FUEL = 4
    COL_SUPPLIER = 5
    COL_MODEL = 6
    COL_CONSUMPTION = 7

    # ─── Step 4: Find data start row ─────────────────────────────────────
    data_start_row = None
    for row_idx in range(1, min(20, ws.max_row + 1)):
        cell_val = ws.cell(row=row_idx, column=COL_SEQ).value
        if cell_val is not None:
            try:
                int(float(str(cell_val)))
                data_start_row = row_idx
                break
            except (ValueError, TypeError):
                continue

    if data_start_row is None:
        result["errors"].append("Could not find data start row (no numeric seq# found)")
        return result

    # ─── Step 5: Parse each data row ─────────────────────────────────────
    seen_generators = set()

    for row_idx in range(data_start_row, ws.max_row + 1):
        seq_val = ws.cell(row=row_idx, column=COL_SEQ).value

        # Skip non-data rows
        if seq_val is None:
            continue
        try:
            int(float(str(seq_val)))
        except (ValueError, TypeError):
            continue

        # Read static columns
        site_name_raw = ws.cell(row=row_idx, column=COL_SITE).value
        if not site_name_raw or not str(site_name_raw).strip():
            continue

        site_name = str(site_name_raw).strip()
        site_id = site_name  # Use name as ID
        site_type = str(ws.cell(row=row_idx, column=COL_TYPE).value or "Regular").strip()
        fuel_type_raw = ws.cell(row=row_idx, column=COL_FUEL).value
        fuel_type = str(fuel_type_raw).strip() if fuel_type_raw and str(fuel_type_raw).strip() not in ("", "None") else None
        supplier_raw = ws.cell(row=row_idx, column=COL_SUPPLIER).value
        supplier = str(supplier_raw).strip() if supplier_raw and str(supplier_raw).strip() not in ("", "None") else None
        model_raw = ws.cell(row=row_idx, column=COL_MODEL).value
        model_name_raw = str(model_raw).strip() if model_raw else "UNKNOWN"
        model_name = normalize_generator_name(model_name_raw)
        consumption_raw = ws.cell(row=row_idx, column=COL_CONSUMPTION).value
        consumption_per_hour = clean_numeric(consumption_raw)

        # Power KVA — sometimes in model name, sometimes consumption_per_hour IS the KVA
        # The column header says KVA for col 6 and Liter for col 7
        # Actually col 6 is Machine Power (model name like "KOHLER-550")
        # and the KVA is embedded in the name or might be in consumption column
        # Let's extract KVA from the model name
        from parsers.name_normalizer import extract_kva_from_model
        power_kva = extract_kva_from_model(model_name_raw)

        # Store generator info (deduplicate by site + raw model name)
        gen_key = (site_id, model_name_raw)
        if gen_key not in seen_generators:
            seen_generators.add(gen_key)
            result["generators"].append({
                "site_id": site_id,
                "site_name": site_name,
                "site_type": site_type if site_type != "None" else "Regular",
                "model_name": model_name,
                "model_name_raw": model_name_raw,
                "power_kva": power_kva,
                "consumption_per_hour": consumption_per_hour,
                "fuel_type": fuel_type,
                "supplier": supplier,
            })

        # ─── Read daily data for each date column ────────────────────
        for date_str, date_col_start in date_columns:
            # Sub-columns relative to date_col_start:
            # 0: Gen Run Hr
            # 1: Daily Used (L)
            # 2: Spare Tank Balance (L)
            # 3: Blackout Hr (if has_blackout)
            gen_run_hr = clean_numeric(ws.cell(row=row_idx, column=date_col_start).value)
            daily_used = clean_numeric(ws.cell(row=row_idx, column=date_col_start + 1).value)
            tank_balance = clean_numeric(ws.cell(row=row_idx, column=date_col_start + 2).value)
            blackout = None
            if has_blackout:
                blackout = clean_numeric(ws.cell(row=row_idx, column=date_col_start + 3).value)

            # Skip row-date if all values are None
            if all(v is None for v in [gen_run_hr, daily_used, tank_balance, blackout]):
                continue

            # Validate
            warnings_for_row = []

            gen_run_hr, w, rejected = validate_range(gen_run_hr, "gen_run_hr", VALIDATION)
            if rejected:
                result["errors"].append(f"Row {row_idx}, {date_str}: {w}")
                continue
            if w:
                warnings_for_row.append(w)

            daily_used, w, rejected = validate_range(daily_used, "daily_used_liters", VALIDATION)
            if w:
                warnings_for_row.append(w)

            tank_balance, w, rejected = validate_range(tank_balance, "spare_tank_balance", VALIDATION)
            if w:
                warnings_for_row.append(w)

            if blackout is not None:
                blackout, w, rejected = validate_range(blackout, "blackout_hr", VALIDATION)
                if rejected:
                    # Don't skip the whole row — just nullify the bad blackout value
                    result["warnings"].append(f"Row {row_idx} ({site_name}), {date_str}: {w} — blackout value ignored, other data kept")
                    blackout = None
                if w and not rejected:
                    warnings_for_row.append(w)

            # Also capture raw blackout text as note (for incident tracking)
            raw_blackout_val = ws.cell(row=row_idx, column=date_col_start + 3).value if has_blackout else None
            if raw_blackout_val and isinstance(raw_blackout_val, str) and raw_blackout_val.strip():
                result["warnings"].append(f"Row {row_idx} ({site_name}), {date_str}: Blackout note: '{raw_blackout_val.strip()}'")


            if warnings_for_row:
                result["warnings"].extend(
                    [f"Row {row_idx} ({site_name}/{model_name_raw}), {date_str}: {w}" for w in warnings_for_row]
                )

            result["daily_data"].append({
                "site_id": site_id,
                "model_name_raw": model_name_raw,
                "date": date_str,
                "gen_run_hr": gen_run_hr,
                "daily_used_liters": daily_used,
                "spare_tank_balance": tank_balance,
                "blackout_hr": blackout,
            })

    wb.close()
    return result

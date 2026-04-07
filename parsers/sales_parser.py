"""
Parser for daily sales data.xlsx and hourly sales data.xlsx.

Daily sales: SALES_DATE, Site Name, Brand, SALES_AMT, MARGIN
Hourly sales: DocumentDate (int YYYYMMDD), Site Name, Brand, SALES_HR, SALES_AMT, TRANS_CNT
"""
import pandas as pd
from parsers.base_parser import clean_numeric, parse_date_from_cell
from config.settings import BRAND_SECTOR_MAP, SEGMENT_SECTOR_MAP


def parse_daily_sales_file(filepath, sheet_name=None):
    """
    Parse daily sales Excel file.

    Returns:
        {
            "records": [ { sales_site_name, date, brand, sales_amt, margin } ],
            "sites_found": [str],
            "brands_found": [str],
            "date_range": (min_date, max_date),
            "errors": [str],
        }
    """
    # Find the right sheet
    if sheet_name is None:
        xl = pd.ExcelFile(filepath)
        for s in xl.sheet_names:
            if "daily" in s.lower() and "sales" in s.lower():
                sheet_name = s
                break
        if sheet_name is None:
            sheet_name = 0
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    result = {"records": [], "sites_found": set(), "brands_found": set(),
              "date_range": (None, None), "errors": []}

    # Find columns by flexible matching
    cols = _detect_columns(df, mode="daily")
    if not cols.get("date") or not (cols.get("site") or cols.get("site_code") or cols.get("cost_center")):
        result["errors"].append("Could not find required columns (date, site name or site code or GOLD_CODE)")
        return result

    # Prefer CostCenter (matches sites.cost_center_code) > GOLD_CODE > Site Name
    site_col = cols.get("cost_center", cols.get("site_code", cols.get("site")))
    has_segment = "segment" in cols

    dates_seen = []

    for idx, row in df.iterrows():
        try:
            # Parse date
            date_val = row[cols["date"]]
            if pd.isna(date_val):
                continue
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = parse_date_from_cell(date_val)
            if not date_str:
                continue

            raw_site = row.get(site_col, "")
            if pd.isna(raw_site):
                continue
            # Convert numeric GOLD_CODE/CostCenter to string
            site_name = str(int(raw_site)).strip() if isinstance(raw_site, (int, float)) else str(raw_site).strip()
            if not site_name or site_name == "nan":
                continue

            brand = str(row.get(cols.get("brand", ""), "")).strip() if cols.get("brand") else "ALL"
            if brand == "nan":
                brand = "ALL"

            sales_amt = clean_numeric(row.get(cols.get("amount", ""), 0)) or 0
            margin = clean_numeric(row.get(cols.get("margin", ""), 0)) or 0

            # Resolve sector: SegmentName → SEGMENT_SECTOR_MAP, or Brand → BRAND_SECTOR_MAP
            sector_id = None
            if has_segment:
                seg = str(row.get(cols["segment"], "")).strip()
                sector_id = SEGMENT_SECTOR_MAP.get(seg)
            if not sector_id and brand != "ALL":
                sector_id = BRAND_SECTOR_MAP.get(brand.upper())

            result["records"].append({
                "sales_site_name": site_name,
                "date": date_str,
                "brand": brand,
                "sales_amt": sales_amt,
                "margin": margin,
                "sector_id": sector_id,
            })
            result["sites_found"].add(site_name)
            result["brands_found"].add(brand)
            dates_seen.append(date_str)

        except Exception as e:
            result["errors"].append(f"Row {idx + 1}: {str(e)}")

    result["sites_found"] = sorted(result["sites_found"])
    result["brands_found"] = sorted(result["brands_found"])
    if dates_seen:
        result["date_range"] = (min(dates_seen), max(dates_seen))

    return result


def parse_hourly_sales_file(filepath, sheet_name=None):
    """
    Parse hourly sales Excel file.

    Returns:
        {
            "records": [ { sales_site_name, date, hour, brand, sales_amt, trans_cnt } ],
            "sites_found": [str],
            "brands_found": [str],
            "date_range": (min_date, max_date),
            "errors": [str],
        }
    """
    # Find the right sheet
    if sheet_name is None:
        xl = pd.ExcelFile(filepath)
        for s in xl.sheet_names:
            if "hourly" in s.lower() and "sales" in s.lower():
                sheet_name = s
                break
        if sheet_name is None:
            sheet_name = 0
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    result = {"records": [], "sites_found": set(), "brands_found": set(),
              "date_range": (None, None), "errors": []}

    cols = _detect_columns(df, mode="hourly")
    if not cols.get("date") or not (cols.get("site") or cols.get("site_code") or cols.get("cost_center")):
        result["errors"].append("Could not find required columns (date, site name or site code or GOLD_CODE)")
        return result

    # Prefer CostCenter (matches sites.cost_center_code) > GOLD_CODE > Site Name
    site_col = cols.get("cost_center", cols.get("site_code", cols.get("site")))
    has_segment = "segment" in cols

    dates_seen = []

    for idx, row in df.iterrows():
        try:
            # Parse date — may be int YYYYMMDD
            date_val = row[cols["date"]]
            if pd.isna(date_val):
                continue

            if isinstance(date_val, (int, float)):
                ds = str(int(date_val))
                if len(ds) == 8:
                    date_str = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
                else:
                    continue
            elif isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = parse_date_from_cell(date_val)
            if not date_str:
                continue

            raw_site = row.get(site_col, "")
            if pd.isna(raw_site):
                continue
            site_name = str(int(raw_site)).strip() if isinstance(raw_site, (int, float)) else str(raw_site).strip()
            if not site_name or site_name == "nan":
                continue

            brand = str(row.get(cols.get("brand", ""), "")).strip() if cols.get("brand") else "ALL"
            if brand == "nan":
                brand = "ALL"

            hour = int(row.get(cols.get("hour", ""), 0)) if cols.get("hour") else 0
            sales_amt = clean_numeric(row.get(cols.get("amount", ""), 0)) or 0
            trans_cnt = int(clean_numeric(row.get(cols.get("trans_cnt", ""), 0)) or 0)

            # Resolve sector: SegmentName → SEGMENT_SECTOR_MAP, or Brand → BRAND_SECTOR_MAP
            sector_id = None
            if has_segment:
                seg = str(row.get(cols["segment"], "")).strip()
                sector_id = SEGMENT_SECTOR_MAP.get(seg)
            if not sector_id and brand != "ALL":
                sector_id = BRAND_SECTOR_MAP.get(brand.upper())

            result["records"].append({
                "sales_site_name": site_name,
                "date": date_str,
                "hour": hour,
                "brand": brand,
                "sales_amt": sales_amt,
                "trans_cnt": trans_cnt,
                "sector_id": sector_id,
            })
            result["sites_found"].add(site_name)
            result["brands_found"].add(brand)
            dates_seen.append(date_str)

        except Exception as e:
            result["errors"].append(f"Row {idx + 1}: {str(e)}")

    result["sites_found"] = sorted(result["sites_found"])
    result["brands_found"] = sorted(result["brands_found"])
    if dates_seen:
        result["date_range"] = (min(dates_seen), max(dates_seen))

    return result


def _detect_columns(df, mode="daily"):
    """Auto-detect column names by flexible matching."""
    cols = {}
    for col in df.columns:
        cl = str(col).strip().lower().replace(" ", "").replace("_", "")
        if "salesdate" in cl or "documentdate" in cl or cl == "date":
            cols["date"] = col
        elif "sitename" in cl or cl == "site":
            cols["site"] = col
        elif "sitecode" in cl:
            cols["site_code"] = col
        elif "goldcode" in cl:
            cols["site_code"] = col  # GOLD_CODE → site identifier
        elif "costcenter" in cl:
            cols["cost_center"] = col
        elif cl == "brand":
            cols["brand"] = col
        elif "segmentname" in cl:
            cols["segment"] = col  # SegmentName → used for sector resolution
            if "brand" not in cols:
                cols["brand"] = col  # also treat as brand fallback
        elif "salesamt" in cl or "salesamount" in cl:
            cols["amount"] = col
        elif "totalamount" in cl:
            cols["amount"] = col  # TotalAmount in hourly
        elif cl == "sales" and mode == "daily":
            if "amount" not in cols:
                cols["amount"] = col
        elif cl == "margin":
            cols["margin"] = col
        elif "saleshr" in cl or "saleshour" in cl:
            cols["hour"] = col
        elif "transcnt" in cl or "transcount" in cl or "transactioncount" in cl:
            cols["trans_cnt"] = col
    return cols

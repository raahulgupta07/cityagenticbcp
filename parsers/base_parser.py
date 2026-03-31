"""
Shared parsing utilities — value cleaning and validation.
"""
from datetime import datetime


def clean_value(val):
    """
    Clean a cell value from Excel.
    Returns None for empty/dash/X values, otherwise the cleaned value.
    """
    if val is None:
        return None
    if isinstance(val, str):
        stripped = val.strip()
        if stripped in ("", "-", "X", "x", "#DIV/0!", "N/A", "n/a"):
            return None
        # Try numeric conversion
        try:
            return float(stripped.replace(",", ""))
        except ValueError:
            return stripped
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return val


def clean_numeric(val):
    """Clean a value and return float or None."""
    cleaned = clean_value(val)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        return float(cleaned)
    if isinstance(cleaned, str):
        try:
            return float(cleaned.replace(",", ""))
        except ValueError:
            return None
    return None


def validate_range(value, field_name, rules):
    """
    Validate a numeric value against config rules.
    Returns (value, warning_msg_or_None, is_rejected).
    """
    if value is None:
        return value, None, False

    rule = rules.get(field_name)
    if not rule:
        return value, None, False

    if value < rule.get("min", float("-inf")) or value > rule.get("max", float("inf")):
        action = rule.get("action", "warn")
        msg = f"{field_name}={value} outside range [{rule.get('min')}, {rule.get('max')}]"
        return value, msg, (action == "reject")

    warn_above = rule.get("warn_above")
    if warn_above and value > warn_above:
        return value, f"{field_name}={value} above warning threshold {warn_above}", False

    return value, None, False


def parse_date_from_cell(val):
    """Extract ISO date string from a cell value (datetime or string)."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, str):
        val = val.strip()
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None

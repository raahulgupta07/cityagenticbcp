"""
Generator name normalization — maps raw Excel names to canonical form.
"""
import re

# Known typo corrections
TYPO_MAP = {
    "KHOLER": "KOHLER",
    "HIMONISA": "HIMOINSA",
    "LONGEN": "LONGEN",
    "POWER MAX": "POWERMAX",
    "POWERMAX": "POWERMAX",
}

def normalize_generator_name(raw_name):
    """
    Normalize a generator model name from Excel.

    Examples:
        'KOHLER -550'   -> 'KOHLER-550'
        'KHOLER-550'    -> 'KOHLER-550'
        '550 KVA - G1'  -> '550KVA-G1'
        'HIMONISA-200'  -> 'HIMOINSA-200'
        '220KVA'        -> '220KVA'
    """
    if not raw_name or not str(raw_name).strip():
        return "UNKNOWN"

    name = str(raw_name).strip()

    # Fix known typos (case-insensitive)
    upper = name.upper()
    for typo, fix in TYPO_MAP.items():
        if typo in upper:
            # Replace preserving the rest
            pattern = re.compile(re.escape(typo), re.IGNORECASE)
            name = pattern.sub(fix, name)

    # Normalize whitespace around dashes: "KOHLER -550" -> "KOHLER-550"
    name = re.sub(r'\s*-\s*', '-', name)

    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def extract_kva_from_model(model_name):
    """
    Extract numeric KVA rating from model name.

    'KOHLER-550' -> 550
    '550KVA-G1'  -> 550
    '220KVA'     -> 220
    'AKSA-100'   -> 100
    """
    if not model_name:
        return None

    name = str(model_name).upper()

    # Pattern: number followed by optional KVA
    match = re.search(r'(\d+)\s*KVA', name)
    if match:
        return float(match.group(1))

    # Pattern: after dash, take the number (KOHLER-550 -> 550)
    match = re.search(r'-(\d+)', name)
    if match:
        return float(match.group(1))

    # Just a bare number
    match = re.search(r'(\d+)', name)
    if match:
        return float(match.group(1))

    return None

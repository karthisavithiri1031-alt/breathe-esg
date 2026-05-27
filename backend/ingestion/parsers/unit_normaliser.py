"""
Unit normalisation utilities.

Design rationale:
- We store raw_quantity/raw_unit verbatim from source.
- normalised_quantity/normalised_unit are what the emission factor applies to.
- Canonical units per category:
    fuel combustion  → litres (liquid) or m³ (gas)
    electricity      → kWh
    travel flight    → km (great-circle distance)
    travel hotel     → room-nights (no normalisation needed)
    travel ground    → km
    procurement      → GBP (spend-based fallback)
"""

from decimal import Decimal

# Conversion factors TO canonical unit
LITRE_CONVERSIONS = {
    "l": Decimal("1"),
    "litre": Decimal("1"),
    "litres": Decimal("1"),
    "liter": Decimal("1"),
    "liters": Decimal("1"),
    "gal": Decimal("3.78541"),   # US gallon → litre
    "gallon": Decimal("3.78541"),
    "gallons": Decimal("3.78541"),
    "imp_gal": Decimal("4.54609"),  # Imperial gallon
    "kg": None,   # density-dependent; handled separately per fuel type
}

KWH_CONVERSIONS = {
    "kwh": Decimal("1"),
    "kw_h": Decimal("1"),
    "mwh": Decimal("1000"),
    "gwh": Decimal("1000000"),
    "gj": Decimal("277.778"),
    "mj": Decimal("0.277778"),
    "kj": Decimal("0.000277778"),
    "therm": Decimal("29.3071"),
    "mmbtu": Decimal("293.071"),
    "btu": Decimal("0.000293071"),
}

KM_CONVERSIONS = {
    "km": Decimal("1"),
    "kilometer": Decimal("1"),
    "kilometers": Decimal("1"),
    "kilometres": Decimal("1"),
    "mile": Decimal("1.60934"),
    "miles": Decimal("1.60934"),
    "mi": Decimal("1.60934"),
    "nm": Decimal("1.852"),   # nautical miles
}

M3_CONVERSIONS = {
    "m3": Decimal("1"),
    "m³": Decimal("1"),
    "cubic_meter": Decimal("1"),
    "cubic_metres": Decimal("1"),
    "cf": Decimal("0.0283168"),   # cubic feet → m³
    "mcf": Decimal("28.3168"),    # thousand cubic feet
    "mmcf": Decimal("28316.8"),
    "scf": Decimal("0.0283168"),  # standard cubic feet (approx)
}


def normalise_unit(raw_quantity: Decimal, raw_unit: str, category: str) -> tuple[Decimal, str, list[str]]:
    """
    Returns (normalised_quantity, normalised_unit, warnings).
    warnings is a list of strings if we had to estimate or make assumptions.
    """
    u = raw_unit.strip().lower().replace(" ", "_").replace("-", "_")
    warnings = []

    if category == "fuel_combustion":
        if u in LITRE_CONVERSIONS and LITRE_CONVERSIONS[u] is not None:
            return raw_quantity * LITRE_CONVERSIONS[u], "litres", warnings
        if u in M3_CONVERSIONS:
            return raw_quantity * M3_CONVERSIONS[u], "m3", warnings
        if u == "kg":
            # Diesel density ~0.85 kg/L — flag as estimated
            warnings.append("Converted kg to litres using diesel density 0.85 kg/L; verify fuel type")
            return raw_quantity / Decimal("0.85"), "litres", warnings
        if u == "gj":
            # Energy-based: note this for factor selection
            return raw_quantity * Decimal("277.778"), "kwh_energy", warnings
        warnings.append(f"Unknown fuel unit '{raw_unit}'; treating as litres")
        return raw_quantity, "litres", warnings

    elif category == "purchased_electricity":
        if u in KWH_CONVERSIONS:
            return raw_quantity * KWH_CONVERSIONS[u], "kWh", warnings
        warnings.append(f"Unknown electricity unit '{raw_unit}'; treating as kWh")
        return raw_quantity, "kWh", warnings

    elif category in ("business_travel_flight", "business_travel_ground"):
        if u in KM_CONVERSIONS:
            return raw_quantity * KM_CONVERSIONS[u], "km", warnings
        if u == "unknown":
            warnings.append("Distance not provided; emission factor applied to passenger-journey placeholder")
            return raw_quantity, "passenger_journey", warnings
        warnings.append(f"Unknown distance unit '{raw_unit}'; treating as km")
        return raw_quantity, "km", warnings

    elif category == "business_travel_hotel":
        # Canonical: room-nights
        if u in ("room_night", "room_nights", "night", "nights", "room-night"):
            return raw_quantity, "room_nights", warnings
        warnings.append(f"Hotel unit '{raw_unit}' mapped to room_nights")
        return raw_quantity, "room_nights", warnings

    elif category == "procurement":
        # Spend-based; canonical is GBP
        return raw_quantity, raw_unit.upper() or "GBP", warnings

    return raw_quantity, raw_unit, [f"No normalisation rule for category '{category}'"]


def parse_date_flexible(date_str: str):
    """
    SAP exports dates in many formats. Try them all.
    Returns a datetime.date or raises ValueError.
    """
    import re
    from datetime import datetime

    if not date_str or not str(date_str).strip():
        raise ValueError("Empty date string")

    s = str(date_str).strip()

    # SAP often gives YYYYMMDD (IDoc / flat file)
    if re.fullmatch(r'\d{8}', s):
        return datetime.strptime(s, "%Y%m%d").date()

    # DD.MM.YYYY (German locale — common in SAP)
    if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', s):
        return datetime.strptime(s, "%d.%m.%Y").date()

    # MM/DD/YYYY (US)
    if re.fullmatch(r'\d{2}/\d{2}/\d{4}', s):
        return datetime.strptime(s, "%m/%d/%Y").date()

    # DD/MM/YYYY (UK/EU)
    if re.fullmatch(r'\d{2}/\d{2}/\d{4}', s):
        return datetime.strptime(s, "%d/%m/%Y").date()

    # ISO 8601
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # Excel serial date (float or int)
    try:
        serial = float(s)
        from datetime import timedelta
        # Excel epoch: 1899-12-30
        return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
    except (ValueError, OverflowError):
        pass

    raise ValueError(f"Cannot parse date: '{date_str}'")

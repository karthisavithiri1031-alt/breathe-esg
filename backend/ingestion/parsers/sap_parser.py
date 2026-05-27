"""
SAP flat-file parser for fuel and procurement data.

Why flat file (not IDoc, not OData)?
IDoc requires SAP middleware and an active RFC connection — not realistic for a
prototype that must work without a live SAP system.  OData/BAPI is viable for
production but again needs credentials.  CSV/tab-delimited flat file exports
are what sustainability leads actually email us: they pull a MB51 (material
movements) or ME2M (purchase orders) report, export to Excel/CSV, and send it.
That's the shape we handle.

Realistic SAP flat-file characteristics handled:
- German column headers (Menge = quantity, Werk = plant, Buchungsdatum = posting date)
- English column headers from the same report type
- YYYYMMDD date format (SAP default posting date)
- DD.MM.YYYY date format (German locale users)
- Quantity with comma as decimal separator (German Excel exports)
- Plant code (Werk) needs lookup table — we use FacilityLookup
- Material Group (Materialgruppe / MatGrp) to classify fuel vs procurement
- Units: L (litres), KG, M3, GAL, PC (pieces — procurement)
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import Any

from .unit_normaliser import normalise_unit, parse_date_flexible

# SAP column header synonyms (German → English canonical)
HEADER_MAP = {
    # Posting date
    "buchungsdatum": "posting_date",
    "posting date": "posting_date",
    "bdat": "posting_date",
    "document date": "posting_date",
    "belegdatum": "posting_date",

    # Quantity
    "menge": "quantity",
    "quantity": "quantity",
    "qty": "quantity",
    "amount": "quantity",
    "mengeinbme": "quantity",

    # Unit of measure
    "me": "unit",
    "bme": "unit",
    "unit": "unit",
    "uom": "unit",
    "base unit": "unit",
    "einheit": "unit",
    "meins": "unit",

    # Plant / facility
    "werk": "plant",
    "plant": "plant",
    "werks": "plant",

    # Material number
    "material": "material",
    "matnr": "material",
    "material number": "material",

    # Material description
    "materialkurztext": "material_desc",
    "material description": "material_desc",
    "maktx": "material_desc",

    # Material group (key for fuel vs procurement split)
    "materialgruppe": "material_group",
    "material group": "material_group",
    "matkl": "material_group",
    "matgr": "material_group",
    "mat. group": "material_group",

    # Movement type (helps distinguish consume vs receive)
    "bewegungsart": "movement_type",
    "movement type": "movement_type",
    "bwart": "movement_type",

    # Cost centre / cost center
    "kostenstelle": "cost_centre",
    "cost center": "cost_centre",
    "cost centre": "cost_centre",
    "kostl": "cost_centre",

    # Net value / spend
    "nettopreis": "net_value",
    "net value": "net_value",
    "dmbtr": "net_value",
    "amount in lc": "net_value",
    "wrbtr": "net_value",

    # Currency
    "waers": "currency",
    "currency": "currency",
    "curr": "currency",
}

# Material group codes that indicate fuel consumption
FUEL_MATERIAL_GROUPS = {
    "001", "002", "003",        # common SAP fuel groups in Indian/EU configs
    "fuel", "fuels",
    "diesel", "petrol", "gasoline", "lpg", "cng", "hsd",
    "energy", "utilities",
    "erdoelprodukte",           # German: petroleum products
    "kraftstoffe",              # German: fuels
    "01", "02",
}

# Movement types that represent consumption (vs receipt / reversal)
CONSUMPTION_MOVEMENTS = {"201", "261", "551", "601", "261e"}


def _clean_number(s: str) -> Decimal:
    """Handle German comma-decimal and thousand-separator variants."""
    s = str(s).strip()
    if not s:
        raise ValueError("Empty numeric field")
    # German: 1.234,56 → 1234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    # Remove thousand separators
    s = s.replace(" ", "").replace("\xa0", "")
    return Decimal(s)


def _classify_category(row: dict) -> str:
    """Fuel combustion vs procurement based on material group and description."""
    mg = str(row.get("material_group", "")).strip().lower()
    desc = str(row.get("material_desc", "")).strip().lower()
    mat = str(row.get("material", "")).strip().lower()

    if mg in FUEL_MATERIAL_GROUPS:
        return "fuel_combustion"
    for kw in ("diesel", "petrol", "gasoline", "fuel", "lpg", "cng", "gas", "oil", "hsd", "hfo"):
        if kw in desc or kw in mat:
            return "fuel_combustion"
    return "procurement"


# DEFRA 2024 emission factors (kg CO2e per litre) — subset
FUEL_EMISSION_FACTORS = {
    "diesel": Decimal("2.51839"),
    "petrol": Decimal("2.31380"),
    "hsd": Decimal("2.51839"),   # High-speed diesel (India)
    "lpg": Decimal("1.55540"),
    "cng_m3": Decimal("2.04040"),  # per m³
    "natural_gas_m3": Decimal("2.04040"),
    "default": Decimal("2.51839"),  # assume diesel if unknown
}

PROCUREMENT_FACTOR = Decimal("0.000309")   # kg CO2e per GBP (DEFRA spend-based, mixed industry)


def get_fuel_factor(row: dict) -> tuple[Decimal, str]:
    desc = (str(row.get("material_desc", "")) + str(row.get("material", ""))).lower()
    for key, factor in FUEL_EMISSION_FACTORS.items():
        if key in desc:
            return factor, f"DEFRA 2024 – {key}"
    return FUEL_EMISSION_FACTORS["default"], "DEFRA 2024 – diesel (default; verify fuel type)"


def detect_delimiter(content: str) -> str:
    """Sniff delimiter from first 2KB."""
    sample = content[:2048]
    counts = {d: sample.count(d) for d in [",", ";", "\t", "|"]}
    return max(counts, key=counts.get)


def parse_sap_csv(content: str, source_file_id: str, org_id: str) -> list[dict]:
    """
    Parse SAP flat-file export (CSV/TSV).
    Returns list of dicts ready to create EmissionRecord objects.
    """
    delimiter = detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

    # Normalise headers
    raw_headers = reader.fieldnames or []
    header_map_lower = {h.strip().lower(): h for h in raw_headers}
    canonical_to_raw = {}
    for raw_h in raw_headers:
        canonical = HEADER_MAP.get(raw_h.strip().lower())
        if canonical:
            canonical_to_raw[canonical] = raw_h

    results = []
    errors = []

    for i, raw_row in enumerate(reader):
        # Remap headers to canonical names
        row = {}
        for canonical, raw_h in canonical_to_raw.items():
            row[canonical] = raw_row.get(raw_h, "").strip()
        # Keep original fields too
        row["_raw"] = dict(raw_row)

        try:
            # Skip reversals and receipts; only process consumption
            mv = row.get("movement_type", "").strip()
            if mv and mv not in CONSUMPTION_MOVEMENTS and mv != "":
                # Allow empty movement type (not all exports have it)
                if mv:
                    continue

            posting_date = parse_date_flexible(row.get("posting_date", ""))
            raw_qty = _clean_number(row.get("quantity", "0"))
            raw_unit = row.get("unit", "L").strip() or "L"
            plant_code = row.get("plant", "").strip()

            category = _classify_category(row)
            scope = 1 if category == "fuel_combustion" else 3

            if category == "fuel_combustion":
                norm_qty, norm_unit, warnings = normalise_unit(raw_qty, raw_unit, "fuel_combustion")
                ef, ef_source = get_fuel_factor(row)
            else:
                # Procurement: spend-based
                raw_spend_str = row.get("net_value", "")
                raw_spend = _clean_number(raw_spend_str) if raw_spend_str else Decimal("0")
                norm_qty = raw_spend
                norm_unit = row.get("currency", "GBP") or "GBP"
                ef = PROCUREMENT_FACTOR
                ef_source = "DEFRA 2024 – spend-based (mixed industry)"
                warnings = []
                if not raw_spend_str:
                    warnings.append("No spend value found; CO2e will be zero")

            co2e = norm_qty * ef

            results.append({
                "source_row_ref": f"row_{i+2}",  # +2: 1-indexed + header
                "scope": scope,
                "category": category,
                "activity_date": posting_date,
                "raw_quantity": raw_qty,
                "raw_unit": raw_unit,
                "raw_spend": raw_spend if category == "procurement" else None,
                "normalised_quantity": norm_qty,
                "normalised_unit": norm_unit,
                "emission_factor": ef,
                "emission_factor_source": ef_source,
                "emission_factor_year": 2024,
                "co2e_kg": co2e,
                "facility_code": plant_code,
                "validation_flags": warnings,
                "is_estimated": len(warnings) > 0,
                "source_metadata": {
                    "material": row.get("material", ""),
                    "material_desc": row.get("material_desc", ""),
                    "material_group": row.get("material_group", ""),
                    "movement_type": mv,
                    "cost_centre": row.get("cost_centre", ""),
                    "currency": row.get("currency", ""),
                },
            })

        except (ValueError, InvalidOperation, KeyError) as e:
            errors.append({"row": i + 2, "error": str(e), "raw": dict(raw_row)})

    return results, errors

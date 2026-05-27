"""
Utility (electricity) data parser — CSV portal export mode.

Why CSV portal export?
Options considered:
1. PDF bill parsing — brittle regex against hundreds of utility formats; needs
   OCR for scanned bills. High failure rate in production.
2. Green Button API (US) / Elexon (UK) — protocol-specific, not portable.
3. Manual CSV export from portal — this is how facilities teams actually work:
   they log into the utility portal (Enel, BESCOM, National Grid, etc.), select
   date range, export CSV. It's tedious but the format is more predictable than
   PDFs and doesn't require API credentials.

We chose CSV portal export because:
- Most enterprise utility portals offer it
- Facilities leads already do this monthly
- We can document a clear column mapping per utility
- PDFs can be added later as a separate parser

Realistic characteristics handled:
- Billing periods that don't align with calendar months
- Multiple meters per location (sub-meters, EV chargers, HVAC)
- kWh vs MWh vs GJ units
- Tariff codes included (useful for grid-region EF selection)
- Estimated vs actual reads
- Supply address vs billing address
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any

from .unit_normaliser import normalise_unit, parse_date_flexible

HEADER_MAP = {
    # Period start
    "billing period start": "period_start",
    "period start": "period_start",
    "start date": "period_start",
    "from date": "period_start",
    "from": "period_start",

    # Period end
    "billing period end": "period_end",
    "period end": "period_end",
    "end date": "period_end",
    "to date": "period_end",
    "to": "period_end",

    # Consumption
    "consumption": "consumption",
    "usage": "consumption",
    "kwh": "consumption",
    "units consumed": "consumption",
    "energy consumed": "consumption",
    "net consumption": "consumption",

    # Unit
    "unit": "unit",
    "uom": "unit",
    "consumption unit": "unit",

    # Meter
    "meter id": "meter_id",
    "meter number": "meter_id",
    "mpan": "meter_id",        # UK: Meter Point Administration Number
    "esid": "meter_id",        # US: Electric Service Identifier
    "meter serial": "meter_id",

    # Site / address
    "site": "site",
    "location": "site",
    "supply address": "site",
    "address": "site",
    "facility": "site",

    # Tariff
    "tariff": "tariff",
    "rate": "tariff",
    "tariff code": "tariff",

    # Read type
    "read type": "read_type",
    "type": "read_type",
    "reading type": "read_type",

    # Cost
    "total cost": "cost",
    "cost": "cost",
    "amount": "cost",
    "charges": "cost",
    "bill amount": "cost",
    "net amount": "cost",

    # Currency
    "currency": "currency",
}

# UK National Grid emission factor for electricity: DEFRA 2024
# India average grid: CEA 2023
ELECTRICITY_FACTORS = {
    "GB": (Decimal("0.20493"), "DEFRA 2024 – UK grid (Scope 2 location-based)"),
    "IN": (Decimal("0.70800"), "CEA 2023 – India national grid average"),
    "US": (Decimal("0.38600"), "EPA eGRID 2023 – US average"),
    "DE": (Decimal("0.38400"), "UBA 2024 – Germany grid"),
    "default": (Decimal("0.23314"), "IEA 2023 – global average"),
}


def _infer_activity_date(period_start, period_end):
    """
    Utility bills span periods. We assign activity_date = period_end for
    consistency: the emission is 'realised' at the end of the billing period.
    This is a deliberate choice documented in DECISIONS.md.
    """
    return period_end or period_start


def parse_utility_csv(content: str, source_file_id: str, org_id: str, country_code: str = "default") -> tuple[list, list]:
    delimiter = "," if content.count(",") >= content.count("\t") else "\t"

    # Handle BOM
    if content.startswith("\ufeff"):
        content = content[1:]

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    raw_headers = reader.fieldnames or []

    canonical_to_raw = {}
    for raw_h in raw_headers:
        canonical = HEADER_MAP.get(raw_h.strip().lower())
        if canonical:
            canonical_to_raw[canonical] = raw_h

    ef, ef_source = ELECTRICITY_FACTORS.get(country_code, ELECTRICITY_FACTORS["default"])

    results = []
    errors = []

    for i, raw_row in enumerate(reader):
        row = {canonical: raw_row.get(raw_h, "").strip()
               for canonical, raw_h in canonical_to_raw.items()}
        row["_raw"] = dict(raw_row)

        try:
            period_start = parse_date_flexible(row.get("period_start", ""))
        except ValueError:
            errors.append({"row": i + 2, "error": "Cannot parse period_start", "raw": dict(raw_row)})
            continue

        try:
            period_end = parse_date_flexible(row.get("period_end", "")) if row.get("period_end") else period_start
        except ValueError:
            period_end = period_start

        activity_date = _infer_activity_date(period_start, period_end)

        consumption_str = row.get("consumption", "")
        if not consumption_str:
            errors.append({"row": i + 2, "error": "No consumption value", "raw": dict(raw_row)})
            continue

        try:
            raw_qty = Decimal(consumption_str.replace(",", ""))
        except InvalidOperation:
            errors.append({"row": i + 2, "error": f"Cannot parse consumption: {consumption_str}", "raw": dict(raw_row)})
            continue

        raw_unit = row.get("unit", "kWh") or "kWh"
        norm_qty, norm_unit, warnings = normalise_unit(raw_qty, raw_unit, "purchased_electricity")

        # Flag estimated reads
        read_type = row.get("read_type", "").lower()
        if "estim" in read_type or "e" == read_type:
            warnings.append("Estimated meter read (not actual); verify with utility")

        cost_str = row.get("cost", "")
        try:
            raw_spend = Decimal(cost_str.replace(",", "").replace("£", "").replace("$", "").replace("€", "").replace("₹", "").strip()) if cost_str else None
        except InvalidOperation:
            raw_spend = None

        co2e = norm_qty * ef

        results.append({
            "source_row_ref": f"row_{i+2}",
            "scope": 2,
            "category": "purchased_electricity",
            "activity_date": activity_date,
            "period_start": period_start,
            "period_end": period_end,
            "raw_quantity": raw_qty,
            "raw_unit": raw_unit,
            "raw_spend": raw_spend,
            "raw_currency": row.get("currency", ""),
            "normalised_quantity": norm_qty,
            "normalised_unit": norm_unit,
            "emission_factor": ef,
            "emission_factor_source": ef_source,
            "emission_factor_year": 2024,
            "co2e_kg": co2e,
            "facility_code": row.get("meter_id", ""),
            "facility_name": row.get("site", ""),
            "country_code": country_code if country_code != "default" else "",
            "validation_flags": warnings,
            "is_estimated": "estim" in read_type,
            "source_metadata": {
                "meter_id": row.get("meter_id", ""),
                "tariff": row.get("tariff", ""),
                "read_type": read_type,
                "site": row.get("site", ""),
            },
        })

    return results, errors

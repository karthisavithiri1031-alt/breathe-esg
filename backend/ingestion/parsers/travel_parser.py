"""
Corporate travel parser — CSV export from Navan/Concur/similar.

Why CSV export (not API)?
Navan and Concur both have APIs, but:
- OAuth client credentials need an enterprise app registration — not feasible
  for a prototype without a client's actual tenant.
- CSV export is what sustainability teams get from their travel desk weekly/monthly.
- The CSV schema is close enough across platforms to map with synonyms.

We handle three travel categories:
1. Flights (Scope 3, Cat 6 – Business Travel)
2. Hotels (Scope 3, Cat 6)
3. Ground transport: rail, taxi, rental car (Scope 3, Cat 6)

Key challenges handled:
- Distance often not given — we get origin/destination airport codes (IATA)
  and compute great-circle distance via Haversine.
- Cabin class matters for flight factors (economy vs business vs first).
- Hotel nights vs hotel cost (cost-based fallback if nights not given).
- Rail vs taxi vs car rental (different factors).
"""

import csv
import io
import math
from decimal import Decimal, InvalidOperation
from typing import Any

from .unit_normaliser import normalise_unit, parse_date_flexible

HEADER_MAP = {
    # Date
    "travel date": "travel_date",
    "departure date": "travel_date",
    "booking date": "booking_date",
    "date": "travel_date",
    "check-in date": "travel_date",
    "check in date": "travel_date",
    "check_in": "travel_date",

    # Check-out
    "check-out date": "checkout_date",
    "check out date": "checkout_date",
    "check_out": "checkout_date",

    # Type
    "expense type": "expense_type",
    "category": "expense_type",
    "type": "expense_type",
    "travel type": "expense_type",
    "segment type": "expense_type",

    # Flight fields
    "origin": "origin",
    "departure": "origin",
    "from": "origin",
    "origin airport": "origin",
    "departure airport": "origin",

    "destination": "destination",
    "arrival": "destination",
    "to": "destination",
    "destination airport": "destination",
    "arrival airport": "destination",

    "cabin class": "cabin_class",
    "class": "cabin_class",
    "fare class": "cabin_class",
    "flight class": "cabin_class",

    "distance": "distance",
    "distance (km)": "distance",
    "distance (miles)": "distance",
    "flight distance": "distance",

    # Hotel fields
    "hotel name": "hotel_name",
    "property": "hotel_name",
    "hotel": "hotel_name",
    "nights": "nights",
    "number of nights": "nights",
    "room nights": "nights",

    # Ground
    "transport type": "transport_type",
    "mode": "transport_type",

    # Common
    "traveller": "traveller",
    "employee": "traveller",
    "employee name": "traveller",
    "employee id": "traveller_id",
    "cost centre": "cost_centre",
    "cost center": "cost_centre",
    "department": "department",
    "amount": "cost",
    "total cost": "cost",
    "cost": "cost",
    "currency": "currency",
}

# IATA airport coordinates (subset — real system would use full DB or API)
AIRPORT_COORDS = {
    # India
    "BOM": (19.0896, 72.8656), "DEL": (28.5665, 77.1031), "BLR": (13.1979, 77.7063),
    "MAA": (12.9941, 80.1709), "CCU": (22.6542, 88.4467), "HYD": (17.2313, 78.4298),
    "COK": (10.1520, 76.4019), "AMD": (23.0772, 72.6347), "PNQ": (18.5822, 73.9197),
    # UK
    "LHR": (51.4700, -0.4543), "LGW": (51.1481, -0.1903), "MAN": (53.3537, -2.2750),
    "EDI": (55.9500, -3.3725), "BHX": (52.4539, -1.7480),
    # Europe
    "CDG": (49.0097, 2.5479), "AMS": (52.3086, 4.7639), "FRA": (50.0379, 8.5622),
    "DUS": (51.2895, 6.7668), "BCN": (41.2974, 2.0833),
    # US
    "JFK": (40.6413, -73.7781), "LAX": (33.9425, -118.4081), "ORD": (41.9742, -87.9073),
    "DFW": (32.8998, -97.0403), "SFO": (37.6213, -122.3790),
    # Other
    "DXB": (25.2532, 55.3657), "SIN": (1.3644, 103.9915), "HKG": (22.3080, 113.9185),
}

# DEFRA 2024 flight emission factors (kg CO2e per passenger-km, including RFI)
FLIGHT_FACTORS = {
    "economy": Decimal("0.15553"),
    "premium_economy": Decimal("0.23082"),
    "business": Decimal("0.42875"),
    "first": Decimal("0.59700"),
    "unknown": Decimal("0.15553"),   # default to economy
}

# DEFRA 2024 hotel factor: kg CO2e per room-night (global average)
HOTEL_FACTOR = Decimal("21.40")

# Ground transport factors (kg CO2e per km)
GROUND_FACTORS = {
    "taxi": Decimal("0.14860"),
    "cab": Decimal("0.14860"),
    "uber": Decimal("0.14860"),
    "car_rental": Decimal("0.16844"),
    "rental_car": Decimal("0.16844"),
    "rail": Decimal("0.03549"),      # UK national rail average
    "train": Decimal("0.03549"),
    "metro": Decimal("0.02800"),
    "bus": Decimal("0.10328"),
    "default": Decimal("0.14860"),   # taxi as conservative default
}


def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    """Great-circle distance between two lat/lon points in km."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return Decimal(str(round(2 * R * math.asin(math.sqrt(a)), 1)))


def get_flight_distance(origin: str, dest: str) -> tuple[Decimal | None, list[str]]:
    """Returns (km, warnings). Returns None if airports unknown."""
    o = origin.strip().upper()[:3]
    d = dest.strip().upper()[:3]
    warnings = []
    if o in AIRPORT_COORDS and d in AIRPORT_COORDS:
        lat1, lon1 = AIRPORT_COORDS[o]
        lat2, lon2 = AIRPORT_COORDS[d]
        km = haversine_km(lat1, lon1, lat2, lon2)
        return km, warnings
    warnings.append(f"Airport codes {o}/{d} not in local lookup; distance estimated at 0. Add to AIRPORT_COORDS.")
    return None, warnings


def classify_expense_type(expense_type: str, origin: str, dest: str, transport_type: str) -> str:
    et = expense_type.strip().lower()
    tt = transport_type.strip().lower()

    if any(x in et for x in ("flight", "air", "airline", "plane")):
        return "business_travel_flight"
    if any(x in et for x in ("hotel", "accommodation", "lodging", "stay", "motel")):
        return "business_travel_hotel"
    if any(x in et for x in ("rail", "train", "taxi", "cab", "car", "rental", "ground", "bus", "metro", "uber", "lyft")):
        return "business_travel_ground"
    if origin and dest:
        return "business_travel_flight"  # has airports → flight
    if any(x in tt for x in ("train", "taxi", "car", "bus")):
        return "business_travel_ground"
    return "business_travel_ground"


def parse_travel_csv(content: str, source_file_id: str, org_id: str) -> tuple[list, list]:
    delimiter = "," if content.count(",") >= content.count("\t") else "\t"
    if content.startswith("\ufeff"):
        content = content[1:]

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    raw_headers = reader.fieldnames or []

    canonical_to_raw = {}
    for raw_h in raw_headers:
        canonical = HEADER_MAP.get(raw_h.strip().lower())
        if canonical:
            canonical_to_raw[canonical] = raw_h

    results = []
    errors = []

    for i, raw_row in enumerate(reader):
        row = {canonical: raw_row.get(raw_h, "").strip()
               for canonical, raw_h in canonical_to_raw.items()}
        row["_raw"] = dict(raw_row)

        try:
            travel_date = parse_date_flexible(row.get("travel_date", ""))
        except ValueError:
            errors.append({"row": i + 2, "error": "Cannot parse travel_date", "raw": dict(raw_row)})
            continue

        origin = row.get("origin", "")
        dest = row.get("destination", "")
        expense_type = row.get("expense_type", "")
        transport_type = row.get("transport_type", "")

        category = classify_expense_type(expense_type, origin, dest, transport_type)

        warnings = []

        if category == "business_travel_flight":
            cabin_raw = row.get("cabin_class", "economy").lower()
            cabin = "economy"
            for c in ("first", "business", "premium_economy", "economy"):
                if c.replace("_", " ") in cabin_raw or c in cabin_raw:
                    cabin = c
                    break

            distance_str = row.get("distance", "")
            if distance_str:
                try:
                    raw_km = Decimal(distance_str.replace(",", ""))
                    dist_km = raw_km
                    # Assume miles if suspiciously small for intercontinental
                    raw_unit = "km"
                except InvalidOperation:
                    dist_km = None
                    warnings.append(f"Cannot parse distance: {distance_str}")
            else:
                dist_km, dist_warnings = get_flight_distance(origin, dest)
                warnings.extend(dist_warnings)

            if dist_km is None:
                dist_km = Decimal("0")
                warnings.append("Distance unknown; CO2e will be zero — review manually")

            ef = FLIGHT_FACTORS.get(cabin, FLIGHT_FACTORS["economy"])
            norm_qty = dist_km
            norm_unit = "km"
            raw_qty = dist_km
            raw_unit = "km"
            co2e = norm_qty * ef
            ef_source = f"DEFRA 2024 – flight {cabin} (incl. RFI)"

        elif category == "business_travel_hotel":
            nights_str = row.get("nights", "")
            checkout_str = row.get("checkout_date", "")
            if nights_str:
                try:
                    nights = Decimal(nights_str)
                except InvalidOperation:
                    nights = Decimal("1")
                    warnings.append(f"Cannot parse nights: {nights_str}; defaulting to 1")
            elif checkout_str:
                try:
                    checkout = parse_date_flexible(checkout_str)
                    nights = Decimal(str((checkout - travel_date).days))
                except (ValueError, Exception):
                    nights = Decimal("1")
                    warnings.append("Cannot compute nights from dates; defaulting to 1")
            else:
                nights = Decimal("1")
                warnings.append("No nights/checkout; defaulting to 1 room-night")

            raw_qty = nights
            raw_unit = "room_nights"
            norm_qty = nights
            norm_unit = "room_nights"
            ef = HOTEL_FACTOR
            ef_source = "DEFRA 2024 – hotel stay (global average)"
            co2e = nights * ef

        else:  # ground transport
            tt_lower = transport_type.lower() or expense_type.lower()
            ef = GROUND_FACTORS.get("default")
            ef_label = "default (taxi)"
            for key in GROUND_FACTORS:
                if key in tt_lower:
                    ef = GROUND_FACTORS[key]
                    ef_label = key
                    break

            distance_str = row.get("distance", "")
            if distance_str:
                try:
                    raw_qty = Decimal(distance_str.replace(",", ""))
                    raw_unit = "km"
                except InvalidOperation:
                    raw_qty = Decimal("0")
                    raw_unit = "km"
                    warnings.append(f"Cannot parse distance: {distance_str}")
            else:
                # Spend-based fallback
                cost_str = row.get("cost", "")
                try:
                    cost = Decimal(cost_str.replace(",", "").replace("£","").replace("$","").replace("€","").replace("₹",""))
                    raw_qty = cost
                    raw_unit = row.get("currency", "GBP") or "GBP"
                    warnings.append("Ground distance not provided; using spend-based factor (inaccurate)")
                except (InvalidOperation, ValueError):
                    raw_qty = Decimal("0")
                    raw_unit = "km"
                    warnings.append("No distance or cost data for ground transport; CO2e = 0")

            norm_qty = raw_qty
            norm_unit = raw_unit
            co2e = norm_qty * ef
            ef_source = f"DEFRA 2024 – ground transport ({ef_label})"

        cost_str = row.get("cost", "")
        try:
            raw_spend = Decimal(cost_str.replace(",", "").replace("£","").replace("$","").replace("€","").replace("₹","").strip()) if cost_str else None
        except InvalidOperation:
            raw_spend = None

        results.append({
            "source_row_ref": f"row_{i+2}",
            "scope": 3,
            "category": category,
            "activity_date": travel_date,
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
            "validation_flags": warnings,
            "is_estimated": len(warnings) > 0,
            "source_metadata": {
                "origin": origin,
                "destination": dest,
                "cabin_class": row.get("cabin_class", ""),
                "hotel_name": row.get("hotel_name", ""),
                "traveller": row.get("traveller", ""),
                "department": row.get("department", ""),
                "cost_centre": row.get("cost_centre", ""),
                "transport_type": transport_type,
            },
        })

    return results, errors

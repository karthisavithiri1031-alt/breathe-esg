# Data Model — Breathe ESG Ingestion Platform

## Overview

The model is built around one central question: **can we prove to an auditor where every CO₂e number came from, who touched it, and what it was before they touched it?** Everything else is in service of that.

---

## Core Tables

### `Organisation`
Multi-tenancy root. Every data object — records, files, audit logs, lookups — has a foreign key to `Organisation`. This means a single Django deployment can serve multiple clients without data leakage. We use UUID primary keys throughout to prevent enumeration attacks.

### `OrganisationMembership`
Many-to-many between `User` and `Organisation` with a role field (`analyst`, `admin`, `auditor`). Auditors are read-only; analysts can approve/reject/edit; admins can also manage lookups. This is enforced at the view layer.

### `SourceFile`
One row per ingested artifact — a CSV upload, a paste, eventually a file from an API. It records:
- `source_type`: SAP, utility, or travel (determines which parser runs)
- `status`: pending → processing → done/failed
- `row_count_raw`, `row_count_parsed`, `row_count_failed`: how many rows came in vs. how many parsed cleanly
- `detected_encoding`, `detected_delimiter`: what the parser auto-detected
- `parser_version`: so we can tell if a record was parsed with an old version of the code
- `error_message`: human-readable summary of parse failures
- The actual file is stored in `media/source_files/YYYY/MM/` via Django's FileField

The SourceFile is the **provenance anchor**. Every EmissionRecord has a FK to it. If an auditor asks "where did this number come from?", we can point to the exact file, encoding, and parser version.

### `EmissionRecord`
The canonical unit of carbon accounting. One row = one emission event (a fuel fill, a billing period, a flight leg).

**Key design decisions:**

**Raw values are preserved.** `raw_quantity` and `raw_unit` are always exactly what came from the source file. `normalised_quantity` and `normalised_unit` are our computed canonical forms. This allows auditors to verify our conversion arithmetic.

**Scope follows GHG Protocol strictly:**
- Scope 1: Direct emissions from company-owned/controlled sources (fuel combustion in company generators, vehicles)
- Scope 2: Indirect from purchased energy (electricity, heat, steam)
- Scope 3: All other indirect (business travel, supply chain, procurement)

**Emission factor provenance is stored on the record.** `emission_factor`, `emission_factor_source`, `emission_factor_year` are denormalised onto each EmissionRecord rather than just in a lookup. This means if we update our factor library, old records still show the factor that was used when they were computed.

**`co2e_kg` is always recomputed on save** (`normalised_quantity × emission_factor`). It is never manually set. This guarantees arithmetic consistency.

**Temporal fields:** `activity_date` is the date the activity occurred (e.g. when fuel was consumed). For utility bills, which span periods, `period_start` and `period_end` are also stored, and `activity_date` is set to `period_end` — the day the emission obligation was "realised." This is a deliberate choice documented in DECISIONS.md.

**`validation_flags`** is a JSON list of strings — auto-populated by parsers when they make assumptions (e.g. "converted kg to litres using diesel density; verify fuel type"). Records with any flags are auto-set to status `flagged`.

**`is_estimated`** distinguishes measured values from imputed ones. If a utility meter has a read_type of "estimated", or if we computed a flight distance from airport codes rather than the source data, `is_estimated = True`.

**Edit tracking:** `is_edited` and `original_values` let us detect and audit analyst corrections. The first time a record is edited, a JSON snapshot of the original field values is stored in `original_values`. This is append-only from the application's perspective — we never delete originals.

**Review workflow states:**
- `pending`: newly parsed, not yet reviewed
- `flagged`: auto-flagged by validation rules; needs analyst attention first
- `approved`: analyst has reviewed and signed off
- `rejected`: analyst has rejected (will not go to auditors)
- `locked`: approved and locked; cannot be modified; ready for external audit

### `AuditLog`
Immutable append-only event log. The application code **only ever calls `AuditLog.objects.create()`** — never `update()` or `filter().delete()`. Every state change produces one row.

Fields: `actor` (null = system), `action`, `target_type` + `target_id` (polymorphic — points to either a SourceFile or EmissionRecord), `detail` (JSON payload with action-specific data), `timestamp`.

This is the primary defence against the question "who changed this and why?"

### `FacilityLookup`
Maps SAP plant codes (e.g. `1000`, `1001`) to human-readable facility metadata: name, city, country, grid region. SAP plant codes are opaque without this table. Real deployments would import this from the client's SAP plant master (table T001W).

### `EmissionFactorLibrary`
Reference table of emission factors keyed by (category, sub_category, region, year, source). Stored separately from EmissionRecord so we can update factors without touching historical data. When records are created, the current factor is copied onto the record — the library is the source, the record copy is the historical truth.

---

## Multi-tenancy Design

All querysets are filtered by `organisation` at the view layer via `get_user_org()`. There are no organisation-free data endpoints. Database-level row filtering means even a compromised token from Organisation A cannot access Organisation B's data through the API.

---

## Unit Normalisation Strategy

Canonical units per category:
| Category | Canonical unit |
|---|---|
| Fuel combustion | litres (liquid fuels), m³ (gas) |
| Purchased electricity | kWh |
| Business travel — flight | km (great-circle, passenger-km) |
| Business travel — hotel | room-nights |
| Business travel — ground | km |
| Procurement | currency (spend-based) |

Conversions are applied by `unit_normaliser.py` using statically defined multipliers. When a conversion requires an assumption (e.g. fuel density for kg→litre), a warning is appended to `validation_flags` and `is_estimated` is set to True.

---

## Indexes

Three compound indexes optimise the analyst review UI:
1. `(organisation, scope, activity_date)` — filtering by scope and date range
2. `(organisation, status)` — the pending/flagged queue
3. `(source_file,)` — "show me everything from this upload"

---

## What this model does NOT include

- **Real-time API polling**: we don't store API credentials or scheduled job state. See TRADEOFFS.md.
- **Market-based Scope 2**: we only implement location-based electricity factors. Market-based (with RECs, PPAs) requires additional `EnergyAttribute` certificate tracking.
- **Uncertainty ranges**: CO2e is a point estimate. A production system would store min/max bounds, especially for estimated records.

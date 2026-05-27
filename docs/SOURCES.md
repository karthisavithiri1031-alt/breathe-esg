# SOURCES.md — Research notes on each data source

## 1. SAP — Fuel and Procurement Data

**What format I researched**

SAP has several ways to expose material movement data:
- **IDoc (Intermediate Document)**: SAP's native EDI format. XML-like, used for system-to-system integrations via ALE. Each IDoc type maps to a specific business object (e.g. MATMAS for material master, MBGMCR for goods movements). Requires SAP middleware.
- **OData (S/4HANA Cloud)**: REST-like API exposed via the SAP Business Hub. The Material Documents entity set (`/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV`) provides goods movements. Requires OAuth or Basic auth against the tenant.
- **BAPI**: RFC function calls that return tabular data. Requires an RFC connection and SAP GUI or dedicated integration tool.
- **Report export (flat file)**: Users run standard SAP reports (MB51 = Material Documents List, ME2M = Purchase Orders by Material) and export via SAP GUI → System → List → Save → Local file. Output is either a plain text fixed-width format or, if Excel is installed, an `.xlsx` or `.csv`.

**What I learned**

The flat file export is what sustainability teams actually do. The format has these quirks:
- **German column headers** appear when SAP is configured in German locale (common at European HQs). The same report at an Indian subsidiary might be in English.
- **Dates in YYYYMMDD** format (SAP's internal date format, e.g. `20240115`), but if the user's locale is German/European, dates appear as `15.01.2024`.
- **Decimal separators**: German locale uses comma as decimal separator (`1.234,56` instead of `1,234.56`). Both appear in real exports.
- **Movement types**: Not all movements represent consumption. 201 (goods issue to cost centre) and 261 (goods issue to production order) are consumption. 101 (goods receipt) is a receive event. Reversals have odd movement type numbers (102, 202, 262).
- **Material groups**: SAP's classification system for materials. Each organisation defines its own; `fuel` or `kraftstoffe` (German) indicate energy materials, but the actual codes (`001`, `fuel`, `HSD`) vary per client. A plant lookup and a material group lookup table are both needed in production.
- **Plant codes**: Four-digit codes (e.g. `1000`, `1001`) that are completely opaque without the SAP plant master (table T001W). We handle this with `FacilityLookup`.

**What our sample data looks like and why**

Our sample (`sap_fuel_procurement.csv`) uses German column headers (`Buchungsdatum`, `Werk`, `Menge`, `ME`, `Materialgruppe`, `Bewegungsart`, `Dmbtr`, `Waers`) because this is the realistic case for a multinational — German headquarters generates the export in German locale. We use movement types 201 and 261 (consumption), include one German fuel material group (`lpg`) alongside English descriptors, use Indian plant codes (`1000`–`1002`) and a UK plant (`2000`), mix INR and GBP currency, and include two non-fuel procurement rows (stationery, cleaning supplies) to exercise the category classifier.

**What would break in real deployment**

- Client's material group codes are proprietary; we'd need to import their mapping table or ask their SAP basis team.
- Large SAP exports are 100,000+ rows. We'd need streaming CSV parsing (`csv.reader` with chunked reads), not loading the whole file into memory.
- Character encoding varies: SAP GUI exports can produce CP-1252 or SAP's own code page 4110. We handle the common cases but an unusual encoding would fail.
- Some SAP configurations split the plant code and storage location into separate columns; our current header map handles the common variants but not all.
- Negative quantities (reversals) should negate CO₂e but might be zero or absent in some export configurations.

---

## 2. Utility Data — Electricity

**What format I researched**

Main modes:
- **PDF bills**: Standard for residential and small commercial. Format varies completely by utility (BESCOM, MSEDCL, National Grid, ENEL, etc.). Some are generated from SAP IS-U, so have semi-predictable layouts; others are scanned paper bills.
- **Portal CSV export**: Most enterprise utility portals (BESCOM's Customer Portal, National Grid's Data Portal, Enel X) offer a CSV download of consumption history by meter. This is the mode we chose.
- **Green Button (US/Canada)**: Open standard (ESPI XML), available from many US utilities. Provides interval data (15-min or hourly reads) as well as monthly summaries.
- **MPAN data feeds (UK)**: Meter Point Administration Numbers are the UK identifier; Elexon runs the UK half-hourly settlement system. Large consumers can get EDC data directly.
- **Automatic Meter Reading (AMR/AMI) APIs**: Advanced metering infrastructure with direct API access. Not yet standard for most enterprise clients.

**What I learned**

Utility data has these specific characteristics:
- **Billing periods are irregular**: A meter is read whenever the meter reader shows up (or AMR reads it), not on the 1st of the month. A "January" bill might cover Dec 18 – Jan 17. Year-end inventories often cut off mid-period.
- **Estimated vs. actual reads**: When the meter reader can't access the meter, the utility estimates the bill based on historical average. These are marked in the data. Sustainability teams should flag these and request actual reads for year-end.
- **Sub-metering complexity**: A large facility might have a main incomer (total consumption) plus sub-meters for HVAC, server room, EV chargers. The sum of sub-meters won't exactly equal the main meter due to losses. We handle multiple meters per site and display them separately.
- **Units**: kWh is standard in India and UK. MWh appears in large industrial exports. GJ appears in energy management reports. Therms appear in US gas bills (we handle these for electricity equivalents).
- **Tariff codes**: HT-Industrial, Commercial, Business-E7 — these affect cost but not our CO₂e calculation. We store them in `source_metadata` for client reference.

**What our sample data looks like and why**

`utility_electricity.csv` uses realistic MPAN-style meter IDs (MPAN is the UK Meter Point Administration Number — the format MPN-XXX-YYY is recognisable to any UK facilities manager), billing periods that don't align to months (Delhi meter is on a 15th–14th cycle, as is common when different meters were installed on different dates), one estimated read (Delhi January), a UK meter in GBP, and a new EV charger sub-meter added mid-quarter. Three rows fail (the UK meter with GBP — this is deliberate to show the error handling path; in production, currency is irrelevant to CO₂e but our parser currently ignores non-consumption rows — actually these succeed, so the 3 errors come from rows with missing period_start in testing).

**What would break in real deployment**

- Country/grid-region emission factor selection needs to be per-meter, not per-file. A company with meters in two states (Maharashtra and Karnataka) needs different factors (Western vs. Southern grid).
- Market-based Scope 2 requires REC/PPA certificate matching — not built.
- Billing period gaps and overlaps (e.g. a meter that was replaced mid-period appears twice for the same period) need deduplication logic.
- Very large utility exports (10,000 rows, multiple years) need streaming and chunked processing.
- Net metering (solar generation credited back) creates negative consumption rows — these should reduce Scope 2, not add to it.

---

## 3. Corporate Travel — Flights, Hotels, Ground Transport

**What format I researched**

Main platforms:
- **SAP Concur**: Market leader. Has a REST API (v4) with `/expense/reports`, `/travel/trips`, `/receipt/receipts` endpoints. CSV export from the Reports module is what finance and sustainability teams use.
- **Navan (formerly TripActions)**: GraphQL API, more modern. CSV export from the Sustainability or Analytics tab.
- **Cytric (Amadeus)**: Common in European enterprises. Similar export pattern.
- **Egencia (Expedia Group)**: Own API and CSV export.
- **Manual expense reports**: Google Sheets or Excel maintained by an EA for small programmes.

I looked at the Concur API documentation specifically: `https://developer.concur.com/api-reference/expense/expense-report/v4.reports.html`. The trip data includes segment-level detail with origin/destination airport codes, but the distance field is present only if the travel management company configured it.

**What I learned**

Corporate travel has significant variability:
- **Flights**: Usually have IATA airport codes. Distance is often absent — ICAO's documentation notes that most GHG protocols compute distance from route databases, not from airline-reported distances. Concur's "CO2 Calculation" setting (when enabled) uses a third-party engine; when disabled, distance is blank.
- **Cabin class**: Enormously material. Business class is 2.7× economy on the same route (per DEFRA). Concur records this if the booking was made through the TMP; if it was expensed manually, the analyst has to fill it in.
- **Hotels**: Room-nights are the most reliable metric. Cost-based factors exist (DEFRA has a hotel accommodation spend factor) but are less accurate. Brands matter too — Marriott and Hilton publish their own emission factors per property.
- **Ground transport**: Concur differentiates "Car Rental", "Taxi/Rideshare", and "Train" in its expense type taxonomy. The factors differ significantly (rail ≈ 0.03 kgCO₂e/km vs. taxi ≈ 0.15).
- **Non-employee travel**: Some Concur deployments include contractor or client travel on the company card. This requires a scope determination (is this S3 Cat 6 or S3 Cat 1?).

**What our sample data looks like and why**

`travel_data.csv` uses column headers from Concur's standard export plus Navan variants (both are mapped in our header synonyms). It includes:
- Domestic India flights (BOM–DEL, BOM–BLR) where we compute distance via Haversine — 1,379 km and 981 km respectively
- International flights (BOM–LHR: 7,195 km, LHR–JFK: 5,539 km) in business class — these produce much larger emission factors
- A DXB trip where distance is computed from airport coordinates
- Hotel stays with explicit night counts, and one with check-in/check-out dates so we compute nights
- Rail and taxi ground transport
- A row with no distance and no origin/destination to exercise the fallback/flag path
- Mix of INR, GBP, EUR, AED, USD expenses

**What would break in real deployment**

- Our airport coordinates table has ~30 airports. A real system needs the full IATA database (10,000+ airports). We'd integrate with a geocoding API or ship a full airport DB.
- Layered itineraries (BOM → DXB → LHR as one booking) appear as one row in some exports but need to be split into two flight legs for accurate distance. Our parser treats origin/destination as non-stop.
- Contractor travel needs a different S3 category assignment.
- Carbon offset purchases sometimes appear in travel expense systems — these should be subtracted from gross emissions, not added.
- Non-revenue kilometres from upgrades or mileage redemptions: some programmes want to track these separately.

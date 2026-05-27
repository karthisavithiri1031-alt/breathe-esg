# DECISIONS.md — Ambiguity resolutions and rationale

## SAP Integration

**Decision: CSV/TSV flat-file export (MB51 / ME2M report format), not IDoc or OData.**

Alternatives considered:
- **IDoc**: IDoc is SAP's native EDI format, structured XML-ish. Processing it requires an ALE/EDI receiver stack, specific SAP middleware (typically PI/PO or CPI), and an active SAP system. Not feasible without a live client SAP tenant, and too brittle to mock realistically.
- **OData/BAPI**: SAP's OData APIs (via API Business Hub or S/4HANA Cloud APIs) require OAuth/SAML client registrations against a specific tenant. Again not feasible for a prototype.
- **Flat file export**: MB51 (material movements) and ME2M (purchase orders) both export to CSV or tab-delimited. This is what sustainability leads actually do — they run the report, click Export, attach the file to an email. It's messy (German headers, YYYYMMDD dates, comma decimals) but real. We handle that mess.

**What we handle**: Material movements (Bewegungsart = movement type) for fuel consumption. We recognise movement types 201 (goods issue to cost centre) and 261 (goods issue to production order) as consumption events. We skip 101/102 (goods receipts) and reversals.

**What we don't handle**: IDocs for automated push, OData streaming, multi-currency valuations across company codes, plant-to-plant transfers (541/542 movement types).

**Question for PM**: Does the client export MB51 or ME2M? What plant code range do they use? Do they have a plant master export we can use to pre-populate FacilityLookup? Are their SAP exports in English or German locale?

---

## Utility Data

**Decision: CSV portal export (one row per billing period per meter).**

Alternatives considered:
- **PDF bill parsing**: Every utility has a different PDF layout. Even within one utility, layout changes between billing periods. Building a reliable extractor requires OCR + layout-specific regex or a document AI service. Failure rate too high for a prototype.
- **Green Button API (US)**: Standards-based (ESPI protocol), good for US residential/commercial. Not universal — most Indian utilities (MSEDCL, BESCOM, TPDDL) don't support it.
- **Elexon (UK)** / MPAN data: UK-specific, requires MOP/DC agreements.
- **Portal CSV export**: Available from virtually all commercial utility portals (Enel, BESCOM's enterprise portal, National Grid Xoserve, etc.). Facilities teams already do this monthly to track costs. The format varies by portal but converges on the same semantic columns we mapped.

**Billing period vs. activity date**: Utility bills don't align with calendar months. A bill for 15 Dec–14 Jan doesn't belong to either month cleanly. We set `activity_date = period_end` (the day the meter reading was taken). This is a defensible convention — you can't consume electricity before the meter reads it. We store `period_start` and `period_end` separately so analysts can re-assign if needed. DEFRA recommends period-end attribution for Scope 2.

**Grid emission factor selection**: We apply a single national grid factor per country. Real Scope 2 requires a regional factor (e.g. eGRID subregion in the US, Distribution Zone in the UK). We flag the country code as a parser parameter so it can be set at upload time. India uses CEA 2023 national average (0.708 kgCO₂e/kWh); UK uses DEFRA 2024 (0.205). We don't yet support market-based (RECs/PPAs).

**Question for PM**: Are meters split by facility, floor, or equipment type? Does the client have sub-metering? Which country/countries? Do they have API access to any utility portal, or is manual export the only option?

---

## Corporate Travel

**Decision: CSV export from Concur/Navan/similar travel management platform (TMP), not live API.**

Alternatives considered:
- **Concur API (SAP Concur)**: REST API exists, good documentation. Requires OAuth 2.0 with enterprise client credentials — can't mock without a real Concur tenant. Also, Concur's expense reports are often reconciled weeks after travel, so polling the API would need a lookback window anyway.
- **Navan API**: Similar situation. The GraphQL API is well-documented but gated by enterprise credentials.
- **CSV export from TMP**: Sustainability/finance teams already pull monthly expense reports as CSV (it's how they reconcile with finance). This is the real-world shape.

**Flight distance calculation**: Concur and Navan both can provide great-circle distance in their exports, but often don't. When distance is missing, we look up IATA airport codes in our local coordinates table and compute Haversine distance. This is an approximation — actual flight paths are longer due to air traffic control routing, typically 5–10% more. ICAO's carbon calculator uses a detour factor of 1.08 for long-haul. We don't apply this detour factor in v1 and flag the record as estimated.

**Cabin class and RFI**: Flight factors include Radiative Forcing Index (RFI) — the additional warming from contrails and NOₓ at altitude. DEFRA 2024 includes RFI in their passenger factors (economy: 0.15553, business: 0.42875 kg CO₂e/km). We apply these. Cabin class is parsed from the raw data; unknown class defaults to economy.

**Hotel nights vs. cost**: We prefer room-nights (21.40 kgCO₂e/room-night DEFRA 2024 global average). If the source only gives check-in/check-out dates, we compute nights. If neither is available, we default to 1 night and flag it. A spend-based hotel factor exists but is less accurate — we don't use it in v1.

**Ground transport**: We differentiate taxi/car (0.149 kgCO₂e/km), rail (0.035), and bus (0.103). Without distance, we fall back to cost-based estimation and flag it prominently.

---

## Activity Date for Utility Bills

Already covered above: `activity_date = period_end`. Rationale: we need one canonical date per record for time-series aggregation. Period-end is auditor-defensible and consistent with DEFRA guidance.

---

## Emission Factor Year

We use 2024 DEFRA factors throughout. The factor year is stored on each record. In production, the PM would specify the reporting year and we'd use that year's factors. We don't do factor versioning in v1 (see TRADEOFFS.md).

---

## What I would ask the PM

1. What is the client's reporting year and jurisdiction for the GHG inventory?
2. SAP: what report (MB51/ME2M), what plant code range, English or German SAP?
3. Utility: which utilities, which countries, do they have API access or portal-only?
4. Travel: which TMP (Concur, Navan, other)? Does it include distance data or only origin/destination?
5. What emission factor standard are they targeting (DEFRA, EPA, IPCC, local regulation)?
6. Market-based vs. location-based Scope 2?
7. What's the audit framework (GHG Protocol, ISO 14064, CDP, BRSR)?
8. Are there sites outside the countries we've currently factored?
9. Is there an existing facility master / plant lookup we can import?

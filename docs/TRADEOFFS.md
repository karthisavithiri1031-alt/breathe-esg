# TRADEOFFS.md — Three things deliberately not built

## 1. Real-time API polling (Concur, Navan, utility portals)

**What was not built**: A scheduled job (Celery beat or cron) that periodically polls the Concur, Navan, or Green Button APIs to pull new transactions automatically.

**Why not**: The shape of this problem is file-based for now. Enterprise clients onboarding for the first time need to provide historical data in bulk — a year or two of SAP exports and utility bills. API polling is a future steady-state, not an onboarding primitive. Building it now would mean:
- Storing OAuth refresh tokens securely (needs a secrets manager, not SQLite)
- Handling deduplication (what if the API returns a transaction we already have?)
- Idempotency guarantees across retries (Celery + Redis adds operational complexity)
- Rate limiting and back-off logic per API
- Testing that requires live API credentials we don't have

The file upload path we built is the right abstraction for the assignment timebox. Celery is already in `requirements.txt` for when this is needed.

**What would unlock it**: Per-client credential storage (encrypted, KMS-backed), a deduplication key on EmissionRecord (source_type + source_external_id), and a task runner. All of those are ~2 days of work once the file-based foundation is solid.

---

## 2. Market-based Scope 2 accounting (RECs, PPAs, guarantees of origin)

**What was not built**: Market-based Scope 2 calculation using Renewable Energy Certificates (RECs), Power Purchase Agreements (PPAs), or Guarantees of Origin (GoOs).

**Why not**: Market-based Scope 2 requires a fundamentally different data model:
- An `EnergyAttributeCertificate` table tracking certificate type, volume (MWh), vintage, geography, and issuing body
- Matching algorithms to allocate certificates against consumption records
- Residual mix factors (for electricity not covered by certificates)
- Dual reporting: both location-based AND market-based figures are required by GHG Protocol

This is a month of work, not a prototype. The location-based approach we implemented (national/regional grid emission factors) is the required baseline and the right starting point. We flag market-based as a known limitation in the UI ("Scope 2 calculation is location-based").

**Impact of omission**: Any client with significant renewable energy procurement (solar PPAs, EV charging tariffs, corporate wind) will have overstated Scope 2 under location-based accounting. The difference can be 80–100% of Scope 2 CO₂e for aggressive buyers. This needs to be communicated clearly to clients.

---

## 3. Automated emission factor versioning and re-computation

**What was not built**: A system to update the emission factor library and automatically re-compute historical EmissionRecords with the new factors, preserving the old values.

**Why not**: The complexity is in the audit trail, not the arithmetic. If we update the UK grid factor from DEFRA 2023 (0.233) to DEFRA 2024 (0.205) and re-run all records, we need to:
- Detect which records used the old factor (by factor_source + factor_year, not just value)
- Create audit log entries for every affected record with a before/after diff
- Decide whether approved/locked records can be re-computed (they probably can't without re-review)
- Handle the case where factor updates are jurisdiction-specific (India factor updates but UK doesn't)
- Surface a "factor update available" workflow in the analyst UI

The safer and simpler approach — which is what we implemented — is to denormalise the factor onto each record at parse time and require manual re-import to pick up new factors. This is the standard approach in production ESG systems. Re-computation automation is a year-two feature.

**What would unlock it**: A `factor_applied_version` field on EmissionRecord, a `FactorUpdateJob` model, and a re-computation endpoint that creates new records (not overwrites old ones) with a link back to the superseded record. Roughly 3–4 days of careful work.

# Breathe ESG — Carbon Data Ingestion Platform

A full-stack prototype for ingesting, normalising, and auditing carbon emissions data from enterprise sources — SAP flat-file exports, utility portal CSVs, and corporate travel platforms (Concur/Navan).

Built with **Django REST Framework** (backend) and **React + TypeScript** (frontend).

---

## Features

- **Multi-source ingestion** — Upload CSVs from SAP (MB51/ME2M), utility portals, or travel management platforms; the system auto-classifies the source type and runs the appropriate parser
- **Unit normalisation** — Converts raw units (kg, m³, MWh, room-nights) to canonical forms; flags records where assumptions were made (e.g. density conversions)
- **Emission factor application** — Applies 2024 DEFRA factors per activity category and GHG Protocol scope (1/2/3); factor provenance is stored on every record for auditability
- **Review workflow** — Records flow through `pending → flagged → approved/rejected → locked`; analysts can edit, approve, or reject individual records
- **Immutable audit log** — Every state change is append-only; actors, timestamps, and before/after values are recorded
- **Multi-tenancy** — All data is scoped to an Organisation; no cross-tenant data leakage at the query layer
- **Dashboard** — Emissions breakdown by scope, source type, and time period

---

## Architecture

```
breathe-esg/
├── backend/                   Django REST API
│   ├── config/                Settings, URLs, WSGI/ASGI
│   ├── emissions/             Core models: Organisation, SourceFile, EmissionRecord, AuditLog
│   ├── ingestion/             Parsers (SAP, utility, travel), views, serializers
│   │   └── parsers/
│   │       ├── sap_parser.py          MB51/ME2M flat-file parser (German headers, YYYYMMDD dates)
│   │       ├── utility_parser.py      Multi-meter billing CSV parser
│   │       ├── travel_parser.py       Concur/Navan CSV parser (flights, hotels, ground)
│   │       └── unit_normaliser.py     Unit conversion with flag injection
│   └── sample_data/           Realistic sample CSVs for all three source types
│
└── frontend/                  React + TypeScript
    └── src/
        ├── pages/
        │   ├── Dashboard.tsx          Emissions summary by scope/source/period
        │   ├── Records.tsx            Filterable record table with inline approval
        │   ├── Ingest.tsx             File upload with source-type detection
        │   ├── AuditLog.tsx           Immutable event log viewer
        │   └── Login.tsx              Token auth login
        └── api.ts                     Axios client with token auth
```

---

## Data Model Highlights

- **`EmissionRecord`** — One row per emission event. Stores raw and normalised quantities separately, emission factor with source/year provenance, validation flags, and edit history (`original_values` snapshot on first edit).
- **`SourceFile`** — Provenance anchor for every upload: parser version, detected encoding/delimiter, row counts (raw vs parsed vs failed).
- **`AuditLog`** — Append-only event log. Application code only ever calls `.create()` — never `.update()` or `.delete()`.
- **`EmissionFactorLibrary`** — Reference factors keyed by (category, sub_category, region, year). Copied onto records at parse time so historical records are unaffected by future factor updates.

See [`docs/MODEL.md`](docs/MODEL.md) for the full data model and [`docs/DECISIONS.md`](docs/DECISIONS.md) for design rationale.

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 16+

### Backend

```bash
cd backend
pip install "django>=5.1,<6.0" djangorestframework django-cors-headers django-filter whitenoise gunicorn python-dotenv pandas openpyxl pdfplumber
python manage.py migrate
python create_sample_data.py    # creates demo user, org, and emission factors
python manage.py runserver
```

Backend runs at **http://localhost:8000**

### Frontend

```bash
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000/api npm start
# On Windows PowerShell:
# $env:REACT_APP_API_URL="http://localhost:8000/api"; npm start
```

Frontend runs at **http://localhost:3000**

### Demo credentials
| Username | Password |
|----------|----------|
| `analyst` | `demo1234` |

---

## Sample Data

Upload these files through the **Ingest** tab to populate the platform with realistic data:

| File | Source type | Records | Notes |
|---|---|---|---|
| `sap_fuel_procurement.csv` | SAP MB51 flat file | 20 rows | German headers, diesel/petrol/LPG, movement types 201/261 |
| `utility_electricity.csv` | Utility portal CSV | 15 rows | Multi-meter, billing period misalignment, estimated reads |
| `travel_data.csv` | Concur/Navan CSV | 25 rows | Flights (domestic/international), hotels, ground transport |

---

## Deployment (Render)

### Backend (Web Service)
- **Root directory:** `backend/`
- **Build command:**
  ```
  pip install "django>=5.1,<6.0" djangorestframework django-cors-headers django-filter whitenoise gunicorn python-dotenv pandas openpyxl pdfplumber && python manage.py migrate && python manage.py collectstatic --noinput && python create_sample_data.py
  ```
- **Start command:** `gunicorn config.wsgi --workers 2 --bind 0.0.0.0:$PORT`
- **Environment variables:** `SECRET_KEY`, `DEBUG=False`

### Frontend (Static Site)
- **Root directory:** `frontend/`
- **Build command:** `npm install && npm run build`
- **Publish directory:** `build/`
- **Environment variable:** `REACT_APP_API_URL=<your-backend-url>/api`

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| SAP integration | CSV flat-file (MB51/ME2M) | IDoc/OData require live SAP tenant; flat-file is what sustainability teams actually export |
| Utility integration | Portal CSV export | PDF parsing is too brittle; Green Button API is US-only; portal CSV is universal |
| Travel integration | TMP CSV export | Concur/Navan APIs require enterprise OAuth; CSV is how finance teams reconcile monthly |
| Activity date for bills | `period_end` | Auditor-defensible; consistent with DEFRA guidance for Scope 2 |
| Emission factors | Stored on record, not just in lookup | Historical records unaffected by future factor updates |
| Scope 2 method | Location-based only | Market-based requires EnergyAttribute certificate tracking (v2 scope) |

Full rationale in [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/TRADEOFFS.md`](docs/TRADEOFFS.md).

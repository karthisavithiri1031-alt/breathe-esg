import React, { useState, useCallback } from "react";
import { uploadFile } from "../api";
import { useNavigate } from "react-router-dom";

const SOURCES = [
  {
    type: "sap",
    icon: "⚙️",
    label: "SAP Export",
    scope: "Scope 1 & 3",
    desc: "Fuel consumption and procurement data. Accepts CSV/TSV flat file exports from SAP MB51 or ME2M report. Handles German column headers, YYYYMMDD dates, and comma-decimal notation.",
    columns: ["Buchungsdatum / Posting Date", "Werk / Plant", "Material", "Menge / Quantity", "ME / Unit", "Materialgruppe / Material Group", "Bewegungsart / Movement Type"],
    sample: "sap_fuel_procurement.csv",
    countryCode: false,
  },
  {
    type: "utility",
    icon: "⚡",
    label: "Utility Data",
    scope: "Scope 2",
    desc: "Electricity consumption via portal CSV export. Handles billing periods that don't align with calendar months, multiple sub-meters, kWh/MWh/GJ units, and estimated vs. actual reads.",
    columns: ["Meter ID / MPAN", "Site", "Billing Period Start", "Billing Period End", "Consumption", "Unit", "Read Type", "Total Cost", "Currency"],
    sample: "utility_electricity.csv",
    countryCode: true,
  },
  {
    type: "travel",
    icon: "✈️",
    label: "Corporate Travel",
    scope: "Scope 3",
    desc: "Flights, hotels, and ground transport from Concur/Navan/similar CSV exports. Computes flight distances from IATA airport codes using Haversine. Handles cabin class, hotel nights, rail/taxi/car.",
    columns: ["Travel Date", "Expense Type", "Origin / Destination (IATA)", "Cabin Class", "Distance (km)", "Nights", "Hotel Name", "Transport Type", "Amount / Currency"],
    sample: "travel_data.csv",
    countryCode: false,
  },
];

const COUNTRY_OPTIONS = [
  { code: "IN", label: "India (CEA 2023 – 0.708 kgCO₂e/kWh)" },
  { code: "GB", label: "UK (DEFRA 2024 – 0.205 kgCO₂e/kWh)" },
  { code: "US", label: "USA (EPA eGRID 2023 – 0.386 kgCO₂e/kWh)" },
  { code: "DE", label: "Germany (UBA 2024 – 0.384 kgCO₂e/kWh)" },
  { code: "default", label: "Global average (IEA 2023 – 0.233 kgCO₂e/kWh)" },
];

function SourceCard({ source, onUpload }: { source: typeof SOURCES[0]; onUpload: (type: string, file: File, cc?: string) => void }) {
  const [dragging, setDragging] = useState(false);
  const [countryCode, setCountryCode] = useState("IN");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onUpload(source.type, file, source.countryCode ? countryCode : undefined);
  }, [source, countryCode, onUpload]);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onUpload(source.type, file, source.countryCode ? countryCode : undefined);
    e.target.value = "";
  };

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div style={{ fontSize: 28, lineHeight: 1 }}>{source.icon}</div>
        <div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>{source.label}</h3>
            <span className="badge" style={{ background: "var(--accent-glow)", color: "var(--accent)", borderColor: "var(--accent-dim)", fontSize: 10 }}>{source.scope}</span>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.6 }}>{source.desc}</p>
        </div>
      </div>

      {/* Expected columns */}
      <div>
        <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.07em", fontWeight: 600, marginBottom: 6 }}>Expected Columns</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {source.columns.map(col => (
            <span key={col} style={{
              padding: "2px 7px", background: "var(--bg)", border: "1px solid var(--border)",
              borderRadius: 4, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-dim)",
            }}>{col}</span>
          ))}
        </div>
      </div>

      {/* Country selector for utility */}
      {source.countryCode && (
        <div>
          <label style={{ display: "block", marginBottom: 6, fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>Grid Emission Factor</label>
          <select value={countryCode} onChange={e => setCountryCode(e.target.value)}>
            {COUNTRY_OPTIONS.map(o => <option key={o.code} value={o.code}>{o.label}</option>)}
          </select>
        </div>
      )}

      {/* Drop zone */}
      <label
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragging ? "var(--accent)" : "var(--border)"}`,
          borderRadius: "var(--radius)",
          padding: "28px 20px",
          textAlign: "center",
          cursor: "pointer",
          background: dragging ? "var(--accent-glow)" : "var(--bg)",
          transition: "all 0.15s",
          display: "block",
        }}
      >
        <input type="file" accept=".csv,.tsv,.txt" onChange={handleFile} style={{ display: "none" }} />
        <div style={{ fontSize: 22, marginBottom: 8 }}>↑</div>
        <div style={{ fontSize: 13, color: "var(--text-dim)", marginBottom: 4 }}>Drop CSV here or click to browse</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)" }}>CSV · TSV · TXT — UTF-8, Latin-1, or Windows-1252</div>
      </label>
    </div>
  );
}

interface UploadResult {
  sourceType: string;
  fileName: string;
  recordsCreated: number;
  parseErrors: number;
  errorDetail: any[];
  status: "success" | "error";
  message?: string;
}

export default function Ingest() {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState<string | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);

  const handleUpload = async (type: string, file: File, countryCode?: string) => {
    setUploading(type);
    try {
      const { data } = await uploadFile(type, file, countryCode);
      setResults(prev => [{
        sourceType: type,
        fileName: file.name,
        recordsCreated: data.records_created,
        parseErrors: data.parse_errors,
        errorDetail: data.parse_error_detail || [],
        status: "success",
      }, ...prev]);
    } catch (e: any) {
      setResults(prev => [{
        sourceType: type,
        fileName: file.name,
        recordsCreated: 0,
        parseErrors: 0,
        errorDetail: [],
        status: "error",
        message: e.response?.data?.error || e.message || "Upload failed",
      }, ...prev]);
    } finally {
      setUploading(null);
    }
  };

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Ingest Data</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Upload CSV exports from SAP, utility portals, and corporate travel platforms. Records are auto-parsed, unit-normalised, and queued for analyst review.</p>
      </div>

      {/* Global loading banner */}
      {uploading && (
        <div style={{
          marginBottom: 20, padding: "14px 20px",
          background: "var(--accent-glow)", border: "1px solid var(--accent-dim)", borderRadius: "var(--radius)",
          display: "flex", alignItems: "center", gap: 12, fontSize: 13,
        }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", animation: "pulse 1s infinite" }} />
          Parsing {uploading} file… detecting headers, normalising units, computing CO₂e…
        </div>
      )}

      {/* Result toasts */}
      {results.slice(0, 3).map((r, i) => (
        <div key={i} style={{
          marginBottom: 12, padding: "14px 16px",
          background: r.status === "success" ? "rgba(74,222,128,0.06)" : "rgba(248,113,113,0.06)",
          border: `1px solid ${r.status === "success" ? "var(--accent-dim)" : "var(--red-dim)"}`,
          borderRadius: "var(--radius)",
          display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4, color: r.status === "success" ? "var(--accent)" : "var(--red)" }}>
              {r.status === "success" ? `✓ ${r.fileName}` : `✕ ${r.fileName}`}
            </div>
            {r.status === "success" ? (
              <div style={{ fontSize: 12, color: "var(--text-dim)" }}>
                {r.recordsCreated} records created
                {r.parseErrors > 0 && <span style={{ color: "var(--amber)", marginLeft: 8 }}>· {r.parseErrors} rows failed</span>}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{r.message}</div>
            )}
            {r.errorDetail.length > 0 && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ fontSize: 11, color: "var(--text-muted)", cursor: "pointer" }}>Show parse errors</summary>
                <div style={{ marginTop: 6, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-muted)" }}>
                  {r.errorDetail.slice(0, 5).map((e, j) => (
                    <div key={j}>Row {e.row}: {e.error}</div>
                  ))}
                </div>
              </details>
            )}
          </div>
          {r.status === "success" && (
            <button className="btn btn-ghost btn-sm" onClick={() => navigate("/records?status=pending")}>
              Review →
            </button>
          )}
        </div>
      ))}

      {/* Source cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
        {SOURCES.map(source => (
          <div key={source.type} style={{ opacity: uploading && uploading !== source.type ? 0.5 : 1, transition: "opacity 0.2s", pointerEvents: uploading && uploading !== source.type ? "none" : "auto" }}>
            <SourceCard source={source} onUpload={handleUpload} />
          </div>
        ))}
      </div>

      {/* Guidance */}
      <div className="card" style={{ marginTop: 24, borderColor: "var(--border)" }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>What happens after upload?</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
          {[
            ["1. Parse", "Headers are auto-detected (English + German). Dates, quantities, and units are extracted."],
            ["2. Normalise", "Units converted to canonical forms (litres, kWh, km). DEFRA/CEA emission factors applied."],
            ["3. Flag", "Records with missing data, estimated values, or suspicious quantities are auto-flagged for review."],
            ["4. Review", "Analysts approve, reject, or note records. Approved records can be locked for audit."],
          ].map(([step, desc]) => (
            <div key={step}>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent)", fontWeight: 500, marginBottom: 4 }}>{step}</div>
              <div style={{ fontSize: 12, color: "var(--text-dim)", lineHeight: 1.6 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

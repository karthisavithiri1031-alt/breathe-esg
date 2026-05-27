import React, { useEffect, useState, useCallback } from "react";
import { getRecords, approveRecord, rejectRecord, lockRecord, bulkApprove } from "../api";

interface EmissionRecord {
  id: string;
  scope: number;
  category: string;
  activity_date: string;
  raw_quantity: string;
  raw_unit: string;
  normalised_quantity: string;
  normalised_unit: string;
  co2e_kg: string;
  emission_factor_source: string;
  facility_code: string;
  facility_name: string;
  status: string;
  validation_flags: string[];
  is_estimated: boolean;
  source_file_name: string;
  source_row_ref: string;
  review_note: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  source_metadata: Record<string, string>;
}

const CATEGORY_LABELS: Record<string, string> = {
  fuel_combustion: "Fuel Combustion",
  purchased_electricity: "Electricity",
  business_travel_flight: "Flight",
  business_travel_hotel: "Hotel",
  business_travel_ground: "Ground",
  procurement: "Procurement",
};

const SCOPE_COLORS: Record<number, string> = {
  1: "var(--scope1)", 2: "var(--scope2)", 3: "var(--scope3)",
};

function fmt(n: string | number) {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return "—";
  if (v >= 1000) return (v / 1000).toFixed(3) + " t";
  return v.toFixed(2) + " kg";
}

export default function Records() {
  const [records, setRecords] = useState<EmissionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<EmissionRecord | null>(null);
  const [note, setNote] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [filters, setFilters] = useState({ scope: "", status: "", category: "" });
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page) };
      if (filters.scope) params.scope = filters.scope;
      if (filters.status) params.status = filters.status;
      if (filters.category) params.category = filters.category;
      const { data } = await getRecords(params);
      const results = data.results || data;
      setRecords(results);
      setTotal(data.count || results.length);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => { load(); }, [load]);

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === records.length) setSelected(new Set());
    else setSelected(new Set(records.map(r => r.id)));
  };

  const doAction = async (action: "approve" | "reject" | "lock") => {
    if (!detail) return;
    setActionLoading(true);
    try {
      if (action === "approve") await approveRecord(detail.id, note);
      else if (action === "reject") await rejectRecord(detail.id, note);
      else await lockRecord(detail.id);
      setDetail(null);
      setNote("");
      load();
    } finally {
      setActionLoading(false);
    }
  };

  const doBulkApprove = async () => {
    if (selected.size === 0) return;
    setActionLoading(true);
    try {
      await bulkApprove(Array.from(selected));
      setSelected(new Set());
      load();
    } finally {
      setActionLoading(false);
    }
  };

  const setFilter = (k: string, v: string) => {
    setFilters(f => ({ ...f, [k]: v }));
    setPage(1);
  };

  return (
    <div className="fade-in">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Emission Records</h1>
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{total} records · review and approve before audit lock</p>
        </div>
        {selected.size > 0 && (
          <button className="btn btn-primary" onClick={doBulkApprove} disabled={actionLoading}>
            ✓ Approve {selected.size} selected
          </button>
        )}
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <select value={filters.scope} onChange={e => setFilter("scope", e.target.value)} style={{ width: "auto", minWidth: 130 }}>
          <option value="">All Scopes</option>
          <option value="1">Scope 1</option>
          <option value="2">Scope 2</option>
          <option value="3">Scope 3</option>
        </select>
        <select value={filters.status} onChange={e => setFilter("status", e.target.value)} style={{ width: "auto", minWidth: 150 }}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="flagged">Flagged</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="locked">Locked</option>
        </select>
        <select value={filters.category} onChange={e => setFilter("category", e.target.value)} style={{ width: "auto", minWidth: 170 }}>
          <option value="">All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        {(filters.scope || filters.status || filters.category) && (
          <button className="btn btn-ghost btn-sm" onClick={() => { setFilters({ scope: "", status: "", category: "" }); setPage(1); }}>
            ✕ Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>Loading…</div>
        ) : records.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>
            No records match the current filters.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 36 }}>
                    <input type="checkbox" checked={selected.size === records.length && records.length > 0}
                      onChange={toggleAll} style={{ width: "auto", cursor: "pointer" }} />
                  </th>
                  <th>Scope / Category</th>
                  <th>Date</th>
                  <th>Quantity</th>
                  <th>CO₂e</th>
                  <th>Facility</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Flags</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr key={r.id} className={selected.has(r.id) ? "selected" : ""}>
                    <td>
                      <input type="checkbox" checked={selected.has(r.id)}
                        onChange={() => toggleSelect(r.id)} style={{ width: "auto", cursor: "pointer" }} />
                    </td>
                    <td>
                      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                        <span className={`scope-badge scope-${r.scope}`}>S{r.scope}</span>
                        <span style={{ fontSize: 12, color: "var(--text-dim)" }}>{CATEGORY_LABELS[r.category] || r.category}</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-dim)", whiteSpace: "nowrap" }}>{r.activity_date}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, whiteSpace: "nowrap" }}>
                      {parseFloat(r.raw_quantity).toLocaleString()} <span style={{ color: "var(--text-muted)" }}>{r.raw_unit}</span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 500, color: "var(--accent)", whiteSpace: "nowrap" }}>
                      {fmt(r.co2e_kg)}
                    </td>
                    <td style={{ fontSize: 12, color: "var(--text-dim)", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.facility_name || r.facility_code || "—"}
                    </td>
                    <td style={{ fontSize: 11, color: "var(--text-muted)", maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.source_file_name}
                    </td>
                    <td><span className={`badge badge-${r.status}`}>{r.status}</span></td>
                    <td>
                      {r.validation_flags.length > 0 && (
                        <span title={r.validation_flags.join("; ")} style={{
                          display: "inline-flex", alignItems: "center", gap: 3,
                          fontSize: 11, color: "var(--amber)", cursor: "help",
                        }}>
                          ⚠ {r.validation_flags.length}
                        </span>
                      )}
                      {r.is_estimated && <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 4 }}>est.</span>}
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => setDetail(r)}>
                        Review →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > 50 && (
          <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Page {page} · {total} records total</span>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>← Prev</button>
              <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => p + 1)} disabled={records.length < 50}>Next →</button>
            </div>
          </div>
        )}
      </div>

      {/* Detail modal */}
      {detail && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
        }} onClick={e => { if (e.target === e.currentTarget) setDetail(null); }}>
          <div className="card fade-in" style={{ width: "100%", maxWidth: 600, maxHeight: "90vh", overflowY: "auto", border: "1px solid var(--border-light)" }}>
            {/* Modal header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
              <div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                  <span className={`scope-badge scope-${detail.scope}`}>Scope {detail.scope}</span>
                  <span className={`badge badge-${detail.status}`}>{detail.status}</span>
                  {detail.is_estimated && <span className="badge" style={{ background: "rgba(251,191,36,0.06)", color: "var(--amber)", borderColor: "var(--amber-dim)" }}>estimated</span>}
                </div>
                <h2 style={{ fontSize: 16, fontWeight: 600 }}>{CATEGORY_LABELS[detail.category] || detail.category}</h2>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{detail.source_file_name} · {detail.source_row_ref}</div>
              </div>
              <button className="btn btn-ghost btn-icon" onClick={() => setDetail(null)} style={{ flexShrink: 0 }}>✕</button>
            </div>

            {/* Data grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
              {[
                ["Activity Date", detail.activity_date],
                ["CO₂e", fmt(detail.co2e_kg)],
                ["Raw Quantity", `${parseFloat(detail.raw_quantity).toLocaleString()} ${detail.raw_unit}`],
                ["Normalised", `${parseFloat(detail.normalised_quantity).toFixed(2)} ${detail.normalised_unit}`],
                ["Emission Factor", detail.emission_factor_source || "—"],
                ["Facility", detail.facility_name || detail.facility_code || "—"],
              ].map(([label, value]) => (
                <div key={label} style={{ padding: "10px 12px", background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4, fontWeight: 600 }}>{label}</div>
                  <div style={{ fontSize: 13, fontFamily: label === "Activity Date" || label === "CO₂e" || label === "Raw Quantity" || label === "Normalised" ? "var(--font-mono)" : undefined }}>{value}</div>
                </div>
              ))}
            </div>

            {/* Source metadata */}
            {Object.keys(detail.source_metadata).length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600, marginBottom: 8 }}>Source Metadata</div>
                <div style={{ background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 12px" }}>
                  {Object.entries(detail.source_metadata).filter(([, v]) => v).map(([k, v]) => (
                    <div key={k} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 12 }}>
                      <span style={{ color: "var(--text-muted)", minWidth: 120, fontFamily: "var(--font-mono)" }}>{k}</span>
                      <span style={{ color: "var(--text-dim)" }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Validation flags */}
            {detail.validation_flags.length > 0 && (
              <div style={{ marginBottom: 20, padding: "12px", background: "rgba(251,191,36,0.05)", border: "1px solid var(--amber-dim)", borderRadius: "var(--radius)" }}>
                <div style={{ fontSize: 11, color: "var(--amber)", fontWeight: 600, marginBottom: 6 }}>⚠ Validation Flags</div>
                {detail.validation_flags.map((f, i) => (
                  <div key={i} style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 2 }}>· {f}</div>
                ))}
              </div>
            )}

            {/* Previous review */}
            {detail.reviewed_by_name && (
              <div style={{ marginBottom: 16, padding: "10px 12px", background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)", fontSize: 12 }}>
                <span style={{ color: "var(--text-muted)" }}>Reviewed by </span>
                <span style={{ color: "var(--text)" }}>{detail.reviewed_by_name}</span>
                {detail.review_note && <span style={{ color: "var(--text-dim)" }}>: "{detail.review_note}"</span>}
              </div>
            )}

            {/* Action buttons */}
            {detail.status !== "locked" && (
              <div>
                <div style={{ marginBottom: 10 }}>
                  <input value={note} onChange={e => setNote(e.target.value)}
                    placeholder="Add a review note (optional)…" style={{ marginBottom: 10 }} />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {detail.status !== "approved" && (
                    <button className="btn btn-primary" onClick={() => doAction("approve")} disabled={actionLoading}>
                      ✓ Approve
                    </button>
                  )}
                  {detail.status !== "rejected" && (
                    <button className="btn btn-danger" onClick={() => doAction("reject")} disabled={actionLoading}>
                      ✕ Reject
                    </button>
                  )}
                  {detail.status === "approved" && (
                    <button className="btn btn-ghost" onClick={() => doAction("lock")} disabled={actionLoading}
                      style={{ borderColor: "var(--blue-dim)", color: "var(--blue)" }}>
                      🔒 Lock for Audit
                    </button>
                  )}
                </div>
              </div>
            )}
            {detail.status === "locked" && (
              <div style={{ padding: "10px 12px", background: "rgba(96,165,250,0.06)", border: "1px solid var(--blue-dim)", borderRadius: "var(--radius)", fontSize: 13, color: "var(--blue)" }}>
                🔒 This record is locked for audit and cannot be modified.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

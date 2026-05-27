import React, { useEffect, useState } from "react";
import { getDashboard, getSourceFiles } from "../api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from "recharts";

interface DashData {
  total_co2e_kg: number;
  scope_breakdown: Record<string, number>;
  category_breakdown: Record<string, { label: string; co2e_kg: number }>;
  status_breakdown: Record<string, { label: string; count: number }>;
  records_total: number;
  records_flagged: number;
  records_approved: number;
  records_pending: number;
  source_files_count: number;
}

function fmt(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(2) + " t";
  if (n >= 1000) return (n / 1000).toFixed(1) + " t";
  return n.toFixed(0) + " kg";
}

export default function Dashboard() {
  const [data, setData] = useState<DashData | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getDashboard(), getSourceFiles()])
      .then(([d, f]) => { setData(d.data); setFiles(f.data.results || f.data); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", gap: 12 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", animation: "pulse 1s infinite" }} />
      <span style={{ color: "var(--text-muted)" }}>Loading dashboard…</span>
    </div>
  );

  if (!data) return <div style={{ color: "var(--text-muted)" }}>No data yet. Upload some files to get started.</div>;

  const totalTonne = data.total_co2e_kg / 1000;

  const scopeData = [
    { name: "Scope 1", value: data.scope_breakdown.scope_1 / 1000, color: "var(--scope1)" },
    { name: "Scope 2", value: data.scope_breakdown.scope_2 / 1000, color: "var(--scope2)" },
    { name: "Scope 3", value: data.scope_breakdown.scope_3 / 1000, color: "var(--scope3)" },
  ];

  const catData = Object.entries(data.category_breakdown)
    .map(([k, v]) => ({ name: v.label.replace("Business Travel – ", ""), value: v.co2e_kg / 1000 }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const statusData = Object.entries(data.status_breakdown)
    .map(([k, v]) => ({ name: v.label, value: v.count, status: k }));

  return (
    <div className="fade-in">
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Emissions Dashboard</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{localStorage.getItem("organisation")} · Carbon inventory overview</p>
      </div>

      {/* Top stat row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Total CO₂e", value: totalTonne.toFixed(2) + " t", sub: "All scopes combined", accent: true },
          { label: "Records", value: data.records_total.toString(), sub: `${data.records_pending} pending review` },
          { label: "Flagged", value: data.records_flagged.toString(), sub: "Auto-flagged for review", warn: data.records_flagged > 0 },
          { label: "Approved", value: data.records_approved.toString(), sub: "Ready for audit lock" },
          { label: "Data Sources", value: data.source_files_count.toString(), sub: "Files ingested" },
        ].map(({ label, value, sub, accent, warn }) => (
          <div key={label} className="card" style={{ borderColor: accent ? "var(--accent-dim)" : warn && value !== "0" ? "var(--red-dim)" : undefined }}>
            <div className="stat-label" style={{ marginBottom: 8 }}>{label}</div>
            <div className="stat-value" style={{ color: accent ? "var(--accent)" : warn && value !== "0" ? "var(--red)" : "var(--text)", marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {/* Scope breakdown */}
        <div className="card">
          <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>Scope Breakdown</h3>
            <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>tCO₂e</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={scopeData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [v.toFixed(3) + " tCO₂e", ""]}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {scopeData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category breakdown */}
        <div className="card">
          <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h3 style={{ fontSize: 14, fontWeight: 600 }}>By Category</h3>
            <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>tCO₂e</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={catData} layout="vertical" margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: "var(--text-muted)", fontSize: 10 }} axisLine={false} tickLine={false} width={120} />
              <Tooltip
                contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [v.toFixed(3) + " tCO₂e", ""]}
              />
              <Bar dataKey="value" fill="var(--accent)" radius={[0, 4, 4, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Review status & recent files */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 16 }}>
        {/* Status */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Review Status</h3>
          {statusData.filter(d => d.value > 0).map(({ name, value, status }) => {
            const colors: Record<string, string> = {
              pending: "var(--amber)", flagged: "var(--red)", approved: "var(--accent)",
              rejected: "var(--text-muted)", locked: "var(--blue)",
            };
            const max = Math.max(...statusData.map(d => d.value), 1);
            return (
              <div key={status} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13 }}>
                  <span style={{ color: "var(--text-dim)" }}>{name}</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: colors[status] }}>{value}</span>
                </div>
                <div style={{ height: 4, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(value / max) * 100}%`, background: colors[status], borderRadius: 2, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>

        {/* Recent files */}
        <div className="card">
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Recent Ingestions</h3>
          {files.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", padding: "20px 0" }}>
              No data files yet. <a href="/ingest" style={{ color: "var(--accent)" }}>Upload files →</a>
            </div>
          ) : files.slice(0, 6).map((f: any) => (
            <div key={f.id} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                background: { sap: "rgba(251,146,60,0.1)", utility: "rgba(96,165,250,0.1)", travel: "rgba(167,139,250,0.1)" }[f.source_type as string] || "var(--bg)",
                display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14,
              }}>
                {{ sap: "⚙️", utility: "⚡", travel: "✈️" }[f.source_type as string] || "📄"}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.file_name}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{f.row_count_parsed} records · {new Date(f.uploaded_at).toLocaleDateString()}</div>
              </div>
              <span className={`badge badge-${f.status}`}>{f.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

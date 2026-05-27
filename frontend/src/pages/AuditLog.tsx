import React, { useEffect, useState } from "react";
import { getAuditLog } from "../api";

interface LogEntry {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  detail: Record<string, any>;
  timestamp: string;
  actor_name: string;
}

const ACTION_STYLES: Record<string, { color: string; icon: string; label: string }> = {
  upload: { color: "var(--blue)", icon: "↑", label: "Upload" },
  parse: { color: "var(--accent)", icon: "◈", label: "Parse" },
  approve: { color: "var(--accent)", icon: "✓", label: "Approve" },
  reject: { color: "var(--red)", icon: "✕", label: "Reject" },
  edit: { color: "var(--amber)", icon: "✎", label: "Edit" },
  lock: { color: "var(--blue)", icon: "🔒", label: "Lock" },
  flag: { color: "var(--amber)", icon: "⚠", label: "Flag" },
};

export default function AuditLog() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAuditLog().then(({ data }) => setLogs(data)).finally(() => setLoading(false));
  }, []);

  const grouped = logs.reduce((acc: Record<string, LogEntry[]>, log) => {
    const date = log.timestamp.split("T")[0];
    if (!acc[date]) acc[date] = [];
    acc[date].push(log);
    return acc;
  }, {});

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Audit Log</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Immutable, append-only record of all system and analyst actions. Never edited in place.</p>
      </div>

      {loading ? (
        <div style={{ color: "var(--text-muted)", padding: "40px", textAlign: "center" }}>Loading…</div>
      ) : logs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
          No actions recorded yet. Start by ingesting data.
        </div>
      ) : (
        <div>
          {Object.entries(grouped).map(([date, entries]) => (
            <div key={date} style={{ marginBottom: 24 }}>
              <div style={{
                fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase",
                letterSpacing: "0.07em", fontWeight: 600, fontFamily: "var(--font-mono)",
                marginBottom: 10, display: "flex", alignItems: "center", gap: 10,
              }}>
                <span>{new Date(date).toLocaleDateString("en-GB", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</span>
                <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
                <span>{entries.length} events</span>
              </div>

              <div className="card" style={{ padding: 0, overflow: "hidden" }}>
                {entries.map((log, i) => {
                  const style = ACTION_STYLES[log.action] || { color: "var(--text-dim)", icon: "·", label: log.action };
                  const time = new Date(log.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

                  return (
                    <div key={log.id} style={{
                      display: "flex", gap: 14, padding: "12px 16px",
                      borderBottom: i < entries.length - 1 ? "1px solid var(--border)" : "none",
                      alignItems: "flex-start",
                    }}>
                      {/* Icon */}
                      <div style={{
                        width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                        background: `${style.color}12`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 12, color: style.color, fontWeight: 600,
                      }}>{style.icon}</div>

                      {/* Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 2, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 13, fontWeight: 500, color: style.color }}>{style.label}</span>
                          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
                            {log.actor_name === "System" ? "by system" : `by ${log.actor_name}`}
                          </span>
                          {log.target_type && (
                            <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                              {log.target_type.replace("_", " ")}
                            </span>
                          )}
                        </div>

                        {/* Detail */}
                        {log.detail && Object.keys(log.detail).length > 0 && (
                          <div style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                            {log.action === "parse" && (
                              <span>{log.detail.parsed} parsed · {log.detail.failed} failed</span>
                            )}
                            {log.action === "approve" && log.detail.note && (
                              <span>"{log.detail.note}"</span>
                            )}
                            {log.action === "reject" && log.detail.note && (
                              <span>"{log.detail.note}"</span>
                            )}
                            {log.action === "flag" && log.detail.flags && (
                              <span>{(log.detail.flags as string[]).slice(0, 2).join(" · ")}</span>
                            )}
                            {log.action === "upload" && (
                              <span>{log.detail.file_name}</span>
                            )}
                          </div>
                        )}

                        {/* Target ID */}
                        {log.target_id && (
                          <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginTop: 2, opacity: 0.6 }}>
                            id:{log.target_id.slice(0, 8)}…
                          </div>
                        )}
                      </div>

                      {/* Time */}
                      <div style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)", flexShrink: 0, paddingTop: 2 }}>{time}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

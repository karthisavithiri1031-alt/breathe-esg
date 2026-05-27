import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, register } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ username: "", password: "", email: "", organisation: "Acme Corporation" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      if (mode === "login") {
        const { data } = await login(form.username, form.password);
        localStorage.setItem("token", data.token);
        localStorage.setItem("username", data.username);
        localStorage.setItem("organisation", data.organisation);
        navigate("/");
      } else {
        const { data } = await register(form.username, form.password, form.email, form.organisation);
        localStorage.setItem("token", data.token);
        localStorage.setItem("username", data.username);
        localStorage.setItem("organisation", data.organisation);
        navigate("/");
      }
    } catch (e: any) {
      setError(e.response?.data?.error || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: "linear-gradient(135deg, var(--accent), var(--accent-dim))",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 28, margin: "0 auto 16px",
          }}>🌿</div>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Breathe ESG</h1>
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Carbon data ingestion & review platform</p>
        </div>

        <div className="card fade-in">
          {/* Tab toggle */}
          <div style={{ display: "flex", marginBottom: 24, background: "var(--bg)", borderRadius: "var(--radius)", padding: 3 }}>
            {(["login", "register"] as const).map(m => (
              <button key={m} onClick={() => setMode(m)} style={{
                flex: 1, padding: "7px", border: "none", cursor: "pointer",
                borderRadius: "calc(var(--radius) - 2px)", fontSize: 13, fontWeight: 500,
                background: mode === m ? "var(--bg-card)" : "transparent",
                color: mode === m ? "var(--text)" : "var(--text-muted)",
                transition: "all 0.15s",
              }}>
                {m === "login" ? "Sign In" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>Username</label>
              <input value={form.username} onChange={e => set("username", e.target.value)} placeholder="analyst" required />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>Password</label>
              <input type="password" value={form.password} onChange={e => set("password", e.target.value)} placeholder="••••••••" required />
            </div>
            {mode === "register" && <>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>Email</label>
                <input type="email" value={form.email} onChange={e => set("email", e.target.value)} placeholder="you@company.com" />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>Organisation Name</label>
                <input value={form.organisation} onChange={e => set("organisation", e.target.value)} placeholder="Acme Corp" required />
              </div>
            </>}

            {error && <div style={{ padding: "10px 12px", background: "rgba(248,113,113,0.08)", border: "1px solid var(--red-dim)", borderRadius: "var(--radius)", color: "var(--red)", fontSize: 13 }}>{error}</div>}

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: 4, justifyContent: "center", padding: "10px" }}>
              {loading ? "…" : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>

          {mode === "login" && (
            <div style={{ marginTop: 16, padding: "12px", background: "var(--bg)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              Demo: <span style={{ color: "var(--accent)" }}>analyst</span> / <span style={{ color: "var(--accent)" }}>demo1234</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from "react-router-dom";
import "./index.css";
import Dashboard from "./pages/Dashboard";
import Records from "./pages/Records";
import Ingest from "./pages/Ingest";
import AuditLog from "./pages/AuditLog";
import Login from "./pages/Login";

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const username = localStorage.getItem("username") || "";
  const org = localStorage.getItem("organisation") || "";

  const logout = () => {
    localStorage.clear();
    navigate("/login");
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar */}
      <nav style={{
        width: 220, background: "var(--bg-card)", borderRight: "1px solid var(--border)",
        display: "flex", flexDirection: "column", padding: "24px 0", position: "fixed",
        top: 0, left: 0, bottom: 0, zIndex: 100,
      }}>
        {/* Logo */}
        <div style={{ padding: "0 20px 28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg, var(--accent), var(--accent-dim))",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16,
            }}>🌿</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, color: "var(--text)" }}>Breathe</div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em" }}>ESG Platform</div>
            </div>
          </div>
        </div>

        {/* Org */}
        <div style={{ padding: "0 20px 20px", borderBottom: "1px solid var(--border)", marginBottom: 8 }}>
          <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 4 }}>Organisation</div>
          <div style={{ fontSize: 13, color: "var(--accent2)", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{org}</div>
        </div>

        {/* Nav links */}
        {[
          { to: "/", icon: "◈", label: "Dashboard" },
          { to: "/records", icon: "≡", label: "Records" },
          { to: "/ingest", icon: "↑", label: "Ingest Data" },
          { to: "/audit", icon: "◎", label: "Audit Log" },
        ].map(({ to, icon, label }) => (
          <NavLink key={to} to={to} end={to === "/"} style={({ isActive }) => ({
            display: "flex", alignItems: "center", gap: 10, padding: "9px 20px",
            textDecoration: "none", fontSize: 13, fontWeight: 500,
            color: isActive ? "var(--accent)" : "var(--text-dim)",
            background: isActive ? "var(--accent-glow)" : "transparent",
            borderRight: isActive ? "2px solid var(--accent)" : "2px solid transparent",
            transition: "all 0.15s",
          })}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 14, width: 16, textAlign: "center" }}>{icon}</span>
            {label}
          </NavLink>
        ))}

        {/* Bottom user info */}
        <div style={{ marginTop: "auto", padding: "16px 20px", borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 8 }}>
            <span style={{ color: "var(--text-muted)" }}>Signed in as </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>{username}</span>
          </div>
          <button className="btn btn-ghost" style={{ width: "100%", justifyContent: "center", fontSize: 12 }} onClick={logout}>
            Sign out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main style={{ marginLeft: 220, flex: 1, minHeight: "100vh", padding: "32px 32px 60px" }}>
        {children}
      </main>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Layout><Dashboard /></Layout></RequireAuth>} />
        <Route path="/records" element={<RequireAuth><Layout><Records /></Layout></RequireAuth>} />
        <Route path="/ingest" element={<RequireAuth><Layout><Ingest /></Layout></RequireAuth>} />
        <Route path="/audit" element={<RequireAuth><Layout><AuditLog /></Layout></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}

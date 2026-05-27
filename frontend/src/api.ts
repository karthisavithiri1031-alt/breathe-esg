import axios from "axios";

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000/api";

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

export const login = (username: string, password: string) =>
  api.post("/auth/login/", { username, password });

export const register = (username: string, password: string, email: string, organisation: string) =>
  api.post("/auth/register/", { username, password, email, organisation });

export const getDashboard = () => api.get("/dashboard/");

export const getRecords = (params?: Record<string, string>) =>
  api.get("/records/", { params });

export const getSourceFiles = () => api.get("/source-files/");

export const approveRecord = (id: string, note?: string) =>
  api.post(`/records/${id}/approve/`, { note });

export const rejectRecord = (id: string, note?: string) =>
  api.post(`/records/${id}/reject/`, { note });

export const lockRecord = (id: string) =>
  api.post(`/records/${id}/lock/`);

export const bulkApprove = (ids: string[]) =>
  api.post("/records/bulk_approve/", { ids });

export const uploadFile = (sourceType: string, file: File, countryCode?: string) => {
  const form = new FormData();
  form.append("source_type", sourceType);
  form.append("file", file);
  if (countryCode) form.append("country_code", countryCode);
  return api.post("/ingest/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getAuditLog = () => api.get("/audit-log/");

export default api;

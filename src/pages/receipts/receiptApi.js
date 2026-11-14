const BASE = "http://127.0.0.1:8000/api/receipts/";
const token = () => JSON.parse(localStorage.getItem("accessToken") || "null");
export async function receiptRequest(path = "", options = {}) {
  const headers = { Authorization: `Bearer ${token()}`, ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(BASE + path, { ...options, headers });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.image?.[0] || JSON.stringify(data));
  return data;
}

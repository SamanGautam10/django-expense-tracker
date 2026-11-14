import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { receiptRequest } from "./receiptApi";
import "./receipts.css";

const categories = ["Bar tabs", "Monthly bill", "Online shopping", "Electronics", "Groceries", "Taxi fare", "Miscellaneous"];
export default function ReviewReceipt() {
  const { id } = useParams(); const navigate = useNavigate();
  const [receipt, setReceipt] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [form, setForm] = useState({merchant:"",purchase_date:"",total:"",category:"Miscellaneous",source:"Receipt Scan"});
  const [error,setError] = useState(""); const [busy,setBusy] = useState(false);
  useEffect(() => { receiptRequest(`${id}/`).then(r => {setReceipt(r);setForm({ merchant:r.merchant||"",purchase_date:r.purchase_date||"",total:r.total||"",category:r.predicted_category||"Miscellaneous",source:"Receipt Scan" });}).catch(e=>setError(e.message)); },[id]);
  useEffect(() => {
    let active = true; let objectUrl = null;
    const jwt = JSON.parse(localStorage.getItem("accessToken") || "null");
    fetch(`http://127.0.0.1:8000/api/receipts/${id}/image/`, {headers:{Authorization:`Bearer ${jwt}`}})
      .then(res => {if (!res.ok) throw new Error("Image not available"); return res.blob();})
      .then(blob => {if(active){objectUrl = URL.createObjectURL(blob);setPreviewUrl(objectUrl);}})
      .catch(() => {});
    return () => {active = false;if(objectUrl) URL.revokeObjectURL(objectUrl);};
  }, [id]);
  const update = e => setForm(prev => ({...prev,[e.target.name]:e.target.value}));
  const confirm = async e => {e.preventDefault();setBusy(true);setError("");try { await receiptRequest(`${id}/confirm/`, {method:"POST",body:JSON.stringify(form)});navigate("/receipts/");}catch(err){setError(err.message);}finally{setBusy(false);}};
  if (!receipt) return <main className="receipt-page">{error||"Loading receipt…"}</main>;
  return <main className="receipt-page"><div className="receipt-heading"><div><h2>Review extracted information</h2><p>Check the AI results before saving an expense.</p></div><button className="btn btn-outline-secondary" onClick={()=>navigate("/receipts/")}>History</button></div>
    {receipt.status === "failed" ? <div className="alert alert-warning">{receipt.error_message || "Receipt scanning failed."} <button className="btn btn-sm btn-outline-secondary" onClick={()=>navigate("/receipts/upload/")}>Try again</button></div> : <div className="receipt-grid">
    <section className="receipt-panel"><h5>Original receipt</h5><p className="text-muted small">Your uploaded receipt · private image</p>{previewUrl ? <img src={previewUrl} alt="Uploaded receipt" className="receipt-preview"/> : <p>Receipt #{id} — image preview unavailable.</p>}</section>
    <form className="receipt-panel" onSubmit={confirm}><h5>Detected fields</h5>
      <label>Merchant<input className="form-control" name="merchant" required maxLength="100" value={form.merchant} onChange={update}/></label>
      <label>Purchase date<input className="form-control" type="date" name="purchase_date" required value={form.purchase_date} onChange={update}/></label>
      <label>Total amount<input className="form-control" type="number" min="0.01" step="0.01" name="total" required value={form.total} onChange={update}/></label>
      <label>Category<select className="form-control" name="category" value={form.category} onChange={update}>{categories.map(c=><option key={c}>{c}</option>)}</select></label>
      <p className="small text-muted">AI suggestion: {receipt.predicted_category || "Model not trained"}{receipt.confidence !== null ? ` (${Math.round(receipt.confidence*100)}% model probability)` : ""}. Always verify.</p>
      <label>Payment source<input className="form-control" name="source" required maxLength="30" value={form.source} onChange={update}/></label>
      <button disabled={busy || receipt.status === "confirmed"} className="btn btn-primary mt-2" type="submit">{busy ? "Saving…" : receipt.status === "confirmed" ? "Already saved" : "Confirm and save expense"}</button>
    </form></div>}
    {error && <div className="alert alert-danger mt-3">{error}</div>}
  </main>;
}

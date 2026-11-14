import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { receiptRequest } from "./receiptApi";
import "./receipts.css";

export default function UploadReceipt() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const choose = (candidate) => {
    setError("");
    if (!candidate) return;
    if (!["image/jpeg", "image/png"].includes(candidate.type) || candidate.size > 5 * 1024 * 1024) {
      setError("Select a JPG or PNG receipt under 5 MB."); return;
    }
    setFile(candidate);
  };
  const submit = async () => {
    if (!file || busy) return;
    setBusy(true); setError("");
    try {
      const form = new FormData(); form.append("image", file);
      const result = await receiptRequest("", { method: "POST", body: form });
      navigate(`/receipts/${result.id}/review/`);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return <main className="receipt-page">
    <div className="receipt-heading"><div><h2>Scan a receipt</h2><p>Turn a paper receipt into an expense in just a few steps.</p></div><button className="btn btn-outline-secondary" onClick={() => navigate("/receipts/")}>Receipt history</button></div>
    <div className={`receipt-drop ${dragging ? "dragging" : ""}`} onDragOver={e => {e.preventDefault(); setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]);}}>
      <div className="receipt-upload-symbol">▧</div><h4>Drop your receipt image here</h4><p>JPG or PNG · Maximum 5 MB</p><label className="btn btn-outline-primary">Choose image<input type="file" accept="image/jpeg,image/png" hidden onChange={e => choose(e.target.files[0])}/></label>
    </div>
    {file && <div className="receipt-selected"><strong>Selected:</strong> {file.name}<br/><button className="btn btn-primary mt-3" disabled={busy} onClick={submit}>{busy ? "Scanning receipt…" : "Scan receipt"}</button></div>}
    {error && <div className="alert alert-danger mt-3" role="alert">{error}</div>}
  </main>;
}

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { receiptRequest } from "./receiptApi";
import "./receipts.css";
export default function ReceiptHistory() {
  const navigate=useNavigate();const [items,setItems]=useState([]);const [error,setError]=useState("");
  const refresh=()=>receiptRequest().then(setItems).catch(e=>setError(e.message));
  useEffect(()=>{refresh();},[]);
  const remove=async id=>{if(!window.confirm("Delete this unconfirmed receipt?"))return;try{await receiptRequest(`${id}/`,{method:"DELETE"});refresh();}catch(e){setError(e.message);}};
  return <main className="receipt-page"><div className="receipt-heading"><div><h2>Receipt history</h2><p>Review scans and track saved expenses.</p></div><button className="btn btn-primary" onClick={()=>navigate("/receipts/upload/")}>+ Scan receipt</button></div>
    {error && <div className="alert alert-danger">{error}</div>}
    {!items.length ? <div className="receipt-panel">No receipts uploaded yet.</div> : <div className="table-responsive receipt-panel"><table className="table"><thead><tr><th>Source</th><th>Content</th><th>Date</th><th>Amount</th><th>Status</th><th>Expense</th><th>Action</th></tr></thead><tbody>{items.map(r=><tr key={r.id}><td>{r.merchant||"Unknown"}</td><td>{r.content||"—"}</td><td>{r.purchase_date||"—"}</td><td>{r.total||"—"}</td><td>{r.status}</td><td>{r.expense||"—"}</td><td>{r.status==="review"?<button className="btn btn-sm btn-outline-primary" onClick={()=>navigate(`/receipts/${r.id}/review/`)}>Review</button>:r.status!=="confirmed"?<button className="btn btn-sm btn-outline-danger" onClick={()=>remove(r.id)}>Delete</button>:"Saved"}</td></tr>)}</tbody></table></div>}
  </main>;
}

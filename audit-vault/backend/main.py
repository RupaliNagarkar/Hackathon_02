"""
Audit Chain Evidence Vault — Backend API v3
- Fixed Gemini 2.5 Flash key + base URL (server-side only, not exposed to frontend)
- Document upload stored under vault/docs/<app_id>/<checklist_id>/
- BankUser upload permissions
- Auditor reads all apps
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid, json, logging, os, shutil
from datetime import datetime
from pathlib import Path

from agents.master_agent    import MasterAgent
from agents.search_agent    import SearchAgent
from agents.evidence_agent  import EvidenceAgent
from agents.exception_agent import ExceptionAgent
from vector_db.vault        import EvidenceVault
from auth                   import authenticate_user, create_token, verify_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Audit Chain Evidence Vault v3", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
security = HTTPBearer()

DOCS_ROOT = Path(__file__).parent.parent / "vault" / "docs"
DOCS_ROOT.mkdir(parents=True, exist_ok=True)

# ── Gemini config (server-side only — never sent to frontend) ────────────────
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"   # ← replace with real key
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_MODEL   = "gemini-2.5-flash"

vault           = EvidenceVault()
master_agent    = MasterAgent(vault)
search_agent    = SearchAgent(vault)
evidence_agent  = EvidenceAgent(vault)
exception_agent = ExceptionAgent(vault)


# ── Models ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class AuditSearchRequest(BaseModel):
    app_id: str
    query: Optional[str] = None
    checklist_id: Optional[str] = None

class ExceptionRequest(BaseModel):
    app_id: str; checklist_id: str; exception_type: str
    description: str; raised_by: str

class AIQueryRequest(BaseModel):
    query: str
    app_id: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": user["username"], "role": user["role"],
                          "name": user["name"], "app_ids": user["app_ids"]})
    return {"token": token, "user": user}


# ── Audit ─────────────────────────────────────────────────────────────────────
@app.post("/api/audit/search")
async def audit_search(req: AuditSearchRequest,
                       creds: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(creds.credentials)
    if not payload: raise HTTPException(status_code=401)
    return await master_agent.process(
        app_id=req.app_id, query=req.query, checklist_id=req.checklist_id,
        auditor=payload["sub"], search_agent=search_agent, evidence_agent=evidence_agent)

@app.get("/api/audit/exceptions/{app_id}")
async def get_exceptions(app_id: str, creds: HTTPAuthorizationCredentials = Depends(security)):
    verify_token(creds.credentials)
    return {"app_id": app_id, "exceptions": vault.get_exceptions(app_id)}

@app.post("/api/audit/exception")
async def raise_exception(req: ExceptionRequest,
                          creds: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(creds.credentials)
    if not payload: raise HTTPException(status_code=401)
    return await exception_agent.handle(
        app_id=req.app_id, checklist_id=req.checklist_id,
        exception_type=req.exception_type, description=req.description,
        raised_by=req.raised_by, auditor=payload["sub"])


# ── Document Upload (bankuser + admin) ───────────────────────────────────────
@app.post("/api/docs/upload")
async def upload_document(
    app_id: str = Form(...),
    checklist_id: str = Form(...),
    file: UploadFile = File(...),
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    payload = verify_token(creds.credentials)
    if not payload: raise HTTPException(status_code=401)
    if payload["role"] not in ("bankuser", "admin"):
        raise HTTPException(status_code=403, detail="Only BankUsers or Admins can upload")
    if app_id not in payload["app_ids"] and payload["role"] != "admin":
        raise HTTPException(status_code=403, detail=f"Not authorised for {app_id}")

    dest_dir = DOCS_ROOT / app_id / checklist_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext       = Path(file.filename).suffix
    doc_id    = f"{uuid.uuid4().hex[:10]}{ext}"
    dest_path = dest_dir / doc_id

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    meta = {"doc_id": doc_id, "original_name": file.filename, "app_id": app_id,
            "checklist_id": checklist_id, "uploaded_by": payload["sub"],
            "role": payload["role"], "uploaded_at": datetime.utcnow().isoformat(),
            "size_bytes": os.path.getsize(dest_path)}
    (dest_dir / f"{doc_id}.meta.json").write_text(json.dumps(meta, indent=2))
    return {"status": "uploaded", "document": meta}


@app.get("/api/docs/list/{app_id}")
async def list_documents(app_id: str, creds: HTTPAuthorizationCredentials = Depends(security)):
    verify_token(creds.credentials)
    app_dir = DOCS_ROOT / app_id
    if not app_dir.exists(): return {"app_id": app_id, "documents": []}
    docs = [json.loads(f.read_text()) for f in app_dir.rglob("*.meta.json")]
    docs.sort(key=lambda d: d["uploaded_at"], reverse=True)
    return {"app_id": app_id, "documents": docs}


@app.get("/api/docs/download/{app_id}/{checklist_id}/{doc_id}")
async def download_document(app_id: str, checklist_id: str, doc_id: str,
                             creds: HTTPAuthorizationCredentials = Depends(security)):
    verify_token(creds.credentials)
    path = DOCS_ROOT / app_id / checklist_id / doc_id
    if not path.exists(): raise HTTPException(status_code=404)
    return FileResponse(str(path), filename=doc_id)


# ── AI Assistant (Gemini key is server-side, never exposed) ──────────────────
@app.post("/api/ai/query")
async def ai_query(req: AIQueryRequest,
                   creds: HTTPAuthorizationCredentials = Depends(security)):
    import httpx
    payload = verify_token(creds.credentials)
    if not payload: raise HTTPException(status_code=401)

    # Build context
    ctx = []
    if req.app_id:
        cl = vault.get_checklist(req.app_id)
        if cl:
            ctx.append(f"Bank checklist for {req.app_id}:\n" +
                "\n".join(f"  {i['id']}: {i['title']} ({i['category']})" for i in cl))
        docs = [json.loads(f.read_text()) for f in (DOCS_ROOT / req.app_id).rglob("*.meta.json")] \
               if (DOCS_ROOT / req.app_id).exists() else []
        if docs:
            ctx.append("Uploaded documents:\n" +
                "\n".join(f"  [{d['checklist_id']}] {d['original_name']} by {d['uploaded_by']}" for d in docs))
        sim = vault.similarity_search(req.query, req.app_id, n_results=3)
        if sim:
            ctx.append("Relevant vault evidence:\n" +
                "\n".join(f"  {s['checklist_id']}: {json.dumps(s['evidence'])[:250]}" for s in sim))

    system_prompt = (
        "You are an expert audit assistant for a banking Audit Chain Evidence Vault. "
        "The bank uses a fixed 7-item checklist: CMDB Integration, CyberArk Integration, "
        "Architecture Diagram, Data Flow Diagram, OS Baseline Sign-off, DB Sign-off, DAM Integration. "
        "Help auditors understand evidence status, interpret documents, identify gaps, and provide "
        "compliance guidance. Be concise and reference checklist IDs (BK001-BK007) when relevant.\n\n"
        + ("\n\n".join(ctx) if ctx else "No application context provided.")
    )

    url     = f"{GEMINI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
    body    = {"model": GEMINI_MODEL, "max_tokens": 1024,
               "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user",   "content": req.query}]}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data   = resp.json()
            answer = data["choices"][0]["message"]["content"]
            return {"answer": answer, "model": GEMINI_MODEL}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI call failed: {e}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

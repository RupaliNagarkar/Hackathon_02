# Audit Chain Evidence Vault v3 — Banking Standard

## What Changed in v3

| Change | Detail |
|--------|--------|
| Fixed 7-item bank checklist | CMDB, CyberArk, Architecture Diagram, Data Flow Diagram, OS Baseline Sign-off, DB Sign-off, DAM Integration — same for all apps |
| AI key fixed server-side | Gemini API key lives in `backend/main.py` only — never sent to frontend |
| No description field | Upload form simplified — just App, Checklist Item, and file |
| Auditor sees all apps | Dropdown shows APP001/002/003 for auditors/admin |
| BankUser replaces maker/checker | One role per app for document upload |
| Coverage donut + gap % | Agent reports completion% and gap% after scanning all 7 items |

---

## Login Credentials

| Username   | Password    | Role      | Access        |
|------------|------------|-----------|---------------|
| auditor1   | audit@123  | Auditor   | All apps      |
| auditor2   | audit@456  | Auditor   | All apps      |
| admin      | admin@123  | Admin     | All apps      |
| bankuser1  | bank@001   | BankUser  | APP001 only   |
| bankuser2  | bank@002   | BankUser  | APP002 only   |
| bankuser3  | bank@003   | BankUser  | APP003 only   |

---

## 7-Item Bank Checklist

| ID    | Title                    | Category        |
|-------|--------------------------|-----------------|
| BK001 | CMDB Integration         | Infrastructure  |
| BK002 | CyberArk Integration     | Security        |
| BK003 | Architecture Diagram     | Documentation   |
| BK004 | Data Flow Diagram        | Documentation   |
| BK005 | OS Baseline Sign-off     | Compliance      |
| BK006 | DB Sign-off              | Compliance      |
| BK007 | DAM Integration          | Security        |

---

## Project Structure

```
audit-vault/
├── frontend/
│   └── index.html          ← Standalone UI, no build needed
├── backend/
│   ├── main.py             ← FastAPI, Gemini key hardcoded here
│   ├── auth.py             ← All users + JWT
│   └── requirements.txt
├── agents/
│   ├── master_agent.py     ← Checks all 7 items, computes coverage%
│   ├── search_agent.py     ← 7 bank connectors (CMDB, CyberArk, etc.)
│   ├── evidence_agent.py
│   └── exception_agent.py
├── vector_db/
│   └── vault.py            ← ChromaDB + fixed checklist
└── vault/
    └── docs/               ← Uploaded files stored here
        ├── APP001/<BK_ID>/
        ├── APP002/<BK_ID>/
        └── APP003/<BK_ID>/
```

---

## Setup

```bash
cd backend

# Set your Gemini key in main.py line:
#   GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open `frontend/index.html` in browser. The frontend simulation works without the backend.

---

## Getting a Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Paste it into `backend/main.py` → `GEMINI_API_KEY = "AIza..."`
4. In the frontend `index.html`, update line: `const GEMINI_KEY = "AIza..."`

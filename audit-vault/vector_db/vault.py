"""
Evidence Vault — ChromaDB vector store
Fixed 7-item bank checklist applied to every application.
"""
import chromadb, json, uuid, logging
from chromadb.utils import embedding_functions
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── Constant bank checklist (same for every app) ─────────────────────────────
BANK_CHECKLIST = [
    {"id": "BK001", "title": "CMDB Integration",           "category": "Infrastructure", "required": True},
    {"id": "BK002", "title": "CyberArk Integration",       "category": "Security",       "required": True},
    {"id": "BK003", "title": "Architecture Diagram",       "category": "Documentation",  "required": True},
    {"id": "BK004", "title": "Data Flow Diagram",          "category": "Documentation",  "required": True},
    {"id": "BK005", "title": "OS Baseline Sign-off",       "category": "Compliance",     "required": True},
    {"id": "BK006", "title": "DB Sign-off",                "category": "Compliance",     "required": True},
    {"id": "BK007", "title": "DAM Integration",            "category": "Security",       "required": True},
]

SUPPORTED_APPS = ["APP001", "APP002", "APP003"]


class EvidenceVault:
    def __init__(self):
        self.client = chromadb.Client()
        self.ef     = embedding_functions.DefaultEmbeddingFunction()
        self.evidence_col = self.client.get_or_create_collection(
            name="evidence_vault",
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"},
        )
        self.exception_col = self.client.get_or_create_collection(
            name="exceptions_vault",
            embedding_function=self.ef,
        )
        self._seed()

    # ── Checklist ─────────────────────────────────────────────────────────────
    def get_checklist(self, app_id: str) -> Optional[List[Dict]]:
        if app_id not in SUPPORTED_APPS:
            return None
        return BANK_CHECKLIST

    # ── Evidence ──────────────────────────────────────────────────────────────
    def store_evidence(self, app_id: str, checklist_id: str, evidence: Dict) -> str:
        doc_id = f"{app_id}_{checklist_id}_{uuid.uuid4().hex[:8]}"
        text   = " | ".join(f"{k}: {v}" for k, v in evidence.items() if isinstance(v, (str, int, float, bool)))
        self.evidence_col.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[{"app_id": app_id, "checklist_id": checklist_id,
                        "stored_at": datetime.utcnow().isoformat(),
                        "evidence_json": json.dumps(evidence)}],
        )
        return doc_id

    def get_evidence(self, app_id: str, checklist_id: str) -> Optional[Dict]:
        results = self.evidence_col.get(
            where={"$and": [{"app_id": {"$eq": app_id}}, {"checklist_id": {"$eq": checklist_id}}]}
        )
        if not results["ids"]:
            return None
        return json.loads(results["metadatas"][0]["evidence_json"])

    def check_evidence_exists(self, app_id: str, checklist_id: str) -> bool:
        return self.get_evidence(app_id, checklist_id) is not None

    def similarity_search(self, query: str, app_id: str, n_results: int = 5) -> List[Dict]:
        try:
            results = self.evidence_col.query(
                query_texts=[query], n_results=n_results,
                where={"app_id": {"$eq": app_id}},
            )
            return [
                {"id": rid, "checklist_id": meta["checklist_id"],
                 "distance": dist, "evidence": json.loads(meta["evidence_json"]),
                 "stored_at": meta["stored_at"]}
                for rid, meta, dist in zip(
                    results["ids"][0], results["metadatas"][0], results["distances"][0]
                )
            ]
        except Exception as e:
            logger.warning(f"Similarity search failed: {e}")
            return []

    # ── Exceptions ────────────────────────────────────────────────────────────
    def store_exception(self, app_id: str, checklist_id: str, exception: Dict) -> str:
        exc_id = f"EXC_{app_id}_{checklist_id}_{uuid.uuid4().hex[:6]}"
        text   = f"Exception {app_id} {checklist_id}: {exception.get('description','')}"
        self.exception_col.upsert(
            ids=[exc_id], documents=[text],
            metadatas=[{"app_id": app_id, "checklist_id": checklist_id,
                        "exception_json": json.dumps(exception),
                        "raised_at": datetime.utcnow().isoformat()}],
        )
        return exc_id

    def get_exceptions(self, app_id: str) -> List[Dict]:
        results = self.exception_col.get(where={"app_id": {"$eq": app_id}})
        return [
            {"id": eid, "checklist_id": meta["checklist_id"],
             "raised_at": meta["raised_at"], **json.loads(meta["exception_json"])}
            for eid, meta in zip(results["ids"], results["metadatas"])
        ]

    # ── Stats ─────────────────────────────────────────────────────────────────
    def get_stats(self) -> Dict:
        return {
            "total_evidence_items": self.evidence_col.count(),
            "total_exceptions":     self.exception_col.count(),
            "supported_apps":       SUPPORTED_APPS,
            "checklist_items":      len(BANK_CHECKLIST),
        }

    # ── Seed ──────────────────────────────────────────────────────────────────
    def _seed(self):
        seeds = [
            ("APP001", "BK001", {"title": "CMDB Integration", "status": "Completed",
                                  "cmdb_tool": "ServiceNow", "assets_registered": 142,
                                  "last_sync": "2024-03-01", "source": "CMDB Team"}),
            ("APP001", "BK002", {"title": "CyberArk Integration", "status": "Completed",
                                  "vault_accounts": 28, "pam_enabled": True,
                                  "last_review": "2024-02-15", "source": "IAM/PAM Team"}),
            ("APP002", "BK001", {"title": "CMDB Integration", "status": "Completed",
                                  "cmdb_tool": "ServiceNow", "assets_registered": 87,
                                  "last_sync": "2024-02-28", "source": "CMDB Team"}),
        ]
        for app_id, cl_id, ev in seeds:
            if not self.check_evidence_exists(app_id, cl_id):
                self.store_evidence(app_id, cl_id, ev)

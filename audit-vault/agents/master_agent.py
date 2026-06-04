"""
Agent 1 — Master Agent
Checks all 7 bank checklist items, considers uploaded documents,
computes completion % and remaining gap.
"""
import asyncio, logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DOCS_ROOT = Path(__file__).parent.parent / "vault" / "docs"


class MasterAgent:
    name = "MasterAgent"

    def __init__(self, vault):
        self.vault = vault

    async def process(self, app_id, auditor, search_agent, evidence_agent,
                      query=None, checklist_id=None) -> Dict[str, Any]:
        logger.info(f"[{self.name}] app_id={app_id}")

        checklist = self.vault.get_checklist(app_id)
        if not checklist:
            return {"status": "error", "message": f"Unknown application: {app_id}"}

        if checklist_id:
            checklist = [c for c in checklist if c["id"] == checklist_id]

        sim_results = []
        if query:
            sim_results = self.vault.similarity_search(query, app_id, n_results=5)

        results = await asyncio.gather(*[
            self._process_item(item, app_id, auditor, search_agent, evidence_agent)
            for item in checklist
        ])

        total    = len(results)
        complete = sum(1 for r in results if r["status"] in ("vault", "fetched", "doc_present"))
        missing  = total - complete
        pct      = round(complete / total * 100, 1) if total else 0

        return {
            "app_id":    app_id,
            "auditor":   auditor,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total":          total,
                "completed":      complete,
                "missing":        missing,
                "completion_pct": pct,
                "gap_pct":        round(100 - pct, 1),
            },
            "checklist_results":       list(results),
            "similarity_search_results": sim_results,
        }

    async def _process_item(self, item, app_id, auditor, search_agent, evidence_agent) -> Dict:
        cid = item["id"]

        # 1 — Check vault
        if self.vault.check_evidence_exists(app_id, cid):
            ev = self.vault.get_evidence(app_id, cid)
            return {**item, "status": "vault", "status_label": "In Vault",
                    "evidence": ev, "agent_used": None, "doc_count": self._doc_count(app_id, cid)}

        # 2 — Check uploaded documents
        doc_count = self._doc_count(app_id, cid)
        if doc_count > 0:
            return {**item, "status": "doc_present", "status_label": "Document Uploaded",
                    "evidence": None, "agent_used": None, "doc_count": doc_count}

        # 3 — Try search agent
        raw = await search_agent.fetch(app_id, cid, item)
        if raw:
            ev = await evidence_agent.generate_and_store(app_id, cid, item, raw, auditor)
            return {**item, "status": "fetched", "status_label": "Agent Fetched",
                    "evidence": ev, "agent_used": "SearchAgent + EvidenceAgent",
                    "doc_count": doc_count}

        return {**item, "status": "missing", "status_label": "Missing",
                "evidence": None, "agent_used": None, "doc_count": doc_count}

    def _doc_count(self, app_id: str, checklist_id: str) -> int:
        d = DOCS_ROOT / app_id / checklist_id
        if not d.exists():
            return 0
        return len([f for f in d.iterdir() if not f.name.endswith(".meta.json")])

"""Agent 3 — Evidence Agent: structures raw data and pushes to vault."""
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class EvidenceAgent:
    name = "EvidenceAgent"

    def __init__(self, vault):
        self.vault = vault

    async def generate_and_store(self, app_id, checklist_id, checklist_item, raw_data, auditor) -> Dict[str, Any]:
        ev = {
            "app_id":          app_id,
            "checklist_id":    checklist_id,
            "checklist_title": checklist_item.get("title", ""),
            "category":        checklist_item.get("category", ""),
            "source":          raw_data.get("source", "Unknown"),
            "retrieved_at":    raw_data.get("retrieved_at", datetime.utcnow().isoformat()),
            "generated_by":    self.name,
            "generated_at":    datetime.utcnow().isoformat(),
            "auditor":         auditor,
            "evidence_data":   raw_data.get("data", {}),
            "review_status":   "Pending Review",
            "is_complete":     len(raw_data.get("data", {})) >= 2,
        }
        doc_id = self.vault.store_evidence(app_id, checklist_id, ev)
        ev["vault_doc_id"] = doc_id
        logger.info(f"[{self.name}] Stored {doc_id}")
        return ev

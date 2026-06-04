"""Exception Handling Agent — RAF, Pending, Waiver, Remediation."""
import logging, uuid
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

EXCEPTION_TYPES = {
    "RAF":      {"label": "Risk Acceptance Form",  "sla_days": 5,  "approver": "CISO"},
    "PENDING":  {"label": "Pending Exception",      "sla_days": 15, "approver": "IT Manager"},
    "WAIVER":   {"label": "Temporary Waiver",       "sla_days": 30, "approver": "Risk Committee"},
    "REMEDIATE":{"label": "Remediation Required",   "sla_days": 10, "approver": "App Owner"},
}


class ExceptionAgent:
    name = "ExceptionAgent"

    def __init__(self, vault):
        self.vault = vault

    async def handle(self, app_id, checklist_id, exception_type, description, raised_by, auditor) -> Dict[str, Any]:
        if exception_type not in EXCEPTION_TYPES:
            return {"status": "error", "message": f"Unknown type: {exception_type}"}
        meta = EXCEPTION_TYPES[exception_type]
        exc = {
            "exception_id":   f"EXC-{uuid.uuid4().hex[:8].upper()}",
            "type":           exception_type,
            "type_label":     meta["label"],
            "app_id":         app_id,
            "checklist_id":   checklist_id,
            "description":    description,
            "raised_by":      raised_by,
            "auditor":        auditor,
            "raised_at":      datetime.utcnow().isoformat(),
            "sla_due":        (datetime.utcnow() + timedelta(days=meta["sla_days"])).isoformat(),
            "approver":       meta["approver"],
            "lifecycle_status": "OPEN",
        }
        exc_id = self.vault.store_exception(app_id, checklist_id, exc)
        exc["vault_id"] = exc_id
        logger.info(f"[{self.name}] Exception created: {exc['exception_id']}")
        return {"status": "created", "exception": exc}

"""
Immutable Audit Logger for EU AI Act Article 12 & GDPR Record-Keeping.
Maintains tamper-evident structured audit records for ingestion, retrieval, inference, and erasure.
"""

import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Schema for an auditable compliance event."""
    event_id: str
    event_type: str  # 'INGESTION', 'PII_REDACTION', 'QUERY_EXECUTION', 'CRYPTO_SHRED', 'VERIFICATION'
    tenant_id: str
    actor_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resource_hash: str  # SHA-256 of document/query content
    details: Dict[str, Any] = Field(default_factory=dict)
    compliance_tags: List[str] = Field(default_factory=list)  # e.g., ['GDPR_ART_17', 'EU_AI_ACT_ART_12']
    prev_record_hash: Optional[str] = None
    record_hash: Optional[str] = None


class AuditLogger:
    """
    Appends audit events to an immutable JSON Lines ledger with hash chaining for tamper detection.
    """

    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file = Path(log_file_path or "./logs/audit_ledger.jsonl")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash: Optional[str] = self._get_latest_hash()

    def _get_latest_hash(self) -> Optional[str]:
        """Reads the last line of the audit ledger to recover the previous hash."""
        if not self.log_file.exists():
            return None
        
        last_line = None
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line
        
        if last_line:
            try:
                data = json.loads(last_line)
                return data.get("record_hash")
            except Exception:
                return None
        return None

    def _compute_record_hash(self, event_dict: Dict[str, Any], prev_hash: Optional[str]) -> str:
        """Computes SHA-256 over canonical JSON string + previous record hash."""
        canonical = json.dumps(event_dict, sort_keys=True, separators=(',', ':'))
        to_hash = f"{prev_hash or 'GENESIS'}:{canonical}".encode("utf-8")
        return hashlib.sha256(to_hash).hexdigest()

    def log_event(
        self,
        event_type: str,
        tenant_id: str,
        actor_id: str,
        raw_content_to_hash: str,
        details: Optional[Dict[str, Any]] = None,
        compliance_tags: Optional[List[str]] = None
    ) -> AuditEvent:
        """Creates, hashes, chains, and records a compliance audit event."""
        res_hash = hashlib.sha256(raw_content_to_hash.encode("utf-8")).hexdigest()
        event_id = f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{hashlib.sha256(os.urandom(8)).hexdigest()[:8]}"
        
        event_data = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resource_hash": res_hash,
            "details": details or {},
            "compliance_tags": compliance_tags or [],
            "prev_record_hash": self._last_hash
        }

        record_hash = self._compute_record_hash(event_data, self._last_hash)
        event_data["record_hash"] = record_hash
        self._last_hash = record_hash

        event = AuditEvent(**event_data)

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

        return event

    def query_logs(
        self,
        tenant_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditEvent]:
        """Queries recorded audit logs filtered by tenant or event type."""
        results = []
        if not self.log_file.exists():
            return results

        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if tenant_id and data.get("tenant_id") != tenant_id:
                        continue
                    if event_type and data.get("event_type") != event_type:
                        continue
                    results.append(AuditEvent(**data))
                except Exception:
                    continue

        return results[-limit:]


# Global audit logger instance
global_audit_logger = AuditLogger()

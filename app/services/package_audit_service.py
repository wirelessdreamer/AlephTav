from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.foundation_contract_service import validate_contract
from app.services.immutable_file_service import install_immutable
from app.services.registry_service import deterministic_json


def record_package_mutation(
    *,
    package_id: str,
    before_hash: str,
    after_hash: str,
    summary: str,
    rationale: str,
    created_by: str,
    checks: list[str],
    review_signoff: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if not all((package_id, before_hash, after_hash, summary, rationale, created_by, checks)):
        raise ValueError("Package mutation requires hashes, actor, rationale and checks")
    namespace = re.sub(r"[^a-z0-9_-]", "_", package_id.lower()).strip("_")
    if not namespace or not namespace[0].isalpha():
        raise ValueError("Package ID must begin with an ASCII letter")
    event = idempotency_key if idempotency_key is not None else uuid4().hex
    digest = hashlib.sha256(f"{package_id}:{event}".encode()).hexdigest()[:24]
    path = get_settings().content_dir / "audit" / "packages" / f"{namespace}.{digest}.json"
    if path.exists():
        import json

        previous = json.loads(path.read_text(encoding="utf-8"))
        if (previous["entity_id"], previous["before_hash"], previous["after_hash"]) != (
            package_id,
            before_hash,
            after_hash,
        ):
            raise ValueError("Audit idempotency key reused for a different mutation")
        return previous
    record = {
        "audit_id": f"aud.pkg.{namespace}.{digest}.0001",
        "entity_type": "package",
        "entity_id": package_id,
        "change_type": "register" if before_hash == "0" * 64 else "update",
        "before_hash": before_hash,
        "after_hash": after_hash,
        "summary": summary,
        "rationale": rationale,
        "triggered_by_issue": None,
        "triggered_by_pr": None,
        "created_by": created_by,
        "created_at": datetime.now(UTC).isoformat(),
        "checks": checks,
        "review_signoff": review_signoff or {},
    }
    validate_contract("audit_record.schema.json", record)
    install_immutable(path, deterministic_json(record).encode("utf-8"))
    return record

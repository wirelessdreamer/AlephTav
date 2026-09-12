"""Codex translation sessions, runs and evidence assembly (FR-3, FR-4, FR-5, FR-6).

A translation session maps one-to-one onto a Codex thread. Only opaque local
metadata is persisted -- never authentication payloads, tokens, or login URLs.

Codex output is validated against the generation contract before anything is
saved. A failed run is preserved as an auditable error and no rendering is
created; a successful run creates renderings as ``proposed`` only.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.errors import GenerationError, NotFoundError, ValidationError
from app.services import (
    codex_app_server_service as codex,
)
from app.services import (
    generation_service,
    registry_service,
    rendering_service,
)

PROMPT_TEMPLATE_VERSION = "codex-translation-v1"

RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"
RUN_INVALID_OUTPUT = "invalid_output"

#: Fields never written to the session store, even if Codex returns them.
_CREDENTIAL_KEYS = frozenset(
    {"accessToken", "refreshToken", "access_token", "refresh_token", "authUrl", "loginUrl", "token"}
)


def _store_path():
    return get_settings().caches_dir / "codex_sessions.json"


def _read_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return {"sessions": {}, "runs": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - corrupt cache is rebuildable
        return {"sessions": {}, "runs": {}}
    data.setdefault("sessions", {})
    data.setdefault("runs", {})
    return data


def _write_store(store: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in _CREDENTIAL_KEYS}


def _now() -> str:
    return datetime.now(UTC).isoformat()


# -- Sessions (FR-3) -------------------------------------------------------


def create_session(
    client: codex.CodexAppServerClient,
    psalm_id: str,
    unit_id: str | None = None,
    layer: str = "literal",
    model: str = "",
    purpose: str = "translation",
    base_instructions: str | None = None,
) -> dict[str, Any]:
    thread_id = client.start_thread(base_instructions=base_instructions)
    session = {
        "session_id": f"cxs.{uuid.uuid4().hex[:12]}",
        "thread_id": thread_id,
        "current_turn_id": None,
        "model": model,
        "provider": codex.PROVIDER_NAME,
        "provider_version": codex.CLIENT_VERSION,
        "purpose": purpose,
        "psalm_id": psalm_id,
        "unit_id": unit_id,
        "layer": layer,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "started_at": _now(),
        "completed_at": None,
        "status": "open",
    }
    store = _read_store()
    store["sessions"][session["session_id"]] = session
    _write_store(store)
    return session


def get_session(session_id: str) -> dict[str, Any]:
    session = _read_store()["sessions"].get(session_id)
    if session is None:
        raise NotFoundError(f"Codex session not found: {session_id}")
    return session


def list_sessions(psalm_id: str | None = None) -> list[dict[str, Any]]:
    sessions = list(_read_store()["sessions"].values())
    if psalm_id:
        sessions = [s for s in sessions if s["psalm_id"] == psalm_id]
    return sorted(sessions, key=lambda s: s["started_at"])


def resume_session(client: codex.CodexAppServerClient, session_id: str) -> dict[str, Any]:
    """Resume a psalm's translation thread without restating the policy."""
    session = get_session(session_id)
    client.resume_thread(session["thread_id"])
    session["status"] = "open"
    store = _read_store()
    store["sessions"][session_id] = session
    _write_store(store)
    return session


# -- Generation inputs (FR-4) ---------------------------------------------


def build_translation_prompt(
    unit_id: str,
    layer: str,
    candidate_count: int = 2,
    style_profile: str | None = None,
    meter_target: str | None = None,
    constraints: list[str] | None = None,
) -> str:
    """Assemble only the evidence the task needs, as required by FR-4."""
    unit = registry_service.load_unit(unit_id)
    tokens = unit.get("tokens", [])

    token_lines = []
    for token in tokens:
        bits = [f"{token.get('token_id')}: {token.get('surface', '')}"]
        for key in ("lemma", "morphology", "gloss", "notes"):
            value = token.get(key)
            if value:
                bits.append(f"{key}={value}")
        token_lines.append("  " + " | ".join(str(b) for b in bits))

    literal = next(
        (r for r in unit.get("renderings", []) if r.get("layer") == "literal"),
        None,
    )
    locked = [
        f"  {r['layer']}: {r['text']}"
        for r in unit.get("renderings", [])
        if r.get("status") == "canonical" and r.get("layer") != layer
    ]

    sections = [
        "# Translation task",
        f"Unit: {unit_id}",
        # MT numbering is kept distinct so a superscription is never mistaken
        # for verse one.
        f"MT reference: {unit['ref']}",
        f"Display reference: {unit['ref']}",
        f"Required output layer: {layer}",
        f"Candidate count: {candidate_count}",
        "",
        "## Hebrew source meaning",
        unit["source_hebrew"],
        "",
        "## Hebrew tokens (ordered)",
        "\n".join(token_lines) if token_lines else "  (none recorded)",
    ]
    if literal is not None and layer != "literal":
        sections += ["", "## Literal baseline", f"  {literal['text']}"]
    if locked:
        sections += ["", "## Locked upstream layers", "\n".join(locked)]
    if style_profile:
        sections += ["", "## Style profile", f"  {style_profile}"]
    if meter_target:
        sections += ["", "## Singability / metrical adaptation target", f"  {meter_target}"]

    all_constraints = list(constraints or [])
    all_constraints.append("Return accuracy commentary in accuracy_note.")
    all_constraints.append("Return creative liberties in creative_liberties_note.")
    all_constraints.append("Do not alter the Hebrew source.")
    sections += ["", "## Constraints", "\n".join(f"  - {c}" for c in all_constraints)]
    return "\n".join(sections)


# -- Runs (FR-5, FR-6) -----------------------------------------------------


def _save_run(run: dict[str, Any]) -> dict[str, Any]:
    store = _read_store()
    store["runs"][run["run_id"]] = run
    if run.get("session_id") and run["session_id"] in store["sessions"]:
        store["sessions"][run["session_id"]]["current_turn_id"] = run.get("turn_id")
    _write_store(store)
    return run


def get_run(run_id: str) -> dict[str, Any]:
    run = _read_store()["runs"].get(run_id)
    if run is None:
        raise NotFoundError(f"Codex run not found: {run_id}")
    return run


def run_translation_turn(
    client: codex.CodexAppServerClient,
    session_id: str,
    unit_id: str,
    layer: str,
    candidate_count: int = 2,
    style_profile: str | None = None,
    meter_target: str | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    session = get_session(session_id)
    prompt = build_translation_prompt(
        unit_id,
        layer,
        candidate_count=candidate_count,
        style_profile=style_profile,
        meter_target=meter_target,
        constraints=constraints,
    )
    run: dict[str, Any] = {
        "run_id": f"cxr.{uuid.uuid4().hex[:12]}",
        "session_id": session_id,
        "thread_id": session["thread_id"],
        "turn_id": None,
        "unit_id": unit_id,
        "layer": layer,
        "provider": codex.PROVIDER_NAME,
        "model": session.get("model", ""),
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "started_at": _now(),
        "completed_at": None,
        "status": RUN_RUNNING,
        "events": [],
        "denied_events": [],
        "validation": None,
        "payload": None,
        "error": None,
    }
    _save_run(run)

    before = len(client.notifications)
    try:
        result = client.run_turn(
            thread_id=session["thread_id"],
            text=prompt,
            output_schema=generation_service.OUTPUT_VALIDATOR.schema,
            model=session.get("model") or None,
        )
    except GenerationError as error:
        run["status"] = RUN_FAILED
        run["error"] = str(error)
        run["completed_at"] = _now()
        run["events"] = [_scrub(n) for n in client.notifications[before:]]
        run["denied_events"] = list(client.denied_events)
        return _save_run(run)

    run["turn_id"] = result.get("turn_id")
    run["events"] = [_scrub(n) for n in client.notifications[before:]]
    run["denied_events"] = list(client.denied_events)
    run["completed_at"] = _now()

    try:
        payload = json.loads(result.get("text") or "")
    except json.JSONDecodeError:
        run["status"] = RUN_INVALID_OUTPUT
        run["error"] = "Codex returned output that was not valid JSON."
        return _save_run(run)

    errors = sorted(
        generation_service.OUTPUT_VALIDATOR.iter_errors(payload),
        key=lambda e: list(e.path),
    )
    if errors:
        # FR-5: preserve the failed run as an auditable error; create nothing.
        run["status"] = RUN_INVALID_OUTPUT
        run["validation"] = [
            {"path": "/".join(str(p) for p in error.path), "message": error.message}
            for error in errors
        ]
        run["error"] = "Codex output failed the generation contract."
        return _save_run(run)

    run["status"] = RUN_COMPLETED
    run["payload"] = payload
    return _save_run(run)


def cancel_run(client: codex.CodexAppServerClient, run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    if run["status"] == RUN_RUNNING and run.get("turn_id"):
        client.interrupt(run["thread_id"], str(run["turn_id"]))
    run["status"] = RUN_CANCELLED
    run["completed_at"] = _now()
    return _save_run(run)


def save_run_candidates(run_id: str, created_by: str = "codex") -> list[dict[str, Any]]:
    """Create renderings from a completed run.

    FR-6: Codex output always enters as ``proposed``. It can never be canonical,
    promote itself, or write content files directly -- creation still goes
    through rendering_service so an audit record is written.
    """
    run = get_run(run_id)
    if run["status"] != RUN_COMPLETED or not run.get("payload"):
        raise ValidationError(f"Run {run_id} has no validated payload to save")

    created: list[dict[str, Any]] = []
    for candidate in run["payload"].get("candidates", []):
        rendering = rendering_service.create_rendering(
            unit_id=run["unit_id"],
            layer=run["layer"],
            text=candidate["text"],
            # Hard-coded, not taken from the payload: Codex cannot choose its
            # own status.
            status="proposed",
            rationale=candidate.get("rationale", "codex suggestion"),
            created_by=created_by,
            alignment_ids=None,
            drift_flags=candidate.get("drift_flags"),
            metrics=candidate.get("metrics"),
            grounding_confidence=candidate.get("grounding_confidence"),
            translation_basis=candidate.get("translation_basis"),
            preserved_source_images=candidate.get("preserved_source_images"),
            differentiator=candidate.get("differentiator"),
            provenance={
                "provider": codex.PROVIDER_NAME,
                "model": run.get("model", ""),
                "thread_id": run["thread_id"],
                "turn_id": run.get("turn_id"),
                "run_id": run["run_id"],
                "prompt_template_version": run["prompt_template_version"],
                "generated_at": run.get("completed_at"),
                "contract_validated": True,
            },
        )
        created.append(rendering)
    return created

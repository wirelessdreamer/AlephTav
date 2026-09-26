from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import codex_analysis_service as analysis
from app.services import codex_app_server_service as codex
from app.services import codex_import_service as importing
from app.services import codex_translation_service as translation

router = APIRouter(tags=["codex"])


@router.post("/codex/psalms/{psalm_id}/import")
def import_translation(psalm_id: str, payload: dict) -> dict:
    """Place a pasted translation: its guidance on the psalm, its verses on each verse."""
    try:
        return importing.import_translation(
            codex.require_client(),
            session_id=payload["session_id"],
            psalm_id=psalm_id,
            text=str(payload.get("text", "")),
            layer=payload.get("layer", "lyric"),
            created_by=payload.get("created_by", "import"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/identify-psalm")
def identify_psalm(payload: dict) -> dict:
    """Ask Codex which psalm a pasted translation translates."""
    try:
        return importing.identify_psalm(codex.require_client(), str(payload.get("text", "")))
    except Exception as error:
        raise_as_http(error)


@router.get("/codex/status")
def codex_status() -> dict:
    """Local provider status. Never returns credentials (FR-1, FR-2)."""
    try:
        return codex.describe_status(codex.active_client())
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/codex/connect")
def codex_connect() -> dict:
    try:
        client = codex.connect()
        return codex.describe_status(client)
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/login")
def codex_login() -> dict:
    """Hand off to Codex's managed ChatGPT sign-in.

    AlephTav never reads the resulting tokens and never stores the login URL.
    """
    try:
        client = codex.require_client()
        result = client.login()
        return {
            "started": True,
            "auth_url_present": bool(
                result.get("authUrl") or result.get("auth_url") or result.get("loginUrl")
            ),
        }
    except Exception as error:
        raise_as_http(error)


@router.get("/codex/models")
def codex_models() -> list[dict]:
    try:
        return codex.require_client().list_models()
    except Exception as error:
        raise_as_http(error)


@router.get("/codex/sessions")
def list_codex_sessions(psalm_id: str | None = None) -> list[dict]:
    try:
        return translation.list_sessions(psalm_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/codex/sessions")
def create_codex_session(payload: dict) -> dict:
    try:
        return translation.create_session(
            codex.require_client(),
            psalm_id=payload["psalm_id"],
            unit_id=payload.get("unit_id"),
            layer=payload.get("layer", "literal"),
            model=payload.get("model", ""),
            purpose=payload.get("purpose", "translation"),
            base_instructions=payload.get("base_instructions"),
            translation_id=payload.get("translation_id") or None,
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/sessions/{session_id}/resume")
def resume_codex_session(session_id: str) -> dict:
    try:
        return translation.resume_session(codex.require_client(), session_id)
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/sessions/{session_id}/interrupt")
def interrupt_codex_session(session_id: str) -> dict:
    """Stop the turn this session is running, if any; the request waiting on it reports why."""
    try:
        return translation.interrupt_session(codex.require_client(), session_id)
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/sessions/{session_id}/turns")
def start_codex_turn(session_id: str, payload: dict) -> dict:
    try:
        return translation.run_translation_turn(
            codex.require_client(),
            session_id=session_id,
            unit_id=payload["unit_id"],
            layer=payload["layer"],
            candidate_count=payload.get("candidate_count", 2),
            style_profile=payload.get("style_profile"),
            meter_target=payload.get("meter_target"),
            constraints=payload.get("constraints"),
        )
    except Exception as error:
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/translation-guidance")
def get_translation_guidance(
    psalm_id: str, translation_id: str | None = Query(default=None)
) -> dict:
    try:
        translation_id = translation_id or None
        return {
            "psalm_id": psalm_id,
            "translation_id": translation_id,
            "translation_guidance": translation.get_guidance(psalm_id, translation_id),
        }
    except Exception as error:
        raise_as_http(error)


@router.put("/psalms/{psalm_id}/translation-guidance")
def put_translation_guidance(psalm_id: str, payload: dict) -> dict:
    """Store the translator's standing direction for one translation of this psalm."""
    try:
        return translation.set_guidance(
            psalm_id,
            payload.get("translation_guidance", ""),
            payload.get("translation_id") or None,
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/rows/{unit_id}/fill")
def fill_comparison_row(unit_id: str, payload: dict) -> dict:
    """Generate literal + English + accuracy notes for one comparison row."""
    try:
        return translation.fill_comparison_row(
            codex.require_client(),
            session_id=payload["session_id"],
            unit_id=unit_id,
            english_layer=payload.get("english_layer", "lyric"),
            created_by=payload.get("created_by", "codex"),
            style_profile=payload.get("style_profile"),
            meter_target=payload.get("meter_target"),
            constraints=payload.get("constraints"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/psalms/{psalm_id}/fill")
def fill_psalm_passage(psalm_id: str, payload: dict) -> dict:
    """Generate literal + English for several rows of a psalm, one turn per layer."""
    try:
        return translation.fill_psalm_passage(
            codex.require_client(),
            session_id=payload["session_id"],
            psalm_id=psalm_id,
            unit_ids=list(payload.get("unit_ids") or []),
            english_layer=payload.get("english_layer", "lyric"),
            created_by=payload.get("created_by", "codex"),
            style_profile=payload.get("style_profile"),
            meter_target=payload.get("meter_target"),
            constraints=payload.get("constraints"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/analysis/verses/{unit_id}")
def analyze_verse(unit_id: str, payload: dict) -> dict:
    """Audit one verse's existing renderings against the Hebrew."""
    try:
        return analysis.analyze_verse(
            codex.require_client(),
            session_id=payload["session_id"],
            unit_id=unit_id,
            english_layer=payload.get("english_layer", "lyric"),
            created_by=payload.get("created_by", "codex-analysis"),
            force=bool(payload.get("force", False)),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/verses/{unit_id}/rebuild")
def rebuild_verse(unit_id: str, payload: dict) -> dict:
    """Retranslate a verse with its open notes; held for the reviewer to accept."""
    try:
        return translation.rebuild_verse(
            codex.require_client(),
            session_id=payload["session_id"],
            unit_id=unit_id,
            english_layer=payload.get("english_layer", "lyric"),
            layers=payload.get("layers"),
            created_by=payload.get("created_by", "codex"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/verses/{unit_id}/rebuild/analyse")
def analyse_rebuild(unit_id: str, payload: dict) -> dict:
    """Audit a pending rebuild's text, blind to the notes that produced it."""
    try:
        return analysis.analyze_rebuild(
            codex.require_client(),
            session_id=payload["session_id"],
            unit_id=unit_id,
            created_by=payload.get("created_by", "codex-analysis"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/verses/{unit_id}/word-suggestions")
def suggest_word_renderings(unit_id: str, payload: dict) -> dict:
    """At least three ranked renderings for a word, from the translator."""
    try:
        return translation.suggest_word_renderings(
            codex.require_client(),
            session_id=payload["session_id"],
            unit_id=unit_id,
            token_ids=list(payload.get("token_ids") or []),
            layer=payload.get("layer", "lyric"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/analysis/psalms/{psalm_id}")
def analyze_psalm(psalm_id: str, payload: dict) -> dict:
    """Audit the psalm as a whole: sections, seams, guardrails, epistemics."""
    try:
        return analysis.analyze_psalm_scope(
            codex.require_client(),
            session_id=payload["session_id"],
            psalm_id=psalm_id,
            english_layer=payload.get("english_layer", "lyric"),
            created_by=payload.get("created_by", "codex-analysis"),
            force=bool(payload.get("force", False)),
        )
    except Exception as error:
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/analysis")
def get_psalm_analysis(psalm_id: str, translation_id: str | None = Query(default=None)) -> dict:
    """The translation's active psalm analysis, or nulls when none has been run."""
    try:
        record = analysis.active_analysis(psalm_id, translation_id or None)
        return {"psalm_id": psalm_id, "analysis": record}
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/runs/{run_id}/cancel")
def cancel_codex_run(run_id: str) -> dict:
    try:
        return translation.cancel_run(codex.require_client(), run_id)
    except Exception as error:
        raise_as_http(error)


@router.get("/codex/runs/{run_id}/events")
def codex_run_events(run_id: str) -> dict:
    """Streamed event log for a run, preserved even when the run failed."""
    try:
        run = translation.get_run(run_id)
        return {
            "run_id": run["run_id"],
            "status": run["status"],
            "events": run.get("events", []),
            "denied_events": run.get("denied_events", []),
            "validation": run.get("validation"),
            "error": run.get("error"),
        }
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/runs/{run_id}/save-candidates")
def save_codex_candidates(run_id: str, payload: dict | None = None) -> list[dict]:
    """Create renderings from a validated run. Always ``proposed`` (FR-6)."""
    try:
        request = payload or {}
        return translation.save_run_candidates(
            run_id, created_by=request.get("created_by", "codex")
        )
    except Exception as error:
        raise_as_http(error)

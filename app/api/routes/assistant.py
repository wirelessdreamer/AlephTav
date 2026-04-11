from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import assistant_service, settings_service

router = APIRouter(tags=["assistant"])


@router.get("/assistant/tools")
def list_tools() -> list[dict]:
    try:
        return assistant_service.list_actions()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/assistant/sessions")
def create_session() -> dict:
    try:
        return assistant_service.create_session()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/assistant/sessions/{session_id}/messages")
def post_message(session_id: str, payload: dict) -> dict:
    try:
        return assistant_service.post_message(session_id, payload["message"], payload.get("context"))
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/assistant/actions/preview")
def preview_action(payload: dict) -> dict:
    try:
        return assistant_service.preview_action(payload["action_id"], payload.get("input", {}))
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/assistant/actions/execute")
def execute_action(payload: dict) -> dict:
    try:
        return assistant_service.execute_action(
            payload["action_id"],
            payload.get("input", {}),
            confirmation_token=payload.get("confirmation_token"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/assistant/settings")
def get_assistant_settings() -> dict:
    try:
        return settings_service.public_settings()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/assistant/settings")
def patch_assistant_settings(payload: dict) -> dict:
    try:
        settings_service.update_settings(payload)
        return settings_service.public_settings()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)

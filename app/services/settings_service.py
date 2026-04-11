from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.config import get_settings
from app.services import registry_service


def _settings_template() -> dict[str, Any]:
    project = registry_service.load_project()
    return {
        "assistant": {
            "model_profile_id": project.get("default_model_profile"),
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "whisper_model": "whisper-1",
        },
        "voice": {
            "output_enabled": False,
            "output_provider": None,
            "output_voice": None,
        },
    }


def load_settings() -> dict[str, Any]:
    path = get_settings().assistant_settings_file
    if not path.exists():
        payload = _settings_template()
        registry_service.write_json(path, payload)
        return payload
    stored = registry_service.read_json(path)
    merged = _settings_template()
    merged.update(stored)
    for key in ("assistant", "openai", "voice"):
        merged[key].update(stored.get(key, {}))
    return merged


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    registry_service.write_json(get_settings().assistant_settings_file, payload)
    return payload


def update_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    updated = deepcopy(current)
    for section, value in patch.items():
        if isinstance(value, dict) and isinstance(updated.get(section), dict):
            updated[section].update(value)
        else:
            updated[section] = value
    return save_settings(updated)


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    masked = deepcopy(settings)
    api_key = masked["openai"].get("api_key", "")
    masked["openai"]["has_api_key"] = bool(api_key)
    masked["openai"]["api_key"] = ""
    return masked

from __future__ import annotations

import json
import uuid
from typing import Any
from urllib import error, request

from app.core.errors import GenerationError, ValidationError
from app.services import settings_service


def _multipart_body(fields: dict[str, str], file_field: str, filename: str, content_type: str, data: bytes) -> tuple[str, bytes]:
    boundary = f"----AlephTavBoundary{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    parts.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            data,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return boundary, b"".join(parts)


def transcribe_audio(filename: str, content_type: str, data: bytes, prompt: str | None = None) -> dict[str, Any]:
    if not data:
        raise ValidationError("Audio upload is empty")

    settings = settings_service.load_settings()
    openai_settings = settings.get("openai", {})
    api_key = openai_settings.get("api_key", "")
    if not api_key:
        raise ValidationError("OpenAI API key is not configured")

    model = openai_settings.get("whisper_model", "whisper-1")
    base_url = str(openai_settings.get("base_url", "https://api.openai.com/v1")).rstrip("/")
    fields = {"model": model, "response_format": "json"}
    if prompt:
        fields["prompt"] = prompt
    boundary, body = _multipart_body(fields, "file", filename, content_type or "application/octet-stream", data)
    transcription_request = request.Request(
        url=f"{base_url}/audio/transcriptions",
        method="POST",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with request.urlopen(transcription_request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:  # pragma: no cover
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(f"Transcription request failed: HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover
        raise GenerationError(f"Transcription request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise GenerationError("Transcription provider returned invalid JSON") from exc
    return {
        "text": payload.get("text", ""),
        "provider": "openai",
        "model": model,
        "filename": filename,
    }

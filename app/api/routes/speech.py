from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import raise_as_http
from app.services import speech_service

router = APIRouter(tags=["speech"])


@router.post("/speech/transcriptions")
async def transcribe_audio(file: UploadFile = File(...), prompt: str | None = Form(default=None)) -> dict:
    try:
        data = await file.read()
        return speech_service.transcribe_audio(file.filename or "audio.webm", file.content_type or "application/octet-stream", data, prompt)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)

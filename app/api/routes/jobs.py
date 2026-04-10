from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import generation_service

router = APIRouter(tags=["jobs"])


@router.post("/jobs/generate")
def generate_job(payload: dict) -> dict:
    try:
        return generation_service.generate_for_unit(
            unit_id=payload["unit_id"],
            layer=payload["layer"],
            style_profile=payload.get("style_profile", "study_literal"),
            model_profile=payload.get("model_profile"),
            seed=payload.get("seed", 42),
            candidate_count=payload.get("candidate_count", 1),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return generation_service.get_job(job_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        if "unit_id" not in request or "layer" not in request:
            job = generation_service.get_job(job_id)
            return generation_service.rerun_layer(
                job["unit_id"],
                job["layer"],
                style_profile=request.get("style_profile", "study_literal"),
                model_profile=request.get("model_profile"),
                seed=request.get("seed", job["seed"]),
                candidate_count=request.get("candidate_count", 1),
            )
        return generation_service.rerun_layer(
            request["unit_id"],
            request["layer"],
            style_profile=request.get("style_profile", "study_literal"),
            model_profile=request.get("model_profile"),
            seed=request.get("seed", 42),
            candidate_count=request.get("candidate_count", 1),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)

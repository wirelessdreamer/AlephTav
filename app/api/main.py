from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    alignments,
    alternates,
    assistant,
    audit,
    export,
    jobs,
    project,
    psalms,
    renderings,
    review,
    search,
    speech,
    tokens,
    units,
)

app = FastAPI(title="Psalms Copyleft Workbench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project.router)
app.include_router(psalms.router)
app.include_router(units.router)
app.include_router(tokens.router)
app.include_router(assistant.router)
app.include_router(search.router)
app.include_router(alignments.router)
app.include_router(renderings.router)
app.include_router(alternates.router)
app.include_router(review.router)
app.include_router(audit.router)
app.include_router(export.router)
app.include_router(jobs.router)
app.include_router(speech.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

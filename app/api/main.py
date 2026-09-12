from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    alignments,
    alternates,
    assistant,
    audit,
    corpus,
    export,
    jobs,
    project,
    psalms,
    renderings,
    review,
    search,
    source_map,
    speech,
    tokens,
    units,
)
from app.services import llama_runtime_service, registry_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the build-once summary caches so the first /psalms and
    # /corpus/layers requests hit RAM instead of touching disk. If the
    # caches haven't been built yet (fresh repo), this performs the build
    # and persists it. See registry_service.build_summary_cache.
    try:
        registry_service.list_psalm_summaries()
        registry_service.get_corpus_layers()
    except Exception:  # pragma: no cover - never block startup over cache warmup
        pass
    # Pre-load the public-domain witness maps (KJV/ASV/WEB). Each one parses
    # a multi-megabyte VPL text file out of a ZIP and is then `lru_cache`d
    # for the process lifetime; doing it here moves that one-time cost off
    # the first `/psalms/{id}` request, which is what the workbench
    # immediately fires for the default psalm.
    try:
        for source in registry_service.PUBLIC_DOMAIN_WITNESS_SOURCES:
            registry_service._load_public_domain_witness_map(source["source_id"])
    except Exception:  # pragma: no cover - witness cache is best-effort
        pass
    try:
        yield
    finally:
        llama_runtime_service.shutdown_all()


app = FastAPI(title="Psalms Copyleft Workbench API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project.router)
app.include_router(psalms.router)
app.include_router(corpus.router)
app.include_router(units.router)
app.include_router(tokens.router)
app.include_router(assistant.router)
app.include_router(search.router)
app.include_router(source_map.router)
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

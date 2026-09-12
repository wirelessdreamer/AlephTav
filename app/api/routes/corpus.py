from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import registry_service

router = APIRouter(tags=["corpus"])


@router.get("/corpus/layers")
def list_corpus_layers() -> list[str]:
    """Return the distinct rendering layer names present anywhere in the corpus.

    Used by the workbench to populate the layer selector without forcing the
    client to walk every unit's renderings. Backed by the derived SQLite
    ``rendering_index`` table; returns ``[]`` if indexes haven't been built.
    """
    try:
        return registry_service.get_corpus_layers()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)

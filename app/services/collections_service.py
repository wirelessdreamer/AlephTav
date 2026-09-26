"""Collections of translations: what the workbench shows as projects.

A collection gathers translations across psalms, as an album holds its Psalm 1 and its
Psalm 3, and holds at most one translation of each psalm. Every translation is in
exactly one collection. This is not the workbench project in ``content/project.json``,
which is the repository's configuration.

The default collection is built in and not stored: each psalm's main translation is in
it until moved. The others live in ``content/collections.json``. Which collection a
translation is in is kept on the translation, so placing and moving translations is
done by ``psalm_translations_service`` and audited on the psalm. Creating or renaming a
collection writes no audit record: an audit id is patterned to a unit, and a
collection belongs to none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.services import registry_service

DEFAULT_ID = "col.default"
DEFAULT_TITLE = "Main translations"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _stored() -> list[dict[str, Any]]:
    path = get_settings().collections_file
    if not path.exists():
        return []
    return list(registry_service.read_json(path)["collections"])


def _save(collections: list[dict[str, Any]]) -> None:
    registry_service.write_json(get_settings().collections_file, {"collections": collections})


def list_collections() -> list[dict[str, Any]]:
    """The default collection first, then the created ones, oldest first."""
    default = {"collection_id": DEFAULT_ID, "title": DEFAULT_TITLE, "built_in": True}
    return [default, *_stored()]


def get_collection(collection_id: str) -> dict[str, Any]:
    if not collection_id:
        raise ValidationError("Say which project")
    for collection in list_collections():
        if collection["collection_id"] == collection_id:
            return collection
    raise NotFoundError(f"There is no project {collection_id}")


def _refuse_taken_title(title: str, collection_id: str | None = None) -> None:
    for collection in list_collections():
        if (
            collection["collection_id"] != collection_id
            and collection["title"].casefold() == title.casefold()
        ):
            raise ValidationError(f"There is already a project named “{title}”")


def create_collection(title: str, created_by: str = "reviewer") -> dict[str, Any]:
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("A project needs a name")
    _refuse_taken_title(cleaned)
    collections = _stored()
    numbers = [int(c["collection_id"].rsplit(".", 1)[1]) for c in collections]
    collection = {
        "collection_id": f"col.{max(numbers, default=0) + 1:04d}",
        "title": cleaned,
        "created_by": created_by,
        "created_at": _now(),
    }
    collections.append(collection)
    _save(collections)
    return collection


def rename_collection(collection_id: str, title: str) -> dict[str, Any]:
    if collection_id == DEFAULT_ID:
        raise ValidationError(f"“{DEFAULT_TITLE}” keeps its name")
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("A project needs a name")
    _refuse_taken_title(cleaned, collection_id)
    collections = _stored()
    for collection in collections:
        if collection["collection_id"] == collection_id:
            collection["title"] = cleaned
            collection["updated_at"] = _now()
            _save(collections)
            return collection
    raise NotFoundError(f"There is no project {collection_id}")

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.core.errors import LicensePolicyError, NotFoundError
from app.services import greek_study_service, registry_service

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    unit_id = "lxx.authored.r0001.ps025.v001.a"
    unit = {"unit_id": unit_id, "source_greek": "λόγος", "tokens": []}
    path = registry_service.unit_path(unit_id)
    path.parent.mkdir(parents=True)
    data = json.dumps(unit).encode()
    path.write_bytes(data)
    manifest_path = path.parents[2] / "package.json"
    record = {
        "path": path.relative_to(manifest_path.parent).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }
    manifest_path.write_text(json.dumps({"files": [record]}), encoding="utf-8")
    view = SimpleNamespace(
        descriptor={"packages": [{"path": manifest_path.relative_to(tmp_path).as_posix()}]},
        payload={"units": [unit]},
    )
    monkeypatch.setattr(greek_study_service, "load_public_view", lambda: view)
    return unit_id, path, manifest_path, view


def test_greek_registry_read_requires_public_release(source, monkeypatch) -> None:
    def denied():
        raise LicensePolicyError("Source release unavailable")

    monkeypatch.setattr(greek_study_service, "load_public_view", denied)
    with pytest.raises(LicensePolicyError):
        registry_service.load_unit(source[0])


def test_greek_registry_read_requires_published_package_and_exact_bytes(source) -> None:
    unit_id, path, _, view = source
    assert registry_service.load_unit(unit_id)["source_greek"] == "λόγος"
    original = view.descriptor["packages"]
    view.descriptor["packages"] = []
    with pytest.raises(NotFoundError, match="outside the published"):
        registry_service.load_unit(unit_id)
    view.descriptor["packages"] = original
    path.write_text(json.dumps({"unit_id": unit_id, "source_greek": "κρυπτός"}), encoding="utf-8")
    with pytest.raises(ValueError, match="approved immutable"):
        registry_service.load_unit(unit_id)


def test_greek_registry_read_rejects_unlisted_file_or_forged_catalog(source) -> None:
    unit_id, _, manifest_path, view = source
    view.payload["units"] = [{"unit_id": unit_id, "source_greek": "κρυπτός"}]
    with pytest.raises(ValueError, match="published catalog"):
        registry_service.load_unit(unit_id)
    manifest_path.write_text(json.dumps({"files": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="approved immutable"):
        registry_service.load_unit(unit_id)

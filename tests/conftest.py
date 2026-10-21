from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_WORKSPACE = Path(tempfile.gettempdir()) / f"alephtav-pytest-{uuid4().hex}"
TEST_ROOT = Path(os.environ.get("ALEPHTAV_TEST_ROOT", TEST_WORKSPACE)).resolve()

if TEST_ROOT == ROOT or ROOT.is_relative_to(TEST_ROOT):
    raise RuntimeError("ALEPHTAV_TEST_ROOT must be an isolated test workspace")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["ALEPHTAV_ROOT_DIR"] = str(TEST_ROOT)


def _link_or_copy(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(source, target_is_directory=source.is_dir())
    except OSError:
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def _copy_tree(source: Path, target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


TEST_ROOT.mkdir(parents=True, exist_ok=True)
_link_or_copy(ROOT / "schemas", TEST_ROOT / "schemas")

from tests.support import bootstrap_fixture_repo  # noqa: E402


@pytest.fixture(scope="session")
def fixture_sources() -> None:
    _copy_tree(ROOT / "data" / "raw", TEST_ROOT / "data" / "raw")


@pytest.fixture(autouse=True)
def seeded_repo(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("no_seeded_repo"):
        return
    request.getfixturevalue("fixture_sources")
    bootstrap_fixture_repo()

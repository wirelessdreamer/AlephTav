from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(os.environ.get("ALEPHTAV_TEST_ROOT", Path(tempfile.gettempdir()) / "alephtav-pytest-workspace")).resolve()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ALEPHTAV_ROOT_DIR", str(TEST_ROOT))


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


TEST_ROOT.mkdir(parents=True, exist_ok=True)
_link_or_copy(ROOT / "schemas", TEST_ROOT / "schemas")
_link_or_copy(ROOT / "data" / "raw", TEST_ROOT / "data" / "raw")

from tests.support import bootstrap_fixture_repo


@pytest.fixture(autouse=True)
def seeded_repo(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("no_seeded_repo"):
        return
    bootstrap_fixture_repo()

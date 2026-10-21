from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_seeded_repo

ROOT = Path(__file__).resolve().parents[2]


def _load_test_configuration(test_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("ALEPHTAV_TEST_ROOT", None)
    if test_root is not None:
        env["ALEPHTAV_TEST_ROOT"] = str(test_root)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, runpy; "
            "config = runpy.run_path('tests/conftest.py'); "
            "root = config['TEST_ROOT']; "
            "print(json.dumps({'root': str(root), "
            "'has_raw': (root / 'data/raw').exists(), "
            "'has_schemas': (root / 'schemas').is_dir()}))",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_independent_test_runs_use_distinct_roots_without_copying_raw() -> None:
    first = _load_test_configuration()
    second = _load_test_configuration()
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_root = json.loads(first.stdout)
    second_root = json.loads(second.stdout)
    assert first_root["root"] != second_root["root"]
    assert first_root["has_schemas"] and second_root["has_schemas"]
    assert not first_root["has_raw"] and not second_root["has_raw"]


@pytest.mark.parametrize("unsafe_root", [ROOT, ROOT.parent])
def test_test_configuration_rejects_live_workspace_or_parent(unsafe_root: Path) -> None:
    result = _load_test_configuration(unsafe_root)
    assert result.returncode != 0
    assert "must be an isolated test workspace" in result.stderr

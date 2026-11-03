"""Hash and immutable-file checks read raw bytes, so a checkout must not convert line endings."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_seeded_repo

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [
        "content/mt/source_snapshots/mt.f352dcdea73daa036a807af6/source_tokens.json",
        "content/audit/packages/source_policy.ab4537d9ff4ed35bb62e4059.json",
        "app/services/greek_lexical_forms.py",
    ],
)
def test_byte_checked_files_check_out_with_lf(path: str) -> None:
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", path],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"{path}: eol: lf"

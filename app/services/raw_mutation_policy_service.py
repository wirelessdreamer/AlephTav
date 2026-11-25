"""Refuse unscoped writes that have no supported audited operation."""

from __future__ import annotations

from typing import NoReturn

from app.core.errors import ValidationError


def reject_unit_update() -> NoReturn:
    raise ValidationError("Raw unit updates are disabled; use the dedicated workbench operations.")


def reject_project_update() -> NoReturn:
    raise ValidationError(
        "Raw project updates are disabled until an authorized, audited "
        "administration workflow is available."
    )

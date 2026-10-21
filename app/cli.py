from __future__ import annotations

import json
from pathlib import Path

import typer

from app.core.config import get_settings
from app.services import (
    concordance_service,
    export_service,
    generation_service,
    github_link_service,
    ingest_service,
    registry_service,
    rendering_service,
    report_service,
    visual_flow_service,
)

app = typer.Typer(help="Psalms translation workbench CLI")


@app.command("migrate-operational-state")
def migrate_operational_state(writers_quiesced: bool = False) -> None:
    """After stopping API/job writers, copy legacy jobs/cards to durable local storage."""
    from app.db.session import migrate_operational_state as migrate

    if not writers_quiesced:
        typer.echo("Stop API/job writers, then rerun with --writers-quiesced.", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(migrate(writers_quiesced=True), indent=2))


@app.command("init-project")
def init_project() -> None:
    project = registry_service.bootstrap_project()
    typer.echo(f"Initialized project {project['project_id']}")


@app.command("import-psalms")
def import_psalms() -> None:
    units = ingest_service.import_vendored_psalms()
    typer.echo(f"Imported {len(units)} unit(s)")


@app.command("attach-annotations")
def attach_annotations() -> None:
    updated = ingest_service.attach_fixture_annotations()
    typer.echo(f"Attached annotations for {updated} unit(s)")


@app.command("build-indexes")
def build_indexes() -> None:
    result = concordance_service.rebuild_indexes()
    typer.echo(json.dumps(result, indent=2))


@app.command("validate-content")
def validate_content() -> None:
    from scripts.validate_content import validate_all_content

    result = validate_all_content()
    typer.echo(json.dumps(result, indent=2))
    if result["errors"]:
        raise typer.Exit(1)


@app.command("audit-licenses")
def audit_licenses() -> None:
    result = registry_service.audit_licenses()
    typer.echo(json.dumps(result, indent=2))
    if result["status"] != "ok":
        raise typer.Exit(1)


@app.command("translate-unit")
def translate_unit(unit_id: str, layer: str, style_profile: str = "study_literal") -> None:
    job = generation_service.generate_for_unit(
        unit_id=unit_id, layer=layer, style_profile=style_profile
    )
    typer.echo(json.dumps(job, indent=2))


@app.command("translate-psalm")
def translate_psalm(psalm_id: str, layer: str, style_profile: str = "study_literal") -> None:
    jobs = generation_service.generate_for_psalm(
        psalm_id=psalm_id, layer=layer, style_profile=style_profile
    )
    typer.echo(json.dumps(jobs, indent=2))


@app.command("rerun-layer")
def rerun_layer(unit_id: str, layer: str) -> None:
    job = generation_service.rerun_layer(unit_id=unit_id, layer=layer)
    typer.echo(json.dumps(job, indent=2))


@app.command("list-alternates")
def list_alternates(unit_id: str) -> None:
    alternates = rendering_service.list_renderings(unit_id, alternates_only=True)
    typer.echo(json.dumps(alternates, indent=2))


@app.command("add-alternate")
def add_alternate(unit_id: str, layer: str, text: str, rationale: str) -> None:
    rendering = rendering_service.create_rendering(
        unit_id=unit_id,
        layer=layer,
        text=text,
        status="accepted_as_alternate",
        rationale=rationale,
        created_by="cli:add-alternate",
    )
    typer.echo(json.dumps(rendering, indent=2, ensure_ascii=False))


@app.command("promote-alternate")
def promote_alternate(rendering_id: str) -> None:
    rendering = rendering_service.promote_rendering(
        rendering_id, reviewer="cli", reviewer_role="release reviewer"
    )
    typer.echo(json.dumps(rendering, indent=2, ensure_ascii=False))


@app.command("demote-canonical")
def demote_canonical(rendering_id: str) -> None:
    rendering = rendering_service.demote_rendering(rendering_id)
    typer.echo(json.dumps(rendering, indent=2, ensure_ascii=False))


@app.command("link-issue")
def link_issue(unit_id: str, issue_number: int) -> None:
    result = github_link_service.link_issue(unit_id, issue_number)
    typer.echo(json.dumps(result, indent=2))


@app.command("link-pr")
def link_pr(unit_id: str, pr_number: int) -> None:
    result = github_link_service.link_pr(unit_id, pr_number)
    typer.echo(json.dumps(result, indent=2))


@app.command("generate-audit-report")
def generate_audit_report() -> None:
    report = report_service.generate_audit_reports()
    typer.echo(json.dumps(report, indent=2))


@app.command("generate-release-report")
def generate_release_report(release_id: str) -> None:
    report = report_service.generate_release_report(release_id)
    typer.echo(json.dumps(report, indent=2))


@app.command("export-book")
def export_book(psalm_id: str | None = None, output_dir: Path | None = None) -> None:
    destination = export_service.export_book(psalm_id=psalm_id, output_dir=output_dir)
    typer.echo(str(destination))


@app.command("export-release")
def export_release(release_id: str) -> None:
    destination = export_service.export_release(release_id)
    typer.echo(str(destination))


@app.command("rebuild-vector-index")
def rebuild_vector_index() -> None:
    typer.echo(json.dumps(visual_flow_service.rebuild_vector_index(), indent=2))


@app.command("greek-build-swete")
def greek_build_swete(psalter_repo: Path, commit: str = "HEAD", revision: str = "r0001") -> None:
    """Build the Swete 1896 package from a rahlfs1931-psalter commit and stage it."""
    from app.services import swete_package_service

    result = swete_package_service.build_and_stage(psalter_repo, commit=commit, revision=revision)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command("greek-approve-preview")
def greek_approve_preview(
    reviewer_id: str,
    rationale: str,
    package_id: str = "swete1896.text",
    revision: str = "r0001",
) -> None:
    """Owner approval to show a staged Greek package as an unreviewed display preview."""
    from app.services import greek_preview_service

    result = greek_preview_service.approve_preview(
        package_id, revision, reviewer_id=reviewer_id, rationale=rationale
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("greek-load-lexical-preview")
def greek_load_lexical_preview(reviewer_id: str, rationale: str) -> None:
    """Load pinned Greek dictionary meanings for local source review and hover cards."""
    from app.services import greek_lexical_preview_service

    result = greek_lexical_preview_service.enable(reviewer_id=reviewer_id, rationale=rationale)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@app.command("greek-audit-lookups")
def greek_audit_lookups(preview_only: bool = False) -> None:
    """Audit every pinned Greek corpus book; --preview-only limits to displayed text."""
    from app.services import greek_lexical_preview_service

    result = (
        greek_lexical_preview_service.audit_lookups()
        if preview_only
        else greek_lexical_preview_service.audit_corpus_lookups()
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("open-settings")
def open_settings() -> None:
    typer.echo(json.dumps(get_settings().as_dict(), indent=2))


if __name__ == "__main__":
    app()

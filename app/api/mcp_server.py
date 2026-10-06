"""The workbench as an MCP server, so an outside LLM can do what the UI does.

Each tool calls the API route the UI calls (or, where a route drops who acted, that route's
service), so it runs the same checks and writes the same audit records. Whatever the LLM
writes or approves is stamped ``mcp:<name>``. Served by the API at ``/mcp``.

Left out: the in-app assistant, speech transcription and the pinned lexical card (UI
only), Codex sign-in (a browser hand-off), and the raw overwrites that would change
canonical content or the review policy without the review service (``PATCH /units``,
``PATCH /project``, demoting a canonical rendering).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from fastapi import HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.api.routes import (
    alignments,
    alternates,
    arrangements,
    assistant,
    audit,
    codex,
    comparisons,
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
    translations,
    units,
    verse_notes,
)
from app.core.errors import ContentError
from app.services import (
    alignment_service,
    arrangement_service,
    registry_service,
    rendering_service,
)
from app.services import verse_notes_service as notes

INSTRUCTIONS = """\
AlephTav: translating the Hebrew Psalms into English with every word traceable to the Hebrew.

Ids: psalm ps001; unit (a verse) ps001.v001.a; Hebrew token ps001.v001.t001. Layers, most
literal first: gloss, literal, phrase, concept, lyric, metered_lyric, parallelism_lyric.

A psalm can have several translations. Its main one has translation_id null; others have ids
like tr.ps001.0001. A translation owns its English (renderings above literal), guidance,
assessments, psalm analysis, song settings and verse notes; the Hebrew, gloss and literal are
shared. Translations live in projects (list_projects); a project holds at most one
translation of a psalm. Pass translation_id to write into a translation other than the main.

Canonical is one rendering per unit and layer. Nothing is written canonical directly: add a
rendering, have it reviewed (review_rendering; two approvals for canonical), then
promote_rendering. Your created_by and reviewer names are recorded as mcp:<name>.

codex_* tools run Codex in the workbench and block until it answers. They need
codex_connect once and a session from create_codex_session.
"""

# The SDK configures root logging at this level; INFO would log every MCP request.
server = MCPServer("alephtav", instructions=INSTRUCTIONS, log_level="WARNING")

READ = ToolAnnotations(read_only_hint=True)

Layer = Literal[
    "gloss", "literal", "phrase", "concept", "lyric", "metered_lyric", "parallelism_lyric"
]
EnglishLayer = Literal["phrase", "concept", "lyric", "metered_lyric", "parallelism_lyric"]

# Route endpoints the tools cover, and those deliberately left out (see the module doc).
COVERED: set[Callable[..., Any]] = set()
EXCLUDED: set[Callable[..., Any]] = {
    assistant.list_tools,
    assistant.create_session,
    assistant.post_message,
    assistant.preview_action,
    assistant.execute_action,
    assistant.get_assistant_settings,
    assistant.patch_assistant_settings,
    speech.transcribe_audio,
    tokens.get_pinned_lexical_card,
    tokens.set_pinned_lexical_card,
    codex.codex_login,
    project.patch_project,
    units.patch_unit,
    renderings.demote_rendering,
}


def _tool(*routes: Callable[..., Any], read_only: bool = False) -> Callable[[Any], Any]:
    """Register a tool that does what ``routes`` do."""
    COVERED.update(routes)
    return server.tool(annotations=READ if read_only else None)


def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Run a route or service; a refusal reaches the LLM as the error it is.

    The result goes back as one compact JSON text: the SDK would otherwise split a list into
    a block per item and indent everything, which costs a psalm's worth of context twice.
    """
    try:
        result = fn(*args, **kwargs)
    except HTTPException as error:
        raise ToolError(str(error.detail)) from error
    except ContentError as error:
        raise ToolError(str(error)) from error
    return json.dumps(result, ensure_ascii=False, default=str)


def _mcp(name: str) -> str:
    """Who acted, marked as acting through the MCP: ``claude`` becomes ``mcp:claude``."""
    name = name.strip()
    if not name:
        return "mcp"
    return name if name.startswith("mcp:") else f"mcp:{name}"


def _payload(**fields: Any) -> dict[str, Any]:
    """A request body without the fields left unset, so the route's defaults apply."""
    return {key: value for key, value in fields.items() if value is not None}


# --- Corpus and psalms -------------------------------------------------------------------


@_tool(project.get_project, read_only=True)
def get_project() -> Any:
    """The workbench's project settings, including the review policy."""
    return _call(project.get_project)


@_tool(corpus.list_corpus_layers, read_only=True)
def list_layers() -> Any:
    """Every rendering layer used anywhere in the corpus."""
    return _call(corpus.list_corpus_layers)


@_tool(psalms.list_psalms, read_only=True)
def list_psalms() -> Any:
    """Every psalm: psalm_id, title and unit_count."""
    return _call(psalms.list_psalms)


@_tool(psalms.get_psalm, read_only=True)
def get_psalm(psalm_id: str) -> Any:
    """A psalm with all its units: Hebrew tokens, renderings, alignments. Large."""
    return _call(psalms.get_psalm, psalm_id)


@_tool(psalms.get_visual_flow, read_only=True)
def get_visual_flow(psalm_id: str) -> Any:
    """The psalm's flow of themes and images, as the workbench charts it."""
    return _call(psalms.get_visual_flow, psalm_id)


@_tool(psalms.get_cloud, read_only=True)
def get_word_cloud(psalm_id: str, scope: str = "selected_psalm", limit: int = 24) -> Any:
    """The psalm's most prominent words (limit 1–96)."""
    return _call(psalms.get_cloud, psalm_id, scope=scope, limit=limit)


@_tool(psalms.get_retrieval, read_only=True)
def get_retrieval(
    psalm_id: str,
    node_id: str,
    scope: str = "selected_psalm",
    include_cross_psalm: bool = True,
    limit: int = 12,
) -> Any:
    """Passages related to one node of the psalm's visual flow."""
    return _call(
        psalms.get_retrieval,
        psalm_id,
        node_id,
        scope=scope,
        include_cross_psalm=include_cross_psalm,
        limit=limit,
    )


@_tool(source_map.get_source_translation_map, read_only=True)
def get_source_map(
    psalm_id: str,
    layer: str = "literal",
    translation_source: str = "saved",
    rendering_status: str = "preferred",
    witness_source_id: str | None = None,
) -> Any:
    """How a layer's English maps onto the Hebrew, word by word, across the psalm."""
    return _call(
        source_map.get_source_translation_map,
        psalm_id,
        layer=layer,
        translation_source=translation_source,
        rendering_status=rendering_status,
        witness_source_id=witness_source_id,
    )


@_tool(units.get_unit, read_only=True)
def get_unit(unit_id: str) -> Any:
    """One unit (verse): Hebrew tokens, renderings, alignments, notes, review state."""
    return _call(units.get_unit, unit_id)


@_tool(units.get_unit_witnesses, read_only=True)
def list_witnesses(unit_id: str) -> Any:
    """Public-domain translations of the unit (KJV, ASV, WEB, ...)."""
    return _call(units.get_unit_witnesses, unit_id)


# --- Hebrew words and search -------------------------------------------------------------


@_tool(tokens.get_token, read_only=True)
def get_token(token_id: str) -> Any:
    """A Hebrew word's lexical card: lemma, morphology, Strong's, glosses."""
    return _call(tokens.get_token, token_id)


@_tool(tokens.get_token_occurrences, read_only=True)
def get_token_occurrences(token_id: str) -> Any:
    """Where else the word at this token occurs."""
    return _call(tokens.get_token_occurrences, token_id)


@_tool(tokens.get_lemma_occurrences, read_only=True)
def get_lemma_occurrences(lemma: str) -> Any:
    """Every occurrence of a Hebrew lemma."""
    return _call(tokens.get_lemma_occurrences, lemma)


@_tool(tokens.get_strong_occurrences, read_only=True)
def get_strong_occurrences(strong: str) -> Any:
    """Every occurrence of a Strong's number."""
    return _call(tokens.get_strong_occurrences, strong)


@_tool(comparisons.get_occurrence_context, read_only=True)
def get_occurrence_context(token_id: str, ref: str, english_layer: str = "lyric") -> Any:
    """How a word was rendered at another occurrence (ref), in context."""
    return _call(comparisons.get_occurrence_context, token_id, ref=ref, english_layer=english_layer)


@_tool(search.search_concordance, read_only=True)
def search_concordance(query: str, field: str = "lemma") -> Any:
    """Concordance search on one token field (lemma, strong, surface, ...)."""
    return _call(search.search_concordance, query=query, field=field)


@_tool(search.advanced_search, read_only=True)
def advanced_search(query: str, scope: str = "all", include_witnesses: bool = False) -> Any:
    """Search Hebrew, renderings and notes (and witnesses, if asked)."""
    return _call(
        search.advanced_search, query=query, scope=scope, include_witnesses=include_witnesses
    )


@_tool(search.preset_view, read_only=True)
def search_preset(name: str, release_id: str | None = None) -> Any:
    """A saved search view by name (e.g. units needing review)."""
    return _call(search.preset_view, name, release_id=release_id)


# --- Projects and translations -----------------------------------------------------------


@_tool(translations.list_collections, read_only=True)
def list_projects() -> Any:
    """Every project, the default one first, with the psalms it has a translation of."""
    return _call(translations.list_collections)


@_tool(translations.create_collection)
def create_project(title: str, created_by: str = "") -> Any:
    """Make a project (an album or songbook) to hold translations."""
    return _call(translations.create_collection, {"title": title, "created_by": _mcp(created_by)})


@_tool(translations.rename_collection)
def rename_project(collection_id: str, title: str) -> Any:
    """Rename a project. The built-in default project keeps its name."""
    return _call(translations.rename_collection, collection_id, {"title": title})


@_tool(translations.rename_collection)
def set_project_license(
    collection_id: str,
    output_text_license: Literal["CC0 1.0", "CC BY 4.0", "CC BY-SA 4.0", "All Rights Reserved"],
) -> Any:
    """Set the content license for the English text in one project."""
    return _call(
        translations.rename_collection,
        collection_id,
        {"output_text_license": output_text_license},
    )


@_tool(translations.list_translations, read_only=True)
def list_translations(psalm_id: str) -> Any:
    """The psalm's translations, its main one (translation_id null) first."""
    return _call(translations.list_translations, psalm_id)


@_tool(translations.create_translation)
def create_translation(
    psalm_id: str,
    title: str,
    collection_id: str,
    created_via: Literal["human", "import"] = "human",
    created_by: str = "",
) -> Any:
    """Start a translation of the psalm in a project that has none of it yet.

    created_via "import" marks one carrying an existing translation's text.
    """
    return _call(
        translations.create_translation,
        psalm_id,
        {
            "title": title,
            "collection_id": collection_id,
            "created_via": created_via,
            "created_by": _mcp(created_by),
        },
    )


@_tool(translations.move_translation)
def move_translation(
    psalm_id: str, translation_id: str | None, collection_id: str, created_by: str = ""
) -> Any:
    """Put a translation (null for the main one) in another project without that psalm."""
    return _call(
        translations.move_translation,
        psalm_id,
        {
            "translation_id": translation_id,
            "collection_id": collection_id,
            "created_by": _mcp(created_by),
        },
    )


@_tool(codex.get_translation_guidance, read_only=True)
def get_translation_guidance(psalm_id: str, translation_id: str | None = None) -> Any:
    """The translator's standing direction for one translation of the psalm."""
    return _call(codex.get_translation_guidance, psalm_id, translation_id=translation_id)


@_tool(codex.put_translation_guidance)
def set_translation_guidance(
    psalm_id: str, translation_guidance: str, translation_id: str | None = None
) -> Any:
    """Store the translator's standing direction for one translation of the psalm."""
    return _call(
        codex.put_translation_guidance,
        psalm_id,
        {"translation_guidance": translation_guidance, "translation_id": translation_id},
    )


@_tool(codex.get_psalm_analysis, read_only=True)
def get_psalm_analysis(psalm_id: str, translation_id: str | None = None) -> Any:
    """The translation's active psalm analysis, or null when none has been run."""
    return _call(codex.get_psalm_analysis, psalm_id, translation_id=translation_id)


@_tool(comparisons.get_comparison_table, read_only=True)
def get_comparison_table(
    psalm_id: str,
    translation_id: str | None = None,
    literal_layer: str = "literal",
    english_layer: str | None = None,
) -> Any:
    """The psalm verse by verse for one translation: Hebrew, literal, English, assessment."""
    return _call(
        comparisons.get_comparison_table,
        psalm_id,
        literal_layer=literal_layer,
        english_layer=english_layer,
        translation_id=translation_id,
    )


# --- Renderings, review, alignments ------------------------------------------------------


@_tool(renderings.get_renderings, alternates.list_alternates, read_only=True)
def list_renderings(
    unit_id: str,
    layer: str | None = None,
    alternates_only: bool = False,
    style_filter: str | None = None,
    basis_filter: str | None = None,
    release_approved_only: bool = False,
) -> Any:
    """A unit's renderings (each tagged with its translation_id), or only its alternates."""
    route = alternates.list_alternates if alternates_only else renderings.get_renderings
    return _call(
        route,
        unit_id,
        layer=layer,
        style_filter=style_filter,
        basis_filter=basis_filter,
        release_approved_only=release_approved_only,
    )


@_tool(renderings.compare_renderings, read_only=True)
def compare_renderings(unit_id: str, left_id: str, right_id: str) -> Any:
    """Two renderings of a unit side by side, with their differences."""
    return _call(renderings.compare_renderings, unit_id, left_id, right_id)


@_tool(renderings.create_rendering, alternates.create_alternate)
def create_rendering(
    unit_id: str,
    layer: Layer,
    text: str,
    rationale: str,
    translation_id: str | None = None,
    status: Literal["draft", "proposed", "under_review"] = "proposed",
    created_by: str = "",
    style_tags: list[str] | None = None,
    target_spans: list[dict[str, Any]] | None = None,
    alignment_ids: list[str] | None = None,
    drift_flags: list[Any] | None = None,
    metrics: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    translation_basis: dict[str, Any] | None = None,
    variation_basis: list[str] | None = None,
    preserved_source_images: list[dict[str, Any]] | None = None,
    differentiator: str | None = None,
    grounding_confidence: float | None = None,
    style_goal: str | None = None,
    metric_profile: str | None = None,
    issue_links: list[str] | None = None,
    pr_links: list[str] | None = None,
) -> Any:
    """Add a rendering of a unit at one layer, in a translation (null: the main one).

    It starts proposed; review_rendering and promote_rendering make it canonical.
    target_spans are {span_id, text, start, end} pieces of the text that alignments point at.
    """
    return _call(
        renderings.create_rendering,
        unit_id,
        _payload(
            layer=layer,
            text=text,
            rationale=rationale,
            translation_id=translation_id,
            status=status,
            created_by=_mcp(created_by),
            style_tags=style_tags,
            target_spans=target_spans,
            alignment_ids=alignment_ids,
            drift_flags=drift_flags,
            metrics=metrics,
            provenance=provenance,
            translation_basis=translation_basis,
            variation_basis=variation_basis,
            preserved_source_images=preserved_source_images,
            differentiator=differentiator,
            grounding_confidence=grounding_confidence,
            style_goal=style_goal,
            metric_profile=metric_profile,
            issue_links=issue_links,
            pr_links=pr_links,
        ),
    )


@_tool(renderings.patch_rendering)
def update_rendering(rendering_id: str, changes: dict[str, Any], created_by: str = "") -> Any:
    """Change fields of a rendering that is not canonical (text, style_tags, target_spans...).

    Status changes go through review_rendering, promote_rendering and deprecate_alternate; a
    canonical rendering changes only by promoting an alternate after review.
    """
    if "status" in changes:
        raise ToolError(
            "Status changes go through review_rendering, promote_rendering or deprecate_alternate"
        )
    try:
        unit = registry_service.load_unit(rendering_service._rendering_unit_id(rendering_id))
    except ContentError as error:
        raise ToolError(str(error)) from error
    current = next(
        (r for r in unit.get("renderings", []) if r["rendering_id"] == rendering_id), None
    )
    if current is None:
        raise ToolError(f"No rendering {rendering_id}")
    if current["status"] == "canonical":
        raise ToolError(
            "A canonical rendering changes only by review: add an alternate with "
            "create_rendering, then review and promote it"
        )
    return _call(rendering_service.update_rendering, rendering_id, changes, _mcp(created_by))


@_tool(alternates.deprecate_alternate)
def deprecate_alternate(rendering_id: str, rationale: str, created_by: str = "") -> Any:
    """Retire an alternate rendering."""
    return _call(
        alternates.deprecate_alternate,
        rendering_id,
        {"rationale": rationale, "created_by": _mcp(created_by)},
    )


_DECISIONS: dict[str, Callable[[str, dict[str, Any]], dict[str, Any]]] = {
    "approve": review.approve,
    "request_changes": review.request_changes,
    "accept-alternate": review.accept_alternate,
    "reject": review.reject,
}


@_tool(
    review.approve,
    review.request_changes,
    review.accept_alternate,
    review.reject,
    alternates.accept_alternate,
    alternates.reject_alternate,
)
def review_rendering(
    target_id: str,
    decision: Literal["approve", "request_changes", "accept-alternate", "reject"],
    reviewer: str,
    reviewer_role: str,
    notes: str = "",
) -> Any:
    """Record a review decision on a rendering, as reviewer mcp:<reviewer>.

    reviewer_role is one of the project's roles (get_project: review_policy.reviewer_roles),
    e.g. "lyric reviewer". Canonical needs two approvals from different reviewers.
    """
    return _call(
        _DECISIONS[decision],
        target_id,
        {"reviewer": _mcp(reviewer), "reviewer_role": reviewer_role, "notes": notes},
    )


@_tool(renderings.promote_rendering, alternates.promote_alternate)
def promote_rendering(rendering_id: str, reviewer: str, reviewer_role: str) -> Any:
    """Make a reviewed rendering canonical, as mcp:<reviewer>; needs the release role."""
    return _call(
        renderings.promote_rendering,
        rendering_id,
        {"reviewer": _mcp(reviewer), "reviewer_role": reviewer_role},
    )


@_tool(alignments.get_alignments, read_only=True)
def list_alignments(unit_id: str) -> Any:
    """A unit's alignments: which Hebrew tokens each rendering span renders."""
    return _call(alignments.get_alignments, unit_id)


@_tool(alignments.post_alignment)
def create_alignment(
    unit_id: str,
    layer: Layer,
    source_token_ids: list[str],
    target_span_ids: list[str],
    alignment_type: Literal[
        "direct",
        "grouped",
        "idiom",
        "conceptual",
        "editorial_expansion",
        "omission_accounted_for",
        "uncertain",
    ],
    confidence: float,
    notes: str = "",
    created_by: str = "",
) -> Any:
    """Link Hebrew tokens to target spans of a rendering at one layer (confidence 0–1)."""
    return _call(
        alignment_service.create_alignment,
        unit_id,
        {
            "layer": layer,
            "source_token_ids": source_token_ids,
            "target_span_ids": target_span_ids,
            "alignment_type": alignment_type,
            "confidence": confidence,
            "notes": notes,
        },
        created_by=_mcp(created_by),
    )


@_tool(alignments.patch_alignment)
def update_alignment(alignment_id: str, changes: dict[str, Any]) -> Any:
    """Change an alignment's tokens, spans, type, confidence or notes."""
    return _call(alignments.patch_alignment, alignment_id, changes)


@_tool(alignments.delete_alignment)
def delete_alignment(alignment_id: str) -> Any:
    """Remove an alignment."""
    return _call(alignments.delete_alignment, alignment_id)


# --- Assessments, verse notes, rebuilds --------------------------------------------------


@_tool(comparisons.list_comparison_assessments, read_only=True)
def list_comparison_assessments(
    psalm_id: str,
    status: str | None = None,
    accuracy_rating: str | None = None,
    reviewer_id: str | None = None,
    include_superseded: bool = False,
) -> Any:
    """The psalm's verse assessments: how each English line relates to the Hebrew."""
    return _call(
        comparisons.list_comparison_assessments,
        psalm_id,
        status=status,
        accuracy_rating=accuracy_rating,
        reviewer_id=reviewer_id,
        include_superseded=include_superseded,
    )


AccuracyRating = Literal[
    "literal", "very_close", "close", "adapted", "interpretive", "omission", "no_source_basis"
]


@_tool(comparisons.create_comparison_assessment)
def create_comparison_assessment(
    unit_id: str,
    accuracy_rating: AccuracyRating | None,
    accuracy_note: str,
    creative_liberties_note: str,
    rationale: str,
    translation_id: str | None = None,
    literal_rendering_id: str | None = None,
    english_rendering_id: str | None = None,
    status: Literal["draft", "proposed", "reviewed"] = "draft",
    display_reference: str | None = None,
    created_by: str = "",
) -> Any:
    """Assess how a verse's English relates to its Hebrew, for one translation."""
    return _call(
        comparisons.create_comparison_assessment,
        _payload(
            unit_id=unit_id,
            accuracy_rating=accuracy_rating,
            accuracy_note=accuracy_note,
            creative_liberties_note=creative_liberties_note,
            rationale=rationale,
            translation_id=translation_id,
            literal_rendering_id=literal_rendering_id,
            english_rendering_id=english_rendering_id,
            status=status,
            display_reference=display_reference,
            created_by=_mcp(created_by),
        ),
    )


@_tool(comparisons.revise_comparison_assessment)
def revise_comparison_assessment(
    comparison_id: str,
    unit_id: str,
    rationale: str,
    changes: dict[str, Any],
    reviewer_id: str | None = None,
    created_by: str = "",
) -> Any:
    """Revise an assessment. The original is superseded by a linked successor.

    changes may set accuracy_rating, accuracy_note, creative_liberties_note, status,
    literal_rendering_id, english_rendering_id and display_reference.
    """
    return _call(
        comparisons.revise_comparison_assessment,
        comparison_id,
        {
            **changes,
            **_payload(
                unit_id=unit_id,
                rationale=rationale,
                reviewer_id=reviewer_id and _mcp(reviewer_id),
                created_by=_mcp(created_by),
            ),
        },
    )


@_tool(verse_notes.add_verse_note)
def add_verse_note(
    unit_id: str,
    text: str,
    applies_to: Literal["literal", "english", "both"] = "english",
    kind: Literal["instruction", "comment"] = "instruction",
    quote: str | None = None,
    token_ids: list[str] | None = None,
    translation_id: str | None = None,
    created_by: str = "",
) -> Any:
    """Note on a verse; open instructions steer the next rebuild of that verse."""
    return _call(
        verse_notes.add_verse_note,
        unit_id,
        _payload(
            text=text,
            applies_to=applies_to,
            kind=kind,
            quote=quote,
            token_ids=token_ids,
            translation_id=translation_id,
            created_by=_mcp(created_by),
        ),
    )


@_tool(verse_notes.update_verse_note)
def update_verse_note(
    unit_id: str,
    note_id: str,
    text: str | None = None,
    applies_to: Literal["literal", "english", "both"] | None = None,
    kind: Literal["instruction", "comment"] | None = None,
    status: Literal["open", "addressed"] | None = None,
    created_by: str = "",
) -> Any:
    """Change a verse note's text, target, kind or status."""
    return _call(
        verse_notes.update_verse_note,
        unit_id,
        note_id,
        _payload(
            text=text,
            applies_to=applies_to,
            kind=kind,
            status=status,
            created_by=_mcp(created_by),
        ),
    )


@_tool(verse_notes.remove_verse_note)
def remove_verse_note(unit_id: str, note_id: str, created_by: str = "") -> Any:
    """Remove a verse note."""
    return _call(notes.remove_note, unit_id, note_id, created_by=_mcp(created_by))


@_tool(verse_notes.accept_rebuild)
def accept_rebuild(
    unit_id: str,
    rebuild_id: str,
    addressed_note_ids: list[str] | None = None,
    created_by: str = "",
) -> Any:
    """Accept a pending rebuild of a verse, marking the notes it addressed."""
    return _call(
        verse_notes.accept_rebuild,
        unit_id,
        rebuild_id,
        _payload(addressed_note_ids=addressed_note_ids, created_by=_mcp(created_by)),
    )


@_tool(verse_notes.discard_rebuild)
def discard_rebuild(unit_id: str, rebuild_id: str, created_by: str = "") -> Any:
    """Discard a pending rebuild of a verse."""
    return _call(verse_notes.discard_rebuild, unit_id, rebuild_id, {"created_by": _mcp(created_by)})


@_tool(verse_notes.get_verse_history, read_only=True)
def get_verse_history(unit_id: str) -> Any:
    """A verse's history: renderings, notes and rebuilds over time."""
    return _call(verse_notes.get_verse_history, unit_id)


@_tool(verse_notes.get_word_suggestions, read_only=True)
def get_word_suggestions(
    unit_id: str, token_ids: list[str], layer: str = "lyric", translation_id: str | None = None
) -> Any:
    """Suggestions already generated for a word; codex_suggest_words makes new ones."""
    return _call(
        verse_notes.get_word_suggestions,
        unit_id,
        token_ids=",".join(token_ids),
        layer=layer,
        translation_id=translation_id,
    )


# --- Song settings -----------------------------------------------------------------------

SectionKind = Literal["verse", "chorus", "refrain", "bridge", "intro", "outro", "other"]
Liberty = Literal["tracks", "compressed", "expanded", "reordered", "added"]


@_tool(arrangements.list_arrangements, read_only=True)
def list_song_settings(psalm_id: str, translation_id: str | None = None) -> Any:
    """A translation's song settings, with the refrains the Hebrew repeats."""
    return _call(arrangements.list_arrangements, psalm_id, translation_id=translation_id)


@_tool(arrangements.get_arrangement, read_only=True)
def get_song_setting(psalm_id: str, arrangement_id: str) -> Any:
    """One song setting with its sections, lines, anchors and approvals."""
    return _call(arrangements.get_arrangement, psalm_id, arrangement_id)


@_tool(arrangements.create_arrangement)
def create_song_setting(
    psalm_id: str,
    title: str,
    translation_id: str | None = None,
    layer: str = "lyric",
    sections: list[dict[str, Any]] | None = None,
    created_by: str = "",
) -> Any:
    """Make a song setting, empty or whole from section specs.

    A section spec: {key, kind, label, repeat_of (another spec's key or null), lines}; a
    line: {text, liberty, rationale, anchors: [{unit_id, token_ids}]} or bare token_ids.
    liberty is tracks, compressed, expanded, reordered or added (added has no anchors).
    """
    return _call(
        arrangements.create_arrangement,
        psalm_id,
        _payload(
            title=title,
            translation_id=translation_id,
            layer=layer,
            sections=sections,
            created_by=_mcp(created_by),
        ),
    )


@_tool(arrangements.update_arrangement)
def update_song_setting(
    psalm_id: str,
    arrangement_id: str,
    title: str | None = None,
    status: str | None = None,
    created_by: str = "",
) -> Any:
    """Rename a song setting or change its status."""
    return _call(
        arrangements.update_arrangement,
        psalm_id,
        arrangement_id,
        _payload(title=title, status=status, created_by=_mcp(created_by)),
    )


@_tool(arrangements.add_section)
def add_section(
    psalm_id: str,
    arrangement_id: str,
    label: str,
    kind: SectionKind = "verse",
    repeat_of: str | None = None,
    index: int | None = None,
    created_by: str = "",
) -> Any:
    """Add a section to a song setting; repeat_of names a section to sing again."""
    return _call(
        arrangements.add_section,
        psalm_id,
        arrangement_id,
        _payload(
            label=label, kind=kind, repeat_of=repeat_of, index=index, created_by=_mcp(created_by)
        ),
    )


@_tool(arrangements.update_section)
def update_section(
    psalm_id: str,
    arrangement_id: str,
    section_id: str,
    kind: SectionKind | None = None,
    label: str | None = None,
    index: int | None = None,
    created_by: str = "",
) -> Any:
    """Change a section's kind or label, or move it."""
    return _call(
        arrangements.update_section,
        psalm_id,
        arrangement_id,
        section_id,
        _payload(kind=kind, label=label, index=index, created_by=_mcp(created_by)),
    )


@_tool(arrangements.remove_section)
def remove_section(
    psalm_id: str, arrangement_id: str, section_id: str, created_by: str = ""
) -> Any:
    """Remove a section and its lines."""
    return _call(
        arrangement_service.remove_section,
        psalm_id,
        arrangement_id,
        section_id,
        created_by=_mcp(created_by),
    )


@_tool(arrangements.add_line)
def add_line(
    psalm_id: str,
    arrangement_id: str,
    section_id: str,
    text: str,
    anchors: list[dict[str, Any]] | None = None,
    liberty: Liberty = "tracks",
    rationale: str = "",
    index: int | None = None,
    created_by: str = "",
) -> Any:
    """Add a sung line; anchors [{unit_id, token_ids}] name the Hebrew it renders."""
    return _call(
        arrangements.add_line,
        psalm_id,
        arrangement_id,
        section_id,
        _payload(
            text=text,
            anchors=anchors,
            liberty=liberty,
            rationale=rationale,
            index=index,
            created_by=_mcp(created_by),
        ),
    )


@_tool(arrangements.update_line)
def update_line(
    psalm_id: str,
    arrangement_id: str,
    line_id: str,
    text: str | None = None,
    anchors: list[dict[str, Any]] | None = None,
    liberty: Liberty | None = None,
    rationale: str | None = None,
    index: int | None = None,
    created_by: str = "",
) -> Any:
    """Change a sung line's text, anchors, liberty or rationale, or move it."""
    return _call(
        arrangements.update_line,
        psalm_id,
        arrangement_id,
        line_id,
        _payload(
            text=text,
            anchors=anchors,
            liberty=liberty,
            rationale=rationale,
            index=index,
            created_by=_mcp(created_by),
        ),
    )


@_tool(arrangements.remove_line)
def remove_line(psalm_id: str, arrangement_id: str, line_id: str, created_by: str = "") -> Any:
    """Remove a sung line."""
    return _call(
        arrangement_service.remove_line,
        psalm_id,
        arrangement_id,
        line_id,
        created_by=_mcp(created_by),
    )


@_tool(arrangements.approve_line)
def approve_line(
    psalm_id: str,
    arrangement_id: str,
    line_id: str,
    reviewer: str,
    reviewer_role: str,
    note: str = "",
) -> Any:
    """Approve a line's declared liberty, as reviewer mcp:<reviewer>."""
    return _call(
        arrangements.approve_line,
        psalm_id,
        arrangement_id,
        line_id,
        {"reviewer": _mcp(reviewer), "reviewer_role": reviewer_role, "note": note},
    )


@_tool(arrangements.approve_omission)
def approve_omission(
    psalm_id: str,
    arrangement_id: str,
    unit_id: str,
    token_ids: list[str],
    reviewer: str,
    reviewer_role: str,
    rationale: str,
    note: str = "",
) -> Any:
    """Approve leaving Hebrew words unsung, as reviewer mcp:<reviewer>."""
    return _call(
        arrangements.approve_omission,
        psalm_id,
        arrangement_id,
        {
            "unit_id": unit_id,
            "token_ids": token_ids,
            "reviewer": _mcp(reviewer),
            "reviewer_role": reviewer_role,
            "rationale": rationale,
            "note": note,
        },
    )


# --- Audit, reports, export, local generation -------------------------------------------


@_tool(audit.get_unit_audit, read_only=True)
def get_unit_audit(unit_id: str) -> Any:
    """Every audit record for a unit."""
    return _call(audit.get_unit_audit, unit_id)


@_tool(audit.get_open_concerns, read_only=True)
def get_open_concerns() -> Any:
    """Open concerns across the corpus: drift flags, unaligned spans, pending reviews."""
    return _call(audit.get_open_concerns)


@_tool(audit.get_release_audit)
def generate_release_report(release_id: str) -> Any:
    """Build (and write) the release report for a release id."""
    return _call(audit.get_release_audit, release_id)


@_tool(export.export_book)
def export_book(psalm_id: str | None = None) -> Any:
    """Export the book (or one psalm); returns the written path."""
    return _call(export.export_book, _payload(psalm_id=psalm_id))


@_tool(export.export_release)
def export_release(release_id: str) -> Any:
    """Export a release bundle; returns the written path."""
    return _call(export.export_release, {"release_id": release_id})


@_tool(jobs.generate_job)
def generate_with_local_model(
    unit_id: str,
    layer: Layer,
    style_profile: str = "study_literal",
    model_profile: str | None = None,
    seed: int = 42,
    candidate_count: int = 1,
) -> Any:
    """Generate rendering candidates with the workbench's local model; returns a job."""
    return _call(
        jobs.generate_job,
        _payload(
            unit_id=unit_id,
            layer=layer,
            style_profile=style_profile,
            model_profile=model_profile,
            seed=seed,
            candidate_count=candidate_count,
        ),
    )


@_tool(jobs.get_job, read_only=True)
def get_job(job_id: str) -> Any:
    """A local-model generation job and its candidates."""
    return _call(jobs.get_job, job_id)


@_tool(jobs.retry_job)
def retry_job(
    job_id: str,
    style_profile: str = "study_literal",
    model_profile: str | None = None,
    seed: int | None = None,
    candidate_count: int = 1,
) -> Any:
    """Run a local-model generation job again."""
    return _call(
        jobs.retry_job,
        job_id,
        _payload(
            style_profile=style_profile,
            model_profile=model_profile,
            seed=seed,
            candidate_count=candidate_count,
        ),
    )


@_tool(units.post_composer_suggestions)
def composer_suggestions(
    unit_id: str,
    stage: str,
    chunks: list[Any],
    candidate_count: int = 3,
    model_profile: str | None = None,
    style_profile: str | None = None,
    basis_filter: str | None = None,
) -> Any:
    """Ask the local model for phrasing suggestions for a verse being composed."""
    return _call(
        units.post_composer_suggestions,
        unit_id,
        _payload(
            stage=stage,
            chunks=chunks,
            candidate_count=candidate_count,
            model_profile=model_profile,
            style_profile=style_profile,
            basis_filter=basis_filter,
        ),
    )


# --- Codex -------------------------------------------------------------------------------


@_tool(codex.codex_status, read_only=True)
def codex_status() -> Any:
    """Whether Codex is connected and signed in."""
    return _call(codex.codex_status)


@_tool(codex.codex_connect)
def codex_connect() -> Any:
    """Start or reconnect the workbench's Codex app server."""
    return _call(codex.codex_connect)


@_tool(codex.codex_models, read_only=True)
def codex_models() -> Any:
    """Models Codex offers, with their reasoning efforts."""
    return _call(codex.codex_models)


@_tool(codex.list_codex_sessions, read_only=True)
def list_codex_sessions(psalm_id: str | None = None) -> Any:
    """Codex sessions, optionally for one psalm."""
    return _call(codex.list_codex_sessions, psalm_id)


@_tool(codex.create_codex_session)
def create_codex_session(
    psalm_id: str,
    translation_id: str | None = None,
    unit_id: str | None = None,
    layer: str = "literal",
    model: str = "",
    purpose: str = "translation",
    base_instructions: str | None = None,
) -> Any:
    """Open a Codex session tied to one translation of a psalm; other codex_* tools use it."""
    return _call(
        codex.create_codex_session,
        _payload(
            psalm_id=psalm_id,
            translation_id=translation_id,
            unit_id=unit_id,
            layer=layer,
            model=model,
            purpose=purpose,
            base_instructions=base_instructions,
        ),
    )


@_tool(codex.resume_codex_session)
def resume_codex_session(session_id: str) -> Any:
    """Reopen an earlier Codex session."""
    return _call(codex.resume_codex_session, session_id)


@_tool(codex.interrupt_codex_session)
def interrupt_codex_session(session_id: str) -> Any:
    """Stop the turn a Codex session is running."""
    return _call(codex.interrupt_codex_session, session_id)


@_tool(codex.start_codex_turn)
def codex_translation_turn(
    session_id: str,
    unit_id: str,
    layer: Layer,
    candidate_count: int = 2,
    style_profile: str | None = None,
    meter_target: str | None = None,
    constraints: list[str] | None = None,
) -> Any:
    """Ask Codex for candidate renderings of a unit; save_codex_candidates keeps them."""
    return _call(
        codex.start_codex_turn,
        session_id,
        _payload(
            unit_id=unit_id,
            layer=layer,
            candidate_count=candidate_count,
            style_profile=style_profile,
            meter_target=meter_target,
            constraints=constraints,
        ),
    )


@_tool(codex.fill_comparison_row)
def codex_fill_verse(
    session_id: str,
    unit_id: str,
    english_layer: EnglishLayer = "lyric",
    style_profile: str | None = None,
    meter_target: str | None = None,
    constraints: list[str] | None = None,
) -> Any:
    """Have Codex write a verse's literal, English and assessment into the session's translation."""
    return _call(
        codex.fill_comparison_row,
        unit_id,
        _payload(
            session_id=session_id,
            english_layer=english_layer,
            style_profile=style_profile,
            meter_target=meter_target,
            constraints=constraints,
        ),
    )


@_tool(codex.fill_psalm_passage)
def codex_fill_passage(
    session_id: str,
    psalm_id: str,
    unit_ids: list[str],
    english_layer: EnglishLayer = "lyric",
    style_profile: str | None = None,
    meter_target: str | None = None,
    constraints: list[str] | None = None,
) -> Any:
    """Have Codex write literal and English for several verses as one passage."""
    return _call(
        codex.fill_psalm_passage,
        psalm_id,
        _payload(
            session_id=session_id,
            unit_ids=unit_ids,
            english_layer=english_layer,
            style_profile=style_profile,
            meter_target=meter_target,
            constraints=constraints,
        ),
    )


@_tool(codex.analyze_verse)
def codex_analyse_verse(
    session_id: str, unit_id: str, english_layer: EnglishLayer = "lyric", force: bool = False
) -> Any:
    """Have Codex assess a verse's renderings against the Hebrew."""
    return _call(
        codex.analyze_verse,
        unit_id,
        {"session_id": session_id, "english_layer": english_layer, "force": force},
    )


@_tool(codex.analyze_psalm)
def codex_analyse_psalm(
    session_id: str, psalm_id: str, english_layer: EnglishLayer = "lyric", force: bool = False
) -> Any:
    """Have Codex analyse the psalm as a whole: sections, seams, guardrails, epistemics."""
    return _call(
        codex.analyze_psalm,
        psalm_id,
        {"session_id": session_id, "english_layer": english_layer, "force": force},
    )


@_tool(codex.rebuild_verse)
def codex_rebuild_verse(
    session_id: str,
    unit_id: str,
    english_layer: EnglishLayer = "lyric",
    layers: list[str] | None = None,
) -> Any:
    """Have Codex retranslate a verse with its open notes; held until accept_rebuild."""
    return _call(
        codex.rebuild_verse,
        unit_id,
        _payload(session_id=session_id, english_layer=english_layer, layers=layers),
    )


@_tool(codex.analyse_rebuild)
def codex_analyse_rebuild(session_id: str, unit_id: str) -> Any:
    """Have Codex assess a pending rebuild, blind to the notes that produced it."""
    return _call(codex.analyse_rebuild, unit_id, {"session_id": session_id})


@_tool(codex.suggest_word_renderings)
def codex_suggest_words(
    session_id: str, unit_id: str, token_ids: list[str], layer: str = "lyric"
) -> Any:
    """Have Codex rank at least three renderings for a word or phrase."""
    return _call(
        codex.suggest_word_renderings,
        unit_id,
        {"session_id": session_id, "token_ids": token_ids, "layer": layer},
    )


@_tool(codex.identify_psalm)
def codex_identify_psalm(text: str) -> Any:
    """Ask Codex which psalm a pasted translation translates (Masoretic numbering)."""
    return _call(codex.identify_psalm, {"text": text})


@_tool(codex.import_translation)
def codex_import_translation(
    session_id: str, psalm_id: str, text: str, layer: str = "lyric"
) -> Any:
    """Have Codex place a pasted translation into the session's translation, verse by verse."""
    return _call(
        codex.import_translation,
        psalm_id,
        {"session_id": session_id, "text": text, "layer": layer},
    )


@_tool(arrangements.arrange_import)
def codex_import_song_setting(
    session_id: str, psalm_id: str, text: str, layer: str = "lyric"
) -> Any:
    """Have Codex read a pasted translation as a song setting, its lines kept as pasted."""
    return _call(
        arrangements.arrange_import,
        psalm_id,
        {"session_id": session_id, "text": text, "layer": layer},
    )


@_tool(arrangements.draft_arrangement)
def codex_draft_song_setting(session_id: str, psalm_id: str, layer: str = "lyric") -> Any:
    """Have Codex draft a whole-psalm song setting, stored as a proposal."""
    return _call(
        arrangements.draft_arrangement, psalm_id, {"session_id": session_id, "layer": layer}
    )


@_tool(codex.codex_run_events, read_only=True)
def get_codex_run(run_id: str) -> Any:
    """A Codex run's status and event log, kept even when it failed."""
    return _call(codex.codex_run_events, run_id)


@_tool(codex.cancel_codex_run)
def cancel_codex_run(run_id: str) -> Any:
    """Cancel a Codex run."""
    return _call(codex.cancel_codex_run, run_id)


@_tool(codex.save_codex_candidates)
def save_codex_candidates(run_id: str) -> Any:
    """Save a validated run's candidates as proposed renderings."""
    return _call(codex.save_codex_candidates, run_id)

import sys
from unittest.mock import MagicMock

import pytest


# Keep tests import-safe outside Anki.
mock_aqt = MagicMock()
sys.modules.setdefault("aqt", mock_aqt)
sys.modules.setdefault("aqt.qt", mock_aqt.qt)
sys.modules.setdefault("aqt.gui_hooks", mock_aqt.gui_hooks)


from run_options import (  # noqa: E402
    AmbiguousMatchPolicy,
    RunOptions,
    SchedulingWritePolicy,
    TranslationAggregationPolicy,
    dict_to_run_options,
    run_options_to_dict,
    validate_run_options,
)

from config_model import AnkiToLingqMapping, IdentityFields, LingqToAnkiMapping, Profile  # noqa: E402
from diff_engine import compute_sync_plan  # noqa: E402


def _make_profile(*, enable_scheduling_writes: bool = False) -> Profile:
    profile = Profile(
        name="test",
        lingq_language="en",
        meaning_locale="en",
        api_token_ref="test",
        lingq_to_anki=LingqToAnkiMapping(
            note_type="Basic",
            field_mapping={"term": "Front", "translation": "Back"},
            identity_fields=IdentityFields(
                pk_field="LingQ_PK", canonical_term_field="LingQ_TermCanonical"
            ),
        ),
        anki_to_lingq=AnkiToLingqMapping(
            term_field="Front", translation_fields=["Back"], fragment_field=None
        ),
        enable_scheduling_writes=enable_scheduling_writes,
    )
    # Deterministic, in-memory LSS (avoids store-backed fallback).
    setattr(profile, "lss", {})
    return profile


def _all_policies(
    *,
    ambiguous: AmbiguousMatchPolicy,
    aggregation: TranslationAggregationPolicy,
    scheduling: SchedulingWritePolicy,
) -> RunOptions:
    return RunOptions(
        ambiguous_match_policy=ambiguous,
        translation_aggregation_policy=aggregation,
        scheduling_write_policy=scheduling,
    )


def test_validate_run_options_requires_explicit_policies():
    errs = validate_run_options(RunOptions())

    assert len(errs) == 3
    assert any("Ambiguous match policy" in e for e in errs)
    assert any("Translation aggregation policy" in e for e in errs)
    assert any("Scheduling write policy" in e for e in errs)


def test_run_options_to_dict_round_trip_preserves_values():
    opts = RunOptions(
        ambiguous_match_policy=AmbiguousMatchPolicy.AGGRESSIVE_LINK_FIRST,
        translation_aggregation_policy=TranslationAggregationPolicy.AVG,
        scheduling_write_policy=SchedulingWritePolicy.FORCE_ON,
    )

    raw = run_options_to_dict(opts)
    parsed = dict_to_run_options(raw)

    assert parsed == opts


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("ASK", AmbiguousMatchPolicy.ASK),
        ("SKIP", AmbiguousMatchPolicy.SKIP),
        ("not-a-policy", AmbiguousMatchPolicy.UNSET),
        (None, AmbiguousMatchPolicy.UNSET),
    ],
)
def test_dict_to_run_options_parses_strings_and_falls_back(raw_value, expected):
    opts = dict_to_run_options({"ambiguous_match_policy": raw_value})
    assert opts.ambiguous_match_policy == expected


@pytest.mark.parametrize(
    "amb_policy, expected_op_type",
    [
        (AmbiguousMatchPolicy.ASK, "conflict"),
        (AmbiguousMatchPolicy.SKIP, "skip"),
        (AmbiguousMatchPolicy.AGGRESSIVE_LINK_FIRST, "link"),
    ],
)
def test_compute_sync_plan_ambiguous_match_policy_changes_outcome(
    amb_policy, expected_op_type
):
    profile = _make_profile(enable_scheduling_writes=False)
    opts = _all_policies(
        ambiguous=amb_policy,
        aggregation=TranslationAggregationPolicy.MAX,
        scheduling=SchedulingWritePolicy.INHERIT_PROFILE,
    )

    anki_notes = [{"note_id": 1, "fields": {"Front": "hello", "Back": "hola"}}]
    lingq_cards = [
        {
            "pk": 1,
            "term": "hello",
            "status": 0,
            "hints": [{"locale": "en", "text": "hola"}],
        },
        {
            "pk": 2,
            "term": "hello",
            "status": 0,
            "hints": [{"locale": "en", "text": "hola"}],
        },
    ]

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    if expected_op_type == "conflict":
        conflicts = plan.get_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].details.get("conflict_type") == "ambiguous_lingq_match"
    elif expected_op_type == "skip":
        assert any(
            (op.op_type == "skip")
            and (op.anki_note_id == 1)
            and (op.lingq_pk is None)
            and (op.details.get("reason") == "ambiguous_match_policy_skip")
            for op in plan.operations
        )
        assert plan.get_conflicts() == []
    else:
        assert any(
            (op.op_type == "link") and (op.anki_note_id == 1) and (op.lingq_pk == 1)
            for op in plan.operations
        )
        assert plan.get_conflicts() == []


def test_compute_sync_plan_anki_polysemy_conflict_includes_translations_when_ask():
    profile = _make_profile(enable_scheduling_writes=False)
    opts = _all_policies(
        ambiguous=AmbiguousMatchPolicy.SKIP,
        aggregation=TranslationAggregationPolicy.ASK,
        scheduling=SchedulingWritePolicy.INHERIT_PROFILE,
    )

    anki_notes = [
        {
            "note_id": 1,
            "fields": {"Front": "poly", "Back": "bbb\naaa\nccc"},
        }
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "poly",
            "status": 0,
            "hints": [{"locale": "en", "text": "aaa"}],
        }
    ]

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    conflicts = plan.get_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].details.get("conflict_type") == "anki_polysemy_needs_policy"
    assert conflicts[0].details.get("translations") == ["aaa", "bbb", "ccc"]


def test_compute_sync_plan_anki_polysemy_skip_when_policy_skip():
    profile = _make_profile(enable_scheduling_writes=False)
    opts = _all_policies(
        ambiguous=AmbiguousMatchPolicy.SKIP,
        aggregation=TranslationAggregationPolicy.SKIP,
        scheduling=SchedulingWritePolicy.INHERIT_PROFILE,
    )

    anki_notes = [
        {
            "note_id": 1,
            "fields": {"Front": "poly", "Back": "bbb\naaa\nccc"},
        }
    ]
    lingq_cards = []

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    assert any(
        (op.op_type == "skip")
        and (op.anki_note_id == 1)
        and (op.lingq_pk is None)
        and (op.details.get("reason") == "translation_aggregation_policy_skip")
        for op in plan.operations
    )
    assert plan.get_conflicts() == []


@pytest.mark.parametrize(
    "agg_policy, expected_pk",
    [
        (TranslationAggregationPolicy.MIN, 1),
        (TranslationAggregationPolicy.AVG, 2),
        (TranslationAggregationPolicy.MAX, 3),
    ],
)
def test_compute_sync_plan_translation_aggregation_deterministically_picks_card(
    agg_policy, expected_pk
):
    profile = _make_profile(enable_scheduling_writes=False)
    opts = _all_policies(
        ambiguous=AmbiguousMatchPolicy.SKIP,
        aggregation=agg_policy,
        scheduling=SchedulingWritePolicy.INHERIT_PROFILE,
    )

    anki_notes = [
        {
            "note_id": 1,
            "fields": {"Front": "poly", "Back": "bbb\naaa\nccc"},
        }
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "poly",
            "status": 0,
            "hints": [{"locale": "en", "text": "aaa"}],
        },
        {
            "pk": 2,
            "term": "poly",
            "status": 0,
            "hints": [{"locale": "en", "text": "bbb"}],
        },
        {
            "pk": 3,
            "term": "poly",
            "status": 0,
            "hints": [{"locale": "en", "text": "ccc"}],
        },
    ]

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    assert any(
        (op.op_type == "link")
        and (op.anki_note_id == 1)
        and (op.lingq_pk == expected_pk)
        for op in plan.operations
    )


def test_compute_sync_plan_scheduling_write_force_off_emits_skip_even_if_enabled_in_profile():
    profile = _make_profile(enable_scheduling_writes=True)
    opts = _all_policies(
        ambiguous=AmbiguousMatchPolicy.SKIP,
        aggregation=TranslationAggregationPolicy.MAX,
        scheduling=SchedulingWritePolicy.FORCE_OFF,
    )

    anki_notes = [
        {
            "note_id": 1,
            "fields": {"LingQ_PK": "1", "Front": "sched", "Back": "hola"},
        }
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "sched",
            "status": 1,
            "hints": [{"locale": "en", "text": "hola"}],
        }
    ]

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    assert any(
        (op.op_type == "skip")
        and (op.anki_note_id == 1)
        and (op.lingq_pk == 1)
        and (op.details.get("reason") == "scheduling_writes_disabled")
        for op in plan.operations
    )
    assert all(op.op_type != "reschedule_anki" for op in plan.operations)


def test_compute_sync_plan_scheduling_write_force_on_allows_reschedule():
    profile = _make_profile(enable_scheduling_writes=False)
    opts = _all_policies(
        ambiguous=AmbiguousMatchPolicy.SKIP,
        aggregation=TranslationAggregationPolicy.MAX,
        scheduling=SchedulingWritePolicy.FORCE_ON,
    )

    anki_notes = [
        {
            "note_id": 1,
            "fields": {"LingQ_PK": "1", "Front": "sched", "Back": "hola"},
        }
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "sched",
            "status": 1,
            "hints": [{"locale": "en", "text": "hola"}],
        }
    ]

    plan = compute_sync_plan(
        anki_notes, lingq_cards, profile, profile.meaning_locale, run_options=opts
    )

    assert any(
        (op.op_type == "reschedule_anki")
        and (op.anki_note_id == 1)
        and (op.lingq_pk == 1)
        for op in plan.operations
    )
    assert all(
        not (
            (op.op_type == "skip")
            and (op.anki_note_id == 1)
            and (op.lingq_pk == 1)
            and (op.details.get("reason") == "scheduling_writes_disabled")
        )
        for op in plan.operations
    )

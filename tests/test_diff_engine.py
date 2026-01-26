import sys
from unittest.mock import MagicMock


# Keep tests import-safe outside Anki.
mock_aqt = MagicMock()
sys.modules.setdefault("aqt", mock_aqt)
sys.modules.setdefault("aqt.qt", mock_aqt.qt)
sys.modules.setdefault("aqt.gui_hooks", mock_aqt.gui_hooks)


from config_model import AnkiToLingqMapping, IdentityFields, LingqToAnkiMapping, Profile
from diff_engine import compute_sync_plan


def _make_profile() -> Profile:
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
            term_field="Front", translation_fields=["Back"]
        ),
        enable_scheduling_writes=False,
    )
    # Deterministic, in-memory LSS (avoids store-backed fallback).
    setattr(profile, "lss", {})
    return profile


def _fixture_inputs():
    anki_notes = [
        {
            "note_id": 10,
            "fields": {"LingQ_PK": "1", "Front": "hello", "Back": "hola"},
        },
        {"note_id": 20, "fields": {"Front": "world", "Back": "mundo"}},
        {"note_id": 30, "fields": {"Front": "cat", "Back": "gato"}},
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "hello",
            "status": 0,
            "hints": [{"locale": "en", "text": "hola"}],
        },
        {
            "pk": 2,
            "term": "world",
            "status": 0,
            "hints": [{"locale": "en", "text": "mundo"}],
        },
        {
            "pk": 3,
            "term": "dog",
            "status": 0,
            "hints": [{"locale": "en", "text": "perro"}],
        },
    ]
    return anki_notes, lingq_cards


def test_compute_sync_plan_deterministic_same_inputs_count_by_type():
    profile = _make_profile()
    anki_notes, lingq_cards = _fixture_inputs()

    plan1 = compute_sync_plan(anki_notes, lingq_cards, profile, profile.meaning_locale)
    plan2 = compute_sync_plan(anki_notes, lingq_cards, profile, profile.meaning_locale)

    assert plan1.count_by_type() == plan2.count_by_type()


def test_compute_sync_plan_deterministic_with_shuffled_input_order_count_by_type():
    profile = _make_profile()
    anki_notes, lingq_cards = _fixture_inputs()

    plan1 = compute_sync_plan(anki_notes, lingq_cards, profile, profile.meaning_locale)
    plan2 = compute_sync_plan(
        list(reversed(anki_notes)),
        list(reversed(lingq_cards)),
        profile,
        profile.meaning_locale,
    )

    assert plan1.count_by_type() == plan2.count_by_type()


def test_compute_sync_plan_empty_inputs_produces_empty_plan():
    profile = _make_profile()

    plan = compute_sync_plan([], [], profile, profile.meaning_locale)

    assert plan.operations == []
    assert plan.count_by_type() == {}


def test_compute_sync_plan_duplicate_pk_conflict():
    profile = _make_profile()

    anki_notes = [
        {
            "note_id": 10,
            "fields": {"LingQ_PK": "1", "Front": "hello", "Back": "hola"},
        },
        {
            "note_id": 20,
            "fields": {"LingQ_PK": "1", "Front": "hello2", "Back": "hola2"},
        },
    ]
    lingq_cards = [
        {
            "pk": 1,
            "term": "hello",
            "status": 0,
            "hints": [{"locale": "en", "text": "hola"}],
        }
    ]

    plan = compute_sync_plan(anki_notes, lingq_cards, profile, profile.meaning_locale)

    conflicts = plan.get_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].details.get("conflict_type") == "duplicate_pk"


def test_compute_sync_plan_pk_priority_over_term():
    profile = _make_profile()

    anki_notes = [
        {
            "note_id": 10,
            "fields": {"LingQ_PK": "1", "Front": "hello", "Back": "hola"},
        }
    ]
    lingq_cards = [
        # Same PK but term doesn't match the Anki term.
        {
            "pk": 1,
            "term": "different",
            "status": 0,
            "hints": [{"locale": "en", "text": "something else"}],
        },
        # Term+translation would match this card if PK were ignored.
        {
            "pk": 999,
            "term": "hello",
            "status": 0,
            "hints": [{"locale": "en", "text": "hola"}],
        },
    ]

    plan = compute_sync_plan(anki_notes, lingq_cards, profile, profile.meaning_locale)

    assert plan.get_conflicts() == []
    assert all(op.op_type != "link" for op in plan.operations)
    assert any(
        (op.op_type == "skip")
        and (op.anki_note_id == 10)
        and (op.lingq_pk == 1)
        and (op.details.get("reason") == "scheduling_writes_disabled")
        for op in plan.operations
    )

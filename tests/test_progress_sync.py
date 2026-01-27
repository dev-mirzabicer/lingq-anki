import sys
from unittest.mock import MagicMock

mock_aqt = MagicMock()
sys.modules["aqt"] = mock_aqt
sys.modules["aqt.qt"] = mock_aqt.qt
sys.modules["aqt.gui_hooks"] = mock_aqt.gui_hooks

from progress_sync import (
    lingq_status_to_tier,
    has_polysemy,
    count_hints_in_locale,
    compare_progress,
)


def test_lingq_status_to_tier_new():
    assert lingq_status_to_tier(0) == "new"


def test_lingq_status_to_tier_learning():
    assert lingq_status_to_tier(1) == "learning"
    assert lingq_status_to_tier(2) == "learning"


def test_lingq_status_to_tier_learned():
    assert lingq_status_to_tier(3) == "learned"


def test_lingq_status_to_tier_known():
    assert lingq_status_to_tier(4) == "known"


def test_lingq_status_to_tier_legacy_known():
    assert lingq_status_to_tier(3, extended_status=3) == "known"


def test_has_polysemy_single_hint():
    hints = [{"locale": "en", "text": "dog"}]
    assert has_polysemy(hints, "en") is False


def test_has_polysemy_multiple_hints():
    hints = [
        {"locale": "en", "text": "dog"},
        {"locale": "en", "text": "hound"},
    ]
    assert has_polysemy(hints, "en") is True


def test_has_polysemy_different_locales():
    hints = [
        {"locale": "en", "text": "dog"},
        {"locale": "sv", "text": "hund"},
    ]
    assert has_polysemy(hints, "en") is False


def test_count_hints_in_locale():
    hints = [
        {"locale": "en", "text": "dog"},
        {"locale": "en", "text": "hound"},
        {"locale": "sv", "text": "hund"},
    ]
    assert count_hints_in_locale(hints, "en") == 2
    assert count_hints_in_locale(hints, "sv") == 1
    assert count_hints_in_locale(hints, "de") == 0


def test_compare_progress_scheduling_disabled():
    result = compare_progress(
        lingq_status=2,
        lingq_hints=[{"locale": "en", "text": "test"}],
        meaning_locale="en",
        anki_has_reviews=True,
        enable_scheduling_writes=False,
        progress_authority_policy="AUTOMATIC",
    )
    assert result.should_sync_to_lingq is False
    assert result.should_sync_to_anki is False
    assert result.reason == "scheduling_writes_disabled"


def test_compare_progress_anki_leads():
    result = compare_progress(
        lingq_status=0,
        lingq_hints=[],
        meaning_locale="en",
        anki_has_reviews=True,
        enable_scheduling_writes=True,
        progress_authority_policy="AUTOMATIC",
    )
    assert result.should_sync_to_lingq is True
    assert result.should_sync_to_anki is False


def test_compare_progress_polysemy_blocks():
    hints = [
        {"locale": "en", "text": "dog"},
        {"locale": "en", "text": "hound"},
    ]
    result = compare_progress(
        lingq_status=2,
        lingq_hints=hints,
        meaning_locale="en",
        anki_has_reviews=False,
        enable_scheduling_writes=True,
        progress_authority_policy="AUTOMATIC",
    )
    assert result.should_sync_to_anki is False
    assert "polysemy" in result.reason


def test_compare_progress_prefer_anki_forces_anki_to_lingq_when_reviewed():
    result = compare_progress(
        lingq_status=3,
        lingq_hints=[],
        meaning_locale="en",
        anki_has_reviews=True,
        enable_scheduling_writes=True,
        progress_authority_policy="PREFER_ANKI",
    )
    assert result.should_sync_to_lingq is True
    assert result.should_sync_to_anki is False
    assert "anki_priority" in result.reason

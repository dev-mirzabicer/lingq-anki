import sys
from unittest.mock import MagicMock

mock_aqt = MagicMock()
sys.modules["aqt"] = mock_aqt
sys.modules["aqt.qt"] = mock_aqt.qt
sys.modules["aqt.gui_hooks"] = mock_aqt.gui_hooks

from hint_reconciliation import (
    normalize_hint_text,
    find_missing_hints,
    build_hints_payload,
    deduplicate_hints,
)


def test_normalize_hint_text():
    assert normalize_hint_text("Hello") == "hello"
    assert normalize_hint_text("  DOG  ") == "dog"


def test_find_missing_hints_all_present():
    anki_translations = ["dog"]
    lingq_hints = [{"locale": "en", "text": "Dog"}]
    missing = find_missing_hints(anki_translations, lingq_hints, "en")
    assert missing == []


def test_find_missing_hints_one_missing():
    anki_translations = ["dog", "hound"]
    lingq_hints = [{"locale": "en", "text": "Dog"}]
    missing = find_missing_hints(anki_translations, lingq_hints, "en")
    assert len(missing) == 1
    assert "hound" in missing


def test_find_missing_hints_wrong_locale():
    anki_translations = ["dog"]
    lingq_hints = [{"locale": "sv", "text": "dog"}]
    missing = find_missing_hints(anki_translations, lingq_hints, "en")
    assert "dog" in missing


def test_build_hints_payload_adds_new():
    existing = [{"locale": "en", "text": "Dog"}]
    new_translations = ["hound"]
    result = build_hints_payload(existing, new_translations, "en")
    texts = [h["text"] for h in result]
    assert "Dog" in texts
    assert "hound" in texts


def test_build_hints_payload_sorted():
    existing = [{"locale": "en", "text": "zebra"}]
    new_translations = ["apple"]
    result = build_hints_payload(existing, new_translations, "en")
    texts = [h["text"] for h in result]
    assert texts.index("apple") < texts.index("zebra")


def test_build_hints_payload_idempotent():
    hints = [{"locale": "en", "text": "dog"}]
    result1 = build_hints_payload(hints, ["cat"], "en")
    result2 = build_hints_payload(hints, ["cat"], "en")
    assert result1 == result2


def test_deduplicate_hints():
    hints = [
        {"locale": "en", "text": "Dog"},
        {"locale": "en", "text": "dog"},
        {"locale": "en", "text": "cat"},
    ]
    result = deduplicate_hints(hints)
    en_texts = [h["text"] for h in result if h["locale"] == "en"]
    assert len(en_texts) == 2

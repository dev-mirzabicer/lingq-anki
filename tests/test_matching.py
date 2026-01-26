import sys
from unittest.mock import MagicMock

mock_aqt = MagicMock()
sys.modules["aqt"] = mock_aqt
sys.modules["aqt.qt"] = mock_aqt.qt
sys.modules["aqt.gui_hooks"] = mock_aqt.gui_hooks

from matching import normalize_text, MatchResult


def test_normalize_text_basic():
    assert normalize_text("Hello") == "hello"


def test_normalize_text_unicode():
    assert normalize_text("Cafe\u0301") == "café"


def test_normalize_text_whitespace():
    assert normalize_text("  hello  world  ") == "hello world"


def test_normalize_text_punctuation_outer():
    assert normalize_text("...hello!") == "hello"


def test_normalize_text_punctuation_inner():
    assert normalize_text("don't") == "don't"


def test_normalize_text_empty():
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_match_result_linked():
    result = MatchResult(status="linked", lingq_pk=123, canonical_term="test")
    assert result.status == "linked"
    assert result.lingq_pk == 123
    assert result.canonical_term == "test"


def test_match_result_create_needed():
    result = MatchResult(status="create_needed")
    assert result.status == "create_needed"
    assert result.lingq_pk is None


def test_match_result_ambiguous():
    result = MatchResult(status="ambiguous", candidates=[{"pk": 1}, {"pk": 2}])
    assert result.status == "ambiguous"
    assert len(result.candidates) == 2

from __future__ import annotations

from typing import Dict, List, Tuple

from matching import normalize_text


def normalize_hint_text(text: str) -> str:
    """Normalize hint text for comparison.

    Delegates to matching.normalize_text to keep matching behavior consistent
    across the codebase.
    """

    return normalize_text(text)


def find_missing_hints(
    anki_translations: List[str],
    lingq_hints: List[Dict],
    locale: str,
) -> List[str]:
    """Return Anki translations not present as LingQ hints for locale."""

    existing_norms = set()
    for hint in lingq_hints:
        if (hint or {}).get("locale") != locale:
            continue
        text = str((hint or {}).get("text") or "")
        norm = normalize_hint_text(text)
        if norm:
            existing_norms.add(norm)

    missing: List[str] = []
    seen_missing_norms = set()
    for translation in anki_translations:
        text = str(translation or "")
        norm = normalize_hint_text(text)
        if not norm:
            continue
        if norm in existing_norms:
            continue
        if norm in seen_missing_norms:
            continue
        missing.append(text)
        seen_missing_norms.add(norm)

    return missing


def build_hints_payload(
    existing_hints: List[Dict],
    new_translations: List[str],
    locale: str,
) -> List[Dict]:
    """Build full hints payload (existing + new), sorted for idempotency."""

    hints: List[Dict] = [dict(h) for h in existing_hints]

    for translation in new_translations:
        text = str(translation or "")
        if not normalize_hint_text(text):
            continue
        hints.append({"locale": locale, "text": text})

    hints = deduplicate_hints(hints)

    def sort_key(hint: Dict) -> Tuple[str, str, str]:
        text = str((hint or {}).get("text") or "")
        loc = str((hint or {}).get("locale") or "")
        return (normalize_hint_text(text), loc, text)

    return sorted(hints, key=sort_key)


def deduplicate_hints(hints: List[Dict]) -> List[Dict]:
    """Remove duplicate hints by (locale, normalized_text), keeping first."""

    seen = set()
    deduped: List[Dict] = []

    for hint in hints:
        loc = str((hint or {}).get("locale") or "")
        text = str((hint or {}).get("text") or "")
        norm = normalize_hint_text(text)
        key = (loc, norm)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hint)

    return deduped

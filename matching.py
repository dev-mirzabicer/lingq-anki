from dataclasses import dataclass, field
from typing import List, Optional, Any

import re
import string
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize text for matching: NFKC, casefold, whitespace collapse, trim punctuation.

    Steps:
    1) NFKC normalization
    2) Casefold (aggressive lowercase)
    3) Collapse whitespace runs to single space
    4) Trim surrounding whitespace
    5) Strip leading/trailing punctuation (keep inner punctuation)
    """
    # 1. NFKC normalization
    text = unicodedata.normalize("NFKC", text)
    # 2. Casefold (aggressive lowercase)
    text = text.casefold()
    # 3. Collapse whitespace runs to single space
    text = re.sub(r"\s+", " ", text)
    # 4. Trim
    text = text.strip()
    # 5. Strip leading/trailing punctuation (keep inner)
    text = text.strip(string.punctuation)
    return text


@dataclass
class MatchResult:
    status: str  # "linked", "create_needed", "ambiguous", "error"
    lingq_pk: Optional[int] = None
    canonical_term: Optional[str] = None
    candidates: List[Any] = field(default_factory=list)
    error_message: Optional[str] = None


def match_anki_note_to_lingq(
    client,  # LingQClient instance
    language: str,
    meaning_locale: str,
    existing_pk: Optional[int],
    term: str,
    translation: str,
) -> MatchResult:
    term_norm = normalize_text(term)
    translation_norm = normalize_text(translation)

    if existing_pk:
        try:
            url = client._make_url(f"/v3/{language}/cards/{existing_pk}/", None)
            card = client._request_json("GET", url)
            pk = card.get("pk") if isinstance(card, dict) else None
            canonical_term = card.get("term") if isinstance(card, dict) else None
            return MatchResult(
                status="linked",
                lingq_pk=int(pk) if pk is not None else int(existing_pk),
                canonical_term=str(canonical_term)
                if canonical_term is not None
                else None,
            )
        except Exception as e:
            return MatchResult(
                status="error",
                lingq_pk=existing_pk,
                error_message=str(e),
            )

    try:
        candidates = client.search_cards(language, term_norm)
    except Exception as e:
        return MatchResult(status="error", error_message=str(e))

    # Narrow to exact term matches when the search endpoint is fuzzy.
    term_candidates = [
        c for c in candidates if normalize_text(str(c.get("term") or "")) == term_norm
    ]
    if term_candidates:
        candidates = term_candidates

    matches: List[Any] = []
    for card in candidates:
        hints = card.get("hints") or []
        for hint in hints:
            if hint.get("locale") != meaning_locale:
                continue
            if normalize_text(str(hint.get("text") or "")) == translation_norm:
                matches.append(card)
                break

    if len(matches) == 1:
        card = matches[0]
        pk = card.get("pk")
        canonical_term = card.get("term")
        return MatchResult(
            status="linked",
            lingq_pk=int(pk) if pk is not None else None,
            canonical_term=str(canonical_term) if canonical_term is not None else None,
        )

    if len(matches) == 0:
        return MatchResult(status="create_needed")

    return MatchResult(status="ambiguous", candidates=matches)

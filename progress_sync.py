from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# LingQ statuses: 0=new, 1=recognized, 2=familiar, 3=learned, 4=known
LINGQ_STATUS_TIERS = {
    0: "new",  # Never reviewed
    1: "learning",  # Recognized
    2: "learning",  # Familiar
    3: "learned",  # Learned
    4: "known",  # Known (mastered)
}


def lingq_status_to_tier(
    lingq_status: int, extended_status: Optional[int] = None
) -> str:
    """Map LingQ status (+ optional extended_status) to a coarse mastery tier.

    LingQ historically represented "known" as status=3 with extended_status=3.
    Newer payloads may use status=4.
    """

    if lingq_status == 3 and extended_status == 3:
        return "known"
    return LINGQ_STATUS_TIERS.get(int(lingq_status), "unknown")


def _coerce_to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_lingq_due_date(value: str) -> Optional[datetime]:
    """Parse a LingQ date/datetime string into a naive UTC datetime.

    Expected formats observed in practice:
    - YYYY-MM-DD
    - ISO 8601 datetime, sometimes with a trailing 'Z'
    """

    raw = (value or "").strip()
    if not raw:
        return None

    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return _coerce_to_utc_naive(dt)
    except ValueError:
        # Try date-only.
        try:
            d = datetime.strptime(raw, "%Y-%m-%d")
            return d
        except ValueError:
            return None


def can_create_synthetic_review(
    lingq_status: int,
    lingq_due_date: Optional[str],
    anki_last_review: Optional[datetime],
    threshold_days: int = 7,
) -> bool:
    """Return True only if we can attribute a real review event with bounded timestamp.

    This function is intentionally conservative. It does NOT create synthetic reviews;
    it only answers whether a synthetic review could be justified.

    Only create synthetic if:
    1. LingQ status changed (evidence of user action)  [caller responsibility]
    2. Timestamp difference is within threshold
    """

    # Caller should only invoke this when a status change was observed.
    if int(lingq_status) <= 0:
        return False
    if anki_last_review is None:
        return False
    if not lingq_due_date:
        return False

    due_dt = _parse_lingq_due_date(lingq_due_date)
    if due_dt is None:
        return False

    last = _coerce_to_utc_naive(anki_last_review)
    delta_s = abs((due_dt - last).total_seconds())
    return delta_s <= float(max(0, int(threshold_days))) * 86400.0


def count_hints_in_locale(hints: List[Dict], locale: str) -> int:
    """Count hints matching the given locale."""

    if not isinstance(locale, str) or not locale.strip():
        return 0

    loc = locale.strip()
    count = 0
    for hint in hints or []:
        if not isinstance(hint, dict):
            continue
        if hint.get("locale") != loc:
            continue
        text = hint.get("text")
        if isinstance(text, str) and text.strip():
            count += 1
    return count


def has_polysemy(hints: List[Dict], locale: str) -> bool:
    """Return True if card has multiple hints in the meaning locale."""

    return count_hints_in_locale(hints, locale) > 1


@dataclass
class ProgressComparison:
    should_sync_to_lingq: bool = False
    should_sync_to_anki: bool = False
    lingq_tier: str = "unknown"
    reason: str = ""


def compare_progress(
    lingq_status: int,
    lingq_hints: List[Dict],
    meaning_locale: str,
    anki_has_reviews: bool,
    enable_scheduling_writes: bool,
) -> ProgressComparison:
    """Compare coarse progress and decide which direction should write.

    FSRS-first hybrid strategy:
    - Anki revlog is the source of truth for scheduling.
    - LingQ status is a coarse mastery tier.

    Polysemy rule enforced here:
    - LingQ->Anki: if LingQ card has multiple hints in meaning locale, skip any
      Anki scheduling/progress updates.
    """

    tier = lingq_status_to_tier(int(lingq_status), None)
    poly = has_polysemy(lingq_hints or [], meaning_locale)

    if not bool(enable_scheduling_writes):
        return ProgressComparison(
            should_sync_to_lingq=False,
            should_sync_to_anki=False,
            lingq_tier=tier,
            reason="scheduling_writes_disabled",
        )

    # If Anki has reviews but LingQ is still 'new', treat this as Anki-leading.
    if bool(anki_has_reviews) and tier == "new":
        return ProgressComparison(
            should_sync_to_lingq=True,
            should_sync_to_anki=False,
            lingq_tier=tier,
            reason="anki_has_reviews_lingq_new",
        )

    # If LingQ shows progress but Anki has no reviews, treat as LingQ-leading.
    if not bool(anki_has_reviews) and tier != "new":
        if poly:
            return ProgressComparison(
                should_sync_to_lingq=False,
                should_sync_to_anki=False,
                lingq_tier=tier,
                reason="polysemy_skip_lingq_to_anki",
            )
        return ProgressComparison(
            should_sync_to_lingq=False,
            should_sync_to_anki=True,
            lingq_tier=tier,
            reason="lingq_has_progress_anki_no_reviews",
        )

    return ProgressComparison(
        should_sync_to_lingq=False,
        should_sync_to_anki=False,
        lingq_tier=tier,
        reason="no_action",
    )


def _debug_payload_summary(
    card: Dict[str, Any], *, meaning_locale: str
) -> Dict[str, Any]:
    """Lightweight helper for callers/tests; not used by sync engine directly."""

    hints = card.get("hints") if isinstance(card, dict) else None
    hints_list = hints if isinstance(hints, list) else []
    return {
        "status": card.get("status") if isinstance(card, dict) else None,
        "extended_status": card.get("extended_status")
        if isinstance(card, dict)
        else None,
        "tier": lingq_status_to_tier(
            int(card.get("status") or 0),
            card.get("extended_status")
            if isinstance(card.get("extended_status"), int)
            else None,
        )
        if isinstance(card, dict)
        else "unknown",
        "polysemy": has_polysemy(hints_list, meaning_locale),
        "hint_count": count_hints_in_locale(hints_list, meaning_locale),
    }

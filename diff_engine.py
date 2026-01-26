from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, cast

from hint_reconciliation import build_hints_payload, find_missing_hints
from matching import normalize_text
from progress_sync import compare_progress, has_polysemy, lingq_status_to_tier


OP_CREATE_LINGQ = "create_lingq"  # create new LingQ card from Anki
OP_CREATE_ANKI = "create_anki"  # create new Anki note from LingQ
OP_LINK = "link"  # link existing Anki note to LingQ card
OP_UPDATE_HINTS = "update_hints"  # update LingQ hints
OP_UPDATE_STATUS = "update_status"  # update LingQ status
OP_RESCHEDULE_ANKI = "reschedule_anki"  # reschedule Anki card
OP_CONFLICT = "conflict"  # ambiguous match needing resolution
OP_SKIP = "skip"  # skipped due to policy (e.g., polysemy)


@dataclass
class SyncOperation:
    op_type: str
    anki_note_id: Optional[int] = None
    lingq_pk: Optional[int] = None
    term: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncPlan:
    operations: List[SyncOperation] = field(default_factory=list)

    def count_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for op in self.operations:
            counts[op.op_type] = counts.get(op.op_type, 0) + 1
        return counts

    def get_conflicts(self) -> List[SyncOperation]:
        return [op for op in self.operations if op.op_type == OP_CONFLICT]

    def get_skips(self) -> List[SyncOperation]:
        return [op for op in self.operations if op.op_type == OP_SKIP]


def compute_sync_plan(
    anki_notes: List[Dict],
    lingq_cards: List[Dict],
    profile,  # Profile dataclass
    meaning_locale: str,
) -> SyncPlan:
    plan = SyncPlan()
    # Optional integration: attach profile name for apply_engine checkpoints.
    setattr(plan, "profile_name", getattr(profile, "name", ""))

    pk_field = profile.lingq_to_anki.identity_fields.pk_field
    canonical_term_field = profile.lingq_to_anki.identity_fields.canonical_term_field
    lingq_language = profile.lingq_language

    # --- Load LSS (injected or store-backed) ---
    lss = _load_lss(profile)

    # --- Normalize and index LingQ cards ---
    lingq_by_pk: Dict[int, Dict[str, Any]] = {}
    lingq_by_term_norm: Dict[str, List[Dict[str, Any]]] = {}

    for card in sorted(lingq_cards, key=lambda c: int((c or {}).get("pk") or 0)):
        pk = _parse_int((card or {}).get("pk"))
        if pk is None:
            continue
        lingq_by_pk[pk] = card
        term_norm = normalize_text(str((card or {}).get("term") or ""))
        if term_norm:
            lingq_by_term_norm.setdefault(term_norm, []).append(card)

    # --- Normalize and index Anki notes ---
    # Index only unlinked notes for reverse matching from LingQ -> Anki.
    anki_sorted = sorted(anki_notes, key=lambda n: int((n or {}).get("note_id") or 0))
    unlinked_anki_by_term_norm: Dict[str, List[Dict[str, Any]]] = {}

    for note in anki_sorted:
        note_id = _parse_int((note or {}).get("note_id"))
        if note_id is None:
            continue
        fields_raw = (note or {}).get("fields")
        fields: Dict[str, Any] = (
            cast(Dict[str, Any], fields_raw) if isinstance(fields_raw, dict) else {}
        )
        existing_pk = _parse_int((fields or {}).get(pk_field))
        if existing_pk is not None:
            continue

        term = str((fields or {}).get(profile.anki_to_lingq.term_field) or "")
        term_norm = normalize_text(term)
        if term_norm:
            unlinked_anki_by_term_norm.setdefault(term_norm, []).append(note)

    # --- Pass 1: process each Anki note (Anki -> LingQ creation/linking + LingQ updates) ---
    linked_lingq_pks: set[int] = set()
    linked_anki_note_ids: set[int] = set()
    used_pk_by_anki_note: Dict[int, int] = {}

    for note in anki_sorted:
        note_id = _parse_int((note or {}).get("note_id"))
        if note_id is None:
            plan.operations.append(
                _op_skip(
                    anki_note_id=None, lingq_pk=None, term="", reason="invalid_payload"
                )
            )
            continue

        fields_raw = (note or {}).get("fields")
        fields: Dict[str, Any] = (
            cast(Dict[str, Any], fields_raw) if isinstance(fields_raw, dict) else {}
        )
        existing_pk = _parse_int((fields or {}).get(pk_field))

        term, term_norm = _extract_anki_term(fields, profile)
        translations, translation_norms = _extract_anki_translations(fields, profile)

        # --- Step 1: PK match if present ---
        if existing_pk is not None:
            card = lingq_by_pk.get(existing_pk)
            if card is None:
                plan.operations.append(
                    _op_conflict(
                        anki_note_id=note_id,
                        lingq_pk=existing_pk,
                        term=term,
                        conflict_type="dangling_pk",
                        recommended_action="refresh_lingq_fetch_or_unlink_note",
                        details={"pk_field": pk_field},
                    )
                )
                continue

            # Detect duplicate PK across Anki notes.
            if existing_pk in linked_lingq_pks:
                plan.operations.append(
                    _op_conflict(
                        anki_note_id=note_id,
                        lingq_pk=existing_pk,
                        term=term,
                        conflict_type="duplicate_pk",
                        recommended_action="dedupe_anki_notes_or_choose_primary",
                        details={"pk": existing_pk},
                    )
                )
                continue

            used_pk_by_anki_note[note_id] = existing_pk
            linked_lingq_pks.add(existing_pk)
            linked_anki_note_ids.add(note_id)

            # No OP_LINK needed if already linked by PK.
            _emit_update_ops_for_linked_pair(
                plan, note, card, lss, profile, meaning_locale
            )
            continue

        # --- Step 2: term+translation matching (requires exactly 1 translation token) ---
        if not term_norm:
            plan.operations.append(_op_skip(note_id, None, term, reason="missing_term"))
            continue
        if len(translations) == 0:
            plan.operations.append(
                _op_skip(note_id, None, term, reason="missing_translation")
            )
            continue
        if len(translations) > 1:
            plan.operations.append(
                _op_conflict(
                    anki_note_id=note_id,
                    lingq_pk=None,
                    term=term,
                    conflict_type="anki_polysemy_needs_policy",
                    recommended_action="choose_aggregation_policy_or_select_single_translation",
                    details={"translations": list(translations)},
                )
            )
            continue

        candidate_cards = lingq_by_term_norm.get(term_norm, [])
        matches = _filter_lingq_by_translation(
            candidate_cards, translation_norms[0], meaning_locale
        )

        if len(matches) == 1:
            card = matches[0]
            pk = _parse_int((card or {}).get("pk"))
            if pk is None:
                plan.operations.append(
                    _op_conflict(
                        note_id,
                        None,
                        term,
                        "invalid_payload",
                        "skip",
                        details={"card": card},
                    )
                )
                continue

            if pk in linked_lingq_pks:
                plan.operations.append(
                    _op_conflict(
                        anki_note_id=note_id,
                        lingq_pk=pk,
                        term=term,
                        conflict_type="ambiguous_lingq_match",
                        recommended_action="multiple_anki_notes_match_same_lingq",
                        details={"lingq_pk": pk},
                    )
                )
                continue

            linked_lingq_pks.add(pk)
            linked_anki_note_ids.add(note_id)
            used_pk_by_anki_note[note_id] = pk

            # Emit OP_LINK (write PK back).
            plan.operations.append(
                _op_link(
                    note_id,
                    pk,
                    term,
                    pk_field,
                    canonical_term_field,
                    str((card or {}).get("term") or ""),
                )
            )

            _emit_update_ops_for_linked_pair(
                plan, note, card, lss, profile, meaning_locale
            )
            continue

        if len(matches) == 0:
            # Create LingQ card from Anki (only if single translation).
            plan.operations.append(
                _op_create_lingq(
                    note_id, term, translations, lingq_language, meaning_locale
                )
            )
            continue

        # len(matches) > 1
        plan.operations.append(
            _op_conflict(
                anki_note_id=note_id,
                lingq_pk=None,
                term=term,
                conflict_type="ambiguous_lingq_match",
                recommended_action="user_select_lingq_pk",
                details={
                    "candidates": [
                        _candidate_summary(c, meaning_locale) for c in matches
                    ]
                },
            )
        )

    # --- Pass 2: process LingQ cards not linked to any Anki note (LingQ -> Anki creation/linking) ---
    for pk, card in sorted(lingq_by_pk.items(), key=lambda t: t[0]):
        if pk in linked_lingq_pks:
            continue

        term = str((card or {}).get("term") or "")
        term_norm = normalize_text(term)
        if not term_norm:
            plan.operations.append(_op_skip(None, pk, term, reason="missing_term"))
            continue

        # Determine a deterministic "primary" translation for matching/creation.
        primary_translation = _select_primary_lingq_translation(card, meaning_locale)
        primary_translation_norm = normalize_text(primary_translation)
        if not primary_translation_norm:
            plan.operations.append(
                _op_skip(None, pk, term, reason="missing_translation")
            )
            continue

        # Attempt to link to a unique unlinked Anki note.
        candidates = unlinked_anki_by_term_norm.get(term_norm, [])
        matches: List[Dict[str, Any]] = []
        for note in candidates:
            fields_raw = (note or {}).get("fields")
            fields: Dict[str, Any] = (
                cast(Dict[str, Any], fields_raw) if isinstance(fields_raw, dict) else {}
            )
            _translations, translation_norms = _extract_anki_translations(
                fields, profile
            )
            if len(translation_norms) != 1:
                continue
            if translation_norms[0] == primary_translation_norm:
                matches.append(note)

        if len(matches) == 1:
            note = matches[0]
            note_id = _parse_int((note or {}).get("note_id"))
            if note_id is not None:
                plan.operations.append(
                    _op_link(
                        note_id,
                        pk,
                        term,
                        pk_field,
                        canonical_term_field,
                        str((card or {}).get("term") or ""),
                    )
                )
                linked_lingq_pks.add(pk)
                linked_anki_note_ids.add(note_id)
                _emit_update_ops_for_linked_pair(
                    plan, note, card, lss, profile, meaning_locale
                )
                continue

        if len(matches) > 1:
            plan.operations.append(
                _op_conflict(
                    anki_note_id=None,
                    lingq_pk=pk,
                    term=term,
                    conflict_type="ambiguous_lingq_match",
                    recommended_action="multiple_anki_notes_match_same_lingq",
                    details={
                        "anki_candidates": [
                            int((n or {}).get("note_id") or 0) for n in matches
                        ]
                    },
                )
            )
            continue

        # Otherwise create Anki note.
        plan.operations.append(
            _op_create_anki_from_lingq(card, profile, meaning_locale)
        )

    return plan


def _load_lss(profile: Any) -> Dict[Any, Any]:
    injected = getattr(profile, "lss", None)
    if isinstance(injected, dict):
        return injected
    # fallback: lss_store.load(profile.name)
    return {}


def _parse_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _extract_anki_term(fields: Dict[str, Any], profile: Any) -> Tuple[str, str]:
    raw = str((fields or {}).get(profile.anki_to_lingq.term_field) or "")
    return raw, normalize_text(raw)


def _extract_anki_translations(
    fields: Dict[str, Any], profile: Any
) -> Tuple[List[str], List[str]]:
    tokens: List[str] = []
    norms: List[str] = []
    for fname in list(getattr(profile.anki_to_lingq, "translation_fields", None) or []):
        raw = str((fields or {}).get(fname) or "")
        # split on newline only
        for part in raw.split("\n"):
            t = part.strip()
            n = normalize_text(t)
            if n:
                tokens.append(t)
                norms.append(n)

    # dedupe norms while keeping stable order
    seen: set[str] = set()
    out_tokens: List[str] = []
    out_norms: List[str] = []
    for t, n in zip(tokens, norms):
        if n in seen:
            continue
        seen.add(n)
        out_tokens.append(t)
        out_norms.append(n)
    return out_tokens, out_norms


def _filter_lingq_by_translation(
    cards: List[Dict[str, Any]], translation_norm: str, meaning_locale: str
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in cards:
        hints_raw = (c or {}).get("hints")
        hints_list = hints_raw if isinstance(hints_raw, list) else []
        for hint in hints_list:
            if not isinstance(hint, dict):
                continue
            if hint.get("locale") != meaning_locale:
                continue
            text = str(hint.get("text") or "")
            if normalize_text(text) == translation_norm:
                out.append(c)
                break
    return out


def _select_primary_lingq_translation(card: Dict[str, Any], meaning_locale: str) -> str:
    # Deterministic primary translation for matching/creation.
    # Prefer highest popularity hint in locale; tie-break by normalized text.
    hints_raw = (card or {}).get("hints")
    hints_list = hints_raw if isinstance(hints_raw, list) else []
    candidates: List[Tuple[int, str, str]] = []  # (-popularity, norm_text, raw_text)
    for h in hints_list:
        if not isinstance(h, dict):
            continue
        if h.get("locale") != meaning_locale:
            continue
        raw = str(h.get("text") or "").strip()
        norm = normalize_text(raw)
        if not norm:
            continue
        pop = h.get("popularity")
        pop_i = int(pop) if isinstance(pop, int) else 0
        candidates.append((-pop_i, norm, raw))
    candidates.sort()
    return candidates[0][2] if candidates else ""


def _emit_update_ops_for_linked_pair(
    plan: SyncPlan,
    note: Dict[str, Any],
    card: Dict[str, Any],
    lss: Dict[Any, Any],
    profile: Any,
    meaning_locale: str,
) -> None:
    note_id = _parse_int((note or {}).get("note_id"))
    pk = _parse_int((card or {}).get("pk"))
    term = str((card or {}).get("term") or "")
    if note_id is None or pk is None:
        plan.operations.append(_op_skip(note_id, pk, term, reason="invalid_payload"))
        return

    # LSS lookup
    _s = lss.get(pk) or lss.get(note_id)  # may be None; reserved for future 3-way diff

    # --- Hints: Anki -> LingQ (additive) ---
    fields_raw = (note or {}).get("fields")
    fields: Dict[str, Any] = (
        cast(Dict[str, Any], fields_raw) if isinstance(fields_raw, dict) else {}
    )
    translations, _translation_norms = _extract_anki_translations(fields, profile)
    lingq_hints_raw = (card or {}).get("hints")
    lingq_hints_list = lingq_hints_raw if isinstance(lingq_hints_raw, list) else []
    lingq_hints: List[Dict[str, Any]] = [
        h for h in lingq_hints_list if isinstance(h, dict)
    ]
    missing = find_missing_hints(translations, lingq_hints, meaning_locale)

    if missing:
        new_payload = build_hints_payload(lingq_hints, missing, meaning_locale)
        if not _hints_payload_equal(new_payload, lingq_hints):
            plan.operations.append(
                SyncOperation(
                    op_type=OP_UPDATE_HINTS,
                    anki_note_id=note_id,
                    lingq_pk=pk,
                    term=term,
                    details={
                        "lingq_language": profile.lingq_language,
                        "hints": new_payload,
                        "reason": "anki_translation_missing_in_lingq",
                    },
                )
            )

    # --- Progress: choose direction using progress_sync.compare_progress ---
    enable_sched = bool(getattr(profile, "enable_scheduling_writes", False))
    anki_has_reviews = _anki_has_reviews(note)
    lingq_status = int((card or {}).get("status") or 0)
    poly = has_polysemy(lingq_hints, meaning_locale)
    comp = compare_progress(
        lingq_status=lingq_status,
        lingq_hints=lingq_hints,
        meaning_locale=meaning_locale,
        anki_has_reviews=anki_has_reviews,
        enable_scheduling_writes=enable_sched,
    )

    if not enable_sched:
        # compare_progress already encodes this, but emit explicit skip for transparency.
        plan.operations.append(
            _op_skip(note_id, pk, term, reason="scheduling_writes_disabled")
        )
        return

    if comp.should_sync_to_lingq:
        # Determine desired LingQ status from Anki (coarse mapping).
        desired_status = _map_anki_progress_to_lingq_status(
            note, current_status=lingq_status
        )
        if desired_status != lingq_status:
            plan.operations.append(
                SyncOperation(
                    op_type=OP_UPDATE_STATUS,
                    anki_note_id=note_id,
                    lingq_pk=pk,
                    term=term,
                    details={
                        "lingq_language": profile.lingq_language,
                        "status": desired_status,
                        "reason": comp.reason,
                    },
                )
            )
        return

    if comp.should_sync_to_anki:
        # Guardrail: polysemy blocks scheduling writes.
        if poly:
            plan.operations.append(
                _op_skip(note_id, pk, term, reason="polysemy_skip_lingq_to_anki")
            )
            return
        plan.operations.append(
            SyncOperation(
                op_type=OP_RESCHEDULE_ANKI,
                anki_note_id=note_id,
                lingq_pk=pk,
                term=term,
                details={
                    "target_tier": lingq_status_to_tier(
                        lingq_status, (card or {}).get("extended_status")
                    ),
                    "lingq_status": lingq_status,
                    "lingq_due_date": (card or {}).get("srs_due_date"),
                    "reason": comp.reason,
                    "fsrs_safe": True,
                },
            )
        )


def _anki_has_reviews(note: Dict[str, Any]) -> bool:
    cards = (note or {}).get("cards")
    if not isinstance(cards, list):
        return False
    for c in cards:
        if not isinstance(c, dict):
            continue
        reps = c.get("reps")
        if isinstance(reps, int) and reps > 0:
            return True
    return False


def _map_anki_progress_to_lingq_status(
    note: Dict[str, Any], current_status: int
) -> int:
    # Coarse, deterministic mapping; tune later.
    # Never decrease LingQ status here.
    reps = 0
    max_ivl = 0
    cards_raw = (note or {}).get("cards")
    cards = cards_raw if isinstance(cards_raw, list) else []
    for c in cards:
        if not isinstance(c, dict):
            continue
        r = c.get("reps")
        if isinstance(r, int) and r > reps:
            reps = r
        ivl = c.get("ivl")
        if isinstance(ivl, int) and ivl > max_ivl:
            max_ivl = ivl

    desired = current_status
    if reps >= 1:
        desired = max(desired, 1)
    if reps >= 3:
        desired = max(desired, 2)
    if max_ivl >= 21:
        desired = max(desired, 3)
    if max_ivl >= 90:
        desired = max(desired, 4)
    return max(0, min(4, int(desired)))


def _hints_payload_equal(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    # Compare by normalized (locale, normalized_text) keys.
    def keyset(hints: List[Dict[str, Any]]) -> set[tuple[str, str]]:
        s: set[tuple[str, str]] = set()
        for h in hints or []:
            if not isinstance(h, dict):
                continue
            loc = str(h.get("locale") or "")
            text = normalize_text(str(h.get("text") or ""))
            if loc and text:
                s.add((loc, text))
        return s

    return keyset(a) == keyset(b)


def _op_link(
    note_id: int,
    pk: int,
    term: str,
    pk_field: str,
    canonical_term_field: str,
    canonical_term_value: str,
) -> SyncOperation:
    return SyncOperation(
        op_type=OP_LINK,
        anki_note_id=note_id,
        lingq_pk=pk,
        term=term,
        details={
            "identity_fields": {
                "pk_field": pk_field,
                "canonical_term_field": canonical_term_field,
            },
            "identity_values": {
                "pk_value": str(pk),
                "canonical_term_value": canonical_term_value,
            },
            "match": {"method": "term_translation", "confidence": "exact"},
        },
    )


def _op_create_lingq(
    note_id: int,
    term: str,
    translations: List[str],
    lingq_language: str,
    meaning_locale: str,
) -> SyncOperation:
    hints = [
        {"locale": meaning_locale, "text": translations[0]}
    ]  # single translation only
    return SyncOperation(
        op_type=OP_CREATE_LINGQ,
        anki_note_id=note_id,
        lingq_pk=None,
        term=term,
        details={"lingq_language": lingq_language, "hints": hints, "source": "anki"},
    )


def _op_create_anki_from_lingq(
    card: Dict[str, Any], profile: Any, meaning_locale: str
) -> SyncOperation:
    pk = _parse_int((card or {}).get("pk"))
    term = str((card or {}).get("term") or "")
    fields_out: Dict[str, str] = {}
    for lingq_key, anki_field in (
        getattr(profile.lingq_to_anki, "field_mapping", None) or {}
    ).items():
        fields_out[str(anki_field)] = _extract_lingq_field(
            card, str(lingq_key), meaning_locale
        )

    # Identity fields
    pk_field = profile.lingq_to_anki.identity_fields.pk_field
    canon_field = profile.lingq_to_anki.identity_fields.canonical_term_field
    if pk is not None:
        fields_out[pk_field] = str(pk)
    fields_out[canon_field] = term
    return SyncOperation(
        op_type=OP_CREATE_ANKI,
        anki_note_id=None,
        lingq_pk=pk,
        term=term,
        details={
            "note_type": profile.lingq_to_anki.note_type,
            "fields": fields_out,
            "identity_fields": {
                "pk_field": pk_field,
                "canonical_term_field": canon_field,
            },
            "identity_values": {
                "pk_value": str(pk) if pk is not None else "",
                "canonical_term_value": term,
            },
            "source": "lingq",
        },
    )


def _extract_lingq_field(
    card: Dict[str, Any], lingq_key: str, meaning_locale: str
) -> str:
    # Deterministic extractor. Extend as needed.
    if lingq_key == "term":
        return str((card or {}).get("term") or "")
    if lingq_key in {"pk", "LingQ_PK"}:
        return str((card or {}).get("pk") or "")
    if lingq_key in {"status"}:
        return str((card or {}).get("status") or "")
    if lingq_key in {"fragment"}:
        return str((card or {}).get("fragment") or "")
    if lingq_key in {"translation", "hint", "meaning"}:
        return _select_primary_lingq_translation(card, meaning_locale)
    if lingq_key in {"translations", "hints"}:
        # Join all hints in locale deterministically.
        hints_raw = (card or {}).get("hints")
        hints = hints_raw if isinstance(hints_raw, list) else []
        texts: List[str] = []
        for h in hints:
            if not isinstance(h, dict):
                continue
            if h.get("locale") != meaning_locale:
                continue
            t = str(h.get("text") or "").strip()
            if normalize_text(t):
                texts.append(t)
        # stable, idempotent join
        texts = sorted(set(texts), key=lambda x: normalize_text(x))
        return "; ".join(texts)
    return str((card or {}).get(lingq_key) or "")


def _op_conflict(
    anki_note_id: Optional[int],
    lingq_pk: Optional[int],
    term: str,
    conflict_type: str,
    recommended_action: str,
    details: Optional[Dict[str, Any]] = None,
) -> SyncOperation:
    d = dict(details or {})
    d["conflict_type"] = conflict_type
    d["recommended_action"] = recommended_action
    return SyncOperation(
        op_type=OP_CONFLICT,
        anki_note_id=anki_note_id,
        lingq_pk=lingq_pk,
        term=term,
        details=d,
    )


def _op_skip(
    anki_note_id: Optional[int], lingq_pk: Optional[int], term: str, reason: str
) -> SyncOperation:
    return SyncOperation(
        op_type=OP_SKIP,
        anki_note_id=anki_note_id,
        lingq_pk=lingq_pk,
        term=term,
        details={"reason": reason},
    )


def _candidate_summary(card: Dict[str, Any], meaning_locale: str) -> Dict[str, Any]:
    pk = _parse_int((card or {}).get("pk"))
    term = str((card or {}).get("term") or "")
    # show only locale hints
    hints: List[str] = []
    hints_raw = (card or {}).get("hints")
    hints_list = hints_raw if isinstance(hints_raw, list) else []
    for h in hints_list:
        if isinstance(h, dict) and h.get("locale") == meaning_locale:
            hints.append(str(h.get("text") or ""))
    return {"pk": pk, "term": term, "hints": hints}

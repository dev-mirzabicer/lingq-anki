from __future__ import annotations

# pyright: reportMissingImports=false

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .diff_engine import (
        OP_CONFLICT,
        OP_CREATE_ANKI,
        OP_CREATE_LINGQ,
        OP_LINK,
        OP_RESCHEDULE_ANKI,
        OP_SKIP,
        OP_UPDATE_HINTS,
        OP_UPDATE_STATUS,
        SyncOperation,
        SyncPlan,
    )
    from .lingq_client import LingQClient
except ImportError:
    from diff_engine import (  # type: ignore[no-redef]
        OP_CONFLICT,
        OP_CREATE_ANKI,
        OP_CREATE_LINGQ,
        OP_LINK,
        OP_RESCHEDULE_ANKI,
        OP_SKIP,
        OP_UPDATE_HINTS,
        OP_UPDATE_STATUS,
        SyncOperation,
        SyncPlan,
    )
    from lingq_client import LingQClient  # type: ignore[no-redef]


_LOGGER = logging.getLogger(__name__)


def _is_anki_runtime() -> bool:
    """Check if running inside Anki with collection available."""
    try:
        from aqt import mw

        return mw is not None and mw.col is not None
    except ImportError:
        return False


@dataclass
class Checkpoint:
    run_id: str
    last_processed_index: int = 0
    completed_ops: List[str] = field(default_factory=list)  # list of op identifiers


@dataclass
class ApplyResult:
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    errors: List[str] = field(default_factory=list)


def _checkpoint_path(profile_name: str) -> Path:
    return Path(f".lingq_sync_checkpoint_{profile_name}.json")


def load_checkpoint(profile_name: str) -> Optional[Checkpoint]:
    path = _checkpoint_path(profile_name)
    if not path.exists():
        return None

    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as e:
        _LOGGER.warning("Failed to load checkpoint %s: %s", str(path), e)
        return None

    if not isinstance(payload, dict):
        return None

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return None

    last_processed_index = payload.get("last_processed_index", 0)
    if not isinstance(last_processed_index, int):
        last_processed_index = 0

    completed_ops = payload.get("completed_ops", [])
    if not isinstance(completed_ops, list) or not all(
        isinstance(x, str) for x in completed_ops
    ):
        completed_ops = []

    return Checkpoint(
        run_id=run_id,
        last_processed_index=max(0, last_processed_index),
        completed_ops=list(completed_ops),
    )


def save_checkpoint(profile_name: str, checkpoint: Checkpoint) -> None:
    path = _checkpoint_path(profile_name)
    tmp = Path(str(path) + ".tmp")

    payload = {
        "run_id": checkpoint.run_id,
        "last_processed_index": int(checkpoint.last_processed_index),
        "completed_ops": list(checkpoint.completed_ops),
    }

    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def clear_checkpoint(profile_name: str) -> None:
    path = _checkpoint_path(profile_name)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _new_run_id() -> str:
    return str(uuid.uuid4())


def _op_identifier(op: SyncOperation) -> str:
    # Keep this stable and human-readable; avoid hashing details to reduce churn.
    anki = "" if op.anki_note_id is None else str(op.anki_note_id)
    pk = "" if op.lingq_pk is None else str(op.lingq_pk)
    term = op.term or ""
    return f"{op.op_type}:{anki}:{pk}:{term}"


def _language_for_op(op: SyncOperation) -> Optional[str]:
    if not isinstance(op.details, dict):
        return None
    for key in ("language", "lingq_language"):
        val = op.details.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _hints_for_op(op: SyncOperation) -> List[Dict[str, Any]]:
    if not isinstance(op.details, dict):
        return []
    hints = op.details.get("hints")
    if isinstance(hints, list) and all(isinstance(x, dict) for x in hints):
        return list(hints)  # type: ignore[return-value]
    return []


def _apply_link(op: SyncOperation) -> bool:
    """Write LingQ PK and canonical term to Anki note fields.

    Returns True if changes were made, False otherwise.
    Raises on error.
    """

    if not _is_anki_runtime():
        raise RuntimeError("Anki runtime required for OP_LINK")

    from aqt import mw

    note_id = op.anki_note_id
    if note_id is None:
        raise ValueError("OP_LINK missing anki_note_id")

    if not isinstance(op.details, dict):
        raise ValueError("OP_LINK missing op.details")

    identity_fields = op.details.get("identity_fields", {})
    identity_values = op.details.get("identity_values", {})
    if not isinstance(identity_fields, dict) or not isinstance(identity_values, dict):
        raise ValueError("OP_LINK missing identity_fields/identity_values")

    pk_field = identity_fields.get("pk_field")
    canon_field = identity_fields.get("canonical_term_field")
    pk_value = str(identity_values.get("pk_value", "")).strip()
    canon_value = str(identity_values.get("canonical_term_value", "")).strip()

    if not isinstance(pk_field, str) or not pk_field.strip():
        raise ValueError("OP_LINK missing identity field name: pk_field")
    if not isinstance(canon_field, str) or not canon_field.strip():
        raise ValueError("OP_LINK missing identity field name: canonical_term_field")
    if not pk_value:
        raise ValueError("OP_LINK missing identity value: pk_value")

    note = mw.col.get_note(note_id)
    model = note.note_type()
    field_names = mw.col.models.field_names(model)

    if pk_field not in field_names or canon_field not in field_names:
        raise ValueError(f"Identity fields not in note type: {pk_field}, {canon_field}")

    existing_pk = (note[pk_field] or "").strip()
    existing_canon = (note[canon_field] or "").strip()

    # Conflict check
    if existing_pk and existing_pk != pk_value:
        raise ValueError(
            f"PK conflict: note has {existing_pk}, trying to set {pk_value}"
        )

    # Idempotency check
    if existing_pk == pk_value and existing_canon == canon_value:
        return False

    # Apply changes
    if not existing_pk:
        note[pk_field] = pk_value
    if existing_canon != canon_value:
        note[canon_field] = canon_value

    mw.col.update_note(note)
    return True


def _apply_create_anki(op: SyncOperation) -> bool:
    """Create new Anki note from LingQ card.

    Returns True if note was created, False if already exists.
    Raises on error.
    """

    if not _is_anki_runtime():
        raise RuntimeError("Anki runtime required for OP_CREATE_ANKI")

    from aqt import mw

    if not isinstance(op.details, dict):
        raise ValueError("OP_CREATE_ANKI missing op.details")

    note_type = str(op.details.get("note_type") or "").strip()
    fields = op.details.get("fields")
    if not note_type or not isinstance(fields, dict):
        raise ValueError("OP_CREATE_ANKI missing note_type or fields")

    identity_fields = op.details.get("identity_fields", {})
    identity_values = op.details.get("identity_values", {})
    if not isinstance(identity_fields, dict) or not isinstance(identity_values, dict):
        raise ValueError("OP_CREATE_ANKI missing identity_fields/identity_values")

    pk_field = identity_fields.get("pk_field")
    pk_value = str(identity_values.get("pk_value", "")).strip()

    if isinstance(pk_field, str) and pk_field.strip() and pk_value:
        existing = mw.col.find_notes(f"{pk_field}:{pk_value}")
        if existing:
            return False

    model = mw.col.models.by_name(note_type)
    if not model:
        raise ValueError(f"Note type not found: {note_type}")

    model_fields = set(mw.col.models.field_names(model))
    for fname in fields.keys():
        if fname not in model_fields:
            raise ValueError(f"Field {fname!r} not in note type {note_type!r}")

    deck_name = str(op.details.get("deck") or "Default").strip() or "Default"
    deck_id = mw.col.decks.id(deck_name)

    note = mw.col.new_note(model)
    for fname, value in fields.items():
        note[fname] = str(value or "")

    mw.col.add_note(note, deck_id)
    return True


def _tier_to_days(tier: str) -> int:
    """Map LingQ tier to Anki interval days."""

    mapping = {"new": 0, "learning": 4, "learned": 28, "known": 90}
    return int(mapping.get(tier, 0))


def _apply_reschedule_anki(op: SyncOperation) -> bool:
    """Reschedule Anki card using FSRS-safe method.

    Returns True if card was rescheduled, False if no change needed.
    Raises on error.

    CRITICAL: Uses set_due_date() - NEVER writes to revlog or memory_state.
    """

    if not _is_anki_runtime():
        raise RuntimeError("Anki runtime required for OP_RESCHEDULE_ANKI")

    from aqt import mw

    note_id = op.anki_note_id
    if note_id is None:
        raise ValueError("OP_RESCHEDULE_ANKI missing anki_note_id")

    if not isinstance(op.details, dict):
        raise ValueError("OP_RESCHEDULE_ANKI missing op.details")

    tier = str(op.details.get("target_tier") or "").strip()
    if tier not in {"new", "learning", "learned", "known"}:
        raise ValueError(f"Invalid target_tier: {tier}")

    note = mw.col.get_note(note_id)
    cards = note.cards()
    if not cards:
        raise ValueError("Note has no cards")

    # Select primary card (first by ordinal)
    card = min(cards, key=lambda c: c.ord)
    target_days = _tier_to_days(tier)

    # Handle "new" tier specially
    if tier == "new":
        if getattr(card, "queue", None) == 0:
            return False
        mw.col.sched.forget_cards([card.id])
        return True

    # Idempotency check
    if getattr(card, "queue", None) == 2 and int(getattr(card, "ivl", 0) or 0) == int(
        target_days
    ):
        return False

    # FSRS-safe rescheduling
    mw.col.sched.set_due_date([card.id], str(target_days))
    return True


def _ordered_operations(plan: SyncPlan) -> List[Tuple[int, SyncOperation]]:
    # Stable grouping (preserve original order within each group).
    groups = [
        OP_LINK,
        OP_CREATE_LINGQ,
        OP_UPDATE_HINTS,
        OP_UPDATE_STATUS,
        OP_CONFLICT,
        OP_SKIP,
    ]
    priorities = {op_type: idx for idx, op_type in enumerate(groups)}

    indexed = list(enumerate(plan.operations))
    indexed.sort(key=lambda t: (priorities.get(t[1].op_type, 999), t[0]))
    return indexed


def _apply_create_lingq(op: SyncOperation, client: LingQClient) -> None:
    language = _language_for_op(op)
    if not language:
        raise ValueError("create_lingq missing language in op.details")
    if not op.term:
        raise ValueError("create_lingq missing term")

    existing = client.search_cards(language, op.term)
    for card in existing:
        term = card.get("term")
        if isinstance(term, str) and term.strip().lower() == op.term.strip().lower():
            # Idempotent: card already exists.
            return

    hints = _hints_for_op(op)
    client.create_card(language, op.term, hints)  # type: ignore[arg-type]


def _apply_update_hints(op: SyncOperation, client: LingQClient) -> None:
    language = _language_for_op(op)
    if not language:
        raise ValueError("update_hints missing language in op.details")
    if op.lingq_pk is None:
        raise ValueError("update_hints missing lingq_pk")
    hints = _hints_for_op(op)
    client.patch_card(language, op.lingq_pk, {"hints": hints})


def _apply_update_status(op: SyncOperation, client: LingQClient) -> None:
    language = _language_for_op(op)
    if not language:
        raise ValueError("update_status missing language in op.details")
    if op.lingq_pk is None:
        raise ValueError("update_status missing lingq_pk")

    if not isinstance(op.details, dict):
        raise ValueError("update_status missing op.details")

    data: Dict[str, Any] = {}
    status = op.details.get("status")
    if isinstance(status, int):
        data["status"] = status
    extended_status = op.details.get("extended_status")
    if isinstance(extended_status, int) or extended_status is None:
        if "extended_status" in op.details:
            data["extended_status"] = extended_status

    if not data:
        raise ValueError("update_status missing status/extended_status in op.details")

    client.patch_card(language, op.lingq_pk, data)


def apply_sync_plan(
    plan: SyncPlan, client: LingQClient, checkpoint: Checkpoint
) -> ApplyResult:
    """Apply a SyncPlan, resuming from a checkpoint.

    Note: apply_sync_plan will persist checkpoints only if the plan object exposes
    a string attribute named 'profile_name'. This keeps the function signature
    stable while allowing per-profile checkpoint files.
    """

    if not checkpoint.run_id:
        checkpoint.run_id = _new_run_id()

    result = ApplyResult()
    ordered = _ordered_operations(plan)
    start_idx = max(0, int(checkpoint.last_processed_index))

    profile_name = getattr(plan, "profile_name", None)
    if not isinstance(profile_name, str) or not profile_name.strip():
        profile_name = None

    completed = set(checkpoint.completed_ops)

    for exec_idx in range(start_idx, len(ordered)):
        _, op = ordered[exec_idx]
        op_id = _op_identifier(op)

        try:
            if op_id in completed:
                result.skipped_count += 1
            elif op.op_type in {OP_CONFLICT, OP_SKIP}:
                result.skipped_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_CREATE_LINGQ:
                _apply_create_lingq(op, client)
                result.success_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_UPDATE_HINTS:
                _apply_update_hints(op, client)
                result.success_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_UPDATE_STATUS:
                _apply_update_status(op, client)
                result.success_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_LINK and _is_anki_runtime():
                changed = _apply_link(op)
                if changed:
                    result.success_count += 1
                else:
                    result.skipped_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_CREATE_ANKI and _is_anki_runtime():
                created = _apply_create_anki(op)
                if created:
                    result.success_count += 1
                else:
                    result.skipped_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type == OP_RESCHEDULE_ANKI and _is_anki_runtime():
                changed = _apply_reschedule_anki(op)
                if changed:
                    result.success_count += 1
                else:
                    result.skipped_count += 1
                checkpoint.completed_ops.append(op_id)
                completed.add(op_id)
            elif op.op_type in {OP_LINK, OP_CREATE_ANKI, OP_RESCHEDULE_ANKI}:
                # Anki-specific operations are intentionally stubbed; no aqt imports.
                result.skipped_count += 1
                result.errors.append(
                    f"Skipped {op.op_type}: requires Anki runtime (aqt)"
                )
            else:
                result.skipped_count += 1
                result.errors.append(f"Skipped unknown op_type={op.op_type}")

        except Exception as e:
            result.error_count += 1
            result.errors.append(f"{op.op_type} failed for {op.term!r}: {e}")

            # Still mark as processed so we don't get stuck retrying forever.
            checkpoint.completed_ops.append(op_id)
            completed.add(op_id)

        finally:
            checkpoint.last_processed_index = exec_idx + 1
            if profile_name:
                save_checkpoint(profile_name, checkpoint)

    return result

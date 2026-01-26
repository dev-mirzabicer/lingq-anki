from __future__ import annotations

# pyright: reportMissingImports=false

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from diff_engine import (
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
from lingq_client import LingQClient


_LOGGER = logging.getLogger(__name__)


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

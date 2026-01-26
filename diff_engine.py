from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    # For now, return empty SyncPlan
    return SyncPlan()

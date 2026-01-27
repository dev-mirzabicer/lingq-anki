from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Type, TypeVar


class _StrEnum(str, Enum):
    """Enum with stable string values for JSON serialization."""

    def __str__(self) -> str:
        return str(self.value)


class AmbiguousMatchPolicy(_StrEnum):
    """How to handle ambiguous matches when linking Anki notes to LingQ cards."""

    UNSET = "UNSET"
    ASK = "ASK"
    SKIP = "SKIP"
    CONSERVATIVE_SKIP = "CONSERVATIVE_SKIP"
    AGGRESSIVE_LINK_FIRST = "AGGRESSIVE_LINK_FIRST"


class TranslationAggregationPolicy(_StrEnum):
    """How to aggregate multiple Anki translations for LingQ hint updates."""

    UNSET = "UNSET"
    ASK = "ASK"
    SKIP = "SKIP"
    MAX = "MAX"
    MIN = "MIN"
    AVG = "AVG"


class SchedulingWritePolicy(_StrEnum):
    """Whether rescheduling writes to Anki should be enabled for this run."""

    UNSET = "UNSET"
    INHERIT_PROFILE = "INHERIT_PROFILE"
    FORCE_ON = "FORCE_ON"
    FORCE_OFF = "FORCE_OFF"


@dataclass
class RunOptions:
    """Per-run options that control sync behavior.

    These options are intentionally separate from persisted config profiles.
    """

    ambiguous_match_policy: AmbiguousMatchPolicy = AmbiguousMatchPolicy.UNSET
    translation_aggregation_policy: TranslationAggregationPolicy = (
        TranslationAggregationPolicy.UNSET
    )
    scheduling_write_policy: SchedulingWritePolicy = SchedulingWritePolicy.UNSET


RUN_OPTIONS_SCHEMA_VERSION = 1


TEnum = TypeVar("TEnum", bound=Enum)


def _parse_enum(enum_cls: Type[TEnum], raw: Any, *, default: TEnum) -> TEnum:
    """Parse a string into an enum value.

    - Stores enum values as strings.
    - Unknown strings fall back to `default`.
    """

    if isinstance(raw, enum_cls):
        return raw
    if isinstance(raw, str):
        # Prefer value lookup, but accept member names too.
        try:
            return enum_cls(raw)  # type: ignore[call-arg]
        except Exception:
            member = getattr(enum_cls, "__members__", {}).get(raw)
            if member is not None:
                return member
    return default


def validate_run_options(opts: RunOptions) -> List[str]:
    errors: List[str] = []

    if not isinstance(opts, RunOptions):
        return ["Run options must be a RunOptions instance."]

    amb = opts.ambiguous_match_policy
    if not isinstance(amb, AmbiguousMatchPolicy) or amb == AmbiguousMatchPolicy.UNSET:
        errors.append(
            "Ambiguous match policy must be selected (ASK/SKIP/CONSERVATIVE_SKIP/AGGRESSIVE_LINK_FIRST)."
        )

    agg = opts.translation_aggregation_policy
    if (
        not isinstance(agg, TranslationAggregationPolicy)
        or agg == TranslationAggregationPolicy.UNSET
    ):
        errors.append(
            "Translation aggregation policy must be selected (ASK/SKIP/MAX/MIN/AVG)."
        )

    sched = opts.scheduling_write_policy
    allowed_sched = {
        SchedulingWritePolicy.INHERIT_PROFILE,
        SchedulingWritePolicy.FORCE_ON,
        SchedulingWritePolicy.FORCE_OFF,
    }
    if not isinstance(sched, SchedulingWritePolicy) or sched not in allowed_sched:
        errors.append(
            "Scheduling write policy must be one of INHERIT_PROFILE/FORCE_ON/FORCE_OFF."
        )

    return errors


def run_options_to_dict(opts: RunOptions) -> Dict[str, Any]:
    return {
        "schema_version": RUN_OPTIONS_SCHEMA_VERSION,
        "ambiguous_match_policy": str(opts.ambiguous_match_policy.value),
        "translation_aggregation_policy": str(
            opts.translation_aggregation_policy.value
        ),
        "scheduling_write_policy": str(opts.scheduling_write_policy.value),
    }


def dict_to_run_options(d: Mapping[str, Any]) -> RunOptions:
    src: Mapping[str, Any] = d if isinstance(d, Mapping) else {}
    return RunOptions(
        ambiguous_match_policy=_parse_enum(
            AmbiguousMatchPolicy,
            src.get("ambiguous_match_policy"),
            default=AmbiguousMatchPolicy.UNSET,
        ),
        translation_aggregation_policy=_parse_enum(
            TranslationAggregationPolicy,
            src.get("translation_aggregation_policy"),
            default=TranslationAggregationPolicy.UNSET,
        ),
        scheduling_write_policy=_parse_enum(
            SchedulingWritePolicy,
            src.get("scheduling_write_policy"),
            default=SchedulingWritePolicy.UNSET,
        ),
    )

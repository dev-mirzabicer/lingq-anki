"""Dataclass-based configuration schema for LingQ-Anki sync.

This module defines the in-file (persisted) configuration model used to
describe sync profiles and their field mappings.

Run-time policies such as conflict resolution and polysemy handling are
intentionally NOT stored here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class HintConfig:
    """Locale-related settings used when generating hints.

    This is a small, explicit container for locale strings (e.g. "en", "sv").
    Profiles may choose to inline locale fields directly instead of using this
    type; it exists to keep locale intent clear and extensible.
    """

    lingq_language: Optional[str] = None
    meaning_locale: Optional[str] = None


@dataclass
class IdentityFields:
    """Field names that uniquely identify a LingQ item in Anki notes.

    These are stored on Anki notes to allow stable round-tripping between
    LingQ items and Anki notes across sync runs.
    """

    pk_field: str = "LingQ_PK"
    canonical_term_field: str = "LingQ_TermCanonical"


@dataclass
class LingqToAnkiMapping:
    """Mapping definition for writing LingQ data into Anki.

    - note_type: Anki note type to create/update (e.g. "Basic").
    - deck_name: Optional Anki deck name to create notes in.
    - field_mapping: LingQ field name -> Anki field name.
    - identity_fields: Anki field names used for identity tracking.
    """

    note_type: str
    deck_name: Optional[str] = None
    field_mapping: Dict[str, str] = field(default_factory=dict)
    identity_fields: IdentityFields = field(default_factory=IdentityFields)


@dataclass
class AnkiToLingqMapping:
    """Mapping definition for writing Anki data back into LingQ.

    - term_field: Name of the Anki field containing the term.
    - translation_fields: Names of Anki fields containing translations.
    - primary_card_template: Optional card template name used as primary.
    - fragment_field: Optional Anki field containing example usage/source text.
    """

    term_field: str
    translation_fields: List[str] = field(default_factory=list)
    primary_card_template: Optional[str] = None
    fragment_field: Optional[str] = None


@dataclass
class Profile:
    """A single LingQ-Anki sync profile.

    A profile groups together locale/language choices, the LingQ API token, and
    the bidirectional mappings required to sync between LingQ and Anki.
    """

    name: str
    lingq_language: str
    meaning_locale: str
    lingq_to_anki: LingqToAnkiMapping
    anki_to_lingq: AnkiToLingqMapping
    api_token: str = ""
    # Backward compat: legacy configs/tests may still set `api_token_ref`.
    # This is no longer persisted; `api_token` is the canonical field.
    api_token_ref: str = ""
    enable_scheduling_writes: bool = False


@dataclass
class Config:
    """Top-level persisted configuration container.

    - config_version: Schema version for forwards/backwards compatibility.
    - profiles: Named sync profiles.
    """

    config_version: int = 1
    profiles: List[Profile] = field(default_factory=list)

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from config_model import (
    AnkiToLingqMapping,
    Config,
    IdentityFields,
    LingqToAnkiMapping,
    Profile,
)

# pyright: reportMissingImports=false
import importlib

aqt = importlib.import_module("aqt")
mw = aqt.mw


def config_to_dict(config: Config) -> dict:
    return asdict(config)


def dict_to_config(data: dict) -> Config:
    if not isinstance(data, dict) or not data:
        return Config()

    config_version = data.get("config_version", 1)
    if not isinstance(config_version, int):
        config_version = 1

    raw_profiles = data.get("profiles", [])
    if not isinstance(raw_profiles, list):
        raw_profiles = []

    profiles: List[Profile] = []
    for p in raw_profiles:
        if not isinstance(p, dict):
            raise TypeError("profile must be a dict")

        l2a_data = p["lingq_to_anki"]
        if not isinstance(l2a_data, dict):
            raise TypeError("lingq_to_anki must be a dict")

        identity_data = l2a_data.get("identity_fields", {})
        if not isinstance(identity_data, dict):
            identity_data = {}
        identity_fields = IdentityFields(**identity_data)

        lingq_to_anki = LingqToAnkiMapping(
            note_type=str(l2a_data["note_type"]),
            field_mapping=_coerce_str_dict(l2a_data.get("field_mapping", {})),
            identity_fields=identity_fields,
        )

        a2l_data = p["anki_to_lingq"]
        if not isinstance(a2l_data, dict):
            raise TypeError("anki_to_lingq must be a dict")

        translation_fields = a2l_data.get("translation_fields", [])
        if not isinstance(translation_fields, list):
            translation_fields = []

        anki_to_lingq = AnkiToLingqMapping(
            term_field=str(a2l_data["term_field"]),
            translation_fields=[str(x) for x in translation_fields],
            primary_card_template=(
                None
                if a2l_data.get("primary_card_template") is None
                else str(a2l_data.get("primary_card_template"))
            ),
        )

        profiles.append(
            Profile(
                name=str(p["name"]),
                lingq_language=str(p["lingq_language"]),
                meaning_locale=str(p["meaning_locale"]),
                api_token_ref=str(p["api_token_ref"]),
                lingq_to_anki=lingq_to_anki,
                anki_to_lingq=anki_to_lingq,
                enable_scheduling_writes=bool(p.get("enable_scheduling_writes", False)),
            )
        )

    return Config(config_version=config_version, profiles=profiles)


def load_config() -> Config:
    try:
        data = mw.addonManager.getConfig(__name__)
    except Exception:
        return Config()

    try:
        return dict_to_config(data or {})
    except Exception:
        return Config()


def save_config(config: Config) -> None:
    mw.addonManager.writeConfig(__name__, config_to_dict(config))


def _coerce_str_dict(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}

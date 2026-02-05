from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

try:
    from .config_model import (
        AnkiToLingqMapping,
        Config,
        IdentityFields,
        LingqToAnkiMapping,
        Profile,
    )
except ImportError:
    from config_model import (  # type: ignore[no-redef]
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


def _legacy_addon_root_name() -> str:
    """Legacy add-on config key derivation (root package).

    Historically we derived the Anki add-on config key from the import package.
    This can break when the add-on folder name differs from the Python package
    name (e.g. hyphens), causing persistence to read/write the wrong bucket.
    """

    package = __package__ or ""
    if package:
        return package.split(".", 1)[0]

    name = __name__ or ""
    if name:
        return name.split(".", 1)[0]

    return "lingq_anki"


def _addon_folder_name() -> str:
    """Return the real Anki add-on folder name used for config storage."""

    try:
        return Path(__file__).resolve().parent.name
    except Exception:
        return ""


_LEGACY_ADDON_CONFIG_KEY = _legacy_addon_root_name()
_ADDON_CONFIG_KEY = _addon_folder_name() or _LEGACY_ADDON_CONFIG_KEY


def _migrate_addon_config_key_if_needed() -> None:
    """Best-effort migration from legacy config bucket to the real folder key.

    If the legacy key differs from the folder key, merge legacy config into the
    new bucket. Preserve `ui_state.last_run_options` (per-profile) so run option
    persistence survives upgrades.
    """

    old_key = str(_LEGACY_ADDON_CONFIG_KEY or "").strip()
    new_key = str(_ADDON_CONFIG_KEY or "").strip()
    if not old_key or not new_key or old_key == new_key:
        return

    try:
        old_data = mw.addonManager.getConfig(old_key)
    except Exception:
        old_data = None
    if not isinstance(old_data, dict) or not old_data:
        return

    try:
        new_data = mw.addonManager.getConfig(new_key)
    except Exception:
        new_data = None
    if not isinstance(new_data, dict):
        new_data = {}

    merged: Dict[str, Any] = dict(new_data)
    for k, v in old_data.items():
        if k not in merged:
            merged[k] = v

    # Preserve/merge ui_state.last_run_options (fill missing profile entries).
    old_ui = old_data.get("ui_state")
    if isinstance(old_ui, dict):
        old_last = old_ui.get("last_run_options")
        if isinstance(old_last, dict) and old_last:
            new_ui = merged.get("ui_state")
            if not isinstance(new_ui, dict):
                new_ui = {}
            new_last = new_ui.get("last_run_options")
            if not isinstance(new_last, dict):
                new_last = {}
            for profile_name, payload in old_last.items():
                if profile_name not in new_last and isinstance(payload, dict):
                    new_last[profile_name] = payload
            new_ui["last_run_options"] = new_last
            merged["ui_state"] = new_ui

    if merged == new_data:
        return

    try:
        mw.addonManager.writeConfig(new_key, merged)
    except Exception:
        return


def config_to_dict(config: Config) -> dict:
    data = asdict(config)

    # Migration/output schema: persist the actual token under `api_token`.
    # Keep `api_token_ref` as a runtime-only backward-compat field.
    raw_profiles = data.get("profiles")
    if isinstance(raw_profiles, list):
        for p in raw_profiles:
            if not isinstance(p, dict):
                continue
            if "api_token" not in p and "api_token_ref" in p:
                p["api_token"] = p.get("api_token_ref", "")
            p.pop("api_token_ref", None)

    return data


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

        deck_raw = l2a_data.get("deck_name")
        deck_name = None
        if deck_raw is not None:
            deck_name = str(deck_raw).strip() or None

        lingq_to_anki = LingqToAnkiMapping(
            note_type=str(l2a_data["note_type"]),
            deck_name=deck_name,
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
            fragment_field=(
                None
                if a2l_data.get("fragment_field") is None
                else str(a2l_data.get("fragment_field"))
            ),
        )

        api_token_value = p.get("api_token")
        if api_token_value is None:
            api_token_value = p.get("api_token_ref", "")

        profiles.append(
            Profile(
                name=str(p["name"]),
                lingq_language=str(p["lingq_language"]),
                meaning_locale=str(p["meaning_locale"]),
                lingq_to_anki=lingq_to_anki,
                anki_to_lingq=anki_to_lingq,
                api_token=str(api_token_value or ""),
                # Backward compat: allow older code/tests to keep using this.
                api_token_ref=str(api_token_value or ""),
                enable_scheduling_writes=bool(p.get("enable_scheduling_writes", False)),
            )
        )

    return Config(config_version=config_version, profiles=profiles)


def load_config() -> Config:
    try:
        _migrate_addon_config_key_if_needed()
    except Exception:
        pass

    try:
        data = mw.addonManager.getConfig(_ADDON_CONFIG_KEY)
    except Exception:
        return Config()

    try:
        config = dict_to_config(data or {})

        # Backwards-compatible migration: if loaded config only had
        # `api_token_ref`, rewrite it back as `api_token`.
        raw_profiles = (data or {}).get("profiles") if isinstance(data, dict) else None
        migrate_tokens = False
        if isinstance(raw_profiles, list):
            for p in raw_profiles:
                if not isinstance(p, dict):
                    continue
                if "api_token" not in p and "api_token_ref" in p:
                    migrate_tokens = True
                    break
        if migrate_tokens:
            try:
                save_config(config)
            except Exception:
                pass

        return config
    except Exception:
        return Config()


def save_config(config: Config) -> None:
    # Preserve any extra keys stored in the add-on config dict (e.g. UI state).
    new_data = config_to_dict(config)
    try:
        existing = mw.addonManager.getConfig(_ADDON_CONFIG_KEY)
    except Exception:
        existing = None

    if isinstance(existing, dict):
        for k, v in existing.items():
            if k not in new_data:
                new_data[k] = v

    mw.addonManager.writeConfig(_ADDON_CONFIG_KEY, new_data)


def _coerce_str_dict(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items()}

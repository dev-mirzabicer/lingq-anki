# pyright: reportMissingImports=false
from __future__ import annotations

_IN_ANKI = False
try:
    import aqt

    _IN_ANKI = aqt.mw is not None
except ImportError:
    pass

if _IN_ANKI:
    from aqt import gui_hooks, mw

    try:
        from . import sync_dialog
    except ImportError:
        import sync_dialog  # type: ignore[no-redef]

    try:
        from . import config_dialog
    except ImportError:
        import config_dialog  # type: ignore[no-redef]

    def show_sync_dialog() -> None:
        dialog = sync_dialog.SyncDialog(mw)
        dialog.exec()

    def show_config_dialog() -> None:
        dialog = config_dialog.ConfigDialog(mw)
        dialog.exec()

    def _register_menu_action() -> None:
        action = mw.form.menuTools.addAction("LingQ Sync...")
        action.triggered.connect(show_sync_dialog)
        mw.addonManager.setConfigAction(__name__, show_config_dialog)

    gui_hooks.main_window_did_init.append(_register_menu_action)

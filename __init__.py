# pyright: reportMissingImports=false
import importlib

aqt = importlib.import_module("aqt")
gui_hooks = aqt.gui_hooks
mw = aqt.mw

from .sync_dialog import SyncDialog


def show_sync_dialog() -> None:
    dialog = SyncDialog(mw)
    dialog.exec()


def _register_menu_action() -> None:
    action = mw.form.menuTools.addAction("LingQ Sync...")
    action.triggered.connect(show_sync_dialog)


gui_hooks.main_window_did_init.append(_register_menu_action)

import sys
from unittest.mock import MagicMock

mock_aqt = MagicMock()
mock_aqt.mw = None  # Set to None so add-on init is skipped during tests
mock_aqt.gui_hooks = MagicMock()
mock_aqt.qt = MagicMock()

sys.modules["aqt"] = mock_aqt
sys.modules["aqt.qt"] = mock_aqt.qt
sys.modules["aqt.gui_hooks"] = mock_aqt.gui_hooks

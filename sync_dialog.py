# pyright: reportMissingImports=false
from __future__ import annotations

import importlib
import threading
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from config_model import Profile
    from diff_engine import SyncPlan

try:
    from .config_dialog import ConfigDialog
except ImportError:
    from config_dialog import ConfigDialog

try:
    from .run_options import (
        AmbiguousMatchPolicy,
        TranslationAggregationPolicy,
        SchedulingWritePolicy,
        RunOptions,
        ProgressAuthorityPolicy,
        validate_run_options,
        run_options_to_dict,
        dict_to_run_options,
    )
except ImportError:
    from run_options import (
        AmbiguousMatchPolicy,
        TranslationAggregationPolicy,
        SchedulingWritePolicy,
        RunOptions,
        ProgressAuthorityPolicy,
        validate_run_options,
        run_options_to_dict,
        dict_to_run_options,
    )

try:
    from .diff_engine import compute_sync_plan
    from .lingq_client import LingQApiError, LingQClient
except ImportError:
    from diff_engine import compute_sync_plan  # type: ignore[no-redef]
    from lingq_client import LingQApiError, LingQClient  # type: ignore[no-redef]

try:
    from .apply_engine import (
        Checkpoint,
        apply_sync_plan,
        clear_checkpoint,
        load_checkpoint,
    )
except ImportError:
    from apply_engine import (  # type: ignore[no-redef]
        Checkpoint,
        apply_sync_plan,
        clear_checkpoint,
        load_checkpoint,
    )

qt = importlib.import_module("aqt.qt")
QDialog = qt.QDialog
QVBoxLayout = qt.QVBoxLayout
QHBoxLayout = qt.QHBoxLayout
QGridLayout = qt.QGridLayout
QTextEdit = qt.QTextEdit
QPushButton = qt.QPushButton
QLabel = qt.QLabel
QComboBox = qt.QComboBox
QProgressBar = qt.QProgressBar
QTableWidget = qt.QTableWidgetItem
QTableWidgetItem = qt.QTableWidgetItem
QHeaderView = qt.QHeaderView
QFrame = qt.QFrame
QSizePolicy = qt.QSizePolicy
QFont = qt.QFont
Qt = qt.Qt
QAbstractItemView = qt.QAbstractItemView
QScrollArea = qt.QScrollArea
QWidget = qt.QWidget
QMessageBox = qt.QMessageBox
QRadioButton = qt.QRadioButton
QButtonGroup = qt.QButtonGroup

# Import table widget separately for clarity
_QTableWidget = qt.QTableWidget


class SyncDialog(QDialog):
    """LingQ-Anki sync dialog with profile selection, dry-run, apply, and results display."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LingQ Sync")
        self.resize(720, 680)
        self.setMinimumSize(600, 500)

        self._current_plan: Optional["SyncPlan"] = None
        self._current_conflicts: List[Any] = []
        self._profiles: List["Profile"] = []
        self._run_options: RunOptions = self._get_safe_default_run_options()

        self._setup_ui()
        self._load_profiles()
        self._update_button_states()

    def _setup_ui(self) -> None:
        """Build the complete dialog layout."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setSpacing(0)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # === Scrollable Content Area ===
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: palette(window);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: palette(mid);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: palette(dark);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Header Section ===
        header = self._create_header_section()
        main_layout.addLayout(header)

        # === Separator ===
        main_layout.addWidget(self._create_separator())

        # === Profile Selection ===
        profile_section = self._create_profile_section()
        main_layout.addLayout(profile_section)

        # === Run Options Section ===
        run_options_section = self._create_run_options_section()
        main_layout.addLayout(run_options_section)

        # === Action Buttons ===
        action_section = self._create_action_section()
        main_layout.addLayout(action_section)

        # === Separator ===
        main_layout.addWidget(self._create_separator())

        # === Summary Section ===
        summary_section = self._create_summary_section()
        main_layout.addLayout(summary_section)

        # === Conflicts Section ===
        conflicts_section = self._create_conflicts_section()
        main_layout.addLayout(conflicts_section)

        # === Log Section ===
        log_section = self._create_log_section()
        main_layout.addLayout(log_section, stretch=1)

        # Add stretch at bottom to push content up when there's extra space
        main_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        outer_layout.addWidget(scroll_area, stretch=1)

        # === Progress Section (fixed at bottom) ===
        progress_container = QWidget()
        progress_container.setStyleSheet("""
            QWidget {
                background: palette(window);
                border-top: 1px solid palette(mid);
            }
        """)
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(20, 12, 20, 12)
        progress_layout.setSpacing(8)

        progress_section = self._create_progress_section()
        progress_layout.addLayout(progress_section)

        outer_layout.addWidget(progress_container)

    def _create_header_section(self) -> QHBoxLayout:
        """Create the title header."""
        layout = QHBoxLayout()

        title = QLabel("LingQ Sync")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: palette(link);")

        subtitle = QLabel("Synchronize your vocabulary between LingQ and Anki")
        subtitle.setStyleSheet(
            "color: palette(window-text); font-size: 12px; opacity: 0.7;"
        )

        title_layout = QVBoxLayout()
        title_layout.setSpacing(4)
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        layout.addLayout(title_layout)
        layout.addStretch()

        return layout

    def _create_profile_section(self) -> QHBoxLayout:
        """Create profile selector dropdown."""
        layout = QHBoxLayout()

        profile_label = QLabel("Profile:")
        profile_label.setStyleSheet("font-weight: 600; color: palette(window-text);")

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(250)
        self.profile_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(base);
                color: palette(text);
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: palette(highlight);
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: palette(base);
                color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
        """)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        self.manage_profiles_btn = QPushButton("Manage...")
        self.manage_profiles_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 14px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 6px;
                font-weight: 600;
                color: palette(button-text);
                font-size: 12px;
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(dark);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
        """)
        self.manage_profiles_btn.clicked.connect(self._open_config_dialog)

        layout.addWidget(profile_label)
        layout.addWidget(self.profile_combo)
        layout.addWidget(self.manage_profiles_btn)
        layout.addStretch()

        return layout

    def _create_run_options_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        header = QLabel("Run Options")
        header.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: palette(window-text);"
        )
        layout.addWidget(header)

        options_frame = QFrame()
        options_frame.setStyleSheet("""
            QFrame {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
                padding: 12px;
            }
        """)

        options_layout = QVBoxLayout(options_frame)
        options_layout.setSpacing(12)
        options_layout.setContentsMargins(16, 12, 16, 12)

        dropdown_style = """
            QComboBox {
                padding: 6px 10px;
                border: 1px solid palette(mid);
                border-radius: 5px;
                background: palette(window);
                color: palette(text);
                font-size: 12px;
                min-width: 220px;
            }
            QComboBox:hover {
                border-color: palette(highlight);
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 6px;
            }
            QComboBox QAbstractItemView {
                background: palette(base);
                color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
        """

        self.ambiguous_combo = QComboBox()
        self.ambiguous_combo.setStyleSheet(dropdown_style)
        self.ambiguous_combo.addItem("Choose...", AmbiguousMatchPolicy.UNSET)
        self.ambiguous_combo.addItem(
            "Ask me (show conflicts)", AmbiguousMatchPolicy.ASK
        )
        self.ambiguous_combo.addItem("Skip", AmbiguousMatchPolicy.SKIP)
        self.ambiguous_combo.addItem(
            "Conservative skip", AmbiguousMatchPolicy.CONSERVATIVE_SKIP
        )
        self.ambiguous_combo.addItem(
            "Aggressive: link first (unsafe)",
            AmbiguousMatchPolicy.AGGRESSIVE_LINK_FIRST,
        )
        self.ambiguous_combo.currentIndexChanged.connect(self._on_run_option_changed)

        ambiguous_row = self._create_option_row(
            "Ambiguous matches:",
            "How to handle terms that match multiple cards",
            self.ambiguous_combo,
        )
        options_layout.addLayout(ambiguous_row)

        self.aggregation_combo = QComboBox()
        self.aggregation_combo.setStyleSheet(dropdown_style)
        self.aggregation_combo.addItem("Choose...", TranslationAggregationPolicy.UNSET)
        self.aggregation_combo.addItem("Ask me", TranslationAggregationPolicy.ASK)
        self.aggregation_combo.addItem("Skip", TranslationAggregationPolicy.SKIP)
        self.aggregation_combo.addItem(
            "MIN (shortest)", TranslationAggregationPolicy.MIN
        )
        self.aggregation_combo.addItem(
            "MAX (longest)", TranslationAggregationPolicy.MAX
        )
        self.aggregation_combo.addItem(
            "AVG (median length)", TranslationAggregationPolicy.AVG
        )
        self.aggregation_combo.currentIndexChanged.connect(self._on_run_option_changed)

        aggregation_row = self._create_option_row(
            "Multi-translation:",
            "How to pick a hint when Anki has multiple translations",
            self.aggregation_combo,
        )
        options_layout.addLayout(aggregation_row)

        self.scheduling_combo = QComboBox()
        self.scheduling_combo.setStyleSheet(dropdown_style)
        self.scheduling_combo.addItem("Choose...", SchedulingWritePolicy.UNSET)
        self.scheduling_combo.addItem(
            "Inherit from profile", SchedulingWritePolicy.INHERIT_PROFILE
        )
        self.scheduling_combo.addItem("Force ON", SchedulingWritePolicy.FORCE_ON)
        self.scheduling_combo.addItem("Force OFF", SchedulingWritePolicy.FORCE_OFF)
        self.scheduling_combo.currentIndexChanged.connect(self._on_run_option_changed)

        scheduling_row = self._create_option_row(
            "Scheduling writes:",
            "Override profile setting for Anki rescheduling",
            self.scheduling_combo,
        )
        options_layout.addLayout(scheduling_row)

        self.progress_combo = QComboBox()
        self.progress_combo.setStyleSheet(dropdown_style)
        self.progress_combo.addItem(
            "Automatic (recommended)", ProgressAuthorityPolicy.AUTOMATIC
        )
        self.progress_combo.addItem(
            "Prefer Anki (ignore LingQ review progress)",
            ProgressAuthorityPolicy.PREFER_ANKI,
        )
        self.progress_combo.addItem(
            "Prefer LingQ (can reschedule even if Anki reviewed)",
            ProgressAuthorityPolicy.PREFER_LINGQ,
        )
        self.progress_combo.currentIndexChanged.connect(self._on_run_option_changed)

        progress_row = self._create_option_row(
            "Progress authority:",
            "Which app should win for progress decisions when they disagree",
            self.progress_combo,
        )
        options_layout.addLayout(progress_row)

        self.run_options_warning = QLabel("")
        self.run_options_warning.setStyleSheet(
            "color: #ef4444; font-size: 11px; font-weight: 500; background: transparent; border: none;"
        )
        self.run_options_warning.setWordWrap(True)
        self.run_options_warning.hide()
        options_layout.addWidget(self.run_options_warning)

        layout.addWidget(options_frame)

        return layout

    def _create_option_row(
        self, label_text: str, help_text: str, combo: QComboBox
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        # Wrap labels in a QWidget for explicit width control
        try:
            QWidget = qt.QWidget
        except AttributeError:
            QWidget = importlib.import_module("aqt.qt").QWidget

        label_widget = QWidget()
        label_widget.setMinimumWidth(280)
        label_container = QVBoxLayout(label_widget)
        label_container.setSpacing(2)
        label_container.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setStyleSheet(
            "font-weight: 600; font-size: 12px; color: palette(window-text); background: transparent; border: none;"
        )
        label_container.addWidget(label)

        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet(
            "font-size: 10px; color: palette(window-text); opacity: 0.65; background: transparent; border: none;"
        )
        label_container.addWidget(help_label)

        row.addWidget(label_widget, stretch=1)
        row.addWidget(combo, stretch=0)

        return row

    def _get_safe_default_run_options(self) -> RunOptions:
        return RunOptions(
            ambiguous_match_policy=AmbiguousMatchPolicy.ASK,
            translation_aggregation_policy=TranslationAggregationPolicy.ASK,
            scheduling_write_policy=SchedulingWritePolicy.INHERIT_PROFILE,
            progress_authority_policy=ProgressAuthorityPolicy.AUTOMATIC,
        )

    def _on_run_option_changed(self) -> None:
        self._run_options = RunOptions(
            ambiguous_match_policy=self.ambiguous_combo.currentData(),
            translation_aggregation_policy=self.aggregation_combo.currentData(),
            scheduling_write_policy=self.scheduling_combo.currentData(),
            progress_authority_policy=self.progress_combo.currentData(),
        )
        self._update_button_states()
        self._save_run_options_for_profile()

    def _get_run_options_meta_key(self, profile_name: str) -> str:
        return f"lingq_sync:last_run_options:{profile_name}"

    def _get_addon_config_key(self) -> str:
        # Prefer the shared config_manager key to avoid package/submodule issues.
        try:
            try:
                from . import config_manager
            except ImportError:
                import config_manager  # type: ignore
            key = getattr(config_manager, "_ADDON_CONFIG_KEY", None)
            if isinstance(key, str) and key.strip():
                return key.strip()
        except Exception:
            pass

        package = __package__ or ""
        if package:
            return package.split(".", 1)[0]
        name = __name__ or ""
        return name.split(".", 1)[0] if name else "lingq_sync"

    def _addon_config_get(self) -> Dict[str, Any]:
        try:
            from aqt import mw

            if not mw or not getattr(mw, "addonManager", None):
                return {}
            data = mw.addonManager.getConfig(self._get_addon_config_key())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _addon_config_set(self, data: Dict[str, Any]) -> None:
        try:
            from aqt import mw

            if not mw or not getattr(mw, "addonManager", None):
                return
            if not isinstance(data, dict):
                return
            mw.addonManager.writeConfig(self._get_addon_config_key(), data)
        except Exception:
            return

    def _fill_run_options_defaults(self, opts: RunOptions) -> RunOptions:
        """Fill missing/UNSET fields from safe defaults.

        This prevents older saved dicts (or partial state) from forcing the user
        to re-select options repeatedly.
        """

        defaults = self._get_safe_default_run_options()
        if (
            getattr(opts, "ambiguous_match_policy", AmbiguousMatchPolicy.UNSET)
            == AmbiguousMatchPolicy.UNSET
        ):
            opts.ambiguous_match_policy = defaults.ambiguous_match_policy
        if (
            getattr(
                opts,
                "translation_aggregation_policy",
                TranslationAggregationPolicy.UNSET,
            )
            == TranslationAggregationPolicy.UNSET
        ):
            opts.translation_aggregation_policy = (
                defaults.translation_aggregation_policy
            )
        if (
            getattr(opts, "scheduling_write_policy", SchedulingWritePolicy.UNSET)
            == SchedulingWritePolicy.UNSET
        ):
            opts.scheduling_write_policy = defaults.scheduling_write_policy
        if not isinstance(
            getattr(opts, "progress_authority_policy", None), ProgressAuthorityPolicy
        ):
            opts.progress_authority_policy = defaults.progress_authority_policy
        return opts

    def _pm_meta_get(self, key: str, default=None):
        try:
            from aqt import mw

            if not mw or not getattr(mw, "pm", None):
                return default
            pm = mw.pm
            meta = getattr(pm, "meta", None)
            if isinstance(meta, dict):
                return meta.get(key, default)
            profile = getattr(pm, "profile", None)
            if isinstance(profile, dict):
                return profile.get("meta", {}).get(key, default)
        except Exception:
            return default
        return default

    def _pm_meta_set(self, key: str, value) -> None:
        try:
            from aqt import mw

            if not mw or not getattr(mw, "pm", None):
                return
            pm = mw.pm
            meta = getattr(pm, "meta", None)
            if isinstance(meta, dict):
                meta[key] = value
                return
            profile = getattr(pm, "profile", None)
            if isinstance(profile, dict):
                profile_meta = profile.get("meta")
                if isinstance(profile_meta, dict):
                    profile_meta[key] = value
                else:
                    profile["meta"] = {key: value}
        except Exception:
            return

    def _save_run_options_for_profile(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            return

        payload = run_options_to_dict(self._run_options)

        # Prefer add-on config persistence (survives restarts, and survives ConfigDialog saves).
        config = self._addon_config_get()
        ui_state = config.get("ui_state") if isinstance(config, dict) else None
        if not isinstance(ui_state, dict):
            ui_state = {}
        last = ui_state.get("last_run_options")
        if not isinstance(last, dict):
            last = {}
        last[str(profile.name)] = payload
        ui_state["last_run_options"] = last
        config["ui_state"] = ui_state
        self._addon_config_set(config)

        # Back-compat: also attempt profile meta.
        key = self._get_run_options_meta_key(profile.name)
        self._pm_meta_set(key, payload)

    def _load_run_options_for_profile(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            self._run_options = self._get_safe_default_run_options()
            self._sync_combos_from_run_options()
            return

        loaded_opts: Optional[RunOptions] = None

        # 1) Try add-on config ui_state
        try:
            config = self._addon_config_get()
            ui_state = config.get("ui_state") if isinstance(config, dict) else None
            last = (
                ui_state.get("last_run_options") if isinstance(ui_state, dict) else None
            )
            saved = last.get(str(profile.name)) if isinstance(last, dict) else None
            if saved:
                loaded_opts = dict_to_run_options(saved)
        except Exception:
            loaded_opts = None

        # 2) Fallback: profile meta
        if loaded_opts is None:
            key = self._get_run_options_meta_key(profile.name)
            saved = self._pm_meta_get(key, None)
            if saved:
                try:
                    loaded_opts = dict_to_run_options(saved)
                except Exception:
                    loaded_opts = None

        if loaded_opts is None:
            loaded_opts = self._get_safe_default_run_options()

        loaded_opts = self._fill_run_options_defaults(loaded_opts)

        self._run_options = loaded_opts
        self._sync_combos_from_run_options()

    def _sync_combos_from_run_options(self) -> None:
        self._set_combo_by_data(
            self.ambiguous_combo, self._run_options.ambiguous_match_policy
        )
        self._set_combo_by_data(
            self.aggregation_combo, self._run_options.translation_aggregation_policy
        )
        self._set_combo_by_data(
            self.scheduling_combo, self._run_options.scheduling_write_policy
        )
        self._set_combo_by_data(
            self.progress_combo, self._run_options.progress_authority_policy
        )

    def _set_combo_by_data(self, combo: QComboBox, value) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentIndex(0)

    def _create_action_section(self) -> QHBoxLayout:
        """Create action buttons: Dry Run, Apply, Close."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Dry Run button
        self.dry_run_btn = QPushButton("Dry Run")
        try:
            self.dry_run_btn.setToolTip(
                "Compute a sync plan without making any changes."
            )
        except Exception:
            pass
        self.dry_run_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 6px;
                font-weight: 600;
                color: palette(button-text);
                font-size: 13px;
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(dark);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
            QPushButton:disabled {
                background: palette(window);
                color: palette(mid);
            }
        """)
        self.dry_run_btn.clicked.connect(self._on_dry_run)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        try:
            self.apply_btn.setToolTip(
                "Execute the sync plan (writes to Anki and LingQ). Requires a Dry Run first."
            )
        except Exception:
            pass
        self.apply_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: palette(highlight);
                border: none;
                border-radius: 6px;
                font-weight: 600;
                color: palette(highlighted-text);
                font-size: 13px;
            }
            QPushButton:hover {
                background: palette(highlight);
            }
            QPushButton:pressed {
                background: palette(highlight);
            }
            QPushButton:disabled {
                background: palette(mid);
                color: palette(midlight);
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply)

        # Self-check button
        self.self_check_btn = QPushButton("Self-check")
        try:
            self.self_check_btn.setToolTip(
                "Run quick diagnostics: profile loading, run options validation, and persistence."
            )
        except Exception:
            pass
        self.self_check_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 6px;
                font-weight: 600;
                color: palette(button-text);
                font-size: 13px;
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(dark);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
        """)
        self.self_check_btn.clicked.connect(self._on_self_check)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 6px;
                font-weight: 500;
                color: palette(window-text);
                font-size: 13px;
            }
            QPushButton:hover {
                background: palette(button);
                border-color: palette(dark);
            }
        """)
        close_btn.clicked.connect(self.close)

        layout.addWidget(self.dry_run_btn)
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.self_check_btn)
        layout.addStretch()
        layout.addWidget(close_btn)

        return layout

    def _create_summary_section(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header = QLabel("Summary")
        header.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: palette(window-text);"
        )
        layout.addWidget(header)

        stats_layout = QGridLayout()
        stats_layout.setSpacing(12)
        stats_layout.setColumnStretch(0, 1)
        stats_layout.setColumnStretch(1, 1)

        self._stat_labels: Dict[str, QLabel] = {}
        stats = [
            ("link", "Links", "#8b5cf6"),
            ("create_lingq", "Create (LingQ)", "#10b981"),
            ("create_anki", "Create (Anki)", "#06b6d4"),
            ("update_hints", "Updates", "#f59e0b"),
            ("reschedule_anki", "Reschedules", "#6366f1"),
            ("conflict", "Conflicts", "#ef4444"),
            ("skip", "Skips", "#9ca3af"),
        ]

        for idx, (key, label, color) in enumerate(stats):
            row = idx // 2
            col = idx % 2

            stat_widget, value_label = self._create_stat_widget(key, label, "0", color)
            self._stat_labels[key] = value_label
            stats_layout.addWidget(stat_widget, row, col)

        layout.addLayout(stats_layout)

        return layout

    def _create_stat_widget(
        self, key: str, label: str, value: str, color: str
    ) -> tuple[QFrame, QLabel]:
        frame = QFrame()
        frame.setMinimumHeight(70)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        frame.setStyleSheet(f"""
            QFrame {{
                background: palette(base);
                border: 1px solid palette(mid);
                border-left: 3px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName(f"stat_value_{key}")
        value_label.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {color}; background: transparent; border: none;"
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(label)
        name_label.setStyleSheet(
            "font-size: 11px; color: palette(window-text); background: transparent; border: none;"
        )
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(value_label)
        layout.addWidget(name_label)

        return frame, value_label

    def _create_conflicts_section(self) -> QVBoxLayout:
        """Create conflicts list display with Resolve button."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self.conflicts_header = QLabel("Conflicts (0)")
        self.conflicts_header.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: palette(window-text);"
        )
        header_layout.addWidget(self.conflicts_header)
        header_layout.addStretch()

        self.resolve_hint_label = QLabel("Select a conflict and click Resolve\u2026")
        self.resolve_hint_label.setStyleSheet(
            "font-size: 11px; color: palette(window-text); opacity: 0.6;"
        )
        self.resolve_hint_label.hide()
        header_layout.addWidget(self.resolve_hint_label)

        self.resolve_btn = QPushButton("Resolve\u2026")
        self.resolve_btn.setEnabled(False)
        self.resolve_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 14px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-weight: 600;
                color: palette(button-text);
                font-size: 12px;
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(dark);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
            QPushButton:disabled {
                background: palette(window);
                color: palette(mid);
            }
        """)
        self.resolve_btn.clicked.connect(self._on_resolve_conflict)
        header_layout.addWidget(self.resolve_btn)

        layout.addLayout(header_layout)

        # Conflicts table
        self.conflicts_table = _QTableWidget()
        self.conflicts_table.setColumnCount(4)
        self.conflicts_table.setHorizontalHeaderLabels(
            ["Term", "Type", "Anki ID", "LingQ PK"]
        )
        self.conflicts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.conflicts_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.conflicts_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.conflicts_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.conflicts_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.conflicts_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.conflicts_table.setMaximumHeight(120)
        self.conflicts_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(base);
                color: palette(text);
                gridline-color: palette(midlight);
            }
            QTableWidget::item {
                padding: 6px 8px;
                color: palette(text);
            }
            QTableWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QHeaderView::section {
                background: palette(button);
                border: none;
                border-bottom: 1px solid palette(mid);
                padding: 8px;
                font-weight: 600;
                color: palette(button-text);
            }
        """)
        self.conflicts_table.itemSelectionChanged.connect(
            self._on_conflict_selection_changed
        )

        layout.addWidget(self.conflicts_table)

        return layout

    def _create_log_section(self) -> QVBoxLayout:
        """Create log output area."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        log_header = QLabel("Log")
        log_header.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: palette(window-text);"
        )
        header_layout.addWidget(log_header)
        header_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 4px;
                font-size: 12px;
                color: palette(window-text);
            }
            QPushButton:hover {
                background: palette(button);
            }
        """)
        clear_btn.clicked.connect(self._clear_log)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(base);
                color: palette(text);
                font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
                font-size: 12px;
                padding: 12px;
            }
        """)
        self.log_output.setMinimumHeight(100)

        layout.addWidget(self.log_output)

        return layout

    def _create_progress_section(self) -> QVBoxLayout:
        """Create progress bar and status display."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background: palette(mid);
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: palette(highlight);
            }
        """)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-size: 12px; color: palette(window-text);")

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        return layout

    def _create_separator(self) -> QFrame:
        """Create a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: palette(mid);")
        line.setMaximumHeight(1)
        return line

    # === Data Loading ===

    def _load_profiles(self) -> None:
        """Load profiles from config and populate dropdown."""
        try:
            try:
                from .config_manager import load_config
            except ImportError:
                from config_manager import load_config

            config = load_config()
            self._profiles = config.profiles

            previous_selection = self.profile_combo.currentText()

            self.profile_combo.clear()
            if not self._profiles:
                self.profile_combo.addItem("(No profiles configured)")
                self._log("No profiles found. Please configure a sync profile first.")
                self.manage_profiles_btn.setFocus()
            else:
                for profile in self._profiles:
                    self.profile_combo.addItem(profile.name)
                self._log(f"Loaded {len(self._profiles)} profile(s)")
                if previous_selection:
                    idx = self.profile_combo.findText(previous_selection)
                    if idx != -1:
                        self.profile_combo.setCurrentIndex(idx)
                    else:
                        self.profile_combo.setCurrentIndex(0)

        except Exception as e:
            self._log(f"Error loading profiles: {e}")
            self.profile_combo.addItem("(Error loading profiles)")
            self.manage_profiles_btn.setFocus()

    def _get_selected_profile(self) -> Optional["Profile"]:
        """Get the currently selected profile."""
        idx = self.profile_combo.currentIndex()
        if 0 <= idx < len(self._profiles):
            return self._profiles[idx]
        return None

    # === Button State Management ===

    def _update_button_states(self) -> None:
        has_profile = self._get_selected_profile() is not None
        has_plan = self._current_plan is not None
        has_conflicts = bool(self._current_plan and self._current_plan.get_conflicts())

        validation_errors = validate_run_options(self._run_options)
        run_options_valid = len(validation_errors) == 0

        if validation_errors:
            missing = []
            for err in validation_errors:
                if "Ambiguous" in err:
                    missing.append("Ambiguous matches")
                elif "aggregation" in err:
                    missing.append("Multi-translation")
                elif "Scheduling" in err:
                    missing.append("Scheduling writes")
            self.run_options_warning.setText(f"Please select: {', '.join(missing)}")
            self.run_options_warning.show()
        else:
            self.run_options_warning.hide()

        self.dry_run_btn.setEnabled(has_profile and run_options_valid)
        self.apply_btn.setEnabled(
            has_profile and has_plan and (not has_conflicts) and run_options_valid
        )

        self.resolve_hint_label.setVisible(has_conflicts)
        self._on_conflict_selection_changed()

    # === Event Handlers ===

    def _on_profile_changed(self, index: int) -> None:
        self._current_plan = None
        self._clear_results()
        self._load_run_options_for_profile()
        self._update_button_states()

        profile = self._get_selected_profile()
        if profile:
            self._log(f"Selected profile: {profile.name}")

    def _open_config_dialog(self) -> None:
        """Open the configuration dialog and reload profiles on close."""
        previous_selection = self.profile_combo.currentText()
        dialog = ConfigDialog(self)
        dialog.exec()

        self._load_profiles()
        if self._profiles:
            idx = self.profile_combo.findText(previous_selection)
            if idx != -1:
                self.profile_combo.setCurrentIndex(idx)
            else:
                self.profile_combo.setCurrentIndex(0)
        else:
            self._log("No profiles available after closing configuration dialog.")
            self.manage_profiles_btn.setFocus()

    def _ensure_identity_fields_exist(self, profile: "Profile") -> bool:
        """Ensure LingQ identity fields exist on the configured note type.

        Returns True if ready to proceed, False if user cancelled or operation failed.
        """
        try:
            from aqt import mw

            if not mw or not getattr(mw, "col", None):
                self._log("Apply blocked: Anki collection not available")
                return False
            models = mw.col.models
        except Exception as e:
            self._log(f"Apply blocked: cannot access Anki models: {e}")
            return False

        note_type = str(getattr(profile.lingq_to_anki, "note_type", "") or "").strip()
        if not note_type:
            self._log("Apply blocked: profile missing note type")
            return False

        model = models.by_name(note_type)
        if not model:
            self._log(f"Apply blocked: note type not found: {note_type}")
            return False

        try:
            existing_fields = set(models.field_names(model))
        except Exception:
            existing_fields = set()

        pk_field = str(profile.lingq_to_anki.identity_fields.pk_field or "").strip()
        canon_field = str(
            profile.lingq_to_anki.identity_fields.canonical_term_field or ""
        ).strip()
        required = [f for f in [pk_field, canon_field] if f]
        missing = [f for f in required if f not in existing_fields]

        if not missing:
            return True

        msg = (
            f"Your note type '{note_type}' is missing required LingQ fields:\n\n"
            + "\n".join(f"- {f}" for f in missing)
            + "\n\nCreate them automatically now?\n\n"
            + "This will add empty fields to all notes of that note type (safe, reversible)."
        )

        confirm = QMessageBox.question(
            self,
            "Create Missing Fields?",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            self._log("Apply cancelled: required identity fields missing")
            return False

        try:
            for field_name in missing:
                # new_field/add_field exist in newer Anki; fall back to camelCase.
                if hasattr(models, "new_field"):
                    fld = models.new_field(field_name)
                else:
                    fld = models.newField(field_name)  # type: ignore[attr-defined]

                if hasattr(models, "add_field"):
                    models.add_field(model, fld)
                else:
                    models.addField(model, fld)  # type: ignore[attr-defined]

            if hasattr(models, "save"):
                models.save(model)
            elif hasattr(models, "update"):
                models.update(model)  # type: ignore[attr-defined]

            # Best-effort UI refresh.
            try:
                mw.reset()
            except Exception:
                pass

            self._log(
                f"Created missing identity fields on note type '{note_type}': {', '.join(missing)}"
            )
            return True
        except Exception as e:
            self._log(f"Failed to create fields on note type '{note_type}': {e}")
            return False

    def _on_dry_run(self) -> None:
        profile = self._get_selected_profile()
        if not profile:
            self._log("No profile selected")
            return

        validation_errors = validate_run_options(self._run_options)
        if validation_errors:
            self._log("Dry run blocked: run options incomplete")
            for err in validation_errors:
                self._log(f"  - {err}")
            return

        # Reset previous plan/results.
        self._current_plan = None
        self._clear_results()
        self._update_button_states()

        self._set_progress(0)
        self._set_status("Computing sync plan...")
        self._log(f"Starting dry run for profile: {profile.name}")
        self._log(
            f"Run options: ambiguous={self._run_options.ambiguous_match_policy.value}, "
            f"aggregation={self._run_options.translation_aggregation_policy.value}, "
            f"scheduling={self._run_options.scheduling_write_policy.value}"
        )

        def call_on_main(fn: Callable[[], None]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_on_main"):
                    tm.run_on_main(fn)
                    return
            except Exception:
                pass
            try:
                qt.QTimer.singleShot(0, fn)
            except Exception:
                fn()

        def set_stage(message: str, progress: int) -> None:
            def _apply() -> None:
                self._set_status(message)
                self._set_progress(progress)

            call_on_main(_apply)

        def snapshot_anki_notes() -> List[Dict[str, Any]]:
            from aqt import mw

            col = mw.col
            note_type = str(
                getattr(profile.lingq_to_anki, "note_type", "") or ""
            ).strip()

            def esc(s: str) -> str:
                return s.replace('"', r'\\"')

            note_query = f'note:"{esc(note_type)}"' if note_type else ""

            pk_field = profile.lingq_to_anki.identity_fields.pk_field
            pk_query = (
                f'{note_query} "{esc(pk_field)}:*"'
                if note_type
                else f'"{esc(pk_field)}:*"'
            )

            ids: Set[int] = set()
            for q in (note_query, pk_query):
                if not q:
                    continue
                try:
                    ids.update([int(x) for x in col.find_notes(q)])
                except Exception:
                    continue

            term_field = profile.anki_to_lingq.term_field
            translation_fields = list(
                getattr(profile.anki_to_lingq, "translation_fields", []) or []
            )
            frag_field = getattr(profile.anki_to_lingq, "fragment_field", None)
            canonical_field = profile.lingq_to_anki.identity_fields.canonical_term_field

            field_names: List[str] = []
            names: List[Any] = [
                term_field,
                *translation_fields,
                pk_field,
                canonical_field,
            ]
            if isinstance(frag_field, str) and frag_field.strip():
                names.append(frag_field.strip())

            for name in names:
                n = str(name or "").strip()
                if n and n not in field_names:
                    field_names.append(n)

            out: List[Dict[str, Any]] = []
            for nid in sorted(ids):
                note = col.get_note(nid)
                fields: Dict[str, str] = {}
                for fname in field_names:
                    try:
                        fields[fname] = str(note[fname] or "")
                    except Exception:
                        fields[fname] = ""

                cards_payload: List[Dict[str, Any]] = []
                try:
                    cards = note.cards()
                except Exception:
                    cards = []
                for c in cards or []:
                    try:
                        cards_payload.append(
                            {
                                "reps": int(getattr(c, "reps", 0) or 0),
                                "ivl": int(getattr(c, "ivl", 0) or 0),
                                "queue": int(getattr(c, "queue", 0) or 0),
                                "ord": int(getattr(c, "ord", 0) or 0),
                                "id": int(getattr(c, "id", 0) or 0),
                            }
                        )
                    except Exception:
                        continue

                # Optimization + safety: do not include unlinked notes with zero reviews.
                # They would otherwise generate massive create_lingq operations.
                existing_pk_val = str(fields.get(pk_field, "") or "").strip()
                if not existing_pk_val and cards_payload:
                    if all(int(x.get("reps", 0) or 0) <= 0 for x in cards_payload):
                        continue

                out.append(
                    {"note_id": int(nid), "fields": fields, "cards": cards_payload}
                )
            return out

        def fetch_lingq_cards() -> List[Dict[str, Any]]:
            token = str(getattr(profile, "api_token", "") or "")
            if not token:
                raise LingQApiError("Missing LingQ API token for this profile")
            language = str(getattr(profile, "lingq_language", "") or "").strip()
            if not language:
                raise LingQApiError("Missing LingQ language for this profile")
            client = LingQClient(token)
            return [dict(c) for c in client.list_cards(language)]

        def task() -> Tuple["SyncPlan", int, int]:
            set_stage("Fetching Anki notes...", 10)
            anki_notes = snapshot_anki_notes()
            set_stage(
                f"Fetched {len(anki_notes)} Anki notes. Fetching LingQ cards...", 35
            )
            lingq_cards = fetch_lingq_cards()
            set_stage(f"Fetched {len(lingq_cards)} LingQ cards. Computing plan...", 70)
            plan = compute_sync_plan(
                anki_notes=anki_notes,
                lingq_cards=lingq_cards,
                profile=profile,
                meaning_locale=profile.meaning_locale,
                run_options=self._run_options,
            )
            return plan, len(anki_notes), len(lingq_cards)

        def on_done(
            result: Optional[Tuple["SyncPlan", int, int]], err: Optional[BaseException]
        ) -> None:
            if err is not None:
                self._set_progress(0)
                self._set_status("Ready")
                self._log(f"Dry run failed: {err}")
                return
            if not result:
                self._set_progress(0)
                self._set_status("Ready")
                self._log("Dry run failed: no result")
                return

            plan, anki_count, lingq_count = result
            self._log(f"Fetched Anki notes: {anki_count}")
            self._log(f"Fetched LingQ cards: {lingq_count}")
            self._display_plan(plan)
            self._set_progress(100)
            self._set_status("Ready")

        def run_in_background(task_fn: Callable[[], Any]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_in_background"):

                    def _done(fut) -> None:  # type: ignore[no-untyped-def]
                        try:
                            res = fut.result()
                            call_on_main(lambda: on_done(res, None))
                        except BaseException as e:
                            call_on_main(lambda: on_done(None, e))

                    tm.run_in_background(task_fn, _done)
                    return
            except Exception:
                pass

            # Fallback: thread + best-effort main-thread callback.
            def _worker() -> None:
                try:
                    res = task_fn()
                    call_on_main(lambda: on_done(res, None))
                except BaseException as e:
                    call_on_main(lambda: on_done(None, e))

            threading.Thread(target=_worker, daemon=True).start()

        run_in_background(task)

    def _on_apply(self) -> None:
        plan = self._current_plan
        if not plan:
            self._log("No sync plan to apply. Run Dry Run first.")
            return

        profile = self._get_selected_profile()
        if not profile:
            self._log("No profile selected")
            return

        validation_errors = validate_run_options(self._run_options)
        if validation_errors:
            self._log("Apply blocked: run options incomplete")
            for err in validation_errors:
                self._log(f"  - {err}")
            return

        conflicts = list(plan.get_conflicts() or [])
        if conflicts:
            self._log(
                f"Apply blocked: {len(conflicts)} conflict(s) present. "
                "Resolve conflicts via Dry Run (conflict UI coming soon)."
            )
            self._update_button_states()
            return

        # Preflight: ensure PK/canonical fields exist so OP_LINK/OP_CREATE_ANKI can succeed.
        if not self._ensure_identity_fields_exist(profile):
            self._set_status("Ready")
            self._update_button_states()
            return

        counts = plan.count_by_type()
        total_ops = len(getattr(plan, "operations", []) or [])

        lines: List[str] = []
        lines.append(f"Profile: {profile.name}")
        lines.append(f"Operations: {total_ops}")
        for op_type, count in sorted(counts.items()):
            lines.append(f"  - {op_type}: {count}")
        lines.append("")
        lines.append(
            "This will modify your Anki collection and/or LingQ data. "
            "The apply run is resumable via checkpointing."
        )

        confirm = QMessageBox.question(
            self,
            "Confirm Apply",
            "Apply the current sync plan?\n\n" + "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            self._log("Apply cancelled")
            self._set_status("Ready")
            return

        # Ensure apply_engine persists checkpoints per-profile.
        try:
            setattr(plan, "profile_name", str(profile.name))
        except Exception:
            pass

        self._set_status("Applying sync plan...")
        self._log(f"Applying sync plan for profile: {profile.name}")
        self._log(
            f"Run options: ambiguous={self._run_options.ambiguous_match_policy.value}, "
            f"aggregation={self._run_options.translation_aggregation_policy.value}, "
            f"scheduling={self._run_options.scheduling_write_policy.value}"
        )

        self._set_ui_running(True)
        self._set_busy_progress(True)

        def call_on_main(fn: Callable[[], None]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_on_main"):
                    tm.run_on_main(fn)
                    return
            except Exception:
                pass
            try:
                qt.QTimer.singleShot(0, fn)
            except Exception:
                fn()

        def task() -> Tuple[Any, Optional[Dict[str, Any]]]:
            token = str(getattr(profile, "api_token", "") or "")
            if not token:
                raise LingQApiError("Missing LingQ API token for this profile")

            client = LingQClient(token)
            checkpoint = load_checkpoint(profile.name) or Checkpoint(run_id="")
            resume_info: Optional[Dict[str, Any]] = None
            if checkpoint.run_id:
                resume_info = {
                    "run_id": checkpoint.run_id,
                    "last_processed_index": int(checkpoint.last_processed_index),
                }

            result = apply_sync_plan(plan, client, checkpoint)
            finished = int(getattr(checkpoint, "last_processed_index", 0) or 0) >= int(
                total_ops
            )
            if finished:
                clear_checkpoint(profile.name)

            return result, resume_info

        def on_done(
            result: Optional[Tuple[Any, Optional[Dict[str, Any]]]],
            err: Optional[BaseException],
        ) -> None:
            self._set_busy_progress(False)
            self._set_progress(100)
            self._set_ui_running(False)

            if err is not None:
                self._set_status("Ready")
                self._log(f"Apply failed: {err}")
                self._log(
                    "Checkpoint (if any) was preserved. Re-run Apply to resume safely."
                )
                return

            if not result:
                self._set_status("Ready")
                self._log("Apply failed: no result")
                return

            apply_result, resume_info = result
            if resume_info:
                self._log(
                    "Resumed from checkpoint: "
                    f"run_id={resume_info.get('run_id')} "
                    f"index={resume_info.get('last_processed_index')}"
                )

            success_count = int(getattr(apply_result, "success_count", 0) or 0)
            skipped_count = int(getattr(apply_result, "skipped_count", 0) or 0)
            error_count = int(getattr(apply_result, "error_count", 0) or 0)
            errors = list(getattr(apply_result, "errors", []) or [])

            self._log(
                f"Apply results: success={success_count}, skipped={skipped_count}, errors={error_count}"
            )
            if errors:
                self._log("First errors:")
                for msg in errors[:5]:
                    self._log(f"  - {msg}")
                if len(errors) > 5:
                    self._log(f"  ... and {len(errors) - 5} more")

            if error_count:
                self._set_status("Apply completed with errors")
            else:
                self._set_status("Apply completed")

            # Nice-to-have: refresh dry run after a clean apply.
            if error_count == 0 and success_count > 0:
                self._log("Refreshing plan (dry run) to confirm 0 changes...")
                call_on_main(self._on_dry_run)

        def run_in_background(task_fn: Callable[[], Any]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_in_background"):

                    def _done(fut) -> None:  # type: ignore[no-untyped-def]
                        try:
                            res = fut.result()
                            call_on_main(lambda: on_done(res, None))
                        except BaseException as e:
                            call_on_main(lambda: on_done(None, e))

                    tm.run_in_background(task_fn, _done)
                    return

            except Exception:
                pass

            # Fallback: thread + best-effort main-thread callback.
            def _worker() -> None:
                try:
                    res = task_fn()
                    call_on_main(lambda: on_done(res, None))
                except BaseException as e:
                    call_on_main(lambda: on_done(None, e))

            threading.Thread(target=_worker, daemon=True).start()

        run_in_background(task)

    def _on_self_check(self) -> None:
        self._set_status("Running self-check...")
        self._log("Self-check: starting")

        checks_ok = True

        try:
            try:
                from .config_manager import load_config
            except ImportError:
                from config_manager import load_config

            config = load_config()
            profiles = getattr(config, "profiles", [])
            self._log(f"Self-check: profiles loaded ({len(profiles)})")
        except Exception as e:
            checks_ok = False
            self._log(f"Self-check: profile load failed: {e}")

        validation_errors = validate_run_options(self._run_options)
        if validation_errors:
            checks_ok = False
            missing = []
            for err in validation_errors:
                if "Ambiguous" in err:
                    missing.append("Ambiguous matches")
                elif "aggregation" in err:
                    missing.append("Multi-translation")
                elif "Scheduling" in err:
                    missing.append("Scheduling writes")
                else:
                    missing.append(err)
            if missing:
                self._log("Self-check: run options missing selections:")
                for item in missing:
                    self._log(f"  - {item}")
        else:
            self._log("Self-check: run options valid")

        profile = self._get_selected_profile()
        if not profile:
            checks_ok = False
            self._log("Self-check: no profile selected for meta persistence test")
        else:
            try:
                key = f"lingq_sync:self_check:{profile.name}"
                sentinel_value = f"self_check:{uuid.uuid4().hex}"
                previous_value = self._pm_meta_get(key, None)
                self._pm_meta_set(key, sentinel_value)
                read_back = self._pm_meta_get(key, None)
                if read_back == sentinel_value:
                    self._log("Self-check: run options persistence OK")
                else:
                    checks_ok = False
                    self._log(
                        "Self-check: run options persistence failed (sentinel mismatch)"
                    )
                self._pm_meta_set(key, previous_value)
            except Exception as e:
                checks_ok = False
                self._log(f"Self-check: run options persistence error: {e}")

        if checks_ok:
            self._set_status("Self-check passed")
            self._log("Self-check: completed")
        else:
            self._set_status("Self-check completed with issues")
            self._log("Self-check: completed with issues")

    # === Conflict Resolution ===

    def _on_conflict_selection_changed(self) -> None:
        selected_rows = self.conflicts_table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0 and len(self._current_conflicts) > 0
        self.resolve_btn.setEnabled(has_selection)

    def _get_selected_conflict_index(self) -> Optional[int]:
        selected_rows = self.conflicts_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        if 0 <= row < len(self._current_conflicts):
            return row
        return None

    def _on_resolve_conflict(self) -> None:
        idx = self._get_selected_conflict_index()
        if idx is None:
            self._log("No conflict selected")
            return

        op = self._current_conflicts[idx]
        conflict_type = op.details.get("conflict_type", "unknown")

        if conflict_type == "duplicate_pk":
            self._resolve_duplicate_pk(op, idx)
        else:
            self._resolve_generic_conflict(op, idx, conflict_type)

    @staticmethod
    def _ellipsize(text: str, max_len: int = 60) -> str:
        text = text.strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "\u2026"

    def _build_note_preview(self, nid: int, profile: "Profile") -> tuple[str, str]:
        """Return (primary_line, secondary_line) for a note in the duplicate-PK dialog.

        primary_line: term + optional translation snippet.
        secondary_line: deck name, note-type name, note id (all best-effort).
        Safe against missing fields/collection — never raises.
        """
        term_text = ""
        translation_text = ""
        deck_name = ""
        note_type_name = ""

        try:
            from aqt import mw as _mw

            if _mw and getattr(_mw, "col", None):
                note = _mw.col.get_note(nid)

                try:
                    term_field = str(
                        getattr(profile.anki_to_lingq, "term_field", "") or ""
                    ).strip()
                    if term_field:
                        term_text = str(note[term_field] or "").strip()
                except Exception:
                    pass

                try:
                    translation_fields = list(
                        getattr(profile.anki_to_lingq, "translation_fields", []) or []
                    )
                    snippets: list[str] = []
                    for tf in translation_fields:
                        tf = str(tf or "").strip()
                        if not tf:
                            continue
                        try:
                            val = str(note[tf] or "").strip()
                        except Exception:
                            continue
                        if val:
                            snippets.append(val)
                        if len(snippets) >= 2:
                            break
                    if snippets:
                        translation_text = "; ".join(snippets)
                except Exception:
                    pass

                try:
                    cards = note.cards()
                    if cards:
                        primary_card = min(cards, key=lambda c: getattr(c, "ord", 0))
                        deck_id = getattr(primary_card, "did", None)
                        if deck_id is not None:
                            deck_name = str(_mw.col.decks.name(deck_id) or "").strip()
                except Exception:
                    pass

                try:
                    model = getattr(note, "model", None)
                    if callable(model):
                        model = model()
                    if model and isinstance(model, dict):
                        note_type_name = str(model.get("name", "") or "").strip()
                    else:
                        mid = getattr(note, "mid", None)
                        if mid is not None:
                            m = _mw.col.models.get(mid)
                            if m:
                                note_type_name = str(m.get("name", "") or "").strip()
                except Exception:
                    pass
        except Exception:
            pass

        primary = self._ellipsize(term_text, 50) if term_text else "(no term)"
        if translation_text:
            primary += " \u2014 " + self._ellipsize(translation_text, 50)

        parts: list[str] = []
        if deck_name:
            parts.append(deck_name)
        if note_type_name:
            parts.append(note_type_name)
        parts.append(f"ID {nid}")
        secondary = "  \u00b7  ".join(parts)

        return primary, secondary

    def _resolve_duplicate_pk(self, op: Any, conflict_idx: int) -> None:
        profile = self._get_selected_profile()
        if not profile:
            self._log("No profile selected")
            return

        pk_field = str(profile.lingq_to_anki.identity_fields.pk_field or "").strip()
        canonical_field = str(
            profile.lingq_to_anki.identity_fields.canonical_term_field or ""
        ).strip()
        lingq_pk = str(op.lingq_pk or "")

        if not pk_field or not lingq_pk:
            self._log("Cannot resolve: missing PK field or LingQ PK value")
            return

        try:
            from aqt import mw

            if not mw or not getattr(mw, "col", None):
                self._log("Cannot resolve: Anki collection not available")
                return
            matching_nids = [
                int(x) for x in mw.col.find_notes(f"{pk_field}:{lingq_pk}")
            ]
        except Exception as e:
            self._log(f"Cannot resolve: failed to search Anki notes: {e}")
            return

        if len(matching_nids) < 2:
            self._log(
                f"Only {len(matching_nids)} note(s) found with {pk_field}={lingq_pk}. "
                "Re-run Dry Run to refresh."
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Resolve Duplicate PK")
        dialog.setMinimumWidth(480)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(20, 16, 20, 16)

        explanation = QLabel(
            f"Multiple Anki notes share the same LingQ PK "
            f"<b>{lingq_pk}</b> in field <b>{pk_field}</b>.\n\n"
            f"Choose which note keeps the PK. The others will have "
            f"their <b>{pk_field}</b>"
            + (f" and <b>{canonical_field}</b>" if canonical_field else "")
            + " fields cleared."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "font-size: 12px; color: palette(window-text); padding-bottom: 4px;"
        )
        dlg_layout.addWidget(explanation)

        btn_group = QButtonGroup(dialog)
        default_nid = int(op.anki_note_id) if op.anki_note_id else None

        for nid in matching_nids:
            primary_text, secondary_text = self._build_note_preview(nid, profile)

            option_widget = QWidget()
            option_layout = QVBoxLayout(option_widget)
            option_layout.setContentsMargins(0, 4, 0, 4)
            option_layout.setSpacing(1)

            radio = QRadioButton(primary_text)
            radio.setStyleSheet("font-size: 13px; color: palette(text); padding: 0;")
            radio.setProperty("nid", nid)
            if nid == default_nid:
                radio.setChecked(True)
            btn_group.addButton(radio)
            option_layout.addWidget(radio)

            meta_label = QLabel(secondary_text)
            meta_label.setStyleSheet(
                "font-size: 11px; color: palette(window-text);"
                " padding-left: 22px; opacity: 0.65;"
            )
            meta_label.setWordWrap(False)
            option_layout.addWidget(meta_label)

            dlg_layout.addWidget(option_widget)

        if not btn_group.checkedButton() and btn_group.buttons():
            btn_group.buttons()[0].setChecked(True)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-size: 12px;
                color: palette(window-text);
            }
            QPushButton:hover { background: palette(button); }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background: palette(highlight);
                border: none;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
                color: palette(highlighted-text);
            }
            QPushButton:hover { background: palette(highlight); }
        """)
        confirm_btn.clicked.connect(dialog.accept)
        button_row.addWidget(confirm_btn)

        dlg_layout.addLayout(button_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        checked = btn_group.checkedButton()
        if not checked:
            return
        keep_nid = int(checked.property("nid"))
        clear_nids = [n for n in matching_nids if n != keep_nid]

        self._log(
            f"Resolving duplicate_pk: keeping PK on note #{keep_nid}, "
            f"clearing {len(clear_nids)} other note(s)"
        )

        self._run_duplicate_pk_fix(clear_nids, pk_field, canonical_field)

    def _run_duplicate_pk_fix(
        self, clear_nids: List[int], pk_field: str, canonical_field: str
    ) -> None:
        self._set_status("Resolving duplicate PK\u2026")
        self._set_busy_progress(True)

        def call_on_main(fn: Callable[[], None]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_on_main"):
                    tm.run_on_main(fn)
                    return
            except Exception:
                pass
            try:
                qt.QTimer.singleShot(0, fn)
            except Exception:
                fn()

        def task() -> int:
            from aqt import mw

            col = mw.col
            cleared = 0
            for nid in clear_nids:
                try:
                    note = col.get_note(nid)
                    changed = False
                    if pk_field and pk_field in [
                        f["name"] for f in note.model()["flds"]
                    ]:
                        if str(note[pk_field] or "").strip():
                            note[pk_field] = ""
                            changed = True
                    if canonical_field and canonical_field in [
                        f["name"] for f in note.model()["flds"]
                    ]:
                        if str(note[canonical_field] or "").strip():
                            note[canonical_field] = ""
                            changed = True
                    if changed:
                        col.update_note(note)
                        cleared += 1
                except Exception:
                    continue
            return cleared

        def on_done(result: Optional[int], err: Optional[BaseException]) -> None:
            self._set_busy_progress(False)
            self._set_progress(100)
            if err is not None:
                self._set_status("Ready")
                self._log(f"Failed to clear duplicate PKs: {err}")
                return
            self._log(f"Cleared PK on {result or 0} note(s). Re-running Dry Run\u2026")
            self._set_status("Ready")
            self._on_dry_run()

        def run_in_background(task_fn: Callable[[], Any]) -> None:
            try:
                from aqt import mw

                tm = getattr(mw, "taskman", None)
                if tm and hasattr(tm, "run_in_background"):

                    def _done(fut) -> None:  # type: ignore[no-untyped-def]
                        try:
                            res = fut.result()
                            call_on_main(lambda: on_done(res, None))
                        except BaseException as e:
                            call_on_main(lambda: on_done(None, e))

                    tm.run_in_background(task_fn, _done)
                    return
            except Exception:
                pass

            def _worker() -> None:
                try:
                    res = task_fn()
                    call_on_main(lambda: on_done(res, None))
                except BaseException as e:
                    call_on_main(lambda: on_done(None, e))

            threading.Thread(target=_worker, daemon=True).start()

        run_in_background(task)

    def _resolve_generic_conflict(
        self, op: Any, conflict_idx: int, conflict_type: str
    ) -> None:
        plan = self._current_plan
        if not plan:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Resolve Conflict")
        dialog.setMinimumWidth(400)
        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(20, 16, 20, 16)

        recommended = op.details.get("recommended_action", "")
        explanation = QLabel(
            f"<b>Conflict type:</b> {conflict_type}<br>"
            f"<b>Term:</b> {op.term or '(unknown)'}<br>"
            f"<b>Recommended:</b> {recommended or 'N/A'}"
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "font-size: 12px; color: palette(window-text); padding-bottom: 4px;"
        )
        dlg_layout.addWidget(explanation)

        btn_group = QButtonGroup(dialog)

        skip_radio = QRadioButton("Skip this item (remove from plan)")
        skip_radio.setStyleSheet(
            "font-size: 12px; color: palette(text); padding: 4px 0;"
        )
        skip_radio.setProperty("action", "skip")
        skip_radio.setChecked(True)
        btn_group.addButton(skip_radio)
        dlg_layout.addWidget(skip_radio)

        rerun_combo_ref: List[QComboBox] = []

        combo_style = """
            QComboBox {
                padding: 6px 10px; border: 1px solid palette(mid);
                border-radius: 5px; background: palette(window);
                color: palette(text); font-size: 12px; min-width: 200px;
                margin-left: 22px;
            }
            QComboBox:hover { border-color: palette(highlight); }
            QComboBox QAbstractItemView {
                background: palette(base); color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
        """
        radio_style = "font-size: 12px; color: palette(text); padding: 4px 0;"

        if conflict_type == "anki_polysemy_needs_policy":
            r = QRadioButton("Adjust Multi-translation policy and re-run Dry Run")
            r.setStyleSheet(radio_style)
            r.setProperty("action", "rerun_aggregation")
            btn_group.addButton(r)
            dlg_layout.addWidget(r)

            c = QComboBox()
            c.setStyleSheet(combo_style)
            c.addItem("MIN (shortest)", TranslationAggregationPolicy.MIN)
            c.addItem("MAX (longest)", TranslationAggregationPolicy.MAX)
            c.addItem("AVG (median length)", TranslationAggregationPolicy.AVG)
            c.addItem("Skip", TranslationAggregationPolicy.SKIP)
            dlg_layout.addWidget(c)
            rerun_combo_ref.append(c)

        elif conflict_type == "ambiguous_lingq_match":
            r = QRadioButton("Adjust Ambiguous matches policy and re-run Dry Run")
            r.setStyleSheet(radio_style)
            r.setProperty("action", "rerun_ambiguous")
            btn_group.addButton(r)
            dlg_layout.addWidget(r)

            c = QComboBox()
            c.setStyleSheet(combo_style)
            c.addItem("Skip", AmbiguousMatchPolicy.SKIP)
            c.addItem("Conservative skip", AmbiguousMatchPolicy.CONSERVATIVE_SKIP)
            c.addItem(
                "Aggressive: link first (unsafe)",
                AmbiguousMatchPolicy.AGGRESSIVE_LINK_FIRST,
            )
            dlg_layout.addWidget(c)
            rerun_combo_ref.append(c)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-size: 12px;
                color: palette(window-text);
            }
            QPushButton:hover { background: palette(button); }
        """)
        cancel_btn.clicked.connect(dialog.reject)
        button_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 18px;
                background: palette(highlight);
                border: none;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
                color: palette(highlighted-text);
            }
            QPushButton:hover { background: palette(highlight); }
        """)
        confirm_btn.clicked.connect(dialog.accept)
        button_row.addWidget(confirm_btn)

        dlg_layout.addLayout(button_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        checked = btn_group.checkedButton()
        if not checked:
            return
        action = str(checked.property("action") or "skip")

        if action == "skip":
            self._skip_conflict_in_plan(op, conflict_idx)
        elif action == "rerun_aggregation" and rerun_combo_ref:
            policy = rerun_combo_ref[0].currentData()
            self._log(
                f"Changing Multi-translation policy to {policy.value} and re-running"
            )
            self._run_options = RunOptions(
                ambiguous_match_policy=self._run_options.ambiguous_match_policy,
                translation_aggregation_policy=policy,
                scheduling_write_policy=self._run_options.scheduling_write_policy,
                progress_authority_policy=self._run_options.progress_authority_policy,
            )
            self._sync_combos_from_run_options()
            self._save_run_options_for_profile()
            self._on_dry_run()
        elif action == "rerun_ambiguous" and rerun_combo_ref:
            policy = rerun_combo_ref[0].currentData()
            self._log(
                f"Changing Ambiguous matches policy to {policy.value} and re-running"
            )
            self._run_options = RunOptions(
                ambiguous_match_policy=policy,
                translation_aggregation_policy=self._run_options.translation_aggregation_policy,
                scheduling_write_policy=self._run_options.scheduling_write_policy,
                progress_authority_policy=self._run_options.progress_authority_policy,
            )
            self._sync_combos_from_run_options()
            self._save_run_options_for_profile()
            self._on_dry_run()

    def _skip_conflict_in_plan(self, op: Any, conflict_idx: int) -> None:
        plan = self._current_plan
        if not plan:
            return

        try:
            try:
                from .diff_engine import OP_SKIP
            except ImportError:
                from diff_engine import OP_SKIP  # type: ignore[no-redef]
        except Exception:
            OP_SKIP = "skip"  # type: ignore[assignment]

        for i, plan_op in enumerate(plan.operations):
            if plan_op is op:
                plan.operations[i] = type(op)(
                    op_type=OP_SKIP,
                    anki_note_id=op.anki_note_id,
                    lingq_pk=op.lingq_pk,
                    term=op.term,
                    details={"reason": "user_skipped_conflict"},
                )
                break

        self._log(f'Skipped conflict for "{op.term}"')
        self._display_plan(plan)

    def _clear_log(self) -> None:
        """Clear the log output."""
        self.log_output.clear()

    # === Display Updates ===

    def _display_plan(self, plan: "SyncPlan") -> None:
        """Display sync plan results in the UI."""
        self._current_plan = plan
        self._update_button_states()

        # Update summary stats
        counts = plan.count_by_type()
        for key, label in self._stat_labels.items():
            if label:
                count = counts.get(key, 0)
                label.setText(str(count))

        conflicts = plan.get_conflicts()
        self._current_conflicts = list(conflicts)
        self.conflicts_header.setText(f"Conflicts ({len(conflicts)})")
        self.conflicts_table.setRowCount(len(conflicts))

        for row, op in enumerate(conflicts):
            self.conflicts_table.setItem(row, 0, QTableWidgetItem(op.term))
            conflict_type = op.details.get("conflict_type", "unknown")
            self.conflicts_table.setItem(row, 1, QTableWidgetItem(conflict_type))
            self.conflicts_table.setItem(
                row, 2, QTableWidgetItem(str(op.anki_note_id or "-"))
            )
            self.conflicts_table.setItem(
                row, 3, QTableWidgetItem(str(op.lingq_pk or "-"))
            )

        # Log summary
        total = len(plan.operations)
        self._log(f"Sync plan computed: {total} operations")
        for op_type, count in sorted(counts.items()):
            self._log(f"  {op_type}: {count}")

    def _clear_results(self) -> None:
        """Clear all result displays."""
        for label in self._stat_labels.values():
            if label:
                label.setText("0")

        self._current_conflicts = []
        self.conflicts_header.setText("Conflicts (0)")
        self.conflicts_table.setRowCount(0)
        self.progress_bar.setValue(0)

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.setText(message)

    def _log(self, message: str) -> None:
        """Append a message to the log output."""
        self.log_output.append(message)

    def _set_progress(self, value: int, maximum: int = 100) -> None:
        """Update the progress bar."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def _set_busy_progress(self, busy: bool) -> None:
        if busy:
            try:
                self.progress_bar.setRange(0, 0)
            except Exception:
                self.progress_bar.setMaximum(0)
                self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 100)

    def _set_ui_running(self, running: bool) -> None:
        widgets = [
            self.profile_combo,
            self.manage_profiles_btn,
            self.dry_run_btn,
            self.apply_btn,
            self.self_check_btn,
            self.ambiguous_combo,
            self.aggregation_combo,
            self.scheduling_combo,
            self.resolve_btn,
        ]
        for w in widgets:
            try:
                w.setEnabled(not running)
            except Exception:
                continue
        if not running:
            self._update_button_states()

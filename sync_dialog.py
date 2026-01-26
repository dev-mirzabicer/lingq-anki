# pyright: reportMissingImports=false
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from config_model import Profile
    from diff_engine import SyncPlan

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
        self._profiles: List["Profile"] = []

        self._setup_ui()
        self._load_profiles()
        self._update_button_states()

    def _setup_ui(self) -> None:
        """Build the complete dialog layout."""
        main_layout = QVBoxLayout(self)
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

        # === Progress Section ===
        progress_section = self._create_progress_section()
        main_layout.addLayout(progress_section)

    def _create_header_section(self) -> QHBoxLayout:
        """Create the title header."""
        layout = QHBoxLayout()

        title = QLabel("LingQ Sync")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2563eb;")

        subtitle = QLabel("Synchronize your vocabulary between LingQ and Anki")
        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")

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
        profile_label.setStyleSheet("font-weight: 600; color: #374151;")

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(250)
        self.profile_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #2563eb;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
        """)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        layout.addWidget(profile_label)
        layout.addWidget(self.profile_combo)
        layout.addStretch()

        return layout

    def _create_action_section(self) -> QHBoxLayout:
        """Create action buttons: Dry Run, Apply, Close."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Dry Run button
        self.dry_run_btn = QPushButton("Dry Run")
        self.dry_run_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-weight: 600;
                color: #475569;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background: #cbd5e1;
            }
            QPushButton:disabled {
                background: #f8fafc;
                color: #94a3b8;
            }
        """)
        self.dry_run_btn.clicked.connect(self._on_dry_run)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: #2563eb;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                color: white;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e40af;
            }
            QPushButton:disabled {
                background: #93c5fd;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: transparent;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                font-weight: 500;
                color: #6b7280;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #f9fafb;
                border-color: #d1d5db;
            }
        """)
        close_btn.clicked.connect(self.close)

        layout.addWidget(self.dry_run_btn)
        layout.addWidget(self.apply_btn)
        layout.addStretch()
        layout.addWidget(close_btn)

        return layout

    def _create_summary_section(self) -> QVBoxLayout:
        """Create summary stats display."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header = QLabel("Summary")
        header.setStyleSheet("font-weight: 600; font-size: 14px; color: #1f2937;")
        layout.addWidget(header)

        # Stats grid
        stats_layout = QGridLayout()
        stats_layout.setSpacing(16)

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
            row = idx // 4
            col = idx % 4

            stat_widget = self._create_stat_widget(label, "0", color)
            self._stat_labels[key] = stat_widget.findChild(QLabel, f"stat_value_{key}")
            stats_layout.addWidget(stat_widget, row, col)

        layout.addLayout(stats_layout)

        return layout

    def _create_stat_widget(self, label: str, value: str, color: str) -> QFrame:
        """Create a single stat display widget."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {color}10;
                border: 1px solid {color}30;
                border-radius: 8px;
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName(
            f"stat_value_{label.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
        )
        value_label.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(label)
        name_label.setStyleSheet("font-size: 11px; color: #64748b;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(value_label)
        layout.addWidget(name_label)

        return frame

    def _create_conflicts_section(self) -> QVBoxLayout:
        """Create conflicts list display."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        self.conflicts_header = QLabel("Conflicts (0)")
        self.conflicts_header.setStyleSheet(
            "font-weight: 600; font-size: 14px; color: #1f2937;"
        )
        header_layout.addWidget(self.conflicts_header)
        header_layout.addStretch()

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
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background: white;
                gridline-color: #f3f4f6;
            }
            QTableWidget::item {
                padding: 6px 8px;
            }
            QHeaderView::section {
                background: #f9fafb;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                padding: 8px;
                font-weight: 600;
                color: #374151;
            }
        """)

        layout.addWidget(self.conflicts_table)

        return layout

    def _create_log_section(self) -> QVBoxLayout:
        """Create log output area."""
        layout = QVBoxLayout()
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        log_header = QLabel("Log")
        log_header.setStyleSheet("font-weight: 600; font-size: 14px; color: #1f2937;")
        header_layout.addWidget(log_header)
        header_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 12px;
                background: transparent;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                font-size: 12px;
                color: #6b7280;
            }
            QPushButton:hover {
                background: #f9fafb;
            }
        """)
        clear_btn.clicked.connect(self._clear_log)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background: #1e293b;
                color: #e2e8f0;
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
                background: #e5e7eb;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563eb, stop:1 #7c3aed);
            }
        """)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-size: 12px; color: #64748b;")

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        return layout

    def _create_separator(self) -> QFrame:
        """Create a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #e5e7eb;")
        line.setMaximumHeight(1)
        return line

    # === Data Loading ===

    def _load_profiles(self) -> None:
        """Load profiles from config and populate dropdown."""
        try:
            from config_manager import load_config

            config = load_config()
            self._profiles = config.profiles

            self.profile_combo.clear()
            if not self._profiles:
                self.profile_combo.addItem("(No profiles configured)")
                self._log("No profiles found. Please configure a sync profile first.")
            else:
                for profile in self._profiles:
                    self.profile_combo.addItem(profile.name)
                self._log(f"Loaded {len(self._profiles)} profile(s)")

        except Exception as e:
            self._log(f"Error loading profiles: {e}")
            self.profile_combo.addItem("(Error loading profiles)")

    def _get_selected_profile(self) -> Optional["Profile"]:
        """Get the currently selected profile."""
        idx = self.profile_combo.currentIndex()
        if 0 <= idx < len(self._profiles):
            return self._profiles[idx]
        return None

    # === Button State Management ===

    def _update_button_states(self) -> None:
        """Update button enabled states based on current state."""
        has_profile = self._get_selected_profile() is not None
        has_plan = self._current_plan is not None

        self.dry_run_btn.setEnabled(has_profile)
        self.apply_btn.setEnabled(has_profile and has_plan)

    # === Event Handlers ===

    def _on_profile_changed(self, index: int) -> None:
        """Handle profile selection change."""
        self._current_plan = None
        self._clear_results()
        self._update_button_states()

        profile = self._get_selected_profile()
        if profile:
            self._log(f"Selected profile: {profile.name}")

    def _on_dry_run(self) -> None:
        """Execute dry run to compute sync plan."""
        profile = self._get_selected_profile()
        if not profile:
            self._log("No profile selected")
            return

        self._set_status("Computing sync plan...")
        self._log(f"Starting dry run for profile: {profile.name}")

        # TODO: Wire up actual sync plan computation using QueryOp
        # For now, just show the UI is ready
        self._log("Dry run not yet implemented - UI structure complete")
        self._set_status("Ready")

    def _on_apply(self) -> None:
        """Apply the computed sync plan."""
        if not self._current_plan:
            self._log("No sync plan to apply. Run Dry Run first.")
            return

        profile = self._get_selected_profile()
        if not profile:
            self._log("No profile selected")
            return

        self._set_status("Applying sync plan...")
        self._log(f"Applying sync plan for profile: {profile.name}")

        # TODO: Wire up actual sync plan application using QueryOp
        self._log("Apply not yet implemented - UI structure complete")
        self._set_status("Ready")

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

        # Update conflicts table
        conflicts = plan.get_conflicts()
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

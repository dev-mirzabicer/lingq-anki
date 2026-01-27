# pyright: reportMissingImports=false
"""Configuration dialog for LingQ-Anki sync profiles.

Provides a two-pane UI for managing sync profiles with secure API token handling.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from config_model import Config, Profile

try:
    from .config_manager import load_config, save_config
    from .config_model import (
        AnkiToLingqMapping,
        Config,
        IdentityFields,
        LingqToAnkiMapping,
        Profile,
    )
except ImportError:
    from config_manager import load_config, save_config  # type: ignore[no-redef]
    from config_model import (  # type: ignore[no-redef]
        AnkiToLingqMapping,
        Config,
        IdentityFields,
        LingqToAnkiMapping,
        Profile,
    )

qt = importlib.import_module("aqt.qt")
QDialog = qt.QDialog
QVBoxLayout = qt.QVBoxLayout
QHBoxLayout = qt.QHBoxLayout
QFormLayout = qt.QFormLayout
QListWidget = qt.QListWidget
QListWidgetItem = qt.QListWidgetItem
QLineEdit = qt.QLineEdit
QCheckBox = qt.QCheckBox
QPushButton = qt.QPushButton
QLabel = qt.QLabel
QFrame = qt.QFrame
QSplitter = qt.QSplitter
QWidget = qt.QWidget
QMessageBox = qt.QMessageBox
Qt = qt.Qt
QSizePolicy = qt.QSizePolicy
QComboBox = qt.QComboBox
QTabWidget = qt.QTabWidget
QScrollArea = qt.QScrollArea
QGroupBox = qt.QGroupBox


def _get_anki_note_types() -> List[str]:
    """Get available note type names from Anki, or empty list if unavailable."""
    try:
        from aqt import mw

        if mw and mw.col and mw.col.models:
            return mw.col.models.all_names()
    except Exception:
        pass
    return []


def _get_anki_deck_names() -> List[str]:
    """Get available deck names from Anki, or empty list if unavailable."""
    try:
        from aqt import mw

        if mw and mw.col and mw.col.decks:
            decks = mw.col.decks
            if hasattr(decks, "all_names"):
                return list(decks.all_names())
            if hasattr(decks, "allNames"):
                return list(decks.allNames())
    except Exception:
        pass
    return []


def _get_anki_fields_for_note_type(note_type_name: str) -> List[str]:
    """Get field names for a note type, or empty list if unavailable."""
    try:
        from aqt import mw

        if mw and mw.col and mw.col.models:
            model = mw.col.models.by_name(note_type_name)
            if model:
                return [f["name"] for f in model["flds"]]
    except Exception:
        pass
    return []


def _get_anki_templates_for_note_type(note_type_name: str) -> List[str]:
    """Get card template names for a note type, or empty list if unavailable."""
    try:
        from aqt import mw

        if mw and mw.col and mw.col.models:
            model = mw.col.models.by_name(note_type_name)
            if model:
                return [t["name"] for t in model["tmpls"]]
    except Exception:
        pass
    return []


def _is_anki_available() -> bool:
    """Check if Anki runtime is available for model introspection."""
    try:
        from aqt import mw

        return mw is not None and mw.col is not None and mw.col.models is not None
    except Exception:
        return False


class ConfigDialog(QDialog):
    """Configuration dialog for managing LingQ-Anki sync profiles."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LingQ Sync Configuration")
        self.resize(780, 520)
        self.setMinimumSize(640, 420)

        self._config: Optional["Config"] = None
        self._current_profile_index: int = -1
        self._unsaved_changes: bool = False

        self._setup_ui()
        self._load_config()
        self._apply_styles()

    def _setup_ui(self) -> None:
        """Build the complete dialog layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === Header ===
        header = self._create_header()
        main_layout.addWidget(header)

        # === Separator ===
        main_layout.addWidget(self._create_separator())

        # === Two-pane content ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left pane: profile list
        left_pane = self._create_profile_list_pane()
        splitter.addWidget(left_pane)

        # Right pane: profile editor
        right_pane = self._create_profile_editor_pane()
        splitter.addWidget(right_pane)

        splitter.setSizes([220, 520])
        main_layout.addWidget(splitter, stretch=1)

        # === Separator ===
        main_layout.addWidget(self._create_separator())

        # === Footer buttons ===
        footer = self._create_footer()
        main_layout.addLayout(footer)

    def _create_header(self) -> QLabel:
        """Create the dialog header."""
        header = QLabel("Profile Configuration")
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: palette(window-text);
                padding-bottom: 4px;
            }
        """)
        return header

    def _create_separator(self) -> QFrame:
        """Create a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: palette(mid);")
        line.setMaximumHeight(1)
        return line

    def _create_profile_list_pane(self) -> QWidget:
        """Create the left pane with profile list and add/delete buttons."""
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        # Profile list header
        list_header = QLabel("Profiles")
        list_header.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: palette(window-text);
            }
        """)
        layout.addWidget(list_header)

        # Profile list widget
        self.profile_list = QListWidget()
        self.profile_list.setStyleSheet("""
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(base);
                color: palette(text);
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:hover:!selected {
                background: palette(midlight);
            }
        """)
        self.profile_list.currentRowChanged.connect(self._on_profile_selected)
        layout.addWidget(self.profile_list, stretch=1)

        # Add/Delete buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
                color: palette(button-text);
            }
            QPushButton:hover {
                background: palette(light);
                border-color: palette(dark);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
        """)
        self.add_btn.clicked.connect(self._on_add_profile)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-weight: 500;
                font-size: 12px;
                color: palette(window-text);
            }
            QPushButton:hover {
                background: #ef4444;
                border-color: #dc2626;
                color: white;
            }
            QPushButton:pressed {
                background: #dc2626;
            }
            QPushButton:disabled {
                color: palette(mid);
                border-color: palette(midlight);
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete_profile)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        return pane

    def _create_profile_editor_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(16)

        basic_section = self._create_basic_settings_section()
        scroll_layout.addWidget(basic_section)

        mapping_section = self._create_mapping_editor_section()
        scroll_layout.addWidget(mapping_section)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        # Placeholder for empty state
        self.empty_state = QLabel("Select a profile to edit, or add a new one.")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setStyleSheet("""
            QLabel {
                color: palette(mid);
                font-size: 13px;
                font-style: italic;
            }
        """)
        self.empty_state.hide()
        layout.addWidget(self.empty_state)

        self.scroll_content = scroll_content
        return pane

    def _create_basic_settings_section(self) -> QFrame:
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                border: 1px solid palette(mid);
                border-radius: 8px;
                background: palette(base);
            }
        """)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Basic Settings")
        header.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: palette(window-text);
                border: none;
                background: transparent;
            }
        """)
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Name field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Profile name...")
        self.name_input.textChanged.connect(self._on_field_changed)
        self._style_input(self.name_input)
        form.addRow(self._create_label("Name"), self.name_input)

        # LingQ Language field
        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText("e.g. sv, de, fr, es...")
        self.language_input.textChanged.connect(self._on_field_changed)
        self._style_input(self.language_input)
        form.addRow(self._create_label("LingQ Language"), self.language_input)

        # Meaning Locale field
        self.locale_input = QLineEdit()
        self.locale_input.setPlaceholderText("e.g. en, sv...")
        self.locale_input.textChanged.connect(self._on_field_changed)
        self._style_input(self.locale_input)
        form.addRow(self._create_label("Meaning Locale"), self.locale_input)

        # API Token field with show/hide toggle
        token_container = QWidget()
        token_layout = QHBoxLayout(token_container)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.setSpacing(8)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("API Token...")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.textChanged.connect(self._on_field_changed)
        self._style_input(self.token_input)

        self.token_toggle_btn = QPushButton("Show")
        self.token_toggle_btn.setFixedWidth(60)
        self.token_toggle_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                background: palette(button);
                border: 1px solid palette(mid);
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                color: palette(button-text);
            }
            QPushButton:hover {
                background: palette(light);
            }
            QPushButton:pressed {
                background: palette(midlight);
            }
        """)
        self.token_toggle_btn.clicked.connect(self._toggle_token_visibility)

        token_layout.addWidget(self.token_input, stretch=1)
        token_layout.addWidget(self.token_toggle_btn)
        form.addRow(self._create_label("API Token"), token_container)

        # Enable Scheduling Writes checkbox
        self.scheduling_checkbox = QCheckBox("Enable scheduling writes to LingQ")
        self.scheduling_checkbox.setStyleSheet("""
            QCheckBox {
                color: palette(text);
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(base);
            }
            QCheckBox::indicator:checked {
                background: palette(highlight);
                border-color: palette(highlight);
            }
            QCheckBox::indicator:hover {
                border-color: palette(dark);
            }
        """)
        self.scheduling_checkbox.stateChanged.connect(self._on_field_changed)
        form.addRow("", self.scheduling_checkbox)

        layout.addLayout(form)
        self.form_container = section
        return section

    def _create_mapping_editor_section(self) -> QFrame:
        section = QFrame()
        section.setStyleSheet("""
            QFrame {
                border: 1px solid palette(mid);
                border-radius: 8px;
                background: palette(base);
            }
        """)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Field Mappings")
        header.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 600;
                color: palette(window-text);
                border: none;
                background: transparent;
            }
        """)
        layout.addWidget(header)

        self._anki_available = _is_anki_available()
        if not self._anki_available:
            notice = QLabel("(Anki not available - type values manually)")
            notice.setStyleSheet("""
                QLabel {
                    color: palette(mid);
                    font-size: 11px;
                    font-style: italic;
                    border: none;
                    background: transparent;
                }
            """)
            layout.addWidget(notice)

        self.mapping_tabs = QTabWidget()
        self.mapping_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(window);
                margin-top: -1px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid palette(mid);
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                background: palette(button);
                color: palette(button-text);
            }
            QTabBar::tab:selected {
                background: palette(window);
                border-bottom: 1px solid palette(window);
            }
            QTabBar::tab:hover:!selected {
                background: palette(light);
            }
        """)

        lingq_to_anki_tab = self._create_lingq_to_anki_tab()
        self.mapping_tabs.addTab(lingq_to_anki_tab, "LingQ → Anki")

        anki_to_lingq_tab = self._create_anki_to_lingq_tab()
        self.mapping_tabs.addTab(anki_to_lingq_tab, "Anki → LingQ")

        layout.addWidget(self.mapping_tabs)
        self.mapping_section = section
        return section

    def _create_lingq_to_anki_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        note_type_container = QVBoxLayout()
        note_type_container.setSpacing(4)
        self.note_type_combo = self._create_combo_or_input("note_type")
        self.note_type_combo.currentTextChanged.connect(self._on_note_type_changed)
        note_type_container.addWidget(self.note_type_combo)
        note_type_hint = QLabel("Anki note type to create/update for LingQ cards")
        self._style_hint(note_type_hint)
        note_type_container.addWidget(note_type_hint)
        note_type_widget = QWidget()
        note_type_widget.setLayout(note_type_container)
        form.addRow(self._create_label("Note Type"), note_type_widget)

        deck_container = QVBoxLayout()
        deck_container.setSpacing(4)
        self.deck_combo = self._create_combo_or_input("deck")
        self.deck_combo.currentTextChanged.connect(self._on_field_changed)
        deck_container.addWidget(self.deck_combo)
        deck_hint = QLabel("Optional: create new notes in this Anki deck")
        self._style_hint(deck_hint)
        deck_container.addWidget(deck_hint)
        deck_widget = QWidget()
        deck_widget.setLayout(deck_container)
        form.addRow(self._create_label("Deck"), deck_widget)

        term_container = QVBoxLayout()
        term_container.setSpacing(4)
        self.term_field_combo = self._create_combo_or_input("field")
        self.term_field_combo.currentTextChanged.connect(self._on_field_changed)
        term_container.addWidget(self.term_field_combo)
        term_hint = QLabel("Anki field to store the LingQ term/word")
        self._style_hint(term_hint)
        term_container.addWidget(term_hint)
        term_widget = QWidget()
        term_widget.setLayout(term_container)
        form.addRow(self._create_label("Term Field"), term_widget)

        trans_container = QVBoxLayout()
        trans_container.setSpacing(4)
        self.translation_field_combo = self._create_combo_or_input("field")
        self.translation_field_combo.currentTextChanged.connect(self._on_field_changed)
        trans_container.addWidget(self.translation_field_combo)
        trans_hint = QLabel("Anki field to store the LingQ translation/hint")
        self._style_hint(trans_hint)
        trans_container.addWidget(trans_hint)
        trans_widget = QWidget()
        trans_widget.setLayout(trans_container)
        form.addRow(self._create_label("Translation Field"), trans_widget)

        layout.addLayout(form)

        identity_group = QGroupBox("Identity Fields")
        identity_group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: 600;
                color: palette(window-text);
                border: 1px solid palette(mid);
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)
        identity_layout = QFormLayout(identity_group)
        identity_layout.setSpacing(10)
        identity_layout.setContentsMargins(12, 8, 12, 12)
        identity_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        pk_container = QVBoxLayout()
        pk_container.setSpacing(4)
        self.pk_field_combo = self._create_combo_or_input("field")
        self.pk_field_combo.currentTextChanged.connect(self._on_field_changed)
        pk_container.addWidget(self.pk_field_combo)
        pk_hint = QLabel("Stores LingQ card ID for stable sync")
        self._style_hint(pk_hint)
        pk_container.addWidget(pk_hint)
        pk_widget = QWidget()
        pk_widget.setLayout(pk_container)
        identity_layout.addRow(self._create_label("PK Field"), pk_widget)

        canonical_container = QVBoxLayout()
        canonical_container.setSpacing(4)
        self.canonical_term_combo = self._create_combo_or_input("field")
        self.canonical_term_combo.currentTextChanged.connect(self._on_field_changed)
        canonical_container.addWidget(self.canonical_term_combo)
        canonical_hint = QLabel("Stores normalized term for matching")
        self._style_hint(canonical_hint)
        canonical_container.addWidget(canonical_hint)
        canonical_widget = QWidget()
        canonical_widget.setLayout(canonical_container)
        identity_layout.addRow(self._create_label("Canonical Term"), canonical_widget)

        layout.addWidget(identity_group)
        layout.addStretch()
        return tab

    def _create_anki_to_lingq_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        term_container = QVBoxLayout()
        term_container.setSpacing(4)
        self.anki_term_field_combo = self._create_combo_or_input("field")
        self.anki_term_field_combo.currentTextChanged.connect(self._on_field_changed)
        term_container.addWidget(self.anki_term_field_combo)
        term_hint = QLabel("Anki field containing the term to sync back to LingQ")
        self._style_hint(term_hint)
        term_container.addWidget(term_hint)
        term_widget = QWidget()
        term_widget.setLayout(term_container)
        form.addRow(self._create_label("Term Field"), term_widget)

        trans_container = QVBoxLayout()
        trans_container.setSpacing(4)
        trans_label = QLabel("Select fields containing translations:")
        trans_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: palette(window-text);
            }
        """)
        trans_container.addWidget(trans_label)

        self.translation_fields_list = QListWidget()
        self.translation_fields_list.setMaximumHeight(100)
        self.translation_fields_list.setStyleSheet("""
            QListWidget {
                border: 1px solid palette(mid);
                border-radius: 4px;
                background: palette(window);
                color: palette(text);
            }
            QListWidget::item {
                padding: 4px 8px;
            }
            QListWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        self.translation_fields_list.itemChanged.connect(self._on_field_changed)
        trans_container.addWidget(self.translation_fields_list)

        trans_hint = QLabel(
            "Check all fields that contain translations to sync to LingQ hints"
        )
        self._style_hint(trans_hint)
        trans_container.addWidget(trans_hint)
        trans_widget = QWidget()
        trans_widget.setLayout(trans_container)
        form.addRow(self._create_label("Translation Fields"), trans_widget)

        template_container = QVBoxLayout()
        template_container.setSpacing(4)
        self.primary_template_combo = self._create_combo_or_input("template")
        self.primary_template_combo.currentTextChanged.connect(self._on_field_changed)
        template_container.addWidget(self.primary_template_combo)
        template_hint = QLabel("Card template used as primary (optional)")
        self._style_hint(template_hint)
        template_container.addWidget(template_hint)
        template_widget = QWidget()
        template_widget.setLayout(template_container)
        form.addRow(self._create_label("Primary Template"), template_widget)

        fragment_container = QVBoxLayout()
        fragment_container.setSpacing(4)
        self.fragment_field_combo = self._create_combo_or_input("field")
        self.fragment_field_combo.currentTextChanged.connect(self._on_field_changed)
        fragment_container.addWidget(self.fragment_field_combo)
        fragment_hint = QLabel(
            "Optional: Anki field containing example usage/source text to send to LingQ (only on create)"
        )
        self._style_hint(fragment_hint)
        fragment_container.addWidget(fragment_hint)
        fragment_widget = QWidget()
        fragment_widget.setLayout(fragment_container)
        form.addRow(self._create_label("Example Field"), fragment_widget)

        layout.addLayout(form)
        layout.addStretch()
        return tab

    def _create_combo_or_input(self, combo_type: str) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(window);
                color: palette(text);
                font-size: 13px;
                min-width: 150px;
            }
            QComboBox:focus {
                border-color: palette(highlight);
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background: palette(base);
                color: palette(text);
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
                border: 1px solid palette(mid);
                border-radius: 4px;
            }
        """)

        if self._anki_available and combo_type == "note_type":
            note_types = _get_anki_note_types()
            combo.addItems(note_types)
        elif self._anki_available and combo_type == "deck":
            combo.addItem("")
            combo.addItems(_get_anki_deck_names())
        elif not self._anki_available:
            combo.lineEdit().setPlaceholderText("(Requires Anki)")

        return combo

    def _style_hint(self, label: QLabel) -> None:
        label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: palette(mid);
                font-style: italic;
            }
        """)

    def _on_note_type_changed(self, note_type_name: str) -> None:
        self._unsaved_changes = True
        self._update_field_combos_for_note_type(note_type_name)
        self._validate_form()

    def _update_field_combos_for_note_type(self, note_type_name: str) -> None:
        if not self._anki_available or not note_type_name:
            return

        fields = _get_anki_fields_for_note_type(note_type_name)
        templates = _get_anki_templates_for_note_type(note_type_name)

        field_combos = [
            self.term_field_combo,
            self.translation_field_combo,
            self.pk_field_combo,
            self.canonical_term_combo,
            self.anki_term_field_combo,
            self.fragment_field_combo,
        ]

        for combo in field_combos:
            current_text = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(fields)
            if current_text and current_text in fields:
                combo.setCurrentText(current_text)
            elif current_text:
                combo.setEditText(current_text)
            combo.blockSignals(False)

        self.translation_fields_list.blockSignals(True)
        checked_fields = self._get_checked_translation_fields()
        self.translation_fields_list.clear()
        for field_name in fields:
            item = QListWidgetItem(field_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if field_name in checked_fields
                else Qt.CheckState.Unchecked
            )
            self.translation_fields_list.addItem(item)
        self.translation_fields_list.blockSignals(False)

        current_template = self.primary_template_combo.currentText()
        self.primary_template_combo.blockSignals(True)
        self.primary_template_combo.clear()
        self.primary_template_combo.addItem("")
        self.primary_template_combo.addItems(templates)
        if current_template and current_template in templates:
            self.primary_template_combo.setCurrentText(current_template)
        elif current_template:
            self.primary_template_combo.setEditText(current_template)
        self.primary_template_combo.blockSignals(False)

    def _get_checked_translation_fields(self) -> List[str]:
        checked = []
        for i in range(self.translation_fields_list.count()):
            item = self.translation_fields_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(item.text())
        return checked

    def _create_label(self, text: str) -> QLabel:
        """Create a styled form label."""
        label = QLabel(text)
        label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                font-weight: 500;
                color: palette(window-text);
                background: transparent;
                border: none;
            }
        """)
        return label

    def _style_input(self, widget: "QLineEdit") -> None:
        """Apply consistent styling to input widgets."""
        widget.setStyleSheet("""
            QLineEdit {
                padding: 10px 12px;
                border: 1px solid palette(mid);
                border-radius: 6px;
                background: palette(window);
                color: palette(text);
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: palette(highlight);
            }
            QLineEdit:disabled {
                background: palette(midlight);
                color: palette(mid);
            }
        """)

    def _create_footer(self) -> QHBoxLayout:
        """Create the footer with Save and Cancel buttons."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Validation message
        self.validation_msg = QLabel("")
        self.validation_msg.setStyleSheet("""
            QLabel {
                color: #ef4444;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.validation_msg)
        layout.addStretch()

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: transparent;
                border: 1px solid palette(mid);
                border-radius: 6px;
                font-weight: 500;
                font-size: 13px;
                color: palette(window-text);
            }
            QPushButton:hover {
                background: palette(button);
                border-color: palette(dark);
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel)

        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                background: palette(highlight);
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                color: palette(highlighted-text);
            }
            QPushButton:hover {
                background: palette(highlight);
            }
            QPushButton:disabled {
                background: palette(mid);
                color: palette(midlight);
            }
        """)
        self.save_btn.clicked.connect(self._on_save)

        layout.addWidget(self.cancel_btn)
        layout.addWidget(self.save_btn)

        return layout

    def _apply_styles(self) -> None:
        """Apply global dialog styles."""
        self.setStyleSheet("""
            QDialog {
                background: palette(window);
            }
        """)

    # === Data Loading ===

    def _load_config(self) -> None:
        """Load configuration and populate profile list."""
        try:
            self._config = load_config()
        except Exception:
            self._config = Config()

        self._populate_profile_list()
        self._update_editor_state()

    def _populate_profile_list(self) -> None:
        """Populate the profile list widget."""
        self.profile_list.clear()
        if self._config and self._config.profiles:
            for profile in self._config.profiles:
                item = QListWidgetItem(profile.name)
                self.profile_list.addItem(item)

            # Select first profile by default
            if self._config.profiles:
                self.profile_list.setCurrentRow(0)
        else:
            self._current_profile_index = -1

        self._update_button_states()

    def _update_editor_state(self) -> None:
        has_selection = self._current_profile_index >= 0
        self.form_container.setVisible(has_selection)
        self.mapping_section.setVisible(has_selection)
        self.empty_state.setVisible(not has_selection)

        if has_selection:
            self._load_profile_to_form()
        else:
            self._clear_form()

    def _load_profile_to_form(self) -> None:
        if not self._config or self._current_profile_index < 0:
            return

        if self._current_profile_index >= len(self._config.profiles):
            return

        profile = self._config.profiles[self._current_profile_index]

        self.name_input.blockSignals(True)
        self.language_input.blockSignals(True)
        self.locale_input.blockSignals(True)
        self.token_input.blockSignals(True)
        self.scheduling_checkbox.blockSignals(True)
        self.note_type_combo.blockSignals(True)
        self.deck_combo.blockSignals(True)
        self.term_field_combo.blockSignals(True)
        self.translation_field_combo.blockSignals(True)
        self.pk_field_combo.blockSignals(True)
        self.canonical_term_combo.blockSignals(True)
        self.anki_term_field_combo.blockSignals(True)
        self.translation_fields_list.blockSignals(True)
        self.primary_template_combo.blockSignals(True)
        self.fragment_field_combo.blockSignals(True)

        self.name_input.setText(profile.name)
        self.language_input.setText(profile.lingq_language)
        self.locale_input.setText(profile.meaning_locale)
        self.token_input.setText(profile.api_token)
        self.scheduling_checkbox.setChecked(profile.enable_scheduling_writes)

        l2a = profile.lingq_to_anki
        self.note_type_combo.setCurrentText(l2a.note_type)
        self.deck_combo.setCurrentText(getattr(l2a, "deck_name", None) or "")
        self._update_field_combos_for_note_type(l2a.note_type)

        term_field = l2a.field_mapping.get("term", "")
        translation_field = l2a.field_mapping.get("translation", "")
        self.term_field_combo.setCurrentText(term_field)
        self.translation_field_combo.setCurrentText(translation_field)

        self.pk_field_combo.setCurrentText(l2a.identity_fields.pk_field)
        self.canonical_term_combo.setCurrentText(
            l2a.identity_fields.canonical_term_field
        )

        a2l = profile.anki_to_lingq
        self.anki_term_field_combo.setCurrentText(a2l.term_field)

        for i in range(self.translation_fields_list.count()):
            item = self.translation_fields_list.item(i)
            if item:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.text() in a2l.translation_fields
                    else Qt.CheckState.Unchecked
                )

        self.primary_template_combo.setCurrentText(a2l.primary_card_template or "")
        self.fragment_field_combo.setCurrentText(a2l.fragment_field or "")

        self.name_input.blockSignals(False)
        self.language_input.blockSignals(False)
        self.locale_input.blockSignals(False)
        self.token_input.blockSignals(False)
        self.scheduling_checkbox.blockSignals(False)
        self.note_type_combo.blockSignals(False)
        self.deck_combo.blockSignals(False)
        self.term_field_combo.blockSignals(False)
        self.translation_field_combo.blockSignals(False)
        self.pk_field_combo.blockSignals(False)
        self.canonical_term_combo.blockSignals(False)
        self.anki_term_field_combo.blockSignals(False)
        self.translation_fields_list.blockSignals(False)
        self.primary_template_combo.blockSignals(False)
        self.fragment_field_combo.blockSignals(False)

        self.validation_msg.setText("")

    def _clear_form(self) -> None:
        self.name_input.clear()
        self.language_input.clear()
        self.locale_input.clear()
        self.token_input.clear()
        self.scheduling_checkbox.setChecked(False)

        self.note_type_combo.setCurrentText("")
        self.deck_combo.setCurrentText("")
        self.term_field_combo.setCurrentText("")
        self.translation_field_combo.setCurrentText("")
        self.pk_field_combo.setCurrentText("")
        self.canonical_term_combo.setCurrentText("")
        self.anki_term_field_combo.setCurrentText("")
        self.translation_fields_list.clear()
        self.primary_template_combo.setCurrentText("")
        self.fragment_field_combo.setCurrentText("")

        self.validation_msg.setText("")

    def _update_button_states(self) -> None:
        """Update button enabled states."""
        has_profiles = bool(self._config and self._config.profiles)
        has_selection = self._current_profile_index >= 0
        self.delete_btn.setEnabled(has_profiles and has_selection)

    # === Event Handlers ===

    def _on_profile_selected(self, index: int) -> None:
        """Handle profile selection change."""
        if self._unsaved_changes and self._current_profile_index >= 0:
            self._save_current_profile_to_config()

        self._current_profile_index = index
        self._update_editor_state()
        self._update_button_states()
        self._unsaved_changes = False

    def _on_field_changed(self) -> None:
        """Handle form field changes."""
        self._unsaved_changes = True
        self._validate_form()

    def _on_add_profile(self) -> None:
        if not self._config:
            self._config = Config()

        if self._unsaved_changes and self._current_profile_index >= 0:
            self._save_current_profile_to_config()

        note_types = _get_anki_note_types() if self._anki_available else []
        default_note_type = (
            "Basic"
            if "Basic" in note_types
            else (note_types[0] if note_types else "Basic")
        )

        fields = (
            _get_anki_fields_for_note_type(default_note_type)
            if self._anki_available
            else []
        )
        default_term = (
            "Front" if "Front" in fields else (fields[0] if fields else "Front")
        )
        default_trans = (
            "Back" if "Back" in fields else (fields[1] if len(fields) > 1 else "Back")
        )

        new_profile = Profile(
            name=f"New Profile {len(self._config.profiles) + 1}",
            lingq_language="",
            meaning_locale="en",
            lingq_to_anki=LingqToAnkiMapping(
                note_type=default_note_type,
                field_mapping={"term": default_term, "translation": default_trans},
                identity_fields=IdentityFields(),
            ),
            anki_to_lingq=AnkiToLingqMapping(
                term_field=default_term,
                translation_fields=[default_trans] if default_trans else [],
            ),
            api_token="",
            enable_scheduling_writes=False,
        )
        self._config.profiles.append(new_profile)

        item = QListWidgetItem(new_profile.name)
        self.profile_list.addItem(item)
        self.profile_list.setCurrentRow(len(self._config.profiles) - 1)

        self._unsaved_changes = True
        self._update_button_states()

    def _on_delete_profile(self) -> None:
        """Delete the selected profile."""
        if not self._config or self._current_profile_index < 0:
            return

        if self._current_profile_index >= len(self._config.profiles):
            return

        profile_name = self._config.profiles[self._current_profile_index].name

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f'Are you sure you want to delete "{profile_name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove from config and list
        del self._config.profiles[self._current_profile_index]
        self.profile_list.takeItem(self._current_profile_index)

        # Update selection
        if self._config.profiles:
            new_index = min(self._current_profile_index, len(self._config.profiles) - 1)
            self.profile_list.setCurrentRow(new_index)
        else:
            self._current_profile_index = -1
            self._update_editor_state()

        self._unsaved_changes = True
        self._update_button_states()

    def _toggle_token_visibility(self) -> None:
        """Toggle API token visibility."""
        if self.token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.token_toggle_btn.setText("Hide")
        else:
            self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.token_toggle_btn.setText("Show")

    def _validate_form(self) -> bool:
        errors = []

        if not self.name_input.text().strip():
            errors.append("Name is required")
        if not self.language_input.text().strip():
            errors.append("LingQ Language is required")
        if not self.locale_input.text().strip():
            errors.append("Meaning Locale is required")
        if not self.token_input.text().strip():
            errors.append("API Token is required")

        if not self.note_type_combo.currentText().strip():
            errors.append("Note Type is required")
        if not self.term_field_combo.currentText().strip():
            errors.append("Term Field is required")
        if not self.translation_field_combo.currentText().strip():
            errors.append("Translation Field is required")
        if not self.pk_field_combo.currentText().strip():
            errors.append("PK Field is required")
        if not self.canonical_term_combo.currentText().strip():
            errors.append("Canonical Term Field is required")

        if not self.anki_term_field_combo.currentText().strip():
            errors.append("Anki Term Field is required")
        if not self._get_checked_translation_fields():
            errors.append("At least one Translation Field must be selected")

        # fragment_field is optional

        if errors:
            self.validation_msg.setText(errors[0])
            return False

        self.validation_msg.setText("")
        return True

    def _save_current_profile_to_config(self) -> None:
        if not self._config or self._current_profile_index < 0:
            return

        if self._current_profile_index >= len(self._config.profiles):
            return

        profile = self._config.profiles[self._current_profile_index]
        profile.name = self.name_input.text().strip()
        profile.lingq_language = self.language_input.text().strip()
        profile.meaning_locale = self.locale_input.text().strip()
        profile.api_token = self.token_input.text()
        profile.enable_scheduling_writes = self.scheduling_checkbox.isChecked()

        profile.lingq_to_anki.note_type = self.note_type_combo.currentText().strip()
        deck_name = self.deck_combo.currentText().strip()
        profile.lingq_to_anki.deck_name = deck_name if deck_name else None
        profile.lingq_to_anki.field_mapping = {
            "term": self.term_field_combo.currentText().strip(),
            "translation": self.translation_field_combo.currentText().strip(),
        }
        profile.lingq_to_anki.identity_fields = IdentityFields(
            pk_field=self.pk_field_combo.currentText().strip(),
            canonical_term_field=self.canonical_term_combo.currentText().strip(),
        )

        profile.anki_to_lingq.term_field = (
            self.anki_term_field_combo.currentText().strip()
        )
        profile.anki_to_lingq.translation_fields = (
            self._get_checked_translation_fields()
        )
        template = self.primary_template_combo.currentText().strip()
        profile.anki_to_lingq.primary_card_template = template if template else None

        frag_field = self.fragment_field_combo.currentText().strip()
        profile.anki_to_lingq.fragment_field = frag_field if frag_field else None

        item = self.profile_list.item(self._current_profile_index)
        if item:
            item.setText(profile.name)

    def _on_save(self) -> None:
        """Save configuration and close dialog."""
        if not self._validate_form():
            return

        # Save current profile to config
        self._save_current_profile_to_config()

        # Persist to disk
        if self._config:
            try:
                save_config(self._config)
                self._unsaved_changes = False
                self.accept()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Save Error",
                    f"Failed to save configuration: {e}",
                )

    def _on_cancel(self) -> None:
        """Close dialog without saving."""
        if self._unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.reject()

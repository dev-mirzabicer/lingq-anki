# pyright: reportMissingImports=false
import importlib

qt = importlib.import_module("aqt.qt")
QDialog = qt.QDialog
QVBoxLayout = qt.QVBoxLayout
QTextEdit = qt.QTextEdit
QPushButton = qt.QPushButton
QLabel = qt.QLabel


class SyncDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LingQ Sync")
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        title = QLabel("LingQ Sync (placeholder)")
        layout.addWidget(title)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QLineEdit, QTextEdit, QFileDialog, QMessageBox
)

class TokenCreationDialog(QDialog):
    def __init__(self, ruleset_manager, parent=None):
        super().__init__(parent)
        self.rm = ruleset_manager
        self.selected_token_data = None
        self.setWindowTitle("Create Token / Assign Ruleset Profile")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # Token Name
        layout.addWidget(QLabel("Token / Character Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Survivor 01, Aragorn, Intercessor...")
        layout.addWidget(self.name_input)

        # 1. Select Game / Ruleset Dropdown
        sys_header = QHBoxLayout()
        sys_header.addWidget(QLabel("Game Ruleset:"))
        self.import_btn = QPushButton("Import Ruleset (.json)")
        self.import_btn.clicked.connect(self.handle_import_ruleset)
        sys_header.addWidget(self.import_btn)
        layout.addLayout(sys_header)

        self.system_combo = QComboBox()
        self.system_combo.addItems(self.rm.get_available_systems())
        self.system_combo.currentTextChanged.connect(self.on_system_changed)
        layout.addWidget(self.system_combo)

        # 2. Select Class / Background Type
        layout.addWidget(QLabel("Category (Class / Background / Job):"))
        self.category_combo = QComboBox()
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        layout.addWidget(self.category_combo)

        # 3. Specific Option Dropdown
        layout.addWidget(QLabel("Specific Selection:"))
        self.specific_option_combo = QComboBox()
        self.specific_option_combo.currentIndexChanged.connect(self.on_option_selected)
        layout.addWidget(self.specific_option_combo)

        # Preview Box
        layout.addWidget(QLabel("Profile Details & Starting Gear:"))
        self.details_preview = QTextEdit()
        self.details_preview.setReadOnly(True)
        self.details_preview.setMaximumHeight(110)
        layout.addWidget(self.details_preview)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.create_btn = QPushButton("Create Token")
        self.create_btn.clicked.connect(self.accept_token)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.create_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        if self.system_combo.count() > 0:
            self.on_system_changed(self.system_combo.currentText())

    def handle_import_ruleset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Ruleset JSON", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                self.rm.import_ruleset(file_path)
                current = self.system_combo.currentText()
                self.system_combo.blockSignals(True)
                self.system_combo.clear()
                self.system_combo.addItems(self.rm.get_available_systems())
                if current in self.rm.get_available_systems():
                    self.system_combo.setCurrentText(current)
                self.system_combo.blockSignals(False)
                self.on_system_changed(self.system_combo.currentText())
                QMessageBox.information(self, "Imported", "Ruleset imported successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Import Error", str(e))

    def on_system_changed(self, system_name):
        self.rm.set_active_ruleset(system_name)
        categories = self.rm.get_character_categories(system_name)
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItems(categories)
        self.category_combo.blockSignals(False)
        self.on_category_changed(self.category_combo.currentText())

    def on_category_changed(self, category):
        system_name = self.system_combo.currentText()
        options = self.rm.get_character_options(category, system_name)
        self.specific_option_combo.blockSignals(True)
        self.specific_option_combo.clear()
        for opt in options:
            self.specific_option_combo.addItem(opt.get("name", "Unnamed"), opt)
        self.specific_option_combo.blockSignals(False)
        self.on_option_selected(0)

    def on_option_selected(self, index):
        opt = self.specific_option_combo.currentData()
        if not opt:
            self.details_preview.clear()
            return
        lines = []
        for k, v in opt.items():
            if k != "name":
                label = k.replace("_", " ").title()
                val = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
                lines.append(f"{label}: {val}")
        self.details_preview.setPlainText("\n".join(lines))

    def accept_token(self):
        self.selected_token_data = {
            "name": self.name_input.text().strip() or "Unnamed Token",
            "ruleset": self.system_combo.currentText(),
            "category": self.category_combo.currentText(),
            "profile": self.specific_option_combo.currentData() or {}
        }
        self.accept()

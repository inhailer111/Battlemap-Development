import random
from pathlib import Path
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout,
)
from core.config import (
    BUILDING_KINDS, STATUS_COLORS, BASE_DIR, TOKENS_DIR,
    swatch, auto_initials,
)
from core.rulesets import RulesetManager

# ----------------------------------------------------------------------------- dialogs
class TokenDialog(QDialog):
    def __init__(self, parent, props):
        super().__init__(parent)
        self.setWindowTitle("Edit Token & Ruleset Profile")
        self.setMinimumWidth(400)
        self.color = QColor(props["color"])
        self.aura_color = QColor(props.get("aura_color", "#3b82f6"))
        self.image_path = props.get("image_path", "")
        self.ruleset_manager = getattr(parent, "ruleset_manager", None) or RulesetManager()
        self.existing_profile = props.get("profile", {})
        form = QFormLayout(self)

        self.name = QLineEdit(props["name"])
        self.ini = QLineEdit(props["initials"])
        self.size = QSpinBox()
        self.size.setRange(1, 8)
        self.size.setValue(props["size"])
        self.size.setSuffix(" square(s)")
        self.btn = QPushButton()
        swatch(self.btn, self.color)
        self.btn.clicked.connect(self.pick)

        img_row = QHBoxLayout()
        self.img_label = QLabel(Path(self.image_path).name if self.image_path else "(initials)")
        self.img_label.setStyleSheet("color:#9ca3af;")
        b_img = QPushButton("Choose Image...")
        b_img.clicked.connect(self.pick_image)
        b_clr = QPushButton("Clear")
        b_clr.clicked.connect(self.clear_image)
        img_row.addWidget(self.img_label, 1)
        img_row.addWidget(b_img)
        img_row.addWidget(b_clr)

        form.addRow("Name", self.name)
        form.addRow("Initials", self.ini)
        form.addRow("Color", self.btn)
        form.addRow("Portrait", img_row)
        form.addRow("Size", self.size)

        # Ruleset & Job/Class Assignment
        self.sys_combo = QComboBox()
        self.sys_combo.addItems(self.ruleset_manager.get_available_systems())
        active_sys = props.get("ruleset") or self.ruleset_manager.active_ruleset_name
        if active_sys in self.ruleset_manager.get_available_systems():
            self.sys_combo.setCurrentText(active_sys)
        self.sys_combo.currentTextChanged.connect(self.on_sys_changed)
        form.addRow("Game Ruleset", self.sys_combo)

        self.cat_combo = QComboBox()
        self.cat_combo.currentTextChanged.connect(self.on_cat_changed)
        form.addRow("Option Category", self.cat_combo)

        self.opt_combo = QComboBox()
        form.addRow("Class / Background / Job", self.opt_combo)

        self.player = QCheckBox("Player token (shares vision with the party)")
        self.player.setChecked(props.get("player", False))
        self.mod = QSpinBox()
        self.mod.setRange(-1000, 5000)
        self.mod.setSingleStep(10)
        self.mod.setSuffix(" ft")
        self.mod.setValue(props.get("vision_mod", 0))
        form.addRow(self.player)
        form.addRow("Vision modifier", self.mod)

        aura_row = QHBoxLayout()
        self.aura_spin = QSpinBox()
        self.aura_spin.setRange(0, 500)
        self.aura_spin.setSingleStep(5)
        self.aura_spin.setSuffix(" ft")
        self.aura_spin.setValue(props.get("aura_ft", 0))
        self.aura_btn = QPushButton()
        swatch(self.aura_btn, self.aura_color)
        self.aura_btn.clicked.connect(self.pick_aura)
        aura_row.addWidget(self.aura_spin)
        aura_row.addWidget(self.aura_btn)
        form.addRow("Aura radius", aura_row)

        form.addRow(QLabel("<b>Status Conditions</b>"))
        self.status_checks = {}
        cur_statuses = set(props.get("statuses", []))
        st_box = QHBoxLayout()
        col1, col2 = QVBoxLayout(), QVBoxLayout()
        for idx, sname in enumerate(STATUS_COLORS):
            cb = QCheckBox(sname)
            cb.setChecked(sname in cur_statuses)
            self.status_checks[sname] = cb
            (col1 if idx % 2 == 0 else col2).addWidget(cb)
        st_box.addLayout(col1)
        st_box.addLayout(col2)
        form.addRow(st_box)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

        if self.sys_combo.count() > 0:
            self.on_sys_changed(self.sys_combo.currentText())

        saved_profile_name = props.get("profile_name", "") or self.existing_profile.get("name", "")
        if saved_profile_name:
            idx = self.opt_combo.findText(saved_profile_name)
            if idx >= 0:
                self.opt_combo.setCurrentIndex(idx)

    def on_sys_changed(self, sys_name):
        self.ruleset_manager.set_active_ruleset(sys_name)
        cats = self.ruleset_manager.get_character_categories(sys_name)
        self.cat_combo.blockSignals(True)
        self.cat_combo.clear()
        self.cat_combo.addItems(cats)
        self.cat_combo.blockSignals(False)
        self.on_cat_changed(self.cat_combo.currentText())

    def on_cat_changed(self, cat):
        sys_name = self.sys_combo.currentText()
        opts = self.ruleset_manager.get_character_options(cat, sys_name)
        self.opt_combo.blockSignals(True)
        self.opt_combo.clear()
        self.opt_combo.addItem("(None / Auto-match by name)", {})
        for opt in opts:
            self.opt_combo.addItem(opt.get("name", "Unnamed"), opt)
        self.opt_combo.blockSignals(False)

    def pick(self):
        c = QColorDialog.getColor(self.color, self, "Token color")
        if c.isValid():
            self.color = c
            swatch(self.btn, c)

    def pick_aura(self):
        c = QColorDialog.getColor(self.aura_color, self, "Aura color")
        if c.isValid():
            self.aura_color = c
            swatch(self.aura_btn, c)

    def pick_image(self):
        start_dir = str(TOKENS_DIR if TOKENS_DIR.exists() else BASE_DIR)
        path, _ = QFileDialog.getOpenFileName(self, "Token Portrait", start_dir, "Images (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self.image_path = path
            self.img_label.setText(Path(path).name)

    def clear_image(self):
        self.image_path = ""
        self.img_label.setText("(initials)")

    def result_props(self):
        name = self.name.text().strip()
        selected_opt = self.opt_combo.currentData()
        if not isinstance(selected_opt, dict):
            selected_opt = {}
        return {"name": name, "initials": self.ini.text().strip() or auto_initials(name),
                "color": self.color.name(), "size": self.size.value(),
                "player": self.player.isChecked(), "vision_mod": self.mod.value(),
                "statuses": [k for k, cb in self.status_checks.items() if cb.isChecked()],
                "aura_ft": self.aura_spin.value(), "aura_color": self.aura_color.name(),
                "image_path": self.image_path,
                "ruleset": self.sys_combo.currentText(),
                "category": self.cat_combo.currentText(),
                "profile_name": selected_opt.get("name", ""),
                "profile": selected_opt}


class CategoryDialog(QDialog):
    def __init__(self, parent, cat):
        super().__init__(parent)
        self.setWindowTitle("Token Category")
        self.color = QColor(cat["color"])
        form = QFormLayout(self)
        self.name = QLineEdit(cat["name"])
        self.ini = QLineEdit(cat.get("initials", ""))
        self.ini.setPlaceholderText("auto")
        self.size = QSpinBox()
        self.size.setRange(1, 8)
        self.size.setValue(cat["size"])
        self.size.setSuffix(" square(s)")
        self.btn = QPushButton()
        swatch(self.btn, self.color)
        self.btn.clicked.connect(self.pick)
        self.player = QCheckBox("Player token (shares vision with the party)")
        self.player.setChecked(cat.get("player", False))
        self.numbered = QCheckBox("Number each one (Walker 1, Walker 2...)")
        self.numbered.setChecked(cat.get("numbered", False))
        form.addRow("Category name", self.name)
        form.addRow("Initials", self.ini)
        form.addRow("Color", self.btn)
        form.addRow("Size", self.size)
        form.addRow(self.player)
        form.addRow(self.numbered)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def pick(self):
        c = QColorDialog.getColor(self.color, self, "Token color")
        if c.isValid():
            self.color = c
            swatch(self.btn, c)

    def result_cat(self):
        return {"name": self.name.text().strip() or "Token", "initials": self.ini.text().strip(),
                "color": self.color.name(), "size": self.size.value(),
                "player": self.player.isChecked(), "numbered": self.numbered.isChecked()}


class GenerateDialog(QDialog):
    SIZES = [("Small (120 x 80 miles)", 120, 80), ("Medium (240 x 160 miles)", 240, 160),
             ("Large (360 x 240 miles)", 360, 240)]
    GENRES = [("Modern / Zombie Apocalypse", "apocalypse"), ("High Fantasy", "fantasy"),
              ("Sci-Fi / Cyberpunk", "scifi"), ("Western / Frontier", "western")]

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Generate a World / Region")
        form = QFormLayout(self)

        self.genre_combo = QComboBox()
        self.genre_combo.addItems([label for label, _ in self.GENRES])
        self.genre_combo.currentIndexChanged.connect(self._on_genre_changed)
        form.addRow("Genre / Theme", self.genre_combo)

        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(random.randrange(1, 100000))
        rnd = QPushButton("Random")
        rnd.clicked.connect(lambda: self.seed.setValue(random.randrange(1, 100000)))
        row = QHBoxLayout()
        row.addWidget(self.seed)
        row.addWidget(rnd)
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Coastal & Mountain Ridge", "Varied (changes with seed)"])
        self.size_combo = QComboBox()
        self.size_combo.addItems([name for name, _w, _h in self.SIZES])
        self.size_combo.setCurrentIndex(1)
        self.density = QComboBox()
        self.density.addItems(["Low", "Medium", "High"])
        self.density.setCurrentIndex(1)
        form.addRow("Seed", row)
        form.addRow("Geography", self.layout_combo)
        form.addRow("Size", self.size_combo)
        form.addRow("Settlement density", self.density)

        form.addRow(QLabel("<b>Street-Level Encounters & Clutter</b>"))
        self.checks = {}
        for key, text in (("cars", "Vehicles / Wagons along roads"), ("barricades", "Barricades & roadblocks"),
                          ("rubble", "Rubble & debris"), ("overgrowth", "Wild overgrowth"), ("zombies", "Hostile encounters")):
            cb = QCheckBox(text)
            cb.setChecked(True)
            self.checks[key] = cb
            form.addRow(cb)
        note = QLabel("Streets and buildings are built on the fly as you zoom in on a settlement.\nThe map continues infinitely past the edge of the region.")
        note.setStyleSheet("color:#9ca3af;")
        form.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _on_genre_changed(self, idx):
        genre = self.GENRES[idx][1]
        is_apoc = (genre == "apocalypse")
        self.checks["rubble"].setChecked(is_apoc)
        self.checks["barricades"].setChecked(is_apoc)

    def options(self):
        _name, wmi, hmi = self.SIZES[self.size_combo.currentIndex()]
        genre = self.GENRES[self.genre_combo.currentIndex()][1]
        return {"seed": self.seed.value(), "layout": "washington" if self.layout_combo.currentIndex() == 0 else "varied",
                "width_mi": wmi, "height_mi": hmi, "density": self.density.currentIndex(),
                "genre": genre, "zombies": {k: cb.isChecked() for k, cb in self.checks.items()}}


class BuildingDialog(QDialog):
    def __init__(self, parent, props):
        super().__init__(parent)
        self.setWindowTitle("Edit Building")
        form = QFormLayout(self)
        self.kind = QComboBox()
        self.kind.addItems(list(BUILDING_KINDS))
        self.kind.setCurrentText(props["kind"])
        self.label = QLineEdit(props["label"])
        form.addRow("Type", self.kind)
        form.addRow("Label", self.label)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def result_props(self):
        return {"kind": self.kind.currentText(), "label": self.label.text().strip()}


class DungeonDialog(QDialog):
    GENRES = [("High Fantasy (Crypt / Keep / Cavern)", "fantasy"),
              ("Sci-Fi / Derelict Station", "scifi"),
              ("Modern / Bunker / Sewer", "apocalypse"),
              ("Western / Abandoned Mine", "western")]

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Generate Dungeon")
        form = QFormLayout(self)

        self.genre_combo = QComboBox()
        self.genre_combo.addItems([label for label, _ in self.GENRES])
        form.addRow("Theme", self.genre_combo)

        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(random.randrange(1, 100000))
        rnd = QPushButton("Random")
        rnd.clicked.connect(lambda: self.seed.setValue(random.randrange(1, 100000)))
        row = QHBoxLayout()
        row.addWidget(self.seed)
        row.addWidget(rnd)
        form.addRow("Seed", row)

        self.rooms_spin = QSpinBox()
        self.rooms_spin.setRange(4, 30)
        self.rooms_spin.setValue(10)
        self.rooms_spin.setSuffix(" rooms")
        form.addRow("Size", self.rooms_spin)

        note = QLabel("Creates stone rooms, corridors, interactive closed doors, vision-blocking walls,\ndungeon props, and encounters. Click any orange door to open it!")
        note.setStyleSheet("color:#9ca3af;")
        form.addRow(note)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def options(self):
        return {
            "seed": self.seed.value(),
            "rooms": self.rooms_spin.value(),
            "genre": self.GENRES[self.genre_combo.currentIndex()][1],
        }


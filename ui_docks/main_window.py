import json
import math
import random
import re
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap, QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QDialog, QFileDialog,
    QGraphicsScene, QLabel, QListWidgetItem, QMainWindow, QMessageBox, QSpinBox,
)
from core.config import (
    UNITS_PER_FT, CELL, HALF, LIGHT_PEN, DARK_PEN,
    LEVELS, JUMP_PX, GENRE_CATEGORIES, MAPS_DIR, APP_STYLESHEET,
    Zoom, Tokens, level_for_zoom, fmt_len, load_categories, save_categories, spiral_offsets,
    swatch, auto_initials, make_icon,
)
from core.math_utils import Snap, snap_point_to_grid
from core.rulesets import RulesetManager, RulesetSettingsDialog
from core.clock_dice import CampaignClock
from map_canvas.canvas_items import (
    UnderlayItem, TokenItem, BuildingItem, item_from_dict,
)
from map_canvas.vision import Vision, reset_explored
from map_canvas.world_assets import Atlas, _ASSET_CACHE, ensure_assets, list_all_props
from map_canvas.overlays import Pointer, Ruler, Template, Chalk, EditTokenCommand
from map_canvas.views import MapView
from ui_docks.dialogs import TokenDialog, CategoryDialog, BuildingDialog
from ui_docks.dock_panels import DockPanelsMixin
from ui_docks.session_controller import SessionControllerMixin


class MainWindow(DockPanelsMixin, SessionControllerMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.ruleset_manager = RulesetManager()
        self.campaign_clock = CampaignClock()
        self.resize(1400, 840)
        self.path = None
        self.categories = load_categories()
        self.token_color = QColor(self.categories[0]["color"])
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-HALF, -HALF, 2 * HALF, 2 * HALF)
        self.undo = QUndoStack(self)
        self.view = MapView(self.scene, self.undo, self)
        self.setCentralWidget(self.view)
        self.tool_actions = {}
        self.tool_pages = {}
        self.player_win, self.frame, self.mirror = None, None, False
        self.player_grid, self.ready = True, False

        self.scale_pill = QLabel("1 sq = 5 ft")
        self.coord_pill = QLabel("X: 0 ft   Y: 0 ft")
        self.statusBar().addPermanentWidget(self.scale_pill)
        self.statusBar().addPermanentWidget(self.coord_pill)

        self.build_menus()
        self.build_dock()
        self.build_player_dock()
        self.build_token_dock()
        self.build_clock_and_dice_dock()
        self.set_tool("select")

        self.undo.cleanChanged.connect(self.update_title)
        self.update_title()
        self.statusBar().showMessage("Ready")
        self.view.refresh_level()
        self.setup_vision()

    def act(self, menu, text, slot, shortcut=None, checkable=False, checked=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if checkable:
            a.setCheckable(True)
            a.setChecked(checked)
            a.toggled.connect(slot)
        else:
            a.triggered.connect(lambda _=False: slot())
        menu.addAction(a)
        return a

    def add_spin(self, form, label, rng, val, slot, suffix="", step=1):
        sp = QSpinBox()
        sp.setRange(*rng)
        sp.setSingleStep(step)
        if suffix:
            sp.setSuffix(suffix)
        sp.setValue(val)
        sp.valueChanged.connect(slot)
        form.addRow(label, sp)
        return sp

    def build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu("&File")
        self.act(m, "New", self.new_file, QKeySequence.New)
        self.act(m, "Open...", self.open_file, QKeySequence.Open)
        self.act(m, "Generate World / Region...", self.generate_state, "Ctrl+Shift+G")
        self.act(m, "Generate Dungeon...", self.generate_dungeon_map, "Ctrl+Shift+D")
        m.addSeparator()
        self.act(m, "Import Background Map Image...", self.import_underlay, "Ctrl+I")
        self.act(m, "Calibrate Imported Map Grid...", self.calibrate_underlay)
        self.act(m, "Remove Background Map Image", self.remove_underlay)
        m.addSeparator()
        self.act(m, "Save", self.save_file, QKeySequence.Save)
        self.act(m, "Save As...", self.save_as, QKeySequence.SaveAs)
        m.addSeparator()
        self.act(m, "Export Current View as PNG...", self.export_png)
        m.addSeparator()
        self.act(m, "Quit", self.close, QKeySequence.Quit)

        m = mb.addMenu("&Edit")
        u = self.undo.createUndoAction(self, "Undo")
        u.setShortcut(QKeySequence.Undo)
        r = self.undo.createRedoAction(self, "Redo")
        r.setShortcut(QKeySequence.Redo)
        m.addAction(u)
        m.addAction(r)
        m.addSeparator()
        self.act(m, "Delete Selected", self.view.delete_selected, "Del")
        self.act(m, "Select All", self.select_all, QKeySequence.SelectAll)

        m = mb.addMenu("&View")
        self.act(m, "Show Grid", lambda v: self.set_view("show_grid", v), "G", True, True)
        self.act(m, "Snap to Grid", self.set_snap, "S", True, True)

        grid_menu = m.addMenu("Grid Shape")
        grid_grp = QActionGroup(self)
        for label, gtype in (("Square Grid", "square"), ("Hex Grid (Pointy-Top)", "hex_pointy"),
                             ("Hex Grid (Flat-Top)", "hex_flat"), ("Gridless (Freeform)", "none")):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(gtype == "square")
            act.triggered.connect(lambda _=False, gt=gtype: self.set_grid_type(gt))
            grid_grp.addAction(act)
            grid_menu.addAction(act)

        diag_menu = m.addMenu("Diagonal Measurement")
        diag_grp = QActionGroup(self)
        for label, drule in (("Standard / 5e (1-1-1)", "5e"), ("Pathfinder / 3.5e (1-2-1-2)", "pf"),
                             ("True Euclidean", "euclidean")):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(drule == "5e")
            act.triggered.connect(lambda _=False, dr=drule: setattr(Snap, "diag_rule", dr))
            diag_grp.addAction(act)
            diag_menu.addAction(act)

        m.addSeparator()
        self.dark_action = self.act(m, "Dark Canvas", self.set_dark, None, True, True)
        self.night_action = self.act(m, "Night Mode", self.set_night, "N", True, False)
        self.act(m, "Show Grid on Player Screen", self.set_player_grid, None, True, True)
        m.addSeparator()
        self.act(m, "Zoom In", lambda: self.view.zoom(1.25, True), QKeySequence.ZoomIn)
        self.act(m, "Zoom Out", lambda: self.view.zoom(0.8, True), QKeySequence.ZoomOut)
        self.act(m, "Reset Zoom", self.reset_zoom, "Ctrl+0")
        self.act(m, "Go to Origin", lambda: self.view.centerOn(0, 0), "Home")
        self.act(m, "Zoom to Selected Token", self.zoom_to_selected, "Z")
        self.act(m, "Zoom to Party", self.zoom_to_party, "Shift+Z")
        gm = m.addMenu("Go to City or Town")
        gm.aboutToShow.connect(lambda: self.fill_city_menu(gm))

        sm = mb.addMenu("&Settings")
        self.act(sm, "Ruleset Selection...", self.open_ruleset_settings)

        pm = mb.addMenu("&Player")
        self.act(pm, "Open Player Screen", self.open_player_screen, "F10")
        sub = pm.addMenu("Open on Screen")
        sub.aboutToShow.connect(lambda: self.fill_screen_menu(sub))
        self.act(pm, "Close Player Screen", self.close_player_screen)
        pm.addSeparator()
        self.act(pm, "Match Player View to My View", self.match_my_view, "Ctrl+M")
        self.act(pm, "Center Player View on Party", self.center_on_party)
        self.laser_action = self.act(pm, "Laser Pointer (show cursor on player screen)",
                                     self.set_laser, "H", True, False)

        hm = mb.addMenu("&Help")
        self.act(hm, "Controls & Shortcuts", self.show_help_dialog, "F1")

        tb = self.addToolBar("Tools")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        group = QActionGroup(self)

        tool_groups = [
            [("select", "Select", "V"), ("eraser", "Eraser", "E"),
             ("measure", "Ruler", "M"), ("template", "AoE", "A")],
            [("pen", "Pen", "P"), ("line", "Line", "L"), ("rect", "Rect", "R"), ("chalk", "Chalk", "C")],
            [("terrain", "Terrain", "Y"), ("road", "Road", "O"), ("building", "Building", "B"),
             ("fence", "Fence", "F"), ("doorwall", "Door/Wall", "D"), ("prop", "Prop", "K")],
            [("token", "Token", "T"), ("reveal", "Reveal", "X")],
        ]
        for gi, items in enumerate(tool_groups):
            if gi > 0:
                tb.addSeparator()
            for key, label, sc in items:
                a = QAction(make_icon(key), label, self)
                a.setToolTip(f"{label} ({sc})")
                a.setCheckable(True)
                a.setShortcut(sc)
                a.triggered.connect(lambda _=False, k=key: self.set_tool(k))
                group.addAction(a)
                tb.addAction(a)
                self.tool_actions[key] = a

        tb.addSeparator()
        scale_lbl = QLabel(" Scale: ")
        scale_lbl.setStyleSheet("color:#9ca3af; font-weight:bold;")
        tb.addWidget(scale_lbl)
        self.scale_combo = QComboBox()
        self.scale_combo.addItems([f"1 sq = {name}" for name, _ in LEVELS])
        self.scale_combo.activated.connect(self.jump_to_level)
        tb.addWidget(self.scale_combo)
        tb.addSeparator()

        self.night_action.setIcon(make_icon("night"))
        self.night_action.setText("Night")
        self.night_action.setToolTip("Night Mode (N)")
        self.laser_action.setIcon(make_icon("laser"))
        self.laser_action.setText("Laser")
        self.laser_action.setToolTip("Laser Pointer (H)")
        tb.addAction(self.night_action)
        tb.addAction(self.laser_action)


    def show_help_dialog(self):
        QMessageBox.information(
            self,
            "Controls & Shortcuts",
            "<b>Navigation</b><br>"
            "• <b>Mouse Wheel:</b> Zoom in / out<br>"
            "• <b>Middle / Right-Drag or Space + Drag:</b> Pan canvas<br>"
            "• <b>Z / Shift+Z:</b> Zoom to selected token / party<br>"
            "• <b>Home:</b> Return to origin (0, 0)<br><br>"
            "<b>Tactical & Editing Tools</b><br>"
            "• <b>V:</b> Select &nbsp;|&nbsp; <b>E:</b> Eraser &nbsp;|&nbsp; <b>M:</b> Ruler &nbsp;|&nbsp; <b>A:</b> AoE Template<br>"
            "• <b>P / L / R / C:</b> Pen, Line, Rect, Temporary Chalk<br>"
            "• <b>Y / O / B / F / D / K:</b> Terrain, Road, Building, Fence, Door/Wall, Prop<br>"
            "• <b>T:</b> Place Token &nbsp;|&nbsp; <b>X:</b> Manual Fog Reveal<br>"
            "• <b>Right-Click Token:</b> Toggle Status Rings or Edit<br>"
            "• <b>Click / Double-Click Door:</b> Open or Close (updates Line-of-Sight)<br>"
            "• <b>Ctrl+I:</b> Import Background Map Image &nbsp;|&nbsp; <b>G / S / N:</b> Grid, Snap, Night"
        )

    def set_tool(self, key):
        if key in self.tool_actions:
            self.tool_actions[key].setChecked(True)
        if key in self.tool_pages:
            self.tool_stack.setCurrentIndex(self.tool_pages[key])
        self.view.set_tool(key)
        self.view.setFocus()

    def set_view(self, attr, value):
        setattr(self.view, attr, value)
        self.view.viewport().update()

    def set_snap(self, v):
        self.view.snap = v
        Snap.on = v

    def set_grid_type(self, gtype):
        Snap.grid_type = gtype
        self.refresh_views()

    def set_dark(self, v):
        old_default = DARK_PEN if self.view.dark else LIGHT_PEN
        self.view.dark = v
        if self.view.pen_color.name() == QColor(old_default).name():
            self.view.pen_color = QColor(DARK_PEN if v else LIGHT_PEN)
            swatch(self.pen_btn, self.view.pen_color)
        self.view.viewport().update()

    def pick_aoe_color(self):
        c = QColorDialog.getColor(Template.color, self, "Template color")
        if c.isValid():
            Template.color = c
            swatch(self.aoe_btn, c)
            self.refresh_views()

    def clear_ruler_template(self):
        Ruler.active = False
        Template.active = False
        self.refresh_views()

    def rescan_prop_assets(self):
        _ASSET_CACHE.clear()
        cur = self.prop_combo.currentText()
        self.prop_combo.clear()
        self.prop_combo.addItems(list_all_props())
        if cur:
            self.prop_combo.setCurrentText(cur)
        self.statusBar().showMessage("Rescanned assets/props folder.")

    def load_genre_pack(self):
        keys = ["apocalypse", "fantasy", "scifi", "western"]
        gkey = keys[self.pack_combo.currentIndex()]
        self.categories = [dict(c) for c in GENRE_CATEGORIES[gkey]]
        save_categories(self.categories)
        self.refresh_categories(0)
        self.apply_preset(self.presets.item(0))
        self.statusBar().showMessage(f"Loaded {self.pack_combo.currentText()} token categories.")

    def toggle_token_status(self, tok, status_name, checked):
        old = tok.props()
        new = dict(old)
        st = list(new.get("statuses", []))
        if checked and status_name not in st:
            st.append(status_name)
        elif not checked and status_name in st:
            st.remove(status_name)
        new["statuses"] = st
        self.undo.push(EditTokenCommand(tok, old, new))

    # ---- Underlay map image import & calibration
    def import_underlay(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Background Map Image", str(MAPS_DIR),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, "Import Failed", "Could not load that image file.")
            return
        self.remove_underlay()
        w_units = (pm.width() / 70.0) * CELL
        h_units = (pm.height() / 70.0) * CELL
        it = UnderlayItem(path, w_units, h_units, 1.0)
        it.setPos(0, 0)
        self.scene.addItem(it)
        self.view.fitInView(QRectF(0, 0, w_units, h_units), Qt.KeepAspectRatio)
        self.view.refresh_level()
        self.statusBar().showMessage("Imported map image. Use File > Calibrate Imported Map Grid to match squares.")

    def calibrate_underlay(self):
        underlays = [it for it in self.scene.items() if isinstance(it, UnderlayItem)]
        if not underlays:
            self.statusBar().showMessage("Import a background map image first (File > Import Background Map Image).")
            return
        self.view._calibrating_underlay = underlays[0]
        self.view.viewport().setCursor(Qt.CrossCursor)
        self.statusBar().showMessage("CALIBRATE GRID: Click and drag a square over ONE grid cell on the image.")

    def remove_underlay(self):
        for it in [i for i in self.scene.items() if isinstance(i, UnderlayItem)]:
            self.scene.removeItem(it)

    # ---- player screen, fog of war and day/night

    def set_laser(self, v):
        Pointer.laser = v
        if not v:
            Pointer.dm = None
        self.update_player_pointer()

    def update_player_pointer(self):
        if self.player_win is not None:
            self.player_win.view.viewport().update()

    def pick_chalk_color(self):
        c = QColorDialog.getColor(Chalk.color, self, "Whiteboard color")
        if c.isValid():
            Chalk.color = c
            swatch(self.chalk_btn, c)

    def chalk_undo(self):
        if Chalk.strokes:
            Chalk.strokes.pop()
            self.refresh_views()

    def chalk_clear(self):
        Chalk.strokes.clear()
        Chalk.cur = None
        self.refresh_views()

    def set_fog_darkness(self, v):
        Vision.fog_alpha = round(255 * v / 100)
        self.fog_label.setText(f"Player fog darkness: {v}%")
        self.refresh_views()

    def set_min_token(self, *_):
        Tokens.min_dm, Tokens.min_tv = self.min_dm_spin.value(), self.min_tv_spin.value()
        self.refresh_token_geometry()
        self.refresh_views()

    def refresh_token_geometry(self):
        for it in self.scene.items():
            if isinstance(it, TokenItem):
                it.refresh_geometry()

    def player_navigated(self):
        if self.player_win is None or getattr(self, "_syncing", False):
            return
        view = self.player_win.view
        self._syncing = True
        try:
            rect = view.mapToScene(view.viewport().rect()).boundingRect()
            self.ensure_frame()
            self.frame.set_view_rect(rect)
            name = LEVELS[level_for_zoom(view.transform().m11())][0]
            self.frame_label.setText(f"Players see {fmt_len(rect.width())} x {fmt_len(rect.height())} "
                                     f"(1 sq = {name}).")
        finally:
            self._syncing = False
        self.schedule_detail()
        if self.mirror:
            self.mirror_chk.setChecked(False)

    def on_dm_view_changed(self):
        if self.ready:
            if self.mirror:
                self.sync_player_view()
            self.schedule_detail()

    def on_zoom_changed(self):
        if self.ready:
            if self.frame is not None:
                self.frame.refresh()
            self.refresh_token_geometry()
            self.on_dm_view_changed()

    def update_scale_ui(self, level):
        self.scale_combo.blockSignals(True)
        self.scale_combo.setCurrentIndex(level)
        self.scale_combo.blockSignals(False)

    def jump_to_level(self, index):
        self.view.set_zoom(JUMP_PX / (LEVELS[index][1] * UNITS_PER_FT))
        self.view.setFocus()

    def reset_zoom(self):
        c = self.view.mapToScene(self.view.viewport().rect().center())
        self.view.resetTransform()
        self.view.centerOn(c)
        self.view.refresh_level()

    def select_all(self):
        for it in self.scene.items():
            if not isinstance(it, UnderlayItem):
                it.setSelected(True)

    def pick_pen_color(self):
        c = QColorDialog.getColor(self.view.pen_color, self, "Pen color")
        if c.isValid():
            self.view.pen_color = c
            swatch(self.pen_btn, c)

    # --- tokens
    def pick_token_color(self):
        c = QColorDialog.getColor(self.token_color, self, "Token color")
        if c.isValid():
            self.token_color = c
            swatch(self.tok_btn, c)

    def apply_preset(self, item):
        if item is None:
            return
        cat = self.categories[self.presets.row(item)]
        self.name_edit.setText(cat["name"])
        self.ini_edit.setText(cat.get("initials", ""))
        self.token_color = QColor(cat["color"])
        swatch(self.tok_btn, cat["color"])
        self.size_spin.setValue(cat["size"])
        self.player_chk.setChecked(cat.get("player", False))
        self.number_chk.setChecked(cat.get("numbered", False))

    def refresh_categories(self, select=None):
        self.presets.clear()
        for cat in self.categories:
            pm = QPixmap(14, 14)
            pm.fill(QColor(cat["color"]))
            label = cat["name"] + ("  (player)" if cat.get("player") else "")
            self.presets.addItem(QListWidgetItem(QIcon(pm), label))
        if select is not None and 0 <= select < len(self.categories):
            self.presets.setCurrentRow(select)

    def current_category(self):
        return {"name": self.name_edit.text().strip() or "Token", "initials": self.ini_edit.text().strip(),
                "color": self.token_color.name(), "size": self.size_spin.value(),
                "player": self.player_chk.isChecked(), "numbered": self.number_chk.isChecked()}

    def new_category(self):
        dlg = CategoryDialog(self, self.current_category())
        if dlg.exec() == QDialog.Accepted:
            self.categories.append(dlg.result_cat())
            save_categories(self.categories)
            self.refresh_categories(len(self.categories) - 1)

    def edit_category(self):
        row = self.presets.currentRow()
        if row < 0:
            self.statusBar().showMessage("Pick a category in the list first.")
            return
        dlg = CategoryDialog(self, self.categories[row])
        if dlg.exec() == QDialog.Accepted:
            self.categories[row] = dlg.result_cat()
            save_categories(self.categories)
            self.refresh_categories(row)

    def delete_category(self):
        row = self.presets.currentRow()
        if row < 0:
            self.statusBar().showMessage("Pick a category in the list first.")
            return
        name = self.categories[row]["name"]
        if QMessageBox.question(self, "Delete category", f"Delete the category \"{name}\"?") == QMessageBox.Yes:
            del self.categories[row]
            save_categories(self.categories)
            self.refresh_categories()

    def next_number(self, base):
        rx = re.compile(r"^" + re.escape(base) + r"\s+(\d+)$")
        nums = []
        for t in self.scene.items():
            if isinstance(t, TokenItem):
                m = rx.match(t.name)
                if m:
                    nums.append(int(m.group(1)))
        return max(nums, default=0) + 1

    def make_tokens(self, sp):
        count, size = self.count_spin.value(), self.size_spin.value()
        size_units = size * CELL
        numbered = self.number_chk.isChecked()
        base = self.name_edit.text().strip()
        first = 1
        if numbered:
            base = re.sub(r"\s*\d+\s*$", "", base) or "Token"
            first = self.next_number(base)
        ini = self.ini_edit.text().strip()
        snap = self.view.snap and Snap.grid_type != "none"
        pitch = max(size_units, Snap.step) if snap else size_units * 1.1
        if snap and Snap.grid_type == "square":
            ox = math.floor(sp.x() / Snap.step) * Snap.step
            oy = math.floor(sp.y() / Snap.step) * Snap.step
        elif snap:
            snapped = snap_point_to_grid(sp)
            ox, oy = snapped.x() - size_units / 2, snapped.y() - size_units / 2
        else:
            ox, oy = sp.x() - size_units / 2, sp.y() - size_units / 2
        occupied = {(round(t.pos().x()), round(t.pos().y())) for t in self.scene.items()
                    if isinstance(t, TokenItem)}
        offsets = []
        if count > 1 and self.arrange_combo.currentText() == "Scatter":
            r = self.spread_spin.value()
            offsets = [(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if dx * dx + dy * dy <= r * r]
            random.shuffle(offsets)
        offsets += spiral_offsets(count * 4 + 25)
        spots, used = [], set()
        for dx, dy in offsets:
            if (dx, dy) in used:
                continue
            used.add((dx, dy))
            x, y = ox + dx * pitch, oy + dy * pitch
            if count > 1 and (round(x), round(y)) in occupied:
                continue
            spots.append((x, y))
            if len(spots) == count:
                break
        toks = []
        for i, (x, y) in enumerate(spots):
            name = f"{base} {first + i}" if numbered else base
            tok = TokenItem(name, ini or auto_initials(name), self.token_color, size, self.player_chk.isChecked())
            tok.setPos(x, y)
            toks.append(tok)
        return toks

    # ---- token list and zooming to tokens

    def zoom_to_selected(self):
        toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem)]
        if toks:
            self.view.focus_items(toks)
        else:
            self.statusBar().showMessage("Select a token first, or double-click one in the Tokens tab.")

    def zoom_to_party(self):
        toks = [it for it in self.scene.items() if isinstance(it, TokenItem) and it.player]
        if toks:
            self.view.focus_items(toks)
        else:
            self.statusBar().showMessage("No player tokens on the map yet.")

    def show_selected_to_players(self):
        toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem)]
        if not toks:
            self.statusBar().showMessage("Select a token first.")
            return
        self.center_player_on_tokens(toks)

    def edit_selected(self):
        sel = [it for it in self.scene.selectedItems() if isinstance(it, (TokenItem, BuildingItem))]
        if not sel:
            self.statusBar().showMessage("Select a token or building to edit.")
            return
        it = sel[0]
        (self.edit_token if isinstance(it, TokenItem) else self.edit_building)(it)

    def edit_building(self, b):
        dlg = BuildingDialog(self, b.props())
        if dlg.exec() == QDialog.Accepted:
            new = dlg.result_props()
            if new != b.props():
                self.undo.push(EditTokenCommand(b, b.props(), new))

    def edit_token(self, tok):
        dlg = TokenDialog(self, tok.props())
        if dlg.exec() == QDialog.Accepted:
            new = dlg.result_props()
            if new != tok.props():
                self.undo.push(EditTokenCommand(tok, tok.props(), new))
                self.update_token_perk_preview(tok)

    def open_ruleset_settings(self):
        dlg = RulesetSettingsDialog(self.ruleset_manager, self)
        if dlg.exec() == QDialog.Accepted:
            selected_sys = dlg.system_combo.currentText()
            self.ruleset_manager.set_active_ruleset(selected_sys)
            self.statusBar().showMessage(f"Active Ruleset set to: {selected_sys}")
            sel_toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem)]
            if sel_toks:
                self.update_token_perk_preview(sel_toks[0])

    # --- files
    def update_title(self, *_):
        name = Path(self.path).name if self.path else "Untitled"
        self.setWindowTitle(f"{name}{'' if self.undo.isClean() else ' *'} - InfinityGrid Tabletop")

    def confirm_discard(self):
        if self.undo.isClean():
            return True
        r = QMessageBox.question(self, "Unsaved changes", "Save changes to this map first?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_file()
        return r == QMessageBox.Discard

    def closeEvent(self, e):
        if not self.confirm_discard():
            e.ignore()
            return
        if self.player_win is not None:
            self.player_win.close()
        e.accept()

    def reset_scene(self):
        self.undo.clear()
        self.view._press_pos = {}
        self.scene.clear()
        self.frame = None
        reset_explored()
        Chalk.strokes.clear()
        Ruler.active = False
        Template.active = False
        Atlas.current = None
        if hasattr(self, "campaign_clock"):
            self.campaign_clock.day = 1
            self.campaign_clock.block_index = 4
            if hasattr(self, "clock_display"):
                self.refresh_campaign_clock_ui(sync_night=False)

    def new_file(self):
        if self.confirm_discard():
            self.reset_scene()
            self.path = None
            self.undo.setClean()
            self.update_title()

    def open_file(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open map", str(MAPS_DIR), "Battle maps (*.json)")
        if path:
            self.load_from(path)

    def load_from(self, path):
        try:
            with open(path) as f:
                data = json.load(f)
            prev, Snap.on = Snap.on, False
            try:
                items = [item_from_dict(d) for d in data["items"]]
            finally:
                Snap.on = prev
        except Exception as ex:
            QMessageBox.warning(self, "Could not open", str(ex))
            return
        self.reset_scene()
        for it in items:
            self.scene.addItem(it)
        self.dark_action.setChecked(data.get("dark", True))
        self.set_grid_type(data.get("grid_type", "square"))
        Snap.diag_rule = data.get("diag_rule", "5e")
        self.view.resetTransform()
        z = data.get("zoom", 1.0)
        self.view.scale(z, z)
        self.view.centerOn(*data.get("center", [0, 0]))
        self.view.refresh_level()
        self.apply_vision_settings(data)
        if "campaign_clock" in data and hasattr(self, "campaign_clock"):
            self.campaign_clock.from_dict(data["campaign_clock"])
            if hasattr(self, "clock_auto_night_chk"):
                self.clock_auto_night_chk.blockSignals(True)
                self.clock_auto_night_chk.setChecked(self.campaign_clock.auto_night)
                self.clock_auto_night_chk.blockSignals(False)
            self.refresh_campaign_clock_ui(sync_night=False)
        self.path = path
        self.undo.setClean()
        self.update_title()

    def save_file(self):
        return self.save_to(self.path) if self.path else self.save_as()

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save map", str(MAPS_DIR / "map.json"), "Battle maps (*.json)")
        if not path:
            return False
        if not path.endswith(".json"):
            path += ".json"
        return self.save_to(path)

    def save_to(self, path):
        c = self.view.mapToScene(self.view.viewport().rect().center())
        data = {"app": "infinity-grid-tabletop", "version": 2, "dark": self.view.dark,
                "grid_type": Snap.grid_type, "diag_rule": Snap.diag_rule,
                "center": [c.x(), c.y()], "zoom": self.view.transform().m11(),
                "items": [it.to_dict() for it in self.scene.items(Qt.AscendingOrder)
                          if hasattr(it, "to_dict")],
                "night": Vision.night, "day_ft": Vision.day_ft, "night_ft": Vision.night_ft,
                "fog_on": Vision.fog_on, "remember": Vision.remember, "fog_alpha": Vision.fog_alpha,
                "min_token_px": [Tokens.min_dm, Tokens.min_tv],
                "explored": [[round(v, 1) for pt in poly for v in pt] for poly in Vision.explored_polys],
                "player_frame": ([self.frame.pos().x(), self.frame.pos().y(), self.frame.rect().width(),
                                  self.frame.rect().height()] if self.frame is not None else None),
                "campaign_clock": self.campaign_clock.to_dict(),
                "world": Atlas.current.to_dict() if Atlas.current is not None else None}
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except OSError as ex:
            QMessageBox.warning(self, "Could not save", str(ex))
            return False
        self.path = path
        self.undo.setClean()
        self.update_title()
        return True

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "map.png", "PNG image (*.png)")
        if path:
            self.scene.clearSelection()
            self.view.viewport().grab().save(path)




def main():
    MAPS_DIR.mkdir(exist_ok=True)
    ensure_assets()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    app.setApplicationName("InfinityGrid Tabletop")
    w = MainWindow()
    w.show()
    w.view.centerOn(0, 0)
    if len(sys.argv) > 1:
        w.load_from(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

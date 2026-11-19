import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget,
)
from core.config import (
    ROAD_STYLES, BUILDING_KINDS, FENCE_STYLES, TERRAIN,
    Tokens, swatch,
)
from core.clock_dice import roll_dice_expression
from map_canvas.canvas_items import TokenItem
from map_canvas.vision import Vision
from map_canvas.world_assets import list_all_props
from map_canvas.overlays import Template, Chalk


class DockPanelsMixin:
    """Left Tool Options dock and Right Player/Vision, Tokens, and Clock & Dice docks."""

    def build_dock(self):
        dock = QDockWidget("Tool Options", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(265)
        self.tool_stack = QStackedWidget()

        def register_page(keys, widget):
            idx = self.tool_stack.addWidget(widget)
            for k in keys:
                self.tool_pages[k] = idx

        # 1. Select page
        w_sel = QWidget()
        lay = QVBoxLayout(w_sel)
        gb = QGroupBox("Selection")
        gl = QVBoxLayout(gb)
        info = QLabel("Click or drag a box to select items.\nDouble-click a token, building, or door to edit/toggle it.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#9ca3af;")
        gl.addWidget(info)
        for text, slot in (("Edit Selected...", self.edit_selected),
                           ("Delete Selected (Del)", self.view.delete_selected)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, sl=slot: sl())
            gl.addWidget(b)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["select"], w_sel)

        # 2. Eraser page
        w_ers = QWidget()
        lay = QVBoxLayout(w_ers)
        gb = QGroupBox("Eraser")
        gl = QFormLayout(gb)
        self.erase_combo = QComboBox()
        self.erase_combo.addItems(["All map items", "Drawings & reveals only"])
        self.erase_combo.currentIndexChanged.connect(
            lambda i: setattr(self.view, "erase_filter", "drawings" if i == 1 else "all")
        )
        gl.addRow("Target", self.erase_combo)
        note = QLabel("Click or drag across items to remove them. Tokens and underlay maps are protected.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9ca3af;")
        gl.addRow(note)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["eraser"], w_ers)

        # 3. Ruler & AoE Template page
        w_aoe = QWidget()
        lay = QVBoxLayout(w_aoe)
        gb = QGroupBox("Measurement & AoE Templates")
        f = QFormLayout(gb)
        self.aoe_shape = QComboBox()
        self.aoe_shape.addItems(["Circle", "Cone", "Line", "Cube"])
        self.aoe_shape.currentTextChanged.connect(lambda v: setattr(Template, "shape", v))
        f.addRow("AoE Shape", self.aoe_shape)
        self.aoe_size = self.add_spin(f, "Default size", (5, 500), Template.size_ft,
                                      lambda v: setattr(Template, "size_ft", v), " ft", 5)
        self.aoe_btn = QPushButton()
        swatch(self.aoe_btn, Template.color)
        self.aoe_btn.clicked.connect(self.pick_aoe_color)
        f.addRow("Color", self.aoe_btn)
        b_clr = QPushButton("Clear Active Template / Ruler")
        b_clr.clicked.connect(self.clear_ruler_template)
        f.addRow(b_clr)
        note = QLabel("Ruler (M) and AoE (A) display live on both DM and Player screens without cluttering the map.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9ca3af;")
        f.addRow(note)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["measure", "template"], w_aoe)

        # 4. Pen / Line / Rect page
        w_pen = QWidget()
        lay = QVBoxLayout(w_pen)
        gb = QGroupBox("Vector Drawing")
        f = QFormLayout(gb)
        self.pen_btn = QPushButton()
        swatch(self.pen_btn, self.view.pen_color)
        self.pen_btn.clicked.connect(self.pick_pen_color)
        f.addRow("Color", self.pen_btn)
        self.width_spin = self.add_spin(f, "Width", (1, 60), self.view.pen_width,
                                        lambda v: setattr(self.view, "pen_width", v), " px")
        fill = QCheckBox("Fill rectangles")
        fill.toggled.connect(lambda v: setattr(self.view, "fill", v))
        f.addRow(fill)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["pen", "line", "rect"], w_pen)

        # 5. Chalk / Whiteboard page
        w_chk = QWidget()
        lay = QVBoxLayout(w_chk)
        gb = QGroupBox("Temporary Whiteboard")
        f = QFormLayout(gb)
        self.chalk_mode = QComboBox()
        self.chalk_mode.addItems(["Pen", "Highlighter", "Circle", "Arrow", "Erase"])
        self.chalk_mode.currentTextChanged.connect(lambda v: setattr(Chalk, "mode", v))
        self.chalk_btn = QPushButton()
        swatch(self.chalk_btn, Chalk.color)
        self.chalk_btn.clicked.connect(self.pick_chalk_color)
        f.addRow("Mark", self.chalk_mode)
        f.addRow("Color", self.chalk_btn)
        self.chalk_width = self.add_spin(f, "Width", (1, 30), Chalk.width,
                                         lambda v: setattr(Chalk, "width", v), " px")
        row = QHBoxLayout()
        for text, slot in (("Undo Mark", self.chalk_undo), ("Clear All", self.chalk_clear)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, sl=slot: sl())
            row.addWidget(b)
        f.addRow(row)
        note = QLabel("Whiteboard marks appear on both screens and are never saved with the map.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9ca3af;")
        f.addRow(note)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["chalk"], w_chk)

        # 6. Road / Building / Fence / DoorWall page
        w_env = QWidget()
        lay = QVBoxLayout(w_env)
        gb = QGroupBox("Structures, Walls & Roads")
        f = QFormLayout(gb)
        self.road_combo = QComboBox()
        self.road_combo.addItems(list(ROAD_STYLES))
        self.road_combo.currentTextChanged.connect(lambda v: setattr(self.view, "road_style", v))
        f.addRow("Road style", self.road_combo)
        self.road_mode_combo = QComboBox()
        self.road_mode_combo.addItems(["Curved", "Straight"])
        self.road_mode_combo.currentTextChanged.connect(lambda v: setattr(self.view, "road_mode", v))
        f.addRow("Road shape", self.road_mode_combo)
        self.road_width = self.add_spin(f, "Road width", (5, 200), self.view.road_width,
                                        lambda v: setattr(self.view, "road_width", v), " ft", 5)
        self.bld_combo = QComboBox()
        self.bld_combo.addItems(list(BUILDING_KINDS))
        self.bld_combo.currentTextChanged.connect(lambda v: setattr(self.view, "building_kind", v))
        f.addRow("Building type", self.bld_combo)
        self.bld_mode_combo = QComboBox()
        self.bld_mode_combo.addItems(["Standard size (click to place)", "Custom size (drag rectangle)"])
        self.bld_mode_combo.currentIndexChanged.connect(
            lambda i: setattr(self.view, "building_mode", "Standard" if i == 0 else "Drag")
        )
        f.addRow("Building size", self.bld_mode_combo)
        self.fence_combo = QComboBox()
        self.fence_combo.addItems(list(FENCE_STYLES))
        self.fence_combo.currentTextChanged.connect(lambda v: setattr(self.view, "fence_style", v))
        f.addRow("Fence style", self.fence_combo)
        self.dw_combo = QComboBox()
        self.dw_combo.addItems([
            "Door (Closed = blocks sight, Open = clear)",
            "Window (Allows sight through glass)",
            "Vision Wall (Always blocks sight)"
        ])
        self.dw_combo.currentIndexChanged.connect(
            lambda i: setattr(self.view, "doorwall_kind", ("door", "window", "wall")[i])
        )
        f.addRow("Opening / Wall", self.dw_combo)
        note = QLabel("Click or right-click any door or window to toggle Open/Closed. Windows always allow line-of-sight.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#9ca3af;")
        f.addRow(note)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["road", "building", "fence", "doorwall"], w_env)

        # 7. Terrain & Reveal page
        w_ter = QWidget()
        lay = QVBoxLayout(w_ter)
        gb = QGroupBox("Terrain & Manual Reveal")
        f = QFormLayout(gb)
        self.terrain_combo = QComboBox()
        for name, color in TERRAIN.items():
            pm = QPixmap(14, 14)
            pm.fill(QColor(color))
            self.terrain_combo.addItem(QIcon(pm), name)
        self.terrain_combo.currentTextChanged.connect(lambda v: setattr(self.view, "terrain_type", v))
        self.terrain_shape = QComboBox()
        self.terrain_shape.addItems(["Brush", "Rectangle"])
        self.terrain_shape.currentTextChanged.connect(lambda v: setattr(self.view, "terrain_mode", v))
        f.addRow("Terrain", self.terrain_combo)
        f.addRow("Shape", self.terrain_shape)
        self.terrain_size = self.add_spin(f, "Brush size", (1, 80), self.view.terrain_brush,
                                          lambda v: setattr(self.view, "terrain_brush", v), " squares")
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["terrain", "reveal"], w_ter)

        # 8. Prop page
        w_prp = QWidget()
        lay = QVBoxLayout(w_prp)
        gb = QGroupBox("Map Props")
        f = QFormLayout(gb)
        self.prop_combo = QComboBox()
        self.prop_combo.addItems(list_all_props())
        self.prop_combo.currentTextChanged.connect(lambda v: setattr(self.view, "prop_kind", v))
        f.addRow("Prop", self.prop_combo)
        self.prop_rot_spin = self.add_spin(f, "Rotation", (0, 359), 0,
                                           lambda v: setattr(self.view, "prop_rot", v), " deg", 15)
        self.prop_rot_spin.setWrapping(True)
        rot_btn = QPushButton("Rotate +90°")
        rot_btn.clicked.connect(lambda: self.prop_rot_spin.setValue((self.prop_rot_spin.value() + 90) % 360))
        f.addRow("", rot_btn)
        b_rescan = QPushButton("Rescan assets/props Folder")
        b_rescan.clicked.connect(self.rescan_prop_assets)
        f.addRow("", b_rescan)
        lay.addWidget(gb)
        lay.addStretch()
        register_page(["prop"], w_prp)

        # 9. Token placement page
        w_tok = QWidget()
        lay = QVBoxLayout(w_tok)
        gb_cat = QGroupBox("Categories & Genre Packs")
        cl = QVBoxLayout(gb_cat)

        pack_row = QHBoxLayout()
        self.pack_combo = QComboBox()
        self.pack_combo.addItems(["Modern / Apocalypse", "High Fantasy", "Sci-Fi / Cyberpunk", "Western / Frontier"])
        b_load_pack = QPushButton("Load Pack")
        b_load_pack.clicked.connect(self.load_genre_pack)
        pack_row.addWidget(self.pack_combo, 1)
        pack_row.addWidget(b_load_pack)
        cl.addLayout(pack_row)

        self.presets = QListWidget()
        self.presets.setMaximumHeight(165)
        self.refresh_categories()
        self.presets.itemClicked.connect(self.apply_preset)
        cl.addWidget(self.presets)
        row = QHBoxLayout()
        for text, slot in (("Save...", self.new_category), ("Edit...", self.edit_category),
                           ("Delete", self.delete_category)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, sl=slot: sl())
            row.addWidget(b)
        cl.addLayout(row)
        lay.addWidget(gb_cat)

        gb_cfg = QGroupBox("Token Properties")
        f = QFormLayout(gb_cfg)
        self.name_edit = QLineEdit(self.categories[0]["name"])
        self.ini_edit = QLineEdit()
        self.ini_edit.setPlaceholderText("auto")
        self.ini_edit.setFixedWidth(52)
        name_row = QHBoxLayout()
        name_row.addWidget(self.name_edit)
        name_row.addWidget(self.ini_edit)
        f.addRow("Name / Ini", name_row)

        self.tok_btn = QPushButton()
        swatch(self.tok_btn, self.token_color)
        self.tok_btn.clicked.connect(self.pick_token_color)
        f.addRow("Color", self.tok_btn)

        self.size_spin = self.add_spin(f, "Size", (1, 8), 1, lambda _v: None, " sq")
        self.player_chk = QCheckBox("Player token (shares vision)")
        self.player_chk.setChecked(True)
        f.addRow(self.player_chk)
        self.number_chk = QCheckBox("Auto-number (1, 2, 3...)")
        f.addRow(self.number_chk)

        self.count_spin = self.add_spin(f, "Place", (1, 100), 1, self.on_count_changed, " per click")
        self.arrange_lbl = QLabel("Arrange")
        self.arrange_combo = QComboBox()
        self.arrange_combo.addItems(["Cluster", "Scatter"])
        f.addRow(self.arrange_lbl, self.arrange_combo)
        self.spread_lbl = QLabel("Radius")
        self.spread_spin = QSpinBox()
        self.spread_spin.setRange(1, 30)
        self.spread_spin.setValue(4)
        self.spread_spin.setSuffix(" sq")
        f.addRow(self.spread_lbl, self.spread_spin)
        self.on_count_changed(1)

        lay.addWidget(gb_cfg)
        lay.addStretch()
        register_page(["token"], w_tok)

        dock.setWidget(self.tool_stack)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def on_count_changed(self, v):
        multi = v > 1
        for w in (self.arrange_lbl, self.arrange_combo, self.spread_lbl, self.spread_spin):
            w.setVisible(multi)


    def build_player_dock(self):
        dock = QDockWidget("Player & Vision", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumWidth(275)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        w = QWidget()
        lay = QVBoxLayout(w)

        gb_scr = QGroupBox("Player Screen (TV)")
        sl = QVBoxLayout(gb_scr)
        row = QHBoxLayout()
        b_open = QPushButton("Open (F10)")
        b_open.clicked.connect(lambda: self.open_player_screen())
        b_close = QPushButton("Close")
        b_close.clicked.connect(lambda: self.close_player_screen())
        row.addWidget(b_open)
        row.addWidget(b_close)
        sl.addLayout(row)

        self.mirror_chk = QCheckBox("Mirror my view (follow pan/zoom)")
        self.mirror_chk.toggled.connect(self.set_mirror)
        sl.addWidget(self.mirror_chk)
        self.frame_chk = QCheckBox("Show cyan player frame on map")
        self.frame_chk.setChecked(True)
        self.frame_chk.toggled.connect(lambda _v: self.update_frame_visibility())
        sl.addWidget(self.frame_chk)

        for text, slot in [("Match my current view", self.match_my_view),
                           ("Center on party", self.center_on_party)]:
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, sl=slot: sl())
            sl.addWidget(b)

        zrow = QHBoxLayout()
        for text, f in (("Zoom In", 0.8), ("Zoom Out", 1.25)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, fac=f: self.zoom_frame(fac))
            zrow.addWidget(b)
        sl.addLayout(zrow)

        self.frame_label = QLabel("Drag the cyan frame border to pan the player view.")
        self.frame_label.setWordWrap(True)
        self.frame_label.setStyleSheet("color:#9ca3af; font-size:11px;")
        sl.addWidget(self.frame_label)
        lay.addWidget(gb_scr)

        gb_vis = QGroupBox("Line-of-Sight & Fog of War")
        vl = QVBoxLayout(gb_vis)
        f = QFormLayout()
        self.day_spin = self.add_spin(f, "Day vision", (10, 5000), Vision.day_ft, self.set_ranges, " ft", 10)
        self.night_spin = self.add_spin(f, "Night vision", (10, 5000), Vision.night_ft, self.set_ranges, " ft", 10)
        vl.addLayout(f)

        self.fog_chk = QCheckBox("Enable fog of war on player screen")
        self.fog_chk.setChecked(Vision.fog_on)
        self.fog_chk.toggled.connect(lambda v: self.set_vision_flag("fog_on", v))
        self.fog_dm_chk = QCheckBox("Preview fog on DM screen")
        self.fog_dm_chk.setChecked(Vision.show_on_dm)
        self.fog_dm_chk.toggled.connect(lambda v: self.set_vision_flag("show_on_dm", v))
        self.remember_chk = QCheckBox("Remember explored areas (dimmed)")
        self.remember_chk.setChecked(Vision.remember)
        self.remember_chk.toggled.connect(lambda v: self.set_vision_flag("remember", v))
        for c in (self.fog_chk, self.fog_dm_chk, self.remember_chk):
            vl.addWidget(c)

        self.fog_label = QLabel("Player fog darkness: 55%")
        vl.addWidget(self.fog_label)
        self.fog_slider = QSlider(Qt.Horizontal)
        self.fog_slider.setRange(0, 100)
        self.fog_slider.setValue(55)
        self.fog_slider.valueChanged.connect(self.set_fog_darkness)
        vl.addWidget(self.fog_slider)

        b_rst = QPushButton("Reset Explored Areas")
        b_rst.clicked.connect(self.reset_explored_ui)
        vl.addWidget(b_rst)
        lay.addWidget(gb_vis)

        gb_sel = QGroupBox("Selected Player Token")
        pl = QFormLayout(gb_sel)
        self.mod_spin = self.add_spin(pl, "Vision bonus", (-1000, 5000), 0, self.on_mod_changed, " ft", 10)
        self.mod_spin.setEnabled(False)
        self.range_label = QLabel("")
        self.range_label.setWordWrap(True)
        self.range_label.setStyleSheet("color:#9ca3af; font-size:11px;")
        pl.addRow(self.range_label)
        lay.addWidget(gb_sel)

        gb_sz = QGroupBox("Zoomed-Out Token Size")
        szl = QFormLayout(gb_sz)
        self.min_dm_spin = self.add_spin(szl, "DM min size", (8, 200), Tokens.min_dm, self.set_min_token, " px")
        self.min_tv_spin = self.add_spin(szl, "Player min size", (8, 200), Tokens.min_tv, self.set_min_token, " px")
        lay.addWidget(gb_sz)

        lay.addStretch()
        scroll.setWidget(w)
        dock.setWidget(scroll)
        self.player_dock = dock
        self.addDockWidget(Qt.RightDockWidgetArea, dock)


    def build_token_dock(self):
        dock = QDockWidget("Tokens", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        w = QWidget()
        lay = QVBoxLayout(w)
        hint = QLabel("Click to select, double-click to focus. ★ = party vision.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        lay.addWidget(hint)
        self.token_list = QListWidget()
        self.token_list.itemClicked.connect(self.select_listed_token)
        self.token_list.itemDoubleClicked.connect(self.zoom_listed_token)
        lay.addWidget(self.token_list)

        self.profile_info_label = QLabel("Select a token to view ruleset profile & perk.")
        self.profile_info_label.setWordWrap(True)
        self.profile_info_label.setStyleSheet("color:#93c5fd; background:#14171f; border:1px solid #323848; border-radius:5px; padding:6px; font-size:11px;")
        lay.addWidget(self.profile_info_label)

        for text, slot in [("Zoom to Selected (Z)", self.zoom_to_selected),
                           ("Zoom to Party (Shift+Z)", self.zoom_to_party),
                           ("Frame Selected on TV", self.show_selected_to_players)]:
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, sl=slot: sl())
            lay.addWidget(b)
        dock.setWidget(w)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self.player_dock, dock)
        self.player_dock.raise_()

    def build_clock_and_dice_dock(self):
        dock = QDockWidget("Clock & Dice", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        w = QWidget()
        lay = QVBoxLayout(w)

        # ---- 2-Hour Activity Block Clock (Contagion)
        gb_clk = QGroupBox("2-Hour Activity Block Clock")
        cl = QVBoxLayout(gb_clk)

        self.clock_display = QLabel()
        self.clock_display.setWordWrap(True)
        self.clock_display.setStyleSheet(
            "background:#14171f; border:1px solid #323848; border-radius:6px; "
            "padding:8px; font-size:12px; color:#f3f4f6;"
        )
        cl.addWidget(self.clock_display)

        btn_row = QHBoxLayout()
        b_prev = QPushButton("-2h")
        b_prev.setToolTip("Rewind 1 Activity Block (2 hours)")
        b_prev.clicked.connect(lambda: self.step_campaign_clock(-1))
        b_next = QPushButton("+1 Block (2h)")
        b_next.setToolTip("Advance 1 Major Activity Block (2 hours)")
        b_next.setStyleSheet("background-color:#1d4ed8; border-color:#3b82f6; font-weight:bold;")
        b_next.clicked.connect(lambda: self.step_campaign_clock(1))
        b_rst = QPushButton("Reset")
        b_rst.setToolTip("Reset to Day 1, 08:00 Morning")
        b_rst.clicked.connect(self.reset_campaign_clock)
        btn_row.addWidget(b_prev)
        btn_row.addWidget(b_next, 2)
        btn_row.addWidget(b_rst)
        cl.addLayout(btn_row)

        self.clock_auto_night_chk = QCheckBox("Auto-toggle Night Mode (20:00 – 06:00)")
        self.clock_auto_night_chk.setChecked(self.campaign_clock.auto_night)
        self.clock_auto_night_chk.toggled.connect(self.on_clock_auto_night_toggled)
        cl.addWidget(self.clock_auto_night_chk)
        lay.addWidget(gb_clk)

        # ---- Built-in Dice Roller & Macro Bar
        gb_dice = QGroupBox("Dice Roller & Token Macros")
        dl = QVBoxLayout(gb_dice)

        # Quick polyhedral dice buttons
        d_row1 = QHBoxLayout()
        for die in ("d4", "d6", "d8", "d10"):
            b = QPushButton(die)
            b.clicked.connect(lambda _=False, d=f"1{die}": self.execute_dice_roll(d))
            d_row1.addWidget(b)
        dl.addLayout(d_row1)

        d_row2 = QHBoxLayout()
        for die in ("d12", "d20", "d100", "2d6"):
            b = QPushButton(die)
            expr = f"1{die}" if die.startswith("d") else die
            b.clicked.connect(lambda _=False, d=expr: self.execute_dice_roll(d))
            d_row2.addWidget(b)
        dl.addLayout(d_row2)

        # Advantage / Disadvantage selector for d20
        adv_row = QHBoxLayout()
        adv_row.addWidget(QLabel("d20 Mode:"))
        self.dice_adv_combo = QComboBox()
        self.dice_adv_combo.addItems(["Normal", "Advantage (2d20H)", "Disadvantage (2d20L)"])
        adv_row.addWidget(self.dice_adv_combo, 1)
        dl.addLayout(adv_row)

        # Custom expression input + Roll button
        expr_row = QHBoxLayout()
        self.dice_input = QLineEdit("1d20")
        self.dice_input.setPlaceholderText("e.g. 1d20+2, 3d6+4")
        self.dice_input.returnPressed.connect(lambda: self.execute_dice_roll(self.dice_input.text()))
        b_roll = QPushButton("Roll")
        b_roll.setStyleSheet("background-color:#2563eb; border-color:#3b82f6; font-weight:bold;")
        b_roll.clicked.connect(lambda: self.execute_dice_roll(self.dice_input.text()))
        expr_row.addWidget(self.dice_input, 1)
        expr_row.addWidget(b_roll)
        dl.addLayout(expr_row)

        # Token Perk Macro Button
        self.token_macro_btn = QPushButton("Roll Selected Token Check (1d20 + Perk)")
        self.token_macro_btn.clicked.connect(self.roll_selected_token_macro)
        dl.addWidget(self.token_macro_btn)

        # Roll history output
        self.dice_log = QTextEdit()
        self.dice_log.setReadOnly(True)
        self.dice_log.setPlaceholderText("Dice roll results will appear here...")
        dl.addWidget(self.dice_log, 1)

        b_clr_log = QPushButton("Clear Roll Log")
        b_clr_log.clicked.connect(self.dice_log.clear)
        dl.addWidget(b_clr_log)

        lay.addWidget(gb_dice, 1)
        dock.setWidget(w)
        self.clock_dice_dock = dock
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self.player_dock, dock)
        self.player_dock.raise_()
        self.refresh_campaign_clock_ui(sync_night=False)

    def step_campaign_clock(self, delta):
        self.campaign_clock.advance_blocks(delta)
        self.refresh_campaign_clock_ui(sync_night=True)

    def reset_campaign_clock(self):
        self.campaign_clock.day = 1
        self.campaign_clock.block_index = 4
        self.refresh_campaign_clock_ui(sync_night=True)

    def on_clock_auto_night_toggled(self, checked):
        self.campaign_clock.auto_night = checked
        if checked:
            self.refresh_campaign_clock_ui(sync_night=True)

    def refresh_campaign_clock_ui(self, sync_night=False):
        day, time_range, label, is_night = self.campaign_clock.current_info()
        phase_badge = (
            "<span style='color:#93c5fd;'><b>NIGHT</b> (Low Visibility)</span>"
            if is_night else
            "<span style='color:#fde047;'><b>DAYLIGHT</b></span>"
        )
        self.clock_display.setText(
            f"<span style='font-size:13px; color:#ffffff;'><b>Day {day}</b> &nbsp;|&nbsp; {time_range}</span><br>"
            f"<span style='color:#9ca3af;'>{label}</span> &nbsp;•&nbsp; {phase_badge}"
        )
        if sync_night and self.campaign_clock.auto_night:
            if hasattr(self, "night_action") and self.night_action.isChecked() != is_night:
                self.night_action.setChecked(is_night)
        self.statusBar().showMessage(f"Clock: Day {day}, {time_range} ({label})")

    def _get_token_profile_and_bonus(self, tok):
        if tok is None:
            return None, 0, ""
        props = tok.props()
        prof = props.get("profile", {})
        if not prof or not prof.get("name"):
            active_prof = self.ruleset_manager.get_active_profile()
            if active_prof and "character_options" in active_prof:
                clean_name = re.sub(r"\s+\d+\s*$", "", tok.name).strip().lower()
                for _cat, options in active_prof["character_options"].items():
                    for opt in options:
                        opt_name = opt.get("name", "").lower()
                        if opt_name == clean_name or (opt_name and opt_name in clean_name):
                            prof = opt
                            break
                    if prof and prof.get("name"):
                        break
        if not isinstance(prof, dict) or not prof.get("name"):
            return None, 0, ""
        bonus_raw = str(prof.get("bonus") or "")
        m = re.search(r"([+-]\d+)", bonus_raw)
        mod = int(m.group(1)) if m else 0
        return prof, mod, bonus_raw

    def roll_selected_token_macro(self):
        sel_toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem)]
        if not sel_toks:
            self.execute_dice_roll("1d20", label="Unassigned Check")
            return
        tok = sel_toks[0]
        prof, mod, bonus_raw = self._get_token_profile_and_bonus(tok)
        active_prof = self.ruleset_manager.get_active_profile() or {}
        engine = active_prof.get("mechanics", {}).get("dice_engine", "1d20")
        if engine == "d6_pool":
            expr = "3d6"
            lbl = f"{tok.name} ({prof.get('name') if prof else 'Unit'})"
        else:
            expr = f"1d20{mod:+d}" if mod != 0 else "1d20"
            job_tag = f" [{prof.get('name')}]" if prof else ""
            lbl = f"{tok.name}{job_tag}"
        self.execute_dice_roll(expr, label=lbl)

    def execute_dice_roll(self, expr: str, label: str = ""):
        idx = self.dice_adv_combo.currentIndex() if hasattr(self, "dice_adv_combo") else 0
        adv_mode = ("normal", "adv", "dis")[idx]
        try:
            total, breakdown, is_crit, is_fumble = roll_dice_expression(expr, adv_mode)
        except Exception:
            self.statusBar().showMessage(f"Invalid dice expression: {expr}")
            return

        if is_crit:
            total_html = f"<span style='color:#22c55e; font-size:13px;'><b>{total} (CRIT!)</b></span>"
        elif is_fumble:
            total_html = f"<span style='color:#ef4444; font-size:13px;'><b>{total} (FUMBLE!)</b></span>"
        else:
            total_html = f"<span style='color:#93c5fd; font-size:13px;'><b>{total}</b></span>"

        prefix = f"<b>{label}:</b> " if label else ""
        entry = f"{prefix}{expr} &rarr; {total_html} <span style='color:#9ca3af;'>({breakdown})</span>"
        self.dice_log.append(entry)
        self.statusBar().showMessage(f"Rolled {expr} = {total} ({breakdown})")

    def refresh_token_list(self):
        toks = [it for it in self.scene.items() if isinstance(it, TokenItem)]
        toks.sort(key=lambda t: (not t.player, t.name.lower(), id(t)))
        sig = tuple((id(t), t.name, t.player, t.color.name(), tuple(t.statuses)) for t in toks)
        if sig == getattr(self, "_token_sig", None):
            return
        self._token_sig, self._token_refs = sig, toks
        self.token_list.clear()
        for t in toks:
            pm = QPixmap(14, 14)
            pm.fill(t.color)
            st_tag = f" [{', '.join(t.statuses)}]" if t.statuses else ""
            self.token_list.addItem(
                QListWidgetItem(QIcon(pm), ("\u2605 " if t.player else "") + (t.name or "(unnamed)") + st_tag)
            )

    def listed_token(self, item):
        row = self.token_list.row(item)
        toks = getattr(self, "_token_refs", [])
        if 0 <= row < len(toks):
            try:
                if toks[row].scene() is self.scene:
                    return toks[row]
            except RuntimeError:
                pass
        return None

    def update_token_perk_preview(self, tok):
        if tok is None:
            return
        props = tok.props()
        prof = props.get("profile", {})

        if not prof or not prof.get("name"):
            active_prof = self.ruleset_manager.get_active_profile()
            if active_prof and "character_options" in active_prof:
                clean_name = re.sub(r"\s+\d+\s*$", "", tok.name).strip().lower()
                for cat, options in active_prof["character_options"].items():
                    for opt in options:
                        opt_name = opt.get("name", "").lower()
                        if opt_name == clean_name or (opt_name and opt_name in clean_name):
                            prof = opt
                            break
                    if prof and prof.get("name"):
                        break

        if isinstance(prof, dict) and prof.get("name"):
            name = prof.get("name")
            bonus = prof.get("bonus") or prof.get("skill_proficiencies") or prof.get("role") or prof.get("hit_die") or "None"
            val = ", ".join(map(str, bonus)) if isinstance(bonus, list) else str(bonus)
            gear = prof.get("starting_gear", [])
            gear_str = ", ".join(gear) if isinstance(gear, list) else str(gear)
            ruleset_name = props.get("ruleset") or self.ruleset_manager.active_ruleset_name or "Active Ruleset"
            self.profile_info_label.setText(
                f"<b>Token:</b> {tok.name}<br>"
                f"<b>Ruleset:</b> {ruleset_name}<br>"
                f"<b>Job/Class:</b> {name}<br>"
                f"<b>Perk / Bonus:</b> {val}<br>"
                f"<b>Gear:</b> {gear_str or 'None'}"
            )
        else:
            self.profile_info_label.setText(f"<b>Token:</b> {tok.name}<br>No ruleset profile assigned.")

    def select_listed_token(self, item):
        tok = self.listed_token(item)
        if tok is not None:
            self.scene.clearSelection()
            tok.setSelected(True)
            self.update_token_perk_preview(tok)

    def zoom_listed_token(self, item):
        tok = self.listed_token(item)
        if tok is not None:
            self.scene.clearSelection()
            tok.setSelected(True)
            self.update_token_perk_preview(tok)
            self.view.focus_items([tok])


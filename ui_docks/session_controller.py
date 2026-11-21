import math
<<<<<<< HEAD
from PySide6.QtCore import Qt, QRectF, QLineF, QTimer
from PySide6.QtGui import QGuiApplication, QPainter
=======
import random
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF, QTimer
from PySide6.QtGui import QGuiApplication
>>>>>>> 73a3bee (Modularize battlemap domain folders and update project files)
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from core.config import (
    UNITS_PER_FT, CELL, LEVELS, JUMP_PX, Zoom, Tokens,
    level_for_zoom, fmt_len, auto_initials, worldgen,
)
from map_canvas.canvas_items import (
    TokenItem, RoadItem, FenceItem, DoorWallItem, BuildingItem,
    TerrainItem, PropItem, PlayerFrame,
)
from map_canvas.vision import (
    Vision, vision_range_ft, reset_explored, update_vision,
)
from map_canvas.world_assets import (
    DETAIL_ZOOM, ENEMY_LOOK, Atlas, _PROP_FT_SOURCE, _QPATHS,
)
from map_canvas.views import PlayerWindow
from ui_docks.dialogs import GenerateDialog, DungeonDialog


class SessionControllerMixin:
    """Vision updates, building interiors, player TV screen sync, and world/dungeon generation."""

    def setup_vision(self):
        self.vision_timer = QTimer(self)
        self.vision_timer.setSingleShot(True)
        self.vision_timer.setInterval(40)
        self.vision_timer.timeout.connect(self.run_vision)
        self.detail_timer = QTimer(self)
        self.detail_timer.setSingleShot(True)
        self.detail_timer.setInterval(120)
        self.detail_timer.timeout.connect(self.run_detail)
        self.scene.changed.connect(self.schedule_vision)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.ready = True
        self.on_selection_changed()
        self.schedule_vision()

    def schedule_vision(self, *_):
        if not self.vision_timer.isActive():
            self.vision_timer.start()

    def check_building_interiors(self):
        player_toks = [it for it in self.scene.items() if isinstance(it, TokenItem) and it.player]
        buildings = [it for it in self.scene.items() if isinstance(it, BuildingItem)]
<<<<<<< HEAD
        windows = [it for it in self.scene.items() if isinstance(it, DoorWallItem) and it.is_window]
        for b in buildings:
            brect = QRectF(b.pos().x(), b.pos().y(), b.w, b.h)
            inside = any(brect.contains(t.center()) for t in player_toks)
            if not inside and windows:
                peek_zone = brect.adjusted(-10 * UNITS_PER_FT, -10 * UNITS_PER_FT,
                                           10 * UNITS_PER_FT, 10 * UNITS_PER_FT)
                for win in windows:
                    wrect = win.sceneBoundingRect().adjusted(-15, -15, 15, 15)
                    if peek_zone.intersects(wrect) and any(
                        QLineF(t.center(), wrect.center()).length() <= 12 * UNITS_PER_FT for t in player_toks
                    ):
                        inside = True
                        break
=======
        for b in buildings:
            brect = QRectF(b.pos().x(), b.pos().y(), b.w, b.h)
            inside = any(brect.contains(t.center()) for t in player_toks)
>>>>>>> 73a3bee (Modularize battlemap domain folders and update project files)
            if inside != b.has_player_inside:
                b.has_player_inside = inside
                b.update()
            if inside and not b.interior_done:
                self.populate_building_interior(b, force=False)

<<<<<<< HEAD
=======
    def _fallback_interior_specs(self, b, seed, genre):
        bx_ft = b.pos().x() / UNITS_PER_FT
        by_ft = b.pos().y() / UNITS_PER_FT
        bw_ft = b.w / UNITS_PER_FT
        bh_ft = b.h / UNITS_PER_FT
        rng = random.Random(f"{seed}:{b.kind}:{round(bx_ft, 1)}:{round(by_ft, 1)}")
        specs = []
        pad = 6.0
        cx = bx_ft + bw_ft / 2.0
        cy = by_ft + bh_ft / 2.0

        kind_props = {
            "House": ["table", "bed", "chest"],
            "Shop": ["counter", "shelf", "crate"],
            "Inn": ["table", "hearth", "bed"],
            "Barn": ["crate", "wagon", "boulder"],
            "Warehouse": ["crate", "crate", "terminal"],
        }
        pool = kind_props.get(b.kind, ["table", "crate"])
        if genre == "apocalypse" and b.kind in ("Shop", "Warehouse"):
            pool = ["crate", "barricade", "terminal"]

        for idx, pkind in enumerate(pool):
            ox = cx + rng.uniform(-max(2.0, bw_ft * 0.25), max(2.0, bw_ft * 0.25))
            oy = cy + rng.uniform(-max(2.0, bh_ft * 0.25), max(2.0, bh_ft * 0.25))
            ox = max(bx_ft + pad, min(bx_ft + max(pad, bw_ft - pad), ox))
            oy = max(by_ft + pad, min(by_ft + max(pad, bh_ft - pad), oy))
            rot = rng.choice([0, 90, 180, 270])
            specs.append({"t": "prop", "kind": pkind, "x": ox, "y": oy, "rot": rot})
        return specs

>>>>>>> 73a3bee (Modularize battlemap domain folders and update project files)
    def populate_building_interior(self, b, force=False):
        if b.interior_done and not force:
            return
        b.interior_done = True
        b.has_player_inside = True
        b.update()
<<<<<<< HEAD
        if worldgen is None:
            return
        seed = Atlas.current.seed if Atlas.current is not None else 42
        genre = Atlas.current.genre if Atlas.current is not None else "fantasy"
        specs = worldgen.generate_building_interior(
            b.pos().x() / UNITS_PER_FT,
            b.pos().y() / UNITS_PER_FT,
            b.w / UNITS_PER_FT,
            b.h / UNITS_PER_FT,
            b.kind,
            seed=seed,
            genre=genre,
        )
        self.instantiate(specs, {})
=======

        seed = Atlas.current.seed if Atlas.current is not None else 42
        genre = Atlas.current.genre if Atlas.current is not None else "apocalypse"
        specs = []

        if worldgen is not None and hasattr(worldgen, "generate_building_interior"):
            try:
                res = worldgen.generate_building_interior(
                    b.pos().x() / UNITS_PER_FT,
                    b.pos().y() / UNITS_PER_FT,
                    b.w / UNITS_PER_FT,
                    b.h / UNITS_PER_FT,
                    b.kind,
                    seed=seed,
                    genre=genre,
                )
                if res:
                    specs = list(res)
            except Exception as ex:
                self.statusBar().showMessage(f"Interior generator note ({ex}); using built-in layout.")

        if not specs:
            specs = self._fallback_interior_specs(b, seed, genre)

        before_items = set(self.scene.items())
        self.instantiate(specs, {})
        for it in self.scene.items():
            if it not in before_items and it.zValue() <= b.zValue():
                it.setZValue(b.zValue() + 2)

>>>>>>> 73a3bee (Modularize battlemap domain folders and update project files)
        self.statusBar().showMessage(f"Generated interior for {b.label or b.kind}.")

    def run_vision(self):
        self.check_building_interiors()
        update_vision(self.scene)
        self.refresh_token_list()
        self.refresh_views()
        self.update_range_label()

    def refresh_views(self):
        if hasattr(self, "view"):
            self.view.viewport().update()
        if getattr(self, "player_win", None) is not None:
            self.player_win.view.viewport().update()

    def set_night(self, v):
        Vision.night = v
        self.schedule_vision()
        self.refresh_views()
        self.update_range_label()

    def set_ranges(self, *_):
        Vision.day_ft, Vision.night_ft = self.day_spin.value(), self.night_spin.value()
        self.schedule_vision()
        self.update_range_label()

    def set_vision_flag(self, name, value):
        setattr(Vision, name, value)
        self.schedule_vision()
        self.refresh_views()

    def reset_explored_ui(self):
        reset_explored()
        self.schedule_vision()
        self.refresh_views()

    def set_player_grid(self, v):
        self.player_grid = v
        self.refresh_views()

    def selected_player_token(self):
        toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem) and it.player]
        return toks[0] if len(toks) == 1 else None

    def on_selection_changed(self):
        tok = self.selected_player_token()
        self.mod_spin.setEnabled(tok is not None)
        self.mod_spin.blockSignals(True)
        self.mod_spin.setValue(tok.vision_mod if tok is not None else 0)
        self.mod_spin.blockSignals(False)
        self.update_range_label()
        all_sel_toks = [it for it in self.scene.selectedItems() if isinstance(it, TokenItem)]
        if len(all_sel_toks) == 1:
            self.update_token_perk_preview(all_sel_toks[0])

    def on_mod_changed(self, v):
        tok = self.selected_player_token()
        if tok is not None:
            tok.vision_mod = v
            tok.update()
            self.schedule_vision()
            self.update_range_label()

    def update_range_label(self):
        tok = self.selected_player_token()
        when = "night" if Vision.night else "day"
        if tok is not None:
            self.range_label.setText(f"{tok.name or 'This token'} sees {vision_range_ft(tok):.0f} ft ({when}).")
        else:
            self.range_label.setText(f"Currently {when}. Select one player token to adjust its vision bonus.")

    def apply_vision_settings(self, data):
        Vision.day_ft, Vision.night_ft = data.get("day_ft", 200), data.get("night_ft", 40)
        Vision.fog_on, Vision.remember = data.get("fog_on", True), data.get("remember", True)
        Atlas.current, Atlas.warned = None, False
        if data.get("world") and worldgen is not None:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                Atlas.current = worldgen.World.from_dict(data["world"])
            finally:
                QApplication.restoreOverrideCursor()
        _QPATHS.clear()
        self.clear_world_caches()
        Vision.fog_alpha = data.get("fog_alpha", 140)
        Tokens.min_dm, Tokens.min_tv = data.get("min_token_px", [28, 44])
        reset_explored(data.get("explored", []))
        self.fog_slider.blockSignals(True)
        self.fog_slider.setValue(round(Vision.fog_alpha * 100 / 255))
        self.fog_slider.blockSignals(False)
        self.fog_label.setText(f"Player fog darkness: {self.fog_slider.value()}%")
        for widget, val in ((self.min_dm_spin, Tokens.min_dm), (self.min_tv_spin, Tokens.min_tv)):
            widget.blockSignals(True)
            widget.setValue(val)
            widget.blockSignals(False)
        self.refresh_token_geometry()
        for widget, val in ((self.day_spin, Vision.day_ft), (self.night_spin, Vision.night_ft)):
            widget.blockSignals(True)
            widget.setValue(val)
            widget.blockSignals(False)
        for widget, val in ((self.fog_chk, Vision.fog_on), (self.remember_chk, Vision.remember)):
            widget.blockSignals(True)
            widget.setChecked(val)
            widget.blockSignals(False)
        self.night_action.setChecked(data.get("night", False))
        frame = data.get("player_frame")
        if frame:
            self.ensure_frame()
            self.frame.set_view_rect(QRectF(*frame))
        self.schedule_vision()

    # ---- the player window and what it shows
    def fill_screen_menu(self, menu):
        menu.clear()
        for scr in QGuiApplication.screens():
            g = scr.geometry()
            act = menu.addAction(f"{scr.name()}  ({g.width()}x{g.height()})")
            act.triggered.connect(lambda _=False, sc=scr: self.open_player_screen(sc))

    def open_player_screen(self, screen=None):
        if self.player_win is None:
            self.player_win = PlayerWindow(self.scene, self)
        win = self.player_win
        target = screen
        if target is None:
            mine = self.screen().name()
            others = [sc for sc in QGuiApplication.screens() if sc.name() != mine]
            target = others[0] if others else None
        win.show()
        if target is not None:
            win.windowHandle().setScreen(target)
            win.move(target.geometry().topLeft())
            win.showFullScreen()
        self.ensure_frame()
        QTimer.singleShot(200, self.sync_player_view)
        self.schedule_vision()

    def close_player_screen(self):
        if self.player_win is not None:
            self.player_win.close()

    def player_closed(self):
        self.player_win = None
        Zoom.tv = 0.0
        self.refresh_token_geometry()

    def set_mirror(self, v):
        self.mirror = v
        self.update_frame_visibility()
        self.sync_player_view()

    def player_aspect(self):
        if self.player_win is not None:
            vp = self.player_win.view.viewport()
            if vp.height() > 0:
                return vp.width() / vp.height()
        return 16 / 9

    def view_rect(self):
        return self.view.mapToScene(self.view.viewport().rect()).boundingRect()

    def expand_to_aspect(self, r):
        a = self.player_aspect()
        c, w, h = r.center(), r.width(), r.height()
        if w <= 0 or h <= 0:
            w, h = 1600.0, 900.0
        if w / h < a:
            w = h * a
        else:
            h = w / a
        return QRectF(c.x() - w / 2, c.y() - h / 2, w, h)

    def ensure_frame(self):
        if self.frame is None:
            self.frame = PlayerFrame(self.sync_player_view)
            self.scene.addItem(self.frame)
            self.frame.set_view_rect(self.expand_to_aspect(self.view_rect()))
        self.update_frame_visibility()

    def update_frame_visibility(self):
        if self.frame is not None:
            self.frame.setVisible(self.frame_chk.isChecked() and not self.mirror)

    def match_my_view(self):
        self.ensure_frame()
        self.frame.set_view_rect(self.expand_to_aspect(self.view_rect()))
        self.sync_player_view()

    def zoom_frame(self, factor):
        self.ensure_frame()
        r = QRectF(self.frame.pos(), self.frame.rect().size())
        c, w, h = r.center(), r.width() * factor, r.height() * factor
        self.frame.set_view_rect(QRectF(c.x() - w / 2, c.y() - h / 2, w, h))
        self.sync_player_view()

    def center_player_on_tokens(self, toks):
        if not toks:
            return
        cx = sum(t.center().x() for t in toks) / len(toks)
        cy = sum(t.center().y() for t in toks) / len(toks)
        if self.mirror:
            self.view.centerOn(cx, cy)
            return
        self.ensure_frame()
        size = self.frame.rect().size()
        self.frame.setPos(cx - size.width() / 2, cy - size.height() / 2)
        self.sync_player_view()

    def center_on_party(self):
        toks = [it for it in self.scene.items() if isinstance(it, TokenItem) and it.player]
        self.center_player_on_tokens(toks)

    def sync_player_view(self):
        if self.player_win is None or getattr(self, "_syncing", False):
            return
        self._syncing = True
        try:
            if self.mirror:
                rect = self.expand_to_aspect(self.view_rect())
            else:
                self.ensure_frame()
                cur = QRectF(self.frame.pos(), self.frame.rect().size())
                rect = self.expand_to_aspect(cur)
                if (abs(rect.width() - cur.width()) > 1e-6 * cur.width()
                        or abs(rect.height() - cur.height()) > 1e-6 * cur.height()):
                    self.frame.set_view_rect(rect)
            self.player_win.view.show_rect(rect)
            self.schedule_detail()
            name = LEVELS[level_for_zoom(self.player_win.view.transform().m11())][0]
            self.frame_label.setText(f"Players see {fmt_len(rect.width())} x {fmt_len(rect.height())} "
                                     f"(1 sq = {name}).")
        finally:
            self._syncing = False

    # ---- the generated state
    def clear_world_caches(self):
        self.view._world_cache = None
        if self.player_win is not None:
            self.player_win.view._world_cache = None

    def generate_state(self):
        if worldgen is None:
            QMessageBox.warning(self, "Worldgen Missing", "worldgen2.py could not be imported.")
            return
        dlg = GenerateDialog(self)
        if dlg.exec() != QDialog.Accepted or not self.confirm_discard():
            return
        opts = dlg.options()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            world = worldgen.World(**opts)
        finally:
            QApplication.restoreOverrideCursor()
        self.reset_scene()
        self.path = None
        Atlas.current, Atlas.warned = world, False
        _QPATHS.clear()
        self.clear_world_caches()
        self.undo.setClean()
        self.update_title()
        k = UNITS_PER_FT
        self.view.fitInView(QRectF(world.x0 * k, world.y0 * k, world.W * k, world.H * k), Qt.KeepAspectRatio)
        self.view.refresh_level()
        st = world.stats()
        self.statusBar().showMessage(f"Generated {opts['genre']} world: {st['cities']} cities, {st['towns']} towns, "
                                     f"{st['highways']} main routes.")
        self.refresh_views()

    def generate_dungeon_map(self):
        if worldgen is None:
            QMessageBox.warning(self, "Worldgen Missing", "worldgen2.py could not be imported.")
            return
        dlg = DungeonDialog(self)
        if dlg.exec() != QDialog.Accepted or not self.confirm_discard():
            return
        opts = dlg.options()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            QApplication.processEvents()
            specs, (sx, sy) = worldgen.generate_dungeon(**opts)
        finally:
            QApplication.restoreOverrideCursor()
        self.reset_scene()
        self.path = None
        self.clear_world_caches()
        self.instantiate(specs, {})
        starter = TokenItem("Party", "PT", "#3b82f6", 1, player=True)
        starter.setPos(sx * UNITS_PER_FT - CELL / 2, sy * UNITS_PER_FT - CELL / 2)
        self.scene.addItem(starter)
        self.undo.setClean()
        self.update_title()
        self.view.set_zoom(JUMP_PX / (5 * UNITS_PER_FT))
        self.view.centerOn(sx * UNITS_PER_FT, sy * UNITS_PER_FT)
        self.schedule_vision()
        self.statusBar().showMessage(f"Generated {opts['rooms']}-room dungeon. Click any orange door to open it!")

    def fill_city_menu(self, menu):
        menu.clear()
        w = Atlas.current
        if w is None:
            menu.addAction("(generate a world first)").setEnabled(False)
            return
        places = sorted(w.cities, key=lambda s: -s.radius) + sorted(w.towns, key=lambda s: -s.radius)[:30]
        for st in places:
            act = menu.addAction(f"{st.name} ({st.kind})")
            act.triggered.connect(lambda _=False, s2=st: self.go_to_settlement(s2))

    def go_to_settlement(self, st):
        self.view.set_zoom(JUMP_PX / (20 * UNITS_PER_FT))
        self.view.centerOn(st.x * UNITS_PER_FT, st.y * UNITS_PER_FT)

    def schedule_detail(self):
        if Atlas.current is not None and hasattr(self, "detail_timer") and not self.detail_timer.isActive():
            self.detail_timer.start()

    def run_detail(self):
        w = Atlas.current
        if w is None or worldgen is None:
            return
        rects = []
        if Zoom.dm >= DETAIL_ZOOM:
            rects.append(self.view_rect())
        if self.player_win is not None and Zoom.tv >= DETAIL_ZOOM:
            pv = self.player_win.view
            rects.append(pv.mapToScene(pv.viewport().rect()).boundingRect())
        ch, k, todo = worldgen.CHUNK_FT, UNITS_PER_FT, []
        for r in rects:
            for cx in range(math.floor(r.left() / k / ch), math.floor(r.right() / k / ch) + 1):
                for cy in range(math.floor(r.top() / k / ch), math.floor(r.bottom() / k / ch) + 1):
                    if (cx, cy) not in w.done and (cx, cy) not in todo:
                        todo.append((cx, cy))
        numbers = {}
        for key in todo[:6]:
            self.instantiate(w.plan_chunk(*key), numbers)
            w.done.add(key)
        if len(todo) > 6:
            self.detail_timer.start()

    def instantiate(self, specs, numbers):
        k = UNITS_PER_FT
        for sp in specs:
            t = sp["t"]
            if t == "road":
                it = RoadItem([QPointF(x * k, y * k) for x, y in sp["pts"]], sp.get("style", "Paved"), sp["width"])
            elif t == "building":
                it = BuildingItem(sp["kind"], sp["w"] * k, sp["h"] * k, sp.get("label", ""))
                it.setPos(sp["x"] * k, sp["y"] * k)
            elif t == "fence":
                it = FenceItem([QPointF(x * k, y * k) for x, y in sp["pts"]], sp.get("style", "Wood"), 1)
            elif t == "terrain":
                it = TerrainItem([QPointF(x * k, y * k) for x, y in sp["pts"]], sp["name"], "rect")
            elif t == "doorwall":
                it = DoorWallItem([QPointF(x * k, y * k) for x, y in sp["pts"]],
                                  kind=sp.get("kind", "door"), is_open=sp.get("is_open", False),
                                  is_door=sp.get("is_door"))
            elif t == "prop":
                fw, fh = _PROP_FT_SOURCE.get(sp["kind"], (10.0, 10.0))
                pw, ph = sp.get("w", fw) * k, sp.get("h", fh) * k
                it = PropItem(sp["kind"], pw, ph, sp.get("rot", 0))
                it.setPos(sp["x"] * k - pw / 2, sp["y"] * k - ph / 2)
            elif t == "token":
                kind = sp["kind"]
                color, size = ENEMY_LOOK.get(kind, ("#ef4444", 1))
                n = numbers.get(kind) or self.next_number(kind)
                numbers[kind] = n + 1
                name = f"{kind} {n}"
                it = TokenItem(name, auto_initials(name), color, size)
                it.setPos(sp["x"] * k, sp["y"] * k)
            else:
                continue
            self.scene.addItem(it)


import math
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsView, QMainWindow, QMenu
from PySide6.QtSvg import QSvgRenderer
from core.config import (
    CELL, UNITS_PER_FT, LEVELS, ZOOM_MIN, ZOOM_MAX, STATUS_COLORS,
    STANDARD_BUILDING_FT, DARK_PEN, Zoom, fmt_len, worldgen,
)
from core.math_utils import Snap, level_for_zoom, snap_point_to_grid
from map_canvas.canvas_items import (
    TokenItem, BuildingItem, RoadItem, FenceItem, DoorWallItem,
    PropItem, TerrainItem, RevealItem, UnderlayItem, StrokeItem,
)
from map_canvas.vision import draw_overlay
from map_canvas.world_assets import Atlas, PROP_UNITS, get_prop_asset, draw_world
from map_canvas.overlays import (
    Pointer, Ruler, Template, Chalk,
    chalk_begin, chalk_move, chalk_end, draw_chalk,
    draw_ruler_and_template, draw_pointer,
    AddCommand, RemoveCommand, MoveCommand,
)

# ----------------------------------------------------------------------------- view
class MapView(QGraphicsView):
    def __init__(self, scene, undo, main):
        super().__init__(scene)
        self.undo, self.main = undo, main
        self.tool = "select"
        self.snap, self.show_grid, self.dark = True, True, True
        self.pen_color, self.pen_width, self.fill = QColor(DARK_PEN), 4, False
        self.road_style, self.road_width, self.road_mode = "Paved", 20, "Curved"
        self.terrain_type, self.terrain_mode, self.terrain_brush = "Grass", "Brush", 4
        self.prop_kind, self.prop_rot = "car", 0
        self.building_kind, self.building_mode, self.fence_style = "House", "Standard", "Wood"
        self.doorwall_kind = "door"
        self.erase_filter = "all"
        self._pan = self._pan_btn = None
        self._space = False
        self._cur = self._start = self._end = None
        self._erased, self._press_pos = [], {}
        self._calibrating_underlay = None
        self.setFrameShape(QFrame.NoFrame)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setMouseTracking(True)
        self.set_tool("select")
    def delete_selected(self):
        items = [i for i in self.scene().selectedItems() if not getattr(i, "locked", False)]
        if items:
            self.undo.push(RemoveCommand(self.scene(), items))

    def set_tool(self, t):
        self.tool = t
        self.setDragMode(QGraphicsView.RubberBandDrag if t == "select" else QGraphicsView.NoDrag)
        if t != "select":
            self.scene().clearSelection()
        if t != "measure":
            Ruler.active = False
        if t != "template":
            Template.active = False
        self.refresh_cursor()
        self.viewport().update()
        if getattr(self.main, "player_win", None) is not None:
            self.main.player_win.view.viewport().update()

    def refresh_cursor(self):
        c = Qt.OpenHandCursor if self._space else {"select": Qt.ArrowCursor,
                                                  "token": Qt.PointingHandCursor}.get(self.tool, Qt.CrossCursor)
        self.viewport().setCursor(c)

    def snap_pt(self, p):
        return snap_point_to_grid(p) if self.snap else p

    def snap_road(self, p, width_ft):
        if not self.snap or Snap.grid_type != "square":
            return self.snap_pt(p)
        g = Snap.step
        n = max(1, round(width_ft * UNITS_PER_FT / g))
        if n % 2:
            return QPointF((math.floor(p.x() / g) + 0.5) * g, (math.floor(p.y() / g) + 0.5) * g)
        return QPointF(round(p.x() / g) * g, round(p.y() / g) * g)

    def standard_building_rect(self, center):
        w_ft, h_ft = STANDARD_BUILDING_FT.get(self.building_kind, (35, 30))
        w, h = w_ft * UNITS_PER_FT, h_ft * UNITS_PER_FT
        if self.snap and Snap.grid_type == "square":
            tl = QPointF(round((center.x() - w / 2) / CELL) * CELL,
                         round((center.y() - h / 2) / CELL) * CELL)
            return QRectF(tl.x(), tl.y(), w, h)
        c = self.snap_pt(center)
        return QRectF(c.x() - w / 2, c.y() - h / 2, w, h)

    def building_rect(self, a, b):
        if self.snap and Snap.grid_type == "square":
            g = Snap.step
            x0, x1 = sorted((math.floor(a.x() / g), math.floor(b.x() / g)))
            y0, y1 = sorted((math.floor(a.y() / g), math.floor(b.y() / g)))
            return QRectF(x0 * g, y0 * g, (x1 - x0 + 1) * g, (y1 - y0 + 1) * g)
        return QRectF(a, b).normalized()

    def zoom(self, factor, center=False):
        cur = self.transform().m11()
        f = max(ZOOM_MIN, min(ZOOM_MAX, cur * factor)) / cur
        if center:
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.scale(f, f)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.refresh_level()

    def refresh_level(self):
        lvl = level_for_zoom(self.transform().m11())
        Snap.step = LEVELS[lvl][1] * UNITS_PER_FT
        self.main.update_scale_ui(lvl)
        Zoom.dm = self.transform().m11()
        self.main.on_zoom_changed()

    def set_zoom(self, z):
        c = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.scale(z, z)
        self.centerOn(c)
        self.refresh_level()

    def focus_items(self, items):
        rect = None
        for it in items:
            d = it.size * CELL
            r = QRectF(it.pos().x(), it.pos().y(), d, d)
            rect = r if rect is None else rect.united(r)
        if rect is None:
            return
        rect.adjust(-4 * CELL, -4 * CELL, 4 * CELL, 4 * CELL)
        self.fitInView(rect, Qt.KeepAspectRatio)
        z = self.transform().m11()
        if z > ZOOM_MAX or z < ZOOM_MIN:
            self.set_zoom(max(ZOOM_MIN, min(ZOOM_MAX, z)))
        self.refresh_level()

    def show_status(self, sp):
        self.main.coord_pill.setText(f"X: {sp.x() / UNITS_PER_FT:,.0f} ft   Y: {sp.y() / UNITS_PER_FT:,.0f} ft")
        self.main.scale_pill.setText(f"1 sq = {fmt_len(Snap.step)}")
        cur, t = self._cur, self.tool
        msg = ""
        if self._calibrating_underlay is not None:
            msg = "CALIBRATE GRID: Drag a box across ONE grid square on the imported map image."
        elif cur is not None:
            if isinstance(cur, BuildingItem):
                msg = f"Building: {fmt_len(cur.w)} x {fmt_len(cur.h)}"
            elif t in ("line", "road", "fence", "doorwall"):
                msg = f"Length: {fmt_len(QLineF(self._start, self._end).length())}"
            elif t == "rect" or (t in ("terrain", "reveal") and cur.mode == "rect"):
                msg = (f"Area: {fmt_len(abs(self._end.x() - self._start.x()))} x "
                       f"{fmt_len(abs(self._end.y() - self._start.y()))}")
        self.main.statusBar().showMessage(msg)

    def drawBackground(self, p, rect):
        p.fillRect(rect, QColor("#1e2127") if self.dark else QColor("#f5f0e6"))
        if Atlas.current is not None:
            try:
                draw_world(self, p, rect)
            except Exception:
                if not Atlas.warned:
                    Atlas.warned = True
                    import traceback
                    traceback.print_exc()
        g = LEVELS[level_for_zoom(self.transform().m11())][1] * UNITS_PER_FT
        step = g * self.transform().m11()
        if not self.show_grid or Snap.grid_type == "none" or step < 4:
            return
        minor = QColor(255, 255, 255, 26) if self.dark else QColor(90, 70, 40, 50)
        major = QColor(255, 255, 255, 72) if self.dark else QColor(90, 70, 40, 120)
        l, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()

        if Snap.grid_type == "square":
            minor_lines, major_lines = [], []
            for i in range(math.floor(l / g), math.ceil(r / g) + 1):
                (major_lines if i % 5 == 0 else minor_lines).append(QLineF(i * g, t, i * g, b))
            for j in range(math.floor(t / g), math.ceil(b / g) + 1):
                (major_lines if j % 5 == 0 else minor_lines).append(QLineF(l, j * g, r, j * g))
            if step >= 10:
                p.setPen(QPen(minor, 0))
                p.drawLines(minor_lines)
            p.setPen(QPen(major, 0))
            p.drawLines(major_lines)
        elif Snap.grid_type in ("hex_pointy", "hex_flat"):
            if step < 10:
                return
            p.setPen(QPen(major, 0))
            R = g / math.sqrt(3)
            if Snap.grid_type == "hex_pointy":
                dx, dy = math.sqrt(3) * R, 1.5 * R
                r0, r1 = math.floor(t / dy) - 1, math.ceil(b / dy) + 1
                c0, c1 = math.floor(l / dx) - 1, math.ceil(r / dx) + 1
                corners = [QPointF(R * math.cos(math.radians(60 * k - 30)),
                                   R * math.sin(math.radians(60 * k - 30))) for k in range(6)]
                lines = []
                for row in range(r0, r1 + 1):
                    cy = row * dy
                    off = (dx / 2) if (row % 2) else 0.0
                    for col in range(c0, c1 + 1):
                        cx = col * dx + off
                        for k in range(3):
                            a, b_pt = corners[k], corners[k + 1]
                            lines.append(QLineF(cx + a.x(), cy + a.y(), cx + b_pt.x(), cy + b_pt.y()))
                p.drawLines(lines)
            else:
                dx, dy = 1.5 * R, math.sqrt(3) * R
                c0, c1 = math.floor(l / dx) - 1, math.ceil(r / dx) + 1
                r0, r1 = math.floor(t / dy) - 1, math.ceil(b / dy) + 1
                corners = [QPointF(R * math.cos(math.radians(60 * k)),
                                   R * math.sin(math.radians(60 * k))) for k in range(6)]
                lines = []
                for col in range(c0, c1 + 1):
                    cx = col * dx
                    off = (dy / 2) if (col % 2) else 0.0
                    for row in range(r0, r1 + 1):
                        cy = row * dy + off
                        for k in range(3):
                            a, b_pt = corners[k], corners[k + 1]
                            lines.append(QLineF(cx + a.x(), cy + a.y(), cx + b_pt.x(), cy + b_pt.y()))
                p.drawLines(lines)

    def drawForeground(self, p, rect):
        draw_overlay(self, p, rect, False)
        draw_chalk(self, p)
        draw_ruler_and_template(self, p)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        if Pointer.dm is not None:
            Pointer.dm = None
            self.main.update_player_pointer()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.main.on_dm_view_changed()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.main.on_dm_view_changed()

    def wheelEvent(self, e):
        self.zoom(1.3 if e.angleDelta().y() > 0 else 1 / 1.3)
        e.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = True
            self.refresh_cursor()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self._space = False
            self.refresh_cursor()
            return
        super().keyReleaseEvent(e)

    def contextMenuEvent(self, e):
        it = self.itemAt(e.pos())
        if isinstance(it, TokenItem):
            menu = QMenu(self)
            menu.addAction("Edit Token...", lambda: self.main.edit_token(it))
            sub = menu.addMenu("Toggle Status")
            for sname in STATUS_COLORS:
                act = sub.addAction(sname)
                act.setCheckable(True)
                act.setChecked(sname in it.statuses)
                act.triggered.connect(lambda checked, s=sname, tok=it: self.main.toggle_token_status(tok, s, checked))
            menu.addSeparator()
            menu.addAction("Delete Token", lambda: self.undo.push(RemoveCommand(self.scene(), [it])))
            menu.exec(e.globalPos())
            self._clear_sticky_pan()
            e.accept()
            return
        if isinstance(it, BuildingItem):
            menu = QMenu(self)
            menu.addAction("Edit Building...", lambda: self.main.edit_building(it))
            menu.addAction("Generate Interior Furniture", lambda: self.main.populate_building_interior(it, force=True))
            menu.addSeparator()
            menu.addAction("Delete Building", lambda: self.undo.push(RemoveCommand(self.scene(), [it])))
            menu.exec(e.globalPos())
            e.accept()
            return
        if isinstance(it, DoorWallItem) and it.interactive:
            it.toggle()
            self.main.schedule_vision()
            kind_lbl = "Door" if it.is_door else "Window"
            state_lbl = "Open" if it.is_open else "Closed"
            self.main.statusBar().showMessage(f"{kind_lbl}: {state_lbl}")
            e.accept()
            return
        super().contextMenuEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.tool == "select":
            it = self.itemAt(e.position().toPoint())
            if isinstance(it, DoorWallItem) and it.interactive:
                it.toggle()
                self.main.schedule_vision()
                e.accept()
                return
            if isinstance(it, (TokenItem, BuildingItem)):
                (self.main.edit_token if isinstance(it, TokenItem) else self.main.edit_building)(it)
                e.accept()
                return
            super().mouseDoubleClickEvent(e)
        else:
            self.mousePressEvent(e)

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if e.button() in (Qt.MiddleButton, Qt.RightButton) or (e.button() == Qt.LeftButton and self._space):
            self._pan, self._pan_btn = pos, e.button()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            e.accept()
            return
        if e.button() != Qt.LeftButton:
            return
        sp = self.mapToScene(pos)

        if self._calibrating_underlay is not None:
            self._start = self._end = sp
            self._cur = StrokeItem([], "#22d3ee", 2 / max(self.transform().m11(), 1e-6))
            self.scene().addItem(self._cur)
            return

        t = self.tool
        if t == "select":
            super().mousePressEvent(e)
            Snap.dragging = True
            self._press_pos = {it: it.pos() for it in self.scene().selectedItems()}
            sel_toks = [it for it in self.scene().selectedItems() if isinstance(it, TokenItem)]
            if sel_toks:
                self.main.update_token_perk_preview(sel_toks[0])
        elif t == "measure":
            Ruler.active = True
            Ruler.start = Ruler.end = self.snap_pt(sp)
            self.main.refresh_views()
        elif t == "template":
            Template.active = True
            Template.start = self.snap_pt(sp)
            Template.end = QPointF(Template.start.x() + Template.size_ft * UNITS_PER_FT, Template.start.y())
            self.main.refresh_views()
        elif t == "pen":
            self._cur = StrokeItem([sp, QPointF(sp.x() + 0.01, sp.y())], self.pen_color,
                                   self.pen_width * Snap.step / CELL)
            self._last = sp
            self.scene().addItem(self._cur)
        elif t in ("line", "rect"):
            self._start = self._end = self.snap_pt(sp)
            self._cur = StrokeItem([], self.pen_color, self.pen_width * Snap.step / CELL,
                                   self.fill and t == "rect")
            self.scene().addItem(self._cur)
        elif t == "road":
            self._road_straight = (self.road_mode == "Straight") or bool(e.modifiers() & Qt.ShiftModifier)
            if self._road_straight:
                self._start = self._end = self.snap_road(sp, self.road_width)
                self._cur = RoadItem([self._start, self._end], self.road_style, self.road_width)
            else:
                self._start = self._end = self._last = sp
                self._cur = RoadItem([sp, QPointF(sp.x() + 0.01, sp.y())], self.road_style, self.road_width)
            self.scene().addItem(self._cur)
        elif t == "fence":
            self._start = self._end = self.snap_pt(sp)
            self._cur = FenceItem([self._start, self._end], self.fence_style, Snap.step / CELL)
            self.scene().addItem(self._cur)
        elif t == "doorwall":
            it = self.itemAt(pos)
            if isinstance(it, DoorWallItem) and it.interactive:
                it.toggle()
                self.main.schedule_vision()
                kind_lbl = "Door" if it.is_door else "Window"
                state_lbl = "Open" if it.is_open else "Closed"
                self.main.statusBar().showMessage(f"{kind_lbl}: {state_lbl}")
                return
            self._start = self._end = self.snap_pt(sp)
            self._cur = DoorWallItem([self._start, self._end], kind=self.doorwall_kind, is_open=False)
            self.scene().addItem(self._cur)
        elif t == "building":
            self._start = sp
            self._bld_standard = (self.building_mode == "Standard") and not (e.modifiers() & Qt.ShiftModifier)
            self._cur = BuildingItem(self.building_kind, CELL, CELL)
            if self._bld_standard:
                self._cur.set_rect(self.standard_building_rect(sp))
            else:
                self._cur.set_rect(self.building_rect(sp, sp))
            self.scene().addItem(self._cur)
        elif t in ("terrain", "reveal"):
            width_ft = self.terrain_brush * Snap.step / UNITS_PER_FT
            if self.terrain_mode == "Rectangle":
                self._start = self._end = self.snap_pt(sp)
                pts, mode = [self._start, self._start], "rect"
            else:
                pts, mode = [sp, QPointF(sp.x() + 0.01, sp.y())], "brush"
                self._last = sp
            self._cur = (TerrainItem(pts, self.terrain_type, mode, width_ft) if t == "terrain"
                         else RevealItem(pts, mode, width_ft))
            self.scene().addItem(self._cur)
        elif t == "prop":
            if self.prop_kind in PROP_UNITS:
                pw, ph = PROP_UNITS[self.prop_kind]
            else:
                asset = get_prop_asset(self.prop_kind)
                if isinstance(asset, QSvgRenderer) and asset.isValid():
                    vb = asset.viewBoxF()
                    aspect = (vb.width() / vb.height()) if vb.height() > 0 else 1.0
                    pw, ph = 100 * aspect, 100
                elif isinstance(asset, QPixmap) and not asset.isNull():
                    aspect = (asset.width() / asset.height()) if asset.height() > 0 else 1.0
                    pw, ph = 100 * aspect, 100
                else:
                    pw, ph = 100, 100
            c = self.snap_pt(sp)
            prop = PropItem(self.prop_kind, pw, ph, self.prop_rot)
            prop.setPos(c.x() - pw / 2, c.y() - ph / 2)
            self.undo.push(AddCommand(self.scene(), [prop], "Place prop"))
        elif t == "chalk":
            chalk_begin(sp, self.transform().m11())
            self.main.refresh_views()
        elif t == "token":
            self.place_token(sp)
        elif t == "eraser":
            self._erased = []
            self.erase_at(sp)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._pan is not None:
            if not (e.buttons() & (Qt.MiddleButton | Qt.RightButton)) and not self._space:
                self._clear_sticky_pan()
                return
            d = pos - self._pan
            self._pan = pos
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() - d.x())
            v.setValue(v.value() - d.y())
            return
        sp = self.mapToScene(pos)
        if Pointer.laser:
            Pointer.dm = sp
            self.main.update_player_pointer()

        if self._calibrating_underlay is not None and self._cur is not None and (e.buttons() & Qt.LeftButton):
            self._end = sp
            s = self._start
            self._cur.pts = [s, QPointF(sp.x(), s.y()), sp, QPointF(s.x(), sp.y()), s]
            self._cur.rebuild()
            self.show_status(sp)
            return

        t = self.tool
        if not (e.buttons() & Qt.LeftButton) or t == "select":
            super().mouseMoveEvent(e)
        elif t == "measure" and Ruler.active:
            Ruler.end = self.snap_pt(sp)
            self.main.refresh_views()
        elif t == "template" and Template.active:
            Template.end = self.snap_pt(sp)
            self.main.refresh_views()
        elif t == "pen" and self._cur:
            if (sp - self._last).manhattanLength() * self.transform().m11() >= 2:
                self._cur.add_point(sp)
                self._last = sp
        elif t in ("line", "rect") and self._cur:
            self._end = end = self.snap_pt(sp)
            s = self._start
            if t == "line":
                self._cur.pts = [s, end]
            else:
                self._cur.pts = [s, QPointF(end.x(), s.y()), end, QPointF(s.x(), end.y()), s]
            self._cur.rebuild()
        elif t == "road" and self._cur:
            if getattr(self, "_road_straight", False):
                self._end = self.snap_road(sp, self.road_width)
                self._cur.pts = [self._start, self._end]
                self._cur.rebuild()
            elif (sp - self._last).manhattanLength() * self.transform().m11() >= 8:
                self._end = sp
                self._cur.pts.append(QPointF(sp))
                self._cur.rebuild()
                self._last = sp
        elif t in ("fence", "doorwall") and self._cur:
            self._end = self.snap_pt(sp)
            self._cur.pts = [self._start, self._end]
            self._cur.rebuild()
        elif t == "building" and self._cur:
            if getattr(self, "_bld_standard", False):
                self._cur.set_rect(self.standard_building_rect(sp))
            else:
                self._cur.set_rect(self.building_rect(self._start, sp))
        elif t in ("terrain", "reveal") and self._cur:
            if self._cur.mode == "rect":
                self._end = self.snap_pt(sp)
                s0, end = self._start, self._end
                self._cur.pts = [s0, QPointF(end.x(), s0.y()), end, QPointF(s0.x(), end.y()), s0]
                self._cur.rebuild()
            elif (sp - self._last).manhattanLength() * self.transform().m11() >= 2:
                self._cur.add_point(sp)
                self._last = sp
        elif t == "chalk":
            chalk_move(sp, self.transform().m11())
            self.main.refresh_views()
        elif t == "eraser":
            self.erase_at(sp)
        self.show_status(sp)

    def mouseReleaseEvent(self, e):
        if self._pan is not None:
            if e.button() == self._pan_btn:
                self._pan = None
                self.refresh_cursor()
            return
        if e.button() != Qt.LeftButton:
            return

        if self._calibrating_underlay is not None and self._cur is not None:
            self.scene().removeItem(self._cur)
            self._cur = None
            underlay = self._calibrating_underlay
            self._calibrating_underlay = None
            w_box = abs(self._end.x() - self._start.x())
            h_box = abs(self._end.y() - self._start.y())
            sq = max(w_box, h_box)
            if sq > 2:
                scale_factor = CELL / sq
                underlay.prepareGeometryChange()
                underlay.w *= scale_factor
                underlay.h *= scale_factor
                underlay.setPos(0, 0)
                underlay.update()
                self.statusBar().showMessage("Grid calibrated to 5 ft squares!")
            return

        t = self.tool
        if t == "select":
            super().mouseReleaseEvent(e)
            Snap.dragging = False
            moves = [(it, old, it.pos()) for it, old in self._press_pos.items()
                     if it.scene() is not None and it.pos() != old]
            self._press_pos = {}
            if moves:
                self.undo.push(MoveCommand(moves))
        elif t in ("pen", "line", "rect", "road", "fence", "doorwall", "building", "terrain", "reveal") and self._cur:
            item, self._cur = self._cur, None
            self.scene().removeItem(item)
            curved_road = (t == "road" and not getattr(self, "_road_straight", False))
            if curved_road and len(item.pts) >= 3 and worldgen is not None:
                smoothed = worldgen.chaikin([(p.x(), p.y()) for p in item.pts], 2)
                item.pts = [QPointF(x, y) for x, y in smoothed]
                item.rebuild()
            keep = (t in ("pen", "building") or curved_road
                    or (t in ("terrain", "reveal") and item.mode == "brush")
                    or self._start != self._end)
            if t == "building" and (item.w < 4 or item.h < 4):
                keep = False
            if keep:
                self.undo.push(AddCommand(self.scene(), [item], "Draw"))
        elif t == "chalk":
            chalk_end()
        elif t == "eraser" and self._erased:
            self.undo.push(RemoveCommand(self.scene(), self._erased))
            self._erased = []
    def _clear_sticky_pan(self):
        self._pan = None
        self._pan_btn = None
        self._space = False
        Snap.dragging = False
        self._press_pos = {}
        self.refresh_cursor()

    def focusOutEvent(self, e):
        self._clear_sticky_pan()
        super().focusOutEvent(e)

    def erase_at(self, sp):
        r = 10 / self.transform().m11()
        big_done = False
        for it in self.scene().items(QRectF(sp.x() - r, sp.y() - r, 2 * r, 2 * r), Qt.IntersectsItemShape):
            if self.erase_filter == "drawings":
                if isinstance(it, (StrokeItem, RevealItem)):
                    self.scene().removeItem(it)
                    self._erased.append(it)
                continue
            big = isinstance(it, (RoadItem, BuildingItem, TerrainItem))
            if isinstance(it, (StrokeItem, FenceItem, DoorWallItem, PropItem, RevealItem)) or (big and not big_done):
                big_done = big_done or big
                self.scene().removeItem(it)
                self._erased.append(it)

    def place_token(self, sp):
        toks = self.main.make_tokens(sp)
        self.undo.push(AddCommand(self.scene(), toks, "Place tokens" if len(toks) > 1 else "Place token"))

    def delete_selected(self):
        items = self.scene().selectedItems()
        if items:
            self.undo.push(RemoveCommand(self.scene(), items))


# ----------------------------------------------------------------------------- player screen
# ----------------------------------------------------------------------------- player screen


class PlayerView(QGraphicsView):
    def __init__(self, scene, main):
        super().__init__(scene)
        self.main = main
        self.viewport().setProperty("player_view", True)
        self.viewport().setCursor(Qt.CrossCursor)
        self.viewport().setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setInteractive(False)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._pan = None
        self._draw = False

    @property
    def dark(self):
        return self.main.view.dark

    @property
    def show_grid(self):
        return self.main.player_grid

    def drawBackground(self, p, rect):
        MapView.drawBackground(self, p, rect)

    def drawForeground(self, p, rect):
        draw_overlay(self, p, rect, True)
        draw_chalk(self, p)
        draw_ruler_and_template(self, p)
        draw_pointer(self, p)

    def show_rect(self, rect):
        vp = self.viewport()
        if vp.width() <= 0 or vp.height() <= 0 or rect.width() <= 0 or rect.height() <= 0:
            return
        s = min(vp.width() / rect.width(), vp.height() / rect.height())
        self.resetTransform()
        self.scale(s, s)
        self.centerOn(rect.center())
        Zoom.tv = self.transform().m11()
        self.main.refresh_token_geometry()

    def zoom_by(self, factor, center=False):
        cur = self.transform().m11()
        f = max(ZOOM_MIN, min(ZOOM_MAX, cur * factor)) / cur
        if center:
            self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.scale(f, f)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        Zoom.tv = self.transform().m11()
        self.main.refresh_token_geometry()
        self.main.player_navigated()

    def nudge(self, dx, dy):
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setValue(h.value() + dx)
        v.setValue(v.value() + dy)
        self.main.player_navigated()

    def wheelEvent(self, e):
        self.zoom_by(1.3 if e.angleDelta().y() > 0 else 1 / 1.3)
        e.accept()

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if e.button() == Qt.LeftButton and self.main.view.tool == "chalk":
            self._draw = True
            chalk_begin(self.mapToScene(pos), self.transform().m11())
            self.main.refresh_views()
        else:
            self._pan = pos
        e.accept()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        Pointer.tv = self.mapToScene(pos)
        if self._draw:
            chalk_move(Pointer.tv, self.transform().m11())
            self.main.refresh_views()
        elif self._pan is not None:
            d = pos - self._pan
            self._pan = pos
            h, v = self.horizontalScrollBar(), self.verticalScrollBar()
            h.setValue(h.value() - d.x())
            v.setValue(v.value() - d.y())
            self.main.player_navigated()
        self.viewport().update()

    def mouseReleaseEvent(self, e):
        if self._draw:
            chalk_end()
            self._draw = False
        self._pan = None

    def leaveEvent(self, e):
        Pointer.tv = None
        self.viewport().update()
        super().leaveEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.main.sync_player_view()


class PlayerWindow(QMainWindow):
    def __init__(self, scene, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("Player Screen")
        self.view = PlayerView(scene, main)
        self.setCentralWidget(self.view)
        self.resize(1280, 720)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif e.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif e.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            dx = {Qt.Key_Left: -80, Qt.Key_Right: 80}.get(e.key(), 0)
            dy = {Qt.Key_Up: -80, Qt.Key_Down: 80}.get(e.key(), 0)
            self.view.nudge(dx, dy)
        elif e.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.view.zoom_by(1.3, True)
        elif e.key() == Qt.Key_Minus:
            self.view.zoom_by(1 / 1.3, True)
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        self.main.player_closed()
        e.accept()


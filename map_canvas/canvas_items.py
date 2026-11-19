import math
import re
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath,
    QPainterPathStroker, QPen, QPixmap,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsRectItem, QStyle, QStyleOptionGraphicsItem
from PySide6.QtSvg import QSvgRenderer
from core.config import (
    CELL, UNITS_PER_FT, ROAD_STYLES, BUILDING_KINDS, FENCE_STYLES,
    STATUS_COLORS, TERRAIN, Zoom, Tokens,
)
from core.math_utils import Snap, snap_point_to_grid


def _vision():
    from map_canvas.vision import Vision
    return Vision


def hidden_in_fog(item):
    from map_canvas.vision import hidden_in_fog as _hif
    return _hif(item)


def get_prop_asset(kind):
    from map_canvas.world_assets import get_prop_asset as _gpa
    return _gpa(kind)


# ----------------------------------------------------------------------------- items
class PlayerSafe:
    def paint(self, p, option, widget=None):
        if widget is not None and widget.property("player_view"):
            if hidden_in_fog(self):
                return
            option = QStyleOptionGraphicsItem(option)
            option.state &= ~QStyle.State_Selected
        super().paint(p, option, widget)


class Snappy:
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and Snap.on and Snap.dragging:
            return snap_point_to_grid(value)
        return super().itemChange(change, value)


class UnderlayItem(QGraphicsItem):
    def __init__(self, img_path, w, h, opacity=1.0):
        super().__init__()
        self.img_path = str(img_path)
        self.w, self.h = float(w), float(h)
        self.opacity_val = float(opacity)
        self._pix = QPixmap(self.img_path)
        self.setZValue(-20)
        self.setAcceptedMouseButtons(Qt.NoButton)

    def boundingRect(self):
        return QRectF(0, 0, self.w, self.h)

    def paint(self, p, option, widget=None):
        if self._pix.isNull():
            return
        p.save()
        p.setOpacity(self.opacity_val)
        p.drawPixmap(QRectF(0, 0, self.w, self.h), self._pix, QRectF(self._pix.rect()))
        p.restore()

    def to_dict(self):
        return {"type": "underlay", "path": self.img_path, "w": self.w, "h": self.h,
                "opacity": self.opacity_val, "x": self.pos().x(), "y": self.pos().y()}


class StrokeItem(PlayerSafe, QGraphicsPathItem):
    def __init__(self, pts, color, width, fill=False):
        super().__init__()
        self.pts = [QPointF(p) for p in pts]
        self.color, self.width, self.fill = QColor(color), width, fill
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setZValue(5)
        self.rebuild()

    def rebuild(self):
        path = QPainterPath()
        if self.pts:
            path.moveTo(self.pts[0])
            for p in self.pts[1:]:
                path.lineTo(p)
        self.setPath(path)
        self.setPen(QPen(self.color, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if self.fill:
            c = QColor(self.color)
            c.setAlpha(70)
            self.setBrush(QBrush(c))
        else:
            self.setBrush(Qt.NoBrush)

    def add_point(self, p):
        self.pts.append(QPointF(p))
        path = self.path()
        path.lineTo(p)
        self.setPath(path)

    def to_dict(self):
        return {"type": "stroke", "color": self.color.name(), "width": self.width, "fill": self.fill,
                "x": self.pos().x(), "y": self.pos().y(), "pts": [[p.x(), p.y()] for p in self.pts]}


class TokenItem(Snappy, QGraphicsItem):
    snap = True

    def __init__(self, name, initials, color, size=1, player=False, vision_mod=0,
                 statuses=None, aura_ft=0, aura_color="#3b82f6", image_path="",
                 ruleset="", category="", profile_name="", profile=None):
        super().__init__()
        self.name, self.initials, self.color, self.size = name, initials, QColor(color), size
        self.player, self.vision_mod = player, vision_mod
        self.statuses = list(statuses) if statuses else []
        self.aura_ft = int(aura_ft)
        self.aura_color = QColor(aura_color)
        self.image_path = image_path or ""
        self.ruleset = ruleset or ""
        self.category = category or ""
        self.profile_name = profile_name or ""
        self.profile = dict(profile) if isinstance(profile, dict) else {}
        self._pix = QPixmap(self.image_path) if self.image_path else QPixmap()
        self._D = self.enlarged()
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(10)

    def props(self):
        return {"name": self.name, "initials": self.initials, "color": self.color.name(), "size": self.size,
                "player": self.player, "vision_mod": self.vision_mod, "statuses": list(self.statuses),
                "aura_ft": self.aura_ft, "aura_color": self.aura_color.name(), "image_path": self.image_path,
                "ruleset": self.ruleset, "category": self.category,
                "profile_name": self.profile_name, "profile": dict(self.profile)}

    def set_props(self, d):
        self.prepareGeometryChange()
        self.name, self.initials, self.size = d["name"], d["initials"], d["size"]
        self.player, self.vision_mod = d.get("player", False), d.get("vision_mod", 0)
        self.color = QColor(d["color"])
        self.statuses = list(d.get("statuses", []))
        self.aura_ft = int(d.get("aura_ft", 0))
        self.aura_color = QColor(d.get("aura_color", "#3b82f6"))
        self.image_path = d.get("image_path", "")
        self.ruleset = d.get("ruleset", self.ruleset)
        self.category = d.get("category", self.category)
        self.profile_name = d.get("profile_name", self.profile_name)
        if "profile" in d and isinstance(d["profile"], dict):
            self.profile = dict(d["profile"])
        self._pix = QPixmap(self.image_path) if self.image_path else QPixmap()
        self._D = self.enlarged()
        self.update()

    def to_dict(self):
        d = {"type": "token", "x": self.pos().x(), "y": self.pos().y()}
        d.update(self.props())
        return d

    def circle(self):
        d = self.size * CELL
        return QRectF(3, 3, d - 6, d - 6)

    def center(self):
        d = self.size * CELL
        return QPointF(self.pos().x() + d / 2, self.pos().y() + d / 2)

    def enlarged(self):
        d = self.size * CELL
        tv = Tokens.min_tv / Zoom.tv if Zoom.tv > 0 else 0
        return max(d, Tokens.min_dm / max(Zoom.dm, 1e-9), tv)

    def refresh_geometry(self):
        big = self.enlarged()
        if abs(big - self._D) > 1e-6:
            self.prepareGeometryChange()
            self._D = big
            self.update()

    def boundingRect(self):
        d, D = self.size * CELL, self._D
        aura_r = (d / 2 + self.aura_ft * UNITS_PER_FT) if self.aura_ft > 0 else 0
        half = max(D / 2, aura_r)
        return QRectF(d / 2 - half - CELL / 2 - 4, d / 2 - half - 4, half * 2 + CELL + 8, half * 2 + 28)

    def shape(self):
        p = QPainterPath()
        d = self.size * CELL
        k = self._D / d
        p.addEllipse(QPointF(d / 2, d / 2), (d / 2 - 3) * k, (d / 2 - 3) * k)
        return p

    def paint(self, p, option, widget=None):
        on_tv = widget is not None and widget.property("player_view")
        if (on_tv and _vision().fog_on and not self.player
                and not _vision().visible.contains(self.center())):
            return
        p.setRenderHint(QPainter.Antialiasing)
        d = self.size * CELL
        c = QPointF(d / 2, d / 2)
        if self.aura_ft > 0:
            ar = d / 2 + self.aura_ft * UNITS_PER_FT
            ac = QColor(self.aura_color)
            ac.setAlpha(45)
            p.setBrush(ac)
            ac_border = QColor(self.aura_color)
            ac_border.setAlpha(180)
            pen = QPen(ac_border, 2, Qt.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawEllipse(c, ar, ar)
        z = p.worldTransform().m11()
        k = max(1.0, (Tokens.min_tv if on_tv else Tokens.min_dm) / (d * z))
        p.save()
        if k > 1.0:
            p.translate(c)
            p.scale(k, k)
            p.translate(-c)
        r = self.circle()
        edge = QColor("#f59e0b") if self.isSelected() and not on_tv else self.color.darker(170)
        p.setPen(QPen(edge, 3))
        p.setBrush(self.color)
        p.drawEllipse(r)
        if not self._pix.isNull():
            p.save()
            clip = QPainterPath()
            clip.addEllipse(r.adjusted(1.5, 1.5, -1.5, -1.5))
            p.setClipPath(clip)
            p.drawPixmap(r.toRect(), self._pix)
            p.restore()
        else:
            lum = 0.299 * self.color.red() + 0.587 * self.color.green() + 0.114 * self.color.blue()
            p.setPen(QColor("#111") if lum > 150 else QColor("#fff"))
            if self.initials:
                font = QFont()
                font.setBold(True)
                px = int(r.height() * 0.42)
                font.setPixelSize(px)
                while px > 6 and QFontMetricsF(font).horizontalAdvance(self.initials) > r.width() * 0.8:
                    px -= 1
                    font.setPixelSize(px)
                p.setFont(font)
                p.drawText(r, Qt.AlignCenter, self.initials)
        if self.player:
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(5, 5, -5, -5))
        if self.statuses:
            rad = r.width() / 2
            dot_r = max(4.0, rad * 0.17)
            for idx, st_name in enumerate(self.statuses[:6]):
                ang = -math.pi / 4 + idx * 0.48
                dx = c.x() + rad * math.cos(ang)
                dy = c.y() + rad * math.sin(ang)
                p.setPen(QPen(QColor("#111827"), 1.5))
                p.setBrush(QColor(STATUS_COLORS.get(st_name, "#ffffff")))
                p.drawEllipse(QPointF(dx, dy), dot_r, dot_r)
        if self.name and k == 1.0:
            font = QFont()
            font.setPixelSize(13)
            p.setFont(font)
            fm = QFontMetricsF(font)
            text = fm.elidedText(self.name, Qt.ElideRight, d + CELL - 14)
            w = fm.horizontalAdvance(text) + 10
            box = QRectF((d - w) / 2, d + 2, w, 18)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 215))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QColor("#111"))
            p.drawText(box, Qt.AlignCenter, text)
        p.restore()


ENV_FLAGS = (QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
             QGraphicsItem.ItemSendsGeometryChanges)


class PolyItem(PlayerSafe, Snappy, QGraphicsPathItem):
    kind = ""
    def __init__(self, pts, style, width=0):
        super().__init__()
        self.pts, self.style, self.width = [QPointF(p) for p in pts], style, width
        self.setFlags(ENV_FLAGS)
        self.rebuild()

    def rebuild(self):
        path = QPainterPath()
        path.moveTo(self.pts[0])
        for p in self.pts[1:]:
            path.lineTo(p)
        self.setPath(path)
        self.style_pen()

    def to_dict(self):
        return {"type": self.kind, "style": self.style, "width": self.width,
                "x": self.pos().x(), "y": self.pos().y(), "pts": [[p.x(), p.y()] for p in self.pts]}


class RoadItem(PolyItem):
    kind = "road"
    def __init__(self, pts, style="Paved", width=20):
        super().__init__(pts, style, width)
        self.setZValue(-5)

    def to_dict(self):
        d = super().to_dict()
        d["width_ft"] = d.pop("width")
        return d

    def style_pen(self):
        self.setPen(QPen(QColor(ROAD_STYLES[self.style][0]), self.width * UNITS_PER_FT,
                         Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setBrush(Qt.NoBrush)

    def paint(self, p, option, widget=None):
        z = p.worldTransform().m11()
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(Qt.NoBrush)
        w = max(self.width * UNITS_PER_FT, 3 / z)
        p.setPen(QPen(QColor(ROAD_STYLES[self.style][0]), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(self.path())
        if self.isSelected() and not (widget is not None and widget.property("player_view")):
            sel = QPen(QColor("#f59e0b"), 2, Qt.DashLine)
            sel.setCosmetic(True)
            p.setPen(sel)
            p.drawPath(self.shape())
        if ROAD_STYLES[self.style][1] and self.width * UNITS_PER_FT * z >= 6:
            mid = QPen(QColor("#f3efe0"), 2, Qt.DashLine)
            mid.setCosmetic(True)
            p.setPen(mid)
            p.drawPath(self.path())


class FenceItem(PolyItem):
    kind = "fence"
    def __init__(self, pts, style="Wood", width=1):
        super().__init__(pts, style, width or 1)
        self.setZValue(3)

    def style_pen(self):
        color, w = FENCE_STYLES[self.style]
        self.setPen(QPen(QColor(color), w * self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setBrush(Qt.NoBrush)

    def boundingRect(self):
        m = 6 * self.width
        return super().boundingRect().adjusted(-m, -m, m, m)

    def shape(self):
        st = QPainterPathStroker()
        st.setWidth(max(self.pen().widthF(), 14 * self.width))
        return st.createStroke(self.path())

    def paint(self, p, option, widget=None):
        if widget is not None and widget.property("player_view") and hidden_in_fog(self):
            return
        p.setRenderHint(QPainter.Antialiasing)
        super().paint(p, option, widget)
        if self.style == "Wood":
            n = max(1, round(self.path().length() / (CELL / 2 * self.width)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#4a2f17"))
            for i in range(n + 1):
                p.drawEllipse(self.path().pointAtPercent(i / n), 4 * self.width, 4 * self.width)
        elif self.style == "Stone wall":
            p.setPen(QPen(QColor("#bdbdbd"), 4 * self.width, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(self.path())


class DoorWallItem(Snappy, QGraphicsPathItem):
    def __init__(self, pts, kind="door", is_open=False, is_door=None):
        super().__init__()
        self.pts = [QPointF(p) for p in pts]
        if is_door is not None and kind == "door":
            self.kind = "door" if is_door else "wall"
        else:
            self.kind = kind if kind in ("door", "window", "wall") else "door"
        self.is_open = bool(is_open)
        self.setFlags(ENV_FLAGS)
        self.setZValue(6)
        self.rebuild()

    @property
    def is_door(self):
        return self.kind == "door"
    @property
    def is_window(self):
        return self.kind == "window"
    @property
    def interactive(self):
        return self.kind in ("door", "window")

    def blocks_vision(self):
        return self.kind == "wall" or (self.kind == "door" and not self.is_open)

    def rebuild(self):
        path = QPainterPath()
        if self.pts:
            path.moveTo(self.pts[0])
            for p in self.pts[1:]:
                path.lineTo(p)
        self.setPath(path)
        self.setPen(QPen(QColor("#f59e0b"), 8))

    def shape(self):
        st = QPainterPathStroker()
        st.setWidth(18)
        return st.createStroke(self.path())

    def toggle(self):
        if self.interactive:
            self.is_open = not self.is_open
            self.update()

    def to_dict(self):
        return {"type": "doorwall", "kind": self.kind, "is_door": self.is_door, "is_open": self.is_open,
                "x": self.pos().x(), "y": self.pos().y(), "pts": [[p.x(), p.y()] for p in self.pts]}

    def paint(self, p, option, widget=None):
        on_tv = widget is not None and widget.property("player_view")
        if on_tv and hidden_in_fog(self):
            return
        p.setRenderHint(QPainter.Antialiasing)
        if self.kind == "door":
            color = QColor("#22c55e") if self.is_open else QColor("#f59e0b")
            style = Qt.DashLine if self.is_open else Qt.SolidLine
            p.setPen(QPen(color, 7, style, Qt.RoundCap))
            p.drawPath(self.path())
        elif self.kind == "window":
            p.setPen(QPen(QColor("#1e293b"), 7, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(self.path())
            glass_style = Qt.DashLine if self.is_open else Qt.SolidLine
            p.setPen(QPen(QColor("#38bdf8"), 3.5, glass_style, Qt.RoundCap))
            p.drawPath(self.path())
        else:
            if on_tv:
                return
            p.setPen(QPen(QColor("#60a5fa"), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(self.path())
        if self.isSelected() and not on_tv:
            sel = QPen(QColor("#ffffff"), 2, Qt.DashLine)
            sel.setCosmetic(True)
            p.setPen(sel)
            p.drawPath(self.shape())


class BuildingItem(Snappy, QGraphicsItem):
    def __init__(self, kind, w, h, label="", interior_done=False):
        super().__init__()
        self.kind, self.w, self.h, self.label = kind, w, h, label
        self.interior_done = bool(interior_done)
        self.has_player_inside = False
        self.setFlags(ENV_FLAGS)
        self.setZValue(2)

    def props(self):
        return {"kind": self.kind, "label": self.label}

    def set_props(self, d):
        self.kind, self.label = d["kind"], d["label"]
        self.update()

    def set_rect(self, r):
        self.prepareGeometryChange()
        self.setPos(r.topLeft())
        self.w, self.h = r.width(), r.height()

    def to_dict(self):
        return {"type": "building", "kind": self.kind, "label": self.label, "w": self.w, "h": self.h,
                "interior_done": self.interior_done, "x": self.pos().x(), "y": self.pos().y()}

    def boundingRect(self):
        return QRectF(-4, -4, self.w + 8, self.h + 8)

    def shape(self):
        p = QPainterPath()
        p.addRect(0, 0, self.w, self.h)
        return p

    def paint(self, p, option, widget=None):
        on_tv = widget is not None and widget.property("player_view")
        if on_tv and hidden_in_fog(self):
            return
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.w, self.h
        base = QColor(BUILDING_KINDS.get(self.kind, "#888888"))
        p.setPen(Qt.NoPen)
        draw_interior = self.has_player_inside and not (on_tv and hidden_in_fog(self))
        if draw_interior:
            floor_col = QColor("#3b2f26") if self.kind in ("House", "Inn", "Shop", "Barn") else QColor("#374151")
            p.fillRect(QRectF(0, 0, w, h), floor_col)
            plank_pen = QPen(floor_col.darker(125), 1)
            plank_pen.setCosmetic(True)
            p.setPen(plank_pen)
            step_p = 2.5 * UNITS_PER_FT
            y_p = step_p
            while y_p < h:
                p.drawLine(QLineF(0, y_p, w, y_p))
                y_p += step_p
        else:
            if w >= h:
                p.fillRect(QRectF(0, 0, w, h / 2), base.lighter(115))
                p.fillRect(QRectF(0, h / 2, w, h / 2), base.darker(115))
                ridge = QLineF(8, h / 2, w - 8, h / 2)
            else:
                p.fillRect(QRectF(0, 0, w / 2, h), base.lighter(115))
                p.fillRect(QRectF(w / 2, 0, w / 2, h), base.darker(115))
                ridge = QLineF(w / 2, 8, w / 2, h - 8)
            ridge_pen = QPen(base.darker(160), 1.5)
            ridge_pen.setCosmetic(True)
            p.setPen(ridge_pen)
            p.drawLine(ridge)
        p.setBrush(Qt.NoBrush)
        wall = QPen(QColor("#f59e0b") if self.isSelected() and not on_tv else QColor("#2b2b2b"), 3)
        wall.setCosmetic(True)
        p.setPen(wall)
        p.drawRect(QRectF(0, 0, w, h))
        if w >= 60:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3a2a1a"))
            p.drawRect(QRectF(w / 2 - 20, h - 6, 40, 12))
        z = p.worldTransform().m11()
        if self.label and w * z > 40:
            lum = 0.299 * base.red() + 0.587 * base.green() + 0.114 * base.blue()
            font = QFont()
            font.setBold(True)
            font.setPixelSize(13)
            sw, sh = w * z, h * z
            p.save()
            p.translate(w / 2, h / 2)
            p.scale(1 / z, 1 / z)
            p.setFont(font)
            p.setPen(QColor("#111") if lum > 150 else QColor("#fff"))
            text = QFontMetricsF(font).elidedText(self.label, Qt.ElideRight, sw - 10)
            p.drawText(QRectF(-sw / 2, -sh / 2, sw, sh), Qt.AlignCenter, text)
            p.restore()


class TerrainItem(QGraphicsPathItem):
    def __init__(self, pts, terrain, mode="brush", width_ft=20):
        super().__init__()
        self.pts, self.terrain, self.mode = [QPointF(p) for p in pts], terrain, mode
        self.width_ft = width_ft
        self.setZValue(-10)
        self.rebuild()

    def rebuild(self):
        path = QPainterPath()
        if self.pts:
            path.moveTo(self.pts[0])
            for p in self.pts[1:]:
                path.lineTo(p)
        self.setPath(path)
        color = QColor(TERRAIN[self.terrain])
        if self.mode == "rect":
            self.setPen(QPen(Qt.NoPen))
            self.setBrush(QBrush(color))
        else:
            self.setPen(QPen(color, self.width_ft * UNITS_PER_FT, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self.setBrush(Qt.NoBrush)

    def add_point(self, p):
        self.pts.append(QPointF(p))
        path = self.path()
        path.lineTo(p)
        self.setPath(path)

    def to_dict(self):
        return {"type": "terrain", "terrain": self.terrain, "mode": self.mode, "width_ft": self.width_ft,
                "x": self.pos().x(), "y": self.pos().y(), "pts": [[p.x(), p.y()] for p in self.pts]}


class PropItem(Snappy, QGraphicsItem):
    def __init__(self, kind, w, h, rot=0):
        super().__init__()
        self.kind, self.w, self.h, self.rot = kind, w, h, rot
        self.setFlags(ENV_FLAGS)
        self.setZValue(4)
        self.setTransformOriginPoint(w / 2, h / 2)
        self.setRotation(rot)

    def boundingRect(self):
        return QRectF(-4, -4, self.w + 8, self.h + 8)

    def shape(self):
        p = QPainterPath()
        p.addRect(0, 0, self.w, self.h)
        return p

    def to_dict(self):
        return {"type": "prop", "kind": self.kind, "w": self.w, "h": self.h, "rot": self.rot,
                "x": self.pos().x(), "y": self.pos().y()}

    def paint(self, p, option, widget=None):
        on_tv = widget is not None and widget.property("player_view")
        if on_tv and hidden_in_fog(self):
            return
        p.setRenderHint(QPainter.Antialiasing)
        asset = get_prop_asset(self.kind)
        if isinstance(asset, QSvgRenderer) and asset.isValid():
            asset.render(p, QRectF(0, 0, self.w, self.h))
        elif isinstance(asset, QPixmap) and not asset.isNull():
            p.drawPixmap(QRectF(0, 0, self.w, self.h).toRect(), asset)
        else:
            p.setBrush(QColor("#888888"))
            p.setPen(QPen(QColor("#222222"), 2))
            p.drawRect(QRectF(0, 0, self.w, self.h))
        if self.isSelected() and not on_tv:
            pen = QPen(QColor("#f59e0b"), 2, Qt.DashLine)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(0, 0, self.w, self.h))


class RevealItem(TerrainItem):
    def __init__(self, pts, mode="brush", width_ft=20):
        self._outline = QPainterPath()
        super().__init__(pts, "Grass", mode, width_ft)
        self.setZValue(-8)

    def rebuild(self):
        super().rebuild()
        self.setBrush(Qt.NoBrush)
        self._outline = self.shape().simplified()

    def add_point(self, p):
        super().add_point(p)
        self._outline = self.shape().simplified()

    def area(self):
        return self._outline.translated(self.pos())

    def to_dict(self):
        d = super().to_dict()
        d["type"] = "reveal"
        return d

    def paint(self, p, option, widget=None):
        if widget is not None and widget.property("player_view"):
            return
        pen = QPen(QColor("#22d3ee"), 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(QColor(34, 211, 238, 28))
        p.drawPath(self._outline)


class PlayerFrame(QGraphicsRectItem):
    def __init__(self, on_move):
        super().__init__(0, 0, 1000, 600)
        self.on_move = on_move
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)

    def margin(self):
        return 10 / max(Zoom.dm, 1e-9)

    def refresh(self):
        self.prepareGeometryChange()
        self.update()

    def set_view_rect(self, r):
        self.prepareGeometryChange()
        self.setRect(0, 0, r.width(), r.height())
        self.setPos(r.topLeft())

    def boundingRect(self):
        m = self.margin()
        return self.rect().adjusted(-m, -m, m, m)

    def shape(self):
        m = self.margin()
        outer, inner = QPainterPath(), QPainterPath()
        outer.addRect(self.rect().adjusted(-m, -m, m, m))
        inner.addRect(self.rect().adjusted(m, m, -m, -m))
        return outer.subtracted(inner)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.on_move()
        return super().itemChange(change, value)

    def paint(self, p, option, widget=None):
        if widget is not None and widget.property("player_view"):
            return
        r = self.rect()
        pen = QPen(QColor("#22d3ee"), 2.5, Qt.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        hs = 6 / max(Zoom.dm, 1e-9)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#22d3ee"))
        for cx, cy in ((r.left(), r.top()), (r.right(), r.top()), (r.left(), r.bottom()), (r.right(), r.bottom())):
            p.drawRect(QRectF(cx - hs, cy - hs, hs * 2, hs * 2))


def item_from_dict(d):
    t = d["type"]
    if t == "token":
        it = TokenItem(
            d["name"], d["initials"], d["color"], d["size"], d.get("player", False),
            d.get("vision_mod", 0), d.get("statuses", []), d.get("aura_ft", 0),
            d.get("aura_color", "#3b82f6"), d.get("image_path", ""),
            d.get("ruleset", ""), d.get("category", ""),
            d.get("profile_name", ""), d.get("profile", {})
        )
    elif t == "building":
        it = BuildingItem(d["kind"], d["w"], d["h"], d.get("label", ""), d.get("interior_done", False))
    elif t == "road":
        it = RoadItem([QPointF(x, y) for x, y in d["pts"]], d["style"],
                      d["width_ft"] if "width_ft" in d else d["width"] * 5)
    elif t == "fence":
        it = FenceItem([QPointF(x, y) for x, y in d["pts"]], d["style"], d.get("width") or 1)
    elif t == "doorwall":
        it = DoorWallItem([QPointF(x, y) for x, y in d["pts"]], kind=d.get("kind", "door"),
                          is_open=d.get("is_open", False), is_door=d.get("is_door"))
    elif t == "prop":
        it = PropItem(d["kind"], d["w"], d["h"], d.get("rot", 0))
    elif t == "reveal":
        it = RevealItem([QPointF(x, y) for x, y in d["pts"]], d["mode"], d["width_ft"])
    elif t == "terrain":
        it = TerrainItem([QPointF(x, y) for x, y in d["pts"]], d["terrain"], d["mode"], d["width_ft"])
    elif t == "underlay":
        it = UnderlayItem(d["path"], d["w"], d["h"], d.get("opacity", 1.0))
    else:
        it = StrokeItem([QPointF(x, y) for x, y in d["pts"]], d["color"], d["width"], d.get("fill", False))
    it.setPos(d["x"], d["y"])
    return it


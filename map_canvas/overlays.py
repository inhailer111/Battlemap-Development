import math
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF, QUndoCommand,
)
from core.config import UNITS_PER_FT
from core.math_utils import Snap, fmt_len, measure_distance_ft

# ----------------------------------------------------------------------------- pointer, ruler, AoE & whiteboard
class Pointer:
    laser = False
    dm = None
    tv = None


class Ruler:
    active = False
    start = None
    end = None


class Template:
    shape = "Circle"
    size_ft = 20
    color = QColor("#ef4444")
    active = False
    start = None
    end = None


class Chalk:
    mode = "Pen"
    color = QColor("#ef4444")
    width = 4
    strokes = []
    cur = None


def seg_dist(p, a, b):
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length2 = dx * dx + dy * dy
    t = 0 if length2 == 0 else max(0, min(1, ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / length2))
    return math.hypot(p.x() - (a.x() + t * dx), p.y() - (a.y() + t * dy))


def stroke_near(st, pt, r):
    pts = st["pts"]
    if st["mode"] == "Circle":
        rect = QRectF(pts[0], pts[1]).normalized()
        c = rect.center()
        a, b = max(rect.width() / 2, 1e-6), max(rect.height() / 2, 1e-6)
        d = math.hypot((pt.x() - c.x()) / a, (pt.y() - c.y()) / b)
        return abs(d - 1) * min(a, b) <= r
    if len(pts) == 1:
        return math.hypot(pt.x() - pts[0].x(), pt.y() - pts[0].y()) <= r
    return any(seg_dist(pt, pts[i], pts[i + 1]) <= r for i in range(len(pts) - 1))


def chalk_begin(pt, z):
    if Chalk.mode == "Erase":
        chalk_move(pt, z)
        return
    two = Chalk.mode in ("Circle", "Arrow")
    Chalk.cur = {"mode": Chalk.mode, "color": QColor(Chalk.color), "width": Chalk.width,
                 "pts": [QPointF(pt), QPointF(pt)] if two else [QPointF(pt)]}
    Chalk.strokes.append(Chalk.cur)


def chalk_move(pt, z):
    if Chalk.mode == "Erase":
        r = 14 / z
        Chalk.strokes[:] = [st for st in Chalk.strokes if not stroke_near(st, pt, r)]
        return
    cur = Chalk.cur
    if cur is None:
        return
    if cur["mode"] in ("Circle", "Arrow"):
        cur["pts"][1] = QPointF(pt)
    elif (pt - cur["pts"][-1]).manhattanLength() * z >= 2:
        cur["pts"].append(QPointF(pt))


def chalk_end():
    Chalk.cur = None


def draw_chalk(view, p):
    if not Chalk.strokes:
        return
    z = view.transform().m11()
    p.setRenderHint(QPainter.Antialiasing)
    for st in Chalk.strokes:
        col, w = QColor(st["color"]), st["width"]
        if st["mode"] == "Highlighter":
            col.setAlpha(110)
            w *= 3
        pen = QPen(col, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        pts = st["pts"]
        if st["mode"] == "Circle":
            p.drawEllipse(QRectF(pts[0], pts[1]).normalized())
        elif st["mode"] == "Arrow":
            a, b = pts
            p.drawLine(a, b)
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            head = 18 / z
            for da in (2.6, -2.6):
                p.drawLine(b, QPointF(b.x() + head * math.cos(ang + da), b.y() + head * math.sin(ang + da)))
        elif len(pts) == 1:
            p.drawPoint(pts[0])
        else:
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.drawPath(path)


def draw_ruler_and_template(view, p):
    z = view.transform().m11()
    p.setRenderHint(QPainter.Antialiasing)
    if Ruler.active and Ruler.start is not None and Ruler.end is not None:
        a, b = Ruler.start, Ruler.end
        pen = QPen(QColor("#f59e0b"), 3, Qt.DashLine, Qt.RoundCap)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.drawLine(a, b)
        p.setBrush(QColor("#f59e0b"))
        p.setPen(Qt.NoPen)
        r_dot = 5 / z
        p.drawEllipse(a, r_dot, r_dot)
        p.drawEllipse(b, r_dot, r_dot)

        dist_ft = measure_distance_ft(a, b)
        sq = dist_ft / (Snap.step / UNITS_PER_FT)
        label = f"{dist_ft:,.0f} ft  ({sq:.1f} sq)" if dist_ft < 2640 else fmt_len(dist_ft * UNITS_PER_FT)
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        p.save()
        p.translate(mid)
        p.scale(1 / z, 1 / z)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(13)
        p.setFont(font)
        fm = QFontMetricsF(font)
        tw = fm.horizontalAdvance(label) + 16
        box = QRectF(-tw / 2, -26, tw, 22)
        p.setBrush(QColor(20, 23, 31, 235))
        p.setPen(QPen(QColor("#f59e0b"), 1.5))
        p.drawRoundedRect(box, 6, 6)
        p.setPen(QColor("#fef3c7"))
        p.drawText(box, Qt.AlignCenter, label)
        p.restore()

    if Template.active and Template.start is not None and Template.end is not None:
        a, b = Template.start, Template.end
        radius_u = QLineF(a, b).length()
        if radius_u < 1:
            radius_u = Template.size_ft * UNITS_PER_FT
        fill = QColor(Template.color)
        fill.setAlpha(65)
        edge = QColor(Template.color)
        edge.setAlpha(220)
        pen = QPen(edge, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(fill)

        sh = Template.shape
        if sh == "Circle":
            p.drawEllipse(a, radius_u, radius_u)
        elif sh == "Cube":
            side = radius_u
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            p.save()
            p.translate(a)
            p.rotate(math.degrees(ang))
            p.drawRect(QRectF(0, -side / 2, side, side))
            p.restore()
        elif sh == "Cone":
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            half_ang = math.radians(26.565)
            p1 = QPointF(a.x() + radius_u * math.cos(ang - half_ang), a.y() + radius_u * math.sin(ang - half_ang))
            p2 = QPointF(a.x() + radius_u * math.cos(ang + half_ang), a.y() + radius_u * math.sin(ang + half_ang))
            p.drawPolygon(QPolygonF([a, p1, p2]))
        elif sh == "Line":
            ang = math.atan2(b.y() - a.y(), b.x() - a.x())
            w_u = 5 * UNITS_PER_FT
            p.save()
            p.translate(a)
            p.rotate(math.degrees(ang))
            p.drawRect(QRectF(0, -w_u / 2, radius_u, w_u))
            p.restore()

        label = f"{sh}: {fmt_len(radius_u)}"
        p.save()
        p.translate(b)
        p.scale(1 / z, 1 / z)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(12)
        p.setFont(font)
        fm = QFontMetricsF(font)
        tw = fm.horizontalAdvance(label) + 14
        box = QRectF(10, -10, tw, 20)
        p.setBrush(QColor(20, 23, 31, 230))
        p.setPen(QPen(edge, 1.5))
        p.drawRoundedRect(box, 5, 5)
        p.setPen(QColor("#ffffff"))
        p.drawText(box, Qt.AlignCenter, label)
        p.restore()


def draw_pointer(view, p):
    pos = Pointer.dm if (Pointer.laser and Pointer.dm is not None) else Pointer.tv
    if pos is None:
        return
    z = view.transform().m11()
    p.save()
    p.translate(pos)
    p.scale(1 / z, 1 / z)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(255, 255, 255, 230), 3))
    p.setBrush(QColor(239, 68, 68, 215))
    p.drawEllipse(QPointF(0, 0), 11, 11)
    p.setPen(QPen(QColor(239, 68, 68, 130), 2))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(0, 0), 21, 21)
    p.restore()


# ----------------------------------------------------------------------------- undo commands
class AddCommand(QUndoCommand):
    def __init__(self, scene, items, text="Add"):
        super().__init__(text)
        self.sc, self.items = scene, list(items)

    def _add(self):
        for it in self.items:
            if it.scene() is None:
                self.sc.addItem(it)

    def _remove(self):
        for it in self.items:
            if it.scene() is self.sc:
                self.sc.removeItem(it)

    def redo(self):
        self._add()

    def undo(self):
        self._remove()


class RemoveCommand(AddCommand):
    def __init__(self, scene, items):
        super().__init__(scene, items, "Delete")

    def redo(self):
        self._remove()

    def undo(self):
        self._add()


class MoveCommand(QUndoCommand):
    def __init__(self, moves):
        super().__init__("Move")
        self.moves = moves

    def redo(self):
        for it, _, new in self.moves:
            it.setPos(new)

    def undo(self):
        for it, old, _ in self.moves:
            it.setPos(old)


class EditTokenCommand(QUndoCommand):
    def __init__(self, item, old, new):
        super().__init__("Edit")
        self.item, self.old, self.new = item, old, new

    def redo(self):
        self.item.set_props(self.new)

    def undo(self):
        self.item.set_props(self.old)



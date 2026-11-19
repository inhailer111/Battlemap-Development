import math
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPolygonF
from core.config import UNITS_PER_FT
from map_canvas.canvas_items import (
    TokenItem, BuildingItem, FenceItem, DoorWallItem, PropItem, StrokeItem, RevealItem,
)

# ----------------------------------------------------------------------------- vision / fog of war
class Vision:
    night = False
    fog_on = True
    show_on_dm = True
    fog_alpha = 140
    remember = True
    day_ft, night_ft = 200, 40
    players = 0
    visible = QPainterPath()
    show = QPainterPath()
    seen = QPainterPath()
    explored = QPainterPath()
    explored_polys = []
    last_pos = {}
    seen_owners = set()
    shown_ids = set()


def vision_range_ft(tok):
    return max(10, (Vision.night_ft if Vision.night else Vision.day_ft) + tok.vision_mod)


def poly_path(pts):
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    path.closeSubpath()
    return path


def reset_explored(polys=()):
    Vision.explored = QPainterPath()
    Vision.explored_polys = []
    Vision.last_pos = {}
    Vision.seen_owners = set()
    for flat in polys:
        pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
        Vision.explored_polys.append(pts)
        Vision.explored = Vision.explored.united(poly_path(pts))


def wall_segments(item):
    if isinstance(item, BuildingItem):
        if item.has_player_inside:
            return None
        x, y = item.pos().x(), item.pos().y()
        pts = [(x, y), (x + item.w, y), (x + item.w, y + item.h), (x, y + item.h), (x, y)]
    elif isinstance(item, FenceItem) and item.style != "Wood":
        pts = [(p.x() + item.pos().x(), p.y() + item.pos().y()) for p in item.pts]
    elif isinstance(item, DoorWallItem) and item.blocks_vision():
        pts = [(p.x() + item.pos().x(), p.y() + item.pos().y()) for p in item.pts]
    else:
        return None
    return [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]


def segs_near(segs, c, R):
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    return min(xs) <= c.x() + R and max(xs) >= c.x() - R and min(ys) <= c.y() + R and max(ys) >= c.y() - R


def visibility_polygon(cx, cy, R, walls):
    segs = [(s, owner) for segments, owner in walls for s in segments]
    two_pi = 2 * math.pi
    angles = [two_pi * i / 90 for i in range(90)]
    if len(segs) < 400:
        for (x1, y1, x2, y2), _ in segs:
            for x, y in ((x1, y1), (x2, y2)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= R * R:
                    a = math.atan2(y - cy, x - cx)
                    angles += [(a - 1e-4) % two_pi, a % two_pi, (a + 1e-4) % two_pi]
    angles.sort()
    pts, hits = [], set()
    for a in angles:
        dx, dy = math.cos(a), math.sin(a)
        best, owner_hit = R, None
        for (x1, y1, x2, y2), owner in segs:
            sx, sy = x2 - x1, y2 - y1
            den = dx * sy - dy * sx
            if abs(den) < 1e-12:
                continue
            t = ((x1 - cx) * sy - (y1 - cy) * sx) / den
            if 1e-6 < t < best:
                u = ((x1 - cx) * dy - (y1 - cy) * dx) / den
                if -1e-9 <= u <= 1 + 1e-9:
                    best, owner_hit = t, owner
        if owner_hit is not None:
            hits.add(owner_hit)
        pts.append((cx + dx * best, cy + dy * best))
    return pts, hits


def owner_shape(owner):
    if isinstance(owner, BuildingItem):
        path = QPainterPath()
        path.addRect(QRectF(owner.pos().x(), owner.pos().y(), owner.w, owner.h))
        return path
    return owner.shape().translated(owner.pos())


def hidden_in_fog(item):
    if not Vision.fog_on:
        return False
    if isinstance(item, BuildingItem) or (isinstance(item, FenceItem) and item.style != "Wood"):
        return id(item) not in Vision.shown_ids
    if isinstance(item, (PropItem, DoorWallItem)):
        scene = item.scene()
        if scene is not None:
            ipos = item.sceneBoundingRect().center()
            for b in scene.items():
                if isinstance(b, BuildingItem):
                    if QRectF(b.pos().x(), b.pos().y(), b.w, b.h).contains(ipos):
                        if not b.has_player_inside:
                            return True
        return not Vision.show.intersects(item.sceneBoundingRect())
    if isinstance(item, (StrokeItem, FenceItem)):
        return not Vision.show.intersects(item.sceneBoundingRect())
    return False


def record_explored(tok, c, R, pts, hits):
    last = Vision.last_pos.get(id(tok))
    if last is not None and QLineF(last, c).length() < R / 2:
        return
    if len(Vision.explored_polys) >= 400:
        return
    Vision.last_pos[id(tok)] = QPointF(c)
    simple = pts[::3] if len(pts) > 60 else pts
    Vision.explored_polys.append(simple)
    Vision.explored = Vision.explored.united(poly_path(simple))
    for owner in hits:
        if isinstance(owner, BuildingItem) and id(owner) not in Vision.seen_owners:
            Vision.seen_owners.add(id(owner))
            x, y = owner.pos().x(), owner.pos().y()
            box = [(x, y), (x + owner.w, y), (x + owner.w, y + owner.h), (x, y + owner.h)]
            Vision.explored_polys.append(box)
            Vision.explored = Vision.explored.united(poly_path(box))


def update_vision(scene):
    tokens, reveals, walls = [], [], []
    for it in scene.items():
        if isinstance(it, TokenItem):
            if it.player:
                tokens.append(it)
        elif isinstance(it, RevealItem):
            reveals.append(it)
        else:
            segs = wall_segments(it)
            if segs:
                walls.append((segs, it))
    Vision.players = len(tokens)
    visible, show = QPainterPath(), QPainterPath()
    shown = set()
    for tok in tokens:
        c = tok.center()
        R = vision_range_ft(tok) * UNITS_PER_FT
        near = [(segs, owner) for segs, owner in walls if segs_near(segs, c, R)]
        pts, hits = visibility_polygon(c.x(), c.y(), R, near)
        visible = visible.united(poly_path(pts))
        for owner in hits:
            show = show.united(owner_shape(owner))
            shown.add(id(owner))
        if Vision.remember:
            record_explored(tok, c, R, pts, hits)
    for r in reveals:
        area = r.area()
        area.setFillRule(Qt.WindingFill)
        visible = visible.united(area)
        for _segs, owner in walls:
            if area.intersects(owner.sceneBoundingRect()):
                shown.add(id(owner))
    Vision.visible, Vision.show = visible, show.united(visible)
    Vision.seen = Vision.explored.united(Vision.show) if Vision.remember else Vision.show
    Vision.shown_ids = shown


def ring(rect, hole):
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    path.addRect(rect)
    path.addPath(hole)
    return path


def draw_overlay(view, p, rect, is_player):
    if Vision.night:
        p.fillRect(rect, QColor(10, 20, 70, 130 if is_player else 95))
    if not Vision.fog_on or not (is_player or Vision.show_on_dm):
        return
    r, g, b = 5, 6, 10
    if is_player:
        fog = Vision.fog_alpha
        mem = int(fog * 150 / 255)
        top = int(round(255 * (1 - (1 - fog / 255) / (1 - mem / 255))))
    else:
        fog, mem, top = 100, 60, 100
    if Vision.remember:
        p.fillPath(ring(rect, Vision.show), QBrush(QColor(r, g, b, mem)))
        p.fillPath(ring(rect, Vision.seen), QBrush(QColor(r, g, b, top)))
    else:
        p.fillPath(ring(rect, Vision.show), QBrush(QColor(r, g, b, fog)))
    if is_player and Vision.players == 0 and Vision.visible.isEmpty():
        p.save()
        p.resetTransform()
        p.setPen(QColor("#9ca3af"))
        p.drawText(view.viewport().rect(), Qt.AlignCenter,
                   "No player tokens yet.\nMark a token as a Player token to give the party vision.")
        p.restore()



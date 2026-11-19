import math
from PySide6.QtCore import QPointF
from core.config import (
    CELL, UNITS_PER_FT, LEVELS, MIN_SQUARE_PX, JUMP_PX, ZOOM_MIN, ZOOM_MAX,
    Zoom, Tokens,
)

class Snap:
    on = True          # snap-to-grid enabled
    step = CELL        # current grid step in scene units (follows the zoom level)
    dragging = False   # true only while the mouse is dragging items in Select mode
    grid_type = "square"  # "square", "hex_pointy", "hex_flat", "none"
    diag_rule = "5e"      # "5e" (Chebyshev), "pf" (1-2-1-2 alternating), "euclidean"


def level_for_zoom(z):
    for i, (_, ft) in enumerate(LEVELS):
        if ft * UNITS_PER_FT * z >= MIN_SQUARE_PX:
            return i
    return len(LEVELS) - 1


def fmt_len(units):
    ft = units / UNITS_PER_FT
    return f"{ft / 5280:.1f} mi" if ft >= 2640 else f"{ft:,.0f} ft"


def measure_distance_ft(a, b):
    """Calculate tabletop distance in feet between two QPointF scene coordinates using active diagonal rule."""
    dx_ft = abs(b.x() - a.x()) / UNITS_PER_FT
    dy_ft = abs(b.y() - a.y()) / UNITS_PER_FT
    if Snap.diag_rule == "euclidean" or Snap.grid_type in ("hex_pointy", "hex_flat", "none"):
        return math.hypot(dx_ft, dy_ft)
    step_ft = Snap.step / UNITS_PER_FT
    sx, sy = dx_ft / step_ft, dy_ft / step_ft
    mn, mx = min(sx, sy), max(sx, sy)
    if Snap.diag_rule == "pf":
        # Alternating 1-2-1-2 diagonal cost
        return (mx + math.floor(mn / 2.0)) * step_ft
    # 5e / Chebyshev (1-1-1 diagonal cost)
    return mx * step_ft


def snap_point_to_grid(p):
    """Snap a QPointF to the active grid geometry (square, pointy hex, or flat hex)."""
    if not Snap.on or Snap.grid_type == "none":
        return p
    g = Snap.step
    if Snap.grid_type == "square":
        return QPointF(round(p.x() / g) * g, round(p.y() / g) * g)
    if Snap.grid_type == "hex_pointy":
        R = g / math.sqrt(3)
        q = (math.sqrt(3) / 3 * p.x() - 1 / 3 * p.y()) / R
        r = (2 / 3 * p.y()) / R
        rq, rr, rs = _cube_round(q, r, -q - r)
        cx = R * math.sqrt(3) * (rq + rr / 2.0)
        cy = R * 1.5 * rr
        return QPointF(cx, cy)
    if Snap.grid_type == "hex_flat":
        R = g / math.sqrt(3)
        q = (2 / 3 * p.x()) / R
        r = (-1 / 3 * p.x() + math.sqrt(3) / 3 * p.y()) / R
        rq, rr, rs = _cube_round(q, r, -q - r)
        cx = R * 1.5 * rq
        cy = R * math.sqrt(3) * (rr + rq / 2.0)
        return QPointF(cx, cy)
    return p


def _cube_round(x, y, z):
    rx, ry, rz = round(x), round(y), round(z)
    xd, yd, zd = abs(rx - x), abs(ry - y), abs(rz - z)
    if xd > yd and xd > zd:
        rx = -ry - rz
    elif yd > zd:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, ry, rz



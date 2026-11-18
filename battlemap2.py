#!/usr/bin/env python3
"""InfinityGrid Tabletop - a universal, nearly infinite grid drawing app for tabletop RPG maps.

Setup (Ubuntu):
    sudo apt install python3-venv libxcb-cursor0
    python3 -m venv .venv && source .venv/bin/activate
    pip install PySide6
Run:
    python3 battlemap.py [optional_map_file.json]
"""
import json
import math
import random
import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF, QLineF, QTimer, QSize, QByteArray
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QFont, QFontMetricsF, QIcon,
                           QKeySequence, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QUndoCommand,
                           QUndoStack, QGuiApplication, QPolygonF, QImage)
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                               QDockWidget, QFileDialog, QFormLayout, QGraphicsItem,
                               QGraphicsPathItem, QGraphicsScene, QGraphicsView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget, QFrame, QGraphicsRectItem,
                               QStyle, QStyleOptionGraphicsItem, QHBoxLayout, QSlider, QStackedWidget,
                               QGroupBox, QScrollArea, QMenu)
from PySide6.QtSvg import QSvgRenderer

try:
    import worldgen2 as worldgen
except ImportError:
    import worldgen   # fallback if saved as worldgen.py

UNITS_PER_FT = 10         # 1 scene unit = 0.1 ft
CELL = 5 * UNITS_PER_FT   # the base 5 ft square (tokens and old maps are sized in these)
HALF = 20_000_000         # scene extends +/- this far (about 400,000 squares each way)
LIGHT_PEN, DARK_PEN = "#1f2937", "#e5e7eb"

# road style -> (colour, dashed centre line); fence style -> (colour, thickness)
ROAD_STYLES = {"Paved": ("#6b7280", True), "Cobblestone": ("#a8977a", False), "Dirt": ("#9a7b4f", False)}
BUILDING_KINDS = {"House": "#b45f3c", "Shop": "#4f6d8f", "Inn": "#8a6a3b", "Barn": "#9c3d3d",
                  "Warehouse": "#7b8088"}
STANDARD_BUILDING_FT = {
    "House": (35, 30),
    "Shop": (45, 35),
    "Inn": (60, 45),
    "Barn": (50, 35),
    "Warehouse": (80, 50),
}
FENCE_STYLES = {"Wood": ("#7a4f2a", 3), "Stone wall": ("#7f7f7f", 10), "Hedge": ("#3f7d3a", 14)}

STATUS_COLORS = {
    "Bloodied": "#ef4444",
    "Poisoned": "#22c55e",
    "Stunned": "#eab308",
    "Prone": "#a855f7",
    "Concentrating": "#3b82f6",
    "Hidden": "#9ca3af",
}

APP_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #181a20;
    color: #e5e7eb;
}
QMenuBar {
    background-color: #14161b;
    color: #d1d5db;
    border-bottom: 1px solid #2a2e39;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #262a35;
    border-radius: 4px;
}
QMenu {
    background-color: #1e2129;
    color: #e5e7eb;
    border: 1px solid #323746;
    padding: 4px;
}
QMenu::item {
    padding: 5px 24px 5px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QToolBar {
    background-color: #1b1e26;
    border-bottom: 1px solid #2a2e39;
    spacing: 3px;
    padding: 4px 6px;
}
QToolBar::separator {
    background-color: #2f3442;
    width: 1px;
    margin: 4px 5px;
}
QToolButton {
    background-color: transparent;
    color: #d1d5db;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 11px;
}
QToolButton:hover {
    background-color: #272b36;
    border-color: #363c4c;
}
QToolButton:checked {
    background-color: #1d4ed8;
    border-color: #3b82f6;
    color: #ffffff;
}
QDockWidget {
    color: #e5e7eb;
    font-weight: bold;
}
QDockWidget::title {
    background-color: #14161b;
    padding: 7px 10px;
    border-bottom: 1px solid #2a2e39;
    border-top: 1px solid #2a2e39;
}
QDockWidget > QWidget, QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #1b1e26;
    color: #e5e7eb;
}
QGroupBox {
    background-color: #212530;
    border: 1px solid #2e3443;
    border-radius: 7px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
    color: #93c5fd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    background-color: #212530;
}
QLabel {
    color: #d1d5db;
}
QPushButton {
    background-color: #292e3c;
    color: #f3f4f6;
    border: 1px solid #3b4254;
    border-radius: 5px;
    padding: 5px 10px;
}
QPushButton:hover {
    background-color: #343b4d;
    border-color: #4f5870;
}
QPushButton:pressed {
    background-color: #1f2430;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #14171f;
    color: #f3f4f6;
    border: 1px solid #323848;
    border-radius: 5px;
    padding: 4px 7px;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #3b82f6;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QListWidget {
    background-color: #14171f;
    color: #f3f4f6;
    border: 1px solid #323848;
    border-radius: 5px;
    padding: 2px;
}
QListWidget::item {
    padding: 4px 6px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QCheckBox {
    color: #d1d5db;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid #454d63;
    background-color: #14171f;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #14171f;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #3b82f6;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QTabBar::tab {
    background-color: #14161b;
    color: #9ca3af;
    padding: 6px 12px;
    border: 1px solid #2a2e39;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}
QTabBar::tab:selected {
    background-color: #1b1e26;
    color: #ffffff;
    font-weight: bold;
}
QStatusBar {
    background-color: #14161b;
    color: #9ca3af;
    border-top: 1px solid #2a2e39;
}
QStatusBar QLabel {
    background-color: #212530;
    color: #d1d5db;
    border: 1px solid #2e3443;
    border-radius: 4px;
    padding: 2px 8px;
    margin: 1px 2px;
    font-size: 11px;
}
"""

TOOL_ICONS = {
    "select": '<path d="M5 3l12 9-5.5 1.2L14 19l-2.3 1-2.5-5.8L5 18z" fill="#e5e7eb"/>',
    "eraser": '<path d="M15.5 4.5l4 4L10 18H5.5l-2-2 12-11.5zM6.5 16H9l6.5-6.5-2-2L5 16h1.5z" fill="#e5e7eb"/><path d="M12 18h8" stroke="#e5e7eb" stroke-width="2" stroke-linecap="round"/>',
    "measure": '<path d="M3 17L17 3l4 4L7 21H3v-4zm5-5l2 2m3-3l2 2m-8 2l2 2" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" fill="none"/>',
    "template": '<circle cx="12" cy="12" r="8" fill="rgba(239,68,68,0.28)" stroke="#ef4444" stroke-width="2" stroke-dasharray="3 2"/><circle cx="12" cy="12" r="2" fill="#ef4444"/>',
    "pen": '<path d="M15.2 3.8l5 5L8 21H3v-5L15.2 3.8zm-1.4 2.8L5 15.4V19h3.6l8.8-8.8-3.6-3.6z" fill="#e5e7eb"/>',
    "line": '<line x1="4" y1="20" x2="20" y2="4" stroke="#e5e7eb" stroke-width="2.4" stroke-linecap="round"/><circle cx="4" cy="20" r="2.2" fill="#3b82f6"/><circle cx="20" cy="4" r="2.2" fill="#3b82f6"/>',
    "rect": '<rect x="4" y="5" width="16" height="14" rx="1.5" fill="none" stroke="#e5e7eb" stroke-width="2.2"/>',
    "chalk": '<path d="M4 17c3-5 6 3 9-3s4 4 7-1" fill="none" stroke="#22d3ee" stroke-width="2.4" stroke-linecap="round"/><path d="M16 4l4 4-8 8H8v-4l8-8z" fill="#e5e7eb"/>',
    "terrain": '<path d="M2 19l6-10 4.5 6.5L16 11l6 8H2z" fill="#e5e7eb"/><circle cx="17.5" cy="6.5" r="2.2" fill="#e5e7eb"/>',
    "road": '<path d="M7 3L3 21h18L17 3H7zm5 2v3m0 3v3m0 3v3" stroke="#e5e7eb" stroke-width="2" stroke-linecap="round" fill="none"/>',
    "building": '<path d="M3 10.5L12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5z" fill="#e5e7eb"/>',
    "fence": '<path d="M5 5v14M12 5v14M19 5v14M3 9h18M3 15h18" stroke="#e5e7eb" stroke-width="2.2" stroke-linecap="round"/>',
    "door": '<rect x="6" y="3" width="12" height="18" rx="1" fill="none" stroke="#f59e0b" stroke-width="2.2"/><circle cx="15" cy="12" r="1.5" fill="#f59e0b"/>',
    "prop": '<rect x="3" y="8" width="18" height="8" rx="3" fill="#e5e7eb"/><circle cx="7" cy="17" r="2.2" fill="#93c5fd"/><circle cx="17" cy="17" r="2.2" fill="#93c5fd"/>',
    "token": '<circle cx="12" cy="8" r="4" fill="#e5e7eb"/><path d="M5 20c0-3.8 3.1-6.5 7-6.5s7 2.7 7 6.5" fill="#e5e7eb"/>',
    "reveal": '<path d="M2 12s3.8-6 10-6 10 6 10 6-3.8 6-10 6-10-6-10-6z" fill="none" stroke="#22d3ee" stroke-width="2.2"/><circle cx="12" cy="12" r="3" fill="#22d3ee"/>',
    "night": '<path d="M19.5 14.5A7.5 7.5 0 0 1 9.5 4.5a7.5 7.5 0 1 0 10 10z" fill="#93c5fd"/>',
    "laser": '<circle cx="12" cy="12" r="4" fill="#ef4444"/><circle cx="12" cy="12" r="8" fill="none" stroke="#ef4444" stroke-width="1.8" stroke-dasharray="3 2"/>',
}


def make_icon(key):
    body = TOOL_ICONS.get(key, "")
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'
    pm = QPixmap(24, 24)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
    p.end()
    return QIcon(pm)


class Snap:
    on = True          # snap-to-grid enabled
    step = CELL        # current grid step in scene units (follows the zoom level)
    dragging = False   # true only while the mouse is dragging items in Select mode
    grid_type = "square"  # "square", "hex_pointy", "hex_flat", "none"
    diag_rule = "5e"      # "5e" (Chebyshev), "pf" (1-2-1-2 alternating), "euclidean"


# (label, feet per grid square): the first three are the play scales, the rest are zoom-out levels
LEVELS = [("5 ft", 5), ("10 ft", 10), ("20 ft", 20), ("100 ft", 100), ("500 ft", 500),
          ("1 mile", 5280), ("5 miles", 26400)]
MIN_SQUARE_PX = 24     # the finest scale whose squares are at least this big on screen is used
JUMP_PX = 36           # on-screen square size when jumping to a scale from the toolbar
ZOOM_MIN, ZOOM_MAX = 3e-5, 8.0

TERRAIN = {"Grass": "#9cc77a", "Forest": "#3f7d4a", "Water": "#5b9bd5", "Sand": "#e3d3a1",
           "Farmland": "#cdbb6f", "Scrub": "#c2b280", "Rock": "#8d8d8d", "Snow": "#f1f5f9"}

BASE_DIR = Path(__file__).resolve().parent
MAPS_DIR, ASSETS_DIR = BASE_DIR / "maps", BASE_DIR / "assets"
PROPS_DIR, TOKENS_DIR = ASSETS_DIR / "props", ASSETS_DIR / "tokens"


class Zoom:
    dm = 1.0   # the DM view's current zoom (used to size the player-frame grab handle)
    tv = 0.0   # the player view's current zoom (0 while the player screen is closed)


class Tokens:
    min_dm = 28   # smallest a token is drawn on the DM screen, in pixels
    min_tv = 44   # smallest a token is drawn on the player screen, in pixels


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
        # Pointy-top hexes with flat-to-flat width = g (radius R = g / sqrt(3))
        R = g / math.sqrt(3)
        q = (math.sqrt(3) / 3 * p.x() - 1 / 3 * p.y()) / R
        r = (2 / 3 * p.y()) / R
        rq, rr, rs = _cube_round(q, r, -q - r)
        cx = R * math.sqrt(3) * (rq + rr / 2.0)
        cy = R * 1.5 * rr
        return QPointF(cx, cy)
    if Snap.grid_type == "hex_flat":
        # Flat-top hexes with flat-to-flat height = g (radius R = g / sqrt(3))
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


GENRE_CATEGORIES = {
    "apocalypse": [
        {"name": "Hero", "color": "#3b82f6", "size": 1, "player": True, "numbered": False},
        {"name": "Ally", "color": "#22c55e", "size": 1, "player": False, "numbered": False},
        {"name": "NPC", "color": "#eab308", "size": 1, "player": False, "numbered": False},
        {"name": "Walker", "color": "#7c8a5a", "size": 1, "player": False, "numbered": True},
        {"name": "Runner", "color": "#c2410c", "size": 1, "player": False, "numbered": True},
        {"name": "Brute", "color": "#7f1d1d", "size": 2, "player": False, "numbered": True},
        {"name": "Raider", "color": "#ef4444", "size": 1, "player": False, "numbered": True},
        {"name": "Object", "color": "#6b7280", "size": 1, "player": False, "numbered": False},
    ],
    "fantasy": [
        {"name": "Adventurer", "color": "#3b82f6", "size": 1, "player": True, "numbered": False},
        {"name": "Companion", "color": "#22c55e", "size": 1, "player": False, "numbered": False},
        {"name": "Townsfolk", "color": "#eab308", "size": 1, "player": False, "numbered": False},
        {"name": "Goblin", "color": "#4d7c0f", "size": 1, "player": False, "numbered": True},
        {"name": "Bandit", "color": "#dc2626", "size": 1, "player": False, "numbered": True},
        {"name": "Ogre", "color": "#7f1d1d", "size": 2, "player": False, "numbered": True},
        {"name": "Dragon", "color": "#991b1b", "size": 3, "player": False, "numbered": False},
        {"name": "Chest / Prop", "color": "#6b7280", "size": 1, "player": False, "numbered": False},
    ],
    "scifi": [
        {"name": "Runner", "color": "#06b6d4", "size": 1, "player": True, "numbered": False},
        {"name": "Contact", "color": "#22c55e", "size": 1, "player": False, "numbered": False},
        {"name": "Citizen", "color": "#eab308", "size": 1, "player": False, "numbered": False},
        {"name": "Sec-Drone", "color": "#f97316", "size": 1, "player": False, "numbered": True},
        {"name": "Cyborg", "color": "#ef4444", "size": 1, "player": False, "numbered": True},
        {"name": "Mech", "color": "#7f1d1d", "size": 2, "player": False, "numbered": True},
        {"name": "Turret", "color": "#64748b", "size": 1, "player": False, "numbered": True},
        {"name": "Terminal", "color": "#6b7280", "size": 1, "player": False, "numbered": False},
    ],
    "western": [
        {"name": "Posse", "color": "#3b82f6", "size": 1, "player": True, "numbered": False},
        {"name": "Deputy", "color": "#22c55e", "size": 1, "player": False, "numbered": False},
        {"name": "Townsfolk", "color": "#eab308", "size": 1, "player": False, "numbered": False},
        {"name": "Outlaw", "color": "#ef4444", "size": 1, "player": False, "numbered": True},
        {"name": "Gunslinger", "color": "#c2410c", "size": 1, "player": False, "numbered": True},
        {"name": "Mount / Horse", "color": "#854d0e", "size": 2, "player": False, "numbered": True},
        {"name": "Stagecoach", "color": "#713f12", "size": 3, "player": False, "numbered": False},
        {"name": "Barrel / Cover", "color": "#6b7280", "size": 1, "player": False, "numbered": False},
    ],
}
DEFAULT_CATEGORIES = GENRE_CATEGORIES["apocalypse"]
CATEGORY_FILE = ASSETS_DIR / "token_categories.json"


def load_categories():
    try:
        with open(CATEGORY_FILE) as f:
            cats = json.load(f)
        cats = [c for c in cats if isinstance(c, dict) and {"name", "color", "size"} <= c.keys()]
        if cats:
            return cats
    except (OSError, ValueError, TypeError):
        pass
    return [dict(c) for c in DEFAULT_CATEGORIES]


def save_categories(cats):
    try:
        ASSETS_DIR.mkdir(exist_ok=True)
        with open(CATEGORY_FILE, "w") as f:
            json.dump(cats, f, indent=2)
    except OSError:
        pass


def spiral_offsets(n):
    """The first n cell offsets of an outward square spiral: (0,0), (1,0), (1,1), (0,1), (-1,1), ..."""
    out, x, y, dx, dy = [], 0, 0, 1, 0
    seg, walked, turns = 1, 0, 0
    while len(out) < n:
        out.append((x, y))
        x, y = x + dx, y + dy
        walked += 1
        if walked == seg:
            walked = 0
            dx, dy = -dy, dx
            turns += 1
            if turns % 2 == 0:
                seg += 1
    return out


def swatch(button, color):
    button.setStyleSheet(
        f"background:{QColor(color).name()}; border:1px solid #6b7280; border-radius:4px; min-height:22px;"
    )


def auto_initials(name):
    words = re.findall(r"[^\W\d_]+", name)
    num = re.search(r"(\d+)\s*$", name)
    if not words:
        ini = ""
    elif len(words) == 1:
        ini = words[0][0].upper() if num else words[0][:2].capitalize()
    else:
        ini = (words[0][0] + words[1][0]).upper()
    return ini + (num.group(1) if num else "")


# ----------------------------------------------------------------------------- items
class PlayerSafe:
    """Mixin: never draw selection outlines on the player screen."""

    def paint(self, p, option, widget=None):
        if widget is not None and widget.property("player_view"):
            if hidden_in_fog(self):
                return
            option = QStyleOptionGraphicsItem(option)
            option.state &= ~QStyle.State_Selected
        super().paint(p, option, widget)


class Snappy:
    """Mixin: item positions snap to the grid while dragging."""

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and Snap.on and Snap.dragging:
            return snap_point_to_grid(value)
        return super().itemChange(change, value)


class UnderlayItem(QGraphicsItem):
    """Locked background battlemap image imported by the DM, calibrated to the grid."""

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
    """Freehand strokes, lines and rectangles (all stored as polylines)."""

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
    """A round character token with initials, optional custom image, aura, status dots, and label."""
    snap = True

    def __init__(self, name, initials, color, size=1, player=False, vision_mod=0,
                 statuses=None, aura_ft=0, aura_color="#3b82f6", image_path=""):
        super().__init__()
        self.name, self.initials, self.color, self.size = name, initials, QColor(color), size
        self.player, self.vision_mod = player, vision_mod
        self.statuses = list(statuses) if statuses else []
        self.aura_ft = int(aura_ft)
        self.aura_color = QColor(aura_color)
        self.image_path = image_path or ""
        self._pix = QPixmap(self.image_path) if self.image_path else QPixmap()
        self._D = self.enlarged()
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(10)

    def props(self):
        return {"name": self.name, "initials": self.initials, "color": self.color.name(), "size": self.size,
                "player": self.player, "vision_mod": self.vision_mod, "statuses": list(self.statuses),
                "aura_ft": self.aura_ft, "aura_color": self.aura_color.name(), "image_path": self.image_path}

    def set_props(self, d):
        self.prepareGeometryChange()
        self.name, self.initials, self.size = d["name"], d["initials"], d["size"]
        self.player, self.vision_mod = d.get("player", False), d.get("vision_mod", 0)
        self.color = QColor(d["color"])
        self.statuses = list(d.get("statuses", []))
        self.aura_ft = int(d.get("aura_ft", 0))
        self.aura_color = QColor(d.get("aura_color", "#3b82f6"))
        self.image_path = d.get("image_path", "")
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
        if (on_tv and Vision.fog_on and not self.player
                and not Vision.visible.contains(self.center())):
            return
        p.setRenderHint(QPainter.Antialiasing)
        d = self.size * CELL
        c = QPointF(d / 2, d / 2)

        # Draw Aura ring (if active)
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

        # Status condition dots along the top-right arc of the token
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
    """Base for roads and fences: a polyline stored as points."""
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
    """Interactive door, window, or wall segment:
    - Door: Closed blocks vision (amber); Open allows vision (green dashed). Click to toggle.
    - Window: Never blocks vision (cyan glass panes); Closed/Open state toggles shutter/opening.
    - Wall: Always blocks vision (invisible on player view, blue on DM view).
    """

    def __init__(self, pts, kind="door", is_open=False, is_door=None):
        super().__init__()
        self.pts = [QPointF(p) for p in pts]
        if is_door is not None and kind == "door":
            # Backwards compatibility with older saves that used is_door bool
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
        # Windows never block vision; walls always block; doors block when closed
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
            # Outer sill frame + bright cyan glass line (dashed if window is open)
            p.setPen(QPen(QColor("#1e293b"), 7, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(self.path())
            glass_style = Qt.DashLine if self.is_open else Qt.SolidLine
            p.setPen(QPen(QColor("#38bdf8"), 3.5, glass_style, Qt.RoundCap))
            p.drawPath(self.path())
        else:
            if on_tv:
                return   # invisible vision-blocking wall on player view (for underlay maps)
            p.setPen(QPen(QColor("#60a5fa"), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(self.path())
        if self.isSelected() and not on_tv:
            sel = QPen(QColor("#ffffff"), 2, Qt.DashLine)
            sel.setCosmetic(True)
            p.setPen(sel)
            p.drawPath(self.shape())


class BuildingItem(Snappy, QGraphicsItem):
    """A rectangular building (house, shop, ...) with a roof ridge, door, optional label, and cutaway interior."""

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

        # Draw roof unless player is inside (or DM screen view showing cutaway)
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
        on_tv = widget is not None and widget.property("player_view")
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
    """Ground cover (water, forest, ...) painted with a round brush or a filled rectangle."""

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
    """A top-down prop drawn from built-in SVGs or user-supplied SVG/PNG files in assets/props/."""

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
    """An area the DM reveals to the players by hand. Only a dashed outline on the DM screen."""

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
    """The window the players see through. Drag its border on the DM map to pan the player view."""

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
            d.get("aura_color", "#3b82f6"), d.get("image_path", "")
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
    """Line segments that block sight: buildings (when outside), stone walls, hedges, and closed doors/walls."""
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
    """Ray-cast outline of what can be seen from (cx, cy) within R, stopped by wall segments."""
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
        # If this prop or door/wall is inside a BuildingItem, hide it unless that building has a player inside
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


# ----------------------------------------------------------------------------- generated world & assets
DETAIL_ZOOM = 0.1
PROP_UNITS = {k: (w * UNITS_PER_FT, h * UNITS_PER_FT) for k, (w, h) in worldgen.PROP_FT.items()}
ENEMY_LOOK = {
    "Walker": ("#7c8a5a", 1), "Runner": ("#c2410c", 1), "Brute": ("#7f1d1d", 2),
    "Goblin": ("#4d7c0f", 1), "Bandit": ("#dc2626", 1), "Ogre": ("#7f1d1d", 2),
    "Sec-Drone": ("#f97316", 1), "Cyborg": ("#ef4444", 1), "Mech": ("#7f1d1d", 2),
    "Outlaw": ("#ef4444", 1), "Gunslinger": ("#c2410c", 1),
}

_WHEELS = ('<rect x="20" y="1" width="26" height="9" rx="3" fill="#111"/><rect x="104" y="1" width="26" height="9" rx="3" fill="#111"/>'
           '<rect x="20" y="55" width="26" height="9" rx="3" fill="#111"/><rect x="104" y="55" width="26" height="9" rx="3" fill="#111"/>')
PROP_SVGS = {
    "car": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 65">'
            '<ellipse cx="77" cy="35" rx="71" ry="25" fill="#000" fill-opacity="0.28"/>'
            '<rect x="3" y="8" width="144" height="49" rx="14" fill="#6f7f93" stroke="#1f242d" stroke-width="2.5"/>'
            '<rect x="40" y="13" width="62" height="39" rx="7" fill="#8b9bb0" stroke="#1f242d" stroke-width="2"/>'
            '<rect x="104" y="14" width="24" height="37" rx="5" fill="#26303d"/><rect x="22" y="15" width="14" height="35" rx="4" fill="#26303d"/>'
            + _WHEELS + '<rect x="143" y="14" width="6" height="10" rx="2" fill="#f4e7a1"/><rect x="143" y="41" width="6" height="10" rx="2" fill="#f4e7a1"/></svg>'),
    "wreck": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 65">'
              '<ellipse cx="77" cy="35" rx="71" ry="25" fill="#000" fill-opacity="0.28"/>'
              '<rect x="3" y="8" width="144" height="49" rx="14" fill="#8a4b2d" stroke="#1f242d" stroke-width="2.5"/>'
              '<rect x="40" y="13" width="62" height="39" rx="7" fill="#6b4a3a" stroke="#1f242d" stroke-width="2"/>'
              '<polygon points="104,14 128,20 122,34 128,48 104,51" fill="#2a2f36"/>'
              '<path d="M44 16 L70 34 L52 50 M70 34 L98 20" stroke="#cfd6dd" stroke-width="1.5" fill="none"/>'
              '<ellipse cx="62" cy="34" rx="30" ry="16" fill="#1a1410" fill-opacity="0.45"/>'
              + _WHEELS + '</svg>'),
    "barricade": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 35">'
                  '<rect x="4" y="5" width="114" height="27" rx="3" fill="#000" fill-opacity="0.25"/>'
                  '<rect x="2" y="3" width="116" height="8" rx="2" fill="#8b5e34" stroke="#1f242d" stroke-width="2"/>'
                  '<rect x="2" y="13" width="116" height="8" rx="2" fill="#a07040" stroke="#1f242d" stroke-width="2"/>'
                  '<rect x="2" y="23" width="116" height="8" rx="2" fill="#7a5230" stroke="#1f242d" stroke-width="2"/>'
                  '<path d="M12 2 L42 33 M78 2 L108 33" stroke="#4a3018" stroke-width="5"/>'
                  '<circle cx="8" cy="7" r="1.6" fill="#ddd"/><circle cx="112" cy="27" r="1.6" fill="#ddd"/></svg>'),
    "rubble": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100">'
               '<ellipse cx="62" cy="56" rx="50" ry="38" fill="#000" fill-opacity="0.22"/>'
               '<polygon points="10,70 40,40 70,60 60,90 20,92" fill="#8a8680" stroke="#1f242d" stroke-width="2.5"/>'
               '<polygon points="60,50 95,30 112,62 84,82" fill="#6f6a63" stroke="#1f242d" stroke-width="2.5"/>'
               '<polygon points="30,30 55,14 66,38 40,48" fill="#a29c92" stroke="#1f242d" stroke-width="2.5"/>'
               '<polygon points="75,78 100,70 108,92 82,96" fill="#5b5750" stroke="#1f242d" stroke-width="2.5"/></svg>'),
    "overgrowth": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 160">'
                   '<g fill="#3f7a3a" fill-opacity="0.82" stroke="#1f242d" stroke-width="2.5">'
                   '<circle cx="60" cy="80" r="42"/><circle cx="110" cy="62" r="46"/><circle cx="140" cy="102" r="38"/>'
                   '<circle cx="86" cy="116" r="34"/></g>'
                   '<g fill="#5fa04f" fill-opacity="0.85"><circle cx="70" cy="70" r="16"/><circle cx="118" cy="58" r="18"/>'
                   '<circle cx="132" cy="104" r="14"/></g></svg>'),
    "wagon": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 70">'
              '<ellipse cx="76" cy="37" rx="52" ry="26" fill="#000" fill-opacity="0.28"/>'
              '<rect x="28" y="14" width="96" height="42" rx="4" fill="#8b5e34" stroke="#1f242d" stroke-width="2.5"/>'
              '<rect x="34" y="19" width="84" height="32" rx="2" fill="#e5dec9" stroke="#9c937e" stroke-width="2"/>'
              '<line x1="2" y1="27" x2="28" y2="27" stroke="#5c3a1d" stroke-width="4"/>'
              '<line x1="2" y1="43" x2="28" y2="43" stroke="#5c3a1d" stroke-width="4"/>'
              '<rect x="44" y="6" width="22" height="6" rx="2" fill="#1f242d"/><rect x="92" y="6" width="22" height="6" rx="2" fill="#1f242d"/>'
              '<rect x="44" y="58" width="22" height="6" rx="2" fill="#1f242d"/><rect x="92" y="58" width="22" height="6" rx="2" fill="#1f242d"/></svg>'),
    "campfire": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60">'
                 '<circle cx="30" cy="30" r="24" fill="#57534e" stroke="#1f242d" stroke-width="2.5" stroke-dasharray="6 4"/>'
                 '<path d="M14 20 L46 40 M46 20 L14 40" stroke="#78350f" stroke-width="5" stroke-linecap="round"/>'
                 '<circle cx="30" cy="30" r="13" fill="#f97316" fill-opacity="0.88"/>'
                 '<circle cx="30" cy="30" r="7" fill="#fde047"/></svg>'),
    "boulder": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 90">'
                '<ellipse cx="52" cy="50" rx="40" ry="33" fill="#000" fill-opacity="0.28"/>'
                '<polygon points="18,68 12,36 38,14 76,20 88,52 68,78 32,80" fill="#78716c" stroke="#1f242d" stroke-width="2.5"/>'
                '<polygon points="26,34 44,22 68,28 54,48 30,48" fill="#a8a29e" fill-opacity="0.5"/></svg>'),
    "crate": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80">'
              '<rect x="9" y="9" width="66" height="66" rx="4" fill="#000" fill-opacity="0.28"/>'
              '<rect x="6" y="6" width="68" height="68" rx="4" fill="#a16207" stroke="#1f242d" stroke-width="2.5"/>'
              '<line x1="8" y1="8" x2="72" y2="72" stroke="#713f12" stroke-width="3.5"/>'
              '<line x1="72" y1="8" x2="8" y2="72" stroke="#713f12" stroke-width="3.5"/>'
              '<rect x="14" y="14" width="52" height="52" fill="none" stroke="#451a03" stroke-width="2.5"/></svg>'),
    "terminal": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 40">'
                 '<rect x="6" y="6" width="52" height="32" rx="4" fill="#000" fill-opacity="0.28"/>'
                 '<rect x="4" y="4" width="52" height="32" rx="4" fill="#1e293b" stroke="#1f242d" stroke-width="2.5"/>'
                 '<rect x="10" y="9" width="40" height="14" rx="2" fill="#06b6d4"/>'
                 '<circle cx="16" cy="29" r="2.5" fill="#22c55e"/><circle cx="25" cy="29" r="2.5" fill="#ef4444"/></svg>'),
    "tree": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
             '<circle cx="64" cy="64" r="46" fill="#000" fill-opacity="0.26"/>'
             '<circle cx="60" cy="60" r="46" fill="#2d6a3e" stroke="#1f242d" stroke-width="2.5"/>'
             '<circle cx="52" cy="52" r="30" fill="#3f8a52" fill-opacity="0.75"/>'
             '<circle cx="68" cy="66" r="22" fill="#235430" fill-opacity="0.5"/>'
             '<circle cx="60" cy="60" r="7" fill="#5c3a1d" stroke="#1f242d" stroke-width="2"/></svg>'),
    "table": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 50">'
              '<rect x="7" y="7" width="68" height="38" rx="4" fill="#000" fill-opacity="0.28"/>'
              '<rect x="5" y="5" width="70" height="40" rx="4" fill="#92400e" stroke="#1f242d" stroke-width="2.5"/>'
              '<line x1="5" y1="18" x2="75" y2="18" stroke="#78350f" stroke-width="1.5"/>'
              '<line x1="5" y1="32" x2="75" y2="32" stroke="#78350f" stroke-width="1.5"/></svg>'),
    "bed": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 70">'
            '<rect x="5" y="5" width="38" height="63" rx="3" fill="#000" fill-opacity="0.28"/>'
            '<rect x="3" y="3" width="39" height="64" rx="3" fill="#78350f" stroke="#1f242d" stroke-width="2.5"/>'
            '<rect x="6" y="18" width="33" height="46" rx="2" fill="#b91c1c"/>'
            '<rect x="6" y="18" width="33" height="10" fill="#f3f4f6"/>'
            '<rect x="9" y="6" width="27" height="10" rx="3" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/></svg>'),
    "chest": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 30">'
              '<rect x="5" y="5" width="38" height="23" rx="2" fill="#000" fill-opacity="0.28"/>'
              '<rect x="3" y="3" width="39" height="24" rx="2" fill="#854d0e" stroke="#1f242d" stroke-width="2.5"/>'
              '<line x1="3" y1="15" x2="42" y2="15" stroke="#1f242d" stroke-width="2"/>'
              '<rect x="19" y="11" width="7" height="8" rx="1" fill="#eab308" stroke="#1f242d" stroke-width="1.5"/></svg>'),
    "tent": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
             '<polygon points="52,10 94,88 10,88" fill="#000" fill-opacity="0.25"/>'
             '<polygon points="50,6 92,84 8,84" fill="#d6c7a9" stroke="#1f242d" stroke-width="2.5"/>'
             '<line x1="50" y1="6" x2="50" y2="84" stroke="#78716c" stroke-width="2.5"/>'
             '<polygon points="50,52 62,84 38,84" fill="#44403c"/></svg>'),
    "counter": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 35">'
                '<rect x="4" y="5" width="114" height="27" rx="3" fill="#000" fill-opacity="0.28"/>'
                '<rect x="2" y="3" width="116" height="28" rx="3" fill="#78350f" stroke="#1f242d" stroke-width="2.5"/>'
                '<rect x="6" y="7" width="108" height="20" rx="2" fill="#92400e"/></svg>'),
    "shelf": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 25">'
              '<rect x="3" y="3" width="74" height="19" rx="2" fill="#713f12" stroke="#1f242d" stroke-width="2.5"/>'
              '<circle cx="16" cy="12" r="4" fill="#22c55e"/><circle cx="32" cy="12" r="4" fill="#3b82f6"/>'
              '<rect x="46" y="8" width="10" height="9" fill="#eab308"/><circle cx="66" cy="12" r="3.5" fill="#ef4444"/></svg>'),
    "hearth": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 40">'
               '<rect x="3" y="3" width="54" height="34" rx="3" fill="#57534e" stroke="#1f242d" stroke-width="2.5"/>'
               '<rect x="12" y="10" width="36" height="22" rx="2" fill="#1c1917"/>'
               '<ellipse cx="30" cy="22" rx="12" ry="7" fill="#f97316"/><ellipse cx="30" cy="23" rx="6" ry="3.5" fill="#fde047"/></svg>'),
    "altar": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 45">'
              '<rect x="5" y="5" width="72" height="37" rx="3" fill="#000" fill-opacity="0.3"/>'
              '<rect x="3" y="3" width="74" height="38" rx="3" fill="#94a3b8" stroke="#1f242d" stroke-width="2.5"/>'
              '<rect x="12" y="10" width="56" height="24" rx="2" fill="#cbd5e1" stroke="#475569" stroke-width="1.5"/>'
              '<circle cx="40" cy="22" r="6" fill="#eab308"/></svg>'),
    "pillar": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">'
               '<circle cx="22" cy="22" r="15" fill="#000" fill-opacity="0.3"/>'
               '<circle cx="20" cy="20" r="15" fill="#94a3b8" stroke="#1f242d" stroke-width="2.5"/>'
               '<circle cx="20" cy="20" r="9" fill="#cbd5e1"/></svg>'),
    "brazier": ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">'
                '<circle cx="20" cy="20" r="15" fill="#334155" stroke="#1f242d" stroke-width="2.5"/>'
                '<circle cx="20" cy="20" r="10" fill="#ea580c"/><circle cx="20" cy="20" r="5" fill="#fef08a"/></svg>'),
}


def ensure_assets():
    ASSETS_DIR.mkdir(exist_ok=True)
    PROPS_DIR.mkdir(exist_ok=True)
    TOKENS_DIR.mkdir(exist_ok=True)
    for name, svg in PROP_SVGS.items():
        f = ASSETS_DIR / f"{name}.svg"
        if not f.exists():
            f.write_text(svg)


_ASSET_CACHE = {}


def get_prop_asset(kind):
    if kind in _ASSET_CACHE:
        return _ASSET_CACHE[kind]
    for folder in (PROPS_DIR, ASSETS_DIR):
        for ext in (".svg", ".png", ".jpg", ".jpeg", ".webp"):
            p = folder / f"{kind}{ext}"
            if p.exists():
                obj = QSvgRenderer(str(p)) if ext == ".svg" else QPixmap(str(p))
                _ASSET_CACHE[kind] = obj
                return obj
    _ASSET_CACHE[kind] = None
    return None


def list_all_props():
    names = list(worldgen.PROP_FT.keys())
    for folder in (PROPS_DIR, ASSETS_DIR):
        if folder.exists():
            for p in sorted(folder.iterdir()):
                if p.suffix.lower() in (".svg", ".png", ".jpg", ".jpeg", ".webp") and p.stem not in names:
                    names.append(p.stem)
    return names


class Atlas:
    current = None
    warned = False


_QPATHS = {}


def world_path(pts):
    path = _QPATHS.get(id(pts))
    if path is None:
        path = QPainterPath(QPointF(pts[0][0] * UNITS_PER_FT, pts[0][1] * UNITS_PER_FT))
        for x, y in pts[1:]:
            path.lineTo(x * UNITS_PER_FT, y * UNITS_PER_FT)
        _QPATHS[id(pts)] = path
    return path


def world_palette():
    return [QColor(TERRAIN[n]).getRgb()[:3] for n in worldgen.BIOMES]


def render_terrain(w, vr, z, nx, ny, B):
    pal = world_palette()
    step = B / (z * UNITS_PER_FT)
    x0, y0 = vr.left() / UNITS_PER_FT, vr.top() / UNITS_PER_FT
    buf = bytearray(nx * ny * 4)
    terrain, biome = w.terrain, w.biome
    for j in range(ny):
        y = y0 + (j + 0.5) * step
        for i in range(nx):
            x = x0 + (i + 0.5) * step
            e, m = terrain(x, y)
            r, g, b = pal[biome(e, m, x, y)]
            shade = 0.80 + 0.5 * e
            k = (j * nx + i) * 4
            buf[k], buf[k + 1], buf[k + 2], buf[k + 3] = min(255, int(b * shade)), min(255, int(g * shade)), min(255, int(r * shade)), 255
    return QImage(bytes(buf), nx, ny, nx * 4, QImage.Format_RGB32).copy()


DOT_ODDS = {worldgen.FOREST: 0.80, worldgen.SCRUB: 0.30, worldgen.GRASS: 0.14, worldgen.FARM: 0.30,
            worldgen.WATER: 0.10, worldgen.ROCK: 0.35, worldgen.SNOW: 0.08, worldgen.SAND: 0.12}
DOT_STYLE = {worldgen.FOREST: ((30, 84, 46, 215), 6, 7, False), worldgen.SCRUB: ((142, 122, 70, 200), 2.5, 2, False),
             worldgen.GRASS: ((96, 150, 70, 190), 1.5, 1.5, False), worldgen.FARM: ((170, 146, 66, 210), 6, 6, True),
             worldgen.WATER: ((255, 255, 255, 120), 4, 4, True), worldgen.ROCK: ((105, 105, 110, 210), 2.5, 3, False),
             worldgen.SNOW: ((205, 220, 240, 220), 1.5, 2, False), worldgen.SAND: ((196, 172, 120, 200), 1.2, 1.2, False)}


def render_dots(w, vr, z):
    if z < 0.0005:
        return {}
    cell = 2 ** math.ceil(math.log2(40 / (z * UNITS_PER_FT)))
    fx0, fy0 = vr.left() / UNITS_PER_FT, vr.top() / UNITS_PER_FT
    i0, i1 = math.floor(fx0 / cell), math.floor(vr.right() / UNITS_PER_FT / cell)
    j0, j1 = math.floor(fy0 / cell), math.floor(vr.bottom() / UNITS_PER_FT / cell)
    if (i1 - i0 + 1) * (j1 - j0 + 1) > 3500:
        return {}
    seed, ppf, out = w.seed, z * UNITS_PER_FT, {}
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            r1, r2 = worldgen.hash2(i, j, seed + 31), worldgen.hash2(j, i, seed + 57)
            x, y = (i + r1) * cell, (j + r2) * cell
            e, m = w.terrain(x, y)
            b = w.biome(e, m, x, y)
            if worldgen.hash2(i * 7 + 1, j * 13 + 5, seed + 77) <= DOT_ODDS[b]:
                out.setdefault(b, []).append(((x - fx0) * ppf, (y - fy0) * ppf, 0.6 + 0.8 * r1))
    return out


def draw_dots(p, dots):
    for b, lst in dots.items():
        color, base, scale, dash = DOT_STYLE[b]
        if dash:
            p.setPen(QPen(QColor(*color), 1.6))
            for x, y, sz in lst:
                r = base + scale * sz * 0.5
                p.drawLine(QPointF(x - r, y), QPointF(x + r, y))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*color))
            for x, y, sz in lst:
                r = base + scale * sz
                p.drawEllipse(QPointF(x, y), r, r)


ROAD_LOOK = {"highway": ("#4b5160", "#8a90a0", 2.6), "county": ("#6b6455", "#b8b09a", 1.5), "spur": ("#6b6455", "#c2b79c", 1.1)}
SYMBOL_PX = {"city": 6, "town": 4, "village": 3, "farm": 2.5}
SYMBOL_COLOR = {"city": "#374151", "town": "#4b5563", "village": "#6b7280", "farm": "#8b5e34"}


def draw_world(view, p, rect):
    w = Atlas.current
    z = view.transform().m11()
    vp = view.viewport()
    W, H = vp.width(), vp.height()
    if W <= 0 or H <= 0:
        return
    vr = view.mapToScene(vp.rect()).boundingRect()
    B = 28
    nx, ny = -(-W // B), -(-H // B)
    key = (round(vr.left(), 2), round(vr.top(), 2), z, W, H, id(w))
    cache = getattr(view, "_world_cache", None)
    if cache is None or cache[0] != key:
        cache = (key, render_terrain(w, vr, z, nx, ny, B), render_dots(w, vr, z))
        view._world_cache = cache
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.drawImage(QRectF(vr.left(), vr.top(), nx * B / z, ny * B / z), cache[1])
    p.save()
    p.resetTransform()
    draw_dots(p, cache[2])
    p.restore()
    fx0, fy0 = vr.left() / UNITS_PER_FT, vr.top() / UNITS_PER_FT
    fx1, fy1 = vr.right() / UNITS_PER_FT, vr.bottom() / UNITS_PER_FT
    p.setBrush(Qt.NoBrush)
    for rv in w.rivers:
        if worldgen.overlaps(rv["bbox"], fx0, fy0, fx1, fy1):
            p.setPen(QPen(QColor("#4f93c9"), max(rv["width"] * UNITS_PER_FT, 2.4 / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(world_path(rv["pts"]))
    for road in w.roads_in_rect(fx0, fy0, fx1, fy1, z > 0.0003):
        casing, fill, minpx = ROAD_LOOK[road["kind"]]
        wd, path = road["width"] * UNITS_PER_FT, world_path(road["pts"])
        p.setPen(QPen(QColor(casing), max(wd * 1.25, (minpx + 1.6) / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(QColor(fill), max(wd, minpx / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)
    if z < DETAIL_ZOOM:
        p.save()
        p.resetTransform()
        font = QFont()
        font.setBold(True)
        font.setPixelSize(12)
        p.setFont(font)
        for st in w.settlements_in_rect(fx0, fy0, fx1, fy1):
            if (st.kind == "village" and z < 5e-4) or (st.kind == "farm" and z < 4e-3) or (st.kind == "town" and z < 8e-5):
                continue
            sx, sy = (st.x * UNITS_PER_FT - vr.left()) * z, (st.y * UNITS_PER_FT - vr.top()) * z
            base, true_r = SYMBOL_PX[st.kind], st.radius * UNITS_PER_FT * z
            if true_r > base:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(70, 70, 80, 60))
                p.drawEllipse(QPointF(sx, sy), true_r, true_r)
            p.setPen(QPen(QColor("#ffffff"), 1.2))
            p.setBrush(QColor(SYMBOL_COLOR[st.kind]))
            p.drawEllipse(QPointF(sx, sy), base, base)
            if (st.kind == "city" and z < 0.02) or (st.kind == "town" and 5e-4 < z < 0.02):
                p.setPen(QColor(255, 255, 255, 230))
                p.drawText(QPointF(sx + base + 5, sy - 4), st.name)
                p.setPen(QColor("#1f2937"))
                p.drawText(QPointF(sx + base + 4, sy - 5), st.name)
        p.restore()


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
    shape = "Circle"   # "Circle", "Cone", "Line", "Cube"
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

    # 1. Tactical Measurement Ruler
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

    # 2. Area-of-Effect (AoE) Template
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
            half_ang = math.radians(26.565)  # standard 53-degree 5e/tabletop cone
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

        # Distance readout pill
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


# ----------------------------------------------------------------------------- dialogs
class TokenDialog(QDialog):
    def __init__(self, parent, props):
        super().__init__(parent)
        self.setWindowTitle("Edit Token")
        self.color = QColor(props["color"])
        self.aura_color = QColor(props.get("aura_color", "#3b82f6"))
        self.image_path = props.get("image_path", "")
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

        self.player = QCheckBox("Player token (shares vision with the party)")
        self.player.setChecked(props.get("player", False))
        self.mod = QSpinBox()
        self.mod.setRange(-1000, 5000)
        self.mod.setSingleStep(10)
        self.mod.setSuffix(" ft")
        self.mod.setValue(props.get("vision_mod", 0))
        form.addRow(self.player)
        form.addRow("Vision modifier", self.mod)

        # Aura settings
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

        # Status conditions
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
        return {"name": name, "initials": self.ini.text().strip() or auto_initials(name),
                "color": self.color.name(), "size": self.size.value(),
                "player": self.player.isChecked(), "vision_mod": self.mod.value(),
                "statuses": [k for k, cb in self.status_checks.items() if cb.isChecked()],
                "aura_ft": self.aura_spin.value(), "aura_color": self.aura_color.name(),
                "image_path": self.image_path}


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
        # Default to clean living towns in Fantasy/Western unless user toggles encounters on
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
            # Snap to base 5 ft CELL (not zoomed-out Snap.step) so buildings stay human-scale
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

        # Calibration mode for imported underlay map image
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
            if curved_road and len(item.pts) >= 3:
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
class PlayerView(QGraphicsView):
    """Read-only view of the same map for the TV: no controls, with fog of war applied."""

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


# ----------------------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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
        # Default scale: 70 px per 5 ft square (standard VTT export resolution)
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
        windows = [it for it in self.scene.items() if isinstance(it, DoorWallItem) and it.is_window]
        for b in buildings:
            brect = QRectF(b.pos().x(), b.pos().y(), b.w, b.h)
            inside = any(brect.contains(t.center()) for t in player_toks)
            # Also peek inside if a player token is standing within 10 ft of a window on this building
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
            if inside != b.has_player_inside:
                b.has_player_inside = inside
                b.update()
            if inside and not b.interior_done:
                self.populate_building_interior(b, force=False)

    def populate_building_interior(self, b, force=False):
        if b.interior_done and not force:
            return
        b.interior_done = True
        b.has_player_inside = True
        b.update()
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
        if data.get("world"):
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
        # Drop a starter party token in the entrance chamber so vision & doors work immediately
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
        if w is None:
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
                fw, fh = worldgen.PROP_FT.get(sp["kind"], (10.0, 10.0))
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

    def select_listed_token(self, item):
        tok = self.listed_token(item)
        if tok is not None:
            self.scene.clearSelection()
            tok.setSelected(True)

    def zoom_listed_token(self, item):
        tok = self.listed_token(item)
        if tok is not None:
            self.scene.clearSelection()
            tok.setSelected(True)
            self.view.focus_items([tok])

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

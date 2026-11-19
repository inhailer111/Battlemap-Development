#!/usr/bin/env python3
"""InfinityGrid Tabletop - a universal, nearly infinite grid drawing app for tabletop RPG maps.

Setup (Ubuntu):
    sudo apt install python3-venv libxcb-cursor0
    python3 -m venv .venv && source .venv/bin/activate
    pip install PySide6
Run:
    python3 battlemap2.py [optional_map_file.json]
"""
import json
import math
import random
import re
import shutil
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
                               QGroupBox, QScrollArea, QMenu, QTextEdit)
from PySide6.QtSvg import QSvgRenderer

try:
    import worldgen2 as worldgen
except ImportError:
    try:
        import worldgen   # fallback if saved as worldgen.py
    except ImportError:
        worldgen = None

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
QLineEdit, QSpinBox, QComboBox, QTextEdit {
    background-color: #14171f;
    color: #f3f4f6;
    border: 1px solid #323848;
    border-radius: 5px;
    padding: 4px 7px;
    min-height: 20px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
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


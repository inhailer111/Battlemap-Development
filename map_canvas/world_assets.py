import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from core.config import (
    UNITS_PER_FT, TERRAIN, ASSETS_DIR, PROPS_DIR, TOKENS_DIR, worldgen,
)

# ----------------------------------------------------------------------------- generated world & assets
DETAIL_ZOOM = 0.1
_DEFAULT_PROP_FT = {
    "car": (15.0, 6.5), "wreck": (15.0, 6.5), "barricade": (12.0, 3.5),
    "rubble": (12.0, 10.0), "overgrowth": (20.0, 16.0), "wagon": (14.0, 7.0),
    "campfire": (6.0, 6.0), "boulder": (10.0, 9.0), "crate": (8.0, 8.0),
    "terminal": (6.0, 4.0), "tree": (12.0, 12.0), "table": (8.0, 5.0),
    "bed": (4.5, 7.0), "chest": (4.5, 3.0), "tent": (10.0, 10.0),
    "counter": (12.0, 3.5), "shelf": (8.0, 2.5), "hearth": (6.0, 4.0),
    "altar": (8.0, 4.5), "pillar": (4.0, 4.0), "brazier": (4.0, 4.0),
}
_PROP_FT_SOURCE = getattr(worldgen, "PROP_FT", _DEFAULT_PROP_FT) if worldgen else _DEFAULT_PROP_FT
PROP_UNITS = {k: (w * UNITS_PER_FT, h * UNITS_PER_FT) for k, (w, h) in _PROP_FT_SOURCE.items()}
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
    names = list(_PROP_FT_SOURCE.keys())
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


_BIOME_ALIASES = {
    "Grassland": "Grass",
}


def world_palette():
    out = []
    for n in worldgen.BIOMES:
        key = _BIOME_ALIASES.get(n, n)
        col = QColor(TERRAIN.get(key, "#888888"))
        out.append(col.getRgb()[:3])
    return out
def _sample_world_cell(w, fx, fy):
    if hasattr(w, "biome_at"):
        b = w.biome_at(fx, fy)
    elif hasattr(w, "biome_name_at"):
        b = w.biome_name_at(fx, fy)
    else:
        b = None

    if hasattr(w, "elevation_at"):
        h = w.elevation_at(fx, fy)
    elif hasattr(w, "height_at"):
        h = w.height_at(fx, fy)
    else:
        h = 0.5
    return b, h


_TERRAIN_DEBUG_PRINTED = False


def render_terrain(w, vr, z, nx, ny, B):
    if nx <= 0 or ny <= 0 or w is None or z == 0:
        return None

    fmt = getattr(QImage, "Format_RGB32", None) or QImage.Format.Format_RGB32
    img = QImage(nx, ny, fmt)
    bg_col = QColor(28, 32, 38)
    img.fill(bg_col)

    has_elev = hasattr(w, "elevation") and callable(w.elevation)
    seed = int(getattr(w, "seed", 1337))
    water_threshold = -0.52

    water_palette = [
        QColor(max(0, 32 - i * 3), max(0, 72 - i * 5), max(0, 114 - i * 6))
        for i in range(8)
    ]
    land_palette = []
    for i in range(32):
        t = i / 31.0
        if t < 0.35:
            u = t / 0.35
            land_palette.append(QColor(int(52 + u * 20), int(74 + u * 22), int(48 + u * 10)))
        elif t < 0.75:
            u = (t - 0.35) / 0.40
            land_palette.append(QColor(int(72 + u * 40), int(96 + u * 18), int(58 + u * 20)))
        else:
            u = (t - 0.75) / 0.25
            land_palette.append(QColor(int(112 + u * 36), int(114 + u * 34), int(108 + u * 36)))

    inv_z_ft = 1.0 / (z * UNITS_PER_FT)
    left_ft = vr.left() / UNITS_PER_FT
    top_ft = vr.top() / UNITS_PER_FT

    for py in range(ny):
        fy = top_ft + (py + 0.5) * B * inv_z_ft
        for px in range(nx):
            fx = left_ft + (px + 0.5) * B * inv_z_ft

            elev = float(w.elevation(fx, fy)) if has_elev else 0.0
            grain = (_hash2(px, py, seed) - 0.5) * 0.14

            if elev + grain * 0.35 < water_threshold:
                depth = max(0.0, min(0.999, (water_threshold - elev) / 0.85))
                col = water_palette[int(depth * len(water_palette))]
            else:
                t = max(0.0, min(0.999, (elev - water_threshold + grain) / 1.85))
                col = land_palette[int(t * len(land_palette))]

            img.setPixelColor(px, py, col)

    return img

def _hash2(a, b, seed=0):
    n = (int(a) * 374761393 + int(b) * 668265263 + int(seed) * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = (n ^ (n >> 16)) & 0xFFFFFFFF
    return n / 4294967296.0

def _biome_dot_odds_map():
    biomes = getattr(worldgen, "BIOMES", None) or []
    base_odds = {
        "Forest": 0.80,
        "Scrub": 0.30,
        "Grass": 0.14,
        "Grassland": 0.14,
        "Farmland": 0.30,
        "Farm": 0.30,
        "Water": 0.10,
        "Rock": 0.35,
        "Snow": 0.08,
        "Sand": 0.12,
    }
    odds_by_id = {}
    odds_by_name = dict(base_odds)
    for idx, bname in enumerate(biomes):
        for k, v in base_odds.items():
            if str(bname).lower() == k.lower():
                odds_by_id[idx] = v
                odds_by_name[bname] = v
    return odds_by_id, odds_by_name


def _dot_odds_for_biome(b, odds_by_id, odds_by_name):
    if isinstance(b, int):
        return odds_by_id.get(b, 0.0)
    if isinstance(b, str):
        return odds_by_name.get(b, odds_by_name.get(b.capitalize(), 0.0))
    return 0.0

def _sample_w_terrain_biome(w, x, y):
    if hasattr(w, "terrain") and callable(w.terrain):
        e, m = w.terrain(x, y)
    elif hasattr(w, "terrain_at") and callable(w.terrain_at):
        e, m = w.terrain_at(x, y)
    else:
        e = w.elevation_at(x, y) if hasattr(w, "elevation_at") and callable(w.elevation_at) else 0.5
        m = w.moisture_at(x, y) if hasattr(w, "moisture_at") and callable(w.moisture_at) else 0.5

    if hasattr(w, "biome") and callable(w.biome):
        b = w.biome(e, m, x, y)
    elif hasattr(w, "biome_at") and callable(w.biome_at):
        b = w.biome_at(x, y)
    else:
        b = "Grass"
    return e, m, b

def render_dots(w, vr, z):
    if worldgen is None or z < 0.0005:
        return {}
    odds_by_id, odds_by_name = _biome_dot_odds_map()
    cell = 2 ** math.ceil(math.log2(40 / (z * UNITS_PER_FT)))
    fx0, fy0 = vr.left() / UNITS_PER_FT, vr.top() / UNITS_PER_FT
    i0, i1 = math.floor(fx0 / cell), math.floor(vr.right() / UNITS_PER_FT / cell)
    j0, j1 = math.floor(fy0 / cell), math.floor(vr.bottom() / UNITS_PER_FT / cell)
    if (i1 - i0 + 1) * (j1 - j0 + 1) > 3500:
        return {}
    seed, ppf, out = w.seed, z * UNITS_PER_FT, {}
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            r1, r2 = _hash2(i, j, seed + 31), _hash2(j, i, seed + 57)
            x, y = (i + r1) * cell, (j + r2) * cell
            _, _, b = _sample_w_terrain_biome(w, x, y)
            odd = _dot_odds_for_biome(b, odds_by_id, odds_by_name)
            if odd > 0 and _hash2(i * 7 + 1, j * 13 + 5, seed + 77) <= odd:
                out.setdefault(b, []).append(((x - fx0) * ppf, (y - fy0) * ppf, 0.6 + 0.8 * r1))
    return out

def _biome_dot_style_map():
    base_styles = {
        "Forest": ((30, 84, 46, 215), 6, 7, False),
        "Scrub": ((142, 122, 70, 200), 2.5, 2, False),
        "Grass": ((92, 148, 68, 170), 2.0, 1.5, False),
        "Grassland": ((92, 148, 68, 170), 2.0, 1.5, False),
        "Farmland": ((186, 158, 72, 185), 2.5, 2, False),
        "Farm": ((186, 158, 72, 185), 2.5, 2, False),
        "Water": ((65, 130, 195, 175), 2.0, 1.5, False),
        "Rock": ((125, 130, 140, 210), 4.0, 3.5, True),
        "Snow": ((230, 238, 248, 200), 3.0, 2.5, False),
        "Sand": ((214, 192, 122, 185), 2.5, 2, False),
    }
    by_id = {}
    by_name = dict(base_styles)
    biomes = getattr(worldgen, "BIOMES", None) or []
    for idx, bname in enumerate(biomes):
        for k, style in base_styles.items():
            if str(bname).lower() == k.lower():
                by_id[idx] = style
                by_name[bname] = style
    return by_id, by_name


def _dot_style_for_key(key, by_id, by_name):
    if isinstance(key, int):
        return by_id.get(key)
    if isinstance(key, str):
        return by_name.get(key, by_name.get(key.capitalize()))
    return None


def draw_dots(p, dots):
    if not dots:
        return
    by_id, by_name = _biome_dot_style_map()
    for b_key, pts in dots.items():
        style = _dot_style_for_key(b_key, by_id, by_name)
        if style is None:
            continue
        rgba, r_base, r_scale, is_rect = style
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(*rgba))
        for sx, sy, mult in pts:
            rad = max(1.5, r_base + r_scale * (mult - 0.6))
            if is_rect:
                p.drawRect(QRectF(sx - rad, sy - rad, rad * 2, rad * 2))
            else:
                p.drawEllipse(QPointF(sx, sy), rad, rad)


ROAD_LOOK = {"highway": ("#4b5160", "#8a90a0", 2.6), "county": ("#6b6455", "#b8b09a", 1.5), "spur": ("#6b6455", "#c2b79c", 1.1)}
SYMBOL_PX = {"city": 6, "town": 4, "village": 3, "farm": 2.5}
SYMBOL_COLOR = {"city": "#374151", "town": "#4b5563", "village": "#6b7280", "farm": "#8b5e34"}


def draw_world(view, p, rect):
    w = getattr(Atlas, "current", None)
    if w is None or worldgen is None:
        return
    z = view.transform().m11()
    vp = view.viewport()
    W, H = vp.width(), vp.height()
    if W <= 0 or H <= 0 or z == 0:
        return

    vr = view.mapToScene(vp.rect()).boundingRect()
    fx0, fy0 = vr.left() / UNITS_PER_FT, vr.top() / UNITS_PER_FT
    fx1, fy1 = vr.right() / UNITS_PER_FT, vr.bottom() / UNITS_PER_FT

    B = 28
    nx, ny = max(1, -(-W // B)), max(1, -(-H // B))
    key = (round(vr.left(), 2), round(vr.top(), 2), round(z, 6), W, H, id(w))
    cache = getattr(view, "_world_cache", None)
    if cache is None or cache[0] != key:
        cache = (key, render_terrain(w, vr, z, nx, ny, B), render_dots(w, vr, z))
        view._world_cache = cache

    terrain_img, dots_data = cache[1], cache[2]
    if terrain_img is not None and not terrain_img.isNull():
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawImage(QRectF(vr.left(), vr.top(), nx * B / z, ny * B / z), terrain_img)

    if dots_data:
        p.save()
        p.resetTransform()
        draw_dots(p, dots_data)
        p.restore()

    p.setBrush(Qt.NoBrush)

    rivers = getattr(w, "rivers", None) or []
    for rv in rivers:
        bbox = rv.get("bbox") if isinstance(rv, dict) else getattr(rv, "bbox", None)
        pts = rv.get("pts") if isinstance(rv, dict) else getattr(rv, "pts", None)
        width = rv.get("width", 2.0) if isinstance(rv, dict) else getattr(rv, "width", 2.0)
        if not pts:
            continue
        if bbox is None or not hasattr(worldgen, "overlaps") or worldgen.overlaps(bbox, fx0, fy0, fx1, fy1):
            p.setPen(QPen(QColor("#4f93c9"), max(width * UNITS_PER_FT, 2.4 / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(world_path(pts))

    roads_fn = getattr(w, "roads_in_rect", None)
    if callable(roads_fn) and "ROAD_LOOK" in globals() and ROAD_LOOK:
        style_aliases = {
            "asphalt": "paved",
            "highway": "paved",
        }
        lower_look = {str(k).lower(): v for k, v in ROAD_LOOK.items()}
        fallback_look = (
            lower_look.get("paved")
            or lower_look.get("road")
            or lower_look.get("dirt")
            or next(iter(ROAD_LOOK.values()))
        )
        for road in roads_fn(fx0, fy0, fx1, fy1):
            if isinstance(road, dict):
                raw_style = road.get("style") or road.get("kind") or road.get("type")
                pts = road.get("pts") or road.get("points")
                width = road.get("width", 26.0)
            else:
                raw_style = (
                    getattr(road, "style", None)
                    or getattr(road, "kind", None)
                    or getattr(road, "type", None)
                )
                pts = getattr(road, "pts", None) or getattr(road, "points", None)
                width = getattr(road, "width", 26.0)

            if not pts or len(pts) < 2:
                continue

            s_key = str(raw_style or "").lower()
            s_key = style_aliases.get(s_key, s_key)
            casing, fill, minpx = lower_look.get(s_key, fallback_look)

            wd, path = float(width) * UNITS_PER_FT, world_path(pts)
            p.setPen(QPen(QColor(casing), max(wd * 1.25, (minpx + 1.6) / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(QColor(fill), max(wd, minpx / z), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)

    settlements_fn = getattr(w, "settlements_in_rect", None)
    if z < DETAIL_ZOOM and callable(settlements_fn):
        p.save()
        p.resetTransform()
        font = QFont()
        font.setBold(True)
        font.setPixelSize(12)
        p.setFont(font)
        for st in settlements_fn(fx0, fy0, fx1, fy1):
            if (st.kind == "village" and z < 5e-4) or (st.kind == "farm" and z < 4e-3) or (st.kind == "town" and z < 8e-5):
                continue
            sx, sy = (st.x * UNITS_PER_FT - vr.left()) * z, (st.y * UNITS_PER_FT - vr.top()) * z
            base = SYMBOL_PX.get(st.kind, 4)
            true_r = st.radius * UNITS_PER_FT * z
            if true_r > base:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(70, 70, 80, 60))
                p.drawEllipse(QPointF(sx, sy), true_r, true_r)
            p.setPen(QPen(QColor("#ffffff"), 1.2))
            p.setBrush(QColor(SYMBOL_COLOR.get(st.kind, "#e5e7eb")))
            p.drawEllipse(QPointF(sx, sy), base, base)
            if (st.kind == "city" and z < 0.02) or (st.kind == "town" and 5e-4 < z < 0.02):
                p.setPen(QColor(255, 255, 255, 230))
                p.drawText(QPointF(sx + base + 5, sy - 4), st.name)
                p.setPen(QColor("#1f2937"))
                p.drawText(QPointF(sx + base + 4, sy - 5), st.name)
        p.restore()

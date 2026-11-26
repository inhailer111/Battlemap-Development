from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, MISSING
from typing import Dict, Iterable, List, Optional, Tuple


GENRE_DATA: Dict[str, dict] = {
    "Contagion": {
        "road_style": "Paved",
        "secondary_style": "Dirt",
        "building_kinds": [
            "house",
            "duplex",
            "warehouse",
            "clinic",
            "police",
            "fire_station",
            "market",
            "barn",
        ],
    },
    "Fantasy": {
        "road_style": "Dirt",
        "secondary_style": "Dirt",
        "building_kinds": ["cottage", "tavern", "smith", "granary", "hall", "shrine"],
    },
    "Sci-Fi": {
        "road_style": "Paved",
        "secondary_style": "Paved",
        "building_kinds": ["hab", "depot", "relay", "medbay", "bunker", "hangar"],
    },
}

RANK: Dict[str, int] = {
    "city": 4,
    "town": 3,
    "village": 2,
    "farm": 1,
}

BIOMES: Tuple[str, ...] = (
    "Water",
    "Marsh",
    "Grassland",
    "Forest",
    "Scrub",
    "Rock",
)


def mix(*vals: int) -> int:
    """Deterministic integer hash mixer for seeded procedural generation."""
    h = 0x9E3779B97F4A7C15
    for v in vals:
        x = int(v) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 30
        x = (x * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 27
        x = (x * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 31
        h ^= (x + 0x9E3779B97F4A7C15 + ((h << 6) & 0xFFFFFFFFFFFFFFFF) + (h >> 2))
        h &= 0xFFFFFFFFFFFFFFFF
    return h

def chaikin(
    pts: List[Tuple[float, float]], iterations: int = 2
) -> List[Tuple[float, float]]:
    """Corner-cutting polyline smoothing (Chaikin's algorithm) for road curves."""
    if len(pts) < 3 or iterations <= 0:
        return list(pts)

    coords = [(float(x), float(y)) for x, y in pts]
    for _ in range(iterations):
        if len(coords) < 3:
            break
        nxt: List[Tuple[float, float]] = [coords[0]]
        for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
            q = (0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1)
            r = (0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1)
            nxt.extend([q, r])
        nxt.append(coords[-1])
        coords = nxt
    return coords

def _dist_point_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


@dataclass
class Settlement:
    uid: int
    name: str
    kind: str  # "city", "town", "village", "farm"
    x: float
    y: float
    radius: float

    def bbox(self) -> Tuple[float, float, float, float]:
        return (
            self.x - self.radius,
            self.y - self.radius,
            self.x + self.radius,
            self.y + self.radius,
        )

@dataclass
class WorldGen:
    CHUNK_FT: int = 250
    seed: int = 1337
    genre: str = "Contagion"
    density: int = 1  # 0=low, 1=med, 2=high
    zombies: Dict[str, bool] = field(
        default_factory=lambda: {
            "cars": True,
            "barricades": True,
            "rubble": True,
            "overgrowth": True,
            "zombies": True,
        }
    )
    include_buildings: bool = True
    state_bounds: Tuple[float, float, float, float] = (-6000.0, -6000.0, 6000.0, 6000.0)
    cities: List[Settlement] = field(default_factory=list)
    towns: List[Settlement] = field(default_factory=list)
    villages: List[Settlement] = field(default_factory=list)
    farms: List[Settlement] = field(default_factory=list)
    highways: List[dict] = field(default_factory=list)
    rivers: List[dict] = field(default_factory=list)
    custom_settlements: List[Settlement] = field(default_factory=list)
    state_tiles: List[Tuple[int, int]] = field(default_factory=list)
    layout: str = "grid"

    def __init__(self, **kwargs) -> None:
        for f in self.__dataclass_fields__.values():
            if f.name in kwargs:
                setattr(self, f.name, kwargs.pop(f.name))
            elif f.default_factory is not MISSING:
                setattr(self, f.name, f.default_factory())
            elif f.default is not MISSING:
                setattr(self, f.name, f.default)
        self._extra_opts = kwargs
        self.done: set = set()
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.genre not in GENRE_DATA:
            self.genre = "Contagion"
        self.density = max(0, min(2, int(self.density)))
        self.x0, self.y0, self.x1, self.y1 = self.state_bounds
        self.W = self.x1 - self.x0
        self.H = self.y1 - self.y0
        self.done = set()
        self._build_state_settlements()
        self._build_rivers()

    def stats(self) -> dict:
        return {
            "cities": len(self.cities),
            "towns": len(self.towns),
            "villages": len(self.villages),
            "farms": len(self.farms),
            "highways": len(self.highways),
            "rivers": len(self.rivers),
        }

    def inside(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    @staticmethod
    def overlaps(
        bbox: Tuple[float, float, float, float],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> bool:
        bx0, by0, bx1, by1 = bbox
        return max(bx0, x0) <= min(bx1, x1) and max(by0, y0) <= min(by1, y1)

    def elevation(self, x: float, y: float) -> float:
        s = float(self.seed)
        w1 = math.sin(x * 0.00042 + s * 0.013) * math.cos(y * 0.00039 - s * 0.007)
        w2 = math.sin((x * 0.00095 - y * 0.00078) + s * 0.021) * 0.45
        w3 = math.cos((x + y) * 0.0021 - s * 0.017) * 0.20
        return w1 + w2 + w3

    def moisture(self, x: float, y: float) -> float:
        s = float(self.seed)
        m1 = math.cos(x * 0.00051 - s * 0.019) * math.sin(y * 0.00047 + s * 0.011)
        m2 = math.sin((x - y) * 0.0013 + s * 0.029) * 0.35
        return max(0.0, min(1.0, 0.5 + 0.45 * (m1 + m2)))

    def is_water(self, x: float, y: float) -> bool:
        return self.elevation(x, y) < -0.52

    def biome_at(self, x: float, y: float) -> str:
        e = self.elevation(x, y)
        if e < -0.52:
            return "Water"
        m = self.moisture(x, y)
        if e < -0.34 and m > 0.55:
            return "Marsh"
        if e > 0.78:
            return "Rock"
        if e > 0.42 and m < 0.48:
            return "Scrub"
        if m > 0.52 or (0.05 < e < 0.65 and m > 0.38):
            return "Forest"
        return "Grassland"

    def _name_for(self, rng: random.Random, kind: str) -> str:
        prefixes = [
            "Asheford",
            "Oakridge",
            "Pinecrest",
            "Cedar Creek",
            "Ironwood",
            "Redwood",
            "Stonebridge",
            "Clearwater",
            "Hawthorne",
            "Ravenswood",
            "Briarcliff",
            "Mapleton",
            "Fairview",
            "Copperfield",
            "Timberline",
        ]
        suffixes = {
            "city": [" Metro", " City", " Crossing"],
            "town": ["", " Town", " Junction", " Hollow"],
            "village": [" Village", " Corners", " Siding"],
            "farm": [" Homestead", " Ranch", " Farmstead"],
        }
        base = rng.choice(prefixes)
        suf = rng.choice(suffixes.get(kind, [""]))
        return f"{base}{suf}".strip()

    def tile_settlements(self, tx: int, ty: int) -> List[Settlement]:
        rng = random.Random(mix(self.seed, tx, ty, 404))
        tile_size = 3000.0
        bx0, by0 = tx * tile_size, ty * tile_size

        density_scale = {0: 0.65, 1: 1.0, 2: 1.35}[self.density]
        plan = (
            ("town", min(0.95, 0.55 * density_scale), 1300.0, 2100.0),
            ("village", min(0.98, 0.72 * density_scale), 750.0, 1200.0),
            ("farm", min(0.99, 0.85 * density_scale), 300.0, 460.0),
        )

        out: List[Settlement] = []
        slots = 1 if self.density == 0 else (2 if self.density == 1 else 3)
        for _ in range(slots):
            for kind, prob, r_min, r_max in plan:
                if rng.random() < prob:
                    sx = bx0 + rng.uniform(350.0, tile_size - 350.0)
                    sy = by0 + rng.uniform(350.0, tile_size - 350.0)
                    if not self.inside(sx, sy) or self.is_water(sx, sy):
                        continue
                    if any(math.hypot(s.x - sx, s.y - sy) < 650.0 for s in out):
                        continue
                    uid = mix(self.seed, tx, ty, len(out), RANK[kind]) & 0x7FFFFFFF
                    out.append(
                        Settlement(
                            uid=uid,
                            name=self._name_for(rng, kind),
                            kind=kind,
                            x=sx,
                            y=sy,
                            radius=rng.uniform(r_min, r_max),
                        )
                    )
        return out

    def _build_state_settlements(self) -> None:
        tile_size = 3000.0
        tx0, tx1 = math.floor(self.x0 / tile_size), math.floor(self.x1 / tile_size)
        ty0, ty1 = math.floor(self.y0 / tile_size), math.floor(self.y1 / tile_size)
        self.state_tiles = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]

        everyone = [
            s
            for key in self.state_tiles
            for s in self.tile_settlements(*key)
            if self.inside(s.x, s.y)
        ]
        everyone.extend(self.custom_settlements)

        self.cities = []
        self.towns = [s for s in everyone if s.kind == "town"]
        self.villages = [s for s in everyone if s.kind == "village"]
        self.farms = [s for s in everyone if s.kind == "farm"]

        want_cities = max(2, len(self.towns) // 4) if self.towns else 0
        while len(self.cities) < want_cities and self.towns:
            t = max(self.towns, key=lambda s: s.radius)
            self.towns.remove(t)
            t.kind = "city"
            t.radius = max(t.radius, 2400.0)
            self.cities.append(t)

        if not self.cities and not self.towns and self.inside(0.0, 0.0) and not self.is_water(0.0, 0.0):
            self.towns.append(
                Settlement(
                    uid=mix(self.seed, 0, 0, RANK["town"]) & 0x7FFFFFFF,
                    name=self._name_for(random.Random(self.seed), "town"),
                    kind="town",
                    x=0.0,
                    y=0.0,
                    radius=1600.0,
                )
            )

        self._build_state_highways()

    def _make_curved_road(
        self,
        a: Tuple[float, float],
        b: Tuple[float, float],
        width: float,
        style: str,
        curve_amp: float = 220.0,
    ) -> dict:
        x1, y1 = a
        x2, y2 = b
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 1e-5:
            return {"pts": [a, b], "width": width, "style": style}
        nx, ny = -dy / dist, dx / dist
        offset = math.sin((x1 + y1 + x2 + y2) * 0.0015 + self.seed) * min(curve_amp, dist * 0.14)
        mx = (x1 + x2) * 0.5 + nx * offset
        my = (y1 + y2) * 0.5 + ny * offset
        return {
            "pts": [(x1, y1), (mx, my), (x2, y2)],
            "width": width,
            "style": style,
        }

    def _build_state_highways(self) -> None:
        self.highways = []
        main_style = GENRE_DATA[self.genre]["road_style"]
        sec_style = GENRE_DATA[self.genre]["secondary_style"]
        hubs = self.cities + self.towns

        if len(hubs) >= 2:
            connected = {hubs[0].uid}
            remaining = list(hubs[1:])
            hub_by_id = {h.uid: h for h in hubs}

            while remaining:
                best = None
                best_d = float("inf")
                for u_id in connected:
                    u = hub_by_id[u_id]
                    for v in remaining:
                        d = math.hypot(v.x - u.x, v.y - u.y)
                        if d < best_d:
                            best_d = d
                            best = (u, v)
                if best is None:
                    break
                u, v = best
                connected.add(v.uid)
                remaining.remove(v)
                width = 36.0 if ("city" in (u.kind, v.kind)) else 26.0
                self.highways.append(self._make_curved_road((u.x, u.y), (v.x, v.y), width, main_style))

            extra_per_hub = {0: 1, 1: 2, 2: 3}[self.density]
            for i, a in enumerate(hubs):
                nearest = sorted(
                    (h for j, h in enumerate(hubs) if j != i),
                    key=lambda h: math.hypot(h.x - a.x, h.y - a.y),
                )[:extra_per_hub]
                for b in nearest:
                    if i < hubs.index(b) and math.hypot(b.x - a.x, b.y - a.y) < 5200.0:
                        width = 30.0 if ("city" in (a.kind, b.kind)) else 22.0
                        self.highways.append(self._make_curved_road((a.x, a.y), (b.x, b.y), width, main_style))

        for s in self.villages:
            snap_x, snap_y = self.snap_to_nearest_road(s.x, s.y, max_snap=3200.0)
            if (snap_x, snap_y) != (s.x, s.y):
                self.highways.append(self._make_curved_road((s.x, s.y), (snap_x, snap_y), 16.0, sec_style, 120.0))

        if self.density >= 1:
            for f in self.farms:
                snap_x, snap_y = self.snap_to_nearest_road(f.x, f.y, max_snap=2200.0)
                if (snap_x, snap_y) != (f.x, f.y):
                    self.highways.append(self._make_curved_road((f.x, f.y), (snap_x, snap_y), 11.0, "Dirt", 80.0))

    def _build_rivers(self) -> None:
        self.rivers = []
        rng = random.Random(mix(self.seed, 777, 1))
        river_count = {0: 1, 1: 2, 2: 3}[self.density]
        for idx in range(river_count):
            px = rng.uniform(self.x0 * 0.75, self.x1 * 0.75)
            py = rng.uniform(self.y0 * 0.75, self.y1 * 0.75)
            pts: List[Tuple[float, float]] = [(px, py)]
            angle = rng.uniform(0.0, math.tau)
            for _ in range(18):
                e_c = self.elevation(px, py)
                best_ang = angle
                best_e = e_c
                for cand in (angle - 0.35, angle, angle + 0.35):
                    tx = px + math.cos(cand) * 450.0
                    ty = py + math.sin(cand) * 450.0
                    te = self.elevation(tx, ty)
                    if te < best_e:
                        best_e = te
                        best_ang = cand
                angle = best_ang + rng.uniform(-0.12, 0.12)
                px += math.cos(angle) * 450.0
                py += math.sin(angle) * 450.0
                pts.append((px, py))
                if not self.inside(px, py):
                    break
            if len(pts) >= 2:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                self.rivers.append(
                    {
                        "id": idx,
                        "pts": pts,
                        "width": 24.0 + idx * 6.0,
                        "bbox": (min(xs), min(ys), max(xs), max(ys)),
                    }
                )

    def all_settlements(self) -> List[Settlement]:
        return self.cities + self.towns + self.villages + self.farms

    def settlements_near(self, x: float, y: float, max_dist: float) -> List[Settlement]:
        return [s for s in self.all_settlements() if math.hypot(s.x - x, s.y - y) <= max_dist]

    def snap_to_nearest_road(self, x: float, y: float, max_snap: float = 1200.0) -> Tuple[float, float]:
        best_pt = (x, y)
        best_dist = max_snap
        for road in self.highways:
            pts = road.get("pts", [])
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                dx, dy = x2 - x1, y2 - y1
                len_sq = dx * dx + dy * dy
                if len_sq <= 1e-9:
                    continue
                t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / len_sq))
                px, py = x1 + t * dx, y1 + t * dy
                d = math.hypot(x - px, y - py)
                if d < best_dist:
                    best_dist = d
                    best_pt = (px, py)
        return best_pt

    def generate_single_town(
        self,
        x: float,
        y: float,
        name: Optional[str] = None,
        kind: str = "town",
        radius: float = 1600.0,
        snap_to_road: bool = True,
        include_buildings: bool = True,
    ) -> Settlement:
        tx, ty = self.snap_to_nearest_road(x, y) if snap_to_road else (x, y)
        rng = random.Random(mix(self.seed, int(tx), int(ty), 888))
        uid = mix(self.seed, int(tx), int(ty), len(self.custom_settlements) + 99) & 0x7FFFFFFF
        town = Settlement(
            uid=uid,
            name=name or self._name_for(rng, kind),
            kind=kind if kind in ("city", "town", "village") else "town",
            x=tx,
            y=ty,
            radius=radius,
        )
        self.custom_settlements.append(town)
        if town.kind == "city":
            self.cities.append(town)
        elif town.kind == "village":
            self.villages.append(town)
        else:
            self.towns.append(town)

        hubs = [h for h in (self.cities + self.towns) if h.uid != town.uid]
        if hubs:
            nearest = min(hubs, key=lambda h: math.hypot(h.x - town.x, h.y - town.y))
            self.highways.append(
                self._make_curved_road(
                    (town.x, town.y),
                    (nearest.x, nearest.y),
                    26.0,
                    GENRE_DATA[self.genre]["road_style"],
                )
            )
        if include_buildings:
            self.include_buildings = True
        return town

    def roads_in_rect(self, x0: float, y0: float, x1: float, y1: float) -> List[dict]:
        out: List[dict] = []
        for road in self.highways:
            pts = road.get("pts", [])
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if (
                    max(ax, bx) >= x0
                    and min(ax, bx) <= x1
                    and max(ay, by) >= y0
                    and min(ay, by) <= y1
                ):
                    out.append(road)
                    break
        return out

    def _collect_road_segments(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        town_streets: List[Tuple[Tuple[float, float], Tuple[float, float], float]],
    ) -> List[Tuple[float, float, float, float, float]]:
        segs: List[Tuple[float, float, float, float, float]] = [
            (a[0], a[1], b[0], b[1], w) for a, b, w in town_streets
        ]
        for road in self.roads_in_rect(x0 - 240.0, y0 - 240.0, x1 + 240.0, y1 + 240.0):
            w = float(road.get("width", 26.0))
            pts = road.get("pts", [])
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                segs.append((ax, ay, bx, by, w))
        return segs

    def _is_clear_of_roads(
        self,
        cx: float,
        cy: float,
        w: float,
        h: float,
        road_segments: Iterable[Tuple[float, float, float, float, float]],
        setback: float = 10.0,
    ) -> bool:
        footprint_radius = 0.5 * math.hypot(w, h)
        for ax, ay, bx, by, r_width in road_segments:
            min_dist = (r_width * 0.5) + setback + footprint_radius * 0.65
            if _dist_point_to_segment(cx, cy, ax, ay, bx, by) < min_dist:
                return False
        return True

    def _settlement_road_network(
        self, s: Settlement
    ) -> List[Tuple[Tuple[float, float], Tuple[float, float], float, str]]:
        """Build one main street branching cleanly off a WorldGen road plus organic side streets."""
        s_rng = random.Random(mix(self.seed, s.uid, 5150))
        road_style = GENRE_DATA[self.genre]["road_style"] if s.kind in ("city", "town") else "Dirt"
        main_w = 18.0 if s.kind == "city" else (15.0 if s.kind == "town" else 11.0)
        side_w = max(8.5, main_w * 0.72)

        segments: List[Tuple[Tuple[float, float], Tuple[float, float], float, str]] = []

        snap_x, snap_y = self.snap_to_nearest_road(s.x, s.y, max_snap=s.radius + 2200.0)
        if (snap_x, snap_y) != (s.x, s.y):
            start = (snap_x, snap_y)
            vx, vy = s.x - snap_x, s.y - snap_y
            vlen = max(1.0, math.hypot(vx, vy))
            ux, uy = vx / vlen, vy / vlen
            end_reach = min(s.radius * 0.65, 520.0 if s.kind != "farm" else 180.0)
            end = (s.x + ux * end_reach, s.y + uy * end_reach)
        else:
            ang0 = s_rng.uniform(0.0, math.tau)
            half_len = min(s.radius * 0.65, 480.0 if s.kind != "farm" else 180.0)
            start = (s.x - math.cos(ang0) * half_len, s.y - math.sin(ang0) * half_len)
            end = (s.x + math.cos(ang0) * half_len, s.y + math.sin(ang0) * half_len)

        dx, dy = end[0] - start[0], end[1] - start[1]
        dist = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / dist, dy / dist
        nx, ny = -uy, ux

        # Keep the junction throat straight for ~55 ft so it branches cleanly off the highway,
        # then curve organically through town
        throat_len = min(55.0, dist * 0.18)
        throat_pt = (start[0] + ux * throat_len, start[1] + uy * throat_len)
        bend1 = s_rng.uniform(-35.0, 35.0)
        bend2 = s_rng.uniform(-40.0, 40.0)
        m1 = (
            start[0] + dx * 0.42 + nx * bend1,
            start[1] + dy * 0.42 + ny * bend1,
        )
        m2 = (
            start[0] + dx * 0.74 + nx * bend2,
            start[1] + dy * 0.74 + ny * bend2,
        )
        spine_nodes = [start, throat_pt, m1, m2, end]
        for a, b in zip(spine_nodes, spine_nodes[1:]):
            segments.append((a, b, main_w, road_style))

        # Branch side streets past the highway junction (t_frac from 0.28 to 0.90)
        branch_count = {"city": 7, "town": 5, "village": 3, "farm": 2}.get(s.kind, 4)
        for i in range(branch_count):
            t_frac = 0.28 + 0.62 * (i / max(1, branch_count - 1))
            scaled = t_frac * (len(spine_nodes) - 1)
            idx = min(len(spine_nodes) - 2, int(scaled))
            u = scaled - idx
            pa, pb = spine_nodes[idx], spine_nodes[idx + 1]
            root = (pa[0] + (pb[0] - pa[0]) * u, pa[1] + (pb[1] - pa[1]) * u)

            spine_ang = math.atan2(pb[1] - pa[1], pb[0] - pa[0])
            side_sign = -1.0 if (i % 2 == 0) else 1.0
            branch_ang = spine_ang + side_sign * s_rng.uniform(0.68, 1.32) + s_rng.uniform(-0.18, 0.18)
            branch_len = min(s.radius * 0.65, s_rng.uniform(180.0, 390.0 if s.kind != "farm" else 140.0))

            b_perp_x, b_perp_y = -math.sin(branch_ang), math.cos(branch_ang)
            b_bend = s_rng.uniform(-35.0, 35.0)
            bm = (
                root[0] + math.cos(branch_ang) * (branch_len * 0.5) + b_perp_x * b_bend,
                root[1] + math.sin(branch_ang) * (branch_len * 0.5) + b_perp_y * b_bend,
            )
            bend_pt = (
                root[0] + math.cos(branch_ang) * branch_len,
                root[1] + math.sin(branch_ang) * branch_len,
            )
            b_style = "Dirt" if s.kind in ("village", "farm") or i >= 3 else road_style
            segments.append((root, bm, side_w, b_style))
            segments.append((bm, bend_pt, max(8.0, side_w * 0.85), "Dirt"))

            if s.kind in ("city", "town") and i < 3 and s_rng.random() < 0.6:
                sub_ang = branch_ang + s_rng.uniform(-0.8, 0.8)
                sub_len = s_rng.uniform(100.0, 200.0)
                sub_end = (
                    bm[0] + math.cos(sub_ang) * sub_len,
                    bm[1] + math.sin(sub_ang) * sub_len,
                )
                segments.append((bm, sub_end, 8.5, "Dirt"))

        return segments

    def plan_chunk(self, cx: int, cy: int) -> List[dict]:
        """Generate a main-street-led organic town layout with every building placed next to a road."""
        ch = float(self.CHUNK_FT)
        x0, y0 = cx * ch, cy * ch
        x1, y1 = x0 + ch, y0 + ch
        chunk_cx, chunk_cy = x0 + ch * 0.5, y0 + ch * 0.5
        rng = random.Random(mix(self.seed, cx, cy, 9001))

        specs: List[dict] = []
        town_streets: List[Tuple[Tuple[float, float], Tuple[float, float], float]] = []
        chunk_road_fronts: List[Tuple[float, float, float, float, float, Settlement]] = []

        nearby_settlements = [
            s
            for s in self.all_settlements()
            if math.hypot(s.x - chunk_cx, s.y - chunk_cy) <= s.radius + ch * 1.6
        ]

        for s in nearby_settlements:
            for a, b, w_seg, st_seg in self._settlement_road_network(s):
                if self._segment_intersects_rect(a[0], a[1], b[0], b[1], x0, y0, x1, y1):
                    town_streets.append((a, b, w_seg))
                    chunk_road_fronts.append((a[0], a[1], b[0], b[1], w_seg, s))
                    specs.append(
                        {
                            "t": "road",
                            "pts": [a, b],
                            "width": w_seg,
                            "style": st_seg,
                        }
                    )

        road_segs = self._collect_road_segments(x0, y0, x1, y1, town_streets)
        placed_buildings: List[dict] = []

        # Place buildings strictly alongside roads in this chunk
        if self.include_buildings and chunk_road_fronts:
            slots_per_seg = 2 + self.density
            for ax, ay, bx, by, r_w, anchor in chunk_road_fronts:
                seg_dx, seg_dy = bx - ax, by - ay
                seg_len = math.hypot(seg_dx, seg_dy)
                if seg_len < 12.0:
                    continue
                ux, uy = seg_dx / seg_len, seg_dy / seg_len
                # Normal vectors on both sides of the road
                normals = [(-uy, ux), (uy, -ux)]
                road_deg = math.degrees(math.atan2(seg_dy, seg_dx))

                for _ in range(slots_per_seg):
                    t_pos = rng.uniform(0.15, 0.85)
                    fx = ax + seg_dx * t_pos
                    fy = ay + seg_dy * t_pos
                    nx, ny = rng.choice(normals)

                    dist_from_center = math.hypot(fx - anchor.x, fy - anchor.y)
                    angle_to_pt = math.atan2(fy - anchor.y, fx - anchor.x)
                    lobe_scale = 0.85 + 0.22 * math.sin(angle_to_pt * 3.0 + anchor.uid)
                    if dist_from_center > anchor.radius * lobe_scale:
                        continue

                    kind, bw, bh = self._pick_zoned_building(rng, anchor.kind, dist_from_center, anchor.radius)
                    # Sit right next to the road edge with a small lot setback
                    lot_offset = (r_w * 0.5) + (bh * 0.5) + rng.uniform(5.0, 14.0)
                    bx_lot = fx + nx * lot_offset + rng.uniform(-6.0, 6.0)
                    by_lot = fy + ny * lot_offset + rng.uniform(-6.0, 6.0)

                    if not (x0 + 8.0 <= bx_lot <= x1 - 8.0 and y0 + 8.0 <= by_lot <= y1 - 8.0):
                        continue
                    if self.is_water(bx_lot, by_lot):
                        continue
                    if not self._is_clear_of_roads(bx_lot, by_lot, bw, bh, road_segs, setback=4.0):
                        continue
                    if any(math.hypot(b["x"] - bx_lot, b["y"] - by_lot) < 28.0 for b in placed_buildings):
                        continue

                    b_spec = {
                        "t": "building",
                        "kind": kind,
                        "x": bx_lot,
                        "y": by_lot,
                        "w": bw,
                        "h": bh,
                        "angle": round(road_deg + rng.uniform(-8.0, 8.0), 1),
                    }
                    placed_buildings.append(b_spec)
                    specs.append(b_spec)

        # Surrounding yard/lot & wild terrain props
        prop_count = 4 + self.density * 3
        for _ in range(prop_count):
            px = rng.uniform(x0 + 10.0, x1 - 10.0)
            py = rng.uniform(y0 + 10.0, y1 - 10.0)
            if self.is_water(px, py):
                continue
            if any(math.hypot(b["x"] - px, b["y"] - py) < 15.0 for b in placed_buildings):
                continue
            biome = self.biome_at(px, py)
            kind = "tree" if biome in ("Forest", "Grassland", "Marsh") else "rock"
            specs.append(
                {
                    "t": "prop",
                    "kind": kind,
                    "x": px,
                    "y": py,
                    "w": 10.0,
                    "h": 10.0,
                    "rot": 0,
                }
            )

        return specs

    @staticmethod
    def _segment_intersects_rect(
        ax: float,
        ay: float,
        bx: float,
        by: float,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> bool:
        if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
            return False
        if (x0 <= ax <= x1 and y0 <= ay <= y1) or (x0 <= bx <= x1 and y0 <= by <= y1):
            return True
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        half_r = math.hypot(x1 - x0, y1 - y0) * 0.5
        return _dist_point_to_segment(cx, cy, ax, ay, bx, by) <= half_r

    def _pick_zoned_building(
        self,
        rng: random.Random,
        settlement_kind: str,
        dist: float,
        radius: float,
    ) -> Tuple[str, float, float]:
        ratio = dist / max(1.0, radius)
        if self.genre == "Contagion":
            if settlement_kind == "farm":
                if ratio < 0.5 and rng.random() < 0.65:
                    return ("barn", rng.uniform(28.0, 42.0), rng.uniform(22.0, 32.0))
                return ("house", rng.uniform(20.0, 28.0), rng.uniform(18.0, 24.0))
            if ratio < 0.35:
                civic_pool = ["market", "clinic", "police", "fire_station", "warehouse"]
                if settlement_kind == "village":
                    civic_pool = ["market", "clinic", "house"]
                kind = rng.choice(civic_pool)
                if kind in ("warehouse", "fire_station", "market"):
                    return (kind, rng.uniform(32.0, 46.0), rng.uniform(24.0, 36.0))
                return (kind, rng.uniform(24.0, 34.0), rng.uniform(20.0, 28.0))
            if ratio < 0.72:
                kind = rng.choice(["duplex", "house", "house", "warehouse"])
                if kind == "warehouse":
                    return (kind, rng.uniform(30.0, 42.0), rng.uniform(22.0, 32.0))
                return (kind, rng.uniform(20.0, 30.0), rng.uniform(18.0, 26.0))
            return (
                rng.choice(["house", "barn"]),
                rng.uniform(20.0, 32.0),
                rng.uniform(18.0, 26.0),
            )

        b_kinds = GENRE_DATA[self.genre]["building_kinds"]
        return (rng.choice(b_kinds), rng.uniform(20.0, 34.0), rng.uniform(18.0, 28.0))
World = WorldGen

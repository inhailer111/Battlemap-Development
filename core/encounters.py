import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class EncounterResult:
    task_type: str
    zone_tier: str
    d20_roll: int
    outcome_band: str
    hazard_triggered: bool
    enemies: List[Dict[str, int]] = field(default_factory=list)
    environment_effects: List[str] = field(default_factory=list)
    status_risks: List[str] = field(default_factory=list)
    loot_drops: List[str] = field(default_factory=list)
    gm_notes: str = ""


class ContagionEncounterGenerator:
    """Task-based single-d20 encounter, hazard, and scavenge generator for Contagion."""

    ZONE_MODIFIERS = {
        "residential": 0,
        "industrial": -1,
        "commercial": -1,
        "hospital": -3,
        "quarantine": -4,
    }

    COMPOSITION_TABLES = {
        "residential": [
            [{"type": "Shambler", "count": 2}, {"type": "Crawler", "count": 1}],
            [{"type": "Runner", "count": 1}, {"type": "Shambler", "count": 2}],
            [{"type": "Infected Local", "count": 3}],
        ],
        "industrial": [
            [{"type": "Brute", "count": 1}, {"type": "Shambler", "count": 2}],
            [{"type": "Hazmat Shambler", "count": 2}, {"type": "Runner", "count": 1}],
            [{"type": "Spitter", "count": 1}, {"type": "Shambler", "count": 3}],
        ],
        "commercial": [
            [{"type": "Shambler", "count": 3}, {"type": "Runner", "count": 1}],
            [{"type": "Crawler", "count": 2}, {"type": "Shambler", "count": 2}],
            [{"type": "Infected Shopper", "count": 3}],
        ],
        "hospital": [
            [{"type": "Screamer", "count": 1}, {"type": "Runner", "count": 2}],
            [{"type": "Stalker", "count": 1}, {"type": "Hazmat Shambler", "count": 2}],
            [{"type": "Shambler Horde", "count": 5}],
        ],
        "quarantine": [
            [{"type": "Brute", "count": 1}, {"type": "Screamer", "count": 1}, {"type": "Runner", "count": 2}],
            [{"type": "Mutant Stalker", "count": 2}, {"type": "Spitter", "count": 1}],
        ],
    }

    ENVIRONMENT_HAZARDS = {
        "scavenging": [
            "Collapsed shelving blocks exit (Agility DC 12 to clear quickly)",
            "Broken glass & rusted rebar (1 Bleed / Contamination check on sprint)",
            "Flickering emergency strobe (-2 Ranged Accuracy; +2 Stealth)",
            "Spore pocket / stagnant bio-sludge (Contamination +1 on failed Endure)",
        ],
        "travel": [
            "Heavy fog / rain (Vision radius halved; noise dampened)",
            "Abandoned vehicle bottleneck (Requires detour or lockpick/pry check)",
            "Downed live power line across street (2-tile hazard zone)",
            "Echoing alley acoustics (Gunfire attracts extra wave next round)",
        ],
        "rest": [
            "Drafty barricade (Exhaustion recovery reduced by 1 unless fuel spent)",
            "Distant horde groans (Sanity check DC 10 or gain Restless)",
        ],
        "perimeter_watch": [
            "Shifting wind carries scent/sound (Perception check at -2)",
            "Low visibility fog bank (Ranged detection range reduced)",
        ],
    }

    LOOT_TABLES = {
        "low": ["Scrap Metal x2", "Rags / Bandage", "Canned Beans", "9mm Rounds (x4)", "Duct Tape"],
        "mid": ["First Aid Kit", "Antibiotics (1 dose)", "12-Gauge Shells (x5)", "Crowbar", "Filtered Water (2L)"],
        "high": ["Hazmat Filter", "Surgical Trauma Pack", "5.56 Ammo (x12)", "Adrenaline Shot", "Reinforced Kevlar Plate"],
    }

    def generate(
        self,
        task_type: str = "scavenging",
        zone_tier: str = "residential",
        noise_level: int = 0,
        scavenge_bonus: int = 0,
        forced_roll: Optional[int] = None,
    ) -> EncounterResult:
        raw_roll = forced_roll if forced_roll is not None else random.randint(1, 20)
        zone_mod = self.ZONE_MODIFIERS.get(zone_tier.lower(), 0)
        effective_roll = max(1, min(20, raw_roll + zone_mod - noise_level + scavenge_bonus))

        if effective_roll <= 9:
            band = "Fail (1-9): Complication & Hostile Contact"
            hazard = True
            enemies = self._pick_enemies(zone_tier, scale=1)
            env = self._pick_hazards(task_type, count=1)
            status = ["Contamination Check (DC 11)", "Sanity -1 if ambushed"]
            loot = self._pick_loot("low", count=1) if task_type == "scavenging" and raw_roll >= 6 else []
            notes = "Hostiles spawn at nearest blind spot or window entry."
        elif effective_roll <= 14:
            band = "Mixed (10-14): Noisy Success / Patrol Nearby"
            hazard = True
            enemies = self._pick_enemies(zone_tier, scale=0) if task_type in ("scavenging", "travel", "perimeter_watch") else []
            env = self._pick_hazards(task_type, count=1)
            status = ["Exhaustion +1 if rushing"]
            loot = self._pick_loot("mid", count=2) if task_type == "scavenging" else []
            notes = "Objective/loot secured or ground covered, with noise/hazard pressure."
        elif effective_roll <= 19:
            band = "Success (15-19): Clean Execution"
            hazard = False
            enemies = []
            env = []
            status = []
            loot = self._pick_loot("mid", count=2) + self._pick_loot("high", count=1) if task_type == "scavenging" else []
            notes = "Clean execution. No ambient threat alerted."
        else:
            band = "Critical (20): Jackpot / Tactical Advantage"
            hazard = False
            enemies = []
            env = ["Secured vantage point (+2 Vision / +2 Cover)"]
            status = ["Sanity +1 (Morale Boost)"]
            loot = self._pick_loot("high", count=2) + self._pick_loot("mid", count=1) if task_type == "scavenging" else []
            notes = "Bonus loot cache or favorable tactical position gained."

        return EncounterResult(
            task_type=task_type,
            zone_tier=zone_tier,
            d20_roll=effective_roll,
            outcome_band=band,
            hazard_triggered=hazard,
            enemies=enemies,
            environment_effects=env,
            status_risks=status,
            loot_drops=loot,
            gm_notes=notes,
        )

    def _pick_enemies(self, zone_tier: str, scale: int = 0) -> List[Dict[str, int]]:
        pool = self.COMPOSITION_TABLES.get(zone_tier.lower(), self.COMPOSITION_TABLES["residential"])
        group = [dict(entry) for entry in random.choice(pool)]
        if scale > 0 and group:
            group[0]["count"] += scale
        return group

    def _pick_hazards(self, task_type: str, count: int = 1) -> List[str]:
        pool = self.ENVIRONMENT_HAZARDS.get(task_type.lower(), self.ENVIRONMENT_HAZARDS["scavenging"])
        return random.sample(pool, min(count, len(pool)))

    def _pick_loot(self, tier: str, count: int = 1) -> List[str]:
        pool = self.LOOT_TABLES.get(tier, self.LOOT_TABLES["low"])
        return random.sample(pool, min(count, len(pool)))
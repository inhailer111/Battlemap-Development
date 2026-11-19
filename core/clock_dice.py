import random
import re

# ----------------------------------------------------------------------------- campaign clock & dice engine
class CampaignClock:
    """Tracks 2-hour Major Activity Blocks (Contagion) and automatic Day/Night vision transitions."""
    BLOCKS = [
        ("00:00 – 02:00", "Midnight Watch", True),
        ("02:00 – 04:00", "Deep Night", True),
        ("04:00 – 06:00", "Pre-Dawn", True),
        ("06:00 – 08:00", "Early Morning", False),
        ("08:00 – 10:00", "Morning", False),
        ("10:00 – 12:00", "Late Morning", False),
        ("12:00 – 14:00", "Midday", False),
        ("14:00 – 16:00", "Afternoon", False),
        ("16:00 – 18:00", "Late Afternoon", False),
        ("18:00 – 20:00", "Dusk / Evening", False),
        ("20:00 – 22:00", "Nightfall", True),
        ("22:00 – 24:00", "Late Night", True),
    ]

    def __init__(self):
        self.day = 1
        self.block_index = 4  # Default: 08:00 - 10:00 (Morning)
        self.auto_night = True

    def advance_blocks(self, n=1):
        total = self.block_index + n
        self.day = max(1, self.day + (total // len(self.BLOCKS)))
        self.block_index = total % len(self.BLOCKS)

    def current_info(self):
        time_range, label, is_night = self.BLOCKS[self.block_index]
        return self.day, time_range, label, is_night

    def to_dict(self):
        return {"day": self.day, "block_index": self.block_index, "auto_night": self.auto_night}

    def from_dict(self, d):
        if not isinstance(d, dict):
            return
        self.day = max(1, int(d.get("day", 1)))
        self.block_index = int(d.get("block_index", 4)) % len(self.BLOCKS)
        self.auto_night = bool(d.get("auto_night", True))


def roll_dice_expression(expr: str, adv_mode: str = "normal"):
    """Evaluate tabletop dice expressions like '1d20+2', '2d6+3', 'd20', '4d6-1'.
    adv_mode: 'normal', 'adv', or 'dis' (applies when rolling 1d20).
    Returns (total_int, breakdown_str, is_crit, is_fumble).
    """
    cleaned = expr.strip().lower().replace(" ", "")
    if not cleaned:
        cleaned = "1d20"
    if cleaned.startswith("d"):
        cleaned = "1" + cleaned

    tokens = re.findall(r"[+-]?[^+-]+", cleaned)
    total = 0
    parts = []
    is_crit = False
    is_fumble = False

    for tok in tokens:
        sign = -1 if tok.startswith("-") else 1
        body = tok[1:] if tok[0] in "+-" else tok
        if "d" in body:
            n_str, s_str = body.split("d", 1)
            count = int(n_str) if n_str else 1
            sides = int(s_str)
            count = max(1, min(100, count))
            sides = max(2, min(1000, sides))

            if count == 1 and sides == 20 and adv_mode in ("adv", "dis"):
                r1 = random.randint(1, 20)
                r2 = random.randint(1, 20)
                chosen = max(r1, r2) if adv_mode == "adv" else min(r1, r2)
                tag = "ADV" if adv_mode == "adv" else "DIS"
                total += sign * chosen
                prefix = "-" if sign < 0 else ("+" if parts else "")
                parts.append(f"{prefix}[{chosen} ({tag}: {r1},{r2})]")
                if sign > 0:
                    is_crit = (chosen == 20)
                    is_fumble = (chosen == 1)
            else:
                rolls = [random.randint(1, sides) for _ in range(count)]
                sub = sum(rolls)
                total += sign * sub
                prefix = "-" if sign < 0 else ("+" if parts else "")
                rolls_fmt = ",".join(str(r) for r in rolls)
                parts.append(f"{prefix}{count}d{sides}[{rolls_fmt}]")
                if count == 1 and sides == 20 and sign > 0:
                    is_crit = (rolls[0] == 20)
                    is_fumble = (rolls[0] == 1)
        else:
            val = int(body)
            total += sign * val
            prefix = "-" if sign < 0 else ("+" if parts else "")
            parts.append(f"{prefix}{val}")

    return total, " ".join(parts), is_crit, is_fumble



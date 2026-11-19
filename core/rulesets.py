import json
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QMessageBox, QPushButton, QTextEdit,
)

# ----------------------------------------------------------------------------- ruleset manager & settings dialog
class RulesetManager:
    def __init__(self, rulesets_dir="rulesets"):
        self.rulesets_dir = Path(rulesets_dir)
        self.rulesets_dir.mkdir(exist_ok=True)
        self.loaded_profiles = {}
        self.active_ruleset_name = None
        self.ensure_default_rulesets()
        self.load_all_rulesets()

    def ensure_default_rulesets(self):
        defaults = {
            "contagion.json": {
                "system_name": "Contagion",
                "version": "1.0",
                "mechanics": {"movement_unit": "feet", "diagonal_rule": "5e", "dice_engine": "1d20"},
                "character_options": {
                    "jobs": [
                        {"name": "Data Specialist", "starting_gear": ["Laptop", "Multi-tool"], "bonus": "+2 Electronics/Security, expert terminal access and network bypass."},
                        {"name": "Paramedic", "starting_gear": ["Trauma Kit (2x1)", "Bandages (1x1)"], "bonus": "+2 Medical, superior treatment efficiency for trauma and infection management."},
                        {"name": "Firefighter", "starting_gear": ["Fire Axe (3x1)", "Gas Mask (2x2)"], "bonus": "+2 Strength/Breaching, handles heavy doors, axes, and environmental hazards."},
                        {"name": "Police Officer", "starting_gear": ["9mm Pistol (2x1)", "Ammo Box (1x1)"], "bonus": "+2 Firearms proficiency and tactical control during engagements."},
                        {"name": "Military Veteran", "starting_gear": ["Assault Rifle", "Combat Knife"], "bonus": "Enhanced combat readiness, weapon handling, and endurance under fire."},
                        {"name": "Security Guard", "starting_gear": ["Flashlight", "Radio"], "bonus": "Access control expertise, vigilant watch bonuses, and protective gear familiarity."},
                        {"name": "Janitor", "starting_gear": ["Keys", "Cleaning Supplies"], "bonus": "Unconventional shortcut navigation through maintenance tunnels and waste systems."},
                        {"name": "Construction Worker", "starting_gear": ["Heavy Hammer", "Toolkit"], "bonus": "Heavy lifting capacity and structural reinforcement proficiency."},
                        {"name": "Auto Mechanic", "starting_gear": ["Crowbar (2x1)", "Duct Tape (1x1)"], "bonus": "+2 Repair/Crafting, excellent for fixing vehicles, engines, and improvised tools."},
                        {"name": "Sorting / Logistics", "starting_gear": ["Clipboard", "Vest"], "bonus": "Inventory management and spatial efficiency optimizations for carrying gear."},
                        {"name": "Warehouse Dispatch", "starting_gear": ["Radio", "Flashlight"], "bonus": "Supply chain insight and efficient scavenging yields in industrial zones."},
                        {"name": "Park Ranger / Hunter", "starting_gear": ["Hunting Rifle (7x1)", "Knife (2x1)"], "bonus": "+2 Survival/Tracking, wilderness navigation, and proficiency with hunting gear and bows."}
                    ]
                }
            },
            "dnd_5e.json": {
                "system_name": "D&D 5e (SRD)",
                "version": "5.1",
                "mechanics": {"movement_unit": "feet", "diagonal_rule": "5e", "dice_engine": "1d20"},
                "character_options": {
                    "classes": [
                        {"name": "Barbarian", "hit_die": "d12", "starting_gear": ["Greataxe", "Handaxes"]},
                        {"name": "Bard", "hit_die": "d8", "starting_gear": ["Rapier", "Lute"]},
                        {"name": "Cleric", "hit_die": "d8", "starting_gear": ["Mace", "Scale Mail", "Shield"]},
                        {"name": "Fighter", "hit_die": "d10", "starting_gear": ["Chain Mail", "Longsword", "Shield"]},
                        {"name": "Monk", "hit_die": "d8", "starting_gear": ["Shortsword", "Darts"]},
                        {"name": "Paladin", "hit_die": "d10", "starting_gear": ["Longsword", "Shield", "Chain Mail"]},
                        {"name": "Ranger", "hit_die": "d10", "starting_gear": ["Scale Mail", "Shortswords", "Longbow"]},
                        {"name": "Rogue", "hit_die": "d8", "starting_gear": ["Rapier", "Shortbow", "Thieves' Tools"]},
                        {"name": "Wizard", "hit_die": "d6", "starting_gear": ["Quarterstaff", "Spellbook"]}
                    ],
                    "backgrounds": [
                        {"name": "Acolyte", "skill_proficiencies": ["Insight", "Religion"]},
                        {"name": "Criminal", "skill_proficiencies": ["Deception", "Stealth"]},
                        {"name": "Folk Hero", "skill_proficiencies": ["Animal Handling", "Survival"]},
                        {"name": "Noble", "skill_proficiencies": ["History", "Persuasion"]},
                        {"name": "Outlander", "skill_proficiencies": ["Athletics", "Survival"]},
                        {"name": "Sage", "skill_proficiencies": ["Arcana", "History"]},
                        {"name": "Soldier", "skill_proficiencies": ["Athletics", "Intimidation"]}
                    ]
                }
            },
            "generic_wargame.json": {
                "system_name": "Generic Wargame / Freeform",
                "version": "1.0",
                "mechanics": {"movement_unit": "inches", "diagonal_rule": "euclidean", "dice_engine": "d6_pool"},
                "character_options": {
                    "unit_types": [
                        {"name": "Infantry Squad", "base_size": "32mm", "role": "Troops"},
                        {"name": "Elite Character", "base_size": "40mm", "role": "HQ / Leader"},
                        {"name": "Light Vehicle", "base_size": "Hull", "role": "Fast Attack"},
                        {"name": "Heavy Armor / Walker", "base_size": "Hull", "role": "Heavy Support"}
                    ]
                }
            }
        }
        for fname, content in defaults.items():
            fpath = self.rulesets_dir / fname
            if not fpath.exists():
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(content, f, indent=2)
                except OSError:
                    pass

    def load_all_rulesets(self):
        self.loaded_profiles.clear()
        for file_path in self.rulesets_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sys_name = data.get("system_name", file_path.stem)
                    self.loaded_profiles[sys_name] = data
            except Exception as e:
                print(f"Error loading ruleset {file_path.name}: {e}")
        if self.loaded_profiles and not self.active_ruleset_name:
            self.active_ruleset_name = list(self.loaded_profiles.keys())[0]

    def import_ruleset(self, file_path: str) -> str:
        src = Path(file_path)
        if not src.exists() or src.suffix.lower() != ".json":
            raise ValueError("Invalid ruleset file. Please select a valid .json file.")
        dest_path = self.rulesets_dir / src.name
        shutil.copy(src, dest_path)
        self.load_all_rulesets()
        return src.stem

    def set_active_ruleset(self, system_name: str) -> bool:
        if system_name in self.loaded_profiles:
            self.active_ruleset_name = system_name
            return True
        return False

    def get_active_profile(self):
        if self.active_ruleset_name:
            return self.loaded_profiles.get(self.active_ruleset_name)
        return None

    def get_available_systems(self) -> list:
        return list(self.loaded_profiles.keys())

    def get_character_categories(self, system_name: str = None) -> list:
        profile = self.loaded_profiles.get(system_name) if system_name else self.get_active_profile()
        if profile and "character_options" in profile:
            return list(profile["character_options"].keys())
        return []

    def get_character_options(self, option_type: str, system_name: str = None) -> list:
        profile = self.loaded_profiles.get(system_name) if system_name else self.get_active_profile()
        if profile and "character_options" in profile:
            return profile["character_options"].get(option_type, [])
        return []


class RulesetSettingsDialog(QDialog):
    def __init__(self, ruleset_manager, parent=None):
        super().__init__(parent)
        self.rm = ruleset_manager
        self.setWindowTitle("Ruleset Settings & Manager")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.system_combo = QComboBox()
        self.system_combo.addItems(self.rm.get_available_systems())
        if self.rm.active_ruleset_name:
            self.system_combo.setCurrentText(self.rm.active_ruleset_name)
        form.addRow("Active Ruleset Profile", self.system_combo)

        b_import = QPushButton("Import External Ruleset (.json)...")
        b_import.clicked.connect(self.import_custom_ruleset)
        form.addRow("", b_import)

        self.preview_info = QTextEdit()
        self.preview_info.setReadOnly(True)
        self.preview_info.setMaximumHeight(140)
        form.addRow("Ruleset Summary", self.preview_info)
        self.system_combo.currentTextChanged.connect(self.update_preview)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.update_preview(self.system_combo.currentText())

    def update_preview(self, sys_name):
        self.rm.set_active_ruleset(sys_name)
        prof = self.rm.get_active_profile()
        if not prof:
            self.preview_info.clear()
            return
        lines = [f"System: {prof.get('system_name', 'Unknown')}",
                 f"Version: {prof.get('version', '1.0')}"]
        mechs = prof.get("mechanics", {})
        for k, v in mechs.items():
            lines.append(f"{k.replace('_', ' ').title()}: {v}")
        opts = prof.get("character_options", {})
        for cat, items in opts.items():
            lines.append(f"{cat.capitalize()} Count: {len(items)}")
        self.preview_info.setPlainText("\n".join(lines))

    def import_custom_ruleset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Ruleset JSON", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                self.rm.import_ruleset(file_path)
                self.system_combo.clear()
                self.system_combo.addItems(self.rm.get_available_systems())
                QMessageBox.information(self, "Success", "Ruleset imported successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))


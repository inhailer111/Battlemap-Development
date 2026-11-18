import json
import shutil
from pathlib import Path

class RulesetManager:
    def __init__(self, rulesets_dir="rulesets"):
        self.rulesets_dir = Path(rulesets_dir)
        self.rulesets_dir.mkdir(exist_ok=True)
        self.loaded_profiles = {}
        self.active_ruleset_name = None
        self.load_all_rulesets()

    def load_all_rulesets(self):
        """Scans the rulesets directory and loads all JSON profile files."""
        self.loaded_profiles.clear()
        for file_path in self.rulesets_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sys_name = data.get("system_name", file_path.stem)
                    self.loaded_profiles[sys_name] = data
            except Exception as e:
                print(f"Error loading ruleset {file_path.name}: {e}")

    def import_ruleset(self, file_path: str) -> str:
        """Imports an external JSON ruleset into the local rulesets directory."""
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
        """Returns available option categories (e.g. 'classes', 'backgrounds', 'jobs')."""
        profile = self.loaded_profiles.get(system_name) if system_name else self.get_active_profile()
        if profile and "character_options" in profile:
            return list(profile["character_options"].keys())
        return []

    def get_character_options(self, option_type: str, system_name: str = None) -> list:
        """Fetch options for a given category (e.g., 'classes' or 'backgrounds')."""
        profile = self.loaded_profiles.get(system_name) if system_name else self.get_active_profile()
        if profile and "character_options" in profile:
            return profile["character_options"].get(option_type, [])
        return []

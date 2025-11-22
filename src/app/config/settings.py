
import yaml
import multiprocessing
from pathlib import Path
from typing import Any, Dict

class SettingsManager:
    """Manages application settings with persistence."""

    def __init__(self):
        # Settings directory: ~/.config/dspx/
        self.config_dir = Path.home() / ".config" / "dspx"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "settings.yaml"
        
        if not self.config_file.exists():
            self.settings = self._get_default_settings()
            self.save_settings()
        else:
            self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file or return defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded_settings = yaml.safe_load(f) or {}
                    # Merge with defaults to ensure we have all keys
                    defaults = self._get_default_settings()
                    defaults.update(loaded_settings)
                    return defaults
            except Exception as e:
                print(f"Error loading settings: {e}")
                return self._get_default_settings()
        else:
            return self._get_default_settings()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Return default settings."""
        return {
            'max_workers': min(32, multiprocessing.cpu_count() * 2),
            'chunk_size': 65536,
            'patterns_dir': str(self.config_dir),
            'patterns_filename': 'dspx_residuals_patterns.csv',
        }

    def save_settings(self):
        """Save current settings to file."""
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(self.settings, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get_setting(self, key: str, default=None) -> Any:
        """Get a specific setting value."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """Set a specific setting and save."""
        self.settings[key] = value
        self.save_settings()

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings."""
        return self.settings.copy()
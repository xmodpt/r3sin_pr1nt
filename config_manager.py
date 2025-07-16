#!/usr/bin/env python3
"""
Configuration Manager for Resin Printer Application
Handles application settings and plugin configurations
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application and plugin configurations"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration files
        self.app_config_file = self.config_dir / "app_config.json"
        self.plugin_config_file = self.config_dir / "plugin_config.json"
        
        # Default configurations
        self.default_app_config = {
            "printer": {
                "serial_port": "/dev/serial0",
                "baudrate": 115200,
                "timeout": 5.0,
                "firmware_version": "V4.13"
            },
            "usb": {
                "mount_point": "/mnt/usb_share",
                "image_file": "/piusb.bin",
                "auto_start": True
            },
            "interface": {
                "theme": "dark",
                "update_interval": 3000,
                "console_max_lines": 50,
                "webcam_enabled": False
            },
            "file_management": {
                "max_files": 50,
                "max_age_days": 30,
                "auto_cleanup": False,
                "allowed_extensions": [".ctb", ".cbddlp", ".pwmx", ".pwmo", ".pwms", ".pws", ".pw0", ".pwx"]
            }
        }
        
        self.default_plugin_config = {
            "enabled_plugins": [],
            "plugin_settings": {}
        }
        
        # Load configurations
        self.app_config = self._load_config(self.app_config_file, self.default_app_config)
        self.plugin_config = self._load_config(self.plugin_config_file, self.default_plugin_config)
    
    def _load_config(self, config_file: Path, default_config: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration from file or create with defaults"""
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_configs(default_config, config)
            else:
                # Create default config file
                self._save_config(config_file, default_config)
                return default_config.copy()
        except Exception as e:
            logger.error(f"Error loading config from {config_file}: {e}")
            return default_config.copy()
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge user config with defaults"""
        result = default.copy()
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def _save_config(self, config_file: Path, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving config to {config_file}: {e}")
            return False
    
    def get_app_config(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get application configuration"""
        if section:
            return self.app_config.get(section, {})
        return self.app_config
    
    def set_app_config(self, section: str, key: str, value: Any) -> bool:
        """Set application configuration value"""
        try:
            if section not in self.app_config:
                self.app_config[section] = {}
            self.app_config[section][key] = value
            return self._save_config(self.app_config_file, self.app_config)
        except Exception as e:
            logger.error(f"Error setting app config {section}.{key}: {e}")
            return False
    
    def get_plugin_config(self, plugin_name: Optional[str] = None) -> Dict[str, Any]:
        """Get plugin configuration"""
        if plugin_name:
            return self.plugin_config["plugin_settings"].get(plugin_name, {})
        return self.plugin_config
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """Set plugin configuration"""
        try:
            if "plugin_settings" not in self.plugin_config:
                self.plugin_config["plugin_settings"] = {}
            self.plugin_config["plugin_settings"][plugin_name] = config
            return self._save_config(self.plugin_config_file, self.plugin_config)
        except Exception as e:
            logger.error(f"Error setting plugin config for {plugin_name}: {e}")
            return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        try:
            if "enabled_plugins" not in self.plugin_config:
                self.plugin_config["enabled_plugins"] = []
            
            if plugin_name not in self.plugin_config["enabled_plugins"]:
                self.plugin_config["enabled_plugins"].append(plugin_name)
                return self._save_config(self.plugin_config_file, self.plugin_config)
            return True
        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}")
            return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        try:
            if "enabled_plugins" not in self.plugin_config:
                self.plugin_config["enabled_plugins"] = []
            
            if plugin_name in self.plugin_config["enabled_plugins"]:
                self.plugin_config["enabled_plugins"].remove(plugin_name)
                return self._save_config(self.plugin_config_file, self.plugin_config)
            return True
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}")
            return False
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if plugin is enabled"""
        return plugin_name in self.plugin_config.get("enabled_plugins", [])
    
    def get_enabled_plugins(self) -> list:
        """Get list of enabled plugins"""
        return self.plugin_config.get("enabled_plugins", [])
    
    def reset_to_defaults(self, section: Optional[str] = None) -> bool:
        """Reset configuration to defaults"""
        try:
            if section == "app":
                self.app_config = self.default_app_config.copy()
                return self._save_config(self.app_config_file, self.app_config)
            elif section == "plugins":
                self.plugin_config = self.default_plugin_config.copy()
                return self._save_config(self.plugin_config_file, self.plugin_config)
            elif section is None:
                self.app_config = self.default_app_config.copy()
                self.plugin_config = self.default_plugin_config.copy()
                return (self._save_config(self.app_config_file, self.app_config) and
                       self._save_config(self.plugin_config_file, self.plugin_config))
            return False
        except Exception as e:
            logger.error(f"Error resetting config: {e}")
            return False
    
    def export_config(self, export_path: str) -> bool:
        """Export all configurations to a file"""
        try:
            export_data = {
                "app_config": self.app_config,
                "plugin_config": self.plugin_config
            }
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """Import configurations from a file"""
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            if "app_config" in import_data:
                self.app_config = self._merge_configs(self.default_app_config, import_data["app_config"])
                self._save_config(self.app_config_file, self.app_config)
            
            if "plugin_config" in import_data:
                self.plugin_config = self._merge_configs(self.default_plugin_config, import_data["plugin_config"])
                self._save_config(self.plugin_config_file, self.plugin_config)
            
            return True
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            return False 

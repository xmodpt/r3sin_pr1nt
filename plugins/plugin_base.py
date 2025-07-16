#!/usr/bin/env python3
"""
Base Plugin Class for Resin Printer Application
All plugins should inherit from this base class
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List
from flask import Blueprint

logger = logging.getLogger(__name__)

class PluginBase(ABC):
    """Base class for all plugins"""
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.name = self.plugin_dir.name
        self.config = {}
        self.enabled = False
        self.blueprint = None
        
        # Load plugin metadata
        self._load_metadata()
        
        # Load plugin configuration
        self._load_config()
    
    def _load_metadata(self):
        """Load plugin metadata from config.json"""
        metadata_file = self.plugin_dir / "config.json"
        try:
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    self.version = metadata.get("version", "1.0.0")
                    self.author = metadata.get("author", "Unknown")
                    self.description = metadata.get("description", "")
                    self.dependencies = metadata.get("dependencies", [])
                    self.hooks = metadata.get("hooks", [])
                    self.routes = metadata.get("routes", [])
                    self.frontend_assets = metadata.get("frontend_assets", {})
            else:
                # Default metadata
                self.version = "1.0.0"
                self.author = "Unknown"
                self.description = ""
                self.dependencies = []
                self.hooks = []
                self.routes = []
                self.frontend_assets = {}
        except Exception as e:
            logger.error(f"Error loading metadata for plugin {self.name}: {e}")
            self.version = "1.0.0"
            self.author = "Unknown"
            self.description = ""
            self.dependencies = []
            self.hooks = []
            self.routes = []
            self.frontend_assets = {}
    
    def _load_config(self):
        """Load plugin configuration"""
        # This will be set by the plugin manager from the global config
        pass
    
    def set_config(self, config: Dict[str, Any]):
        """Set plugin configuration"""
        self.config = config
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup when plugin is disabled - must be implemented by subclasses"""
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get plugin metadata"""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "dependencies": self.dependencies,
            "hooks": self.hooks,
            "routes": self.routes,
            "frontend_assets": self.frontend_assets,
            "enabled": self.enabled
        }
    
    def create_blueprint(self) -> Optional[Blueprint]:
        """Create Flask blueprint for plugin routes"""
        if not self.routes:
            return None
        
        self.blueprint = Blueprint(
            f'plugin_{self.name}',
            __name__,
            url_prefix=f'/api/plugins/{self.name}'
        )
        
        # Register routes defined in metadata
        self.register_routes()
        
        return self.blueprint
    
    def register_routes(self):
        """Register plugin routes - can be overridden by subclasses"""
        pass
    
    def get_frontend_assets(self) -> Dict[str, List[str]]:
        """Get frontend assets (CSS/JS files) for this plugin"""
        assets = {"css": [], "js": []}
        
        for asset_type, files in self.frontend_assets.items():
            if asset_type in assets:
                for file in files:
                    asset_path = f"/static/plugins/{self.name}/{file}"
                    assets[asset_type].append(asset_path)
        
        return assets
    
    # Hook methods - can be overridden by plugins
    def on_printer_connected(self, printer_info: Dict[str, Any]):
        """Called when printer connects"""
        pass
    
    def on_printer_disconnected(self):
        """Called when printer disconnects"""
        pass
    
    def on_print_started(self, filename: str):
        """Called when print starts"""
        pass
    
    def on_print_finished(self, filename: str, status: str):
        """Called when print finishes"""
        pass
    
    def on_print_paused(self, filename: str):
        """Called when print is paused"""
        pass
    
    def on_print_resumed(self, filename: str):
        """Called when print is resumed"""
        pass
    
    def on_file_uploaded(self, filename: str, file_size: int):
        """Called when file is uploaded"""
        pass
    
    def on_file_deleted(self, filename: str):
        """Called when file is deleted"""
        pass
    
    def on_status_update(self, status: Dict[str, Any]):
        """Called on every status update"""
        pass
    
    def modify_status_response(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Modify status response before sending to client"""
        return status
    
    def get_toolbar_items(self) -> List[Dict[str, Any]]:
        """Return toolbar items to be added to the interface"""
        return []
    
    def get_status_bar_items(self) -> List[Dict[str, Any]]:
        """Return status bar items to be added to the interface"""
        return []
    
    def get_config_tabs(self) -> List[Dict[str, Any]]:
        """Return configuration tabs for the settings modal"""
        return []
    
    def handle_config_save(self, config_data: Dict[str, Any]) -> bool:
        """Handle configuration save from the settings modal"""
        try:
            self.config.update(config_data)
            return True
        except Exception as e:
            logger.error(f"Error saving config for plugin {self.name}: {e}")
            return False
    
    def __str__(self):
        return f"Plugin: {self.name} v{self.version} by {self.author}"
    
    def __repr__(self):
        return f"<Plugin {self.name} v{self.version}>" 

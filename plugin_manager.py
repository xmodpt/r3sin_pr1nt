#!/usr/bin/env python3
"""
Plugin Manager for Resin Printer Application
Handles plugin discovery, loading, and management
Fixed version with better error handling and debug logging
"""

import importlib.util
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from flask import Flask

from plugins.plugin_base import PluginBase

logger = logging.getLogger(__name__)

class PluginManager:
    """Manages all plugins for the application"""
    
    def __init__(self, plugins_dir: str = "plugins", config_manager=None):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(exist_ok=True)
        self.config_manager = config_manager
        
        # Plugin storage
        self.available_plugins: Dict[str, PluginBase] = {}
        self.loaded_plugins: Dict[str, PluginBase] = {}
        self.plugin_hooks: Dict[str, List[PluginBase]] = {}
        
        # Create __init__.py if it doesn't exist
        init_file = self.plugins_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            
        logger.info(f"Plugin Manager initialized with directory: {self.plugins_dir}")
        logger.info(f"Config manager available: {self.config_manager is not None}")
    
    def discover_plugins(self) -> List[str]:
        """Discover all available plugins"""
        discovered = []
        
        logger.info(f"Discovering plugins in: {self.plugins_dir}")
        logger.info(f"Directory exists: {self.plugins_dir.exists()}")
        
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
            return discovered
        
        try:
            for plugin_dir in self.plugins_dir.iterdir():
                logger.debug(f"Checking directory: {plugin_dir}")
                
                if (plugin_dir.is_dir() and 
                    not plugin_dir.name.startswith('__') and
                    not plugin_dir.name.startswith('.')):
                    
                    plugin_file = plugin_dir / "plugin.py"
                    config_file = plugin_dir / "config.json"
                    
                    logger.debug(f"Plugin file exists: {plugin_file.exists()}")
                    logger.debug(f"Config file exists: {config_file.exists()}")
                    
                    if plugin_file.exists():
                        discovered.append(plugin_dir.name)
                        logger.info(f"Found plugin: {plugin_dir.name}")
                    else:
                        logger.debug(f"Skipping {plugin_dir.name} - no plugin.py found")
        except Exception as e:
            logger.error(f"Error during plugin discovery: {e}")
            logger.exception("Full traceback:")
        
        logger.info(f"Discovered {len(discovered)} plugins: {', '.join(discovered)}")
        return discovered
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin"""
        try:
            logger.info(f"Loading plugin: {plugin_name}")
            
            plugin_dir = self.plugins_dir / plugin_name
            if not plugin_dir.exists():
                logger.error(f"Plugin directory not found: {plugin_dir}")
                return False
            
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                logger.error(f"Plugin file not found: {plugin_file}")
                return False
            
            logger.info(f"Loading plugin from: {plugin_file}")
            
            # Remove from sys.modules if already loaded to force reload
            module_name = f"plugins.{plugin_name}.plugin"
            if module_name in sys.modules:
                logger.info(f"Removing existing module: {module_name}")
                del sys.modules[module_name]
            
            # Import the plugin module
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec is None:
                logger.error(f"Could not create module spec for {plugin_name}")
                return False
                
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules
            sys.modules[module_name] = module
            
            # Execute the module
            spec.loader.exec_module(module)
            logger.info(f"Successfully executed module for {plugin_name}")
            
            # Find the plugin class (should be named Plugin)
            plugin_class = getattr(module, 'Plugin', None)
            if not plugin_class:
                logger.error(f"No Plugin class found in {plugin_name}/plugin.py")
                return False
            
            logger.info(f"Found Plugin class in {plugin_name}")
            
            # Instantiate the plugin
            plugin_instance = plugin_class(plugin_dir)
            logger.info(f"Created plugin instance for {plugin_name}")
            
            # Set configuration if available
            if self.config_manager:
                plugin_config = self.config_manager.get_plugin_config(plugin_name)
                plugin_instance.set_config(plugin_config)
                logger.info(f"Applied config to {plugin_name}: {plugin_config}")
            else:
                logger.warning("No config manager available - using default config")
            
            # Store the plugin
            self.available_plugins[plugin_name] = plugin_instance
            
            logger.info(f"Successfully loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_name}: {e}")
            logger.exception("Full traceback:")
            return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin"""
        try:
            logger.info(f"Enabling plugin: {plugin_name}")
            
            # Load plugin if not already loaded
            if plugin_name not in self.available_plugins:
                logger.info(f"Plugin {plugin_name} not loaded, attempting to load...")
                if not self.load_plugin(plugin_name):
                    logger.error(f"Failed to load plugin {plugin_name}")
                    return False
            
            plugin = self.available_plugins[plugin_name]
            logger.info(f"Plugin instance found: {plugin}")
            
            # Check dependencies
            if not self._check_dependencies(plugin):
                logger.error(f"Dependencies not met for plugin {plugin_name}")
                return False
            
            # Initialize the plugin
            logger.info(f"Initializing plugin {plugin_name}")
            if not plugin.initialize():
                logger.error(f"Plugin {plugin_name} failed to initialize")
                return False
            
            # Mark as enabled
            plugin.enabled = True
            self.loaded_plugins[plugin_name] = plugin
            
            # Register hooks
            self._register_plugin_hooks(plugin)
            
            # Update configuration
            if self.config_manager:
                success = self.config_manager.enable_plugin(plugin_name)
                logger.info(f"Config update success: {success}")
            else:
                logger.warning("No config manager - plugin enable state not saved")
            
            logger.info(f"Plugin {plugin_name} enabled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}")
            logger.exception("Full traceback:")
            return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin"""
        try:
            logger.info(f"Disabling plugin: {plugin_name}")
            
            if plugin_name not in self.loaded_plugins:
                logger.info(f"Plugin {plugin_name} already disabled")
                return True  # Already disabled
            
            plugin = self.loaded_plugins[plugin_name]
            
            # Cleanup the plugin
            try:
                plugin.cleanup()
                logger.info(f"Plugin {plugin_name} cleanup completed")
            except Exception as e:
                logger.error(f"Error during plugin cleanup: {e}")
            
            # Mark as disabled
            plugin.enabled = False
            
            # Unregister hooks
            self._unregister_plugin_hooks(plugin)
            
            # Remove from loaded plugins
            del self.loaded_plugins[plugin_name]
            
            # Update configuration
            if self.config_manager:
                success = self.config_manager.disable_plugin(plugin_name)
                logger.info(f"Config update success: {success}")
            
            logger.info(f"Plugin {plugin_name} disabled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}")
            logger.exception("Full traceback:")
            return False
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin"""
        logger.info(f"Reloading plugin: {plugin_name}")
        
        was_enabled = plugin_name in self.loaded_plugins
        logger.info(f"Plugin was enabled: {was_enabled}")
        
        # Disable if currently enabled
        if was_enabled:
            self.disable_plugin(plugin_name)
        
        # Remove from available plugins
        if plugin_name in self.available_plugins:
            del self.available_plugins[plugin_name]
        
        # Remove from sys.modules to force reload
        module_name = f"plugins.{plugin_name}.plugin"
        if module_name in sys.modules:
            del sys.modules[module_name]
            logger.info(f"Removed module from sys.modules: {module_name}")
        
        # Load and enable if it was previously enabled
        if self.load_plugin(plugin_name):
            if was_enabled:
                return self.enable_plugin(plugin_name)
            return True
        
        return False
    
    def _check_dependencies(self, plugin: PluginBase) -> bool:
        """Check if plugin dependencies are met"""
        for dep in plugin.dependencies:
            if dep not in self.loaded_plugins:
                logger.warning(f"Missing dependency: {dep}")
                return False
        return True
    
    def _register_plugin_hooks(self, plugin: PluginBase):
        """Register plugin hooks"""
        for hook in plugin.hooks:
            if hook not in self.plugin_hooks:
                self.plugin_hooks[hook] = []
            if plugin not in self.plugin_hooks[hook]:
                self.plugin_hooks[hook].append(plugin)
                logger.debug(f"Registered hook {hook} for plugin {plugin.name}")
    
    def _unregister_plugin_hooks(self, plugin: PluginBase):
        """Unregister plugin hooks"""
        for hook_list in self.plugin_hooks.values():
            if plugin in hook_list:
                hook_list.remove(plugin)
    
    def register_blueprints(self, app: Flask):
        """Register all plugin blueprints with Flask app"""
        for plugin in self.loaded_plugins.values():
            try:
                blueprint = plugin.create_blueprint()
                if blueprint:
                    app.register_blueprint(blueprint)
                    logger.info(f"Registered blueprint for plugin {plugin.name}")
            except Exception as e:
                logger.error(f"Error registering blueprint for plugin {plugin.name}: {e}")
    
    def call_hook(self, hook_name: str, *args, **kwargs):
        """Call all plugins registered for a specific hook"""
        if hook_name in self.plugin_hooks:
            for plugin in self.plugin_hooks[hook_name]:
                try:
                    method_name = f"on_{hook_name}"
                    if hasattr(plugin, method_name):
                        method = getattr(plugin, method_name)
                        method(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error calling hook {hook_name} on plugin {plugin.name}: {e}")
    
    def modify_response(self, response_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Allow plugins to modify responses"""
        for plugin in self.loaded_plugins.values():
            try:
                method_name = f"modify_{response_type}_response"
                if hasattr(plugin, method_name):
                    method = getattr(plugin, method_name)
                    data = method(data)
            except Exception as e:
                logger.error(f"Error modifying {response_type} response in plugin {plugin.name}: {e}")
        return data
    
    def get_toolbar_items(self) -> List[Dict[str, Any]]:
        """Get toolbar items from all plugins"""
        items = []
        for plugin in self.loaded_plugins.values():
            try:
                plugin_items = plugin.get_toolbar_items()
                for item in plugin_items:
                    item['plugin'] = plugin.name
                    items.append(item)
            except Exception as e:
                logger.error(f"Error getting toolbar items from plugin {plugin.name}: {e}")
        return items
    
    def get_status_bar_items(self) -> List[Dict[str, Any]]:
        """Get status bar items from all plugins"""
        items = []
        for plugin in self.loaded_plugins.values():
            try:
                plugin_items = plugin.get_status_bar_items()
                for item in plugin_items:
                    item['plugin'] = plugin.name
                    items.append(item)
            except Exception as e:
                logger.error(f"Error getting status bar items from plugin {plugin.name}: {e}")
        return items
    
    def get_config_tabs(self) -> List[Dict[str, Any]]:
        """Get configuration tabs from all plugins"""
        tabs = []
        for plugin in self.loaded_plugins.values():
            try:
                plugin_tabs = plugin.get_config_tabs()
                for tab in plugin_tabs:
                    tab['plugin'] = plugin.name
                    tabs.append(tab)
            except Exception as e:
                logger.error(f"Error getting config tabs from plugin {plugin.name}: {e}")
        return tabs
    
    def get_frontend_assets(self) -> Dict[str, List[str]]:
        """Get all frontend assets from loaded plugins"""
        assets = {"css": [], "js": []}
        for plugin in self.loaded_plugins.values():
            try:
                plugin_assets = plugin.get_frontend_assets()
                for asset_type, files in plugin_assets.items():
                    if asset_type in assets:
                        assets[asset_type].extend(files)
            except Exception as e:
                logger.error(f"Error getting frontend assets from plugin {plugin.name}: {e}")
        return assets
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific plugin"""
        if plugin_name in self.available_plugins:
            return self.available_plugins[plugin_name].get_metadata()
        return None
    
    def get_all_plugins_info(self) -> List[Dict[str, Any]]:
        """Get information about all plugins"""
        plugins_info = []
        
        # Add available plugins
        for name, plugin in self.available_plugins.items():
            info = plugin.get_metadata()
            info['loaded'] = name in self.loaded_plugins
            plugins_info.append(info)
        
        return plugins_info
    
    def initialize_enabled_plugins(self):
        """Initialize all enabled plugins from configuration"""
        if not self.config_manager:
            logger.warning("No config manager available for plugin initialization")
            return
        
        try:
            enabled_plugins = self.config_manager.get_enabled_plugins()
            logger.info(f"Found {len(enabled_plugins)} enabled plugins in config: {enabled_plugins}")
            
            for plugin_name in enabled_plugins:
                logger.info(f"Auto-enabling plugin: {plugin_name}")
                if self.enable_plugin(plugin_name):
                    logger.info(f"Successfully enabled plugin: {plugin_name}")
                else:
                    logger.error(f"Failed to enable plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Error initializing enabled plugins: {e}")
            logger.exception("Full traceback:")
    
    def shutdown_all_plugins(self):
        """Shutdown all loaded plugins"""
        plugin_names = list(self.loaded_plugins.keys())
        for plugin_name in plugin_names:
            logger.info(f"Shutting down plugin: {plugin_name}")
            self.disable_plugin(plugin_name)
        
        logger.info("All plugins shutdown")
    
    def save_plugin_config(self, plugin_name: str, config_data: Dict[str, Any]) -> bool:
        """Save configuration for a specific plugin"""
        try:
            logger.info(f"Saving config for plugin {plugin_name}: {config_data}")
            
            if plugin_name in self.loaded_plugins:
                plugin = self.loaded_plugins[plugin_name]
                if plugin.handle_config_save(config_data):
                    # Save to global config
                    if self.config_manager:
                        success = self.config_manager.set_plugin_config(plugin_name, config_data)
                        logger.info(f"Config saved to manager: {success}")
                        return success
                    return True
            else:
                logger.warning(f"Plugin {plugin_name} not loaded, cannot save config")
                # Still save to config manager even if plugin not loaded
                if self.config_manager:
                    success = self.config_manager.set_plugin_config(plugin_name, config_data)
                    logger.info(f"Config saved to manager (plugin not loaded): {success}")
                    return success
            return False
        except Exception as e:
            logger.error(f"Error saving config for plugin {plugin_name}: {e}")
            logger.exception("Full traceback:")
            return False
#!/usr/bin/env python3
"""
Plugin Installer for Resin Printer Application
Handles installation, uninstallation, and management of plugin packages
"""

import os
import shutil
import zipfile
import json
import tempfile
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class PluginInstaller:
    """Manages plugin installation and uninstallation"""
    
    def __init__(self, plugins_dir: str = "plugins", static_dir: str = "static", templates_dir: str = "templates"):
        self.plugins_dir = Path(plugins_dir)
        self.static_dir = Path(static_dir)
        self.templates_dir = Path(templates_dir)
        self.plugin_static_dir = self.static_dir / "plugins"
        self.plugin_templates_dir = self.templates_dir / "plugins"
        
        # Ensure directories exist
        self.plugins_dir.mkdir(exist_ok=True)
        self.plugin_static_dir.mkdir(exist_ok=True)
        self.plugin_templates_dir.mkdir(exist_ok=True)
    
    def install_plugin_from_zip(self, zip_file_path: str, force_overwrite: bool = False) -> Tuple[bool, str]:
        """Install a plugin from a ZIP file"""
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Extract ZIP file
                with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)
                
                # Find and validate plugin structure
                plugin_info = self._find_and_validate_plugin(temp_path)
                if not plugin_info:
                    return False, "Invalid plugin structure or missing config.json"
                
                plugin_name = plugin_info['name']
                plugin_source_dir = plugin_info['source_dir']
                
                # Check if plugin already exists
                if self._plugin_exists(plugin_name) and not force_overwrite:
                    return False, f"Plugin '{plugin_name}' already exists. Use force_overwrite=True to replace."
                
                # Install the plugin
                success, message = self._install_plugin_files(plugin_name, plugin_source_dir, plugin_info['config'])
                
                if success:
                    logger.info(f"Successfully installed plugin: {plugin_name}")
                    return True, f"Plugin '{plugin_name}' installed successfully"
                else:
                    return False, message
                    
        except Exception as e:
            logger.error(f"Error installing plugin from ZIP: {e}")
            return False, f"Installation failed: {str(e)}"
    
    def install_plugin_from_directory(self, source_dir: str, force_overwrite: bool = False) -> Tuple[bool, str]:
        """Install a plugin from a local directory"""
        try:
            source_path = Path(source_dir)
            if not source_path.exists():
                return False, f"Source directory does not exist: {source_dir}"
            
            # Find and validate plugin structure
            plugin_info = self._find_and_validate_plugin(source_path)
            if not plugin_info:
                return False, "Invalid plugin structure or missing config.json"
            
            plugin_name = plugin_info['name']
            
            # Check if plugin already exists
            if self._plugin_exists(plugin_name) and not force_overwrite:
                return False, f"Plugin '{plugin_name}' already exists. Use force_overwrite=True to replace."
            
            # Install the plugin
            success, message = self._install_plugin_files(plugin_name, source_path, plugin_info['config'])
            
            if success:
                logger.info(f"Successfully installed plugin: {plugin_name}")
                return True, f"Plugin '{plugin_name}' installed successfully"
            else:
                return False, message
                
        except Exception as e:
            logger.error(f"Error installing plugin from directory: {e}")
            return False, f"Installation failed: {str(e)}"
    
    def uninstall_plugin(self, plugin_name: str) -> Tuple[bool, str]:
        """Uninstall a plugin and remove all its files"""
        try:
            if not self._plugin_exists(plugin_name):
                return False, f"Plugin '{plugin_name}' is not installed"
            
            # Load plugin config to understand file locations
            plugin_dir = self.plugins_dir / plugin_name
            config_file = plugin_dir / "config.json"
            
            plugin_config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    plugin_config = json.load(f)
            
            # Remove plugin directory
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
                logger.info(f"Removed plugin directory: {plugin_dir}")
            
            # Remove static files
            plugin_static_dir = self.plugin_static_dir / plugin_name
            if plugin_static_dir.exists():
                shutil.rmtree(plugin_static_dir)
                logger.info(f"Removed plugin static files: {plugin_static_dir}")
            
            # Remove template files
            plugin_template_dir = self.plugin_templates_dir / plugin_name
            if plugin_template_dir.exists():
                shutil.rmtree(plugin_template_dir)
                logger.info(f"Removed plugin template files: {plugin_template_dir}")
            
            # Remove any additional files specified in config
            frontend_assets = plugin_config.get('frontend_assets', {})
            for asset_type, files in frontend_assets.items():
                for file_name in files:
                    asset_path = self.static_dir / asset_type / f"{plugin_name}_{file_name}"
                    if asset_path.exists():
                        asset_path.unlink()
                        logger.info(f"Removed asset file: {asset_path}")
            
            logger.info(f"Successfully uninstalled plugin: {plugin_name}")
            return True, f"Plugin '{plugin_name}' uninstalled successfully"
            
        except Exception as e:
            logger.error(f"Error uninstalling plugin {plugin_name}: {e}")
            return False, f"Uninstallation failed: {str(e)}"
    
    def list_installed_plugins(self) -> List[Dict[str, Any]]:
        """List all installed plugins with their information"""
        plugins = []
        
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith('__'):
                config_file = plugin_dir / "config.json"
                if config_file.exists():
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                        
                        # Calculate plugin size
                        size = self._calculate_directory_size(plugin_dir)
                        
                        # Check for static files
                        static_dir = self.plugin_static_dir / plugin_dir.name
                        if static_dir.exists():
                            size += self._calculate_directory_size(static_dir)
                        
                        plugins.append({
                            'name': config.get('name', plugin_dir.name),
                            'version': config.get('version', 'Unknown'),
                            'author': config.get('author', 'Unknown'),
                            'description': config.get('description', ''),
                            'size': size,
                            'has_static_files': static_dir.exists() if static_dir else False,
                            'dependencies': config.get('dependencies', []),
                            'permissions': config.get('permissions', [])
                        })
                    except Exception as e:
                        logger.error(f"Error reading plugin config for {plugin_dir.name}: {e}")
        
        return plugins
    
    def validate_plugin_package(self, package_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Validate a plugin package before installation"""
        try:
            if package_path.endswith('.zip'):
                # Validate ZIP file
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    
                    with zipfile.ZipFile(package_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_path)
                    
                    plugin_info = self._find_and_validate_plugin(temp_path)
                    if plugin_info:
                        return True, "Valid plugin package", plugin_info['config']
                    else:
                        return False, "Invalid plugin structure", None
            else:
                # Validate directory
                source_path = Path(package_path)
                plugin_info = self._find_and_validate_plugin(source_path)
                if plugin_info:
                    return True, "Valid plugin directory", plugin_info['config']
                else:
                    return False, "Invalid plugin structure", None
                    
        except Exception as e:
            return False, f"Validation failed: {str(e)}", None
    
    def create_plugin_package(self, plugin_name: str, output_path: str) -> Tuple[bool, str]:
        """Create a distributable ZIP package from an installed plugin"""
        try:
            if not self._plugin_exists(plugin_name):
                return False, f"Plugin '{plugin_name}' is not installed"
            
            plugin_dir = self.plugins_dir / plugin_name
            output_file = Path(output_path)
            
            # Create ZIP file
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add plugin directory contents
                for file_path in plugin_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(plugin_dir.parent)
                        zipf.write(file_path, arcname)
                
                # Add static files if they exist
                plugin_static_dir = self.plugin_static_dir / plugin_name
                if plugin_static_dir.exists():
                    for file_path in plugin_static_dir.rglob('*'):
                        if file_path.is_file():
                            arcname = Path("static") / "plugins" / file_path.relative_to(self.plugin_static_dir)
                            zipf.write(file_path, arcname)
                
                # Add template files if they exist
                plugin_template_dir = self.plugin_templates_dir / plugin_name
                if plugin_template_dir.exists():
                    for file_path in plugin_template_dir.rglob('*'):
                        if file_path.is_file():
                            arcname = Path("templates") / "plugins" / file_path.relative_to(self.plugin_templates_dir)
                            zipf.write(file_path, arcname)
            
            return True, f"Plugin package created: {output_file}"
            
        except Exception as e:
            logger.error(f"Error creating plugin package: {e}")
            return False, f"Package creation failed: {str(e)}"
    
    def _find_and_validate_plugin(self, source_path: Path) -> Optional[Dict[str, Any]]:
        """Find and validate plugin structure in a directory"""
        # Look for plugin.py and config.json in the source directory or subdirectories
        for potential_plugin_dir in [source_path] + list(source_path.iterdir()):
            if potential_plugin_dir.is_dir():
                config_file = potential_plugin_dir / "config.json"
                plugin_file = potential_plugin_dir / "plugin.py"
                
                if config_file.exists() and plugin_file.exists():
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                        
                        # Validate required fields
                        required_fields = ['name', 'version', 'author', 'description']
                        if all(field in config for field in required_fields):
                            return {
                                'name': config['name'],
                                'source_dir': potential_plugin_dir,
                                'config': config
                            }
                    except Exception as e:
                        logger.error(f"Error reading config.json: {e}")
                        continue
        
        return None
    
    def _plugin_exists(self, plugin_name: str) -> bool:
        """Check if a plugin is already installed"""
        plugin_dir = self.plugins_dir / plugin_name
        return plugin_dir.exists() and (plugin_dir / "plugin.py").exists()
    
    def _install_plugin_files(self, plugin_name: str, source_dir: Path, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Install plugin files to appropriate locations"""
        try:
            # Install main plugin directory
            target_plugin_dir = self.plugins_dir / plugin_name
            if target_plugin_dir.exists():
                shutil.rmtree(target_plugin_dir)
            
            shutil.copytree(source_dir, target_plugin_dir)
            logger.info(f"Copied plugin files to: {target_plugin_dir}")
            
            # Install static files if they exist in the package
            source_static_dir = None
            
            # Look for static files in the source
            potential_static_dirs = [
                source_dir.parent / "static" / "plugins" / plugin_name,
                source_dir / "static",
                source_dir / f"static_{plugin_name}"
            ]
            
            for static_dir in potential_static_dirs:
                if static_dir.exists():
                    source_static_dir = static_dir
                    break
            
            if source_static_dir:
                target_static_dir = self.plugin_static_dir / plugin_name
                if target_static_dir.exists():
                    shutil.rmtree(target_static_dir)
                shutil.copytree(source_static_dir, target_static_dir)
                logger.info(f"Copied static files to: {target_static_dir}")
            
            # Install template files if they exist
            source_template_dir = None
            
            potential_template_dirs = [
                source_dir.parent / "templates" / "plugins" / plugin_name,
                source_dir / "templates",
                source_dir / f"templates_{plugin_name}"
            ]
            
            for template_dir in potential_template_dirs:
                if template_dir.exists():
                    source_template_dir = template_dir
                    break
            
            if source_template_dir:
                target_template_dir = self.plugin_templates_dir / plugin_name
                if target_template_dir.exists():
                    shutil.rmtree(target_template_dir)
                shutil.copytree(source_template_dir, target_template_dir)
                logger.info(f"Copied template files to: {target_template_dir}")
            
            return True, "Plugin files installed successfully"
            
        except Exception as e:
            logger.error(f"Error installing plugin files: {e}")
            return False, f"File installation failed: {str(e)}"
    
    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of a directory in bytes"""
        total_size = 0
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Error calculating directory size: {e}")
        
        return total_size
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB" 

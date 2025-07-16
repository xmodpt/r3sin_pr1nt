#!/usr/bin/env python3
"""
Configuration Routes for Resin Printer Application
Handles API endpoints for configuration and plugin management
"""

import logging
from flask import Blueprint, request, jsonify, send_from_directory
from pathlib import Path

logger = logging.getLogger(__name__)

def create_config_routes(config_manager, plugin_manager):
    """Create configuration routes blueprint"""
    
    config_bp = Blueprint('config', __name__, url_prefix='/api/config')
    
    @config_bp.route('/app', methods=['GET'])
    def get_app_config():
        """Get application configuration"""
        try:
            section = request.args.get('section')
            config = config_manager.get_app_config(section)
            return jsonify({'success': True, 'config': config})
        except Exception as e:
            logger.error(f"Error getting app config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/app', methods=['POST'])
    def set_app_config():
        """Set application configuration"""
        try:
            data = request.get_json()
            section = data.get('section')
            key = data.get('key')
            value = data.get('value')
            
            if not section or not key:
                return jsonify({'success': False, 'error': 'Section and key are required'})
            
            success = config_manager.set_app_config(section, key, value)
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error setting app config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/app/bulk', methods=['POST'])
    def set_app_config_bulk():
        """Set multiple application configuration values"""
        try:
            data = request.get_json()
            configs = data.get('configs', [])
            
            results = []
            for config_item in configs:
                section = config_item.get('section')
                key = config_item.get('key')
                value = config_item.get('value')
                
                if section and key:
                    success = config_manager.set_app_config(section, key, value)
                    results.append({
                        'section': section,
                        'key': key,
                        'success': success
                    })
            
            return jsonify({'success': True, 'results': results})
            
        except Exception as e:
            logger.error(f"Error setting bulk app config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins', methods=['GET'])
    def get_plugins_config():
        """Get plugin configuration"""
        try:
            plugin_name = request.args.get('plugin')
            config = config_manager.get_plugin_config(plugin_name)
            return jsonify({'success': True, 'config': config})
        except Exception as e:
            logger.error(f"Error getting plugin config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/<plugin_name>', methods=['POST'])
    def set_plugin_config(plugin_name):
        """Set plugin configuration"""
        try:
            data = request.get_json()
            config_data = data.get('config', {})
            
            success = plugin_manager.save_plugin_config(plugin_name, config_data)
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error setting plugin config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/list', methods=['GET'])
    def list_plugins():
        """List all available plugins"""
        try:
            # Discover plugins first
            discovered_plugins = plugin_manager.discover_plugins()
            logger.info(f"API: Discovered plugins: {discovered_plugins}")
            
            # Try to load each discovered plugin if not already loaded
            for plugin_name in discovered_plugins:
                if plugin_name not in plugin_manager.available_plugins:
                    logger.info(f"API: Loading plugin {plugin_name}")
                    plugin_manager.load_plugin(plugin_name)
            
            plugins_info = plugin_manager.get_all_plugins_info()
            logger.info(f"API: Returning {len(plugins_info)} plugins")
            
            return jsonify({'success': True, 'plugins': plugins_info})
            
        except Exception as e:
            logger.error(f"Error listing plugins: {e}")
            logger.exception("Full traceback:")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/<plugin_name>/enable', methods=['POST'])
    def enable_plugin(plugin_name):
        """Enable a plugin"""
        try:
            success = plugin_manager.enable_plugin(plugin_name)
            if success:
                return jsonify({'success': True, 'message': f'Plugin {plugin_name} enabled'})
            else:
                return jsonify({'success': False, 'error': f'Failed to enable plugin {plugin_name}'})
                
        except Exception as e:
            logger.error(f"Error enabling plugin {plugin_name}: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/<plugin_name>/disable', methods=['POST'])
    def disable_plugin(plugin_name):
        """Disable a plugin"""
        try:
            success = plugin_manager.disable_plugin(plugin_name)
            if success:
                return jsonify({'success': True, 'message': f'Plugin {plugin_name} disabled'})
            else:
                return jsonify({'success': False, 'error': f'Failed to disable plugin {plugin_name}'})
                
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_name}: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/<plugin_name>/reload', methods=['POST'])
    def reload_plugin(plugin_name):
        """Reload a plugin"""
        try:
            success = plugin_manager.reload_plugin(plugin_name)
            if success:
                return jsonify({'success': True, 'message': f'Plugin {plugin_name} reloaded'})
            else:
                return jsonify({'success': False, 'error': f'Failed to reload plugin {plugin_name}'})
                
        except Exception as e:
            logger.error(f"Error reloading plugin {plugin_name}: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/plugins/<plugin_name>/info', methods=['GET'])
    def get_plugin_info(plugin_name):
        """Get plugin information"""
        try:
            info = plugin_manager.get_plugin_info(plugin_name)
            if info:
                return jsonify({'success': True, 'plugin': info})
            else:
                return jsonify({'success': False, 'error': f'Plugin {plugin_name} not found'})
                
        except Exception as e:
            logger.error(f"Error getting plugin info {plugin_name}: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/reset', methods=['POST'])
    def reset_config():
        """Reset configuration to defaults"""
        try:
            data = request.get_json()
            section = data.get('section')  # 'app', 'plugins', or None for all
            
            success = config_manager.reset_to_defaults(section)
            return jsonify({'success': success})
            
        except Exception as e:
            logger.error(f"Error resetting config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/export', methods=['GET'])
    def export_config():
        """Export configuration"""
        try:
            export_path = "/tmp/printer_config_export.json"
            success = config_manager.export_config(export_path)
            
            if success:
                return send_from_directory(
                    "/tmp", 
                    "printer_config_export.json",
                    as_attachment=True,
                    download_name="printer_config.json"
                )
            else:
                return jsonify({'success': False, 'error': 'Failed to export configuration'})
                
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/import', methods=['POST'])
    def import_config():
        """Import configuration"""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'})
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'})
            
            # Save uploaded file temporarily
            import_path = "/tmp/printer_config_import.json"
            file.save(import_path)
            
            # Import configuration
            success = config_manager.import_config(import_path)
            
            # Cleanup temp file
            Path(import_path).unlink(missing_ok=True)
            
            if success:
                return jsonify({'success': True, 'message': 'Configuration imported successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to import configuration'})
                
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/ui/toolbar_items', methods=['GET'])
    def get_toolbar_items():
        """Get toolbar items from plugins"""
        try:
            items = plugin_manager.get_toolbar_items()
            return jsonify({'success': True, 'items': items})
        except Exception as e:
            logger.error(f"Error getting toolbar items: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/ui/status_bar_items', methods=['GET'])
    def get_status_bar_items():
        """Get status bar items from plugins"""
        try:
            items = plugin_manager.get_status_bar_items()
            return jsonify({'success': True, 'items': items})
        except Exception as e:
            logger.error(f"Error getting status bar items: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/ui/config_tabs', methods=['GET'])
    def get_config_tabs():
        """Get configuration tabs from plugins"""
        try:
            tabs = plugin_manager.get_config_tabs()
            return jsonify({'success': True, 'tabs': tabs})
        except Exception as e:
            logger.error(f"Error getting config tabs: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @config_bp.route('/ui/frontend_assets', methods=['GET'])
    def get_frontend_assets():
        """Get frontend assets from plugins"""
        try:
            assets = plugin_manager.get_frontend_assets()
            return jsonify({'success': True, 'assets': assets})
        except Exception as e:
            logger.error(f"Error getting frontend assets: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    return config_bp
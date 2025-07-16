#!/usr/bin/env python3
"""
Hello World Plugin - Example plugin for Resin Printer Application
Demonstrates basic plugin functionality and adds "Hello World" to status bar
"""

import logging
from typing import Dict, Any, List
from flask import jsonify
import sys
import os

# Add the parent directory to Python path so we can import plugin_base
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.plugin_base import PluginBase

logger = logging.getLogger(__name__)

class Plugin(PluginBase):
    """Hello World Plugin - Example implementation"""
    
    def initialize(self) -> bool:
        """Initialize the Hello World plugin"""
        try:
            logger.info("Hello World plugin initializing...")
            
            # Set default configuration if not set
            if not self.config:
                self.config = {
                    "message": "Hello World",
                    "show_in_status": True,
                    "show_time": True,
                    "color": "#4caf50"
                }
            
            logger.info("Hello World plugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Hello World plugin: {e}")
            return False
    
    def cleanup(self):
        """Cleanup when plugin is disabled"""
        logger.info("Hello World plugin cleaning up...")
        # Nothing special to cleanup for this simple plugin
    
    def get_status_bar_items(self) -> List[Dict[str, Any]]:
        """Add Hello World message to status bar"""
        if not self.get_config("show_in_status", True):
            return []
        
        message = self.get_config("message", "Hello World")
        show_time = self.get_config("show_time", True)
        color = self.get_config("color", "#4caf50")
        
        # Add timestamp if enabled
        if show_time:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            display_message = f"{message} ({timestamp})"
        else:
            display_message = message
        
        return [{
            "id": "hello_world_message",
            "type": "text",
            "content": display_message,
            "style": {
                "color": color,
                "font-weight": "600",
                "font-size": "0.85rem"
            },
            "tooltip": f"Hello World Plugin - {self.version}",
            "priority": 100  # Lower numbers = higher priority
        }]
    
    def get_config_tabs(self) -> List[Dict[str, Any]]:
        """Provide configuration tab for settings modal"""
        return [{
            "id": "hello_world_config",
            "title": "Hello World",
            "icon": "👋",
            "content": {
                "type": "form",
                "fields": [
                    {
                        "name": "message",
                        "label": "Message",
                        "type": "text",
                        "value": self.get_config("message", "Hello World"),
                        "placeholder": "Enter your message",
                        "required": True,
                        "help": "The message to display in the status bar"
                    },
                    {
                        "name": "show_in_status",
                        "label": "Show in Status Bar",
                        "type": "checkbox",
                        "value": self.get_config("show_in_status", True),
                        "help": "Whether to show the message in the status bar"
                    },
                    {
                        "name": "show_time",
                        "label": "Show Timestamp",
                        "type": "checkbox",
                        "value": self.get_config("show_time", True),
                        "help": "Include current time with the message"
                    },
                    {
                        "name": "color",
                        "label": "Text Color",
                        "type": "color",
                        "value": self.get_config("color", "#4caf50"),
                        "help": "Color of the text in the status bar"
                    }
                ]
            }
        }]
    
    def handle_config_save(self, config_data: Dict[str, Any]) -> bool:
        """Handle configuration save from settings modal"""
        try:
            # Validate configuration
            if "message" not in config_data or not config_data["message"].strip():
                logger.error("Message cannot be empty")
                return False
            
            # Update configuration
            self.config.update(config_data)
            logger.info(f"Hello World plugin configuration updated: {config_data}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Hello World plugin config: {e}")
            return False
    
    def register_routes(self):
        """Register plugin-specific API routes"""
        if not self.blueprint:
            return
        
        @self.blueprint.route('/info')
        def get_plugin_info():
            """Get plugin information"""
            return jsonify({
                "name": self.name,
                "version": self.version,
                "author": self.author,
                "description": self.description,
                "message": self.get_config("message", "Hello World"),
                "enabled": self.enabled
            })
        
        @self.blueprint.route('/message')
        def get_message():
            """Get current message"""
            return jsonify({
                "message": self.get_config("message", "Hello World"),
                "show_time": self.get_config("show_time", True),
                "color": self.get_config("color", "#4caf50")
            })
        
        @self.blueprint.route('/test')
        def test_endpoint():
            """Test endpoint"""
            return jsonify({
                "status": "success",
                "message": "Hello World plugin is working!",
                "timestamp": __import__('datetime').datetime.now().isoformat()
            })
    
    def on_printer_connected(self, printer_info: Dict[str, Any]):
        """Called when printer connects"""
        logger.info(f"Hello World plugin: Printer connected - {printer_info}")
    
    def on_printer_disconnected(self):
        """Called when printer disconnects"""
        logger.info("Hello World plugin: Printer disconnected")
    
    def on_print_started(self, filename: str):
        """Called when print starts"""
        logger.info(f"Hello World plugin: Print started - {filename}")
    
    def on_print_finished(self, filename: str, status: str):
        """Called when print finishes"""
        logger.info(f"Hello World plugin: Print finished - {filename} ({status})")
    
    def on_status_update(self, status: Dict[str, Any]):
        """Called on every status update"""
        # Don't log this as it's called very frequently
        pass
    
    def modify_status_response(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Modify status response to include plugin info"""
        # Add plugin status to the response
        if "plugins" not in status:
            status["plugins"] = {}
        
        status["plugins"]["hello_world"] = {
            "enabled": self.enabled,
            "message": self.get_config("message", "Hello World"),
            "version": self.version
        }
        
        return status
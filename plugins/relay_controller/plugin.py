#!/usr/bin/env python3
"""
Relay Controller Plugin - GPIO relay control for Resin Printer Application
Integrates seamlessly with the main app's card layout and toolbar
"""

import logging
import sys
import os
from typing import Dict, Any, List
from flask import jsonify, request
import json

# Add the parent directory to Python path so we can import plugin_base
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.plugin_base import PluginBase

# Try to import GPIO, fallback to simulation mode
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = logging.getLogger(__name__)

class Plugin(PluginBase):
    """Relay Controller Plugin"""
    
    def __init__(self, plugin_dir):
        super().__init__(plugin_dir)
        self.relay_states = {}
        self.gpio_initialized = False
        
    def initialize(self) -> bool:
        """Initialize the Relay Controller plugin"""
        try:
            logger.info("Relay Controller plugin initializing...")
            
            # Set default configuration if not set
            if not self.config:
                self.config = {
                    "relay_1": {
                        "enabled": True,
                        "gpio": 22,
                        "behavior": "NO",
                        "name": "UV Light",
                        "icon": "fas fa-lightbulb",
                        "invert_logic": False
                    },
                    "relay_2": {
                        "enabled": True,
                        "gpio": 23,
                        "behavior": "NO",
                        "name": "Exhaust Fan",
                        "icon": "fas fa-fan",
                        "invert_logic": False
                    },
                    "relay_3": {
                        "enabled": True,
                        "gpio": 24,
                        "behavior": "NO",
                        "name": "Wash Station",
                        "icon": "fas fa-shower",
                        "invert_logic": False
                    },
                    "relay_4": {
                        "enabled": True,
                        "gpio": 25,
                        "behavior": "NO",
                        "name": "Curing Light",
                        "icon": "fas fa-fire",
                        "invert_logic": False
                    },
                    "display_mode": "toolbar",  # toolbar, cards, both
                    "show_in_status": True
                }
            
            # Initialize GPIO
            self._setup_gpio()
            
            logger.info("Relay Controller plugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Relay Controller plugin: {e}")
            return False
    
    def cleanup(self):
        """Cleanup when plugin is disabled"""
        logger.info("Relay Controller plugin cleaning up...")
        self._cleanup_gpio()
    
    def _setup_gpio(self):
        """Initialize GPIO settings"""
        if not GPIO_AVAILABLE:
            logger.warning("GPIO not available - running in simulation mode")
            for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
                relay_config = self.config.get(relay_id, {})
                if relay_config.get('enabled', False):
                    if relay_config.get('behavior', 'NO') == 'NO':
                        self.relay_states[relay_id] = False
                    else:
                        self.relay_states[relay_id] = True
            return
        
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
                relay_config = self.config.get(relay_id, {})
                if relay_config.get('enabled', False):
                    gpio_pin = relay_config.get('gpio', 18)
                    logger.info(f"Setting up GPIO pin {gpio_pin} for {relay_id}")
                    
                    GPIO.setup(gpio_pin, GPIO.OUT)
                    
                    if relay_config.get('behavior', 'NO') == 'NO':
                        GPIO.output(gpio_pin, GPIO.LOW)
                        self.relay_states[relay_id] = False
                    else:
                        GPIO.output(gpio_pin, GPIO.LOW)
                        self.relay_states[relay_id] = True
            
            self.gpio_initialized = True
            logger.info("GPIO setup completed")
                        
        except Exception as e:
            logger.error(f"Error setting up GPIO: {e}")
    
    def _cleanup_gpio(self):
        """Clean up GPIO resources"""
        if GPIO_AVAILABLE and self.gpio_initialized:
            try:
                logger.info("Cleaning up GPIO...")
                for relay_id in self.relay_states:
                    self._set_relay_state(relay_id, False)
                GPIO.cleanup()
                logger.info("GPIO cleanup completed")
            except Exception as e:
                logger.error(f"Error during GPIO cleanup: {e}")
        
        self.gpio_initialized = False
    
    def _get_display_state(self, relay_id: str, actual_state: bool) -> bool:
        """Get the display state based on actual state and invert logic setting"""
        relay_config = self.config.get(relay_id, {})
        invert_logic = relay_config.get('invert_logic', False)
        return not actual_state if invert_logic else actual_state
    
    def _set_relay_state(self, relay_id: str, state: bool) -> bool:
        """Set relay state based on configuration"""
        relay_config = self.config.get(relay_id)
        
        if not relay_config or not relay_config.get('enabled', False):
            logger.warning(f"Relay {relay_id} not enabled or not found")
            return False
        
        if not GPIO_AVAILABLE:
            logger.info(f"Simulation mode: Setting {relay_id} to {'ON' if state else 'OFF'}")
            self.relay_states[relay_id] = state
            return True
        
        try:
            gpio_pin = relay_config.get('gpio', 18)
            behavior = relay_config.get('behavior', 'NO')
            
            if behavior == 'NO':
                gpio_state = GPIO.HIGH if state else GPIO.LOW
                GPIO.output(gpio_pin, gpio_state)
            else:
                gpio_state = GPIO.LOW if state else GPIO.HIGH
                GPIO.output(gpio_pin, gpio_state)
            
            self.relay_states[relay_id] = state
            logger.debug(f"Set {relay_id} to {'ON' if state else 'OFF'}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting relay {relay_id}: {e}")
            return False
    
    def get_toolbar_items(self) -> List[Dict[str, Any]]:
        """Return toolbar items for relay controls"""
        if self.config.get('display_mode') not in ['toolbar', 'both']:
            return []
        
        items = []
        
        for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
            relay_config = self.config.get(relay_id, {})
            if relay_config.get('enabled', False):
                actual_state = self.relay_states.get(relay_id, False)
                display_state = self._get_display_state(relay_id, actual_state)
                
                items.append({
                    "id": f"relay_toolbar_{relay_id}",
                    "type": "button",
                    "content": f'<i class="{relay_config.get("icon", "fas fa-power-off")}"></i>',
                    "title": relay_config.get('name', relay_id),
                    "onclick": f"toggleRelay('{relay_id}')",
                    "class": f"relay-toolbar-btn {'relay-on' if display_state else 'relay-off'}",
                    "style": {
                        "color": "#28a745" if display_state else "#c7c7c7",
                        "font-size": "1.2rem",
                        "cursor": "pointer",
                        "padding": "8px",
                        "border-radius": "4px",
                        "border": "1px solid #555",
                        "background": "#2d5a31" if display_state else "#3a3a3a",
                        "transition": "all 0.3s ease",
                        "width": "40px",
                        "height": "40px",
                        "display": "flex",
                        "align-items": "center",
                        "justify-content": "center",
                        "margin": "0 4px"
                    },
                    "priority": 200 + int(relay_id.split('_')[1])
                })
        
        return items
    
    def get_card_items(self) -> List[Dict[str, Any]]:
        """Return card items to be inserted into main app layout"""
        if self.config.get('display_mode') not in ['cards', 'both']:
            return []
        
        # Create relay control card that integrates with main app
        enabled_relays = []
        for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
            relay_config = self.config.get(relay_id, {})
            if relay_config.get('enabled', False):
                actual_state = self.relay_states.get(relay_id, False)
                display_state = self._get_display_state(relay_id, actual_state)
                enabled_relays.append({
                    'id': relay_id,
                    'name': relay_config.get('name', relay_id),
                    'icon': relay_config.get('icon', 'fas fa-power-off'),
                    'state': display_state
                })
        
        if not enabled_relays:
            return []
        
        # Generate HTML for relay card
        relay_buttons_html = ""
        for relay in enabled_relays:
            state_class = "relay-on" if relay['state'] else "relay-off"
            state_text = "ON" if relay['state'] else "OFF"
            relay_buttons_html += f'''
                <div class="relay-card-item">
                    <button class="relay-card-btn {state_class}" onclick="toggleRelay('{relay['id']}')" 
                            id="card-{relay['id']}" title="{relay['name']}">
                        <i class="relay-card-icon {relay['icon']}"></i>
                        <div class="relay-card-name">{relay['name']}</div>
                        <div class="relay-card-status">{state_text}</div>
                    </button>
                </div>
            '''
        
        card_html = f'''
            <div class="card">
                <div class="card-header">
                    <div class="card-header-left">🔌 Relay Control</div>
                </div>
                <div class="relay-card-grid">
                    {relay_buttons_html}
                </div>
            </div>
        '''
        
        return [{
            "id": "relay_control_card",
            "type": "card",
            "content": card_html,
            "position": "after_status",  # Insert after status card
            "priority": 150
        }]
    
    def get_status_bar_items(self) -> List[Dict[str, Any]]:
        """Add relay status to status bar"""
        if not self.config.get('show_in_status', True):
            return []
        
        enabled_relays = []
        on_count = 0
        
        for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
            relay_config = self.config.get(relay_id, {})
            if relay_config.get('enabled', False):
                enabled_relays.append(relay_config.get('name', relay_id))
                actual_state = self.relay_states.get(relay_id, False)
                display_state = self._get_display_state(relay_id, actual_state)
                if display_state:
                    on_count += 1
        
        if not enabled_relays:
            return []
        
        status_text = f"Relays: {on_count}/{len(enabled_relays)} ON"
        
        return [{
            "id": "relay_status",
            "type": "text",
            "content": status_text,
            "style": {
                "color": "#28a745" if on_count > 0 else "#c7c7c7",
                "font-weight": "600",
                "font-size": "0.8rem"
            },
            "tooltip": f"Relay Controller - {', '.join(enabled_relays)}",
            "priority": 150
        }]
    
    def get_frontend_assets(self) -> Dict[str, List[str]]:
        """Get CSS/JS for relay cards"""
        return {
            "css": ["relay_controller.css"],
            "js": ["relay_controller.js"]
        }
    
    def get_config_tabs(self) -> List[Dict[str, Any]]:
        """Provide configuration tab for settings modal"""
        return [{
            "id": "relay_controller_config",
            "title": "Relay Controller",
            "icon": "🔌",
            "content": {
                "type": "form",
                "fields": [
                    {
                        "name": "display_mode",
                        "label": "Display Mode",
                        "type": "select",
                        "value": self.config.get("display_mode", "toolbar"),
                        "options": [
                            {"value": "toolbar", "label": "Toolbar Only - Small buttons in top toolbar"},
                            {"value": "cards", "label": "Cards - Large buttons in main interface"},
                            {"value": "both", "label": "Both - Toolbar + Cards"}
                        ],
                        "help": "How to display relay controls in the interface"
                    },
                    {
                        "name": "show_in_status",
                        "label": "Show Status Summary",
                        "type": "checkbox",
                        "value": self.config.get("show_in_status", True),
                        "help": "Show relay count in status bar"
                    }
                ] + self._generate_relay_config_fields()
            }
        }]
    
    def _generate_relay_config_fields(self) -> List[Dict[str, Any]]:
        """Generate configuration fields for all relays"""
        fields = []
        
        for i in range(1, 5):
            relay_id = f"relay_{i}"
            relay_config = self.config.get(relay_id, {})
            
            fields.extend([
                {
                    "name": f"{relay_id}_enabled",
                    "label": f"Relay {i} Enabled",
                    "type": "checkbox",
                    "value": relay_config.get("enabled", False),
                    "help": f"Enable/disable relay {i}"
                },
                {
                    "name": f"{relay_id}_name",
                    "label": f"Relay {i} Name",
                    "type": "text",
                    "value": relay_config.get("name", f"Relay {i}"),
                    "help": f"Display name for relay {i}"
                },
                {
                    "name": f"{relay_id}_gpio",
                    "label": f"Relay {i} GPIO Pin",
                    "type": "number",
                    "value": relay_config.get("gpio", 18 + i),
                    "min": 1,
                    "max": 40,
                    "help": f"GPIO pin number for relay {i}"
                },
                {
                    "name": f"{relay_id}_icon",
                    "label": f"Relay {i} Icon",
                    "type": "select",
                    "value": relay_config.get("icon", "fas fa-power-off"),
                    "options": [
                        {"value": "fas fa-lightbulb", "label": "💡 Light Bulb"},
                        {"value": "fas fa-fan", "label": "🌀 Fan"},
                        {"value": "fas fa-shower", "label": "🚿 Wash/Pump"},
                        {"value": "fas fa-fire", "label": "🔥 Heater/Curing"},
                        {"value": "fas fa-plug", "label": "🔌 Power"},
                        {"value": "fas fa-camera", "label": "📷 Camera"},
                        {"value": "fas fa-bell", "label": "🔔 Alarm"},
                        {"value": "fas fa-power-off", "label": "⚡ Generic Power"}
                    ],
                    "help": f"Icon to display for relay {i}"
                },
                {
                    "name": f"{relay_id}_behavior",
                    "label": f"Relay {i} Type",
                    "type": "select",
                    "value": relay_config.get("behavior", "NO"),
                    "options": [
                        {"value": "NO", "label": "NO (Normally Open)"},
                        {"value": "NC", "label": "NC (Normally Closed)"}
                    ],
                    "help": f"Relay {i} electrical behavior"
                },
                {
                    "name": f"{relay_id}_invert_logic",
                    "label": f"Relay {i} Invert Display",
                    "type": "checkbox",
                    "value": relay_config.get("invert_logic", False),
                    "help": f"Invert the display logic for relay {i}"
                }
            ])
        
        return fields
    
    def handle_config_save(self, config_data: Dict[str, Any]) -> bool:
        """Handle configuration save from settings modal"""
        try:
            # Update relay configurations
            for i in range(1, 5):
                relay_id = f"relay_{i}"
                self.config[relay_id] = {
                    "enabled": config_data.get(f"{relay_id}_enabled", False),
                    "name": config_data.get(f"{relay_id}_name", f"Relay {i}"),
                    "gpio": int(config_data.get(f"{relay_id}_gpio", 18 + i)),
                    "icon": config_data.get(f"{relay_id}_icon", "fas fa-power-off"),
                    "behavior": config_data.get(f"{relay_id}_behavior", "NO"),
                    "invert_logic": config_data.get(f"{relay_id}_invert_logic", False)
                }
            
            # Update display settings
            self.config["display_mode"] = config_data.get("display_mode", "toolbar")
            self.config["show_in_status"] = config_data.get("show_in_status", True)
            
            # Reinitialize GPIO with new configuration
            self._cleanup_gpio()
            self.relay_states.clear()
            self._setup_gpio()
            
            logger.info("Relay Controller configuration updated")
            return True
            
        except Exception as e:
            logger.error(f"Error saving Relay Controller config: {e}")
            return False
    
    def register_routes(self):
        """Register plugin-specific API routes"""
        if not self.blueprint:
            return
        
        @self.blueprint.route('/toggle_relay/<relay_id>')
        def toggle_relay(relay_id):
            """Toggle relay state"""
            current_state = self.relay_states.get(relay_id, False)
            new_state = not current_state
            
            if self._set_relay_state(relay_id, new_state):
                display_state = self._get_display_state(relay_id, new_state)
                relay_config = self.config.get(relay_id, {})
                relay_name = relay_config.get('name', relay_id)
                
                return jsonify({
                    'success': True,
                    'relay_id': relay_id,
                    'state': display_state,
                    'actual_state': new_state,
                    'message': f'{relay_name} turned {"ON" if display_state else "OFF"}'
                })
            else:
                display_state = self._get_display_state(relay_id, current_state)
                return jsonify({
                    'success': False,
                    'relay_id': relay_id,
                    'state': display_state,
                    'message': f'Failed to toggle {relay_id}'
                }), 500
        
        @self.blueprint.route('/set_relay/<relay_id>/<state>')
        def set_relay(relay_id, state):
            """Set specific relay state"""
            display_state = state.lower() in ['on', 'true', '1']
            
            # Calculate actual state needed based on invert logic
            relay_config = self.config.get(relay_id, {})
            invert_logic = relay_config.get('invert_logic', False)
            
            actual_state = not display_state if invert_logic else display_state
            
            if self._set_relay_state(relay_id, actual_state):
                relay_name = relay_config.get('name', relay_id)
                return jsonify({
                    'success': True,
                    'relay_id': relay_id,
                    'state': display_state,
                    'actual_state': actual_state,
                    'message': f'{relay_name} set to {"ON" if display_state else "OFF"}'
                })
            else:
                current_display_state = self._get_display_state(relay_id, self.relay_states.get(relay_id, False))
                return jsonify({
                    'success': False,
                    'relay_id': relay_id,
                    'state': current_display_state,
                    'message': f'Failed to set {relay_id}'
                }), 500
        
        @self.blueprint.route('/get_status')
        def get_status():
            """Get current status of all relays"""
            status = {}
            for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
                relay_config = self.config.get(relay_id, {})
                if relay_config.get('enabled', False):
                    actual_state = self.relay_states.get(relay_id, False)
                    display_state = self._get_display_state(relay_id, actual_state)
                    
                    status[relay_id] = {
                        'state': display_state,
                        'actual_state': actual_state,
                        'name': relay_config.get('name', relay_id),
                        'gpio': relay_config.get('gpio', 18),
                        'icon': relay_config.get('icon', 'fas fa-power-off'),
                        'invert_logic': relay_config.get('invert_logic', False)
                    }
            
            return jsonify(status)
    
    def modify_status_response(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Add relay information to status response"""
        if "plugins" not in status:
            status["plugins"] = {}
        
        relay_summary = {}
        for relay_id in ['relay_1', 'relay_2', 'relay_3', 'relay_4']:
            relay_config = self.config.get(relay_id, {})
            if relay_config.get('enabled', False):
                actual_state = self.relay_states.get(relay_id, False)
                display_state = self._get_display_state(relay_id, actual_state)
                relay_summary[relay_id] = {
                    'name': relay_config.get('name', relay_id),
                    'state': display_state
                }
        
        status["plugins"]["relay_controller"] = {
            "enabled": self.enabled,
            "relays": relay_summary,
            "version": self.version
        }
        
        return status
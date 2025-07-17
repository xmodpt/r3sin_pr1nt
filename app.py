#!/usr/bin/env python3
"""
Resin Printer Control Application using Chituboard Communication Protocol
Based on Chituboard plugin for proper firmware communication
Now with modular file management and plugin system
"""

import os
import shutil
import subprocess
import time
import serial
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import logging
import tempfile
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# Import our new modular components
from file_manager import FileManager
from file_routes import create_file_routes
from config_manager import ConfigManager
from plugin_manager import PluginManager
from config_routes import create_config_routes

# Configuration - Use your working mount point
USB_DRIVE_MOUNT = Path("/mnt/usb_share")  # Your working USB mount point
USB_DRIVE_MOUNT.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'.ctb', '.cbddlp', '.pwmx', '.pwmo', '.pwms', '.pws', '.pw0', '.pwx'}

# Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# Add logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize managers
config_manager = ConfigManager()
file_manager = FileManager(USB_DRIVE_MOUNT, ALLOWED_EXTENSIONS)
plugin_manager = PluginManager(config_manager=config_manager)

# Register blueprints
file_blueprint = create_file_routes(file_manager)
config_blueprint = create_config_routes(config_manager, plugin_manager)
app.register_blueprint(file_blueprint)
app.register_blueprint(config_blueprint)

# Printer State Enums (from Chituboard approach)
class PrinterState(Enum):
    IDLE = "IDLE"
    PRINTING = "PRINTING"
    PAUSED = "PAUSED" 
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

@dataclass
class PrintStatus:
    state: PrinterState = PrinterState.IDLE
    progress_percent: float = 0.0
    current_layer: int = 0
    total_layers: int = 0
    current_byte: int = 0
    total_bytes: int = 0

class ChituboardPrinter:
    """
    Printer communication class based on Chituboard plugin approach
    Handles the specific firmware quirks and communication protocols
    """
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # Load configuration
        printer_config = config_manager.get_app_config('printer') if config_manager else {}
        
        self.serial_port = printer_config.get('serial_port', '/dev/serial0')
        self.baudrate = printer_config.get('baudrate', 115200)
        self.timeout = printer_config.get('timeout', 5.0)
        self.firmware_version = printer_config.get('firmware_version', 'V4.13')
        
        self.connection = None
        self.is_connected = False
        self.print_status = PrintStatus()
        self.selected_file = ""
        self.z_position = 0.0
        self._communication_lock = threading.Lock()
        self._logged_replacements = {}
        self._monitoring_thread = None
        self._stop_monitoring = False
        
        # Chituboard communication settings
        self.communication_settings = {
            'helloCommand': 'M4002',
            'ignoreErrorsFromFirmware': True,
            'sdAlwaysAvailable': True,
            'maxCommunicationTimeouts': 0,
            'neverSendChecksum': True,
            'unknownCommandsNeedAck': False,
            'disconnectOnErrors': False,
            'firmwareDetection': False,
            'exclusive': True
        }
        
        # Regex patterns for parsing responses (from Chituboard)
        self.regex_float_pattern = r"[-+]?[0-9]*\.?[0-9]+"
        self.regex_int_pattern = r"\d+"
        self.parse_M4000 = {
            "floatB": re.compile(r"(^|[^A-Za-z])[Bb]:\s*(?P<actual>%s)(\s*\/?\s*(?P<target>%s))?" %
                             (self.regex_float_pattern, self.regex_float_pattern)),
            "floatD": re.compile(r"(^|[^A-Za-z])[Dd]z?\s*(?P<current>%s)(\s*\/?\s*(?P<total>%s))(\s*\/?\s*(?P<pause>%s))?" %
                             (self.regex_float_pattern, self.regex_float_pattern, self.regex_int_pattern)),
            "floatX": re.compile(r"(^|[^A-Za-z])[Xx]:(?P<value>%s)" % self.regex_float_pattern),
            "floatY": re.compile(r"(^|[^A-Za-z])[Yy]:(?P<value>%s)" % self.regex_float_pattern),
            "floatZ": re.compile(r"(^|[^A-Za-z])[Zz]:(?P<value>%s)" % self.regex_float_pattern),
        }
        self.regex_sdPrintingByte = re.compile(r"(?P<current>[0-9]+)/(?P<total>[0-9]+)")
        self.fix_M114 = re.compile(r"C: ")
        
    def connect(self):
        """Connect to printer with proper initialization"""
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
                
            # Give the serial port a moment to be available
            time.sleep(1)
                
            self.connection = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                exclusive=False  # Changed to False for compatibility
            )
            
            # Wait for connection to stabilize
            time.sleep(2)
            
            # Clear any pending data
            self.connection.reset_input_buffer()
            self.connection.reset_output_buffer()
            
            # Send hello command (Chituboard approach)
            response = self._send_command("M4002")
            if response:
                self.is_connected = True
                
                # Initialize SD card (critical for USB gadget mode)
                try:
                    self._send_command("M21")  # Initialize SD card
                    time.sleep(1)
                except Exception as e:
                    logger.debug(f"SD initialization warning: {e}")
                
                # Try to get firmware version
                try:
                    version_response = self._send_command("M115")
                    if version_response and "FIRMWARE_NAME:" in version_response:
                        # Parse firmware version from response
                        if "PROTOCOL_VERSION:" in version_response:
                            parts = version_response.split("PROTOCOL_VERSION:")
                            if len(parts) > 1:
                                self.firmware_version = parts[1].strip().split()[0]
                except Exception as e:
                    logger.debug(f"Could not get firmware version: {e}")
                
                # Start monitoring thread
                self._start_monitoring()
                
                # Call plugin hook
                plugin_manager.call_hook('printer_connected', {
                    'firmware_version': self.firmware_version,
                    'serial_port': self.serial_port,
                    'baudrate': self.baudrate
                })
                    
                logger.info(f"Connected to printer, firmware: {self.firmware_version}")
                return True
            else:
                logger.error("No response to hello command")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to printer: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from printer"""
        try:
            self._stop_monitoring = True
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=5)
                
            if self.connection and self.connection.is_open:
                self.connection.close()
            
            # Call plugin hook
            plugin_manager.call_hook('printer_disconnected')
            
            self.is_connected = False
            logger.info("Disconnected from printer")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def _start_monitoring(self):
        """Start monitoring thread for USB status and printer communication"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return
            
        self._stop_monitoring = False
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        logger.info("Started printer monitoring thread")
    
    def _monitoring_loop(self):
        """Monitor printer status"""
        while not self._stop_monitoring and self.is_connected:
            try:
                # Update print status less frequently to avoid overwhelming printer
                if self.print_status.state == PrinterState.PRINTING:
                    self.get_print_status()
                    
                time.sleep(3)  # Check every 3 seconds instead of 1
                
            except Exception as e:
                logger.debug(f"Monitoring loop error: {e}")
                time.sleep(5)
    
    def _send_command(self, command, timeout=None):
        """
        Send command to printer with proper response handling
        Based on Chituboard's communication approach
        """
        if not self.connection or not self.connection.is_open:
            raise Exception("Printer not connected")
            
        with self._communication_lock:
            try:
                # Clear input buffer
                self.connection.reset_input_buffer()
                
                # Send command with proper line ending
                if not command.endswith('\n'):
                    command += '\n'
                command_bytes = command.encode('latin-1', errors='ignore')  # Use latin-1 for binary safety
                self.connection.write(command_bytes)
                self.connection.flush()
                
                # Wait for response with extended timeout for USB operations
                response_timeout = timeout or (self.timeout * 3 if 'M6030' in command or 'M23' in command else self.timeout)
                response = ""
                start_time = time.time()
                
                while time.time() - start_time < response_timeout:
                    if self.connection.in_waiting > 0:
                        try:
                            # Read with latin-1 encoding for binary safety
                            char = self.connection.read(1).decode('latin-1', errors='ignore')
                            response += char
                            if response.endswith('\n') or response.endswith('\r\n'):
                                break
                        except UnicodeDecodeError:
                            continue
                    else:
                        time.sleep(0.01)
                
                # Process response using Chituboard approach
                response = self._process_response(response.strip(), command.strip())
                logger.debug(f"Command: {command.strip()} -> Response: {response}")
                return response
                
            except Exception as e:
                logger.error(f"Communication error for command {command.strip()}: {e}")
                raise
    
    def _process_response(self, response, original_command):
        """
        Process printer response using Chituboard's firmware fixes
        """
        if not response:
            return response
        
        # Handle binary data in response
        try:
            # Filter out non-printable characters except newlines
            filtered_response = ''.join(char for char in response if ord(char) >= 32 or char in '\r\n\t')
            if filtered_response != response:
                logger.debug(f"Filtered binary data from response: {len(response)} -> {len(filtered_response)} chars")
                response = filtered_response
        except:
            pass
            
        # Fix "wait" responses (Chituboard fix)
        if response == "wait" or response.startswith("wait"):
            self._log_replacement("wait", response, "echo:busy processing")
            return "echo:busy processing"
        
        # Fix firmware identifier (Chituboard fix) 
        if "CBD make it" in response:
            fixed = response.replace("CBD make it", f"FIRMWARE_NAME:CBD made it PROTOCOL_VERSION:{self.firmware_version}")
            self._log_replacement("identifier", response, fixed)
            return fixed
        elif "ZWLF make it" in response:
            fixed = response.replace("ZWLF make it", f"FIRMWARE_NAME:ZWLF made it PROTOCOL_VERSION:{self.firmware_version}")
            self._log_replacement("identifier", response, fixed)
            return fixed
            
        # Fix M114 response format (Chituboard fix)
        if "C: X:" in response:
            fixed = self.fix_M114.sub("", response)
            self._log_replacement("M114", response, fixed)
            return fixed
            
        # Process M4000 responses (temperature simulation)
        if original_command == "M4000":
            return self._process_m4000_response(response)
            
        # Handle start command response
        if response.startswith('ok V'):
            self.firmware_version = response[3:]
            fixed = 'ok start' + response
            self._log_replacement("start", response, fixed)
            return fixed
            
        return response
    
    def _process_m4000_response(self, response):
        """
        Process M4000 response and convert to temperature format
        Based on Chituboard's approach
        """
        matchB = self.parse_M4000["floatB"].search(response)
        matchD = self.parse_M4000["floatD"].search(response)
        
        if matchB:
            try:
                actual = matchB.group('actual')
                target = matchB.group('target') if matchB.group('target') else actual
                # Convert to temperature format that monitoring expects
                return f"T:0 /0 B:{actual} /{target}"
            except Exception as e:
                logger.debug(f"Error parsing M4000 B response: {e}")
                
        if matchD:
            try:
                current = int(float(matchD.group('current')))
                total = int(float(matchD.group('total')))
                pause = int(matchD.group('pause')) if matchD.group('pause') else 0
                
                # Update print status
                if total > 0:
                    self.print_status.current_byte = current
                    self.print_status.total_bytes = total
                    self.print_status.progress_percent = (current / total) * 100
                    
                    # Check if paused
                    if pause == 1 and current > 0:
                        self.print_status.state = PrinterState.PAUSED
                        
                    # Check if finished
                    elif current >= total and total > 0:
                        self.print_status.state = PrinterState.FINISHED
                        
                    elif current > 0:
                        self.print_status.state = PrinterState.PRINTING
                        
                return f"SD printing byte {current}/{total}"
                
            except Exception as e:
                logger.debug(f"Error parsing M4000 D response: {e}")
                
        return response
    
    def _log_replacement(self, replacement_type, original, replacement):
        """Log response replacements (from Chituboard)"""
        if replacement_type not in self._logged_replacements:
            logger.info(f"Replacing {replacement_type}: '{original}' -> '{replacement}'")
            self._logged_replacements[replacement_type] = True
        else:
            logger.debug(f"Replacing {replacement_type}: '{original}' -> '{replacement}'")
    
    def get_firmware_version(self):
        """Get firmware version"""
        if not self.is_connected:
            raise Exception("Printer not connected")
        return self.firmware_version
    
    def get_print_status(self):
        """Get current print status"""
        if not self.is_connected:
            return PrintStatus(state=PrinterState.UNKNOWN)
            
        try:
            # Query printer status using M27 (SD card status)
            response = self._send_command("M27")
            if response:
                # Parse SD printing status
                if "SD printing byte" in response:
                    match = self.regex_sdPrintingByte.search(response)
                    if match:
                        current = int(match.group("current"))
                        total = int(match.group("total"))
                        
                        self.print_status.current_byte = current
                        self.print_status.total_bytes = total
                        
                        if total > 0:
                            self.print_status.progress_percent = (current / total) * 100
                            
                            if current >= total:
                                self.print_status.state = PrinterState.FINISHED
                            elif current > 0:
                                self.print_status.state = PrinterState.PRINTING
                            else:
                                self.print_status.state = PrinterState.IDLE
                        else:
                            self.print_status.state = PrinterState.IDLE
                            
                elif "Not SD printing" in response:
                    self.print_status.state = PrinterState.IDLE
                    self.print_status.progress_percent = 0
                    self.print_status.current_byte = 0
            
            # Call plugin hook
            plugin_manager.call_hook('status_update', {
                'print_status': self.print_status,
                'z_position': self.z_position,
                'selected_file': self.selected_file
            })
                    
            return self.print_status
            
        except Exception as e:
            logger.error(f"Error getting print status: {e}")
            return PrintStatus(state=PrinterState.ERROR)
    
    def get_selected_file(self):
        """Get currently selected file"""
        return self.selected_file
    
    def get_z_position(self):
        """Get current Z position"""
        try:
            response = self._send_command("M114")
            if response and "Z:" in response:
                match = self.parse_M4000["floatZ"].search(response)
                if match:
                    self.z_position = float(match.group('value'))
            return self.z_position
        except Exception as e:
            logger.debug(f"Error getting Z position: {e}")
            return self.z_position
    
    def select_file(self, filename):
        """Select file for printing"""
        try:
            # Initialize SD card first
            init_response = self._send_command("M21")
            time.sleep(1)
            
            # Select the file
            response = self._send_command(f"M23 {filename}", timeout=10)
            if response and ("ok" in response.lower() or "file opened" in response.lower()):
                self.selected_file = filename
                logger.info(f"File selected: {filename}")
                return True
            else:
                logger.warning(f"File selection failed: {response}")
                return False
        except Exception as e:
            logger.error(f"Error selecting file {filename}: {e}")
            return False
    
    def start_printing(self, filename=None):
        """Start printing selected file"""
        try:
            if filename:
                if not self.select_file(filename):
                    return False
                    
            if not self.selected_file:
                logger.error("No file selected for printing")
                return False
                
            # Use M6030 command for starting print (Chituboard approach)
            logger.info(f"Starting print: {self.selected_file}")
            response = self._send_command(f"M6030 '{self.selected_file}'", timeout=15)
            
            if response and "ok" in response.lower():
                self.print_status.state = PrinterState.PRINTING
                
                # Call plugin hook
                plugin_manager.call_hook('print_started', self.selected_file)
                
                logger.info(f"Started printing: {self.selected_file}")
                return True
            else:
                logger.warning(f"Print start failed: {response}")
                return False
            
        except Exception as e:
            logger.error(f"Error starting print: {e}")
            return False
    
    def pause_printing(self):
        """Pause current print"""
        try:
            response = self._send_command("M25")
            if response and "ok" in response.lower():
                self.print_status.state = PrinterState.PAUSED
                
                # Call plugin hook
                plugin_manager.call_hook('print_paused', self.selected_file)
                
                logger.info("Print paused")
                return True
            return False
        except Exception as e:
            logger.error(f"Error pausing print: {e}")
            return False
    
    def resume_printing(self):
        """Resume paused print"""
        try:
            response = self._send_command("M24")
            if response and "ok" in response.lower():
                self.print_status.state = PrinterState.PRINTING
                
                # Call plugin hook
                plugin_manager.call_hook('print_resumed', self.selected_file)
                
                logger.info("Print resumed")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resuming print: {e}")
            return False
    
    def stop_printing(self):
        """Stop current print"""
        try:
            response = self._send_command("M33")
            if response and "ok" in response.lower():
                old_status = self.print_status.state.value
                self.print_status.state = PrinterState.IDLE
                self.print_status.progress_percent = 0
                self.print_status.current_byte = 0
                
                # Call plugin hook
                plugin_manager.call_hook('print_finished', self.selected_file, old_status)
                
                self.selected_file = ""
                logger.info("Print stopped")
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping print: {e}")
            return False
    
    def move_to_home(self):
        """Home Z axis"""
        try:
            response = self._send_command("G28 Z0")
            return response and "ok" in response.lower()
        except Exception as e:
            logger.error(f"Error homing Z: {e}")
            return False
    
    def move_by(self, distance):
        """Move Z axis by relative distance"""
        try:
            response = self._send_command(f"G91\nG1 Z{distance} F600\nG90")
            return response and "ok" in response.lower()
        except Exception as e:
            logger.error(f"Error moving Z by {distance}: {e}")
            return False
    
    def reboot(self):
        """Reboot printer"""
        try:
            response = self._send_command("M999")
            return True  # Don't wait for response as printer reboots
        except Exception as e:
            logger.error(f"Error rebooting printer: {e}")
            return False

# Initialize printer with config manager
printer = ChituboardPrinter(config_manager)

def test_printer_connection():
    """Test if we can communicate with the printer"""
    try:
        if not printer.is_connected:
            connected = printer.connect()
            if not connected:
                return False, "Failed to connect"
        
        firmware_version = printer.get_firmware_version()
        return True, firmware_version
    except Exception as e:
        logger.error(f"Printer connection test failed: {e}")
        return False, str(e)

def serialize_print_status(status):
    """Convert PrintStatus object to JSON serializable dict"""
    if status is None:
        return {'state': 'UNKNOWN', 'progress': 0, 'current_layer': 0, 'total_layers': 0}
    
    return {
        'state': status.state.value,
        'progress_percent': status.progress_percent,
        'current_layer': status.current_layer,
        'total_layers': status.total_layers,
        'current_byte': status.current_byte,
        'total_bytes': status.total_bytes
    }

# ----------------- ROUTES -----------------

@app.route('/')
def index():
    # Get plugin assets for template
    plugin_assets = plugin_manager.get_frontend_assets()
    return render_template('index.html', plugin_assets=plugin_assets)

@app.route('/api/status')
def api_status():
    connected, firmware_info = test_printer_connection()
    
    if connected:
        firmware_version = firmware_info
        status = printer.get_print_status()
        selected_file = printer.get_selected_file()
        z_pos = printer.get_z_position()
    else:
        firmware_version = f"Connection Error: {firmware_info}"
        status = PrintStatus(state=PrinterState.IDLE)
        selected_file = ""
        z_pos = 0.0

    response_data = {
        'connected': connected,
        'firmware_version': firmware_version,
        'print_status': serialize_print_status(status),
        'selected_file': selected_file,
        'z_position': z_pos
    }
    
    # Allow plugins to modify the response
    response_data = plugin_manager.modify_response('status', response_data)
    
    return jsonify(response_data)

@app.route('/api/connect', methods=['POST'])
def api_connect():
    try:
        connected, info = test_printer_connection()
        if connected:
            return jsonify({'success': True, 'message': 'Printer is connected'})
        else:
            return jsonify({'success': False, 'error': f'Cannot connect to printer: {info}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    try:
        printer.disconnect()
        return jsonify({'success': True, 'message': 'Disconnected from printer'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/pause', methods=['POST'])
def api_pause():
    try:
        success = printer.pause_printing()
        if success:
            return jsonify({'success': True, 'message': 'Print paused'})
        else:
            return jsonify({'success': False, 'error': 'Failed to pause print'})
    except Exception as e:
        logger.error(f"Failed to pause print: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resume', methods=['POST'])
def api_resume():
    try:
        success = printer.resume_printing()
        if success:
            return jsonify({'success': True, 'message': 'Print resumed'})
        else:
            return jsonify({'success': False, 'error': 'Failed to resume print'})
    except Exception as e:
        logger.error(f"Failed to resume print: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    try:
        success = printer.stop_printing()
        if success:
            return jsonify({'success': True, 'message': 'Print stopped'})
        else:
            return jsonify({'success': False, 'error': 'Failed to stop print'})
    except Exception as e:
        logger.error(f"Failed to stop print: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/home_z', methods=['POST'])
def api_home_z():
    try:
        success = printer.move_to_home()
        if success:
            return jsonify({'success': True, 'message': 'Z axis homed'})
        else:
            return jsonify({'success': False, 'error': 'Failed to home Z axis'})
    except Exception as e:
        logger.error(f"Failed to home Z: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/move_z', methods=['POST'])
def api_move_z():
    data = request.get_json()
    distance = float(data.get('distance', 0))
    try:
        success = printer.move_by(distance)
        if success:
            return jsonify({'success': True, 'message': f'Moved Z by {distance}mm'})
        else:
            return jsonify({'success': False, 'error': f'Failed to move Z by {distance}mm'})
    except Exception as e:
        logger.error(f"Failed to move Z by {distance}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reboot', methods=['POST'])
def api_reboot():
    try:
        success = printer.reboot()
        if success:
            return jsonify({'success': True, 'message': 'Printer rebooting...'})
        else:
            return jsonify({'success': False, 'error': 'Failed to reboot printer'})
    except Exception as e:
        logger.error(f"Failed to reboot printer: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/recover_usb_error', methods=['POST'])
def api_recover_usb_error():
    """Recover from USB/Memory errors like M_11800"""
    try:
        logger.info("Attempting USB error recovery...")
        
        # Step 1: Stop any current operation
        try:
            printer._send_command("M33")  # Stop print if running
            time.sleep(2)
        except:
            pass
            
        # Step 2: Clear memory caches
        try:
            subprocess.run(['sudo', 'sh', '-c', 'echo 1 > /proc/sys/vm/drop_caches'], 
                         capture_output=True, text=True)
        except:
            pass
            
        # Step 3: Reset USB communication
        try:
            subprocess.run(['sudo', 'rmmod', 'g_mass_storage'], capture_output=True, text=True)
            time.sleep(2)
            subprocess.run(['sudo', 'modprobe', 'g_mass_storage', 'file=/piusb.bin', 
                          'removable=1', 'ro=0', 'stall=0', 'nofua=1', 'cdrom=0'], 
                         capture_output=True, text=True)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"USB module restart failed: {e}")
            
        # Step 4: Reset printer communication
        try:
            printer._send_command("M21")    # Initialize SD card
            time.sleep(1)
        except:
            pass
            
        logger.info("USB error recovery completed")
        return jsonify({
            'success': True, 
            'message': 'USB error recovery completed. Memory cleared and USB reloaded.'
        })
        
    except Exception as e:
        logger.error(f"USB error recovery failed: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/select_file', methods=['POST'])
def api_select_file():
    data = request.get_json()
    filename = data.get('filename', '')
    
    logger.info(f"Attempting to select file: {filename}")
    
    try:
        # Check if file exists using file manager
        if not file_manager.file_exists(filename):
            logger.error(f"File not found: {filename}")
            return jsonify({'success': False, 'error': f'File not found: {filename}'})
        
        connected, info = test_printer_connection()
        if not connected:
            logger.error(f"Printer not connected: {info}")
            return jsonify({'success': False, 'error': f'Printer not connected: {info}'})
        
        success = printer.select_file(filename)
        if success:
            logger.info(f"File selected successfully: {filename}")
            return jsonify({'success': True, 'message': f'Selected file: {filename}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to select file'})
        
    except Exception as e:
        logger.error(f"Failed to select file {filename}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/print_file', methods=['POST'])
def api_print_file():
    data = request.get_json()
    filename = data.get('filename', '')
    
    logger.info(f"Attempting to print file: {filename}")
    
    try:
        # Check if file exists using file manager
        if not file_manager.file_exists(filename):
            logger.error(f"File not found: {filename}")
            return jsonify({'success': False, 'error': f'File not found: {filename}'})
        
        connected, info = test_printer_connection()
        if not connected:
            logger.error(f"Printer not connected: {info}")
            return jsonify({'success': False, 'error': f'Printer not connected: {info}'})
        
        success = printer.start_printing(filename)
        if success:
            return jsonify({'success': True, 'message': f'Print started: {filename}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to start print'})
        
    except Exception as e:
        logger.error(f"Failed to print {filename}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check_usb_installation')
def api_check_usb_installation():
    """Check if USB gadget is installed - adapted for g_mass_storage"""
    try:
        # Check for g_mass_storage setup
        usb_image_exists = Path('/piusb.bin').exists()
        mount_point_exists = USB_DRIVE_MOUNT.exists()
        
        # Check if g_mass_storage is configured in rc.local
        rc_local_configured = False
        try:
            with open('/etc/rc.local', 'r') as f:
                rc_local_configured = 'g_mass_storage' in f.read()
        except:
            pass
        
        # Check if mount is in fstab
        fstab_configured = False
        try:
            with open('/etc/fstab', 'r') as f:
                fstab_configured = '/piusb.bin' in f.read()
        except:
            pass
        
        installed = all([usb_image_exists, mount_point_exists, rc_local_configured, fstab_configured])
        
        return jsonify({
            'installed': installed,
            'setup_type': 'g_mass_storage',
            'components': {
                'usb_image': usb_image_exists,
                'mount_point': mount_point_exists,
                'rc_local': rc_local_configured,
                'fstab': fstab_configured
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to check USB installation: {e}")
        return jsonify({'error': str(e), 'installed': False})

@app.route('/api/usb_status')
def api_usb_status():
    """Check USB drive status - adapted for g_mass_storage setup"""
    try:
        # Check if g_mass_storage module is loaded
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        service_active = 'g_mass_storage' in result.stdout
        
        # Check if mount point is mounted
        mounted = False
        if USB_DRIVE_MOUNT.exists():
            try:
                result = subprocess.run(['mountpoint', '-q', str(USB_DRIVE_MOUNT)], 
                                      capture_output=True)
                mounted = result.returncode == 0
            except:
                try:
                    with open('/proc/mounts', 'r') as f:
                        mount_data = f.read()
                        mounted = str(USB_DRIVE_MOUNT) in mount_data
                except:
                    mounted = False
        
        # Get USB space using file manager
        usb_space = file_manager.get_disk_usage()
        
        return jsonify({
            'service_running': service_active,
            'mounted': mounted,
            'mount_point': str(USB_DRIVE_MOUNT),
            'usb_space': usb_space,
            'setup_type': 'g_mass_storage'
        })
    except Exception as e:
        logger.error(f"Failed to get USB status: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/start_usb_gadget', methods=['POST'])
def api_start_usb_gadget():
    """Start USB gadget using g_mass_storage"""
    try:
        # Load g_mass_storage module with optimized parameters
        result = subprocess.run([
            'sudo', 'modprobe', 'g_mass_storage',
            'file=/piusb.bin',
            'removable=1',
            'ro=0',
            'stall=0',
            'nofua=1',
            'cdrom=0'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'USB Gadget started'})
        else:
            return jsonify({'success': False, 'error': result.stderr})
    except Exception as e:
        logger.error(f"Failed to start USB gadget: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop_usb_gadget', methods=['POST'])
def api_stop_usb_gadget():
    """Stop USB gadget"""
    try:
        result = subprocess.run(['sudo', 'rmmod', 'g_mass_storage'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'USB Gadget stopped'})
        else:
            return jsonify({'success': False, 'error': result.stderr})
    except Exception as e:
        logger.error(f"Failed to stop USB gadget: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/install_usb_gadget', methods=['POST'])
def api_install_usb_gadget():
    """This route is not needed since you already have a working setup"""
    return jsonify({
        'success': False, 
        'error': 'USB gadget already installed using g_mass_storage. No additional installation needed.'
    })

def cleanup():
    try:
        if printer and printer.is_connected:
            printer.disconnect()
        if plugin_manager:
            plugin_manager.shutdown_all_plugins()
    except:
        pass

if __name__ == '__main__':
    import atexit
    atexit.register(cleanup)
    
    print("🖨️ Resin Print Portal with Plugin System")
    print("Initializing plugin system...")
    
    # Discover and load plugins
    discovered_plugins = plugin_manager.discover_plugins()
    
    # Try to load all discovered plugins
    for plugin_name in discovered_plugins:
        if plugin_manager.load_plugin(plugin_name):
            print(f"✅ Plugin loaded: {plugin_name}")
        else:
            print(f"❌ Failed to load plugin: {plugin_name}")
    
    # Initialize enabled plugins
    plugin_manager.initialize_enabled_plugins()
    
    # Register plugin blueprints
    plugin_manager.register_blueprints(app)
    
    print("Testing printer connection...")
    connected, info = test_printer_connection()
    if connected:
        print(f"✅ Printer connected: {info}")
    else:
        print(f"❌ Printer connection failed: {info}")
        print("Check your serial port configuration and make sure the printer is connected.")
    
    # Test file manager initialization
    is_valid, message = file_manager.validate_mount_point()
    if is_valid:
        print(f"✅ File manager initialized: {message}")
    else:
        print(f"⚠️ File manager warning: {message}")
    
    # Show loaded plugins
    loaded_plugins = list(plugin_manager.loaded_plugins.keys())
    if loaded_plugins:
        print(f"✅ Loaded plugins: {', '.join(loaded_plugins)}")
    else:
        print("ℹ️ No plugins loaded")
    
    app.run(host='0.0.0.0', port=5000)
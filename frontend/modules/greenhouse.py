import sys
import json
import uuid
import logging
import requests
import os
from PyQt5.QtWidgets import (QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTextEdit, QLineEdit, QTabWidget,
                             QLabel, QGroupBox, QGridLayout, QMessageBox, QCheckBox,
                            )
from PyQt5.QtCore import QDateTime, Qt, QTimer
from PyQt5 import uic

from modules.command_worker import CommandWorker
from modules.styles import GreenhouseTheme, StyleSheetGenerator
from modules.edge_fog_aggregator import EdgeToFogAggregator, SensorReading, SensorType
from modules.redis_client import RedisEdgeClient

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('greenhouse_system.log', encoding='utf-8')
        ]
    )

class GreenhouseDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pending_commands = {}
        self.session_id = str(uuid.uuid4())
        self.rabbitmq_connected = False
        self.command_worker = None
        
        # Import config after it's initialized
        from modules.config import config
        self.backend_url = config.BACKEND_URL
        
        # Initialize Edge-to-Fog aggregator
        self.edge_aggregator = EdgeToFogAggregator()
        self.redis_edge_client = RedisEdgeClient()
        
        # Initialize styling
        self.theme = GreenhouseTheme()
        self.styler = StyleSheetGenerator(self.theme)
        
        self.logger = logging.getLogger('GreenhouseDesktop')
        self.logger.info(f"Starting application with session ID: {self.session_id}")
        self.logger.info(f"Backend URL: {self.backend_url}")
        
        # Load UI from .ui file
        self.setupUI()
        
        # Setup functionality and signal connections
        self.add_functions()
        
        # Setup command worker
        self.setup_command_worker()
        
        # Setup edge-to-fog aggregator
        self.setup_edge_aggregator()
        
        # Apply custom styles (UI file already has styles, but we can override if needed)
        self.apply_styles()
        
    def setupUI(self):
        """Load UI from .ui file in frontend directory"""
        # UI file is always in the frontend directory (same level as modules/)
        # From frontend/modules/greenhouse.py -> frontend/front.ui
        frontend_dir = os.path.dirname(os.path.dirname(__file__))
        ui_path = os.path.join(frontend_dir, 'front.ui')
        
        if not os.path.exists(ui_path):
            error_msg = f"UI file not found at: {ui_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        self.logger.info(f"Loading UI from: {ui_path}")
        uic.loadUi(ui_path, self)
        
        # Update session label with actual session ID
        self.session_label.setText(self.session_id[:8] + "...")
        self.session_label.setToolTip(f"Full Session ID: {self.session_id}")
        
        # Path label removed (no longer needed without shell commands)
        # self.path_label.setText(self.current_path)
        
        # Initialize auto-refresh timer
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_all_status)
        
    def add_functions(self):
        """Setup signal connections and functionality"""
        # User Tab - Sensor reading buttons
        self.tempButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "temperature"}))
        self.humidityButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "humidity"}))
        self.lightButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "light"}))
        self.co2Button.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "co2"}))
        self.soilMoistureButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "soil_moisture"}))
        self.soilPHButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "soil_ph"}))
        
        # User Tab - Device control buttons
        self.waterCanalButton.clicked.connect(lambda: self.send_user_command("switch_water_canal", {"action": "toggle"}))
        self.fanButton.clicked.connect(lambda: self.send_user_command("switch_fan", {"fanId": "fan_1", "action": "toggle"}))
        self.heaterButton.clicked.connect(lambda: self.send_user_command("switch_heater", {"heaterId": "heater_1", "action": "toggle"}))
        self.actuatorButton.clicked.connect(lambda: self.send_user_command("switch_actuator", {"actuatorId": "actuator_1", "action": "toggle"}))
        
        # User Tab - Clear button
        self.btn_clear_user.clicked.connect(self.user_output.clear)
        
        # Legacy buttons (kept for backward compatibility, can be removed if not needed)
        if hasattr(self, 'statusButton'):
            self.statusButton.clicked.connect(lambda: self.send_user_command("read_sensor", {"sensor": "temperature"}))
        if hasattr(self, 'listFilesButton'):
            # Remove or repurpose this button
            pass
        if hasattr(self, 'pathButton'):
            # Remove or repurpose this button
            pass
        
        # Server Tab - Server management buttons
        self.healthButton.clicked.connect(self.check_server_health)
        self.statsButton.clicked.connect(self.view_server_stats)
        self.sessionsButton.clicked.connect(self.list_sessions)
        self.cacheKeysButton.clicked.connect(self.list_cache_keys)
        self.clearCacheButton.clicked.connect(self.clear_all_cache)
        self.queuesButton.clicked.connect(self.check_queues)
        self.testCommandButton.clicked.connect(self.test_server_command)
        self.refreshButton.clicked.connect(self.refresh_all_status)
        self.logFilesButton.clicked.connect(self.list_log_files)
        self.viewLogButton.clicked.connect(self.view_session_log)
        
        # Fog Data buttons (if they exist in UI, otherwise will be added dynamically)
        if hasattr(self, 'fogAggregatedButton'):
            self.fogAggregatedButton.clicked.connect(self.view_fog_aggregated_data)
        if hasattr(self, 'fogDevicesButton'):
            self.fogDevicesButton.clicked.connect(self.view_fog_devices)
        if hasattr(self, 'fogAnomaliesButton'):
            self.fogAnomaliesButton.clicked.connect(self.view_fog_anomalies)
        
        # Server Tab - Auto-refresh checkbox
        self.auto_refresh.toggled.connect(self.toggle_auto_refresh)
        
        # Server Tab - Clear button
        self.btn_clear_server.clicked.connect(self.server_info.clear)
        
    def apply_styles(self):
        """Apply custom styles if needed (UI file already has styles)"""
        # The UI file already contains styles, but we can override specific widgets if needed
        # For example, update connection status and status label styles dynamically
        pass

    def list_log_files(self):
        """List all session log files"""
        result = self.make_server_request('/logs')
        if result:
            self.display_formatted_json("Session Log Files", result)

    def view_session_log(self):
        """View specific session log"""
        session_id = self.session_log_input.text().strip()
        if not session_id:
            self.show_error("Session ID Required", "Please enter a session ID")
            return
        
        result = self.make_server_request(f'/sessions/{session_id}/log')
        if result:
            self.server_info.append(f"=== Session Log: {result.get('sessionId', 'Unknown')} ===\n")
            self.server_info.append(f"Session Number: {result.get('sessionNumber', 'Unknown')}\n")
            self.server_info.append(f"Log File: {result.get('logFile', 'Unknown')}\n")
            self.server_info.append("=" * 50 + "\n")
            self.server_info.append(result.get('content', 'No log content available'))
            self.server_info.append("\n" + "=" * 50 + "\n")
        
    def toggle_auto_refresh(self, enabled):
        if enabled:
            self.auto_refresh_timer.start(10000)  # 10 seconds
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] Auto-refresh enabled")
        else:
            self.auto_refresh_timer.stop()
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] Auto-refresh disabled")
        
    def refresh_all_status(self):
        """Refresh all server status information"""
        self.check_server_health()
        self.view_server_stats()
        self.list_sessions()
        
    def make_server_request(self, endpoint, method='GET', data=None):
        """Make HTTP request to backend server"""
        try:
            url = f"{self.backend_url}{endpoint}"
            self.server_info.append(f"[{QDateTime.currentDateTime().toString('hh:mm:ss')}] {method} {endpoint}")
            
            if method == 'GET':
                response = requests.get(url, timeout=5)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=5)
            elif method == 'POST':
                response = requests.post(url, json=data, timeout=5)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 200:
                return response.json()
            else:
                self.server_info.append(f"Error: {response.status_code} - {response.text}\n")
                return None
                
        except requests.exceptions.ConnectionError:
            self.server_info.append(f"Error: Cannot connect to backend server at {self.backend_url}. Make sure it's running.\n")
            return None
        except requests.exceptions.Timeout:
            self.server_info.append("Error: Request timeout - server is not responding\n")
            return None
        except Exception as e:
            self.server_info.append(f"Error: {str(e)}\n")
            return None
        
    def check_server_health(self):
        """Check server health status"""
        result = self.make_server_request('/health')
        if result:
            self.display_formatted_json("Server Health", result)
        
    def view_server_stats(self):
        """View server statistics"""
        result = self.make_server_request('/stats')
        if result:
            self.display_formatted_json("Server Statistics", result)
        
    def list_sessions(self):
        """List active sessions"""
        result = self.make_server_request('/sessions')
        if result:
            self.display_formatted_json("Active Sessions", result)
        
    def list_cache_keys(self):
        """List cache keys"""
        result = self.make_server_request('/cache/keys')
        if result:
            self.display_formatted_json("Cache Keys", result)
        
    def clear_all_cache(self):
        """Clear all cache"""
        reply = QMessageBox.question(self, 'Clear Cache', 
                                   'Are you sure you want to clear ALL cache?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            result = self.make_server_request('/cache/clear', method='DELETE')
            if result:
                self.display_formatted_json("Cache Clear Result", result)
        
    def check_queues(self):
        """Check RabbitMQ queue status"""
        result = self.make_server_request('/queues')
        if result:
            self.display_formatted_json("Queue Status", result)
        
    def test_server_command(self):
        """Test server command execution"""
        command_data = {
            "command": "read_sensor",
            "parameters": {}
        }
        result = self.make_server_request('/command', method='POST', data=command_data)
        if result:
            self.display_formatted_json("Test Command Result", result)
        
    def display_formatted_json(self, title, data):
        """Display formatted JSON in server info panel"""
        self.server_info.append(f"=== {title} ===")
        self.server_info.append(json.dumps(data, indent=2))
        self.server_info.append("=" * 50 + "\n")
        
    def setup_command_worker(self):
        self.logger.info("Setting up command worker")
        self.command_worker = CommandWorker()
        self.command_worker.response_received.connect(self.handle_response)
        self.command_worker.connection_status.connect(self.update_connection_status)
        self.command_worker.error_occurred.connect(self.handle_error)
        
        # Initial connection
        self.command_worker.setup_rabbitmq()
        
        # Setup connection check timer
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection)
        self.connection_timer.start(10000)
    
    def setup_edge_aggregator(self):
        """Setup Edge-to-Fog aggregator and connect signals"""
        self.logger.info("Setting up Edge-to-Fog aggregator")
        
        # Connect aggregator signals to UI handlers
        self.edge_aggregator.new_aggregated_data.connect(self.handle_aggregated_data)
        self.edge_aggregator.anomaly_detected.connect(self.handle_anomaly)
        self.edge_aggregator.device_status_changed.connect(self.handle_device_status)
        
        # Connect to Redis for local caching
        self.redis_edge_client.connect()
        
        # Setup sensor data consumer (if RabbitMQ is available)
        # For now, we'll simulate sensor data or receive from RabbitMQ
        self.setup_sensor_data_consumer()
        
        # Register some example edge devices (in real scenario, these would come from discovery)
        self.register_example_devices()
        
        self.logger.info("Edge-to-Fog aggregator setup complete")
    
    def setup_sensor_data_consumer(self):
        """Setup consumer for sensor data from RabbitMQ or simulate it"""
        # For now, we'll use a timer to simulate sensor readings
        # In production, this would consume from a RabbitMQ queue
        self.sensor_simulator_timer = QTimer()
        self.sensor_simulator_timer.timeout.connect(self.simulate_sensor_reading)
        self.sensor_simulator_timer.start(5000)  # Every 5 seconds
        
        self.logger.info("Sensor data consumer started (simulation mode)")
    
    def simulate_sensor_reading(self):
        """Simulate sensor readings for testing"""
        from datetime import datetime
        import random
        
        # Simulate readings from different locations
        locations = ["Zone_A", "Zone_B", "Zone_C"]
        devices = ["device_001", "device_002", "device_003"]
        
        for i, (location, device_id) in enumerate(zip(locations, devices)):
            # Temperature
            temp_reading = SensorReading(
                device_id=device_id,
                sensor_type=SensorType.TEMPERATURE,
                value=20.0 + random.uniform(-5, 10),
                timestamp=datetime.now(),
                location=location,
                quality=random.uniform(0.8, 1.0),
                battery_level=random.uniform(80, 100),
                signal_strength=random.uniform(70, 100)
            )
            self.edge_aggregator.add_sensor_reading(temp_reading)
            
            # Humidity
            humidity_reading = SensorReading(
                device_id=device_id,
                sensor_type=SensorType.HUMIDITY,
                value=50.0 + random.uniform(-10, 20),
                timestamp=datetime.now(),
                location=location,
                quality=random.uniform(0.8, 1.0),
                battery_level=random.uniform(80, 100),
                signal_strength=random.uniform(70, 100)
            )
            self.edge_aggregator.add_sensor_reading(humidity_reading)
    
    def register_example_devices(self):
        """Register example edge devices"""
        self.edge_aggregator.register_edge_device(
            device_id="device_001",
            device_type="sensor_node",
            location="Zone_A",
            capabilities=[SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.SOIL_MOISTURE],
            ip_address="192.168.1.101"
        )
        self.edge_aggregator.register_edge_device(
            device_id="device_002",
            device_type="sensor_node",
            location="Zone_B",
            capabilities=[SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.LIGHT_INTENSITY],
            ip_address="192.168.1.102"
        )
        self.edge_aggregator.register_edge_device(
            device_id="device_003",
            device_type="sensor_node",
            location="Zone_C",
            capabilities=[SensorType.TEMPERATURE, SensorType.CO2_LEVEL, SensorType.SOIL_PH],
            ip_address="192.168.1.103"
        )
    
    def handle_aggregated_data(self, data: dict):
        """Handle new aggregated data from edge aggregator"""
        self.logger.debug(f"Received aggregated data: {data.get('sensor_type')} at {data.get('location')}")
        
        # Cache aggregated data locally
        cache_key = f"agg:{data.get('sensor_type')}:{data.get('location')}:{data.get('timeframe')}"
        self.redis_edge_client.set(cache_key, data, ttl=600)  # 10 minutes
        
        # Sync to backend (async, don't block UI)
        self.sync_aggregated_data_to_backend(data)
        
        # Display in appropriate UI component (if available)
        # Try server_info as fallback if fog_output doesn't exist
        output_widget = getattr(self, 'fog_output', None) or getattr(self, 'server_info', None)
        if output_widget:
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            output_widget.append(
                f"[{timestamp}] 📊 AGG: {data.get('sensor_type')} @ {data.get('location')} "
                f"({data.get('timeframe')}): avg={data.get('average'):.2f}, "
                f"min={data.get('min'):.2f}, max={data.get('max'):.2f}, "
                f"count={data.get('count')}, quality={data.get('quality_score'):.2f}\n"
            )
    
    def sync_aggregated_data_to_backend(self, data: dict):
        """Sync aggregated data to backend via HTTP API"""
        try:
            payload = {
                'sensorType': data.get('sensor_type'),
                'location': data.get('location'),
                'timeframe': data.get('timeframe'),
                'data': {
                    'average': data.get('average'),
                    'min': data.get('min'),
                    'max': data.get('max'),
                    'count': data.get('count'),
                    'std_dev': data.get('std_dev'),
                    'quality_score': data.get('quality_score'),
                    'timestamp': data.get('timestamp')
                }
            }
            
            # Use requests in a non-blocking way (could be improved with QThread)
            import threading
            def sync_thread():
                try:
                    response = requests.post(
                        f"{self.backend_url}/fog/aggregated",
                        json=payload,
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.logger.debug(f"Synced aggregated data to backend: {data.get('sensor_type')}")
                    else:
                        self.logger.warning(f"Failed to sync aggregated data: {response.status_code}")
                except Exception as e:
                    self.logger.debug(f"Backend sync failed (non-critical): {e}")
            
            thread = threading.Thread(target=sync_thread, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Error syncing to backend: {e}")
    
    def handle_anomaly(self, anomaly: dict):
        """Handle detected anomaly"""
        self.logger.warning(f"Anomaly detected: {anomaly.get('message')}")
        
        # Sync anomaly to backend
        self.sync_anomaly_to_backend(anomaly)
        
        # Display anomaly in UI
        output_widget = getattr(self, 'fog_output', None) or getattr(self, 'server_info', None)
        if output_widget:
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            severity_icon = "🔴" if anomaly.get('severity') == 'critical' else "🟡" if anomaly.get('severity') == 'warning' else "🔵"
            output_widget.append(
                f"[{timestamp}] {severity_icon} ANOMALY: {anomaly.get('message')} "
                f"({anomaly.get('sensor_type')} @ {anomaly.get('location')})\n"
            )
    
    def sync_anomaly_to_backend(self, anomaly: dict):
        """Sync anomaly to backend via HTTP API"""
        try:
            import threading
            def sync_thread():
                try:
                    response = requests.post(
                        f"{self.backend_url}/fog/anomalies",
                        json=anomaly,
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.logger.debug(f"Synced anomaly to backend: {anomaly.get('anomaly_id')}")
                    else:
                        self.logger.warning(f"Failed to sync anomaly: {response.status_code}")
                except Exception as e:
                    self.logger.debug(f"Backend sync failed (non-critical): {e}")
            
            thread = threading.Thread(target=sync_thread, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.debug(f"Error syncing anomaly to backend: {e}")
    
    def handle_device_status(self, status: dict):
        """Handle device status change"""
        self.logger.info(f"Device status: {status.get('device_id')} - {status.get('status')}")
    
    def view_fog_aggregated_data(self):
        """View aggregated fog data from backend"""
        result = self.make_server_request('/fog/aggregated')
        if result:
            self.display_formatted_json("Fog Aggregated Data", result)
    
    def view_fog_devices(self):
        """View fog edge devices from backend"""
        result = self.make_server_request('/fog/devices')
        if result:
            self.display_formatted_json("Fog Edge Devices", result)
    
    def view_fog_anomalies(self):
        """View fog anomalies from backend"""
        limit = 20
        result = self.make_server_request(f'/fog/anomalies?limit={limit}')
        if result:
            self.display_formatted_json("Fog Anomalies", result)
        
    def update_connection_status(self, connected):
        self.rabbitmq_connected = connected
        if connected:
            self.connection_status.setText("✅ Connected to RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.success}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.success};
            """)
        else:
            self.connection_status.setText("❌ Disconnected from RabbitMQ")
            self.connection_status.setStyleSheet(f"""
                color: {self.theme.colors.error}; 
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_100};
                padding: 2px 6px;
                border-radius: {self.theme.borderRadius.sm};
                border: 1px solid {self.theme.colors.grey_300};
                border-left: 2px solid {self.theme.colors.error};
            """)
        
    def check_connection(self):
        if not self.rabbitmq_connected:
            self.logger.info("Attempting to reconnect to RabbitMQ...")
            self.command_worker.setup_rabbitmq()
        
    def send_user_command(self, command, parameters=None):
        """Send a user command with automatic retry"""
        command_id = str(uuid.uuid4())
        command_data = {
            'commandId': command_id,
            'command': command,
            'type': 'user',
            'parameters': parameters or {},
            'sessionId': self.session_id
        }
        
        self.pending_commands[command_id] = {
            "type": "user",
            "command": command,
            "parameters": parameters or {}
        }
        
        self.logger.info(f"Sending user command {command_id}: {command}")
        
        import time
        time.sleep(0.1)
        
        if self.command_worker.send_command(command_data):
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.user_output.append(f"[{timestamp}] Sent: {command}")
            return True
        else:
            self.logger.warning("First send attempt failed, attempting reconnect...")
            if self.command_worker.attempt_reconnect():
                time.sleep(0.1)
                if self.command_worker.send_command(command_data):
                    self.logger.info("Command sent successfully after reconnect")
                    timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
                    self.user_output.append(f"[{timestamp}] Sent: {command} [after reconnect]")
                    return True
            
            self.logger.error("Failed to send command after retry")
            timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
            self.user_output.append(f"[{timestamp}] Failed to send: {command}")
            return False
        
    def handle_response(self, response):
        command_id = response.get('commandId')
        result = response.get('result', {})
        cached = response.get('cached', False)
        error = response.get('error')
        session_id = response.get('sessionId')
        current_path = response.get('currentPath')
        
        self.logger.info(f"Received response for command {command_id}, cached: {cached}, error: {bool(error)}")
        
        # DEBUG: Log pending commands
        self.logger.info(f"Pending commands: {list(self.pending_commands.keys())}")
        
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        
        if command_id in self.pending_commands:
            command_info = self.pending_commands[command_id]
            self.logger.info(f"Found command info: type={command_info.get('type')}, command={command_info.get('command')}")
            
            # Path tracking removed (no longer needed without shell commands)
            # if current_path:
            #     self.current_path = current_path
            #     self.path_label.setText(self.current_path)
            #     self.logger.info(f"Current path updated to: {self.current_path}")
            
            if error:
                output_text = f"ERROR: {error}"
                self.logger.error(f"Command {command_id} failed: {error}")
            else:
                if isinstance(result, dict):
                    if 'output' in result:
                        output_text = result['output']
                    elif 'newPath' in result:
                        output_text = result['output'] if 'output' in result else f"Changed to: {result['newPath']}"
                    else:
                        output_text = json.dumps(result, indent=2)
                else:
                    output_text = str(result)
            
            cache_indicator = " [CACHED]" if cached else ""
            session_indicator = f" [Session: {session_id[:8]}...]" if session_id else ""
            
            # All commands are now user commands (greenhouse commands)
            self.logger.info(f"Appending to USER output: {output_text[:100]}...")
            self.user_output.append(f"[{timestamp}] Result{cache_indicator}{session_indicator}:\n{output_text}\n{'-'*50}")
                
            del self.pending_commands[command_id]
            
        else:
            self.logger.warning(f"Command ID {command_id} not found in pending_commands!")
            # Fallback: try to display anyway
            if error:
                output_text = f"ERROR: {error}"
            else:
                output_text = str(result)
            
            self.user_output.append(f"[{timestamp}] [UNKNOWN COMMAND] Result:\n{output_text}\n{'-'*50}")
            
        status_suffix = " (cached)" if cached else ""
        if error:
            self.status_label.setText(f"❌ Command failed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.error};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 6px 12px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.error};
            """)
        else:
            self.status_label.setText(f"✅ Command completed{status_suffix}")
            self.status_label.setStyleSheet(f"""
                color: {self.theme.colors.success};
                font-weight: {self.theme.typography.medium};
                background-color: {self.theme.colors.grey_50};
                padding: 6px 12px;
                border-radius: {self.theme.borderRadius.md};
                border-left: 3px solid {self.theme.colors.success};
            """)

    def handle_error(self, error_message):
        self.logger.error(f"Command worker error: {error_message}")
        self.show_error("System Error", error_message)

    def show_error(self, title, message):
        self.logger.warning(f"Showing error dialog: {title} - {message}")
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.exec_()

    def closeEvent(self, event):
        self.logger.info("Application shutting down")
        if self.command_worker:
            self.command_worker.disconnect()
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.stop()
        if hasattr(self, 'sensor_simulator_timer') and self.sensor_simulator_timer.isActive():
            self.sensor_simulator_timer.stop()
        if self.redis_edge_client:
            self.redis_edge_client.disconnect()
        event.accept()
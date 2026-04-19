import logging
import threading
from typing import Dict

import requests
from PyQt5.QtCore import QDateTime, QTimer

from modules.edge_fog_aggregator import EdgeToFogAggregator, SensorReading, SensorType
from modules.redis_client import RedisEdgeClient
from modules.config import config


class EdgeFogMixin:
    """
    Mixin that encapsulates Edge-to-Fog aggregation concerns:
    - Managing the EdgeToFogAggregator instance
    - Simulating / consuming sensor data
    - Syncing aggregated data and anomalies to backend
    - Handling device status notifications

    Expects the main window to provide:
      - self.backend_url (str)
      - self.logger (logging.Logger)
      - self.edge_aggregator (EdgeToFogAggregator)
      - self.redis_edge_client (RedisEdgeClient)
    """

    def setup_edge_aggregator(self):
        """Setup Edge-to-Fog aggregator and connect signals"""
        self.logger.info("Setting up Edge-to-Fog aggregator")

        # Connect aggregator signals to UI handlers
        self.edge_aggregator.new_aggregated_data.connect(self.handle_aggregated_data)
        self.edge_aggregator.anomaly_detected.connect(self.handle_anomaly)
        self.edge_aggregator.device_status_changed.connect(self.handle_device_status)

        # Connect to Redis for local caching
        self.redis_edge_client.connect()

        # Register example devices before starting the simulator timer
        self.register_example_devices()

        # Setup sensor data consumer (if RabbitMQ is available)
        self.setup_sensor_data_consumer()

        self.logger.info("Edge-to-Fog aggregator setup complete")

    def setup_sensor_data_consumer(self):
        """Setup consumer for sensor data from RabbitMQ or simulate it"""
        # For now, we'll use a timer to simulate sensor readings
        # In production, this would consume from a RabbitMQ queue
        self.sensor_simulator_timer = QTimer()
        self.sensor_simulator_timer.timeout.connect(self.simulate_sensor_reading)
        self.sensor_simulator_timer.start(config.EDGE_FOG_SENSOR_SIM_INTERVAL_MS)

        self.logger.info("Sensor data consumer started (simulation mode)")

    def simulate_sensor_reading(self):
        """Simulate sensor readings for testing"""
        from datetime import datetime
        import random

        devices = list(self.edge_aggregator.edge_devices.keys())
        default_triplet = ('device_001', 'device_002', 'device_003')
        if len(devices) < 3:
            devices = list(default_triplet)

        for device_id in devices[:3]:
            location = self.edge_aggregator.edge_devices.get(device_id, {}).get('location', 'Zone_A')
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
        ips = [x.strip() for x in config.EDGE_FOG_EXAMPLE_DEVICE_IPS.split(',') if x.strip()]
        fallback = ['192.168.1.101', '192.168.1.102', '192.168.1.103']
        while len(ips) < 3:
            ips.append(fallback[len(ips) % 3])

        specs = (
            (
                'device_001',
                'sensor_node',
                'Zone_A',
                [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.SOIL_MOISTURE],
                ips[0],
            ),
            (
                'device_002',
                'sensor_node',
                'Zone_B',
                [SensorType.TEMPERATURE, SensorType.HUMIDITY, SensorType.LIGHT_INTENSITY],
                ips[1],
            ),
            (
                'device_003',
                'sensor_node',
                'Zone_C',
                [SensorType.TEMPERATURE, SensorType.CO2_LEVEL, SensorType.SOIL_PH],
                ips[2],
            ),
        )
        for device_id, device_type, location, capabilities, ip_address in specs:
            self.edge_aggregator.register_edge_device(
                device_id=device_id,
                device_type=device_type,
                location=location,
                capabilities=capabilities,
                ip_address=ip_address,
            )

    def handle_aggregated_data(self, data: dict):
        """Handle new aggregated data from edge aggregator"""
        self.logger.debug(f"Received aggregated data: {data.get('sensor_type')} at {data.get('location')}")

        # Cache aggregated data locally
        cache_key = f"agg:{data.get('sensor_type')}:{data.get('location')}:{data.get('timeframe')}"
        self.redis_edge_client.set(cache_key, data, ttl=config.EDGE_FOG_REDIS_CACHE_TTL_SEC)

        # Sync to backend (async, don't block UI)
        self.sync_aggregated_data_to_backend(data)

        # Display in appropriate UI component (if available)
        # Log aggregated data (tables will be updated via API calls)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.logger.info(
            f"[{timestamp}] 📊 AGG: {data.get('sensor_type')} @ {data.get('location')} "
            f"({data.get('timeframe')}): avg={data.get('average'):.2f}, "
            f"min={data.get('min'):.2f}, max={data.get('max'):.2f}, "
            f"count={data.get('count')}, quality={data.get('quality_score'):.2f}"
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

        # Log anomaly (tables will be updated via API calls)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        severity_icon = "🔴" if anomaly.get('severity') == 'critical' else "🟡" if anomaly.get('severity') == 'warning' else "🔵"
        self.logger.warning(
            f"[{timestamp}] {severity_icon} ANOMALY: {anomaly.get('message')} "
            f"({anomaly.get('sensor_type')} @ {anomaly.get('location')})"
        )

    def sync_anomaly_to_backend(self, anomaly: dict):
        """Sync anomaly to backend via HTTP API"""
        try:
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




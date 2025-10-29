import json
import uuid
import logging
import math
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from enum import Enum
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class SensorType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    SOIL_MOISTURE = "soil_moisture"
    LIGHT_INTENSITY = "light_intensity"
    CO2_LEVEL = "co2_level"
    SOIL_PH = "soil_ph"

class DataQuality(Enum):
    EXCELLENT = 1.0
    GOOD = 0.8
    FAIR = 0.6
    POOR = 0.4
    UNRELIABLE = 0.2

@dataclass
class SensorReading:
    device_id: str
    sensor_type: SensorType
    value: float
    timestamp: datetime
    location: str
    quality: float = 1.0
    battery_level: Optional[float] = None
    signal_strength: Optional[float] = None

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['sensor_type'] = self.sensor_type.value
        return data

@dataclass
class AggregatedData:
    timeframe: str
    sensor_type: SensorType
    average: float
    min: float
    max: float
    count: int
    std_dev: float
    timestamp: datetime
    quality_score: float
    location: str

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['sensor_type'] = self.sensor_type.value
        return data

@dataclass
class Anomaly:
    anomaly_id: str
    sensor_type: SensorType
    location: str
    anomaly_type: str
    severity: str
    message: str
    timestamp: datetime
    value: float
    expected_range: tuple

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['sensor_type'] = self.sensor_type.value
        return data

class EdgeToFogAggregator(QObject):
    """Handles data aggregation from edge devices to fog node"""
    
    # Signals for UI updates
    new_aggregated_data = pyqtSignal(dict)
    anomaly_detected = pyqtSignal(dict)
    device_status_changed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.raw_data_buffer: Dict[str, List[SensorReading]] = {}
        self.aggregated_data: Dict[str, List[AggregatedData]] = {}
        self.edge_devices: Dict[str, Dict] = {}
        self.anomalies: List[Anomaly] = []
        self.aggregation_lock = threading.Lock()
        
        # Aggregation windows in seconds
        self.aggregation_windows = {
            '1min': 60,
            '5min': 300,
            '15min': 900,
            '1h': 3600
        }
        
        # Expected ranges for different sensor types
        self.expected_ranges = {
            SensorType.TEMPERATURE: (15.0, 35.0),      # Celsius
            SensorType.HUMIDITY: (30.0, 80.0),         # Percentage
            SensorType.SOIL_MOISTURE: (20.0, 80.0),    # Percentage
            SensorType.LIGHT_INTENSITY: (0.0, 1000.0), # Lux
            SensorType.CO2_LEVEL: (300.0, 1500.0),     # PPM
            SensorType.SOIL_PH: (5.5, 7.5)             # pH
        }
        
        # Anomaly detection thresholds
        self.anomaly_thresholds = {
            'variance_threshold': 0.3,  # 30% of average value
            'consecutive_outliers': 3,
            'rate_of_change': 5.0       # Max change per minute
        }
        
        self.logger = logging.getLogger('EdgeFogAggregator')
        self.setup_aggregation_timers()
    
    def setup_aggregation_timers(self):
        """Setup timers for periodic aggregation"""
        self.aggregation_timer = QTimer()
        self.aggregation_timer.timeout.connect(self.run_periodic_aggregation)
        self.aggregation_timer.start(60000)  # Run every minute
        
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_old_data)
        self.cleanup_timer.start(300000)  # Cleanup every 5 minutes
    
    def register_edge_device(self, device_id: str, device_type: str, location: str, 
                           capabilities: List[SensorType], ip_address: str = None):
        """Register a new edge device"""
        with self.aggregation_lock:
            self.edge_devices[device_id] = {
                'type': device_type,
                'location': location,
                'capabilities': capabilities,
                'ip_address': ip_address,
                'last_seen': datetime.now(),
                'status': 'online',
                'battery_level': 100.0,
                'registered_at': datetime.now()
            }
            
            device_info = {
                'device_id': device_id,
                'status': 'registered',
                'location': location,
                'capabilities': [cap.value for cap in capabilities]
            }
            
            self.device_status_changed.emit(device_info)
            self.logger.info(f"Registered edge device: {device_id} at {location}")
    
    def update_device_status(self, device_id: str, status: str, battery_level: float = None):
        """Update device status and battery level"""
        if device_id in self.edge_devices:
            self.edge_devices[device_id]['last_seen'] = datetime.now()
            self.edge_devices[device_id]['status'] = status
            
            if battery_level is not None:
                self.edge_devices[device_id]['battery_level'] = battery_level
            
            status_info = {
                'device_id': device_id,
                'status': status,
                'battery_level': battery_level,
                'last_seen': datetime.now().isoformat()
            }
            
            self.device_status_changed.emit(status_info)
    
    def add_sensor_reading(self, reading: SensorReading):
        """Add raw sensor data to aggregation buffer"""
        with self.aggregation_lock:
            key = f"{reading.sensor_type.value}_{reading.location}"
            
            if key not in self.raw_data_buffer:
                self.raw_data_buffer[key] = []
            
            self.raw_data_buffer[key].append(reading)
            
            # Update device status
            self.update_device_status(reading.device_id, 'online', reading.battery_level)
            
            # Check for immediate anomalies
            self.check_immediate_anomalies(reading)
            
            self.logger.debug(f"Added reading: {reading.sensor_type.value} at {reading.location}: {reading.value}")
    
    def check_immediate_anomalies(self, reading: SensorReading):
        """Check for immediate anomalies in new readings"""
        if reading.sensor_type in self.expected_ranges:
            min_expected, max_expected = self.expected_ranges[reading.sensor_type]
            
            if reading.value < min_expected or reading.value > max_expected:
                anomaly = Anomaly(
                    anomaly_id=str(uuid.uuid4()),
                    sensor_type=reading.sensor_type,
                    location=reading.location,
                    anomaly_type="out_of_range",
                    severity="critical" if abs(reading.value - (min_expected + max_expected)/2) > 10 else "warning",
                    message=f"{reading.sensor_type.value} out of range: {reading.value:.1f} (expected {min_expected}-{max_expected})",
                    timestamp=datetime.now(),
                    value=reading.value,
                    expected_range=(min_expected, max_expected)
                )
                
                self.anomalies.append(anomaly)
                self.anomaly_detected.emit(anomaly.to_dict())
                self.logger.warning(f"Anomaly detected: {anomaly.message}")
    
    def run_periodic_aggregation(self):
        """Run aggregation for all sensor types and locations"""
        with self.aggregation_lock:
            for key in list(self.raw_data_buffer.keys()):
                # Extract sensor type and location from key
                sensor_type_str, location = key.split('_', 1)
                sensor_type = SensorType(sensor_type_str)
                
                for window_name, window_seconds in self.aggregation_windows.items():
                    aggregated = self.aggregate_data(sensor_type, location, window_name)
                    
                    if aggregated:
                        # Store aggregated data
                        agg_key = f"{sensor_type.value}_{location}_{window_name}"
                        if agg_key not in self.aggregated_data:
                            self.aggregated_data[agg_key] = []
                        
                        self.aggregated_data[agg_key].append(aggregated)
                        
                        # Emit signal for UI updates
                        self.new_aggregated_data.emit(aggregated.to_dict())
                        
                        # Run advanced anomaly detection
                        self.detect_advanced_anomalies(aggregated)
    
    def aggregate_data(self, sensor_type: SensorType, location: str, window: str) -> Optional[AggregatedData]:
        """Aggregate data for specific sensor type and time window"""
        key = f"{sensor_type.value}_{location}"
        if key not in self.raw_data_buffer:
            return None
        
        readings = self.raw_data_buffer[key]
        window_seconds = self.aggregation_windows[window]
        
        # Filter readings within time window
        current_time = datetime.now()
        recent_readings = [
            r for r in readings 
            if (current_time - r.timestamp).total_seconds() <= window_seconds
        ]
        
        if not recent_readings:
            return None
        
        values = [r.value for r in recent_readings]
        quality_scores = [r.quality for r in recent_readings]
        
        # Calculate quality-weighted average
        total_quality = sum(quality_scores)
        if total_quality > 0:
            weighted_values = [v * q for v, q in zip(values, quality_scores)]
            average = sum(weighted_values) / total_quality
        else:
            average = sum(values) / len(values)
        
        return AggregatedData(
            timeframe=window,
            sensor_type=sensor_type,
            average=average,
            min=min(values),
            max=max(values),
            count=len(values),
            std_dev=self._calculate_std_dev(values),
            timestamp=current_time,
            quality_score=sum(quality_scores) / len(quality_scores),
            location=location
        )
    
    def detect_advanced_anomalies(self, aggregated: AggregatedData):
        """Detect advanced anomalies in aggregated data"""
        anomalies = []
        
        # High variance detection
        if aggregated.std_dev > (aggregated.average * self.anomaly_thresholds['variance_threshold']):
            anomalies.append({
                'type': 'high_variance',
                'severity': 'warning',
                'message': f'High variance detected in {aggregated.sensor_type.value} readings'
            })
        
        # Rate of change detection (compare with previous aggregation)
        rate_anomaly = self.detect_rate_of_change_anomaly(aggregated)
        if rate_anomaly:
            anomalies.append(rate_anomaly)
        
        # Trend detection
        trend_anomaly = self.detect_trend_anomaly(aggregated)
        if trend_anomaly:
            anomalies.append(trend_anomaly)
        
        # Create anomaly objects
        for anomaly_info in anomalies:
            anomaly = Anomaly(
                anomaly_id=str(uuid.uuid4()),
                sensor_type=aggregated.sensor_type,
                location=aggregated.location,
                anomaly_type=anomaly_info['type'],
                severity=anomaly_info['severity'],
                message=anomaly_info['message'],
                timestamp=datetime.now(),
                value=aggregated.average,
                expected_range=self.expected_ranges.get(aggregated.sensor_type, (0, 100))
            )
            
            self.anomalies.append(anomaly)
            self.anomaly_detected.emit(anomaly.to_dict())
    
    def detect_rate_of_change_anomaly(self, current_agg: AggregatedData) -> Optional[Dict]:
        """Detect anomalies based on rate of change"""
        key = f"{current_agg.sensor_type.value}_{current_agg.location}_{current_agg.timeframe}"
        
        if key in self.aggregated_data and len(self.aggregated_data[key]) >= 2:
            previous_data = self.aggregated_data[key][-2]
            time_diff = (current_agg.timestamp - previous_data.timestamp).total_seconds() / 60  # in minutes
            
            if time_diff > 0:
                rate_of_change = abs(current_agg.average - previous_data.average) / time_diff
                
                if rate_of_change > self.anomaly_thresholds['rate_of_change']:
                    return {
                        'type': 'rapid_change',
                        'severity': 'warning',
                        'message': f'Rapid change in {current_agg.sensor_type.value}: {rate_of_change:.1f}/min'
                    }
        
        return None
    
    def detect_trend_anomaly(self, current_agg: AggregatedData) -> Optional[Dict]:
        """Detect anomalies based on trend analysis"""
        key = f"{current_agg.sensor_type.value}_{current_agg.location}_{current_agg.timeframe}"
        
        if key in self.aggregated_data and len(self.aggregated_data[key]) >= 5:
            recent_data = self.aggregated_data[key][-5:]
            values = [agg.average for agg in recent_data]
            
            # Simple trend detection: check if last 3 points are consistently increasing/decreasing
            if (all(values[i] < values[i+1] for i in range(len(values)-1)) or
                all(values[i] > values[i+1] for i in range(len(values)-1))):
                
                trend = "increasing" if values[-1] > values[0] else "decreasing"
                return {
                    'type': 'sustained_trend',
                    'severity': 'info',
                    'message': f'Sustained {trend} trend in {current_agg.sensor_type.value}'
                }
        
        return None
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation of values"""
        if len(values) <= 1:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def get_aggregated_metrics(self, sensor_type: SensorType = None, location: str = None) -> Dict[str, Any]:
        """Get aggregated metrics for dashboard display"""
        with self.aggregation_lock:
            metrics = {}
            
            locations = [location] if location else set(
                device['location'] for device in self.edge_devices.values()
            )
            
            sensor_types = [sensor_type] if sensor_type else list(SensorType)
            
            for loc in locations:
                metrics[loc] = {}
                for s_type in sensor_types:
                    metrics[loc][s_type.value] = {}
                    for window in ['1min', '5min', '15min']:
                        aggregated = self.aggregate_data(s_type, loc, window)
                        if aggregated:
                            metrics[loc][s_type.value][window] = aggregated.to_dict()
            
            return metrics
    
    def get_device_status(self) -> List[Dict]:
        """Get status of all edge devices"""
        with self.aggregation_lock:
            devices = []
            for device_id, info in self.edge_devices.items():
                device_status = {
                    'device_id': device_id,
                    'type': info['type'],
                    'location': info['location'],
                    'status': info['status'],
                    'battery_level': info.get('battery_level', 100.0),
                    'last_seen': info['last_seen'].isoformat(),
                    'capabilities': [cap.value for cap in info['capabilities']]
                }
                devices.append(device_status)
            
            return devices
    
    def get_recent_anomalies(self, limit: int = 10) -> List[Dict]:
        """Get recent anomalies"""
        with self.aggregation_lock:
            recent_anomalies = sorted(self.anomalies, key=lambda x: x.timestamp, reverse=True)[:limit]
            return [anomaly.to_dict() for anomaly in recent_anomalies]
    
    def cleanup_old_data(self):
        """Clean up old data to prevent memory overflow"""
        with self.aggregation_lock:
            current_time = datetime.now()
            
            # Clean raw data buffer (keep only last 2 hours)
            for key in list(self.raw_data_buffer.keys()):
                self.raw_data_buffer[key] = [
                    r for r in self.raw_data_buffer[key] 
                    if (current_time - r.timestamp).total_seconds() < 7200  # 2 hours
                ]
                
                # Remove empty buffers
                if not self.raw_data_buffer[key]:
                    del self.raw_data_buffer[key]
            
            # Clean aggregated data (keep only last 24 hours)
            for key in list(self.aggregated_data.keys()):
                self.aggregated_data[key] = [
                    agg for agg in self.aggregated_data[key] 
                    if (current_time - agg.timestamp).total_seconds() < 86400  # 24 hours
                ]
                
                # Remove empty lists
                if not self.aggregated_data[key]:
                    del self.aggregated_data[key]
            
            # Clean old anomalies (keep only last 100)
            if len(self.anomalies) > 100:
                self.anomalies = sorted(self.anomalies, key=lambda x: x.timestamp, reverse=True)[:100]
            
            self.logger.debug("Cleaned up old data")
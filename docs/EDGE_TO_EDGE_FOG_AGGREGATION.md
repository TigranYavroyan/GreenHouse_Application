# Edge-to-Edge Fog Data Aggregation Mechanism

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Data Flow](#data-flow)
5. [Implementation Details](#implementation-details)
6. [API Reference](#api-reference)
7. [Configuration](#configuration)
8. [Usage Examples](#usage-examples)
9. [Anomaly Detection](#anomaly-detection)
10. [Caching Strategy](#caching-strategy)

---

## Overview

The Edge-to-Edge Fog Data Aggregation system is a distributed data processing architecture designed for greenhouse automation. It implements a three-tier architecture:

- **Edge Layer**: Physical sensor devices collecting raw environmental data
- **Fog Layer**: Desktop application (PyQt5) that aggregates and processes data locally
- **Backend Layer**: Express.js server that coordinates multiple fog nodes and provides centralized storage

### Key Benefits

- **Offline-First Operation**: Local caching allows the system to function without backend connectivity
- **Reduced Network Traffic**: Aggregation at the fog layer reduces data volume sent to backend
- **Real-Time Processing**: Time-windowed aggregation provides near real-time insights
- **Anomaly Detection**: Automatic detection of unusual patterns in sensor data
- **Scalability**: Multiple edge devices can be managed by a single fog node
- **Quality-Aware**: Quality scoring ensures reliable data aggregation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Edge Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Sensor   │  │ Sensor   │  │ Sensor   │  │ Sensor   │       │
│  │ Device 1 │  │ Device 2 │  │ Device 3 │  │ Device N │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │            │              │              │              │
│       └────────────┴──────────────┴──────────────┘              │
│                          │                                      │
│                          ▼                                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Raw Sensor Readings
                            │ (via RabbitMQ or Direct)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Fog Layer (Desktop App)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         EdgeToFogAggregator                              │  │
│  │  • Time-windowed aggregation (1min, 5min, 15min, 1h)     │  │
│  │  • Anomaly detection                                     │  │
│  │  • Device management                                     │  │
│  │  • Quality scoring                                       │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         RedisEdgeClient (Local Cache)                    │  │
│  │  • Cache-aside pattern                                   │  │
│  │  • TTL-based expiration                                  │  │
│  │  • Namespace organization                                │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│                 │ Aggregated Data + Anomalies                   │
│                 ▼                                                │
│         HTTP POST (Async, Non-blocking)                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend Layer (Express.js)                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         REST API Endpoints                               │  │
│  │  • POST /fog/aggregated                                 │  │
│  │  • GET  /fog/aggregated                                  │  │
│  │  • POST /fog/anomalies                                  │  │
│  │  • GET  /fog/anomalies                                  │  │
│  │  • GET  /fog/devices                                    │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                                │
│                 ▼                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Central Redis Cache                             │  │
│  │  • fog:agg:{sensorType}:{location}:{timeframe}         │  │
│  │  • fog:anomaly:{anomaly_id}                            │  │
│  │  • fog:device:{device_id}                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. EdgeToFogAggregator (`frontend/modules/edge_fog_aggregator.py`)

The core aggregation engine that processes raw sensor data and generates aggregated metrics.

#### Key Responsibilities:
- **Data Buffering**: Maintains raw sensor readings in memory buffers organized by sensor type and location
- **Time-Windowed Aggregation**: Calculates statistics (average, min, max, std_dev, count) for multiple time windows
- **Anomaly Detection**: Identifies unusual patterns using multiple algorithms
- **Device Management**: Tracks edge device registration, status, and capabilities
- **Quality Scoring**: Applies quality-weighted aggregation based on sensor reliability

#### Aggregation Windows:
- `1min`: 60 seconds - Real-time monitoring
- `5min`: 300 seconds - Short-term trends
- `15min`: 900 seconds - Medium-term analysis
- `1h`: 3600 seconds - Long-term patterns

#### Data Structures:

```python
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

@dataclass
class Anomaly:
    anomaly_id: str
    sensor_type: SensorType
    location: str
    anomaly_type: str
    severity: str  # 'critical', 'warning', 'info'
    message: str
    timestamp: datetime
    value: float
    expected_range: tuple
```

### 2. RedisEdgeClient (`frontend/modules/redis_client.py`)

Local Redis client for edge node caching.

#### Features:
- **Cache-Aside Pattern**: Application checks cache first, then fetches from source if miss
- **TTL Management**: Automatic expiration of cached data
- **Namespace Organization**: Keys organized by namespace (e.g., `agg:sensor_type:location:timeframe`)
- **Graceful Degradation**: System continues to function if Redis is unavailable

#### Key Operations:
- `get(key)`: Retrieve cached value
- `set(key, value, ttl)`: Store value with expiration
- `delete(key)`: Remove cached value
- `clear_namespace(namespace)`: Clear all keys in a namespace

### 3. Backend API (`backend/router/routes.js`)

REST API endpoints for fog data management.

#### Endpoints:
- `POST /fog/aggregated`: Store aggregated sensor data
- `GET /fog/aggregated`: Retrieve aggregated data with filtering
- `POST /fog/anomalies`: Store detected anomalies
- `GET /fog/anomalies`: Retrieve recent anomalies
- `GET /fog/devices`: List registered edge devices

### 4. Integration Layer (`frontend/modules/greenhouse.py`)

Desktop application integration that connects all components.

#### Responsibilities:
- **Signal Handling**: Connects aggregator signals to UI update handlers
- **Backend Sync**: Asynchronously syncs aggregated data and anomalies to backend
- **Sensor Data Input**: Receives sensor readings (simulated or from RabbitMQ)
- **UI Updates**: Displays aggregated data and anomalies in the Server tab

---

## Data Flow

### 1. Sensor Data Collection

**Current Implementation (Simulation)**:
```python
# Timer-based simulation (every 5 seconds)
def simulate_sensor_reading(self):
    reading = SensorReading(
        device_id="device_001",
        sensor_type=SensorType.TEMPERATURE,
        value=20.0 + random.uniform(-5, 10),
        timestamp=datetime.now(),
        location="Zone_A",
        quality=random.uniform(0.8, 1.0)
    )
    self.edge_aggregator.add_sensor_reading(reading)
```

**Production Implementation** (RabbitMQ Consumer):
```python
# Would consume from RabbitMQ queue
def consume_sensor_data(self, message):
    data = json.loads(message.body)
    reading = SensorReading(**data)
    self.edge_aggregator.add_sensor_reading(reading)
```

### 2. Aggregation Process

1. **Raw Data Buffer**: Sensor readings are stored in `raw_data_buffer` organized by `{sensor_type}_{location}`
2. **Periodic Aggregation**: Timer triggers aggregation every 60 seconds
3. **Time Window Processing**: For each time window (1min, 5min, 15min, 1h):
   - Filter readings within the time window
   - Calculate statistics (average, min, max, std_dev, count)
   - Apply quality-weighted averaging
   - Generate `AggregatedData` object
4. **Signal Emission**: Emit `new_aggregated_data` signal with aggregated data

### 3. Local Caching

```python
def handle_aggregated_data(self, data: dict):
    # Cache key format: agg:{sensor_type}:{location}:{timeframe}
    cache_key = f"agg:{data.get('sensor_type')}:{data.get('location')}:{data.get('timeframe')}"
    self.redis_edge_client.set(cache_key, data, ttl=600)  # 10 minutes
```

### 4. Backend Synchronization

```python
def sync_aggregated_data_to_backend(self, data: dict):
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
    # Async HTTP POST in background thread
    requests.post(f"{backend_url}/fog/aggregated", json=payload)
```

### 5. Backend Storage

Backend stores data in Redis with namespace organization:
- **Aggregated Data**: `fog:agg:{sensorType}:{location}:{timeframe}`
- **Anomalies**: `fog:anomaly:{anomaly_id}`
- **Devices**: `fog:device:{device_id}`

TTL values:
- 1min aggregations: 300 seconds (5 minutes)
- 5min aggregations: 600 seconds (10 minutes)
- 15min aggregations: 1800 seconds (30 minutes)
- 1h aggregations: 3600 seconds (1 hour)
- Anomalies: 86400 seconds (24 hours)

---

## Implementation Details

### Aggregation Algorithm

The aggregation process uses quality-weighted averaging:

```python
def aggregate_data(self, sensor_type: SensorType, location: str, window: str):
    # Filter readings within time window
    recent_readings = [
        r for r in readings 
        if (current_time - r.timestamp).total_seconds() <= window_seconds
    ]
    
    values = [r.value for r in recent_readings]
    quality_scores = [r.quality for r in recent_readings]
    
    # Quality-weighted average
    total_quality = sum(quality_scores)
    if total_quality > 0:
        weighted_values = [v * q for v, q in zip(values, quality_scores)]
        average = sum(weighted_values) / total_quality
    else:
        average = sum(values) / len(values)
    
    # Calculate statistics
    return AggregatedData(
        average=average,
        min=min(values),
        max=max(values),
        count=len(values),
        std_dev=self._calculate_std_dev(values),
        quality_score=sum(quality_scores) / len(quality_scores)
    )
```

### Thread Safety

The aggregator uses `threading.Lock` to ensure thread-safe operations:

```python
def add_sensor_reading(self, reading: SensorReading):
    with self.aggregation_lock:
        # Thread-safe buffer update
        self.raw_data_buffer[key].append(reading)
```

### Non-Blocking UI

All I/O operations run in background threads to prevent UI blocking:

```python
def sync_aggregated_data_to_backend(self, data: dict):
    import threading
    def sync_thread():
        requests.post(f"{backend_url}/fog/aggregated", json=payload)
    
    thread = threading.Thread(target=sync_thread, daemon=True)
    thread.start()
```

### Periodic Cleanup

Automatic cleanup prevents memory overflow:

```python
def cleanup_old_data(self):
    # Clean raw data buffer (keep only last 2 hours)
    # Clean aggregated data (keep only last 24 hours)
    # Keep only last 100 anomalies
```

---

## API Reference

### POST /fog/aggregated

Store aggregated sensor data.

**Request Body**:
```json
{
  "sensorType": "temperature",
  "location": "Zone_A",
  "timeframe": "1min",
  "data": {
    "average": 22.5,
    "min": 20.0,
    "max": 25.0,
    "count": 12,
    "std_dev": 1.2,
    "quality_score": 0.95,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Response**: `200 OK` with stored data

**Redis Key**: `fog:agg:temperature:Zone_A:1min`

### GET /fog/aggregated

Retrieve aggregated data with optional filtering.

**Query Parameters**:
- `sensorType` (optional): Filter by sensor type
- `location` (optional): Filter by location
- `timeframe` (optional): Filter by time window

**Example**: `GET /fog/aggregated?sensorType=temperature&location=Zone_A`

**Response**:
```json
{
  "count": 4,
  "data": [
    {
      "sensorType": "temperature",
      "location": "Zone_A",
      "timeframe": "1min",
      "average": 22.5,
      "min": 20.0,
      "max": 25.0,
      "count": 12,
      "std_dev": 1.2,
      "quality_score": 0.95,
      "timestamp": "2024-01-15T10:30:00Z",
      "receivedAt": "2024-01-15T10:30:05Z"
    }
  ]
}
```

### POST /fog/anomalies

Store detected anomaly.

**Request Body**:
```json
{
  "anomaly_id": "uuid-here",
  "sensor_type": "temperature",
  "location": "Zone_A",
  "anomaly_type": "out_of_range",
  "severity": "critical",
  "message": "Temperature out of range: 40.0 (expected 15.0-35.0)",
  "timestamp": "2024-01-15T10:30:00Z",
  "value": 40.0,
  "expected_range": [15.0, 35.0]
}
```

**Response**: `200 OK`

### GET /fog/anomalies

Retrieve recent anomalies.

**Query Parameters**:
- `limit` (optional, default: 10): Maximum number of anomalies to return

**Response**:
```json
{
  "count": 5,
  "anomalies": [
    {
      "anomaly_id": "uuid-here",
      "sensor_type": "temperature",
      "location": "Zone_A",
      "anomaly_type": "out_of_range",
      "severity": "critical",
      "message": "Temperature out of range: 40.0",
      "timestamp": "2024-01-15T10:30:00Z",
      "value": 40.0,
      "expected_range": [15.0, 35.0]
    }
  ]
}
```

### GET /fog/devices

List all registered edge devices.

**Response**:
```json
{
  "count": 3,
  "devices": [
    {
      "device_id": "device_001",
      "type": "sensor_node",
      "location": "Zone_A",
      "status": "online",
      "battery_level": 85.0,
      "last_seen": "2024-01-15T10:30:00Z",
      "capabilities": ["temperature", "humidity", "soil_moisture"]
    }
  ]
}
```

---

## Configuration

### Frontend Configuration (`frontend/modules/config.py`)

```python
# Redis Edge Cache Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Backend URL
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:3000')
```

### Environment Variables

**Frontend**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
BACKEND_URL=http://localhost:3000
```

**Backend**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Aggregation Configuration

Aggregation windows and thresholds are configured in `EdgeToFogAggregator`:

```python
self.aggregation_windows = {
    '1min': 60,
    '5min': 300,
    '15min': 900,
    '1h': 3600
}

self.expected_ranges = {
    SensorType.TEMPERATURE: (15.0, 35.0),
    SensorType.HUMIDITY: (30.0, 80.0),
    SensorType.SOIL_MOISTURE: (20.0, 80.0),
    SensorType.LIGHT_INTENSITY: (0.0, 1000.0),
    SensorType.CO2_LEVEL: (300.0, 1500.0),
    SensorType.SOIL_PH: (5.5, 7.5)
}

self.anomaly_thresholds = {
    'variance_threshold': 0.3,  # 30% of average value
    'consecutive_outliers': 3,
    'rate_of_change': 5.0  # Max change per minute
}
```

---

## Usage Examples

### Registering an Edge Device

```python
aggregator.register_edge_device(
    device_id="device_001",
    device_type="sensor_node",
    location="Zone_A",
    capabilities=[
        SensorType.TEMPERATURE,
        SensorType.HUMIDITY,
        SensorType.SOIL_MOISTURE
    ],
    ip_address="192.168.1.101"
)
```

### Adding Sensor Reading

```python
reading = SensorReading(
    device_id="device_001",
    sensor_type=SensorType.TEMPERATURE,
    value=22.5,
    timestamp=datetime.now(),
    location="Zone_A",
    quality=0.95,
    battery_level=85.0,
    signal_strength=90.0
)
aggregator.add_sensor_reading(reading)
```

### Retrieving Aggregated Metrics

```python
metrics = aggregator.get_aggregated_metrics(
    sensor_type=SensorType.TEMPERATURE,
    location="Zone_A"
)
```

### Getting Device Status

```python
devices = aggregator.get_device_status()
for device in devices:
    print(f"{device['device_id']}: {device['status']}")
```

### Accessing Recent Anomalies

```python
anomalies = aggregator.get_recent_anomalies(limit=10)
for anomaly in anomalies:
    print(f"{anomaly['severity']}: {anomaly['message']}")
```

---

## Anomaly Detection

The system implements multiple anomaly detection algorithms:

### 1. Out-of-Range Detection

Immediate detection when sensor reading exceeds expected range:

```python
if reading.value < min_expected or reading.value > max_expected:
    # Create anomaly
    severity = "critical" if deviation > 10 else "warning"
```

### 2. High Variance Detection

Detects when standard deviation exceeds threshold:

```python
if aggregated.std_dev > (aggregated.average * 0.3):
    # High variance detected
    anomaly_type = "high_variance"
    severity = "warning"
```

### 3. Rate of Change Detection

Detects rapid changes in sensor values:

```python
rate_of_change = abs(current_avg - previous_avg) / time_diff_minutes
if rate_of_change > 5.0:  # 5 units per minute
    anomaly_type = "rapid_change"
    severity = "warning"
```

### 4. Trend Detection

Identifies sustained increasing or decreasing trends:

```python
# Check if last 5 points show consistent trend
if all(values[i] < values[i+1] for i in range(len(values)-1)):
    anomaly_type = "sustained_trend"
    severity = "info"
```

### Anomaly Severity Levels

- **critical**: Immediate attention required (e.g., out of range by >10 units)
- **warning**: Potential issue (e.g., high variance, rapid change)
- **info**: Informational (e.g., sustained trend)

---

## Caching Strategy

### Cache-Aside Pattern

1. **Read Path**:
   - Check local Redis cache first
   - If miss, fetch from aggregator
   - Store in cache for future requests

2. **Write Path**:
   - Generate aggregated data
   - Store in local cache
   - Sync to backend asynchronously

### Cache Key Organization

**Local Edge Cache**:
- `agg:{sensor_type}:{location}:{timeframe}` - Aggregated data
- TTL: 600 seconds (10 minutes)

**Backend Central Cache**:
- `fog:agg:{sensorType}:{location}:{timeframe}` - Aggregated data
- `fog:anomaly:{anomaly_id}` - Anomalies
- `fog:device:{device_id}` - Device information

### TTL Strategy

- **Short-term data (1min)**: 5 minutes TTL
- **Medium-term data (5min, 15min)**: 10-30 minutes TTL
- **Long-term data (1h)**: 1 hour TTL
- **Anomalies**: 24 hours TTL

### Cache Invalidation

- Automatic expiration via TTL
- Manual invalidation via `clear_namespace()`
- No explicit invalidation on updates (eventual consistency)

---

## Edge-to-Edge Communication

### Current Implementation

Currently, edge nodes communicate with the backend only. Direct edge-to-edge communication is a future enhancement.

### Future Enhancement: Direct Edge-to-Edge Sync

**Proposed Architecture**:
1. Edge nodes publish aggregated data to RabbitMQ exchange
2. Other edge nodes subscribe to relevant topics
3. Local cache updated from peer nodes
4. Conflict resolution using timestamps or version vectors

**Benefits**:
- Reduced latency for peer-to-peer queries
- Reduced backend load
- Improved resilience (works even if backend is down)

---

## Performance Considerations

### Memory Management

- Raw data buffer: Keeps last 2 hours of readings
- Aggregated data: Keeps last 24 hours
- Anomalies: Keeps last 100 entries
- Automatic cleanup every 5 minutes

### Network Optimization

- Aggregation reduces data volume by ~90% (12 readings → 1 aggregation)
- Async backend sync prevents UI blocking
- Graceful degradation if backend unavailable

### Scalability

- Each fog node can handle multiple edge devices
- Backend can coordinate multiple fog nodes
- Redis horizontal scaling for large deployments

---

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis is running: `redis-cli ping`
   - Verify `REDIS_HOST` and `REDIS_PORT` configuration
   - System continues to function without cache (graceful degradation)

2. **Backend Sync Fails**
   - Check backend is running: `curl http://localhost:3000/metadata/health/`
   - Verify `BACKEND_URL` configuration
   - Check network connectivity
   - Errors are logged but don't block aggregation

3. **No Aggregated Data**
   - Verify sensor readings are being added: Check logs
   - Check aggregation timer is running
   - Verify device registration

4. **Anomalies Not Detected**
   - Check expected ranges configuration
   - Verify anomaly thresholds
   - Check sensor data quality scores

---

## Testing

### Manual Testing

1. **Start Backend**:
   ```bash
   cd backend && npm start
   ```

2. **Start Redis**:
   ```bash
   docker compose up redis -d
   ```

3. **Start Frontend**:
   ```bash
   cd frontend && python main.py
   ```

4. **Verify Aggregation**:
   - Check Server tab for aggregated data (appears every minute)
   - Verify data is cached locally
   - Check backend endpoints return data

### API Testing

Fog routes require a JWT from `POST /auth/login` (same as other authenticated HTTP APIs).

```bash
TOKEN="<paste_access_token_here>"

# Get aggregated data
curl -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:3000/fog/aggregated?sensorType=temperature"

# Get anomalies
curl -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:3000/fog/anomalies?limit=10"

# Get devices
curl -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:3000/fog/devices"
```

---

## Future Enhancements

1. **Real RabbitMQ Consumer**: Replace simulation with actual RabbitMQ consumer
2. **Dedicated Fog Tab**: Add UI tab for fog data visualization
3. **Edge-to-Edge Sync**: Direct edge node communication
4. **Advanced Visualization**: Charts and graphs for aggregated metrics
5. **Device Auto-Discovery**: Automatic device discovery instead of manual registration
6. **Machine Learning**: ML-based anomaly detection
7. **Predictive Analytics**: Forecast future sensor values
8. **Multi-Fog Coordination**: Backend coordinates multiple fog nodes

---

## References

- **Integration Summary**: `docs/EDGE_FOG_INTEGRATION_SUMMARY.md`
- **Architecture Description**: `docs/overall_architecture_description.txt`
- **Source Code**:
  - `frontend/modules/edge_fog_aggregator.py`
  - `frontend/modules/redis_client.py`
  - `frontend/modules/greenhouse.py`
  - `backend/router/routes.js`

---

## Conclusion

The Edge-to-Edge Fog Data Aggregation system provides a robust, scalable, and offline-capable solution for greenhouse automation data processing. It efficiently aggregates sensor data at the fog layer, detects anomalies in real-time, and provides a centralized API for querying aggregated data across multiple edge nodes.


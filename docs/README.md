# Greenhouse Automation Application


A distributed greenhouse automation system with a PyQt5 desktop frontend and Node.js backend, communicating via RabbitMQ message queues and using Redis for caching.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
- [Backend Modules](#backend-modules)
- [Frontend Modules](#frontend-modules)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Edge-to-Fog Data Aggregation](#edge-to-fog-data-aggregation)
- [Dependencies](#dependencies)

---

## Architecture Overview

### High-Level Architecture

The Greenhouse Automation Application follows a **microservices architecture** with clear separation between frontend, backend, and infrastructure services:

```
┌─────────────────┐
│  PyQt5 Frontend │  (Desktop GUI Application)
│   (Python)      │
└────────┬────────┘
         │
         │ RabbitMQ Messages
         │ (greenhouse_commands)
         ▼
┌─────────────────┐
│  RabbitMQ       │  (Message Broker)
│  Message Queue  │
└────────┬────────┘
         │
         │ Command Processing
         ▼
┌─────────────────┐
│  Node.js        │  (Express API Server)
│  Backend        │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────────────┐
│ Redis  │ │ Greenhouse Core │
│ Cache  │ │ (Simulator/Real)│
└────────┘ └──────────────────┘
         │RabbitMQClient
         │ HTTP API
         ▼
┌─────────────────┐
│ Greenhouse Core │  (FastAPI Simulator or Real Core)
│   Simulator     │
└─────────────────┘
```

### Step-by-Step Architecture Flow

#### 1. **Frontend Initialization**
- PyQt5 desktop application starts with a unique session ID
- `CommandWorker` establishes connection to RabbitMQ
- GUI displays connection status and session information

#### 2. **Command Submission**
- User interacts with GUI (Control tab, Scheduling tab, or Server tab)
- Frontend creates command payload with:
  - `commandId` (UUID)
  - `command` (e.g., "read_temperature_data", "switch_water_canal", "read_sensor", "switch_actuator")
  - `parameters` (command-specific parameters)
  - `sessionId` (unique session identifier)
  - `type` ("user" or "developer")
- Command is sent to RabbitMQ queue: `greenhouse_commands`

#### 2.1 **Scheduling (Persistent Backend Runtime)**
- The frontend Scheduling tab writes schedules to backend REST API (`/schedules`)
- Backend runtime executes enabled cron schedules and dispatches commands to `greenhouse_commands`
- Scheduler completion is defined as successful queue publish (dispatch), not final core response completion
- Schedule persistence is database-backed and survives frontend/backend restarts (enabled schedules are reloaded)

#### 3. **Backend Command Consumption**
- Backend RabbitMQ consumer listens on `greenhouse_commands` queue
- When message arrives:
  - Parses JSON command data
  - Routes to `CommandProcessor` for handling

#### 4. **Command Processing**
- `CommandProcessor` checks if command is stateful (affects session state)
- For non-stateful commands:
  - Checks Redis cache first (cache key based on command, parameters, session)
  - If cache hit: returns cached result immediately
  - If cache miss: proceeds to execution
- For stateful commands (actuator control commands):
  - Always executes (no caching)
- Commands are queued per-session to ensure sequential execution

#### 5. **Command Execution**
- `CommandExecutor` receives the command and routes it to Greenhouse Core via HTTP
  - **Greenhouse Commands** (routed to Greenhouse Core via HTTP):
    - `read_temperature_data`: Reads temperature sensor data from greenhouse core
      - Parameters: None
      - Returns: Temperature value, unit, timestamp, sensor ID, location
    - `read_humidity_data`: Reads humidity sensor data
      - Parameters: None
      - Returns: Humidity value, unit, timestamp, sensor ID, location
    - `read_light_data`: Reads light intensity sensor data
      - Parameters: None
      - Returns: Light value, unit, timestamp, sensor ID, location
    - `read_co2_data`: Reads CO2 level sensor data
      - Parameters: None
      - Returns: CO2 value, unit, timestamp, sensor ID, location
    - `read_soil_moisture_data`: Reads soil moisture sensor data
      - Parameters: None
      - Returns: Soil moisture value, unit, timestamp, sensor ID, location
    - `read_soil_ph_data`: Reads soil pH sensor data
      - Parameters: None
      - Returns: Soil pH value, unit, timestamp, sensor ID, location
    - `switch_water_canal`: Controls water canal actuator
      - Parameters: `action` ("on", "off", "toggle")
      - Returns: Device ID, status, previous status, timestamp
    - `switch_actuator`: Controls generic actuators
      - Parameters: `actuatorId` (string), `action` ("on", "off", "toggle")
      - Returns: Actuator ID, status, previous status, timestamp
    - `switch_fan`: Controls fan actuators
      - Parameters: `fanId` (string), `action` ("on", "off", "toggle")
      - Returns: Fan ID, status, speed, previous status, timestamp
    - `switch_heater`: Controls heater actuators
      - Parameters: `heaterId` (string), `action` ("on", "off", "toggle")
      - Returns: Heater ID, status, temperature, previous status, timestamp
    - `read_sensor`: Legacy command, routes to appropriate sensor command based on `sensor` parameter ("temperature", "humidity", "light", "co2", "soil_moisture", "soil_ph")
- **Execution Flow**:
  1. Commands are routed to `GreenhouseCoreClient.executeCommand()`
  2. Client sends HTTP POST to Greenhouse Core API (`/api/v1/commands/execute`)
  3. Core processes command and returns JSON response
  4. Client handles retries, timeouts, and error recovery
  5. Response is normalized to standard format
- Results include: `output` (JSON string), `data` (parsed object), `executionTime`, `error` (if any)

#### 6. **Session Management**
- `SessionManager` maintains session state:
  - Session creation time and last activity
  - Per-session command queue (Promise chain)
  - Session-specific logger
- Sessions auto-cleanup after 30 minutes of inactivity

#### 7. **Caching Strategy**
- Redis caches command results with TTL:
  - **Greenhouse Commands**:
    - `read_temperature_data`: No caching (TTL 0, live readings)
    - `read_humidity_data`: No caching (TTL 0, live readings)
    - `read_light_data`: No caching (TTL 0, live readings)
    - `read_co2_data`: No caching (TTL 0, live readings)
    - `read_soil_moisture_data`: No caching (TTL 0, live readings)
    - `read_soil_ph_data`: No caching (TTL 0, live readings)
    - `read_sensor`: No caching (TTL 0, live readings)
    - `switch_water_canal`: No caching (stateful)
    - `switch_actuator`: No caching (stateful)
    - `switch_fan`: No caching (stateful)
    - `switch_heater`: No caching (stateful)
- Cache key format: `cmd:{sessionId}:{command}:{currentPath}:{parameters}`
- Only successful results are cached (errors are not cached)

#### 8. **Response Delivery**
- Processed command result is sent to RabbitMQ queue: `command_responses`
- Response includes:
  - `commandId` (matches request)
  - `result` (execution output or error)
  - `cached` (boolean indicating if result was from cache)
  - `sessionId`
  - `timestamp`

#### 9. **Frontend Response Handling**
- `CommandWorker` polls `command_responses` queue (non-blocking)
- When response arrives:
  - Emits `response_received` signal
  - `GreenhouseDesktop` handles the signal
  - Updates appropriate output area (user output or developer terminal)
  - Shows cache indicator if result was cached

#### 10. **Logging & Monitoring**
- **System Logging**: Backend writes to `logs/backend_system.log`
- **Session Logging**: Each session has dedicated log file `logs/session_{number}.log`
- **Command Tracking**: All commands logged with ID, action, and details
- **Statistics**: Backend tracks:
  - Total commands processed
  - Cache hits/misses
  - Error count

---

## System Components

### Infrastructure Services

#### **Redis** (`greenhouse-redis`)
- **Purpose**: In-memory cache for command results
- **Port**: 6379 (internal only)
- **Data Persistence**: Volume-mounted data directory
- **Health Check**: Redis ping every 10 seconds

#### **RabbitMQ** (`greenhouse-rabbitmq`)
- **Purpose**: Message broker for asynchronous command/response communication
- **Ports**: 
  - 5672 (AMQP, internal)
  - 15672 (Management UI, commented out)
- **Queues**:
  - `greenhouse_commands`: Commands from frontend to backend
  - `command_responses`: Responses from backend to frontend
- **Durability**: Both queues are durable (survive broker restart)
- **QoS**: Backend prefetch set to 5 messages

#### **Backend** (`greenhouse-backend`)
- **Technology**: Node.js 18+ with Express.js
- **Port**: 3000 (exposed to host)
- **Dependencies**: Redis, RabbitMQ, PostgreSQL, Greenhouse Core Simulator
- **Health Check**: HTTP GET `/metadata/health/` every 30 seconds
- **Greenhouse Core Integration**: Uses `GreenhouseCoreClient` to communicate with greenhouse core via HTTP API
- **Core HTTP API**: Exposes `/status`, `/schema/*`, `/getters`, `/executors`, and `/api/executors/:name/:action` for desktop polling and executor actions

### Backend Persistent IoT Model

The backend uses Sequelize + PostgreSQL to persist a generic IoT entity model:

- `User` has many `Device`
- `Device` has many `Sensor`, `Actuator`, and `Schedule`
- `Sensor` has many `SensorReading` and `SensorAlertRule`
- `SensorAlertRule` has many `SensorAlert`

Extensibility details:
- UUID primary keys on all entities
- `JSONB metadata` fields for dynamic configuration and future growth
- Generic sensor categorization through free-form `Sensor.type`
- Time-series storage in `SensorReading` with `timestamp` + numeric `value`
- Automation via cron in `Schedule.cron_expression`
- Threshold monitoring through `SensorAlertRule` operators/thresholds

#### **Greenhouse Core Server** (External Service)
- **Technology**: External greenhouse core runtime (network service)
- **Base URL**: `http://192.168.27.16:8080`
- **Purpose**: Executes real greenhouse commands and exposes real state/executor APIs
- **Required APIs**:
  - `POST /api/v1/commands/execute`
    - Body: `{ command, parameters, commandId, sessionId }`
    - Returns: `{ success, result, error, commandId, timestamp }`
  - `GET /status`
  - `GET /schema/getters`
  - `GET /schema/executors`
  - `GET /getters`
  - `GET /getters/:key`
  - `GET /executors`
  - `POST /api/executors/:name/mode`
  - `POST /api/executors/:name/on`
  - `POST /api/executors/:name/off`
  - `POST /api/executors/:name/set`

#### **Frontend** (`greenhouse-frontend`)
- **Technology**: Python 3 with PyQt5
- **Display**: X11 forwarding for GUI (Linux)
- **Modes**: 
  - GUI mode (default)
  - Headless mode is removed (`--nogui` exits with warning)
- **Dependencies**: RabbitMQ, Backend API

---

## Backend Modules

### Core Application

#### **`index.js`**
- **Purpose**: Application entry point
- **Functionality**: 
  - Creates `App` instance
  - Handles startup errors
  - Exits on fatal errors

#### **`app.js`**
- **Purpose**: Main application class orchestrating all components
- **Key Responsibilities**:
  - Initializes Express server
  - Sets up middleware (JSON parsing, CORS)
  - Creates and wires all service components:
    - `RedisClientWrapper`
    - `RabbitMQClient`
    - `GreenhouseCoreClient`
    - `SessionManager`
    - `CommandExecutor`
    - `CommandProcessor`
  - Configures routes
  - Sets up RabbitMQ consumer for `greenhouse_commands` queue
  - Manages session cleanup timer (every 5 minutes)
  - Handles graceful startup and error recovery

### Sequelize Entity Layer

#### **`entity/index.js`**
- **Purpose**: Central model registry and association bootstrap
- **Responsibilities**:
  - Imports and initializes all Sequelize entities
  - Wires foreign key relations (`hasMany` / `belongsTo`)
  - Ensures associations are loaded before `sequelize.sync()`

#### **Entity Files**
- `entity/user.entity.js`
- `entity/device.entity.js`
- `entity/sensor.entity.js`
- `entity/sensor-reading.entity.js`
- `entity/actuator.entity.js`
- `entity/schedule.entity.js`
- `entity/sensor-alert-rule.entity.js`
- `entity/sensor-alert.entity.js`

### Clients

#### **`clients/redisClient.js`** (`RedisClientWrapper`)
- **Purpose**: Redis connection and caching operations
- **Functionality**:
  - Manages Redis client connection lifecycle
  - Provides methods: `get()`, `setEx()`, `keys()`, `del()`
  - Handles connection events (connect, ready, error, end)
  - Exposes `isOpen` property for connection status

#### **`clients/rabbitmqClient.js`** (`RabbitMQClient`)
- **Purpose**: RabbitMQ connection and message operations
- **Functionality**:
  - Establishes AMQP connection and channel
  - Queue declaration (`assertQueue`)
  - Message publishing (`sendToQueue`)
  - Message consumption (`consume`)
  - Queue inspection (`checkQueue`)
  - Automatic reconnection on connection loss
  - Prefetch configuration for load balancing

#### **`clients/greenhouseCoreClient.js`** (`GreenhouseCoreClient`)
- **Purpose**: Abstract interface for communicating with greenhouse core system
- **Functionality**:
  - HTTP client for greenhouse core API communication
  - Generic `executeCommand()` method for all greenhouse commands
  - Core state/executor methods (`/status`, `/schema/*`, `/getters`, `/executors`, `/api/executors/*`)
  - Health check endpoint monitoring
  - Retry logic with exponential backoff
  - Timeout handling
  - Connection status tracking
  - Configurable via environment variables (URL, timeout, retries)
- **Default Endpoint**: `http://192.168.27.16:8080` (overridable via `GREENHOUSE_CORE_URL`)

### Core Services

#### **`sessions/sessionManager.js`** (`SessionManager`)
- **Purpose**: Manages user sessions and their state
- **Key Features**:
  - Creates unique sessions with sequential numbering
  - Maintains session state:
    - Creation timestamp
    - Last activity timestamp
  - Per-session command queue (Promise chain) for sequential execution
  - Session-specific loggers
  - Automatic cleanup of inactive sessions (30-minute timeout)
  - Session listing and retrieval

#### **`processor/commandProcessor.js`** (`CommandProcessor`)
- **Purpose**: Orchestrates command processing workflow
- **Key Responsibilities**:
  - Receives command data from RabbitMQ
  - Determines if command is stateful (affects session state)
  - Implements caching strategy:
    - Generates cache keys based on command, parameters, session
    - Checks Redis cache for non-stateful commands
    - Stores results with TTL (time-to-live)
  - Queues commands per-session (ensures sequential execution)
  - Tracks statistics: total processed, cache hits, cache misses, errors
  - Returns structured response with result, cache status, and metadata

#### **`executor/commandExecutor.js`** (`CommandExecutor`)
- **Purpose**: Executes greenhouse commands by routing them to Greenhouse Core via HTTP
- **Greenhouse Commands** (routed to Greenhouse Core):
  - `read_temperature_data`: Reads temperature sensor data
  - `read_humidity_data`: Reads humidity sensor data
  - `read_light_data`: Reads light intensity sensor data
  - `read_co2_data`: Reads CO2 level sensor data
  - `read_soil_moisture_data`: Reads soil moisture sensor data
  - `read_soil_ph_data`: Reads soil pH sensor data
  - `switch_water_canal`: Controls water canal actuator
  - `switch_actuator`: Controls generic actuators
  - `switch_fan`: Controls fan actuators
  - `switch_heater`: Controls heater actuators
  - `read_sensor`: Legacy command, routes to appropriate sensor command based on `sensor` parameter
- **Features**:
  - Routes all commands to `GreenhouseCoreClient` (HTTP API)
  - Configurable timeout (default 15 seconds)
  - Normalizes responses from greenhouse core
  - Error handling with structured error objects
  - Legacy command mapping (read_sensor → specific sensor commands)

### Routing

#### **`router/routes.js`**
- **Purpose**: Defines REST API endpoints
- **Endpoints**:
  - `GET /`: API information and available endpoints
  - `GET /metadata/health/`: System health check with Redis/RabbitMQ status
  - `GET /sessions`: List all active sessions
  - `GET /sessions/:sessionId/log`: Get session log content
  - `DELETE /sessions/:sessionId`: Terminate a session
  - `GET /logs`: List all log files
  - `GET /logs/system`: Get system log content
  - `GET /cache/keys`: List all cache keys
  - `DELETE /cache/clear`: Clear all cached entries
  - `GET /metadata/stats/`: Get command processing statistics
  - `GET /metadata/queues/`: Get RabbitMQ queue status
  - `GET /status`: Greenhouse core status
  - `GET /schema/getters`: Getter schema
  - `GET /schema/executors`: Executor schema
  - `GET /getters`: Getter snapshots
  - `GET /getters/:key`: Single getter snapshot
  - `GET /executors`: Executor snapshots
  - `POST /api/executors/:name/:action`: Executor command route (`mode|on|off|set`)
  - Compatibility aliases: none (use root core routes)

### Logging

#### **`logger/systemLogger.js`** (`SystemLogger`)
- **Purpose**: System-wide logging
- **Features**:
  - Logs to `logs/backend_system.log`
  - Log levels: `info`, `error`, `warn`, `debug`
  - Timestamped entries
  - Console output for all levels except debug
  - Log file header with system information

#### **`logger/sessionLogger.js`** (`createSessionLogger`)
- **Purpose**: Per-session logging
- **Features**:
  - Creates dedicated log file per session: `logs/session_{number}.log`
  - Logs session lifecycle events
  - Tracks command execution with command IDs
  - Log levels: `info`, `error`, `debug`, `command`
  - Integrates with system logger for important events

### Configuration

#### **`config/index.js`**
- **Purpose**: Centralized configuration management
- **Configuration Sections**:
  - `redis`: Host and port (default: redis:6379)
  - `rabbitmq`: Host and port (default: rabbitmq:5672)
  - `server`: Port (default: 3000)
  - `exec`: Command execution timeout (default: 15000ms)
  - `greenhouseCore`: Greenhouse core API configuration
    - `url`: Base URL for greenhouse core API (default: http://localhost:3001)
    - `timeout`: Request timeout in milliseconds (default: 10000)
    - `retries`: Number of retry attempts (default: 2)
  - `logsDir`: Logs directory path
- **Environment Variables**: All values can be overridden via environment variables
  - `GREENHOUSE_CORE_URL`: Greenhouse core API URL
  - `GREENHOUSE_CORE_TIMEOUT`: Request timeout in milliseconds
  - `GREENHOUSE_CORE_RETRIES`: Number of retry attempts

---

## Frontend Modules

### Main Application

#### **`main.py`**
- **Purpose**: Application entry point
- **Functionality**:
  - Parses command-line arguments (`--nogui`, `--debug`)
  - Initializes logging
  - Enforces authentication gate before opening the main window
  - Runs in two modes:
    - **GUI Mode**: Launches PyQt5 desktop application
    - **Headless Mode**: CLI interface for command execution
  - Sets up X11 runtime directory for GUI
  - Configures application-wide font (Segoe UI)

#### **Desktop Auth UI**
- Sign-in / sign-up is presented in a blocking dialog before `GreenhouseDesktop` is shown.
- JWT is persisted in local desktop settings (`QSettings`) for session restore across restarts.
- On token validation failure, stored token is cleared and auth dialog is shown again.
- Main window includes logout action that clears token and prompts re-authentication.

### Core GUI Module

#### **`modules/greenhouse.py`** (`GreenhouseDesktop`)
- **Purpose**: Main PyQt5 desktop application window
- **Key Features**:
  - **Three-Tab Interface**:
    1. **Control Tab**: User-friendly greenhouse controls (sensors and actuators)
    2. **Scheduling Tab**: One-time delayed command scheduling (`Now`, presets, custom `hh:mm:ss`)
    3. **Server Tab**: Backend monitoring and management
  - **Session Management**:
    - Generates unique session ID on startup
    - Displays session information in header
  - **Command Handling**:
    - Sends commands via `CommandWorker`
    - Handles responses and updates UI
    - Displays cache indicators
    - Shows execution status
  - **Server Integration**:
    - HTTP requests to backend API
    - Health checks, statistics, session listing
    - Cache management
    - Queue monitoring
    - Log viewing
  - **Styling**: Modern UI with custom theme and stylesheets
  - **Auto-refresh**: Optional periodic server status updates

#### **`modules/schedules/schedules.runtime.js`** (`SchedulesRuntime`)
- **Purpose**: Backend cron runtime for persistent schedule dispatch
- **Key Features**:
  - Loads enabled schedules from database at startup
  - Registers cron jobs per schedule and keeps runtime map in memory
  - Dispatches command envelopes to `greenhouse_commands`
  - Updates schedule metadata with dispatch status and last command id

### Communication

#### **`modules/command_worker.py`** (`CommandWorker`)
- **Purpose**: RabbitMQ communication handler
- **Key Features**:
  - Connects to RabbitMQ broker
  - Sends commands to `greenhouse_commands` queue
  - Receives responses from `command_responses` queue
  - Non-blocking message polling using QTimer (every 100ms)
  - Automatic reconnection on connection loss
  - PyQt5 signals for:
    - `response_received`: Emitted when command response arrives
    - `connection_status`: Emitted when connection state changes
    - `error_occurred`: Emitted on errors
  - Thread-safe operations
  - Pending command tracking

#### **`modules/rabbitmq_client.py`** (`RabbitMQClient`)
- **Purpose**: Alternative RabbitMQ client (thread-safe implementation)
- **Features**:
  - QMutex-based thread safety
  - QTimer-based event processing
  - Connection status signals
  - Message sending and receiving
  - Automatic connection maintenance

### Styling

#### **`modules/styles.py`** (`GreenhouseTheme`, `StyleSheetGenerator`)
- **Purpose**: UI theming and styling
- **Components**:
  - `GreenhouseTheme`: Defines color palette, typography, spacing, border radius
  - `StyleSheetGenerator`: Generates Qt stylesheets for:
    - Buttons (primary, secondary, outline, default)
    - Text edits
    - Line edits
    - Group boxes
    - Tab widgets
    - Checkboxes
    - Labels (caption, body, subtitle)

### Edge/Fog Aggregation

#### **`modules/edge_fog_aggregator.py`** (`EdgeToFogAggregator`)
- **Purpose**: Edge-to-Fog data aggregation and anomaly detection
- **Key Features**:
  - Time-windowed aggregation (1min, 5min, 15min, 1h)
  - Quality-weighted averaging for sensor data
  - Real-time anomaly detection (out-of-range, variance, rate of change, trends)
  - Edge device registration and status tracking
  - Thread-safe data buffering and processing
  - Automatic cleanup of old data (2 hours for raw, 24 hours for aggregated)
- **Supported Sensor Types**:
  - Temperature, Humidity, Soil Moisture, Light Intensity, CO2 Level, Soil pH
- **Aggregation Windows**: 1 minute, 5 minutes, 15 minutes, 1 hour
- **Anomaly Detection**:
  - Out-of-range detection (immediate)
  - High variance detection
  - Rate of change detection
  - Sustained trend detection
- **Signals**: `new_aggregated_data`, `anomaly_detected`, `device_status_changed`
- **Data Structures**: `SensorReading`, `AggregatedData`, `Anomaly`

#### **`modules/redis_client.py`** (`RedisEdgeClient`)
- **Purpose**: Local Redis caching for edge node (cache-aside pattern)
- **Features**:
  - Cache-aside pattern implementation
  - TTL-based expiration
  - Namespace-based key organization
  - Graceful degradation (continues without Redis)
  - Thread-safe operations
- **Key Operations**:
  - `get(key)`: Retrieve cached value
  - `set(key, value, ttl)`: Store value with expiration
  - `delete(key)`: Remove cached value
  - `keys(pattern)`: List keys matching pattern
  - `clear_namespace(namespace)`: Clear all keys in namespace
- **Configuration**: Uses `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` from config

#### **`modules/config.py`** (`Config`)
- **Purpose**: Centralized configuration management for frontend
- **Features**:
  - Environment-based configuration loading (`.env.development`, `.env.production`)
  - Automatic environment detection (`ENVIRONMENT` or `NODE_ENV`)
  - Configuration class with defaults
  - RabbitMQ URL generation helper
- **Configuration Values**:
  - Backend API URL
  - RabbitMQ connection settings
  - Redis edge cache settings
  - Environment mode (production/development)

### Additional Modules

#### **`modules/new_greenhouse.py`** & **`modules/new_style.py`**
- **Purpose**: Alternative implementations or development versions
- **Note**: May contain experimental code

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- X11 server (for GUI mode on Linux)
- Git

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd GreenHouse_Application
   ```

2. **Start all services**:
   ```bash
   ./start.sh
   ```
   The `start.sh` script:
   - Sets up X11 display for GUI (Linux)
   - Starts all Docker services
   - Waits for backend to be ready
   - Performs health check
   - Displays service URLs
   
   Or manually:
   ```bash
   docker compose up -d
   ```

3. **Access services**:
   - Backend API: http://localhost:3000
   - RabbitMQ Management: http://localhost:15672 (guest/guest) - if enabled
   - Frontend: Runs in Docker container with GUI

4. **View logs**:
   ```bash
   docker compose logs -f
   ```

5. **Stop services**:
   ```bash
   docker compose down
   ```

### Development Setup

#### Backend Development

```bash
cd backend
npm install
npm run dev  # Uses nodemon for auto-reload
```

#### Frontend Development

```bash
cd frontend
pip install -r requirements.txt
python main.py  # GUI mode
python main.py --nogui  # Deprecated: exits with warning
python main.py --debug  # Debug logging
```

---

## Configuration

### Environment Variables

#### Backend
- `NODE_ENV`: Environment (production/development)
- `PORT`: Server port (default: 3000)
- `REDIS_HOST`: Redis hostname (default: redis)
- `REDIS_PORT`: Redis port (default: 6379)
- `RABBITMQ_HOST`: RabbitMQ hostname (default: rabbitmq)
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `EXEC_TIMEOUT_MS`: Command execution timeout (default: 15000)
- `GREENHOUSE_CORE_URL`: Greenhouse core API URL (default: http://localhost:3001)
- `GREENHOUSE_CORE_TIMEOUT`: Request timeout in milliseconds (default: 10000)
- `GREENHOUSE_CORE_RETRIES`: Number of retry attempts (default: 2)

#### Frontend
- `BACKEND_URL`: Backend API URL (default: http://localhost:3000)
- `RABBITMQ_HOST`: RabbitMQ hostname (default: rabbitmq)
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `RABBITMQ_USER`: RabbitMQ username (default: guest)
- `RABBITMQ_PASS`: RabbitMQ password (default: guest)
- `REDIS_HOST`: Redis hostname for edge caching (default: localhost)
- `REDIS_PORT`: Redis port for edge caching (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `ENVIRONMENT`: Environment mode - `production` or `development` (default: development)
- `DISPLAY`: Display endpoint for GUI mode (Linux example: `:0`, Windows X server example: `host.docker.internal:0.0`)
- `XVFB_SCREEN`: Optional virtual display geometry fallback (default: `1920x1080x24`)
- `ENABLE_VNC`: When `true`, starts VNC in Xvfb fallback mode for remote interaction (default: `false`)
- `VNC_PORT`: VNC port used when `ENABLE_VNC=true` (default: `5900`)

### Environment Configuration Files

The frontend supports the following environment configuration files:

- **`.env.development`**: Development environment
- **`.env.production`**: Production environment
- **`.env.example`**: Template for creating environment files

**Configuration Loading**:
- `ENVIRONMENT=production` → loads `.env.production`
- `ENVIRONMENT=development` → loads `.env.development`

See `frontend/README_ENV.md` for detailed configuration guide.

---

## API Endpoints

### Health & Information

- `GET /` - API information and endpoint list
- `GET /metadata/health/` - System health check with component status

### Authentication (JWT only)

- `POST /auth/register` - Register user account
- `POST /auth/login` - Login and receive access JWT
- Desktop-oriented mode uses JWT-only auth (no refresh token flow).
- Desktop frontend sends JWT via `Authorization: Bearer <jwt>` on backend API requests.
- Unauthorized/forbidden API responses trigger automatic local session reset and re-auth prompt.

### Persistent IoT CRUD

- `GET /users` - returns only authenticated user in `data[0]`
- `GET|PATCH|DELETE /users/:id` - allowed only for the authenticated user id
- `POST /users` is disabled (use `POST /auth/register`)
- `GET|POST /devices`, `GET|PATCH|DELETE /devices/:id`
- `GET|POST /sensors`, `GET|PATCH|DELETE /sensors/:id`
- `GET|POST /sensor-readings`, `GET|PATCH|DELETE /sensor-readings/:id`
- `GET|POST /actuators`, `GET|PATCH|DELETE /actuators/:id`
- `GET|POST /schedules`, `GET|PATCH|DELETE /schedules/:id`
- `GET|POST /sensor-alert-rules`, `GET|PATCH|DELETE /sensor-alert-rules/:id`
- `GET|POST /sensor-alerts`, `GET|PATCH|DELETE /sensor-alerts/:id`
- Protected CRUD endpoints require `Authorization: Bearer <jwt>`.
- Ownership is enforced by JWT identity only.

### Sessions

- `GET /sessions` - List all active sessions
- `GET /sessions/:sessionId/log` - Get session log content
- `DELETE /sessions/:sessionId` - Terminate a session

### Logs

- `GET /logs` - List all log files
- `GET /logs/system` - Get system log content

### Cache

- `GET /cache/keys` - List all cache keys (pattern: `cmd:*`)
- `DELETE /cache/clear` - Clear all cached entries
- `DELETE /cache/clear-errors` - Clear only error entries from cache (removes corrupted or error cache entries)

### Edge/Fog Data Aggregation

- `POST /fog/aggregated` - Store aggregated sensor data from edge nodes
  - Body: `{ sensorType, location, timeframe, data }`
  - Stores in Redis with namespace: `fog:agg:{sensorType}:{location}:{timeframe}`
- `GET /fog/aggregated` - Retrieve aggregated data with optional filtering
  - Query params: `sensorType`, `location`, `timeframe` (all optional)
  - Returns: `{ count, data: [...] }`
- `GET /fog/devices` - List all registered edge devices
  - Returns: `{ count, devices: [...] }`
- `POST /fog/anomalies` - Store detected anomaly from edge node
  - Body: `{ anomaly_id, sensor_type, location, anomaly_type, severity, message, timestamp, value, expected_range }`
  - Stores in Redis: `fog:anomaly:{anomaly_id}` and adds to recent list
- `GET /fog/anomalies` - Retrieve recent anomalies
  - Query params: `limit` (default: 10)
  - Returns: `{ count, anomalies: [...] }`

### Statistics & Monitoring

- `GET /metadata/stats/` - Get command processing statistics
- `GET /metadata/queues/` - Get RabbitMQ queue status

---

## Greenhouse Core Integration

### Core Client Design

The backend uses `GreenhouseCoreClient` as a dedicated integration layer for the real greenhouse core server. This design provides:

1. **Configurability**: Core endpoint remains configurable through environment variables
2. **Reliability**: Built-in retry logic, timeout handling, and connection status tracking
3. **Consistency**: Normalized response format for command execution results

### Command Routing

The `CommandExecutor` routes all commands to Greenhouse Core via HTTP:
- **Sensor Reading Commands**: `read_temperature_data`, `read_humidity_data`, `read_light_data`, `read_co2_data`, `read_soil_moisture_data`, `read_soil_ph_data` → Greenhouse Core via HTTP
- **Actuator Control Commands**: `switch_water_canal`, `switch_actuator`, `switch_fan`, `switch_heater` → Greenhouse Core via HTTP
- **Legacy Command**: `read_sensor` → Automatically routes to appropriate sensor command based on `sensor` parameter

### Current Core Configuration

The backend is configured to use the real core server at `http://192.168.27.16:8080` by default. `GREENHOUSE_CORE_URL` can still be overridden when needed.

The `GreenhouseCoreClient` includes:
- Automatic retry logic with exponential backoff (configurable retries)
- Timeout handling (configurable timeout)
- Connection status tracking
- Normalized response format

---

## Edge-to-Fog Data Aggregation

### Overview

The system implements a three-tier Edge-to-Fog data aggregation architecture:

- **Edge Layer**: Physical sensor devices collecting raw environmental data
- **Fog Layer**: Desktop application (PyQt5) that aggregates and processes data locally
- **Backend Layer**: Express.js server that coordinates multiple fog nodes and provides centralized storage

### Key Benefits

- **Offline-First Operation**: Local caching allows the system to function without backend connectivity
- **Reduced Network Traffic**: Aggregation at the fog layer reduces data volume sent to backend (~90% reduction)
- **Real-Time Processing**: Time-windowed aggregation provides near real-time insights
- **Anomaly Detection**: Automatic detection of unusual patterns in sensor data
- **Scalability**: Multiple edge devices can be managed by a single fog node
- **Quality-Aware**: Quality scoring ensures reliable data aggregation

### Architecture Flow

```
Edge Sensors → EdgeToFogAggregator → RedisEdgeClient (Local Cache) → Backend API → Central Redis
     ↓                ↓                        ↓                          ↓
Raw Readings    Aggregated Data         Cache (TTL)              Storage & Coordination
```

### Aggregation Windows

- **1min**: 60 seconds - Real-time monitoring
- **5min**: 300 seconds - Short-term trends
- **15min**: 900 seconds - Medium-term analysis
- **1h**: 3600 seconds - Long-term patterns

### Supported Sensor Types

- Temperature (expected range: 15.0-35.0°C)
- Humidity (expected range: 30.0-80.0%)
- Soil Moisture (expected range: 20.0-80.0%)
- Light Intensity (expected range: 0.0-1000.0 Lux)
- CO2 Level (expected range: 300.0-1500.0 PPM)
- Soil pH (expected range: 5.5-7.5)

### Anomaly Detection

The system implements multiple anomaly detection algorithms:

1. **Out-of-Range Detection**: Immediate detection when sensor reading exceeds expected range
2. **High Variance Detection**: Detects when standard deviation exceeds 30% of average value
3. **Rate of Change Detection**: Detects rapid changes (>5 units per minute)
4. **Trend Detection**: Identifies sustained increasing or decreasing trends

**Anomaly Severity Levels**:
- `critical`: Immediate attention required
- `warning`: Potential issue
- `info`: Informational trend

### Caching Strategy

**Local Edge Cache** (RedisEdgeClient):
- Cache-aside pattern
- TTL: 10 minutes for aggregated data
- Key format: `agg:{sensor_type}:{location}:{timeframe}`
- Graceful degradation if Redis unavailable

**Backend Central Cache**:
- Key format: `fog:agg:{sensorType}:{location}:{timeframe}`
- TTL: 5-60 minutes depending on timeframe
- Anomalies: 24 hours TTL
- Devices: Persistent storage

### Integration

The Edge/Fog aggregation is integrated into the main desktop application:

- **Initialization**: `EdgeToFogAggregator` and `RedisEdgeClient` are initialized in `GreenhouseDesktop`
- **Sensor Data Input**: Currently simulated (every 5 seconds), can be replaced with RabbitMQ consumer
- **UI Display**: Aggregated data and anomalies displayed in Server tab
- **Backend Sync**: Async HTTP POST to backend endpoints (non-blocking)

### Usage Example

```python
# Register edge device
aggregator.register_edge_device(
    device_id="device_001",
    device_type="sensor_node",
    location="Zone_A",
    capabilities=[SensorType.TEMPERATURE, SensorType.HUMIDITY]
)

# Add sensor reading
reading = SensorReading(
    device_id="device_001",
    sensor_type=SensorType.TEMPERATURE,
    value=22.5,
    timestamp=datetime.now(),
    location="Zone_A",
    quality=0.95
)
aggregator.add_sensor_reading(reading)

# Get aggregated metrics
metrics = aggregator.get_aggregated_metrics(
    sensor_type=SensorType.TEMPERATURE,
    location="Zone_A"
)
```

### Documentation

For detailed documentation on Edge-to-Fog aggregation, see:
- `docs/EDGE_TO_EDGE_FOG_AGGREGATION.md` - Complete technical documentation
- `docs/EDGE_FOG_INTEGRATION_SUMMARY.md` - Integration summary

---

## Dependencies

### Backend Dependencies

**Production**:
- `express`: ^4.18.2 - Web framework
- `amqplib`: ^0.10.3 - RabbitMQ client
- `redis`: ^4.6.7 - Redis client
- `dotenv`: ^16.0.3 - Environment variable management

**Development**:
- `nodemon`: ^3.1.10 - Auto-reload for development
- `cross-env`: ^7.0.3 - Cross-platform environment variables
- `eslint`: ^8.46.0 - Code linting
- `prettier`: ^3.6.2 - Code formatting

### Frontend Dependencies

- `PyQt5`: 5.15.9 - GUI framework
- `pika`: 1.3.2 - RabbitMQ client
- `requests`: 2.31.0 - HTTP client
- `python-dotenv`: 1.0.0 - Environment variable management
- `redis`: 5.0.1 - Redis client for edge caching

### Infrastructure

- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration
- **Redis**: 7-alpine - Caching and data storage
- **RabbitMQ**: 3-management-alpine - Message broker

---

## Architecture Benefits

1. **Scalability**: RabbitMQ allows multiple frontend instances and backend workers
2. **Reliability**: Durable queues ensure message persistence
3. **Performance**: Redis caching reduces redundant command execution
4. **Isolation**: Per-session state prevents command interference
5. **Observability**: Comprehensive logging at system and session levels
6. **Flexibility**: Support for both GUI and headless operation modes
7. **Modularity**: Abstract greenhouse core interface allows easy integration with different core implementations
8. **Resilience**: Automatic retry and timeout handling for greenhouse core communication
9. **Edge Computing**: Edge-to-Fog aggregation reduces network traffic and enables offline operation
10. **Real-Time Insights**: Time-windowed aggregation provides near real-time data analysis
11. **Anomaly Detection**: Automatic detection of unusual patterns in sensor data
12. **Quality-Aware Processing**: Quality-weighted aggregation ensures reliable data processing

---

## License

MIT

---

## Author

Greenhouse Automation Team


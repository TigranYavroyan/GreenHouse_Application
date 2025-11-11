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
┌────────┐ ┌────────┐
│ Redis  │ │ Shell  │
│ Cache  │ │ Exec   │
└────────┘ └────────┘
```

### Step-by-Step Architecture Flow

#### 1. **Frontend Initialization**
- PyQt5 desktop application starts with a unique session ID
- `CommandWorker` establishes connection to RabbitMQ
- GUI displays connection status and session information

#### 2. **Command Submission**
- User interacts with GUI (Control tab, Terminal tab, or Server tab)
- Frontend creates command payload with:
  - `commandId` (UUID)
  - `command` (e.g., "read_sensor", "execute_raw", "list_directory")
  - `parameters` (command-specific parameters)
  - `sessionId` (unique session identifier)
  - `type` ("user" or "developer")
- Command is sent to RabbitMQ queue: `greenhouse_commands`

#### 3. **Backend Command Consumption**
- Backend RabbitMQ consumer listens on `greenhouse_commands` queue
- When message arrives:
  - Parses JSON command data
  - Routes to `CommandProcessor` for handling

#### 4. **Command Processing**
- `CommandProcessor` checks if command is stateful (affects session state)
- For non-stateful commands:
  - Checks Redis cache first (cache key based on command, parameters, path, session)
  - If cache hit: returns cached result immediately
  - If cache miss: proceeds to execution
- For stateful commands (navigate, change_directory, execute_raw):
  - Always executes (no caching)
- Commands are queued per-session to ensure sequential execution

#### 5. **Command Execution**
- `CommandExecutor` receives the command
- Executes appropriate shell command or system operation:
  - `list_directory`: `ls -la` in current session path
  - `navigate`/`change_directory`: `cd` command with path validation
  - `execute_raw`: Executes arbitrary shell command
  - `read_sensor`: Simulates sensor data (temperature, humidity, light)
  - `system_status`: `ps aux` for system monitoring
  - `get_current_path`: Returns current working directory
- Results include: `output`, `stderr`, `executionTime`, `error` (if any)

#### 6. **Session Management**
- `SessionManager` maintains session state:
  - Current working directory (`currentPath`)
  - Previous path (`previousPath`)
  - Session creation time and last activity
  - Per-session command queue (Promise chain)
  - Session-specific logger
- Sessions auto-cleanup after 30 minutes of inactivity

#### 7. **Caching Strategy**
- Redis caches command results with TTL:
  - `list_directory`: 15 seconds
  - `system_status`: 8 seconds
  - `read_sensor`: 5 seconds
  - `get_current_path`: 15 seconds
  - `execute_raw`: No caching (always fresh)
- Cache key format: `cmd:{sessionId}:{command}:{currentPath}:{parameters}`

#### 8. **Response Delivery**
- Processed command result is sent to RabbitMQ queue: `command_responses`
- Response includes:
  - `commandId` (matches request)
  - `result` (execution output or error)
  - `cached` (boolean indicating if result was from cache)
  - `sessionId`
  - `currentPath` (updated if navigation occurred)
  - `timestamp`

#### 9. **Frontend Response Handling**
- `CommandWorker` polls `command_responses` queue (non-blocking)
- When response arrives:
  - Emits `response_received` signal
  - `GreenhouseDesktop` handles the signal
  - Updates appropriate output area (user output or developer terminal)
  - Updates current path display if changed
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
- **Dependencies**: Redis, RabbitMQ
- **Health Check**: HTTP GET `/health` every 30 seconds

#### **Frontend** (`greenhouse-frontend`)
- **Technology**: Python 3 with PyQt5
- **Display**: X11 forwarding for GUI (Linux)
- **Modes**: 
  - GUI mode (default)
  - Headless mode (`--nogui` flag)
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
    - `SessionManager`
    - `CommandExecutor`
    - `CommandProcessor`
  - Configures routes
  - Sets up RabbitMQ consumer for `greenhouse_commands` queue
  - Manages session cleanup timer (every 5 minutes)
  - Handles graceful startup and error recovery

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

### Core Services

#### **`sessions/sessionManager.js`** (`SessionManager`)
- **Purpose**: Manages user sessions and their state
- **Key Features**:
  - Creates unique sessions with sequential numbering
  - Maintains session state:
    - Current working directory
    - Previous directory
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
    - Generates cache keys based on command, parameters, path, session
    - Checks Redis cache for non-stateful commands
    - Stores results with TTL (time-to-live)
  - Queues commands per-session (ensures sequential execution)
  - Updates session state (current path) after navigation commands
  - Tracks statistics: total processed, cache hits, cache misses, errors
  - Returns structured response with result, cache status, and metadata

#### **`executor/commandExecutor.js`** (`CommandExecutor`)
- **Purpose**: Executes shell commands and system operations
- **Supported Commands**:
  - `list_directory`: Lists files in current directory (`ls -la`)
  - `navigate`: Changes directory and returns new path (`cd` + `pwd`)
  - `change_directory`: Same as navigate
  - `get_current_path`: Returns current working directory
  - `system_status`: Shows running processes (`ps aux`)
  - `execute_raw`: Executes arbitrary shell command
  - `read_sensor`: Simulates sensor data (temperature, humidity, light)
- **Features**:
  - Executes commands in session's working directory
  - Configurable timeout (default 15 seconds)
  - Captures stdout, stderr, and execution time
  - Error handling with structured error objects
  - Max buffer size: 10MB

### Routing

#### **`router/routes.js`**
- **Purpose**: Defines REST API endpoints
- **Endpoints**:
  - `GET /`: API information and available endpoints
  - `GET /health`: System health check with Redis/RabbitMQ status
  - `GET /sessions`: List all active sessions
  - `GET /sessions/:sessionId/log`: Get session log content
  - `DELETE /sessions/:sessionId`: Terminate a session
  - `GET /logs`: List all log files
  - `GET /logs/system`: Get system log content
  - `GET /cache/keys`: List all cache keys
  - `DELETE /cache/clear`: Clear all cached entries
  - `GET /stats`: Get command processing statistics
  - `GET /queues`: Get RabbitMQ queue status

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
  - `logsDir`: Logs directory path
- **Environment Variables**: All values can be overridden via environment variables

---

## Frontend Modules

### Main Application

#### **`main.py`**
- **Purpose**: Application entry point
- **Functionality**:
  - Parses command-line arguments (`--nogui`, `--debug`)
  - Initializes logging
  - Runs in two modes:
    - **GUI Mode**: Launches PyQt5 desktop application
    - **Headless Mode**: CLI interface for command execution
  - Sets up X11 runtime directory for GUI
  - Configures application-wide font (Segoe UI)

### Core GUI Module

#### **`modules/greenhouse.py`** (`GreenhouseDesktop`)
- **Purpose**: Main PyQt5 desktop application window
- **Key Features**:
  - **Three-Tab Interface**:
    1. **Control Tab**: User-friendly greenhouse controls (sensors, system status, file operations)
    2. **Terminal Tab**: Developer terminal for raw shell commands
    3. **Server Tab**: Backend monitoring and management
  - **Session Management**:
    - Generates unique session ID on startup
    - Displays session information in header
    - Tracks current working directory
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

### Additional Modules

#### **`modules/edge_fog_aggregator.py`**
- **Purpose**: Edge/Fog computing aggregation (if implemented)
- **Note**: File exists but functionality may vary

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
python main.py --nogui  # Headless mode
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

#### Frontend
- `BACKEND_URL`: Backend API URL (default: http://localhost:3000)
- `RABBITMQ_HOST`: RabbitMQ hostname (default: rabbitmq)
- `RABBITMQ_PORT`: RabbitMQ port (default: 5672)
- `RABBITMQ_USER`: RabbitMQ username (default: guest)
- `RABBITMQ_PASS`: RabbitMQ password (default: guest)
- `DISPLAY`: X11 display (for GUI)
- `XAUTHORITY`: X11 authority file (for GUI)

---

## API Endpoints

### Health & Information

- `GET /` - API information and endpoint list
- `GET /health` - System health check with component status

### Sessions

- `GET /sessions` - List all active sessions
- `GET /sessions/:sessionId/log` - Get session log content
- `DELETE /sessions/:sessionId` - Terminate a session

### Logs

- `GET /logs` - List all log files
- `GET /logs/system` - Get system log content

### Cache

- `GET /cache/keys` - List all cache keys
- `DELETE /cache/clear` - Clear all cached entries

### Statistics & Monitoring

- `GET /stats` - Get command processing statistics
- `GET /queues` - Get RabbitMQ queue status

---

## Architecture Benefits

1. **Scalability**: RabbitMQ allows multiple frontend instances and backend workers
2. **Reliability**: Durable queues ensure message persistence
3. **Performance**: Redis caching reduces redundant command execution
4. **Isolation**: Per-session state prevents command interference
5. **Observability**: Comprehensive logging at system and session levels
6. **Flexibility**: Support for both GUI and headless operation modes

---

## License

MIT

---

## Author

Greenhouse Automation Team


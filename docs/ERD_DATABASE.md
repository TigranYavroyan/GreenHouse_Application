# Database ERD and Stored Data

This project uses two data stores:

- **PostgreSQL** for relational, persistent domain data.
- **Redis** for cache and short-lived operational data.

Last reviewed against entity definitions in `backend/entity/*.js`: 2026-04-28.

## What is saved in PostgreSQL

The backend Sequelize entities persist these tables:

- `users`
- `devices`
- `sensors`
- `sensor_readings`
- `actuators`
- `schedules`
- `sensor_alert_rules`
- `sensor_alerts`
- `user_logs`

## PostgreSQL ERD (Mermaid)

```mermaid
erDiagram
    USERS {
        UUID id PK
        STRING username UK
        STRING email UK
        STRING password
        BOOLEAN verified
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    DEVICES {
        UUID id PK
        UUID user_id FK
        STRING name
        STRING type
        STRING status
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    SENSORS {
        UUID id PK
        UUID device_id FK
        STRING name
        STRING type
        STRING unit
        BOOLEAN is_active
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    SENSOR_READINGS {
        UUID id PK
        UUID sensor_id FK
        DOUBLE value
        DATETIME timestamp
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    ACTUATORS {
        UUID id PK
        UUID device_id FK
        STRING name
        STRING type
        STRING status
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    SCHEDULES {
        UUID id PK
        UUID device_id FK
        STRING name
        STRING cron_expression
        STRING action
        BOOLEAN enabled
        JSONB payload
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    SENSOR_ALERT_RULES {
        UUID id PK
        UUID sensor_id FK
        STRING name
        STRING operator
        DOUBLE threshold_value
        DOUBLE threshold_min
        DOUBLE threshold_max
        STRING severity
        BOOLEAN enabled
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    SENSOR_ALERTS {
        UUID id PK
        UUID sensor_alert_rule_id FK
        DOUBLE value
        TEXT message
        STRING status
        DATETIME triggered_at
        DATETIME acknowledged_at
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    USER_LOGS {
        UUID id PK
        UUID user_id FK
        STRING category
        STRING title
        JSONB payload
        JSONB metadata
        DATETIME created_at
        DATETIME updated_at
    }

    USERS ||--o{ DEVICES : owns
    USERS ||--o{ USER_LOGS : writes
    DEVICES ||--o{ SENSORS : has
    DEVICES ||--o{ ACTUATORS : has
    DEVICES ||--o{ SCHEDULES : has
    SENSORS ||--o{ SENSOR_READINGS : records
    SENSORS ||--o{ SENSOR_ALERT_RULES : defines
    SENSOR_ALERT_RULES ||--o{ SENSOR_ALERTS : triggers
```

## What is saved in Redis

Redis is used as non-relational cache/storage (not part of ERD):

- Command cache: `cmd:{sessionId}:{command}:{currentPath}:{parameters}`
- Fog aggregates: `fog:agg:{sensorType}:{location}:{timeframe}`
- Fog anomalies: `fog:anomaly:{anomaly_id}`
- Recent anomalies list: `fog:anomalies:recent`
- Fog devices: `fog:device:{device_id}`

Most Redis keys are TTL-based and can expire automatically.

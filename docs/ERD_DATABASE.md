# Database ERD and Stored Data

This project uses two data stores:

- **PostgreSQL** for relational, persistent domain data.
- **Redis** for cache and short-lived operational data.

Last reviewed against entity definitions and associations in `backend/entity/*.js` and `backend/entity/index.js`: 2026-05-02.

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

Entity boxes use **PostgreSQL table names** (`users`, `devices`, …). Relationship lines use Crow’s Foot notation: `||` = exactly one on the parent side, `o{` = zero or many on the child side.

**Referential actions (Sequelize `onDelete: 'CASCADE'` where set):** deleting a `users` row cascades to `devices` and `user_logs`; deleting a `devices` row cascades to `sensors`, `actuators`, and `schedules`; deleting a `sensors` row cascades to `sensor_readings` and `sensor_alert_rules`; deleting a `sensor_alert_rules` row cascades to `sensor_alerts`. Parent `belongsTo` sides do not add extra CASCADE beyond these `hasMany` definitions.

```mermaid
erDiagram
    users {
        uuid id PK
        varchar username UK
        varchar email UK
        varchar password
        boolean verified
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    devices {
        uuid id PK
        uuid user_id FK
        varchar name
        varchar type
        varchar status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    sensors {
        uuid id PK
        uuid device_id FK
        varchar name
        varchar type
        varchar unit
        boolean is_active
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    sensor_readings {
        uuid id PK
        uuid sensor_id FK
        float8 value
        timestamptz timestamp
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    actuators {
        uuid id PK
        uuid device_id FK
        varchar name
        varchar type
        varchar status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    schedules {
        uuid id PK
        uuid device_id FK
        varchar name
        varchar cron_expression
        varchar action
        boolean enabled
        jsonb payload
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    sensor_alert_rules {
        uuid id PK
        uuid sensor_id FK
        varchar name
        varchar operator
        float8 threshold_value
        float8 threshold_min
        float8 threshold_max
        varchar severity
        boolean enabled
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    sensor_alerts {
        uuid id PK
        uuid sensor_alert_rule_id FK
        float8 value
        text message
        varchar status
        timestamp triggered_at
        timestamp acknowledged_at
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    user_logs {
        uuid id PK
        uuid user_id FK
        varchar category
        varchar title
        jsonb payload
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    users ||--o{ devices : "user_id"
    users ||--o{ user_logs : "user_id"
    devices ||--o{ sensors : "device_id"
    devices ||--o{ actuators : "device_id"
    devices ||--o{ schedules : "device_id"
    sensors ||--o{ sensor_readings : "sensor_id"
    sensors ||--o{ sensor_alert_rules : "sensor_id"
    sensor_alert_rules ||--o{ sensor_alerts : "sensor_alert_rule_id"
```

## What is saved in Redis

Redis is used as non-relational cache/storage (not part of ERD):

- Command cache: `cmd:{sessionId}:{command}:{currentPath}:{parameters}`
- Fog aggregates: `fog:agg:{sensorType}:{location}:{timeframe}`
- Fog anomalies: `fog:anomaly:{anomaly_id}`
- Recent anomalies list: `fog:anomalies:recent`
- Fog devices: `fog:device:{device_id}`

Most Redis keys are TTL-based and can expire automatically.

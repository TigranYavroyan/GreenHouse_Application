import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const SensorAlert = sequelize.define('SensorAlert', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    value: {
        type: DataTypes.DOUBLE,
        allowNull: false,
    },
    message: {
        type: DataTypes.TEXT,
        allowNull: false,
    },
    status: {
        type: DataTypes.STRING(20),
        allowNull: false,
        defaultValue: 'open',
    },
    triggeredAt: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
        field: 'triggered_at',
    },
    acknowledgedAt: {
        type: DataTypes.DATE,
        allowNull: true,
        field: 'acknowledged_at',
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'sensor_alerts',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['sensor_alert_rule_id', 'triggered_at'],
        },
        {
            fields: ['status'],
        },
    ],
});

export default SensorAlert;

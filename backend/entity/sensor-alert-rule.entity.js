import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const SensorAlertRule = sequelize.define('SensorAlertRule', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    name: {
        type: DataTypes.STRING(120),
        allowNull: false,
    },
    operator: {
        type: DataTypes.STRING(30),
        allowNull: false,
        defaultValue: 'gt',
    },
    thresholdValue: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'threshold_value',
    },
    thresholdMin: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'threshold_min',
    },
    thresholdMax: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'threshold_max',
    },
    severity: {
        type: DataTypes.STRING(20),
        allowNull: false,
        defaultValue: 'warning',
    },
    enabled: {
        type: DataTypes.BOOLEAN,
        allowNull: false,
        defaultValue: true,
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'sensor_alert_rules',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['sensor_id'],
        },
        {
            fields: ['enabled'],
        },
    ],
});

export default SensorAlertRule;

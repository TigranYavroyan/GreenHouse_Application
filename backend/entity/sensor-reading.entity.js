import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const SensorReading = sequelize.define('SensorReading', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    value: {
        type: DataTypes.DOUBLE,
        allowNull: false,
    },
    timestamp: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'sensor_readings',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['sensor_id', 'timestamp'],
        },
        {
            fields: ['timestamp'],
        },
    ],
});

export default SensorReading;

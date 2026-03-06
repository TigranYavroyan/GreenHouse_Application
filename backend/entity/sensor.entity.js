import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const Sensor = sequelize.define('Sensor', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    name: {
        type: DataTypes.STRING(120),
        allowNull: false,
    },
    type: {
        type: DataTypes.STRING(100),
        allowNull: false,
    },
    unit: {
        type: DataTypes.STRING(30),
        allowNull: true,
    },
    isActive: {
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
    tableName: 'sensors',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['device_id'],
        },
        {
            fields: ['type'],
        },
    ],
});

export default Sensor;

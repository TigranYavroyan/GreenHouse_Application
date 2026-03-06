import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const Actuator = sequelize.define('Actuator', {
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
    status: {
        type: DataTypes.STRING(50),
        allowNull: false,
        defaultValue: 'off',
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'actuators',
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

export default Actuator;

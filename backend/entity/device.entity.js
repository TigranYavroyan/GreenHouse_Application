import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const Device = sequelize.define('Device', {
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
        defaultValue: 'controller',
    },
    status: {
        type: DataTypes.STRING(50),
        allowNull: false,
        defaultValue: 'offline',
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'devices',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['user_id'],
        },
    ],
});

export default Device;

import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const UserLog = sequelize.define('UserLog', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    category: {
        type: DataTypes.STRING(50),
        allowNull: false,
        defaultValue: 'control',
    },
    title: {
        type: DataTypes.STRING(160),
        allowNull: false,
    },
    payload: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
    metadata: {
        type: DataTypes.JSONB,
        allowNull: false,
        defaultValue: {},
    },
}, {
    tableName: 'user_logs',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['user_id', 'created_at'],
        },
        {
            fields: ['category'],
        },
    ],
});

export default UserLog;

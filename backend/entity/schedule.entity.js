import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const Schedule = sequelize.define('Schedule', {
    id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
    },
    name: {
        type: DataTypes.STRING(120),
        allowNull: false,
    },
    cronExpression: {
        type: DataTypes.STRING(100),
        allowNull: false,
        field: 'cron_expression',
    },
    action: {
        type: DataTypes.STRING(120),
        allowNull: false,
    },
    enabled: {
        type: DataTypes.BOOLEAN,
        allowNull: false,
        defaultValue: true,
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
    tableName: 'schedules',
    underscored: true,
    timestamps: true,
    indexes: [
        {
            fields: ['device_id'],
        },
        {
            fields: ['enabled'],
        },
    ],
});

export default Schedule;

import User from './user.entity.js';
import { DataTypes } from 'sequelize';
import ConfigPostgres from '../config/configPostgres.js';

const sequelize = await ConfigPostgres.getInstance();

const SensorsData = sequelize.define('SensorsData', {
    temperature: {
        type: DataTypes.FLOAT,
        allowNull: false,
    },
    humidity: {
        type: DataTypes.FLOAT,
        allowNull: false,
    },
    light: {
        type: DataTypes.FLOAT,
        allowNull: false,
    }
});

User.hasOne(SensorsData, { foreignKey: 'userId', onDelete: 'CASCADE' });
SensorsData.belongsTo(User, { foreignKey: 'userId' });

export default SensorsData;

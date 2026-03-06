import User from './user.entity.js';
import Device from './device.entity.js';
import Sensor from './sensor.entity.js';
import SensorReading from './sensor-reading.entity.js';
import Actuator from './actuator.entity.js';
import Schedule from './schedule.entity.js';
import SensorAlertRule from './sensor-alert-rule.entity.js';
import SensorAlert from './sensor-alert.entity.js';

User.hasMany(Device, {
    foreignKey: {
        name: 'userId',
        allowNull: false,
        field: 'user_id',
    },
    as: 'devices',
    onDelete: 'CASCADE',
});
Device.belongsTo(User, {
    foreignKey: {
        name: 'userId',
        allowNull: false,
        field: 'user_id',
    },
    as: 'user',
});

Device.hasMany(Sensor, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'sensors',
    onDelete: 'CASCADE',
});
Sensor.belongsTo(Device, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'device',
});

Device.hasMany(Actuator, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'actuators',
    onDelete: 'CASCADE',
});
Actuator.belongsTo(Device, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'device',
});

Device.hasMany(Schedule, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'schedules',
    onDelete: 'CASCADE',
});
Schedule.belongsTo(Device, {
    foreignKey: {
        name: 'deviceId',
        allowNull: false,
        field: 'device_id',
    },
    as: 'device',
});

Sensor.hasMany(SensorReading, {
    foreignKey: {
        name: 'sensorId',
        allowNull: false,
        field: 'sensor_id',
    },
    as: 'readings',
    onDelete: 'CASCADE',
});
SensorReading.belongsTo(Sensor, {
    foreignKey: {
        name: 'sensorId',
        allowNull: false,
        field: 'sensor_id',
    },
    as: 'sensor',
});

Sensor.hasMany(SensorAlertRule, {
    foreignKey: {
        name: 'sensorId',
        allowNull: false,
        field: 'sensor_id',
    },
    as: 'alertRules',
    onDelete: 'CASCADE',
});
SensorAlertRule.belongsTo(Sensor, {
    foreignKey: {
        name: 'sensorId',
        allowNull: false,
        field: 'sensor_id',
    },
    as: 'sensor',
});

SensorAlertRule.hasMany(SensorAlert, {
    foreignKey: {
        name: 'sensorAlertRuleId',
        allowNull: false,
        field: 'sensor_alert_rule_id',
    },
    as: 'alerts',
    onDelete: 'CASCADE',
});
SensorAlert.belongsTo(SensorAlertRule, {
    foreignKey: {
        name: 'sensorAlertRuleId',
        allowNull: false,
        field: 'sensor_alert_rule_id',
    },
    as: 'alertRule',
});

export {
    User,
    Device,
    Sensor,
    SensorReading,
    Actuator,
    Schedule,
    SensorAlertRule,
    SensorAlert,
};


/**
 * Pure rules for command result TTL, statefulness, and deterministic Redis keys.
 */

const COMMAND_TTL_SEC = {
  read_temperature_data: 0,
  read_humidity_data: 0,
  read_light_data: 0,
  read_co2_data: 0,
  read_soil_moisture_data: 0,
  read_soil_ph_data: 0,
  read_sensor: 0,
  switch_water_canal: 0,
  switch_actuator: 0,
  switch_fan: 0,
  switch_heater: 0,
};

const STATEFUL_COMMANDS = new Set([
  'switch_water_canal',
  'switch_actuator',
  'switch_fan',
  'switch_heater',
]);

const DEFAULT_TTL_SEC = 8;

export function getTTLForCommand(command, _parameters = {}) {
  if (Object.prototype.hasOwnProperty.call(COMMAND_TTL_SEC, command)) {
    return COMMAND_TTL_SEC[command];
  }
  return DEFAULT_TTL_SEC;
}

export function isStateful(command) {
  return STATEFUL_COMMANDS.has(command);
}

export function generateCacheKey(command, parameters, currentPath, sessionId) {
  const sortedParams = parameters
    ? Object.keys(parameters)
        .sort()
        .reduce((obj, key) => {
          obj[key] = parameters[key];
          return obj;
        }, {})
    : {};
  return `cmd:${sessionId}:${command}:${currentPath}:${JSON.stringify(sortedParams)}`;
}

/** Whether this command may use Redis result cache + idempotency keys. */
export function resolveCachePlan(command, parameters = {}) {
  const ttl = getTTLForCommand(command, parameters);
  return {
    ttl,
    shouldCache: !isStateful(command) && ttl > 0,
  };
}

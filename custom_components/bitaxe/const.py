"""Constants for the Bitaxe integration."""

DOMAIN = "bitaxe"

# Config flow
CONF_HOST = "host"

# Default values
DEFAULT_SCAN_INTERVAL = 30

# API endpoints (per AxeOS documentation at https://osmu.wiki/bitaxe/api/)
API_SYSTEM_INFO = "/api/system/info"  # Returns all mining data (power, hashrate, temp, fan, etc.)


# Sensor keys
SENSOR_POWER = "power"
SENSOR_VOLTAGE = "voltage"
SENSOR_CURRENT = "current"
SENSOR_TEMP = "temp"
SENSOR_VR_TEMP = "vrTemp"
SENSOR_HASHRATE = "hashRate"
SENSOR_BEST_DIFF = "bestDiff"
SENSOR_BEST_SESSION_DIFF = "bestSessionDiff"
SENSOR_FREQUENCY = "frequency"
SENSOR_SHARES_ACCEPTED = "sharesAccepted"
SENSOR_SHARES_REJECTED = "sharesRejected"
SENSOR_UPTIME = "uptimeSeconds"
SENSOR_FAN_SPEED = "fanspeed"
SENSOR_FAN_RPM = "fanrpm"

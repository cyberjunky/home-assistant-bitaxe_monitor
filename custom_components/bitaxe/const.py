"""Constants for the Bitaxe integration."""

from datetime import timedelta

DOMAIN = "bitaxe"

SCAN_INTERVAL = timedelta(seconds=30)

# Snapshot of the last known device data, used to set up the entities while
# the miner is switched off
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.snapshot"

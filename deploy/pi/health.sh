#!/usr/bin/env bash
# Publish the Pi's health (#29): CPU temperature, load and uptime, once per station ID.
# Payload and topic as in docs/architecture.md. Run by nc-health.timer every 60 s.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# Read only the keys we need from .env instead of sourcing it.
env_value() { grep -E "^$1=" "$REPO/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true; }

STATION_ID="$(env_value STATION_ID)"; STATION_ID="${STATION_ID:-station-1}"
STATION_IDS="$(env_value STATION_IDS)"
MQTT_HOST="$(env_value MQTT_HOST)"; MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="$(env_value MQTT_PORT)"; MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="$(env_value MQTT_USERNAME)"
MQTT_PASSWORD="$(env_value MQTT_PASSWORD)"

cpu_temp=$(awk '{ printf "%.1f", $1 / 1000 }' /sys/class/thermal/thermal_zone0/temp)
load1=$(cut -d' ' -f1 /proc/loadavg)
uptime_s=$(cut -d. -f1 /proc/uptime)
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

auth=()
if [[ -n "$MQTT_USERNAME" ]]; then auth=(-u "$MQTT_USERNAME" -P "$MQTT_PASSWORD"); fi

for station in $STATION_ID ${STATION_IDS//,/ }; do
  payload=$(printf '{"station_id": "%s", "timestamp": "%s", "cpu_temp": %s, "load1": %s, "uptime_s": %s}' \
    "$station" "$timestamp" "$cpu_temp" "$load1" "$uptime_s")
  mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" "${auth[@]}" -q 1 \
    -t "naturecheckpoint/$station/health" -m "$payload"
done

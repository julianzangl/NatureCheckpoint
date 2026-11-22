#!/usr/bin/env bash
# Add a Mosquitto user, or change its password, in deploy/mosquitto/passwd.
# Usage: bash deploy/mosquitto/add-user.sh <user> <password>
# Users: station-1, station-2 (sensor nodes) and ingest (mqtt-ingest).
# The passwd file is git-ignored. Runs mosquitto_passwd from the broker image, so only Docker is needed.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <user> <password>" >&2
  exit 1
fi

cd "$(dirname "$0")"
touch passwd

# MSYS_NO_PATHCONV stops Git Bash on Windows from rewriting the container paths.
MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/mosquitto/config" eclipse-mosquitto:2 \
  mosquitto_passwd -b /mosquitto/config/passwd "$1" "$2"

echo "User '$1' saved in deploy/mosquitto/passwd."
echo "If the broker is running, reload it: docker compose -f deploy/docker-compose.yml kill -s SIGHUP mosquitto"

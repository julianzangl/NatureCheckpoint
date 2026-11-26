#!/usr/bin/env bash
# Install and start the NatureCheckpoint systemd units on the Pi (#30). Run with sudo:
#   sudo deploy/pi/install-services.sh [--stop-lab5]
# --stop-lab5 stops and disables the course's lab5-publisher.service, which also uses GPIO16.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_AS="${SUDO_USER:-admin}"
UNITS=(nc-backend.service nc-ingest.service nc-sensor-node.service nc-health.service nc-health.timer)

if [[ "${1:-}" == "--stop-lab5" ]] && systemctl list-unit-files lab5-publisher.service >/dev/null; then
  systemctl disable --now lab5-publisher.service || true
  echo "lab5-publisher.service stopped and disabled"
fi

for unit in "${UNITS[@]}"; do
  sed -e "s|@REPO@|$REPO|g" -e "s|@USER@|$RUN_AS|g" "$REPO/deploy/pi/$unit" > "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now nc-backend.service nc-ingest.service nc-sensor-node.service nc-health.timer
systemctl --no-pager --lines=0 status nc-backend nc-ingest nc-sensor-node nc-health.timer || true

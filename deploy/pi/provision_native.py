"""Provision InfluxDB and Grafana that run natively on the Pi (no Docker).

The Pi in the demo already runs InfluxDB 2 and Grafana as system services. This script gives
NatureCheckpoint its own org, bucket and token in that InfluxDB, and the same data source and
dashboards in Grafana that Docker Compose provisions from ``deploy/grafana/``.

It is idempotent: existing objects are kept. New tokens are written into the repository's
``.env`` and never printed.

Needs in the environment (e.g. ``set -a; . ~/secrets.env; set +a``):
    INFLUX_OPERATOR_TOKEN   an InfluxDB operator (all-access) token
    GRAFANA_ADMIN_PASSWORD  the Grafana admin password

Run from the repository root: ``.venv/bin/python deploy/pi/provision_native.py``
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
DASHBOARDS = REPO_ROOT / "deploy" / "grafana" / "dashboards"

INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
ORG = os.getenv("INFLUXDB_ORG", "naturecheckpoint")
BUCKET = os.getenv("INFLUXDB_BUCKET", "environment")
RETENTION_S = 90 * 24 * 3600
TOKEN_DESCRIPTION = "naturecheckpoint read/write"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def set_env(path: Path, updates: dict[str, str]) -> None:
    """Replace or append keys in a .env file, keeping all other lines."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    done: set[str] = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in updates and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={updates[key]}"
            done.add(key)
    lines += [f"{key}={value}" for key, value in updates.items() if key not in done]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)


def provision_influx(operator_token: str) -> str:
    """Return a read/write token for our bucket, creating org, bucket and token if needed."""
    api = httpx.Client(
        base_url=INFLUX_URL, headers={"Authorization": f"Token {operator_token}"}, timeout=10
    )
    orgs = api.get("/api/v2/orgs", params={"org": ORG})
    if orgs.status_code == 200 and orgs.json().get("orgs"):
        org_id = orgs.json()["orgs"][0]["id"]
    else:
        org_id = api.post("/api/v2/orgs", json={"name": ORG}).raise_for_status().json()["id"]
        print(f"influx: created org {ORG}")

    buckets = api.get("/api/v2/buckets", params={"orgID": org_id, "name": BUCKET})
    found = buckets.json().get("buckets", []) if buckets.status_code == 200 else []
    if found:
        bucket_id = found[0]["id"]
    else:
        body = {
            "orgID": org_id,
            "name": BUCKET,
            "retentionRules": [{"type": "expire", "everySeconds": RETENTION_S}],
        }
        bucket_id = api.post("/api/v2/buckets", json=body).raise_for_status().json()["id"]
        print(f"influx: created bucket {BUCKET} (90 days)")

    existing = read_env(ENV_FILE).get("INFLUXDB_TOKEN", "")
    if existing:
        check = httpx.get(
            f"{INFLUX_URL}/api/v2/buckets",
            params={"orgID": org_id, "name": BUCKET},
            headers={"Authorization": f"Token {existing}"},
            timeout=10,
        )
        if check.status_code == 200 and check.json().get("buckets"):
            print("influx: token in .env still valid")
            return existing

    resource = {"type": "buckets", "id": bucket_id, "orgID": org_id}
    body = {
        "orgID": org_id,
        "description": TOKEN_DESCRIPTION,
        "permissions": [
            {"action": "read", "resource": resource},
            {"action": "write", "resource": resource},
        ],
    }
    token = api.post("/api/v2/authorizations", json=body).raise_for_status().json()["token"]
    print("influx: created read/write token (stored in .env)")
    return token


def provision_grafana(password: str, token: str) -> None:
    api = httpx.Client(base_url=GRAFANA_URL, auth=("admin", password), timeout=10)
    datasource = {
        "name": "NatureCheckpoint InfluxDB",
        "uid": "influxdb",
        "type": "influxdb",
        "access": "proxy",
        "url": INFLUX_URL,
        "jsonData": {"version": "Flux", "organization": ORG, "defaultBucket": BUCKET},
        "secureJsonData": {"token": token},
    }
    if api.get("/api/datasources/uid/influxdb").status_code == 200:
        api.put("/api/datasources/uid/influxdb", json=datasource).raise_for_status()
        print("grafana: updated data source")
    else:
        api.post("/api/datasources", json=datasource).raise_for_status()
        print("grafana: created data source")

    folders = api.get("/api/folders").raise_for_status().json()
    folder = next((f for f in folders if f["title"] == "NatureCheckpoint"), None)
    if folder is None:
        folder = api.post("/api/folders", json={"title": "NatureCheckpoint"}).raise_for_status()
        folder = folder.json()
    for path in sorted(DASHBOARDS.glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        dashboard.pop("id", None)
        body = {"dashboard": dashboard, "folderUid": folder["uid"], "overwrite": True}
        api.post("/api/dashboards/db", json=body).raise_for_status()
        print(f"grafana: imported {path.name}")


def main() -> None:
    operator_token = os.getenv("INFLUX_OPERATOR_TOKEN", "")
    password = os.getenv("GRAFANA_ADMIN_PASSWORD", "")
    if not operator_token or not password:
        sys.exit("INFLUX_OPERATOR_TOKEN and GRAFANA_ADMIN_PASSWORD must be set")
    token = provision_influx(operator_token)
    set_env(
        ENV_FILE,
        {
            "INFLUXDB_URL": INFLUX_URL,
            "INFLUXDB_TOKEN": token,
            "INFLUXDB_ORG": ORG,
            "INFLUXDB_BUCKET": BUCKET,
        },
    )
    provision_grafana(password, token)


if __name__ == "__main__":
    main()

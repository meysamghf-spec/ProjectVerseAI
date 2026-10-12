"""Live API smoke test for a running ProjectVerse AI backend.

Usage:
    python scripts/smoke_api.py http://127.0.0.1:8000

The script creates a small software project, reopens it, checks schedule and
report generation, confirms another owner cannot read it, and deletes it.
It does not call an external language model.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def request(base: str, path: str, method: str = "GET", body: dict | None = None, owner: str = "smoke-user"):
    data = None if body is None else json.dumps(body).encode()
    headers = {"X-Owner-Id": owner, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            payload = response.read()
            parsed = json.loads(payload.decode() or "null") if payload else None
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        try:
            parsed = json.loads(detail) if detail else None
        except json.JSONDecodeError:
            parsed = detail
        return exc.code, parsed


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SMOKE FAIL: {message}")
    print(f"SMOKE OK: {message}")


def main() -> None:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
    status, health = request(base, "/api/v1/health")
    expect(status == 200 and health.get("status") == "ok", "health endpoint")
    status, ready = request(base, "/api/v1/ready")
    expect(status == 200 and ready.get("database") is True, "readiness endpoint")

    status, project = request(
        base,
        "/api/v1/projects",
        "POST",
        {
            "prompt": "Plan a small software platform with four engineers and a three month schedule.",
            "name": "Smoke software project",
            "category": "software",
            "generate": True,
            "run_monte_carlo": False,
        },
    )
    expect(status == 201 and project.get("id"), f"project creation ({status})")
    project_id = project["id"]
    status, reopened = request(base, f"/api/v1/projects/{project_id}")
    expect(status == 200 and reopened.get("name") == "Smoke software project", "project reopen")
    expect(len(reopened.get("tasks") or []) > 1, "generated tasks")
    expect((reopened.get("latest_simulation") or {}).get("result", {}).get("project_duration", 0) > 0, "deterministic schedule")

    status, hidden = request(base, f"/api/v1/projects/{project_id}", owner="other-smoke-user")
    expect(status == 404, "owner isolation")

    status, report = request(
        base,
        f"/api/v1/projects/{project_id}/reports",
        "POST",
        {"format": "json", "report_type": "summary"},
    )
    expect(status == 200 and isinstance(report, dict) and report.get("disclaimer"), "JSON report")

    status, _deleted = request(base, f"/api/v1/projects/{project_id}", "DELETE")
    expect(status == 204, "project deletion")
    status, missing = request(base, f"/api/v1/projects/{project_id}")
    expect(status == 404, "deleted project stays hidden")
    print("SMOKE PASS")


if __name__ == "__main__":
    main()

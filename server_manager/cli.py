from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="server-manager")
    parser.add_argument(
        "--url",
        default=os.getenv("SERVER_MANAGER_URL", "http://127.0.0.1:8080"),
        help="Server Manager API URL.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("SERVER_MANAGER_API_TOKEN"),
        help="API bearer token.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("service_id", nargs="?")

    subparsers.add_parser("resources")
    subparsers.add_parser("audit")
    subparsers.add_parser("schedules")

    schedule_add = subparsers.add_parser("schedule-add")
    schedule_add.add_argument("service_id")
    schedule_add.add_argument("operation", choices=["start", "stop", "restart"])
    schedule_add.add_argument("kind", choices=["daily", "weekly"])
    schedule_add.add_argument("time", help="HH:MM")
    schedule_add.add_argument("--weekday", action="append", default=[])

    schedule_delete = subparsers.add_parser("schedule-delete")
    schedule_delete.add_argument("schedule_id")

    for command in ("start", "stop", "restart"):
        operation_parser = subparsers.add_parser(command)
        operation_parser.add_argument("service_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            if args.service_id:
                payload = _request(args.url, args.token, "GET", f"/api/services/{args.service_id}/status")
                _print_json(payload)
            else:
                payload = _request(args.url, args.token, "GET", "/api/services")
                _print_services(payload)
        elif args.command in {"start", "stop", "restart"}:
            payload = _request(
                args.url,
                args.token,
                "POST",
                f"/api/services/{args.service_id}/{args.command}",
                source="CLI",
            )
            _print_json(payload)
        elif args.command == "resources":
            payload = _request(args.url, args.token, "GET", "/api/resources/summary")
            _print_json(payload)
        elif args.command == "audit":
            payload = _request(args.url, args.token, "GET", "/api/audit")
            _print_json(payload)
        elif args.command == "schedules":
            payload = _request(args.url, args.token, "GET", "/api/schedules")
            _print_json(payload)
        elif args.command == "schedule-add":
            hour, minute = _parse_time(args.time)
            payload = _request(
                args.url,
                args.token,
                "POST",
                "/api/schedules",
                body={
                    "service_id": args.service_id,
                    "operation": args.operation,
                    "kind": args.kind,
                    "hour": hour,
                    "minute": minute,
                    "weekdays": args.weekday,
                },
                source="CLI",
            )
            _print_json(payload)
        elif args.command == "schedule-delete":
            payload = _request(
                args.url,
                args.token,
                "DELETE",
                f"/api/schedules/{args.schedule_id}",
                source="CLI",
            )
            _print_json(payload)
    except urllib.error.HTTPError as exc:
        _print_http_error(exc)
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach Server Manager: {exc.reason}", file=sys.stderr)
        return 1

    return 0


def _request(
    base_url: str,
    token: str | None,
    method: str,
    path: str,
    *,
    source: str | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if source:
        headers["X-Server-Manager-Source"] = source
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        method=method,
        headers=headers,
        data=data,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _print_services(payload: dict[str, Any]) -> None:
    services = payload.get("services", [])
    for service in services:
        capabilities = service.get("capabilities", {})
        enabled_ops = ",".join(name for name, enabled in capabilities.items() if enabled)
        print(
            f"{service['id']:<24} {service['type'] or '-':<16} "
            f"{service['availability']:<12} {service['config_status']:<8} {enabled_ops}"
        )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_http_error(exc: urllib.error.HTTPError) -> None:
    body = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise SystemExit("Time must use HH:MM format.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise SystemExit("Time must be between 00:00 and 23:59.")
    return hour, minute


if __name__ == "__main__":
    raise SystemExit(main())

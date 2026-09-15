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
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if source:
        headers["X-Server-Manager-Source"] = source
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        method=method,
        headers=headers,
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


if __name__ == "__main__":
    raise SystemExit(main())

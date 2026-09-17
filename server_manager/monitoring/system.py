from __future__ import annotations

import os
import time
from pathlib import Path

import psutil


def system_resources(path: str = "/") -> dict:
    virtual_memory = psutil.virtual_memory()
    disk = psutil.disk_usage(path if Path(path).exists() else "/")
    load_average = os.getloadavg() if hasattr(os, "getloadavg") else None
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "load_average": load_average,
        "boot_time": psutil.boot_time(),
        "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
        "memory": {
            "total_bytes": virtual_memory.total,
            "used_bytes": virtual_memory.used,
            "available_bytes": virtual_memory.available,
            "percent": virtual_memory.percent,
            "note": (
                "Available memory is Linux's estimate of memory usable without swapping. "
                "Used memory includes kernel, processes, buffers and cache."
            ),
        },
        "disk": {
            "path": path,
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "swap": {
            "total_bytes": psutil.swap_memory().total,
            "used_bytes": psutil.swap_memory().used,
            "free_bytes": psutil.swap_memory().free,
            "percent": psutil.swap_memory().percent,
        },
        "temperature_celsius": _temperature(),
    }


def resource_summary(service_resources: list[dict], path: str = "/") -> dict:
    system = system_resources(path)
    monitored_memory = sum(
        item.get("memory_bytes") or 0
        for item in service_resources
        if isinstance(item.get("memory_bytes"), int)
    )
    used = system["memory"]["used_bytes"]
    return {
        "system": system,
        "services": service_resources,
        "memory_accounting": {
            "monitored_services_bytes": monitored_memory,
            "unattributed_used_bytes": max(used - monitored_memory, 0),
            "available_bytes": system["memory"]["available_bytes"],
            "note": (
                "Unattributed used memory is not necessarily waste or free memory. It includes the OS, "
                "Docker daemon, unmanaged processes, shared memory and Linux cache effects."
            ),
        },
    }


def _temperature() -> float | None:
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if not thermal_path.exists():
        return None
    try:
        return int(thermal_path.read_text(encoding="utf-8").strip()) / 1000
    except (OSError, ValueError):
        return None

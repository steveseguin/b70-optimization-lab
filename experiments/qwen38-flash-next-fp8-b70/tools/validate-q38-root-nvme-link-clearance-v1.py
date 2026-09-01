#!/usr/bin/env python3
"""Fail closed unless the fixed root-NVMe maintenance clearance is exact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CLEARANCE_PATH = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/host/"
    "20260901-root-nvme-link-clearance-v1.json"
)
EXPECTED_DEVICES = [
    {
        "device_id": 0,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "pci_bdf_address": "0000:23:00.0",
    },
    {
        "device_id": 1,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "pci_bdf_address": "0000:27:00.0",
    },
    {
        "device_id": 2,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "pci_bdf_address": "0000:43:00.0",
    },
    {
        "device_id": 3,
        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
        "pci_bdf_address": "0000:47:00.0",
    },
]


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} keys mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def require_int(value: Any, expected: int | None, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    if expected is not None and value != expected:
        raise ValueError(f"{label} must equal {expected}")
    return value


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("clearance must be a JSON object")
    require_exact_keys(
        value,
        {
            "schema_version",
            "status",
            "classification",
            "firmware_after",
            "idle",
            "bounded_read",
            "smart",
            "b70_devices",
        },
        "clearance",
    )
    require_int(value["schema_version"], 1, "schema_version")
    if value["status"] != "pass":
        raise ValueError("status must equal pass")
    if value["classification"] != "q38_root_nvme_link_clearance_v1":
        raise ValueError("classification is not q38_root_nvme_link_clearance_v1")
    if value["firmware_after"] != "5B2QGXA7":
        raise ValueError("firmware_after must equal 5B2QGXA7")

    idle = value["idle"]
    if not isinstance(idle, dict):
        raise ValueError("idle must be an object")
    require_exact_keys(
        idle,
        {"seconds", "local_nvme_corrected_delta", "root_port_corrected_delta"},
        "idle",
    )
    if require_int(idle["seconds"], None, "idle.seconds") < 1800:
        raise ValueError("idle.seconds must be at least 1800")
    require_int(
        idle["local_nvme_corrected_delta"],
        0,
        "idle.local_nvme_corrected_delta",
    )
    require_int(idle["root_port_corrected_delta"], 0, "idle.root_port_corrected_delta")

    bounded = value["bounded_read"]
    if not isinstance(bounded, dict):
        raise ValueError("bounded_read must be an object")
    require_exact_keys(
        bounded,
        {"local_nvme_corrected_delta", "root_port_corrected_delta"},
        "bounded_read",
    )
    require_int(
        bounded["local_nvme_corrected_delta"],
        0,
        "bounded_read.local_nvme_corrected_delta",
    )
    require_int(
        bounded["root_port_corrected_delta"],
        0,
        "bounded_read.root_port_corrected_delta",
    )

    smart = value["smart"]
    if not isinstance(smart, dict):
        raise ValueError("smart must be an object")
    require_exact_keys(smart, {"critical_warning", "media_errors"}, "smart")
    require_int(smart["critical_warning"], 0, "smart.critical_warning")
    require_int(smart["media_errors"], 0, "smart.media_errors")

    devices = value["b70_devices"]
    if not isinstance(devices, list) or len(devices) != len(EXPECTED_DEVICES):
        raise ValueError("b70_devices must identify the exact four-B70 topology")
    for index, (device, expected) in enumerate(zip(devices, EXPECTED_DEVICES)):
        if not isinstance(device, dict):
            raise ValueError(f"b70_devices[{index}] must be an object")
        require_exact_keys(
            device,
            {"device_id", "device_name", "pci_bdf_address"},
            f"b70_devices[{index}]",
        )
        require_int(
            device["device_id"],
            expected["device_id"],
            f"b70_devices[{index}].device_id",
        )
        if device["device_name"] != expected["device_name"]:
            raise ValueError(f"b70_devices[{index}].device_name mismatch")
        if device["pci_bdf_address"] != expected["pci_bdf_address"]:
            raise ValueError(f"b70_devices[{index}].pci_bdf_address mismatch")
    return value


def validate_file(path: Path, *, require_fixed_path: bool = True) -> dict[str, Any]:
    if require_fixed_path and path != CLEARANCE_PATH:
        raise ValueError(f"clearance path must equal {CLEARANCE_PATH}")
    if path.is_symlink():
        raise ValueError("clearance must not be a symlink")
    if not path.is_file():
        raise FileNotFoundError(f"clearance is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("clearance is not valid JSON") from exc
    return validate(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clearance-json", type=Path, required=True)
    args = parser.parse_args()
    value = validate_file(args.clearance_json)
    print(
        json.dumps(
            {
                "status": "pass",
                "classification": value["classification"],
                "clearance_path": str(args.clearance_json),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

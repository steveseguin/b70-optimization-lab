#!/usr/bin/env python3
"""CPU-only strict-schema and live-binding tests for root-NVMe clearance."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import unittest


MODULE_PATH = Path(__file__).with_name("validate-q38-root-nvme-link-clearance-v1.py")
SPEC = importlib.util.spec_from_file_location("q38_link_clearance", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BOOT_ID = "11111111-2222-4333-8444-555555555555"


def valid_live_identity() -> dict:
    return {
        "boot_id": BOOT_ID,
        "root_nvme": copy.deepcopy(MODULE.EXPECTED_ROOT_NVME),
    }


def valid_clearance() -> dict:
    return {
        "schema_version": 1,
        "status": "pass",
        "classification": "q38_root_nvme_link_clearance_v1",
        "boot_id": BOOT_ID,
        "root_nvme": copy.deepcopy(MODULE.EXPECTED_ROOT_NVME),
        "idle": {
            "seconds": 1800,
            "local_nvme_corrected_delta": 0,
            "root_port_corrected_delta": 0,
        },
        "bounded_read": {
            "local_nvme_corrected_delta": 0,
            "root_port_corrected_delta": 0,
        },
        "smart": {"critical_warning": 0, "media_errors": 0},
        "b70_devices": copy.deepcopy(MODULE.EXPECTED_DEVICES),
    }


def validate(receipt: dict, live: dict | None = None) -> dict:
    return MODULE.validate(
        receipt,
        live_identity=valid_live_identity() if live is None else live,
    )


class ClearanceContractTests(unittest.TestCase):
    def test_accepts_exact_current_boot_and_hardware(self) -> None:
        self.assertEqual(validate(valid_clearance())["status"], "pass")

    def test_rejects_receipt_replayed_on_another_boot(self) -> None:
        receipt = valid_clearance()
        receipt["boot_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        with self.assertRaisesRegex(ValueError, "current boot"):
            validate(receipt)

    def test_rejects_each_receipt_nvme_identity_drift(self) -> None:
        mutations = {
            "controller": "nvme1",
            "serial": "OTHER",
            "model": "OTHER",
            "pci_bdf": "0000:02:00.0",
            "firmware": "4B2QGXA7",
        }
        for field, value in mutations.items():
            receipt = valid_clearance()
            receipt["root_nvme"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, f"root_nvme.{field}"),
            ):
                validate(receipt)

    def test_rejects_each_live_nvme_identity_drift(self) -> None:
        mutations = {
            "controller": "nvme1",
            "serial": "OTHER",
            "model": "OTHER",
            "pci_bdf": "0000:02:00.0",
            "firmware": "4B2QGXA7",
        }
        for field, value in mutations.items():
            live = valid_live_identity()
            live["root_nvme"][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(ValueError, f"live root_nvme.{field}"),
            ):
                validate(valid_clearance(), live)

    def test_validate_file_always_uses_live_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary, "clearance.json")
            path.write_text(json.dumps(valid_clearance()), encoding="utf-8")
            stale = valid_live_identity()
            stale["boot_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
            with (
                mock.patch.object(MODULE, "read_live_identity", return_value=stale),
                self.assertRaisesRegex(ValueError, "current boot"),
            ):
                MODULE.validate_file(path, require_fixed_path=False)

    def test_read_live_identity_derives_and_verifies_pci_ancestor(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            controller = (
                root / "devices/pci0000:00/0000:00:03.1/0000:01:00.0/nvme/nvme0"
            )
            controller.mkdir(parents=True)
            values = {
                "serial": "S6WSNS0T109768K\n",
                "model": "Samsung SSD 980 PRO with Heatsink 1TB   \n",
                "address": "0000:01:00.0\n",
                "firmware_rev": "5B2QGXA7\n",
            }
            for name, value in values.items():
                (controller / name).write_text(value, encoding="utf-8")
            class_controller = root / "class/nvme/nvme0"
            class_controller.parent.mkdir(parents=True)
            class_controller.symlink_to(controller, target_is_directory=True)
            boot_id = root / "boot_id"
            boot_id.write_text(f"{BOOT_ID}\n", encoding="utf-8")

            with (
                mock.patch.object(MODULE, "BOOT_ID_PATH", boot_id),
                mock.patch.object(MODULE, "NVME_SYSFS", class_controller),
            ):
                self.assertEqual(MODULE.read_live_identity(), valid_live_identity())
                (controller / "address").write_text("0000:02:00.0\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "ancestor and address"):
                    MODULE.read_live_identity()

    def test_idle_must_reach_1800_seconds_with_zero_deltas(self) -> None:
        for field, value in (
            ("seconds", 1799),
            ("local_nvme_corrected_delta", 1),
            ("root_port_corrected_delta", 1),
        ):
            receipt = valid_clearance()
            receipt["idle"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(receipt)

    def test_bounded_read_and_smart_must_be_clean(self) -> None:
        for section, field in (
            ("bounded_read", "local_nvme_corrected_delta"),
            ("bounded_read", "root_port_corrected_delta"),
            ("smart", "critical_warning"),
            ("smart", "media_errors"),
        ):
            receipt = valid_clearance()
            receipt[section][field] = 1
            with (
                self.subTest(section=section, field=field),
                self.assertRaises(ValueError),
            ):
                validate(receipt)

    def test_rejects_topology_drift(self) -> None:
        receipt = valid_clearance()
        receipt["b70_devices"].pop()
        with self.assertRaisesRegex(ValueError, "four-B70 topology"):
            validate(receipt)

    def test_rejects_extra_keys_and_boolean_integers(self) -> None:
        receipt = valid_clearance()
        receipt["extra"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            validate(receipt)
        receipt = valid_clearance()
        receipt["smart"]["critical_warning"] = False
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            validate(receipt)

    def test_rejects_boolean_or_floating_point_device_ids(self) -> None:
        for device_id in (False, True, 0.0, 1.0):
            receipt = valid_clearance()
            receipt["b70_devices"][int(device_id)]["device_id"] = device_id
            with (
                self.subTest(device_id=device_id),
                self.assertRaisesRegex(ValueError, "must be an integer"),
            ):
                validate(receipt)


if __name__ == "__main__":
    unittest.main()

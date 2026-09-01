#!/usr/bin/env python3
"""CPU-only strict-schema tests for the root-NVMe clearance gate."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).with_name("validate-q38-root-nvme-link-clearance-v1.py")
SPEC = importlib.util.spec_from_file_location("q38_link_clearance", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_clearance() -> dict:
    return {
        "schema_version": 1,
        "status": "pass",
        "classification": "q38_root_nvme_link_clearance_v1",
        "firmware_after": "5B2QGXA7",
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


class ClearanceContractTests(unittest.TestCase):
    def test_accepts_exact_clearance(self) -> None:
        self.assertEqual(MODULE.validate(valid_clearance())["status"], "pass")

    def test_idle_must_reach_1800_seconds_with_zero_deltas(self) -> None:
        for field, value in (
            ("seconds", 1799),
            ("local_nvme_corrected_delta", 1),
            ("root_port_corrected_delta", 1),
        ):
            receipt = valid_clearance()
            receipt["idle"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                MODULE.validate(receipt)

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
                MODULE.validate(receipt)

    def test_rejects_firmware_or_topology_drift(self) -> None:
        receipt = valid_clearance()
        receipt["firmware_after"] = "OLD"
        with self.assertRaisesRegex(ValueError, "firmware_after"):
            MODULE.validate(receipt)
        receipt = valid_clearance()
        receipt["b70_devices"].pop()
        with self.assertRaisesRegex(ValueError, "four-B70 topology"):
            MODULE.validate(receipt)

    def test_rejects_extra_keys_and_boolean_integers(self) -> None:
        receipt = valid_clearance()
        receipt["extra"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "keys mismatch"):
            MODULE.validate(receipt)
        receipt = valid_clearance()
        receipt["smart"]["critical_warning"] = False
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            MODULE.validate(receipt)

    def test_rejects_boolean_or_floating_point_device_ids(self) -> None:
        for device_id in (False, True, 0.0, 1.0):
            receipt = valid_clearance()
            receipt["b70_devices"][int(device_id)]["device_id"] = device_id
            with (
                self.subTest(device_id=device_id),
                self.assertRaisesRegex(ValueError, "must be an integer"),
            ):
                MODULE.validate(receipt)


if __name__ == "__main__":
    unittest.main()

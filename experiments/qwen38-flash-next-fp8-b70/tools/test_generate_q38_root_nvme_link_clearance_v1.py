#!/usr/bin/env python3
"""CPU-only tests for the root-NVMe clearance receipt generator."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


def load(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_").replace(".py", ""), path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve postponed annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GEN = load("generate-q38-root-nvme-link-clearance-v1.py")
VAL = load("validate-q38-root-nvme-link-clearance-v1.py")
BOOT_ID = "11111111-2222-4333-8444-555555555555"


def make_sampler(sequence):
    """Return a sampler that yields LinkSamples from (t, ep, root, sectors) tuples."""
    state = {"i": 0}

    def sampler():
        i = min(state["i"], len(sequence) - 1)
        state["i"] += 1
        t, ep, root, sectors = sequence[i]
        return GEN.LinkSample(
            monotonic=t,
            endpoint_corrected=ep,
            endpoint_nonfatal=0,
            endpoint_fatal=0,
            root_corrected=root,
            sectors_read=sectors,
        )

    return sampler


class IdleWindowTests(unittest.TestCase):
    def test_clean_window_passes_after_required_seconds(self):
        sampler = make_sampler([(0, 10, 0, 100), (900, 10, 0, 100), (1800, 10, 0, 104)])
        ok, record = GEN.run_idle_window(
            seconds=1800, poll_seconds=0, sampler=sampler, sleeper=lambda s: None
        )
        self.assertTrue(ok)
        self.assertEqual(record["seconds"], 1800)
        self.assertEqual(record["local_nvme_corrected_delta"], 0)
        self.assertEqual(record["root_port_corrected_delta"], 0)

    def test_first_endpoint_increment_stops_immediately(self):
        sampler = make_sampler([(0, 10, 0, 100), (30, 11, 0, 100), (1800, 11, 0, 100)])
        ok, record = GEN.run_idle_window(
            seconds=1800, poll_seconds=0, sampler=sampler, sleeper=lambda s: None
        )
        self.assertFalse(ok)
        self.assertEqual(record["reason"], "link-event")
        self.assertEqual(record["seconds"], 30)
        self.assertEqual(record["local_nvme_corrected_delta"], 1)

    def test_root_port_increment_stops(self):
        sampler = make_sampler([(0, 10, 0, 100), (30, 10, 1, 100)])
        ok, record = GEN.run_idle_window(
            seconds=1800, poll_seconds=0, sampler=sampler, sleeper=lambda s: None
        )
        self.assertFalse(ok)
        self.assertEqual(record["root_port_corrected_delta"], 1)


class BoundedReadTests(unittest.TestCase):
    def make_source(self, tmp: str, sizes):
        source = Path(tmp)
        for index, size in enumerate(sizes):
            (source / f"model-{index:05d}.safetensors").write_bytes(b"\0" * size)
        return source

    def test_plan_respects_budget_and_block_rounding(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(tmp, [40 << 20, 40 << 20, 40 << 20])
            plan = GEN.select_read_files(source, 64 << 20)
            self.assertEqual([take for _, take in plan], [32 << 20, 32 << 20])

    def test_clean_read_passes_and_records_bytes(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(tmp, [64 << 20])
            calls = []
            sampler = make_sampler([(0, 5, 0, 0), (1, 5, 0, 131072)])
            ok, record = GEN.run_bounded_read(
                source=source,
                read_gib=0,
                sampler=sampler,
                runner=lambda cmd: calls.append(cmd),
                budget_bytes=32 << 20,
            )
            self.assertTrue(ok)
            self.assertEqual(record["bytes_read"], 32 << 20)
            self.assertEqual(len(calls), 1)
            self.assertIn("iflag=direct", calls[0])
            self.assertIn("count=2", calls[0])
            self.assertEqual(calls[0][0], "dd")

    def test_link_event_during_read_fails(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(tmp, [64 << 20])
            sampler = make_sampler([(0, 5, 0, 0), (1, 6, 0, 131072)])
            ok, record = GEN.run_bounded_read(
                source=source,
                read_gib=0,
                sampler=sampler,
                runner=lambda cmd: None,
                budget_bytes=32 << 20,
            )
            self.assertFalse(ok)
            self.assertEqual(record["local_nvme_corrected_delta"], 1)

    def test_short_read_fails(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(tmp, [32 << 20])
            sampler = make_sampler([(0, 5, 0, 0), (1, 5, 0, 0)])
            ok, record = GEN.run_bounded_read(
                source=source,
                read_gib=0,
                sampler=sampler,
                runner=lambda cmd: None,
                budget_bytes=64 << 20,
            )
            self.assertFalse(ok)
            self.assertEqual(record["bytes_read"], 32 << 20)


class ReceiptTests(unittest.TestCase):
    def live(self):
        return {"boot_id": BOOT_ID, "root_nvme": copy.deepcopy(VAL.EXPECTED_ROOT_NVME)}

    def test_assembled_receipt_passes_tracked_validator(self):
        receipt = GEN.build_receipt(
            boot_id=BOOT_ID,
            root_nvme=copy.deepcopy(VAL.EXPECTED_ROOT_NVME),
            idle={
                "seconds": 1803,
                "local_nvme_corrected_delta": 0,
                "root_port_corrected_delta": 0,
                "polls": 361,
            },
            bounded={
                "local_nvme_corrected_delta": 0,
                "root_port_corrected_delta": 0,
                "bytes_read": 4 << 30,
            },
            smart={"critical_warning": 0, "media_errors": 0, "temperature_c": 41},
            b70_devices=copy.deepcopy(VAL.EXPECTED_DEVICES),
        )
        self.assertEqual(VAL.validate(receipt, live_identity=self.live()), receipt)
        self.assertEqual(
            set(receipt),
            {
                "schema_version",
                "status",
                "classification",
                "boot_id",
                "root_nvme",
                "idle",
                "bounded_read",
                "smart",
                "b70_devices",
            },
        )

    def test_dirty_idle_receipt_is_rejected_by_validator(self):
        receipt = GEN.build_receipt(
            boot_id=BOOT_ID,
            root_nvme=copy.deepcopy(VAL.EXPECTED_ROOT_NVME),
            idle={
                "seconds": 1800,
                "local_nvme_corrected_delta": 1,
                "root_port_corrected_delta": 0,
            },
            bounded={"local_nvme_corrected_delta": 0, "root_port_corrected_delta": 0},
            smart={"critical_warning": 0, "media_errors": 0},
            b70_devices=copy.deepcopy(VAL.EXPECTED_DEVICES),
        )
        with self.assertRaises(ValueError):
            VAL.validate(receipt, live_identity=self.live())

    def test_stale_firmware_receipt_is_rejected_by_validator(self):
        stale = copy.deepcopy(VAL.EXPECTED_ROOT_NVME)
        stale["firmware"] = "4B2QGXA7"
        receipt = GEN.build_receipt(
            boot_id=BOOT_ID,
            root_nvme=stale,
            idle={
                "seconds": 1800,
                "local_nvme_corrected_delta": 0,
                "root_port_corrected_delta": 0,
            },
            bounded={"local_nvme_corrected_delta": 0, "root_port_corrected_delta": 0},
            smart={"critical_warning": 0, "media_errors": 0},
            b70_devices=copy.deepcopy(VAL.EXPECTED_DEVICES),
        )
        live = self.live()
        live["root_nvme"]["firmware"] = "4B2QGXA7"
        with self.assertRaises(ValueError):
            VAL.validate(receipt, live_identity=live)


if __name__ == "__main__":
    unittest.main()

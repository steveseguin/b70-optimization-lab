#!/usr/bin/env python3
"""Regressions for tools/check-container-packet.py.

The checker is what stops a generated container packet from drifting away from the recipe launcher
it claims to reproduce, and it runs in CI where neither the image nor the weights exist. A checker
that silently stops checking is worse than none, so these tests pin both directions: the committed
packets pass, and each way a packet can drift fails.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("ccp", ROOT / "tools/check-container-packet.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContainerPacketCheckerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load()
        cls.packets = sorted(p.parent for p in ROOT.glob("packages/*/compose.yaml"))

    def test_committed_packets_pass(self):
        self.assertTrue(self.packets, "expected at least one container packet")
        for packet in self.packets:
            with self.subTest(packet=packet.name):
                self.assertEqual(self.m.check(packet), [], f"{packet.name} should be consistent")

    def test_launcher_requirements_are_not_empty(self):
        names = self.m.launcher_env_names()
        self.assertGreater(len(names), 40,
                           "the launcher env requirement collapsed; a parser change probably "
                           "classified everything as conditional")
        self.assertIn("VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH", names)

    def test_conditionally_forwarded_variables_are_not_required(self):
        names = self.m.launcher_env_names()
        # Forwarded only when the operator sets them; a packet that does not use them is still valid.
        for optional in ("VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS", "VLLM_XPU_W4A16_DETERMINISM_PAD_LOW"):
            self.assertNotIn(optional, names)

    def _mutated(self, transform):
        source = (self.packets[0] / "compose.yaml").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "packet"
            d.mkdir()
            (d / "compose.yaml").write_text(transform(source))
            return self.m.check(d)

    def test_missing_launcher_env_fails(self):
        errs = self._mutated(lambda s: "\n".join(
            line for line in s.splitlines() if "VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH" not in line))
        self.assertTrue(any("missing" in e for e in errs), errs)

    def test_floating_tag_fails(self):
        errs = self._mutated(lambda s: s.replace(
            s.split("image: ")[1].split("\n")[0], "ghcr.io/example/image:latest"))
        self.assertTrue(any("not pinned by digest" in e for e in errs), errs)

    def test_writable_model_mount_fails(self):
        errs = self._mutated(lambda s: s.replace(":/model:ro", ":/model"))
        self.assertTrue(any("read-only" in e for e in errs), errs)

    def test_port_off_loopback_fails(self):
        errs = self._mutated(lambda s: s.replace('"127.0.0.1:${PORT:-18131}:8000"', '"${PORT:-18131}:8000"'))
        self.assertTrue(any("loopback" in e for e in errs), errs)

    def test_profiles_must_differ_only_in_device_selection(self):
        # The value appears in the shared anchor and again in each service. Only a service-level
        # change alters the resolved config, so mutate the second occurrence, not the first.
        def one_service_only(s: str) -> str:
            first = s.index('PYTHONHASHSEED: "0"')
            second = s.index('PYTHONHASHSEED: "0"', first + 1)
            return s[:second] + 'PYTHONHASHSEED: "1"' + s[second + len('PYTHONHASHSEED: "0"'):]

        errs = self._mutated(one_service_only)
        self.assertTrue(any("differ only in device selection" in e for e in errs), errs)

    def test_serving_argument_drift_fails(self):
        def change_one_profile(source):
            doc = self.m.yaml.safe_load(source)
            cmd = doc["services"]["two-gpu"]["command"]
            cmd[cmd.index("--max-model-len") + 1] = "1"
            return self.m.yaml.safe_dump(doc)

        errs = self._mutated(change_one_profile)
        self.assertTrue(any("serving arguments differ" in e for e in errs), errs)

    def test_extra_serving_argument_fails(self):
        def change_one_profile(source):
            doc = self.m.yaml.safe_load(source)
            doc["services"]["two-gpu"]["command"].extend(["--seed", "2"])
            return self.m.yaml.safe_dump(doc)

        errs = self._mutated(change_one_profile)
        self.assertTrue(any("serving arguments differ" in e for e in errs), errs)

    def test_two_card_only_packet_is_accepted_and_undeclared_profile_fails(self):
        """The 27B FP8 packet ships only two-gpu (declared in package.json). A packet declared two-card-only
        must not carry a one-gpu service, and a two-profile packet must not drop one silently."""
        import json, shutil
        fp8 = ROOT / "packages/qwen38-27b-fp8-tp2-b70"
        self.assertEqual(self.m.check(fp8), [], "the two-card-only FP8 packet should pass")
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "qwen38-27b-fp8-tp2-b70"
            packet.mkdir()
            shutil.copy(fp8 / "compose.yaml", packet / "compose.yaml")
            meta = json.loads((fp8 / "package.json").read_text())
            meta["container_packet"]["profiles"] = {"one-gpu": {"cards": 1, "tensor_parallel_size": 1},
                                                    "two-gpu": {"cards": 2, "tensor_parallel_size": 2}}
            (packet / "package.json").write_text(json.dumps(meta))
            errs = self.m.check(packet)
            self.assertTrue(any("has no one-gpu service" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()

    def test_two_card_only_packet_is_accepted_and_undeclared_profile_fails(self):
        """The 27B FP8 packet ships only two-gpu (declared in package.json). A packet declared two-card-only
        must not carry a one-gpu service, and a two-profile packet must not drop one silently."""
        import json, shutil
        fp8 = ROOT / "packages/qwen38-27b-fp8-tp2-b70"
        self.assertEqual(self.m.check(fp8), [], "the two-card-only FP8 packet should pass")
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / "qwen38-27b-fp8-tp2-b70"
            packet.mkdir()
            shutil.copy(fp8 / "compose.yaml", packet / "compose.yaml")
            meta = json.loads((fp8 / "package.json").read_text())
            meta["container_packet"]["profiles"] = {"one-gpu": {"cards": 1, "tensor_parallel_size": 1},
                                                    "two-gpu": {"cards": 2, "tensor_parallel_size": 2}}
            (packet / "package.json").write_text(json.dumps(meta))
            errs = self.m.check(packet)
            self.assertTrue(any("has no one-gpu service" in e for e in errs), errs)

#!/usr/bin/env python3
"""CPU-only contract tests for the bounded GPU3 health diagnostic."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKER = load_module(
    "gpu3_health_worker_test",
    SCRIPT_DIR / "qwen38_gpu3_incumbent_control_health_worker.py",
)
SUPERVISOR = load_module(
    "gpu3_health_supervisor_test",
    SCRIPT_DIR / "qwen38_gpu3_incumbent_control_health_supervisor.py",
)


def dummy_process(pid: int = 1234) -> dict[str, object]:
    return {
        "boot_id": "test-boot",
        "pid": pid,
        "pgid": pid,
        "sid": pid,
        "start_ticks": 98765,
    }


def advancing_clock():
    value = -10.0

    def now():
        nonlocal value
        value += 10.0
        return value

    return now


class FakeXPU:
    def __init__(self, fail_sync: bool = False) -> None:
        self.calls = 0
        self.fail_sync = fail_sync

    def synchronize(self) -> None:
        self.calls += 1
        if self.fail_sync:
            raise RuntimeError("synthetic synchronize failure")


class FakeBase:
    MIN_SAMPLES = 30
    MIN_LAUNCHES_PER_SAMPLE = 50
    MIN_STABILITY_REPLAYS = 16

    @staticmethod
    def _run_case(torch, launch, device, kv, samples, launches, stability):
        del device, samples, launches, stability
        assert kv == 128
        for _ in range(10):
            launch()
        torch.xpu.synchronize()
        raise AssertionError("instrumented stop failed")


class ShortWarmupBase(FakeBase):
    @staticmethod
    def _run_case(torch, launch, device, kv, samples, launches, stability):
        del device, kv, samples, launches, stability
        for _ in range(9):
            launch()
        torch.xpu.synchronize()


class HealthContractTests(unittest.TestCase):
    def make_contract(self, root: Path) -> tuple[Path, str]:
        path = root / "contract.json"
        WORKER.atomic_json(path, {"schema": "test"})
        return path, WORKER.sha256_file(path)

    def make_chain(
        self, root: Path, writer: str = "worker"
    ) -> tuple[WORKER.ReceiptChain, Path, str]:
        contract, digest = self.make_contract(root)
        chain = WORKER.ReceiptChain(
            root / f"{writer}-phases",
            writer,
            contract,
            digest,
            dummy_process(),
        )
        return chain, contract, digest

    def test_strict_json_rejects_duplicate_and_nonstandard_constant(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text('{"a":1,"a":2}\n', encoding="utf-8")
            with self.assertRaises(WORKER.ContractError):
                WORKER.load_json(path)
            path.write_text('{"a":NaN}\n', encoding="utf-8")
            with self.assertRaises(WORKER.ContractError):
                WORKER.load_json(path)

    def test_atomic_json_is_immutable_and_collision_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "packet.json"
            WORKER.atomic_json(path, {"passed": True})
            self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            self.assertEqual(json.loads(path.read_text()), {"passed": True})
            with self.assertRaises(WORKER.ContractError):
                WORKER.atomic_json(path, {"passed": False})

    def test_receipt_chain_rederives_hashes_and_rejects_writable_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root)
            first, first_sha = chain.emit("first", {"value": 1})
            second, _ = chain.emit("second", {"value": 2})
            receipts = WORKER.validate_receipt_chain(
                chain.directory, "worker", contract, digest
            )
            self.assertEqual([item["phase"] for item in receipts], ["first", "second"])
            self.assertEqual(
                WORKER.load_json(second)["previous_receipt_sha256"], first_sha
            )
            first.chmod(0o644)
            with self.assertRaisesRegex(WORKER.ContractError, "writable"):
                WORKER.validate_receipt_chain(
                    chain.directory, "worker", contract, digest
                )

    def test_instrumented_warmup_counts_ten_returns_then_one_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root)
            torch = SimpleNamespace(xpu=FakeXPU())
            result = WORKER.instrumented_warmup(
                FakeBase,
                torch,
                lambda: object(),
                chain,
                {"proc_self_maps_sha256": "a" * 64},
            )
            self.assertEqual(
                result,
                {
                    "returned_fa_launches": 10,
                    "synchronize_entries": 1,
                    "synchronize_returns": 1,
                },
            )
            receipts = WORKER.validate_receipt_chain(
                chain.directory, "worker", contract, digest
            )
            self.assertEqual(
                [item["phase"] for item in receipts],
                ["fa-launch-returned"] * 10 + ["sync-enter", "sync-return"],
            )
            self.assertEqual(torch.xpu.calls, 1)

    def test_instrumented_warmup_rejects_sync_before_ten_returns(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root)
            torch = SimpleNamespace(xpu=FakeXPU())
            with self.assertRaisesRegex(WORKER.ContractError, "exactly ten"):
                WORKER.instrumented_warmup(
                    ShortWarmupBase,
                    torch,
                    lambda: object(),
                    chain,
                    {"proc_self_maps_sha256": "a" * 64},
                )
            self.assertEqual(torch.xpu.calls, 0)

    def test_sync_enter_survives_a_synchronize_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root)
            torch = SimpleNamespace(xpu=FakeXPU(fail_sync=True))
            with self.assertRaisesRegex(RuntimeError, "synthetic synchronize"):
                WORKER.instrumented_warmup(
                    FakeBase,
                    torch,
                    lambda: object(),
                    chain,
                    {"proc_self_maps_sha256": "a" * 64},
                )
            receipts = WORKER.validate_receipt_chain(
                chain.directory, "worker", contract, digest
            )
            self.assertEqual(receipts[-1]["phase"], "sync-enter")
            self.assertNotIn("sync-return", [item["phase"] for item in receipts])

    def test_mapping_evidence_requires_exact_three_stock_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {}
            lines = []
            for name, basename in (
                ("extension", "_vllm_fa2_C.abi3.so"),
                ("device_library", "libattn_kernels_xe_2.so"),
                ("stock_library", "libattn_stock.so"),
            ):
                path = root / basename
                path.write_bytes(name.encode())
                files[name] = {"path": str(path), "sha256": WORKER.sha256_file(path)}
                lines.append(f"1000-2000 r-xp 00000000 00:00 0 {path}")
            stage = {"files": files}
            base = SimpleNamespace(sha256_file=WORKER.sha256_file)
            evidence = WORKER.mapping_evidence(base, stage, "\n".join(lines) + "\n")
            self.assertTrue(evidence["passed"])
            duplicate_dir = root / "duplicate"
            duplicate_dir.mkdir()
            duplicate = duplicate_dir / "libattn_stock.so"
            duplicate.write_bytes(b"duplicate")
            bad_maps = (
                "\n".join(lines + [f"3000-4000 r-xp 0 00:00 0 {duplicate}"]) + "\n"
            )
            with self.assertRaisesRegex(WORKER.ContractError, "mapped stock_library"):
                WORKER.mapping_evidence(base, stage, bad_maps)

    def test_supervisor_deep_mapping_validator_rejects_tampered_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {}
            lines = []
            for name, basename in (
                ("extension", "_vllm_fa2_C.abi3.so"),
                ("device_library", "libattn_kernels_xe_2.so"),
                ("stock_library", "libattn_stock.so"),
            ):
                path = root / basename
                path.write_bytes(name.encode())
                files[name] = {"path": str(path), "sha256": WORKER.sha256_file(path)}
                lines.append(f"1000-2000 r-xp 00000000 00:00 0 {path}")
            stage = {"files": files}
            mapping = WORKER.mapping_evidence(
                SimpleNamespace(sha256_file=WORKER.sha256_file),
                stage,
                "\n".join(lines) + "\n",
            )
            self.assertIs(
                SUPERVISOR.validate_mapping_payload(WORKER, mapping, stage, "mapping"),
                mapping,
            )
            mapping["selected_lines"]["stock_library"][0] += " trailing"
            with self.assertRaisesRegex(SUPERVISOR.SupervisorError, "path differs"):
                SUPERVISOR.validate_mapping_payload(WORKER, mapping, stage, "mapping")

    def test_uuid_parser_accepts_only_canonical_uuid(self):
        props = SimpleNamespace(uuid=WORKER.EXPECTED_DEVICE_UUID)
        self.assertEqual(WORKER.device_uuid_text(props), WORKER.EXPECTED_DEVICE_UUID)
        with self.assertRaisesRegex(WORKER.ContractError, "malformed"):
            WORKER.device_uuid_text(SimpleNamespace(uuid="47:00.0"))

    def test_timeout_receipt_precedes_term_and_five_second_kill_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            events = []
            groups = iter([[child], [child], [child], []])

            def killpg_fn(pid, sent_signal):
                receipts = WORKER.validate_receipt_chain(
                    chain.directory, "supervisor", contract, digest
                )
                events.append(("signal", pid, sent_signal, receipts[-1]["phase"]))

            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGKILL),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=killpg_fn,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertFalse(result["unkillable"])
            self.assertTrue(result["entry_receipt_persisted"])
            self.assertTrue(result["term_grace_receipt_persisted"])
            self.assertIs(
                SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup"),
                result,
            )
            signals = [event for event in events if event[0] == "signal"]
            self.assertEqual(signals[0][1:3], (4321, signal.SIGTERM))
            self.assertEqual(signals[0][3], "timeout-before-term")
            self.assertEqual(signals[1][1:3], (4321, signal.SIGKILL))
            self.assertEqual(signals[1][3], "term-grace-expired-before-kill")
            self.assertEqual(signals[2][1:3], (4321, signal.SIGKILL))
            self.assertEqual(signals[2][3], "final-kill-retry-before-signal")

    def test_primary_launch_receipt_failure_uses_fallback_and_enters_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            command = ["python", "worker.py"]
            original_emit = chain.emit

            def fail_primary(phase, data):
                if phase == "child-launched":
                    raise OSError("synthetic primary launch receipt failure")
                return original_emit(phase, data)

            chain.emit = fail_primary
            phase, errors, first_error = SUPERVISOR.emit_launch_boundary_nonthrowing(
                chain, command, child
            )
            self.assertEqual(phase, "child-launched-after-supervisor-error")
            self.assertIsInstance(first_error, OSError)
            self.assertEqual(
                [item["operation"] for item in errors], ["emit:child-launched"]
            )
            groups = iter([[child], [], []])
            cleanup = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "supervisor-baseexception",
                {
                    "kind": "supervisor-baseexception",
                    "exception_type": "OSError",
                },
                launch_receipt_phase=phase,
                initial_errors=errors,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertFalse(cleanup["unkillable"])
            self.assertEqual(
                cleanup["launch_receipt_phase"],
                "child-launched-after-supervisor-error",
            )
            SUPERVISOR.validate_cleanup_state(WORKER, cleanup, child, "cleanup")

    def test_both_launch_receipt_failures_still_enter_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)

            def fail_launch_receipts(phase, _data):
                if phase.startswith("child-launched"):
                    raise OSError(f"synthetic {phase} receipt failure")
                return original_emit(phase, _data)

            original_emit = chain.emit
            chain.emit = fail_launch_receipts
            phase, errors, first_error = SUPERVISOR.emit_launch_boundary_nonthrowing(
                chain, ["python", "worker.py"], child
            )
            self.assertIsNone(phase)
            self.assertIsInstance(first_error, OSError)
            self.assertEqual(
                [item["operation"] for item in errors],
                [
                    "emit:child-launched",
                    "emit:child-launched-after-supervisor-error",
                ],
            )
            groups = iter([[child], [], []])
            cleanup = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "supervisor-baseexception",
                {
                    "kind": "supervisor-baseexception",
                    "exception_type": "OSError",
                },
                launch_receipt_phase=phase,
                initial_errors=errors,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertFalse(cleanup["unkillable"])
            self.assertIsNone(cleanup["launch_receipt_phase"])
            SUPERVISOR.validate_cleanup_state(WORKER, cleanup, child, "cleanup")

    def test_double_identity_read_failure_terminates_live_fresh_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            proc = subprocess.Popen(
                ["/usr/bin/sleep", "30"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                with mock.patch.object(
                    WORKER,
                    "process_identity",
                    side_effect=RuntimeError("synthetic canonical identity failure"),
                ):
                    child, verified, identity_errors = (
                        SUPERVISOR.acquire_child_identity(WORKER, proc.pid)
                    )
                self.assertFalse(verified)
                self.assertIsNone(proc.poll())
                self.assertEqual(child["pid"], proc.pid)
                self.assertEqual(child["pgid"], proc.pid)
                self.assertEqual(child["sid"], proc.pid)
                self.assertEqual(
                    [item["operation"] for item in identity_errors],
                    [
                        "worker-process-identity-attempt-1",
                        "worker-process-identity-attempt-2",
                    ],
                )
                phase, receipt_errors, _ = (
                    SUPERVISOR.emit_unverified_identity_boundary_nonthrowing(
                        chain, ["/usr/bin/sleep", "30"], child, identity_errors
                    )
                )
                with mock.patch.object(
                    WORKER,
                    "process_identity",
                    side_effect=RuntimeError("canonical helper remains broken"),
                ):
                    cleanup = SUPERVISOR.cleanup_process_group(
                        WORKER,
                        proc,
                        child,
                        chain,
                        root,
                        0.0,
                        "supervisor-baseexception",
                        {
                            "kind": "supervisor-baseexception",
                            "exception_type": "SupervisorError",
                        },
                        launch_receipt_phase=phase,
                        initial_errors=identity_errors + receipt_errors,
                        group_fn=SUPERVISOR.supervisor_local_process_group_members,
                        identity_fn=lambda pid: (
                            SUPERVISOR.supervisor_local_process_identity(WORKER, pid)
                        ),
                    )
                self.assertFalse(cleanup["unkillable"])
                self.assertIsNotNone(proc.poll())
                self.assertTrue(cleanup["sigterm_sent"])
                SUPERVISOR.validate_cleanup_state(WORKER, cleanup, child, "cleanup")
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)

    def test_all_identity_reads_fail_emergency_cleanup_leaves_no_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "worker.stdout.log.tmp").write_bytes(b"stdout fixture\n")
            (root / "worker.stderr.log.tmp").write_bytes(b"stderr fixture\n")
            chain, _, _ = self.make_chain(root, "supervisor")
            proc = subprocess.Popen(
                ["/usr/bin/sleep", "30"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                with (
                    mock.patch.object(
                        WORKER,
                        "process_identity",
                        side_effect=RuntimeError("canonical identity unavailable"),
                    ),
                    mock.patch.object(
                        SUPERVISOR,
                        "supervisor_local_process_identity",
                        side_effect=OSError("local proc identity unavailable"),
                    ),
                ):
                    with self.assertRaises(
                        SUPERVISOR.ChildIdentityAcquisitionError
                    ) as raised:
                        SUPERVISOR.acquire_child_identity(WORKER, proc.pid)
                    state = SUPERVISOR.emergency_cleanup_unidentified_child(
                        WORKER,
                        proc,
                        chain,
                        root,
                        0.0,
                        raised.exception.errors,
                    )
                self.assertFalse(state["unkillable"])
                self.assertFalse(state["final_group_exists"])
                self.assertTrue(state["sigterm_sent"])
                self.assertIsNotNone(proc.poll())
                with self.assertRaises(ProcessLookupError):
                    os.killpg(proc.pid, 0)
                packet = root / "unidentified-child-emergency.json"
                self.assertTrue(packet.is_file())
                self.assertEqual(packet.stat().st_mode & 0o777, 0o444)
                self.assertEqual(WORKER.load_json(packet), state)
                self.assertFalse((root / "terminal.json").exists())
                self.assertEqual(
                    [item["operation"] for item in state["identity_errors"]],
                    [
                        "worker-process-identity-attempt-1",
                        "worker-process-identity-attempt-2",
                        "supervisor-local-process-identity",
                    ],
                )
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)

    def test_local_cleanup_scan_failure_falls_through_to_emergency_kill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "worker.stdout.log.tmp").write_bytes(b"")
            (root / "worker.stderr.log.tmp").write_bytes(b"")
            chain, _, _ = self.make_chain(root, "supervisor")
            proc = subprocess.Popen(
                ["/usr/bin/sleep", "30"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                with mock.patch.object(
                    WORKER,
                    "process_identity",
                    side_effect=RuntimeError("canonical helper remains broken"),
                ):
                    child, verified, identity_errors = (
                        SUPERVISOR.acquire_child_identity(WORKER, proc.pid)
                    )
                    phase, receipt_errors, _ = (
                        SUPERVISOR.emit_unverified_identity_boundary_nonthrowing(
                            chain, ["/usr/bin/sleep", "30"], child, identity_errors
                        )
                    )
                    cleanup = SUPERVISOR.cleanup_process_group(
                        WORKER,
                        proc,
                        child,
                        chain,
                        root,
                        0.0,
                        "supervisor-baseexception",
                        {
                            "kind": "supervisor-baseexception",
                            "exception_type": "SupervisorError",
                        },
                        launch_receipt_phase=phase,
                        initial_errors=identity_errors + receipt_errors,
                        group_fn=mock.Mock(
                            side_effect=OSError("local group scan unavailable")
                        ),
                        identity_fn=mock.Mock(
                            side_effect=OSError("local leader read unavailable")
                        ),
                        monotonic_fn=advancing_clock(),
                        sleep_fn=lambda _seconds: None,
                    )
                    self.assertTrue(cleanup["unkillable"])
                    self.assertIsNone(proc.poll())
                    emergency = SUPERVISOR.emergency_cleanup_unidentified_child(
                        WORKER,
                        proc,
                        chain,
                        root,
                        0.0,
                        identity_errors + cleanup["errors"],
                    )
                self.assertFalse(emergency["unkillable"])
                self.assertIsNotNone(proc.poll())
                with self.assertRaises(ProcessLookupError):
                    os.killpg(proc.pid, 0)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)

    def test_timeout_that_exits_on_term_does_not_kill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            signals = []
            child = dummy_process(4321)
            groups = iter([[child], [], []])
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda pid, sent_signal: signals.append((pid, sent_signal)),
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertEqual(result["child_returncode"], -signal.SIGTERM)
            self.assertFalse(result["sigkill_attempted"])
            self.assertEqual(signals, [(4321, signal.SIGTERM)])

    def test_cleanup_tracks_descendant_after_group_leader_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            descendant = {**child, "pid": 4322, "start_ticks": 98766}
            groups = iter([[child], [descendant], [], []])
            signals = []
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertIn((4321, signal.SIGKILL), signals)
            self.assertFalse(result["unkillable"])

    def test_external_interrupt_receipt_precedes_term(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            signals = []
            groups = iter([[child], [], []])

            def killpg_fn(pid, sent_signal):
                receipts = WORKER.validate_receipt_chain(
                    chain.directory, "supervisor", contract, digest
                )
                signals.append((pid, sent_signal, receipts[-1]["phase"]))

            abort = {
                "kind": "external-interrupt",
                "signal_number": signal.SIGTERM,
                "signal_name": "SIGTERM",
                "exception_type": "ExternalInterrupt",
                "message": "external signal SIGTERM",
            }
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "external-interrupt",
                abort,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=killpg_fn,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertEqual(result["child_returncode"], -signal.SIGTERM)
            self.assertEqual(
                signals,
                [(4321, signal.SIGTERM, "external-interrupt-before-term")],
            )

    def test_supervisor_baseexception_receipt_precedes_term(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract, digest = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            observations = []
            groups = iter([[child], [], []])

            def killpg_fn(pid, sent_signal):
                receipts = WORKER.validate_receipt_chain(
                    chain.directory, "supervisor", contract, digest
                )
                observations.append((pid, sent_signal, receipts[-1]["phase"]))

            SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "supervisor-baseexception",
                {
                    "abort": {
                        "kind": "supervisor-baseexception",
                        "exception_type": "KeyboardInterrupt",
                    }
                }["abort"],
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=killpg_fn,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertEqual(
                observations,
                [(4321, signal.SIGTERM, "supervisor-abort-before-term")],
            )

    def test_cleanup_esrch_rescans_and_records_disappearance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            groups = iter([[child], [], [], []])

            def vanished(_pid, _sent_signal):
                raise ProcessLookupError(3, "gone")

            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=vanished,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertTrue(result["sigterm_esrch_group_disappeared"])
            self.assertFalse(result["sigterm_sent"])
            self.assertFalse(result["unkillable"])
            SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup")

    def test_cleanup_preterm_disappearance_emits_no_grace_or_signal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            signals = []
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: 0),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: [],
                killpg_fn=lambda pid, sig: signals.append((pid, sig)),
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertEqual(signals, [])
            self.assertFalse(result["sigterm_attempted"])
            self.assertFalse(result["term_grace_receipt_persisted"])
            self.assertEqual(
                result["receipts_persisted"],
                ["timeout-before-term", "cleanup-complete"],
            )
            SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup")

    def test_cleanup_scan_and_receipt_races_do_not_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            scans = 0

            def group_fn(_worker, _expected):
                nonlocal scans
                scans += 1
                if scans == 1:
                    raise RuntimeError("synthetic scan race")
                return []

            original_emit = chain.emit

            def flaky_emit(phase, data):
                if phase == "timeout-before-term":
                    raise OSError("synthetic receipt race")
                return original_emit(phase, data)

            chain.emit = flaky_emit
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: 0),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=group_fn,
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            operations = {item["operation"] for item in result["errors"]}
            self.assertIn("pre-term-group-scan", operations)
            self.assertIn("emit:timeout-before-term", operations)
            self.assertIn("cleanup-complete", result["receipts_persisted"])
            SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup")

    def test_cleanup_records_unkillable_descendant_after_final_kill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            descendant = {**child, "pid": 4322, "start_ticks": 98766}
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: 0),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: [descendant],
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            self.assertTrue(result["unkillable"])
            self.assertIsNone(result["child_returncode"])
            self.assertEqual(result["leader_returncode_observed"], 0)
            self.assertEqual(result["final_process_group_snapshot"], [descendant])
            SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup")

    def test_cleanup_durable_packet_tamper_fails_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, _, _ = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            groups = iter([[child], [], []])
            result = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            packet = Path(result["durable_packet"]["path"])
            packet.chmod(0o644)
            with self.assertRaisesRegex(SUPERVISOR.SupervisorError, "changed"):
                SUPERVISOR.validate_cleanup_state(WORKER, result, child, "cleanup")

    def test_cleanup_receipt_payloads_round_trip_deep_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chain, contract_path, contract_sha = self.make_chain(root, "supervisor")
            child = dummy_process(4321)
            supervisor_process = dummy_process(1000)
            chain.identity = supervisor_process
            chain.emit(
                "supervisor-start",
                {
                    "deadline_seconds": SUPERVISOR.DEADLINE_SECONDS,
                    "term_grace_seconds": SUPERVISOR.TERM_GRACE_SECONDS,
                    "kill_grace_seconds": SUPERVISOR.KILL_GRACE_SECONDS,
                },
            )
            command = [
                str(SUPERVISOR.XPU_PYTHON),
                str(SUPERVISOR.WORKER),
                "--contract",
                str(contract_path),
            ]
            chain.emit("child-launched", {"argv": command, "child_process": child})
            groups = iter([[child], [], []])
            cleanup = SUPERVISOR.cleanup_process_group(
                WORKER,
                SimpleNamespace(pid=4321, poll=lambda: -signal.SIGTERM),
                child,
                chain,
                root,
                0.0,
                "timeout",
                None,
                group_fn=lambda _worker, _expected: next(groups, []),
                killpg_fn=lambda _pid, _signal: None,
                monotonic_fn=advancing_clock(),
                sleep_fn=lambda _seconds: None,
            )
            terminal = {
                "supervisor_process": supervisor_process,
                "child_process": child,
                "child_identity_verified": True,
                "child_identity_errors": [],
                "contract_path": str(contract_path),
                "child_returncode": cleanup["child_returncode"],
                "timed_out": True,
                "sigterm_sent": cleanup["sigterm_sent"],
                "sigkill_sent": cleanup["sigkill_sent"],
                "unkillable": cleanup["unkillable"],
                "abort": None,
                "cleanup": cleanup,
                "late_signals": [],
                "final_process_group_snapshot": cleanup["final_process_group_snapshot"],
                "passed": False,
                "classification": "gpu3-incumbent-control-timeout-terminated",
                "worker_success_validation_error": None,
                "worker_failure_validation_error": None,
                "worker_phase_validation_error": None,
            }
            chain.emit(
                "child-outcome",
                {
                    "child_process": child,
                    "child_identity_verified": True,
                    "child_identity_errors": [],
                    "returncode": terminal["child_returncode"],
                    "timed_out": True,
                    "sigterm_sent": terminal["sigterm_sent"],
                    "sigkill_sent": terminal["sigkill_sent"],
                    "unkillable": terminal["unkillable"],
                    "abort": None,
                    "cleanup": cleanup,
                    "late_signals": [],
                    "final_process_group_snapshot": terminal[
                        "final_process_group_snapshot"
                    ],
                },
            )
            chain.emit(
                "supervisor-terminal-ready",
                {
                    "passed": False,
                    "classification": terminal["classification"],
                    "child_identity_verified": True,
                    "child_identity_errors": [],
                    "success_validation_error": None,
                    "failure_validation_error": None,
                    "worker_phase_validation_error": None,
                    "abort": None,
                    "cleanup": cleanup,
                    "late_signals": [],
                },
            )
            receipts = WORKER.validate_receipt_chain(
                chain.directory, "supervisor", contract_path, contract_sha
            )
            SUPERVISOR.validate_supervisor_receipt_payloads(
                WORKER,
                receipts,
                terminal,
                {"files": {"worker": {"path": str(SUPERVISOR.WORKER)}}},
                root,
            )

    def test_pending_signal_during_finalization_enters_cleanup_once(self):
        action, late, handled = SUPERVISOR.classify_pending_signals(
            False, [signal.SIGTERM], 0
        )
        self.assertEqual((action, late, handled), (signal.SIGTERM, [], 1))

    def test_pending_signal_with_unkillable_cleanup_is_late_not_reentrant(self):
        action, late, handled = SUPERVISOR.classify_pending_signals(
            True, [signal.SIGINT, signal.SIGTERM], 0
        )
        self.assertEqual(action, None)
        self.assertEqual(late, [signal.SIGINT, signal.SIGTERM])
        self.assertEqual(handled, 2)

    def test_blocked_kernel_signals_are_consumed_once_at_both_terminal_fences(self):
        signal_set = {signal.SIGINT, signal.SIGTERM}
        handled = []
        original_handlers = {signum: signal.getsignal(signum) for signum in signal_set}
        for signum in signal_set:
            signal.signal(signum, lambda number, _frame: handled.append(number))
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signal_set)
        mask_restored = False
        try:
            os.kill(os.getpid(), signal.SIGINT)
            self.assertEqual(
                SUPERVISOR.consume_blocked_kernel_signals(signal_set),
                [signal.SIGINT],
            )
            os.kill(os.getpid(), signal.SIGTERM)
            self.assertEqual(
                SUPERVISOR.consume_blocked_kernel_signals(signal_set),
                [signal.SIGTERM],
            )
            self.assertFalse(signal.sigpending() & signal_set)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            mask_restored = True
            self.assertEqual(handled, [])
        finally:
            if not mask_restored:
                SUPERVISOR.consume_blocked_kernel_signals(signal_set)
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            for signum, original_handler in original_handlers.items():
                signal.signal(signum, original_handler)

    def test_final_fence_cleanup_records_signal_during_cleanup_as_late(self):
        pending = [signal.SIGTERM]
        action, late, handled = SUPERVISOR.classify_pending_signals(False, pending, 0)
        self.assertEqual((action, late, handled), (signal.SIGTERM, [], 1))

        # The handler is unblocked during the cleanup action and appends SIGINT.
        pending.append(signal.SIGINT)
        signal_set = {signal.SIGINT, signal.SIGTERM}
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, signal_set)
        mask_restored = False
        try:
            # A second signal races after cleanup returns but before the final
            # blocked snapshot; it must be drained into the same late inventory.
            os.kill(os.getpid(), signal.SIGTERM)
            handled = SUPERVISOR.record_post_cleanup_signals(
                signal_set, pending, handled, late
            )
            self.assertEqual(late, [signal.SIGINT, signal.SIGTERM])
            self.assertEqual(handled, 3)
            self.assertFalse(signal.sigpending() & signal_set)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
            mask_restored = True
        finally:
            if not mask_restored:
                SUPERVISOR.consume_blocked_kernel_signals(signal_set)
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    def test_process_group_snapshot_rejects_wrong_session(self):
        child = dummy_process(4321)
        escaped = {**child, "pid": 4322, "sid": 9999}
        with self.assertRaisesRegex(SUPERVISOR.SupervisorError, "escaped"):
            SUPERVISOR.validate_process_group_snapshot(
                WORKER, [escaped], child, "snapshot"
            )

    def test_worker_hash_is_checked_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "worker.py"
            path.write_text(
                "raise AssertionError('must not import')\n", encoding="utf-8"
            )
            with (
                mock.patch.object(SUPERVISOR, "WORKER", path),
                mock.patch.object(SUPERVISOR, "WORKER_SHA256", "0" * 64),
                mock.patch.object(
                    SUPERVISOR.importlib.util,
                    "spec_from_file_location",
                    side_effect=AssertionError("import attempted before SHA gate"),
                ) as construct,
            ):
                with self.assertRaisesRegex(
                    SUPERVISOR.SupervisorError, "before import"
                ):
                    SUPERVISOR.load_worker_module()
                construct.assert_not_called()

    def test_full_graph_manifest_rederives_every_stage_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / "stage"
            package = stage / "vllm_xpu_kernels"
            package.mkdir(parents=True)
            first = package / "__init__.py"
            second = package / "lib.so"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            manifest = root / "graph.sha256"
            manifest.write_text("fixture\n", encoding="utf-8")
            entries = {
                first.resolve(): WORKER.sha256_file(first),
                second.resolve(): WORKER.sha256_file(second),
            }
            base = SimpleNamespace(
                parse_sha256_manifest=lambda *_args, **_kwargs: entries
            )
            result = WORKER.stock_graph_identity(
                base,
                stage=stage,
                manifest=manifest,
                expected_manifest_sha256=WORKER.sha256_file(manifest),
            )
            self.assertEqual(result["file_count"], 2)
            (package / "extra.py").write_bytes(b"extra")
            with self.assertRaisesRegex(WORKER.ContractError, "inventory differs"):
                WORKER.stock_graph_identity(
                    base,
                    stage=stage,
                    manifest=manifest,
                    expected_manifest_sha256=WORKER.sha256_file(manifest),
                )

    def test_wait_tracks_descendant_after_group_leader_exit(self):
        child = dummy_process(4321)
        descendant = {
            **child,
            "pid": 4322,
            "start_ticks": 98766,
        }
        groups = iter([[descendant], []])
        result = SUPERVISOR.wait_until(
            SimpleNamespace(poll=lambda: 0),
            SUPERVISOR.time.monotonic() + 1,
            worker=WORKER,
            process_group=child,
            group_fn=lambda _worker, _group: next(groups),
        )
        self.assertEqual(result, 0)

    def test_unkillable_mutable_snapshot_uses_recorded_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "worker.stdout.log.tmp"
            path.write_bytes(b"before")
            snapshot = [
                {
                    "path": "worker.stdout.log.tmp",
                    "size_bytes": len(b"before"),
                    "sha256": WORKER.sha256_file(path),
                    "writable": True,
                }
            ]
            path.write_bytes(b"after")
            SUPERVISOR.validate_snapshot_entries(
                WORKER, snapshot, root, "snapshot", require_current=False
            )
            with self.assertRaisesRegex(SUPERVISOR.SupervisorError, "changed"):
                SUPERVISOR.validate_snapshot_entries(
                    WORKER, snapshot, root, "snapshot", require_current=True
                )

    def test_output_root_rejects_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            actual = root / "actual"
            actual.mkdir()
            link = root / "link"
            link.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(SUPERVISOR.SupervisorError, "canonical"):
                SUPERVISOR.validate_new_output_root(link / "result")

    def test_output_root_creation_is_dirfd_bound_and_collision_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            output = parent / "result"
            canonical_parent = SUPERVISOR.validate_new_output_root(output)
            SUPERVISOR.create_output_root(output, canonical_parent)
            self.assertTrue(output.is_dir())
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(SUPERVISOR.SupervisorError):
                SUPERVISOR.validate_new_output_root(output)

    def test_worker_failure_packet_binds_exact_child_and_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            WORKER.atomic_json(contract, {"schema": "fixture"})
            contract_sha = WORKER.sha256_file(contract)
            child = dummy_process(4321)
            failure = root / "worker-failure.json"
            payload = {
                "schema": WORKER.SCHEMA_FAILURE,
                "passed": False,
                "classification": "gpu3-incumbent-control-health-worker-failure",
                "contract_path": str(contract),
                "contract_sha256": contract_sha,
                "process": child,
                "exception_type": "RuntimeError",
                "message": "fixture",
                "phase_receipt_snapshot": [],
                "receipt_chain_validation_error": None,
            }
            WORKER.atomic_json(failure, payload)
            self.assertEqual(
                SUPERVISOR.validate_worker_failure(
                    WORKER, root, contract, contract_sha, child
                ),
                {"path": str(failure), "sha256": WORKER.sha256_file(failure)},
            )
            with self.assertRaisesRegex(
                SUPERVISOR.SupervisorError, "contract mismatch"
            ):
                SUPERVISOR.validate_worker_failure(
                    WORKER, root, contract, contract_sha, dummy_process(9999)
                )

    def test_failed_worker_partial_chain_must_be_exact_success_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract, digest = self.make_contract(root)
            chain = WORKER.ReceiptChain(
                root / "worker-phases",
                "worker",
                contract,
                digest,
                dummy_process(4321),
            )
            chain.emit("device-bound", {})
            with self.assertRaisesRegex(
                SUPERVISOR.SupervisorError, "exact success prefix"
            ):
                SUPERVISOR.validate_worker_partial_chain(
                    WORKER,
                    root,
                    contract,
                    digest,
                    dummy_process(4321),
                )

    def test_supervisor_is_torch_free_and_has_no_candidate_input(self):
        source = (
            SCRIPT_DIR / "qwen38_gpu3_incumbent_control_health_supervisor.py"
        ).read_text()
        self.assertNotIn("import torch", source)
        self.assertNotIn("candidate_manifest", source)
        self.assertIn('worker.Q64_POLICY_ENV: "0"', source)
        self.assertIn('worker.Q8_POLICY_ENV: "0"', source)


if __name__ == "__main__":
    unittest.main()

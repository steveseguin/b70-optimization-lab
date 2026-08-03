#!/usr/bin/env python3

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
MODULE_PATH = TOOLS / "validate_laguna_worker_selector_evidence.py"
SPEC = importlib.util.spec_from_file_location("worker_selector_validator", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _record(rank: int, *, pid: int | None = None, exact_prefill: bool = False) -> dict:
    selectors = (
        validator.LATENCY_EXPECTED_SELECTORS
        if exact_prefill
        else validator.EXPECTED_SELECTORS
    )
    return {
        "schema": validator.LATENCY_SCHEMA if exact_prefill else validator.SCHEMA,
        "pid": 1000 + rank if pid is None else pid,
        "pid_start_time_ticks": 2000 + rank,
        "worker_name": f"Worker_TP{rank}_EP{rank}",
        "world_size": 4,
        "ranks": {"global": rank, "local": rank, "tp": rank, "ep": rank},
        "selector_contract_sha256": (
            validator.LATENCY_SELECTOR_CONTRACT_SHA256
            if exact_prefill
            else validator.SELECTOR_CONTRACT_SHA256
        ),
        "selector_count": len(selectors),
        "selectors": dict(selectors),
    }


def _log_line(record: dict) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
    rank = record["ranks"]["global"]
    marker = (
        validator.LATENCY_MARKER
        if record["schema"] == validator.LATENCY_SCHEMA
        else validator.MARKER
    )
    return f"(Worker_TP{rank}_EP{rank}) {marker} {encoded}\n"


def _stat_line(pid: int, start_time: int) -> str:
    return f"{pid} (Worker ) name) " + " ".join(["S"] + ["1"] * 18 + [str(start_time)])


def _map_line(path: Path, metadata: os.stat_result | None = None) -> str:
    metadata = path.stat() if metadata is None else metadata
    device = f"{os.major(metadata.st_dev):x}:{os.minor(metadata.st_dev):x}"
    return f"0000-1000 r-xp 0 {device} {metadata.st_ino} {path}\n"


class WorkerSelectorEvidenceTests(unittest.TestCase):
    def test_selector_contract_hash_matches_frozen_worker_checks(self) -> None:
        self.assertEqual(
            validator.selector_contract_sha256(),
            validator.SELECTOR_CONTRACT_SHA256,
        )

    def test_valid_shuffled_records_are_sorted_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            log.write_text(
                "noise\n" + "".join(_log_line(_record(rank)) for rank in [2, 0, 3, 1])
            )

            records = validator.parse_worker_selector_log(log)

        self.assertEqual(
            [record["ranks"]["global"] for record in records], list(range(4))
        )
        self.assertTrue(
            all(
                record["selectors"] == validator.EXPECTED_SELECTORS
                for record in records
            )
        )

    def test_latency_contract_requires_exact_prefill_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            log.write_text(
                "".join(
                    _log_line(_record(rank, exact_prefill=True)) for rank in range(4)
                )
            )

            records = validator.parse_worker_selector_log(
                log, require_exact_prefill=True
            )

        self.assertTrue(
            all(
                record["selectors"]["VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS"] == "1"
                for record in records
            )
        )

    def test_latency_contract_rejects_legacy_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            log.write_text("".join(_log_line(_record(rank)) for rank in range(4)))
            with self.assertRaisesRegex(ValueError, "expected four"):
                validator.parse_worker_selector_log(log, require_exact_prefill=True)

    def test_duplicate_json_key_is_rejected(self) -> None:
        encoded = json.dumps(_record(0), sort_keys=True, separators=(",", ":"))
        duplicate = encoded[:-1] + ',"pid":1000}'
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            other = "".join(_log_line(_record(rank)) for rank in range(1, 4))
            log.write_text(f"{validator.MARKER} {duplicate}\n" + other)
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                validator.parse_worker_selector_log(log)

    def test_noncanonical_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            noncanonical = json.dumps(_record(0), sort_keys=False)
            other = "".join(_log_line(_record(rank)) for rank in range(1, 4))
            log.write_text(f"{validator.MARKER} {noncanonical}\n" + other)
            with self.assertRaisesRegex(ValueError, "not canonical"):
                validator.parse_worker_selector_log(log)

    def test_rank_pid_and_selector_drift_are_rejected(self) -> None:
        mutations = []
        duplicate_pid = _record(1, pid=1000)
        mutations.append((duplicate_pid, "PIDs are not unique"))
        wrong_rank = _record(1)
        wrong_rank["ranks"]["tp"] = 0
        mutations.append((wrong_rank, "rank identity"))
        wrong_selector = _record(1)
        wrong_selector["selectors"]["VLLM_XPU_LAGUNA_SCALE_FOLD"] = "1"
        mutations.append((wrong_selector, "frozen map"))

        for mutated, expected in mutations:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp) / "server.log"
                records = [_record(rank) for rank in range(4)]
                records[1] = mutated
                log.write_text("".join(_log_line(record) for record in records))
                with self.assertRaisesRegex(ValueError, expected):
                    validator.parse_worker_selector_log(log)

    def test_missing_extra_and_non_string_selectors_are_rejected(self) -> None:
        mutations = []
        missing = _record(0)
        missing["selectors"].pop("LAGUNA_M")
        mutations.append(missing)
        extra = _record(0)
        extra["selectors"]["HF_TOKEN"] = "secret"
        mutations.append(extra)
        non_string = _record(0)
        non_string["selectors"]["LAGUNA_M"] = 12
        mutations.append(non_string)

        for mutated in mutations:
            with self.subTest(mutated=mutated), tempfile.TemporaryDirectory() as tmp:
                log = Path(tmp) / "server.log"
                records = [mutated] + [_record(rank) for rank in range(1, 4)]
                log.write_text("".join(_log_line(record) for record in records))
                with self.assertRaisesRegex(ValueError, "frozen map"):
                    validator.parse_worker_selector_log(log)

    def test_every_frozen_selector_is_required_with_exact_string_value(self) -> None:
        for name in validator.EXPECTED_SELECTORS:
            for mutation in ("missing", "wrong"):
                with (
                    self.subTest(name=name, mutation=mutation),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    first = _record(0)
                    if mutation == "missing":
                        first["selectors"].pop(name)
                    else:
                        first["selectors"][name] = "wrong\nsecret-like-value"
                    log = Path(tmp) / "server.log"
                    records = [first] + [_record(rank) for rank in range(1, 4)]
                    log.write_text("".join(_log_line(record) for record in records))
                    with self.assertRaisesRegex(ValueError, "frozen map"):
                        validator.parse_worker_selector_log(log)

    def test_grouped_gemm_map_proof_binds_pid_and_start_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dso = root / "libgrouped_gemm_xe_2.so"
            dso.write_bytes(b"grouped-gemm-fixture")
            digest = hashlib.sha256(dso.read_bytes()).hexdigest()
            records = [_record(rank) for rank in range(4)]
            for record in records:
                proc = root / "proc" / str(record["pid"])
                proc.mkdir(parents=True)
                proc.joinpath("stat").write_text(
                    _stat_line(record["pid"], record["pid_start_time_ticks"])
                )
                proc.joinpath("maps").write_text(_map_line(dso))

            summaries = validator.verify_grouped_gemm_maps(
                records,
                proc_root=root / "proc",
                expected_dso=dso,
                expected_sha256=digest,
            )

        self.assertEqual(
            [summary["global_rank"] for summary in summaries], list(range(4))
        )
        self.assertTrue(all(summary["sha256"] == digest for summary in summaries))

    def test_grouped_gemm_map_proof_rejects_identity_and_map_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dso = root / "libgrouped_gemm_xe_2.so"
            wrong = root / "wrong" / "libgrouped_gemm_xe_2.so"
            wrong.parent.mkdir()
            dso.write_bytes(b"expected")
            wrong.write_bytes(b"wrong")
            digest = hashlib.sha256(dso.read_bytes()).hexdigest()
            records = [_record(rank) for rank in range(4)]
            for record in records:
                proc = root / "proc" / str(record["pid"])
                proc.mkdir(parents=True)
                proc.joinpath("stat").write_text(
                    _stat_line(record["pid"], record["pid_start_time_ticks"])
                )
                proc.joinpath("maps").write_text(_map_line(dso))

            bad_identity = copy.deepcopy(records)
            bad_identity[0]["pid_start_time_ticks"] += 1
            with self.assertRaisesRegex(ValueError, "start time drifted"):
                validator.verify_grouped_gemm_maps(
                    bad_identity,
                    proc_root=root / "proc",
                    expected_dso=dso,
                    expected_sha256=digest,
                )

            first_maps = root / "proc" / str(records[0]["pid"]) / "maps"
            first_maps.write_text(_map_line(wrong))
            with self.assertRaisesRegex(ValueError, "wrong grouped-GEMM"):
                validator.verify_grouped_gemm_maps(
                    records,
                    proc_root=root / "proc",
                    expected_dso=dso,
                    expected_sha256=digest,
                )

    def test_grouped_gemm_map_proof_rejects_replaced_path_inode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dso = root / "libgrouped_gemm_xe_2.so"
            replacement = root / "replacement.so"
            dso.write_bytes(b"old-mapped-inode")
            old_metadata = dso.stat()
            replacement.write_bytes(b"expected-current-file")
            replacement.replace(dso)
            digest = hashlib.sha256(dso.read_bytes()).hexdigest()
            records = [_record(rank) for rank in range(4)]
            for record in records:
                proc = root / "proc" / str(record["pid"])
                proc.mkdir(parents=True)
                proc.joinpath("stat").write_text(
                    _stat_line(record["pid"], record["pid_start_time_ticks"])
                )
                proc.joinpath("maps").write_text(_map_line(dso, old_metadata))

            with self.assertRaisesRegex(ValueError, "inode drifted"):
                validator.verify_grouped_gemm_maps(
                    records,
                    proc_root=root / "proc",
                    expected_dso=dso,
                    expected_sha256=digest,
                )

    def test_grouped_gemm_hash_stays_bound_to_open_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dso = root / "libgrouped_gemm_xe_2.so"
            replacement = root / "replacement.so"
            dso.write_bytes(b"wrong-opened-file")
            replacement.write_bytes(b"expected-path-swap")
            digest = hashlib.sha256(replacement.read_bytes()).hexdigest()
            records = [_record(rank) for rank in range(4)]
            for record in records:
                proc = root / "proc" / str(record["pid"])
                proc.mkdir(parents=True)
                proc.joinpath("stat").write_text(
                    _stat_line(record["pid"], record["pid_start_time_ticks"])
                )
                proc.joinpath("maps").write_text(_map_line(dso))

            original_sha256_fd = validator._sha256_fd

            def swap_path_then_hash(fd: int) -> str:
                replacement.replace(dso)
                return original_sha256_fd(fd)

            with mock.patch.object(
                validator, "_sha256_fd", side_effect=swap_path_then_hash
            ):
                with self.assertRaisesRegex(ValueError, "hash drifted"):
                    validator.verify_grouped_gemm_maps(
                        records,
                        proc_root=root / "proc",
                        expected_dso=dso,
                        expected_sha256=digest,
                    )

    def test_grouped_gemm_proof_rejects_final_path_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dso = root / "libgrouped_gemm_xe_2.so"
            replacement = root / "replacement.so"
            dso.write_bytes(b"expected-open-file")
            replacement.write_bytes(b"wrong-final-path")
            digest = hashlib.sha256(dso.read_bytes()).hexdigest()
            records = [_record(rank) for rank in range(4)]
            for record in records:
                proc = root / "proc" / str(record["pid"])
                proc.mkdir(parents=True)
                proc.joinpath("stat").write_text(
                    _stat_line(record["pid"], record["pid_start_time_ticks"])
                )
                proc.joinpath("maps").write_text(_map_line(dso))

            original_sha256_fd = validator._sha256_fd
            hash_calls = 0

            def replace_path_during_final_hash(fd: int) -> str:
                nonlocal hash_calls
                hash_calls += 1
                if hash_calls == 2:
                    replacement.replace(dso)
                return original_sha256_fd(fd)

            with mock.patch.object(
                validator,
                "_sha256_fd",
                side_effect=replace_path_during_final_hash,
            ):
                with self.assertRaisesRegex(ValueError, "pathname identity drifted"):
                    validator.verify_grouped_gemm_maps(
                        records,
                        proc_root=root / "proc",
                        expected_dso=dso,
                        expected_sha256=digest,
                    )

    def test_canonical_writer_is_exclusive_and_mode_600(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.jsonl"
            validator.write_canonical_jsonl(output, [_record(0)])
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertTrue(output.read_bytes().endswith(b"\n"))
            with self.assertRaises(FileExistsError):
                validator.write_canonical_jsonl(output, [_record(0)])

    def test_canonical_writer_removes_partial_file_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.jsonl"
            with mock.patch.object(validator.os, "write", side_effect=OSError("boom")):
                with self.assertRaisesRegex(OSError, "boom"):
                    validator.write_canonical_jsonl(output, [_record(0)])
            self.assertFalse(output.exists())

    def test_canonical_writer_removes_file_on_chmod_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.jsonl"
            with mock.patch.object(validator.os, "fchmod", side_effect=OSError("boom")):
                with self.assertRaisesRegex(OSError, "boom"):
                    validator.write_canonical_jsonl(output, [_record(0)])
            self.assertFalse(output.exists())

    def test_canonical_writer_cleans_up_if_fstat_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence.jsonl"
            with (
                mock.patch.object(
                    validator.os, "fstat", side_effect=OSError("fstat unavailable")
                ),
                mock.patch.object(
                    validator.os, "fchmod", side_effect=OSError("chmod failed")
                ),
            ):
                with self.assertRaisesRegex(OSError, "chmod failed"):
                    validator.write_canonical_jsonl(output, [_record(0)])
            self.assertFalse(output.exists())

    def test_paired_publication_removes_first_output_if_second_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            selector_output = Path(tmp) / "selectors.jsonl"
            map_output = Path(tmp) / "maps.jsonl"
            original = validator.write_canonical_jsonl
            calls = 0

            def fail_second(path, records):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("second publication failed")
                return original(path, records)

            with mock.patch.object(
                validator, "write_canonical_jsonl", side_effect=fail_second
            ):
                with self.assertRaisesRegex(OSError, "second publication failed"):
                    validator.write_evidence_pair(
                        selector_output,
                        [_record(0)],
                        map_output,
                        [{"global_rank": 0}],
                    )
            self.assertFalse(selector_output.exists())
            self.assertFalse(map_output.exists())


if __name__ == "__main__":
    unittest.main()

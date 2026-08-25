#!/usr/bin/env python3
"""CPU-only tests for parse-llama-bench-exact-depth.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("parse-llama-bench-exact-depth.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("parse_llama_bench_exact_depth", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
PARSER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PARSER
SPEC.loader.exec_module(PARSER)


DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
MODEL = "/models/qwen.gguf"
BINARY = "/runtime/llama-bench"


def row(depth: int, *, prefill: bool = False) -> dict[str, object]:
    n_prompt, n_gen = (2048, 0) if prefill else (0, 128)
    scale = 1000.0 if prefill else 25.0
    samples = [scale - depth / 100000, scale - depth / 100000 + 0.5]
    return {
        "build_commit": "deadbee",
        "build_number": 1,
        "backends": "SYCL",
        "model_filename": MODEL,
        "model_type": "qwen test",
        "model_size": 123,
        "model_n_params": 456,
        "n_prompt": n_prompt,
        "n_gen": n_gen,
        "n_depth": depth,
        "avg_ns": 100,
        "stddev_ns": 2,
        "avg_ts": sum(samples) / len(samples),
        "stddev_ts": 0.25,
        "samples_ns": [101, 99],
        "samples_ts": samples,
    }


def bench_rows(*, include_prefill: bool = True) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for depth in DEPTHS:
        if include_prefill:
            rows.append(row(depth, prefill=True))
        rows.append(row(depth))
    return rows


def metadata(*, graph_requested: bool = False, capture: int = 0, replay: int = 0):
    return {
        "schema": PARSER.METADATA_SCHEMA,
        "receipt_id": "qwen-test-depth-v1",
        "declared_depths": DEPTHS,
        "binary": {"path": BINARY, "sha256": "a" * 64, "commit": "deadbee"},
        "model": {
            "path": MODEL,
            "sha256": "b" * 64,
            "revision": "pinned-revision",
            "quantization": "Q4_K_M",
        },
        "argv": [BINARY, "-m", MODEL, "-p", "2048", "-n", "128", "-o", "json"],
        "env": {"GGML_SYCL_ENABLE_VMM": "1", "ZES_ENABLE_SYSMAN": "1"},
        "cell_selectors": {
            "revision": "qwen3.8-27b",
            "artifact_id": "qwen-test",
            "tp": 1,
            "mtp": 0,
            "kv": "f16",
        },
        "graph": {
            "requested": graph_requested,
            "capture": {"count": capture, "source": "stderr"},
            "replay": {"count": replay, "source": "stderr"},
        },
    }


class ReceiptTests(unittest.TestCase):
    def build(self, rows=None, meta=None):
        return PARSER.build_receipt(
            bench_rows() if rows is None else rows,
            metadata() if meta is None else meta,
            bench_path=Path("/evidence/bench.json"),
            metadata_path=Path("/evidence/meta.json"),
        )

    def test_emits_seven_cell_ready_raw_engine_points(self) -> None:
        receipt = self.build()
        self.assertEqual(receipt["status"], "passed")
        self.assertEqual(receipt["measurement"]["classification"], "raw-engine")
        self.assertFalse(receipt["measurement"]["is_http_serving_metric"])
        self.assertFalse(receipt["measurement"]["includes_quality_gate"])
        self.assertTrue(receipt["gate"]["exact_cell_ready"])
        self.assertEqual(len(receipt["cells"]), 7)
        zero = receipt["cells"][0]
        self.assertEqual(zero["active_context_tokens"], 0)
        self.assertEqual(zero["depth_evidence"]["reported_value"], 0)
        self.assertTrue(zero["depth_evidence"]["true_zero_measurement"])
        self.assertEqual(zero["decode"]["workload"], "tg128")
        self.assertEqual(zero["prefill"]["workload"], "pp2048")
        self.assertEqual(zero["selectors"]["graph_mode"], "off")
        self.assertEqual(receipt["identity"]["binary"]["sha256"], "a" * 64)
        self.assertRegex(receipt["identity"]["argv_sha256"], r"^[0-9a-f]{64}$")

    def test_prefill_is_optional_and_decode_remains_required(self) -> None:
        receipt = self.build(rows=bench_rows(include_prefill=False))
        self.assertTrue(receipt["gate"]["exact_cell_ready"])
        self.assertTrue(all(cell["prefill"] is None for cell in receipt["cells"]))

        missing = bench_rows(include_prefill=False)[1:]
        with self.assertRaisesRegex(PARSER.ContractError, "missing: 0"):
            self.build(rows=missing)

    def test_duplicate_and_undeclared_decode_rows_fail_closed(self) -> None:
        duplicate = bench_rows(include_prefill=False)
        duplicate.append(row(0))
        with self.assertRaisesRegex(PARSER.ContractError, "multiple tg128"):
            self.build(rows=duplicate)

        declared = metadata()
        declared["declared_depths"] = [0, 2048]
        with self.assertRaisesRegex(PARSER.ContractError, "undeclared n_depth"):
            self.build(rows=bench_rows(include_prefill=False), meta=declared)

    def test_missing_or_aliased_zero_depth_is_not_accepted(self) -> None:
        missing = bench_rows(include_prefill=False)
        del missing[0]["n_depth"]
        with self.assertRaisesRegex(PARSER.ContractError, "n_depth is invalid"):
            self.build(rows=missing)

        aliased = bench_rows(include_prefill=False)
        aliased[0]["n_depth"] = False
        with self.assertRaisesRegex(PARSER.ContractError, "plain integer"):
            self.build(rows=aliased)

        meta = metadata()
        meta["declared_depths"] = DEPTHS[1:]
        with self.assertRaisesRegex(PARSER.ContractError, "include true depth 0"):
            self.build(meta=meta)

    def test_graph_request_is_not_graph_on_without_positive_evidence(self) -> None:
        requested = self.build(meta=metadata(graph_requested=True))
        self.assertEqual(requested["graph"]["classification"], "requested-unverified")
        self.assertFalse(requested["gate"]["exact_cell_ready"])
        self.assertIsNone(requested["cells"][0]["selectors"]["graph_mode"])

        verified = self.build(meta=metadata(graph_requested=True, capture=1, replay=14))
        self.assertEqual(
            verified["graph"]["classification"], "verified-capture-and-replay"
        )
        self.assertTrue(verified["gate"]["exact_cell_ready"])
        self.assertEqual(verified["cells"][0]["selectors"]["graph_mode"], "on")

        with self.assertRaisesRegex(
            PARSER.ContractError, "when graph was not requested"
        ):
            self.build(meta=metadata(capture=1, replay=1))

    def test_model_and_invocation_identities_are_bound(self) -> None:
        wrong_row = bench_rows()
        wrong_row[0]["model_filename"] = "/models/other.gguf"
        with self.assertRaisesRegex(PARSER.ContractError, "model_filename"):
            self.build(rows=wrong_row)

        wrong_argv = metadata()
        wrong_argv["argv"] = [BINARY, "-m", "/models/other.gguf"]
        with self.assertRaisesRegex(PARSER.ContractError, "model.path exactly once"):
            self.build(meta=wrong_argv)

        wrong_env = metadata()
        wrong_env["env"] = {"FLAG": 1}
        with self.assertRaisesRegex(PARSER.ContractError, "must be a string"):
            self.build(meta=wrong_env)


class ModeTests(unittest.TestCase):
    def write_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        bench = root / "bench.json"
        meta = root / "meta.json"
        output = root / "receipt.json"
        bench.write_text(json.dumps(bench_rows()), encoding="utf-8")
        meta.write_text(json.dumps(metadata()), encoding="utf-8")
        return bench, meta, output

    def args(self, bench: Path, meta: Path, output: Path, **modes: bool):
        values = {"plan": False, "check": False, "create": False} | modes
        return SimpleNamespace(
            bench_json=bench,
            metadata=meta,
            output=output,
            **values,
        )

    def test_default_plan_is_inert(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            bench, meta, output = self.write_inputs(Path(value))
            result = PARSER.execute(self.args(bench, meta, output))
            self.assertEqual(result["mode"], "plan")
            self.assertEqual(result["status"], "planned")
            self.assertFalse(output.exists())

    def test_create_only_and_check_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            bench, meta, output = self.write_inputs(Path(value))
            created = PARSER.execute(self.args(bench, meta, output, create=True))
            self.assertEqual(created["status"], "created")
            original = output.read_bytes()
            checked = PARSER.execute(self.args(bench, meta, output, check=True))
            self.assertEqual(checked["status"], "passed")
            self.assertEqual(output.read_bytes(), original)
            with self.assertRaisesRegex(PARSER.ContractError, "refusing to overwrite"):
                PARSER.execute(self.args(bench, meta, output, create=True))

            output.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(PARSER.ContractError, "differs"):
                PARSER.execute(self.args(bench, meta, output, check=True))


if __name__ == "__main__":
    unittest.main()

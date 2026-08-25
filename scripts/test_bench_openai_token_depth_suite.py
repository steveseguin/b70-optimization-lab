#!/usr/bin/env python3
"""Focused CPU-only tests for bench-openai-token-depth-suite.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).with_name("bench-openai-token-depth-suite.py")
SPEC = importlib.util.spec_from_file_location("bench_openai_token_depth_suite", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
BENCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BENCH
SPEC.loader.exec_module(BENCH)


class FakeResponse:
    def __init__(self, events: list[dict[str, object] | str]) -> None:
        self.headers = {"X-Request-Id": "response-request-id"}
        self._lines = []
        for event in events:
            body = event if isinstance(event, str) else json.dumps(event)
            self._lines.append(f"data: {body}\n".encode())

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def __iter__(self):
        return iter(self._lines)


def fixture_payload(
    *, token_count: int = 2048, declared_hash: str | None = None
) -> dict[str, object]:
    token_ids = [7] * token_count
    provenance = {
        "builder_sha256": "a" * 64,
        "source_tokenizer_sha256": "b" * 64,
    }
    return {
        "schema": BENCH.SCHEMA,
        "fixture_id": "fixture-test-v1",
        "provenance": provenance,
        "provenance_sha256": BENCH.sha256_bytes(BENCH.canonical_bytes(provenance)),
        "cases": [
            {
                "id": "depth-0",
                "depth": 0,
                "prompt_token_ids": [],
                "prompt_token_ids_sha256": BENCH.token_ids_sha256([]),
            },
            {
                "id": f"depth-{token_count}",
                "depth": token_count,
                "prompt_token_ids": token_ids,
                "prompt_token_ids_sha256": (
                    declared_hash or BENCH.token_ids_sha256(token_ids)
                ),
            },
        ],
    }


def write_fixture(root: Path, payload: dict[str, object] | None = None) -> Path:
    path = root / "fixture.json"
    path.write_text(json.dumps(payload or fixture_payload()), encoding="utf-8")
    return path


def vllm_events(prompt_ids: list[int]) -> list[dict[str, object] | str]:
    events: list[dict[str, object] | str] = []
    for index in range(BENCH.MAX_TOKENS):
        choice: dict[str, object] = {
            "index": 0,
            "text": "x",
            "token_ids": [1000 + index],
            "finish_reason": None,
        }
        if index == 0:
            choice["prompt_token_ids"] = prompt_ids
        events.append({"id": "cmpl-vllm", "choices": [choice]})
    events.append(
        {
            "id": "cmpl-vllm",
            "choices": [
                {"index": 0, "text": "", "token_ids": [], "finish_reason": "length"}
            ],
            "usage": {
                "prompt_tokens": len(prompt_ids),
                "completion_tokens": BENCH.MAX_TOKENS,
                "total_tokens": len(prompt_ids) + BENCH.MAX_TOKENS,
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }
    )
    events.append("[DONE]")
    return events


def llama_events(prompt_count: int) -> list[dict[str, object] | str]:
    events: list[dict[str, object] | str] = []
    for index in range(BENCH.MAX_TOKENS):
        events.append(
            {
                "id": "cmpl-llama",
                "choices": [{"index": 0, "text": "y", "finish_reason": None}],
                "__verbose": {
                    "tokens": [2000 + index],
                    "stop": False,
                    "truncated": False,
                },
            }
        )
    events.append(
        {
            "id": "cmpl-llama",
            "choices": [{"index": 0, "text": "", "finish_reason": "length"}],
            "usage": {
                "prompt_tokens": prompt_count,
                "completion_tokens": BENCH.MAX_TOKENS,
                "total_tokens": prompt_count + BENCH.MAX_TOKENS,
                "prompt_tokens_details": {"cached_tokens": 0},
            },
            "timings": {"cache_n": 0},
            "__verbose": {
                "tokens": [],
                "stop": True,
                "stop_type": "limit",
                "truncated": False,
                "context_shifted": False,
            },
        }
    )
    events.append("[DONE]")
    return events


def clock_values() -> list[float]:
    # start, 128 token-bearing events, end
    return [0.0] + [0.1 * (index + 1) for index in range(BENCH.MAX_TOKENS)] + [13.0]


class FixtureTests(unittest.TestCase):
    def test_loads_exact_flat_case_and_carries_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = write_fixture(Path(value))
            fixture = BENCH.load_fixture(path, 2048)
        self.assertEqual(fixture.fixture_id, "fixture-test-v1")
        self.assertEqual(fixture.selected.depth, 2048)
        self.assertEqual(len(fixture.selected.prompt_token_ids), 2048)
        self.assertEqual(fixture.provenance["builder_sha256"], "a" * 64)
        self.assertRegex(fixture.provenance_sha256, r"^[0-9a-f]{64}$")

    def test_rejects_wrong_prompt_hash(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            path = write_fixture(Path(value), fixture_payload(declared_hash="0" * 64))
            with self.assertRaisesRegex(ValueError, "prompt token hash mismatch"):
                BENCH.load_fixture(path, 2048)

    def test_rejects_nested_or_boolean_prompt_tokens(self) -> None:
        for malformed in ([[7]], [True]):
            payload = fixture_payload()
            case = payload["cases"][-1]
            case["prompt_token_ids"] = malformed + [7] * (2048 - len(malformed))
            case["prompt_token_ids_sha256"] = BENCH.token_ids_sha256(
                case["prompt_token_ids"]
            )
            with (
                self.subTest(malformed=malformed),
                tempfile.TemporaryDirectory() as value,
            ):
                path = write_fixture(Path(value), payload)
                with self.assertRaisesRegex(ValueError, "non-negative integer"):
                    BENCH.load_fixture(path, 2048)


class RequestTests(unittest.TestCase):
    def test_request_freezes_token_completion_contract(self) -> None:
        prompt = [3] * 2048
        payload = BENCH.request_payload(
            model="qwen", prompt_token_ids=prompt, adapter="vllm"
        )
        self.assertIs(payload["prompt"], prompt)
        self.assertEqual(payload["max_tokens"], 128)
        self.assertTrue(payload["ignore_eos"])
        self.assertTrue(payload["return_token_ids"])
        self.assertFalse(payload["add_special_tokens"])
        self.assertIsNone(payload["truncate_prompt_tokens"])
        self.assertNotIn("messages", payload)
        self.assertNotIn("chat_template_kwargs", payload)

    def test_llama_request_disables_prompt_cache(self) -> None:
        payload = BENCH.request_payload(
            model="qwen", prompt_token_ids=[3] * 2048, adapter="llama-server"
        )
        self.assertFalse(payload["cache_prompt"])
        self.assertTrue(payload["return_tokens"])
        self.assertTrue(payload["verbose"])

    def test_auto_request_does_not_send_llama_only_fields_to_vllm(self) -> None:
        payload = BENCH.request_payload(
            model="qwen", prompt_token_ids=[3] * 2048, adapter="auto"
        )
        self.assertNotIn("cache_prompt", payload)
        self.assertNotIn("return_tokens", payload)
        self.assertNotIn("verbose", payload)


class ResponseTests(unittest.TestCase):
    def load(self, root: Path) -> BENCH.Fixture:
        return BENCH.load_fixture(write_fixture(root), 2048)

    def run_stream(
        self,
        events: list[dict[str, object] | str],
        payload: dict[str, object],
        adapter: str = "auto",
    ) -> dict[str, object]:
        values = iter(clock_values())
        with (
            mock.patch.object(
                BENCH.urllib.request, "urlopen", return_value=FakeResponse(events)
            ),
            mock.patch.object(
                BENCH.time, "perf_counter", side_effect=lambda: next(values)
            ),
            mock.patch.object(BENCH.time, "time", return_value=1000.0),
        ):
            return BENCH.post_stream(
                base_url="http://127.0.0.1:18080",
                payload=payload,
                timeout=30,
                requested_adapter=adapter,
                request_id="depth-test",
            )

    def test_vllm_adapter_passes_exact_depth_gate(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            fixture = self.load(Path(value))
            payload = BENCH.request_payload(
                model="qwen",
                prompt_token_ids=fixture.selected.prompt_token_ids,
                adapter="vllm",
            )
            row = self.run_stream(
                vllm_events(fixture.selected.prompt_token_ids), payload
            )
            args = SimpleNamespace(
                base_url="http://127.0.0.1:18080",
                model="qwen",
                response_adapter="auto",
                context_capacity=2176,
            )
            receipt = BENCH.build_receipt(
                args=args, fixture=fixture, payload=payload, row=row
            )
        self.assertEqual(row["adapter"], "vllm")
        self.assertEqual(len(row["token_ids"]), 128)
        self.assertTrue(receipt["gate"]["passed"])
        self.assertEqual(receipt["metric_window"]["timestamped_events"], 100)
        self.assertEqual(receipt["metric_window"]["inter_token_intervals"], 99)
        self.assertEqual(receipt["run_identity"]["active_context_tokens"], 2048)
        self.assertTrue(receipt["context_semantics"]["fills_exact_active_context_axis"])
        self.assertAlmostEqual(
            receipt["metric_window"]["conventional_99_interval_tok_s"], 10.0
        )
        self.assertEqual(
            receipt["fixture"]["prompt_token_ids_sha256"],
            fixture.selected.prompt_token_ids_sha256,
        )

    def test_llama_server_verbose_adapter_passes(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            fixture = self.load(Path(value))
            payload = BENCH.request_payload(
                model="qwen",
                prompt_token_ids=fixture.selected.prompt_token_ids,
                adapter="llama-server",
            )
            row = self.run_stream(
                llama_events(fixture.selected.depth), payload, "llama-server"
            )
            checks, timing = BENCH.validate_response(
                fixture, payload, row, context_capacity=2176
            )
        self.assertEqual(row["adapter"], "llama-server")
        self.assertTrue(all(checks.values()))
        self.assertEqual(timing["inter_token_intervals"], 99)
        self.assertFalse(row["verbose_truncated"])
        self.assertEqual(row["verbose_stop_type"], "limit")

    def test_truncated_llama_response_fails_gate(self) -> None:
        events = llama_events(2048)
        final = events[-2]
        final["__verbose"]["truncated"] = True
        with tempfile.TemporaryDirectory() as value:
            fixture = self.load(Path(value))
            payload = BENCH.request_payload(
                model="qwen",
                prompt_token_ids=fixture.selected.prompt_token_ids,
                adapter="llama-server",
            )
            row = self.run_stream(events, payload, "llama-server")
            checks, _ = BENCH.validate_response(
                fixture, payload, row, context_capacity=2176
            )
        self.assertFalse(checks["llama_prompt_not_truncated"])


class CliTests(unittest.TestCase):
    def test_execute_rejects_insufficient_capacity_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            fixture = BENCH.load_fixture(write_fixture(Path(value)), 2048)
            args = SimpleNamespace(
                base_url="http://127.0.0.1:18080",
                model="qwen",
                response_adapter="vllm",
                context_capacity=2175,
                timeout=30,
                out=None,
            )
            with mock.patch.object(
                BENCH.urllib.request,
                "urlopen",
                side_effect=AssertionError("network called"),
            ) as urlopen:
                with self.assertRaisesRegex(ValueError, r"depth \+ 128"):
                    BENCH.execute(args, fixture)
                self.assertFalse(urlopen.called)

    def test_default_check_and_plan_never_contact_network(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            fixture = write_fixture(root)
            output = root / "must-not-exist.json"
            with mock.patch.object(
                BENCH.urllib.request,
                "urlopen",
                side_effect=AssertionError("network called"),
            ) as urlopen:
                for argv in (
                    [],
                    ["--check", "--fixture", str(fixture), "--depth", "2048"],
                    ["--plan", "--fixture", str(fixture), "--depth", "2048"],
                ):
                    with (
                        self.subTest(argv=argv),
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        self.assertEqual(BENCH.main(argv), 0)
                self.assertFalse(urlopen.called)
            self.assertFalse(output.exists())

    def test_out_rejected_without_execute(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            fixture = write_fixture(root)
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                BENCH.main(
                    [
                        "--plan",
                        "--fixture",
                        str(fixture),
                        "--depth",
                        "2048",
                        "--out",
                        str(root / "receipt.json"),
                    ]
                )


if __name__ == "__main__":
    unittest.main()

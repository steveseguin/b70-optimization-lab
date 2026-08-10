#!/usr/bin/env python3
"""Offline tests for the synchronized once-only four-service capture."""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("capture-embedded-mtp-four-service-realistic.py")
SUITE = SCRIPT.parents[3] / "repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
SPEC = importlib.util.spec_from_file_location("four_service_capture", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)


class FourServiceCaptureTests(unittest.TestCase):
    def test_three_synchronized_waves_are_once_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            prepared_path = root / "prepared.json"
            journal_path = root / "journal.jsonl"
            output_path = root / "capture.json"
            config = {
                "schema": capture.CONFIG_SCHEMA,
                "services": [
                    {
                        "service_index": index,
                        "gpu_index": index,
                        "base_url": f"http://127.0.0.1:{21000 + index}",
                        "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{index}",
                    }
                    for index in range(4)
                ],
            }
            config_path.write_text(json.dumps(config))
            _, prompts = capture.core.load_suite(SUITE)
            prepared = {
                "schema": f"{capture.SCHEMA}-prepared",
                "suite_sha256": capture.core.SUITE_SHA256,
                "suite_path": str(SUITE.resolve()),
                "suite": {"suite_id": "fixed"},
                "config_path": str(config_path.resolve()),
                "config_sha256": capture.core.sha256_bytes(config_path.read_bytes()),
                "service_count": 4,
                "wave_count": 3,
                "generation_requests": 0,
                "rows": [
                    {
                        "prompt_index": index,
                        "prompt_id": prompts[index]["id"],
                        "prompt_sha256": capture.core.sha256_bytes(
                            prompts[index]["prompt"].encode()
                        ),
                        "rendered_prompt": f"rendered-{index}",
                        "rendered_prompt_sha256": capture.core.sha256_bytes(
                            f"rendered-{index}".encode()
                        ),
                        "wave_index": index // 4,
                        "service_index": index % 4,
                        "gpu_index": index % 4,
                        "base_url": f"http://127.0.0.1:{21000 + index % 4}",
                        "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{index % 4}",
                    }
                    for index in range(12)
                ],
            }
            prepared_path.write_text(json.dumps(prepared))
            calls: list[tuple[str, str]] = []

            def fake_stream(
                base_url: str,
                model: str,
                prompt: str,
                request_id: str,
                timeout: int,
            ) -> dict[str, object]:
                del timeout
                started = time.time()
                calls.append((request_id, prompt))
                time.sleep(0.05)
                return {
                    "request_id": request_id,
                    "request_started_epoch_s": started,
                    "elapsed_s": 0.05,
                    "cached_tokens": 0,
                    "stream_token_id_count": 100,
                    "completion_tokens": 100,
                    "stream_complete_positions": list(range(100)),
                    "base_url_seen": base_url,
                    "model_seen": model,
                }

            args = argparse.Namespace(
                config=config_path,
                prepared=prepared_path,
                journal=journal_path,
                output=output_path,
                timeout=10,
            )
            with mock.patch.object(capture.core, "stream_once", side_effect=fake_stream):
                self.assertEqual(capture.run(args), 0)
            result = json.loads(output_path.read_text())
            journal = [json.loads(line) for line in journal_path.read_text().splitlines()]
            self.assertEqual(len(calls), 12)
            self.assertEqual(len({call[0] for call in calls}), 12)
            self.assertEqual([row["prompt_index"] for row in result["rows"]], list(range(12)))
            self.assertEqual(
                [wave["service_indices"] for wave in result["waves"]],
                [[0, 1, 2, 3]] * 3,
            )
            self.assertTrue(
                all(wave["four_way_overlap_s"] > 0 for wave in result["waves"])
            )
            self.assertEqual(
                [entry["event"] for entry in journal].count("request_started"), 12
            )
            self.assertEqual(
                [entry["event"] for entry in journal].count("request_completed"), 12
            )
            self.assertNotIn("request_failed", [entry["event"] for entry in journal])
            self.assertTrue(
                result["stream_position_evidence"]["all_generated_positions_present"]
            )

    def test_invalid_partition_fails_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            prepared_path = root / "prepared.json"
            config = {
                "schema": capture.CONFIG_SCHEMA,
                "services": [
                    {
                        "service_index": index,
                        "gpu_index": index,
                        "base_url": f"http://127.0.0.1:{22000 + index}",
                        "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{index}",
                    }
                    for index in range(4)
                ],
            }
            config_path.write_text(json.dumps(config))
            _, prompts = capture.core.load_suite(SUITE)
            prepared_path.write_text(
                json.dumps(
                    {
                        "schema": f"{capture.SCHEMA}-prepared",
                        "suite_sha256": capture.core.SUITE_SHA256,
                        "suite_path": str(SUITE.resolve()),
                        "config_path": str(config_path.resolve()),
                        "config_sha256": capture.core.sha256_bytes(config_path.read_bytes()),
                        "service_count": 4,
                        "wave_count": 3,
                        "generation_requests": 0,
                        "rows": [
                            {
                                "prompt_index": index,
                                "prompt_id": prompts[index]["id"],
                                "prompt_sha256": capture.core.sha256_bytes(
                                    prompts[index]["prompt"].encode()
                                ),
                                "rendered_prompt": f"rendered-{index}",
                                "rendered_prompt_sha256": capture.core.sha256_bytes(
                                    f"rendered-{index}".encode()
                                ),
                                "wave_index": index // 4,
                                "service_index": (index + 1) % 4,
                                "gpu_index": index % 4,
                                "base_url": f"http://127.0.0.1:{22000 + index % 4}",
                                "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{index % 4}",
                            }
                            for index in range(12)
                        ],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "partition"):
                capture.validate_prepared(prepared_path, config_path)


if __name__ == "__main__":
    unittest.main()

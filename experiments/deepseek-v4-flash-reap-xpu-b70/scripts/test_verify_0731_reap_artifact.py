#!/usr/bin/env python3

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("verify-0731-reap-artifact.py")
SPEC = importlib.util.spec_from_file_location("verify_0731_reap_artifact", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VerifierTests(unittest.TestCase):
    def test_safe_relative_paths(self):
        self.assertTrue(MODULE.safe_relative("model-00001-of-00048.safetensors"))
        for value in ("", "/absolute", "../escape", "a/../../escape", "a\\b"):
            self.assertFalse(MODULE.safe_relative(value))

    def test_full_receipt_requires_complete_pinned_sidecars(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / "evidence"
            run = evidence / "20260826T000000Z"
            run.mkdir(parents=True)
            summary = {
                "format": "b70-pinned-hf-post-download-validation-v1",
                "status": "pass",
                "completed_utc": "2026-08-26T00:00:00+00:00",
                "plan": {
                    "targets": [
                        {
                            "id": "deepseek-v4-flash-0731-reap",
                            "revision": MODULE.REVISION,
                            "tree_sha256": MODULE.TREE_SHA256,
                            "root": "/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP",
                            "repo_id": "0xSero/DeepSeek-V4-Flash-0731-REAP",
                            "file_count": 80,
                            "total_bytes": 107818438413,
                            "shard_count": 48,
                            "shard_bytes": 107808354264,
                            "tensor_count": 45821,
                            "index_total_size": 107803320952,
                        }
                    ]
                },
            }
            (run / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            hash_rows = [
                {"file": f"file-{index}", "status": "pass"}
                for index in range(MODULE.EXPECTED["files"])
            ]
            expected_files = {row["file"] for row in hash_rows}
            header_rows = [
                {"file": f"shard-{index}", "status": "pass"}
                for index in range(MODULE.EXPECTED["shards"])
            ]
            expected_shards = {row["file"] for row in header_rows}
            dry_rows = [{"file": f"file-{index}", "size": "-"} for index in range(80)]
            (run / "deepseek-v4-flash-0731-reap-hashes.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in hash_rows), encoding="utf-8"
            )
            (run / "deepseek-v4-flash-0731-reap-headers.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in header_rows), encoding="utf-8"
            )
            (run / "deepseek-v4-flash-0731-reap-dry-run.stdout.json").write_text(
                json.dumps(dry_rows),
                encoding="utf-8",
            )
            original = MODULE.EVIDENCE_ROOT
            MODULE.EVIDENCE_ROOT = evidence
            try:
                MODULE.validate_full_receipt(
                    run / "summary.json",
                    Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP"),
                    expected_files,
                    expected_shards,
                )
                hash_rows[0]["file"] = "wrong-file"
                (run / "deepseek-v4-flash-0731-reap-hashes.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in hash_rows), encoding="utf-8"
                )
                with self.assertRaises(MODULE.VerificationError):
                    MODULE.validate_full_receipt(
                        run / "summary.json",
                        Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP"),
                        expected_files,
                        expected_shards,
                    )
                hash_rows[0]["file"] = "file-0"
                (run / "deepseek-v4-flash-0731-reap-hashes.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in hash_rows), encoding="utf-8"
                )
                header_rows[0]["file"] = "wrong-shard"
                (run / "deepseek-v4-flash-0731-reap-headers.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in header_rows), encoding="utf-8"
                )
                with self.assertRaises(MODULE.VerificationError):
                    MODULE.validate_full_receipt(
                        run / "summary.json",
                        Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP"),
                        expected_files,
                        expected_shards,
                    )
                header_rows[0]["file"] = "shard-0"
                (run / "deepseek-v4-flash-0731-reap-headers.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in header_rows), encoding="utf-8"
                )
                dry_rows[0]["file"] = "wrong-file"
                (run / "deepseek-v4-flash-0731-reap-dry-run.stdout.json").write_text(
                    json.dumps(dry_rows), encoding="utf-8"
                )
                with self.assertRaises(MODULE.VerificationError):
                    MODULE.validate_full_receipt(
                        run / "summary.json",
                        Path("/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-REAP"),
                        expected_files,
                        expected_shards,
                    )
            finally:
                MODULE.EVIDENCE_ROOT = original

    def test_receipt_outside_evidence_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "summary.json"
            path.write_text('{"status":"pass"}', encoding="utf-8")
            with self.assertRaises(MODULE.VerificationError):
                MODULE.validate_full_receipt(path, Path("/model"), set(), set())


if __name__ == "__main__":
    unittest.main()

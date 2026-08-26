#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("validate-20260826-pinned-hf-downloads.py")
SPEC = importlib.util.spec_from_file_location("pinned_download_validator", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def safetensors_file(path: Path, tensors: dict[str, bytes]) -> None:
    offset = 0
    header = {}
    payload = b""
    for name, value in tensors.items():
        header[name] = {"dtype": "U8", "shape": [len(value)], "data_offsets": [offset, offset + len(value)]}
        payload += value
        offset += len(value)
    raw = json.dumps(header, separators=(",", ":")).encode()
    padding = (8 - len(raw) % 8) % 8
    raw += b" " * padding
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + payload)


class ValidatorTests(unittest.TestCase):
    def test_default_is_inert_plan(self):
        with mock.patch.object(MODULE, "reject_live_downloads") as reject:
            self.assertEqual(MODULE.main([]), 0)
        reject.assert_not_called()

    def test_incomplete_file_blocks_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            partial = root / ".cache/huggingface/download/x.incomplete"
            partial.parent.mkdir(parents=True)
            partial.touch()
            original = MODULE.TARGETS
            MODULE.TARGETS = ({"repo_id": "example/model", "root": root},)
            try:
                with self.assertRaises(MODULE.ValidationError):
                    MODULE.reject_live_downloads(root / "empty-proc")
            finally:
                MODULE.TARGETS = original

    def test_tokenless_environment(self):
        MODULE.os.environ["HF_TOKEN"] = "never-log-this"
        env = MODULE.tokenless_env()
        self.assertNotIn("HF_TOKEN", env)
        self.assertEqual(env["HF_HUB_DISABLE_IMPLICIT_TOKEN"], "1")
        MODULE.os.environ.pop("HF_TOKEN")

    def test_detects_matching_hf_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary) / "123"
            proc.mkdir()
            target = MODULE.TARGETS[0]
            (proc / "cmdline").write_bytes(
                b"/usr/bin/hf\0download\0" + target["repo_id"].encode() + b"\0"
            )
            self.assertEqual(MODULE.active_downloads(Path(temporary)), ["123"])

    def test_global_download_gate_still_detects_unselected_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary) / "123"
            proc.mkdir()
            qwen, deepseek = MODULE.TARGETS
            (proc / "cmdline").write_bytes(
                b"/usr/bin/hf\0download\0" + qwen["repo_id"].encode() + b"\0"
            )
            self.assertEqual(MODULE.active_downloads(Path(temporary), (deepseek,)), [])
            with self.assertRaises(MODULE.ValidationError):
                MODULE.reject_live_downloads(Path(temporary))

    def test_single_target_plan_contains_only_selection(self):
        with mock.patch("builtins.print") as output:
            self.assertEqual(MODULE.main(["--target", MODULE.TARGETS[1]["id"]]), 0)
        plan = json.loads(output.call_args.args[0])
        self.assertEqual([target["id"] for target in plan["targets"]], [MODULE.TARGETS[1]["id"]])

    def test_strict_json_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.load_json(path)

    def test_header_closure_and_gap_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            good = Path(temporary) / "good.safetensors"
            safetensors_file(good, {"a": b"ab", "b": b"cd"})
            self.assertEqual(set(MODULE.read_safetensors_header(good)), {"a", "b"})

            bad = Path(temporary) / "bad.safetensors"
            header = {"a": {"dtype": "U8", "shape": [1], "data_offsets": [1, 2]}}
            raw = json.dumps(header).encode()
            bad.write_bytes(struct.pack("<Q", len(raw)) + raw + b"xx")
            with self.assertRaises(MODULE.ValidationError):
                MODULE.read_safetensors_header(bad)

    def test_digest_matches_lfs_and_git_blob_conventions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value"
            path.write_bytes(b"abc")
            sha, blob = MODULE.digest_file(path, sha256=True, git_blob=True)
            self.assertEqual(sha, hashlib.sha256(b"abc").hexdigest())
            self.assertEqual(blob, hashlib.sha1(b"blob 3\0abc").hexdigest())


if __name__ == "__main__":
    unittest.main()

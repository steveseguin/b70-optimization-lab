#!/usr/bin/env python3
"""Regression checks for the fail-closed current-main image preflight."""

from __future__ import annotations

import unittest
from pathlib import Path


LANE_DIR = Path(__file__).resolve().parents[1]
DOCKERFILE = LANE_DIR / "docker" / "Dockerfile.absolute-current-main"
PREFLIGHT = LANE_DIR / "docker" / "absolute-current-main-preflight.py"
BUILDER = (
    LANE_DIR
    / "scripts"
    / "build-20260823-qwen38-absolute-current-main-images.sh"
)


class AbsoluteCurrentMainImagePreflightTest(unittest.TestCase):
    def test_dockerfile_executes_hash_pinned_script_without_heredoc(self) -> None:
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("COPY absolute-current-main-preflight.py", text)
        self.assertIn('sha256sum /tmp/absolute-current-main-preflight.py', text)
        self.assertIn(
            "/opt/venv/bin/python /tmp/absolute-current-main-preflight.py", text
        )
        self.assertNotIn("python - <<", text)
        self.assertIn("test -s /opt/neural-download/import-receipt.json", text)

    def test_builder_preserves_and_requires_preflight_receipt(self) -> None:
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn('preflight_script="$lane_dir/docker/', text)
        self.assertIn('preflight_script_sha256=$(sha256sum "$preflight_script"', text)
        self.assertIn(
            '--build-arg "PREFLIGHT_SCRIPT_SHA256=$preflight_script_sha256"', text
        )
        self.assertIn(
            "test -s /opt/neural-download/import-receipt.json; cat ", text
        )
        self.assertIn('cp -- "$preflight_script" "$archive_dir/"', text)
        self.assertIn(
            'schema: "neural-download-absolute-current-main-build-v3"', text
        )

    def test_preflight_writes_receipt_only_after_checks(self) -> None:
        text = PREFLIGHT.read_text(encoding="utf-8")
        receipt_write = text.index(
            'Path("/opt/neural-download/import-receipt.json").write_text'
        )
        for required_check in (
            'importlib.import_module("vllm")',
            'importlib.import_module(module)',
            "required_schemas = [",
            'sha256(rust_extension) != os.environ["RUST_EXTENSION_EXPECTED"]',
        ):
            self.assertLess(text.index(required_check), receipt_write)


if __name__ == "__main__":
    unittest.main()

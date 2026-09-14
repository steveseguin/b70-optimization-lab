#!/usr/bin/env python3
"""CPU-only admission boundary tests; no process/device discovery or recovery."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('compiler_v2', Path(__file__).with_name('prepare-compiler-runtime-v2.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def require(value, message):
    if not value:
        raise RuntimeError(message)


class OfflineAdmission(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ltx-offline-admission-')
        self.root = Path(self.temporary.name)
        self.receipt = self.root / 'model-verification.json'
        self.receipt.write_text(json.dumps({'status': 'passed'}))
        self.fault = self.root / 'FAULT.json'
        self.fault.write_text(json.dumps({'reason': 'recorded kernel incident'}))
        self.original_fault = self.fault.read_bytes()
        self.common = SimpleNamespace(
            safe_path=lambda root, name: root / name,
            sha=lambda path: hashlib.sha256(path.read_bytes()).hexdigest(),
            MODEL_VERIFICATION_SHA256=hashlib.sha256(self.receipt.read_bytes()).hexdigest(),
            require=require,
            verify_model_receipt=lambda: self.fail('Offline preparation called runtime admission'))
        self.root_patch = patch.object(builder, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def test_valid_provenance_can_be_prepared_with_fault_preserved(self):
        result = builder.verify_model_receipt_offline(self.common)
        self.assertTrue(result['fault_latch_present_at_preparation'])
        self.assertIn('not attempted', result['runtime_admission'])
        self.assertEqual(self.fault.read_bytes(), self.original_fault)
        self.assertEqual(result['fault_latch_sha256_at_preparation'], self.common.sha(self.fault))

    def test_fault_does_not_excuse_changed_model_receipt(self):
        self.receipt.write_text(json.dumps({'status': 'passed', 'modified': True}))
        with self.assertRaisesRegex(RuntimeError, 'receipt changed'):
            builder.verify_model_receipt_offline(self.common)
        self.assertEqual(self.fault.read_bytes(), self.original_fault)

    def test_matching_receipt_hash_still_requires_passed_status(self):
        self.receipt.write_text(json.dumps({'status': 'failed'}))
        self.common.MODEL_VERIFICATION_SHA256 = self.common.sha(self.receipt)
        with self.assertRaisesRegex(RuntimeError, 'gate not passed'):
            builder.verify_model_receipt_offline(self.common)
        self.assertEqual(self.fault.read_bytes(), self.original_fault)


if __name__ == '__main__':
    unittest.main()

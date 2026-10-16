"""Synthetic CPU fixtures only; never read the real model or native runtime."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import test_verify_qwen38_flash_next_fp8_tree as fixtures

SPEC = importlib.util.spec_from_file_location(
    'a367_payload', Path(__file__).with_name('verify-flash-next-a367-launch-payload.py'))
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class LaunchPayload(unittest.TestCase):
    def run_fixture(self, change=None):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root, contract = fixtures.write_fixture(base)
            tree = root / '.cache/huggingface/trees' / (contract.revision + '.json')
            files = json.loads(tree.read_text())['files']
            hf = base / 'hf.json'
            hf.write_text(json.dumps(dict(sha=contract.revision, siblings=[
                dict(rfilename=n, size=f['size'], blobId=f['blob_id'],
                     **({'lfs': {'sha256': f['lfs_sha256']}} if f['lfs_sha256'] else {}))
                for n, f in files.items()])))
            hf_sha = AUDIT.digest(hf)
            output = base / 'receipt.json'
            if change:
                change(root, hf, output)
            spec = types.SimpleNamespace(name='synthetic_verifier', loader=mock.Mock())
            with contextlib.ExitStack() as stack:
                for name, value in dict(REPO=base, MODEL=root, HF=hf, HF_SHA=hf_sha).items():
                    stack.enter_context(mock.patch.object(AUDIT, name, value))
                stack.enter_context(mock.patch.object(fixtures.MODULE, 'PINNED', contract))
                stack.enter_context(mock.patch.object(AUDIT.importlib.util, 'spec_from_file_location', return_value=spec))
                stack.enter_context(mock.patch.object(AUDIT.importlib.util, 'module_from_spec', return_value=fixtures.MODULE))
                stack.enter_context(mock.patch.object(sys, 'argv', ['audit', '--receipt', str(output)]))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                rc = AUDIT.main()
            return rc, json.loads(output.read_text())

    def test_complete_receipt_and_all_sha256(self):
        rc, r = self.run_fixture()
        self.assertEqual(rc, 0)
        self.assertTrue(r['passed'] and r['all_files_sha256_verified'])
        self.assertEqual(len(r['files']), 3)
        self.assertTrue(all(len(f['sha256']) == 64 for f in r['files']))
        self.assertGreaterEqual(r['verified_unix'], r['started_unix'])

    def test_same_size_payload_corruption(self):
        rc, r = self.run_fixture(lambda root, *_: (root / 'model-00001-of-00001.safetensors').write_bytes(b'same-size-corrupt'))
        self.assertEqual(rc, 1)
        self.assertEqual(r['mismatches'], ['model-00001-of-00001.safetensors'])
        self.assertFalse(r['all_files_sha256_verified'])

    def test_extra_file_is_hashed_and_rejected(self):
        rc, r = self.run_fixture(lambda root, *_: (root / 'extra').write_bytes(b'extra'))
        self.assertEqual(rc, 1)
        self.assertEqual(r['extra'], ['extra'])
        self.assertIn('extra', {f['path'] for f in r['files']})

    def test_independent_manifest_tampering_precedes_bulk_read(self):
        with mock.patch.object(AUDIT, 'file_hashes') as read:
            rc, r = self.run_fixture(lambda root, hf, _: hf.write_text('{}'))
        self.assertEqual(rc, 1)
        read.assert_not_called()
        self.assertIn('publisher manifest changed', r['error'])

    def test_receipt_cannot_be_overwritten(self):
        with self.assertRaises(SystemExit):
            self.run_fixture(lambda root, hf, output: output.write_text('{}'))

    def test_ordinary_file_has_standard_git_blob_and_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plain.txt'
            path.write_bytes(b'abc')
            sha, blob, size, stable = AUDIT.file_hashes(path)
            self.assertEqual(sha, hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(blob, fixtures.git_blob(b'abc'))
            self.assertEqual(size, 3)
            self.assertTrue(stable)


if __name__ == '__main__':
    unittest.main()

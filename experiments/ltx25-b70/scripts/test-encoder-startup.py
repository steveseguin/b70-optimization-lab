#!/usr/bin/env python3
"""CPU-only rejection gates; no ComfyUI import or device operation."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, mock_open

import encoder_runtime_common as common

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('encoder_launcher', SCRIPTS / 'serve-encoder.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ltx-startup-cpu-')
        self.root = Path(self.temp.name)
        self.patcher = patch.object(common, 'ROOT', self.root)
        self.patcher.start()
        self.packet = self.root / 'prepared-encoder-test'
        self.packet.mkdir()
        self.manifest = {'schema': 'ltx.encoder-runtime-packet.v2', 'source_commit': common.PIN,
                         'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                         'status': 'prepared-inactive-not-deployed', 'files': {},
                         'extension_sha256s': {}, 'startup_tools': {}}
        for name in common.EXTENSIONS:
            p = self.packet / 'source/scripts' / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('# fixture ' + name + '\n')
            self.manifest['extension_sha256s'][name] = common.sha(p)
        for node, name in common.NODES.items():
            p = self.packet / 'source/custom_nodes' / node / '__init__.py'
            p.parent.mkdir(parents=True)
            p.write_bytes((self.packet / 'source/scripts' / name).read_bytes())
        for p in self.packet.rglob('*'):
            if p.is_file():
                self.manifest['files'][str(p.relative_to(self.packet))] = common.sha(p)
        (self.packet / 'STATUS.txt').write_text('INACTIVE\n')
        self.save_manifest()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def save_manifest(self):
        p = self.packet / 'manifest.json'
        p.write_text(json.dumps(self.manifest))
        self.digest = common.sha(p)

    def test_packet_exact_hashes_pass(self):
        self.assertEqual(common.verify_packet(self.packet, self.digest), self.manifest)

    def test_manifest_and_source_tampering_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'manifest changed'):
            common.verify_packet(self.packet, '0' * 64)
        (self.packet / 'source/scripts/resident_node.py').write_text('# changed\n')
        with self.assertRaisesRegex(RuntimeError, 'Packet file changed'):
            common.verify_packet(self.packet, self.digest)

    def test_extra_file_and_symlink_fail(self):
        extra = self.packet / 'unexpected.py'
        extra.write_text('# extra\n')
        with self.assertRaisesRegex(RuntimeError, 'Uninventoried'):
            common.verify_packet(self.packet, self.digest)
        extra.unlink()
        extra.symlink_to(self.packet / 'STATUS.txt')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            common.verify_packet(self.packet, self.digest)

    def test_traversal_manifest_path_fails(self):
        self.manifest['files']['../escape'] = '0' * 64
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            common.verify_packet(self.packet, self.digest)

    def test_custom_node_digest_must_equal_imported_helper(self):
        name = 'source/custom_nodes/ltx_speed_lab/__init__.py'
        p = self.packet / name
        p.write_text('# a different but inventoried module\n')
        self.manifest['files'][name] = common.sha(p)
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, 'Custom node copy differs'):
            common.verify_packet(self.packet, self.digest)

    def test_check_only_does_not_touch_locks_or_create_run(self):
        run = self.root / 'encoder-server-test'
        with patch.object(launcher, 'prepare_start', return_value=(self.manifest, run)), \
             patch.object(launcher.fcntl, 'flock', side_effect=AssertionError('locks touched')), \
             contextlib.redirect_stdout(io.StringIO()):
            launcher.launch(self.packet, self.digest, run.name, check_only=True)
        self.assertFalse(run.exists())

    def test_ownership_failure_precedes_torch_import_and_run_creation(self):
        run = self.root / 'encoder-server-test'
        import builtins
        real_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name == 'torch' or name.startswith('comfy'):
                raise AssertionError('Device runtime imported before ownership was established')
            return real_import(name, *args, **kwargs)
        with patch.object(launcher, 'prepare_start', return_value=(self.manifest, run)), \
             patch.object(launcher.fcntl, 'flock', side_effect=BlockingIOError('owned')), \
             patch('builtins.open', mock_open()), patch('builtins.__import__', guarded_import):
            with self.assertRaises(BlockingIOError):
                launcher.launch(self.packet, self.digest, run.name)
        self.assertFalse(run.exists())

    def test_receipt_creation_refuses_overwrite(self):
        target = self.root / 'receipt.json'
        launcher.write_json(target, {'original': True})
        before = target.read_bytes()
        with self.assertRaises(FileExistsError):
            launcher.write_json(target, {'replacement': True})
        self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
                      'source_sha256s': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                          [Path(__file__), SCRIPTS / 'serve-encoder.py', SCRIPTS / 'encoder_runtime_common.py']},
                      'scope': 'CPU rejection tests only; no GPU or server launch'}, indent=2))
    raise SystemExit(not result.wasSuccessful())

"""Regression checks for the worker import failure; no devices or model calls."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import import_check

class Imports(unittest.TestCase):
    def test_real_worker_closed_environment(self):
        row = import_check.launch('B')
        self.assertTrue(row['passed'])
        self.assertEqual(row['runtime_modules'], ['pipeline','suite','storage'])
        self.assertTrue(any(p.endswith('packet71b-depth2-engine/storage.py') for p in row['files']))
        self.assertFalse(any(p.endswith('chain-registration.json') for p in row['files']))

    def test_deferred_missing_storage_is_not_swallowed(self):
        failure = subprocess.CompletedProcess([], 1, '', 'FileNotFoundError: missing runtime dependency')
        with patch.object(import_check.subprocess, 'run', return_value=failure):
            with self.assertRaisesRegex(RuntimeError, 'missing runtime dependency'):
                import_check.launch('B')

    def test_original_failure_before_device_contact(self):
        old = import_check.HERE.parent.with_name('packet71-depth2-engine')
        code = 'import sys;sys.path.insert(0,'+repr(str(old))+');import suite'
        result = subprocess.run(['/usr/bin/python3','-B','-c',code], stdin=subprocess.DEVNULL,
                                capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('chain-registration.json',result.stderr)
        self.assertIn('FileNotFoundError',result.stderr)

    def test_chain_storage_cannot_be_admitted(self):
        sys.path.insert(0,str(import_check.HERE.parent))
        try:
            import storage
            with self.assertRaisesRegex(RuntimeError,'screen-only'):
                storage.precheck()
        finally:sys.path.pop(0)

if __name__ == '__main__':unittest.main()

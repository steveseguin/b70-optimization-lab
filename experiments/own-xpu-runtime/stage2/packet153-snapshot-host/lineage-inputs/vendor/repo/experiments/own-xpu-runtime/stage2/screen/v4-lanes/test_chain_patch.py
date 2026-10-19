"""Apply the template only in scratch and test early drain versus report success."""
import ast
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import types
import unittest
from unittest.mock import patch

import common as C
import make_chain_patch as recipe
from test_lane_admission import Files


class ChainPatchTests(Files):
    def setUp(self):
        super().setUp()
        self.scratch = self.root / 'future-packet'
        self.scratch.mkdir()
        originals = recipe.sources()
        for name, text in originals.items():
            (self.scratch / name).write_text(text)
        retained = (C.HERE / 'chain-window-drain.patch').read_text()
        self.assertEqual(retained, recipe.render())
        subprocess.run(['patch', '--batch', '-p1'], cwd=self.scratch,
                       input=retained, text=True, capture_output=True, check=True)
        for name, text in originals.items():
            actual = (self.scratch / name).read_text()
            self.assertEqual(actual, recipe.transform(name, text))
            compile(actual, name, 'exec')
        self.adapter = C.module('future_chain_adapter', self.scratch / 'window_adapter.py')
        tree = ast.parse((self.scratch / 'window.py').read_text())
        watch = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Watch')
        self.globals = dict(require=C.require, live_owner_pids=lambda watch: [],
                            Path=Path, B=self.root, save=C.save)
        exec(compile(ast.Module(body=[watch], type_ignores=[]), '<patched Watch>', 'exec'), self.globals)
        self.drain_root = self.root / 'drain'
        self.drain_root.mkdir()
        self.admission = self.adapter.WindowAdmission('K2', self.root / 'admission.json',
            root=self.root/'leases', proc=self.proc, now=self.clock.now,
            topology=lambda lane: {}, drain_root=self.drain_root)

    def start(self, *, exited=True):
        self.admission.__enter__()
        self.addCleanup(self.admission.__exit__, None, None, None)
        self.pid(); self.fd()
        self.admission.register(101)
        if exited:
            shutil.rmtree(self.proc/'101')
        watch = self.globals['Watch'].__new__(self.globals['Watch'])
        watch.admission = self.admission
        watch.postflight = lambda: None
        return watch

    def test_k2_report_failure_leaves_drain_true_and_no_lease_or_latch(self):
        watch = self.start()
        watch.finish_devices()
        self.assertTrue(C.read(self.drain_root/'teardown-state.json')['drained'])
        self.assertFalse((self.root/'leases/active-lane-A.json').exists())
        with (self.drain_root/'teardown.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # The dispatcher/validator fails after owners/postflight completed.
        error = ValueError('selection must name exactly route/recurrence/hc')
        watch.latch(error)
        row = dict(window='K2', passed=False, error=str(error))
        C.save(self.root/'window.json', row)
        with self.assertRaisesRegex(ValueError, 'original window did not pass'):
            self.adapter.bind_receipt(self.root/'window.json', self.admission)
        self.assertFalse(C.read(self.root/'admission.json')['passed'])
        self.assertTrue(C.read(self.drain_root/'teardown-state.json')['drained'])
        self.assertFalse((self.root/'FAULT.json').exists())
        with self.assertRaisesRegex(ValueError, 'launch after terminal drain'):
            watch.mark_launched(102)

    def test_successful_receipt_binds_after_early_release_without_double_completion(self):
        watch = self.start()
        watch.finish_devices()
        C.save(self.root/'window.json', dict(window='K2', passed=True,
            launched_pids=[101], boot_id=self.admission.lease.record['boot_id']))
        self.adapter.bind_receipt(self.root/'window.json', self.admission)
        self.assertTrue(self.adapter.verify_receipt(C.read(self.root/'window.json'))['passed'])

    def test_live_owner_keeps_record_undrained(self):
        watch = self.start(exited=False)
        with self.assertRaisesRegex(ValueError, 'device owners still live'):
            watch.finish_devices()
        self.assertFalse(C.read(self.drain_root/'teardown-state.json')['drained'])
        self.assertTrue((self.root/'leases/active-lane-A.json').exists())

    def test_postflight_failure_keeps_record_undrained(self):
        watch = self.start()
        def fail(): raise ValueError('postflight fault')
        watch.postflight = fail
        with self.assertRaisesRegex(ValueError, 'postflight fault'):
            watch.finish_devices()
        self.assertFalse(C.read(self.drain_root/'teardown-state.json')['drained'])
        self.assertTrue((self.root/'leases/active-lane-A.json').exists())

    def test_hook_precedes_fixture_receipt_hashes_and_k2_postprocessor(self):
        tree = ast.parse((self.scratch/'window.py').read_text())
        fixture = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='run_fixtures')
        text = ast.get_source_segment((self.scratch/'window.py').read_text(), fixture)
        self.assertLess(text.index('watch.finish_devices()'), text.index('for entry,child in zip(entries,children):'))
        self.assertIn("record['receipts']=run_fixtures(a,out,native_env,watch)",
                      (self.scratch/'window.py').read_text())


if __name__ == '__main__': unittest.main()

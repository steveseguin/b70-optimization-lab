"""CPU-only calibration threshold plumbing and boundary regressions."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import calibration as c
import screen
from test_overlay_cpu import guard


class LoadingGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for p in (patch.dict(guard.os.environ, {
                'B70_SCREEN1B': '1', 'B70_SCREEN1B_STATE_DIR': tmp.name,
                c.LOADING_GUARD_ENV: '90000000000'}),
                patch.object(guard, '_cancelled', False),
                patch.object(guard, '_loading', False)):
            p.start()
            self.addCleanup(p.stop)

    def check(self, pressure, growth=0, total=124_179_509_248):
        with patch.object(guard, 'memory', return_value={
                'MemTotal': total, 'MemAvailable': total-pressure}):
            return guard.check_admission(growth)

    def test_attempt3_pressure_now_admitted(self):
        self.check(80_005_660_672, 2048)
        self.assertFalse((self.root/'STOP').exists())

    def test_exact_90gb_and_below_old_available_floor_admitted(self):
        row = self.check(90_000_000_000-2048, 2048)
        self.assertLess(row['MemAvailable'], 32*c.GIB)
        self.assertEqual(row['pressure_limit_bytes'], c.HOST_LIMIT)
        self.assertEqual(row['available_floor_bytes'], 124_179_509_248-c.HOST_LIMIT)

    def test_projected_growth_over_90gb_refused_with_receipts(self):
        with self.assertRaisesRegex(guard.LoadCancelled, '90 GB pressure'):
            self.check(89_999_997_952, 2049)
        rows = [json.loads(line) for p in self.root.glob('loader-*.jsonl')
                for line in p.read_text().splitlines()]
        refusal = next(r for r in rows if r['event']=='allocation_refused')
        self.assertEqual(refusal['pressure_limit_bytes'],90_000_000_000)
        self.assertEqual(refusal['projected_pressure_bytes'],90_000_000_001)
        self.assertTrue(refusal['calibrate_load'])
        with self.assertRaisesRegex(guard.LoadCancelled,'first stop:.*90 GB pressure'):
            guard.check_cancel()

    def test_explicit_lower_threshold_is_used(self):
        with patch.dict(guard.os.environ,{c.LOADING_GUARD_ENV:'89000000000'}):
            self.check(89_000_000_000)
            with self.assertRaisesRegex(guard.LoadCancelled,'89 GB pressure'):
                self.check(89_000_000_001)

    def test_invalid_overlay_threshold_refused(self):
        for value in ('0','-1','90000000001','NaN'):
            with self.subTest(value=value), patch.dict(guard.os.environ,{c.LOADING_GUARD_ENV:value}):
                with self.assertRaises(ValueError): self.check(70_000_000_000)

    def test_normal_modes_do_not_receive_override(self):
        for mode in ('mtp0','mtp1','mtp3'):
            cmd=screen.launch(SimpleNamespace(mode=mode,port=19988),self.root)
            self.assertIsNone(c.loading_guard_bytes(cmd))

    def test_explicit_launch_value_and_calibration_receipt(self):
        cmd=screen.launch(SimpleNamespace(mode='calibrate-load',port=19988,
                                         loading_ram_guard_gb=89),self.root)
        self.assertEqual(c.loading_guard_bytes(cmd),89_000_000_000)
        with patch.object(c,'identity',return_value={'fixture':True}):
            screen.write_calibration(self.root,cmd,False,False,None,'fixture')
        receipt=json.loads((self.root/'calibration-load.json').read_text())
        self.assertEqual(receipt['loading_ram_guard_bytes'],89_000_000_000)
        self.assertFalse(receipt['verdict']['passed'])

    def test_cli_rejects_wrong_mode_and_invalid_values_before_operations(self):
        for mode, value in (('mtp1','90'),('mtp0','90'),('mtp3','90'),
                            ('calibrate-load','0'),('calibrate-load','91'),
                            ('calibrate-load','nan')):
            with self.subTest(mode=mode,value=value), \
                 patch.object(screen.sys,'argv',['screen.py','run','--mode',mode,
                              '--loading-ram-guard-gb',value,'--dry-run']), \
                 patch.object(screen,'overlay_check') as verify, \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): screen.main()
                verify.assert_not_called()


if __name__ == '__main__': unittest.main()

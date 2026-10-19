import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import memory_plan as M
import queue_runner as Q
import suite_driver as D
import views as V

class AsyncPolicy(unittest.TestCase):
    def test_every_full_window_uses_same_measured_bound(self):
        for w in ('KD','W2m','WS','WS128x','WS128','WSCREEN'):
            p=M.window_plan(w)
            self.assertEqual(p['host_required_available_bytes'],98990252032)
            self.assertEqual(p['host_reserve_bytes'],8*1024**3)
            self.assertEqual(p['host_categories']['gpuactive_shadow_bound'],4*1024**3)
            self.assertEqual(p['async_device_staging_bytes'],1179648)
            self.assertEqual(sum(p['host_categories'].values())+M.HOST_RESERVE,p['host_required_available_bytes'])
    def test_tampered_budget_rejected(self):
        for delta in (-1,1):
            p=M.window_plan('WSCREEN');p['host_required_available_bytes']+=delta
            with self.assertRaisesRegex(ValueError,'sealed capacity policy'):M.admit({'MemAvailable':10**15},p)
    def test_observations_cannot_shrink_policy(self):
        self.assertEqual(M.window_plan('WSCREEN'),M.window_plan('WSCREEN',{'peak_shadow_bytes':0}))
    def test_missing_smoke_refuses_bracket(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d,patch.object(Q,'ROOT',Path(d)):
            with self.assertRaises(FileNotFoundError):Q.verify_smoke()
    def test_smoke_and_bracket_dimensions(self):
        self.assertEqual(V.bracket('smoke'),[('S0','resident')])
        self.assertEqual([v for _,v in V.bracket('resident')],['mapped','resident','mapped','resident','mapped'])
        self.assertEqual(V.digest('mapped'),V.digest('resident'))
    def test_streamed_cannot_enter_async_native(self):
        from types import SimpleNamespace
        with self.assertRaisesRegex(ValueError,'zero-copy'):
            D.native_command(SimpleNamespace(view='resident',window='WSCREEN',miss_mode='streamed'),D.oracle_inputs(),Path('/unused'))
    def test_recorded_library_not_empty(self):
        lib=json.loads((Q.P/'library-path.json').read_text())['LD_LIBRARY_PATH']
        self.assertIn('/opt/intel/oneapi/compiler/2026.0/lib',lib)
        for cmd in Q.commands(Path('/unused'),0,'review',lib,'smoke').values():
            self.assertIn('LD_LIBRARY_PATH='+lib,cmd)
if __name__=='__main__':unittest.main()

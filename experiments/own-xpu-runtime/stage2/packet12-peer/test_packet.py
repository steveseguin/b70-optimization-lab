import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import device_window as window
from receipt import SIZES, summarize
from project import calculate

def fixture(peer=True):
    cases = []
    for mode in (['peer', 'host-bounce'] if peer else ['host-bounce']):
        for n in SIZES:
            for direction in ('A->B', 'B->A'):
                cases.append(dict(kind='copy', mode=mode, bytes=n, direction=direction, exact=True,
                                  samples=[dict(wall_ns=10000, events=[[1, 1001]]*(2 if mode == 'host-bounce' else 1)) for _ in range(20)]))
        cases.append(dict(kind='exchange', mode=mode, bytes=10240, rounds=60, exact=True,
                          samples=[dict(wall_ns=6000000, events=[[1, 1001]]*(300 if mode == 'host-bounce' else 180)) for _ in range(5)]))
    return dict(schema='own-runtime.peer.native.v1', passed=True, error='', identity='CPU fixture only',
                access_ab=peer, access_ba=peer, cases=cases,
                teardown=dict(safe_to_exit=True, idle_marker_complete=True, status='complete', in_flight=0, live_bytes=0))

class ReceiptTests(unittest.TestCase):
    def test_projection_is_reproducible_and_unmeasured(self):
        saved = json.loads((Path(__file__).parent/'projection.json').read_text())
        self.assertEqual(saved, calculate())
        self.assertFalse(saved['measured'])
        self.assertEqual(saved['checkpoint_layers'], 48)
        self.assertAlmostEqual(saved['sequential_ms'], 60.4231825)
        chosen = next(r for r in saved['scenarios'] if r['parallel_fraction_assumed'] == .8
                      and r['exchanges'] == 60 and r['round_us_assumed'] == 61.8)
        self.assertAlmostEqual(chosen['exchange_ms'], 3.708)
        self.assertGreater(chosen['gain'], 1)
        self.assertLess(chosen['gain'], 2)

    def test_coverage_and_units(self):
        r = summarize(fixture())
        self.assertEqual(len(r['rows']), 18)
        self.assertEqual(r['rows'][0]['payload_wall_GBps'], 1.024)
        self.assertEqual(r['rows'][8]['measured_60_round_wall_ms'], 6)
        self.assertEqual(r['rows'][8]['mean_per_round_us'], 100)

    def test_missing_duplicate_inexact(self):
        for mutate in (lambda n: n['cases'].pop(), lambda n: n['cases'].append(n['cases'][0]),
                       lambda n: n['cases'][0].update(exact=False), lambda n: n['teardown'].update(live_bytes=1),
                       lambda n: n.update(passed=False), lambda n: n['cases'][0]['samples'].pop(),
                       lambda n: n['cases'][0]['samples'][0]['events'].pop()):
            n = fixture(); mutate(n)
            with self.assertRaises(ValueError): summarize(n)

    def test_optional_event_timing(self):
        n = fixture(False)
        for sample in n['cases'][0]['samples']: sample['events'][0] = [0, 0]
        r = summarize(n)['rows'][0]
        self.assertIsNone(r['payload_event_GBps'])
        self.assertEqual(r['samples_without_event_timing'], 20)
        self.assertEqual(r['payload_wall_GBps'], 1.024)

    def test_nonfinite_wall(self):
        for bad in (0, -1, float('nan'), float('inf')):
            n = fixture(); n['cases'][0]['samples'][0]['wall_ns'] = bad
            with self.assertRaises(ValueError): summarize(n)

    def test_directional_access(self):
        n = fixture(False); n['access_ab'] = True
        self.assertEqual(summarize(n)['selected'], 'host-bounce')

class WindowTests(unittest.TestCase):
    def simulate(self, fault=None, native=None, live=False, pre_error=False, deadline=False):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent/'build') as tmp:
            root = Path(tmp); (root/'build').mkdir(); binary = root/'binary'; binary.write_text('never executed')
            out = root/'build/run'; calls = []; ticks = [0]
            class Child:
                pid, returncode = 4321, 0
                running = live
                def poll(self): return None if self.running else self.returncode
                def send_signal(self, sig): calls.append(('signal', sig)); self.running = False
            child = Child()
            def launch(*args, **kwargs):
                calls.append(('launch', args))
                (out/'native.json').write_text(json.dumps(native if native is not None else fixture()))
                return child
            def journal(cursor=None):
                if pre_error: raise RuntimeError('no journal')
                if cursor and fault == 'lost': raise RuntimeError('journal lost')
                return ((fault or '') if cursor else 'old history', 'cursor')
            def monotonic():
                ticks[0] += 121 if deadline else .01
                return ticks[0]
            with patch.object(window, 'HERE', root), patch.object(window, 'journal', journal), \
                 patch.object(window.subprocess, 'Popen', launch), patch.object(window.time, 'sleep'), \
                 patch.object(window.time, 'monotonic', monotonic), patch.object(window.signal, 'signal'):
                if pre_error:
                    with self.assertRaises(RuntimeError): window.run_window(binary, [2, 3], out, 120, {})
                    self.assertEqual(calls, [])
                    return
                code = window.run_window(binary, [2, 3], out, 120, {})
                record = json.loads((out/'window.json').read_text())
                result = (code, record, copy.deepcopy(calls), (root/'build/FAULT.json').exists())
                if result[3]:
                    with self.assertRaises(RuntimeError): window.run_window(binary, [2, 3], root/'build/second', 120, {})
                return result

    def test_success(self):
        code, record, calls, latch = self.simulate()
        self.assertEqual(code, 0); self.assertTrue(record['passed']); self.assertFalse(latch)
        self.assertEqual(len(calls), 1)

    def test_fault_latch_and_one_signal(self):
        code, record, calls, latch = self.simulate(fault='xe: Fault response', live=True)
        self.assertEqual(code, 1); self.assertFalse(record['passed']); self.assertTrue(latch)
        self.assertEqual([x[0] for x in calls], ['launch', 'signal'])
        self.assertTrue(record['fault_lines'])

    def test_post_exit_fault(self):
        self.assertEqual(self.simulate(fault='engine reset')[0], 1)

    def test_lost_journal(self):
        self.assertTrue(self.simulate(fault='lost', live=True)[3])

    def test_preflight_refuses_launch(self):
        self.simulate(pre_error=True)

    def test_timeout(self):
        code, record, calls, latch = self.simulate(deadline=True, live=True)
        self.assertEqual(code, 1); self.assertTrue(latch)
        self.assertEqual(record['stop_reason'], 'window deadline')
        self.assertEqual(len(calls), 2)

    def test_exactness_and_teardown_failure(self):
        for change in ('exact', 'teardown'):
            n = fixture()
            if change == 'exact': n['cases'][0]['exact'] = False
            else: n['teardown']['safe_to_exit'] = False
            self.assertTrue(self.simulate(native=n)[3])

    def test_specific_fault_signatures(self):
        self.assertIsNone(window.FAULT.search('configuration changed'))
        self.assertIsNotNone(window.FAULT.search('CAT error'))

if __name__ == '__main__': unittest.main()

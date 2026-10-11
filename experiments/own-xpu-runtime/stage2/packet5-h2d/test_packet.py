import copy
import unittest
import jsonschema
from plan import chunks, make_plan
from receipt import summary, validate_receipt


def fixture(peer=False):
    plan = make_plan()
    devices = ['LevelZero:3:B70:uuid=cpu-test-a'] + (['LevelZero:2:B70:uuid=cpu-test-b'] if peer else [])
    teardown = [dict(schema='own-xpu-runtime.teardown.v1', backend=d, safe_to_exit=True,
        status='complete', exit_code=0, idle_marker_complete=True, live_bytes=0, in_flight=0,
        error='', sequence=['quiesce', 'drain', 'graphs-released', 'idle-marker-complete',
                           'events-released', 'queue-released', 'context-released']) for d in devices]
    r = dict(schema='own-runtime.h2d.native.v1', completed=True, error='', devices=devices,
             teardown=teardown, census=[],
             cases=[], overlap=[])
    peak = plan['requested_peak']
    for i, device in enumerate(devices):
        totals = ({'device': peak['card_a_device_bytes'], 'host-pinned': peak['card_a_pinned_bytes'], 'host-shadow': peak['card_a_pageable_bytes']} if i == 0 else
                  {'device': peak['optional_card_b_device_bytes'], 'host-pinned': peak['optional_card_b_pinned_bytes'], 'host-shadow': 0})
        r['census'].append(dict(schema='own-xpu-runtime.census.v1', totals=totals,
            allocations=[dict(bytes=n, memory=m, live=True) for m,n in totals.items() if n], unmeasured_driver_shadow_bytes=None))
    for c in plan['cases']:
        modes = ['H2D-pinned', 'H2D-pageable', 'D2H-pinned', 'D2H-pageable', 'D2D'] + (['host-bounce-A-B'] if peer else [])
        for section, names in [('cases', modes), ('overlap', ['copy-only', 'compute-only', 'serial', 'concurrent'])]:
            for mode in names:
                ev = []
                if mode != 'compute-only':
                    offset = 100
                    for n in c['chunks']:
                        kind = 'H2D' if section == 'overlap' else mode.split('-')[0]
                        if mode == 'host-bounce-A-B': kind = 'D2H-A'
                        ev.append(dict(device=devices[0], kind=kind, start_ns=offset, end_ns=offset+n))
                        offset += n
                    if mode == 'host-bounce-A-B':
                        for n in c['chunks']:
                            ev.append(dict(device=devices[1], kind='H2D-B', start_ns=1, end_ns=1+n))
                if section == 'overlap' and mode != 'copy-only':
                    start = c['bytes']+100 if mode == 'serial' else 100
                    ev.append(dict(device=devices[0], kind='GEMV', start_ns=start, end_ns=start+1000))
                wall = 10000 if mode == 'serial' else 5000
                r[section].append(dict(label=c['label'], bytes=c['bytes'], mode=mode, verified=True,
                    samples=[dict(wall_ns=wall, host_bounce_memcpy_ns=30 if mode == 'host-bounce-A-B' else 0,
                                  events=copy.deepcopy(ev)) for _ in range(20)]))
    return summary(r, plan)


class PlanTests(unittest.TestCase):
    def test_census_triplets(self):
        p = make_plan(); a, b = p['expert_grids']
        self.assertEqual([a['triplet_bytes'], b['triplet_bytes']], [1971200, 2329600])
        self.assertEqual([len(a['layers']), b['layers']], [47, [2]])
        self.assertEqual([v['bytes'] for v in a['parts']], [524800, 524800, 921600])
        self.assertEqual([v['bytes'] for v in b['parts']], [704000, 704000, 921600])
        self.assertEqual(p['active_expert_bytes_per_token'], 949760000)
    def test_top10_not_full_model(self):
        self.assertEqual([c['bytes'] for c in make_plan()['cases']], [1971200,19712000,2329600,23296000,67108864,268435456])
    def test_chunk_bound(self):
        self.assertEqual(chunks(256*2**20), [128*2**20]*2)
        for bad in (0, -1, 256*2**20+1, True, 1.5):
            with self.assertRaises(ValueError): chunks(bad)
    def test_no_rate_in_plan(self):
        self.assertFalse(make_plan()['measured'])
        self.assertIsNone(make_plan()['requested_peak']['driver_shadow_bytes'])

class ReceiptTests(unittest.TestCase):
    def test_one_card(self): self.assertTrue(validate_receipt(fixture()))
    def test_bounce(self):
        r = fixture(True); self.assertTrue(validate_receipt(r))
        b = next(row for row in r['cases'] if row['mode'] == 'host-bounce-A-B')
        self.assertEqual(b['link_bytes_per_repetition'], 2*b['bytes'])
        self.assertEqual(b['median_event_payload_GBps'], .5)
    def test_overlap_math(self):
        r = fixture(); s = r['overlap_summary'][0]
        self.assertEqual(s['overlap_ratio'], 2)
        self.assertEqual(s['median_event_overlap_fraction'], 1)
    def test_stream_floor_math(self):
        r = fixture(); f = r['streaming_arithmetic']['pinned']
        self.assertAlmostEqual(f['all_miss_transfer_seconds_per_token'], 48*5000/1e9)
    def test_bad_receipts(self):
        mutations = [
            lambda r: r.update(measured=False),
            lambda r: r.update(completed=False),
            lambda r: r['cases'].pop(),
            lambda r: r['cases'][0]['samples'].pop(),
            lambda r: r['cases'][0].update(verified=False),
            lambda r: r['cases'][0].update(bytes=1),
            lambda r: r['cases'][0].update(median_wall_GBps=9999),
            lambda r: r['cases'][0]['samples'][0].update(wall_ns=float('nan')),
            lambda r: r['cases'][0]['samples'][0]['events'][0].update(end_ns=0),
            lambda r: r['cases'][0]['samples'][0]['events'][0].update(kind='GEMV'),
            lambda r: r['cases'][0]['samples'][0]['events'][0].update(device='wrong'),
            lambda r: r['census'][0]['totals'].update(device=1),
            lambda r: r['teardown'][0].update(live_bytes=1),
            lambda r: r['teardown'][0].update(safe_to_exit=False),
            lambda r: r['teardown'][0]['sequence'].reverse(),
            lambda r: r['overlap_summary'][0].update(overlap_ratio=99),
            lambda r: r['plan'].update(census_sha256='wrong'),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                r = fixture(); mutate(r)
                with self.assertRaises((ValueError, KeyError, jsonschema.ValidationError)): validate_receipt(r)

class WindowTests(unittest.TestCase):
    def test_fault_signatures(self):
        from device_window import FAULT
        for line in ('Fault response', 'Engine memory CAT error', 'engine reset',
                     'device coredump', 'GuC lockup', 'timed out GPU job'):
            self.assertIsNotNone(FAULT.search(line))
        self.assertIsNone(FAULT.search('network hang timeout; routine log'))

    def test_new_journal_boundary(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from device_window import packet2
        with patch.object(packet2.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='', stdout='clean\n-- cursor: next\n')) as run:
            text, cursor = packet2.journal('previous')
            self.assertEqual((text, cursor), ('clean\n', 'next'))
            self.assertIn('--after-cursor', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['timeout'], 2)
        with patch.object(packet2.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr='denied', stdout='')):
            with self.assertRaises(RuntimeError): packet2.journal()

if __name__ == '__main__': unittest.main()

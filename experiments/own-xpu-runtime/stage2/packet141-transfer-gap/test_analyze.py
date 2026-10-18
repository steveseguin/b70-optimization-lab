"""Synthetic timing/receipt tests only; none of these values are measurements."""
import copy
import json
from pathlib import Path
import resource
import tempfile
import unittest
from unittest.mock import patch
import analyze as A

P = Path(__file__).resolve().parent
REG = json.loads((P / 'preregistration.json').read_text())


def fixture(ratio=1.1):
    names = ['attention', 'hc.a.low', 'expsgate', 'expsdown', 'router', 'route', 'ple.kn', 'ffn.combine']
    sites = [dict(site=i, label='blk.0.' + name, **{'class': name}, kernel_count=2)
             for i, name in enumerate(names)]
    sites.append(dict(site=8, label='blk.0.zero', **{'class': 'zero'}, kernel_count=0))
    plan = dict(sites=sites, kernels=16)
    touches = [dict(site=s['site'], kernel_count=s['kernel_count'],
                    pretouch_events=1 if s['kernel_count'] else 0,
                    pretouch_bytes=4096 if s['kernel_count'] else 0) for s in sites]
    events, halves, states, controls = [], [], [], []
    clock = 1000
    for block in range(4):
        for slot in range(4):
            arm = A.ARMS[(block + slot) % 4]
            first = clock
            kns = tns = 0
            for site in sites:
                if not site['kernel_count']: continue
                for repeat in range(6 if arm == 'b' else 1):
                    flags = ([True] if arm == 'c' else []) + [False] * site['kernel_count']
                    for touch in flags:
                        duration = 25000 if touch else (int(300000 * ratio) if arm in ('a', 'natural') else 300000)
                        events.append(dict(block=block, arm=arm, site=site['site'], label=site['label'],
                                           **{'class': site['class']}, repeat=repeat,
                                           warmup=arm == 'b' and repeat < 2, pretouch=touch,
                                           start_ns=clock, end_ns=clock + duration))
                        clock += duration
                        if touch: tns += duration
                        else: kns += duration
            span = clock - first
            halves.append(dict(block=block, slot=slot, arm=arm, routes_equal=True, state_equal=True,
                               wall_ms=span / 1e6, kernel_ns=kns if arm != 'b' else 0,
                               pretouch_ns=tns if arm != 'b' else 0, event_span_ns=span if arm != 'b' else 0))
            states.append(dict(block=block, arm=arm, sha256_by_allocation={'1': 'a' * 64, '2': 'b' * 64}))
        controls.append(dict(block=block, wall_ms=16 * 300000 * ratio / 1e6, state_equal=True))
    return [plan, copy.deepcopy(REG), events, halves, controls, states, touches]


class Analysis(unittest.TestCase):
    def decision(self, ratio, cost=.5, validity=()):
        return A.decision({'attention': dict(a_over_b=ratio, a_ms=cost)}, validity, REG)

    def test_close_includes_115(self):
        self.assertEqual(self.decision(1.15)['verdict'], 'close-kernel-bound-under-diagnostic')
        self.assertEqual(self.decision(1.15001)['verdict'], 'report-and-close-intermediate')

    def test_followup_includes_130_and_half_ms(self):
        self.assertEqual(self.decision(1.3)['followup_classes'], ['attention'])
        self.assertEqual(self.decision(1.3, .4999)['followup_classes'], [])
        self.assertEqual(self.decision(1.2999)['followup_classes'], [])

    def test_validity_withholds_both_decisions(self):
        for ratio in (1.1, 1.5):
            self.assertEqual(self.decision(ratio, validity=['invalid'])['verdict'], 'inconclusive')
        with self.assertRaises(ValueError): A.decision({}, [], REG)

    def test_complete_coverage_and_separate_pretouch(self):
        r = A.timings(*fixture())
        self.assertEqual(r['verdict'], 'close-kernel-bound-under-diagnostic')
        self.assertEqual(r['event_count'], 608)
        self.assertEqual(r['pretouch']['bytes_per_half'], 32768)
        self.assertAlmostEqual(r['pretouch']['time_ms'], .2)
        self.assertEqual(set(r['classes']), set(REG['classes']))
        self.assertTrue(all(abs(c['a_over_b'] - 1.1) < 1e-12 for c in r['classes'].values()))

    def test_large_ratio_recommends_classes(self):
        self.assertEqual(len(A.timings(*fixture(1.3))['followup_classes']), 8)

    def test_never_sum_site_medians(self):
        f = fixture()
        # Two passes: individual medians sum to 5 ms, while complete sample
        # totals [101, 4, 6, 101] ms have a median of 53.5 ms.
        pairs = [(1000000, 100000000), (2000000, 2000000),
                 (3000000, 3000000), (100000000, 1000000)]
        for block in range(4):
            selected = [e for e in f[2] if e['block'] == block and e['arm'] == 'b']
            clock = selected[0]['start_ns']
            counters = {}
            for e in selected:
                duration = e['end_ns'] - e['start_ns']
                if e['site'] == 0 and e['repeat'] >= 2:
                    k = counters.get(e['repeat'], 0); counters[e['repeat']] = k + 1
                    duration = pairs[e['repeat'] - 2][k]
                e['start_ns'], e['end_ns'] = clock, clock + duration
                clock += duration
        self.assertEqual(A.timings(*f)['classes']['attention']['b_ms'], 53.5)

    def test_incomplete_duplicate_reordered_events(self):
        for mutation in ('missing', 'duplicate', 'order', 'clock', 'label', 'warmup'):
            with self.subTest(mutation=mutation):
                f = fixture()
                if mutation == 'missing': f[2].pop()
                if mutation == 'duplicate': f[2].insert(0, f[2][0].copy())
                if mutation == 'order': f[2][0], f[2][2] = f[2][2], f[2][0]
                if mutation == 'clock': f[2][0]['end_ns'] = f[2][0]['start_ns']
                if mutation == 'label': f[2][0]['label'] = 'wrong'
                if mutation == 'warmup': f[2][0]['warmup'] = True
                with self.assertRaises(ValueError): A.timings(*f)

    def test_complete_touch_manifest_including_zero_sites(self):
        for mutation in ('missing-zero', 'duplicate'):
            f = fixture()
            if mutation == 'missing-zero': f[6].pop()
            else: f[6].append(f[6][0])
            with self.assertRaises(ValueError): A.timings(*f)

    def test_equality_and_control_fail_closed(self):
        for mutation in ('routes', 'state', 'hash', 'control', 'missing-control', 'missing-half'):
            with self.subTest(mutation=mutation):
                f = fixture()
                if mutation == 'routes': f[3][0]['routes_equal'] = False
                if mutation == 'state': f[3][0]['state_equal'] = False
                if mutation == 'hash': f[5][0]['sha256_by_allocation']['1'] = 'c' * 64
                if mutation == 'control': f[4][0]['state_equal'] = False
                if mutation == 'missing-control': f[4].pop()
                if mutation == 'missing-half': f[3].pop()
                with self.assertRaises(ValueError): A.timings(*f)

    def test_observer_overhead(self):
        f = fixture()
        for c in f[4]: c['wall_ms'] /= 1.2
        self.assertEqual(A.timings(*f)['verdict'], 'inconclusive')

    def test_natural_sensitivity(self):
        f = fixture()
        for e in f[2]:
            if e['arm'] == 'natural':
                e['start_ns'] *= 2; e['end_ns'] *= 2
        for h in f[3]:
            if h['arm'] == 'natural':
                for k in ('kernel_ns', 'event_span_ns', 'wall_ms'): h[k] *= 2
        self.assertEqual(A.timings(*f)['verdict'], 'inconclusive')

    def test_issue_gap(self):
        f = fixture()
        for arm in ('a', 'c', 'natural'):
            for block in range(4):
                rows = [e for e in f[2] if e['arm'] == arm and e['block'] == block]
                for i, e in enumerate(rows):
                    e['start_ns'] += i * 100000; e['end_ns'] += i * 100000
                h = next(h for h in f[3] if h['arm'] == arm and h['block'] == block)
                h['event_span_ns'] += (len(rows) - 1) * 100000
        self.assertEqual(A.timings(*f)['verdict'], 'inconclusive')

    def test_complete_disk_reader_and_hash_tamper(self):
        import capture_identity as I
        f = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            def write(name, value, jsonl=False):
                path = out / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(''.join(json.dumps(r) + '\n' for r in value) if jsonl else json.dumps(value))
            write('identity.json', {})
            write('lane-coordination.json', dict(passed=True, released_before_report=True))
            write('run/teardown.json', dict(drained=True))
            suite = json.loads((P / 'suite.snapshot.json').read_text())
            write('suite-manifest.snapshot.json', suite)
            requests = []
            for name, count in [('incident-retrospective', 47), ('post-probe', 8)]:
                r = dict(passed=True, exact_reference=True, tokens=suite['prompts'][0]['expected_tokens'][:count])
                write('run/' + name + '/receipt.json', r); requests.append(r)
            write('run/report-inputs.json', dict(passed=True, requests=requests, device_isolation=dict(passed=True)))
            native = 'run/incident-retrospective/rank0/'
            write(native + 'p141-complete.json', dict(passed=True, diagnostic_only=True, blocks=4, arms=4, arithmetic='iq3-p49-split32-v1'))
            for name, value in zip(('events', 'halves', 'controls', 'state-hashes', 'touch-plan'), f[2:]):
                write(native + 'p141-' + name + '.jsonl', value, True)
            files = {str(x.relative_to(out)): A.sha(x) for x in out.rglob('*') if x.is_file()}
            write('window.json', dict(passed=True, device_executed=True, device_complete=True,
                  lease_released=True, child_still_running=False, diagnostic_only=True, identity={}, files=files))
            original_read = A.read
            def read(path):
                return f[0] if path == P / 'probe-plan.json' else original_read(path)
            with patch.object(I, 'verify'), patch.object(I, 'verify_identity'), patch.object(A, 'read', side_effect=read):
                self.assertTrue(A.analyze(out)['evidence_valid'])
                (out / (native + 'p141-events.jsonl')).write_text('{}\n')
                with self.assertRaisesRegex(ValueError, 'changed evidence'): A.analyze(out)


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    unittest.main()

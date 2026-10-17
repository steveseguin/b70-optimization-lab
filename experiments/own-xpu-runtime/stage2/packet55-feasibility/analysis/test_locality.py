#!/usr/bin/env python3
"""Small CPU-only checks of accounting, replacement and trace refusal."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import locality as loc


class LocalityTests(unittest.TestCase):
    def test_packet46_budget_and_all_sizes(self):
        budget = loc.placement(18_000_000_000)
        self.assertEqual(budget['slots'], 9082)
        self.assertEqual(budget['owned_bytes'], 17_998_372_864)
        self.assertEqual(budget['payload_bytes'], 17_970_176_000)
        for gb in loc.SIZES:
            p = loc.placement(gb * 1_000_000_000)
            self.assertLessEqual(p['owned_bytes'], gb * 1_000_000_000)
            self.assertTrue(all(0 <= q <= 512 for q in p['quotas']))

    def test_replacement_frequency_and_ties(self):
        lru, lfu = (loc.LayerCache(p, 2) for p in ('lru', 'lfu'))
        for c in (lru, lfu):
            for e in (1, 1, 2, 3):
                c.access(e)
        self.assertEqual(set(lru.entries), {2, 3})
        self.assertEqual(set(lfu.entries), {1, 3})
        c = loc.LayerCache('lfu', 2)
        for e in (4, 5, 6):
            c.access(e)
        self.assertEqual(set(c.entries), {5, 6})
        for _ in range(100):
            c.access(5)
        self.assertLessEqual(len(c.heap), 16)

    def test_static_never_admits_test_data(self):
        c = loc.LayerCache('static', 1)
        c.entries[4] = (7, 0)
        self.assertTrue(c.access(4))
        self.assertFalse(c.access(3))
        self.assertEqual(list(c.entries), [4])

    def test_route_pins_all_selected_residents_before_admission(self):
        for policy in ('lru', 'lfu'):
            for route in ([4, 1], [1, 4]):
                c = loc.LayerCache(policy, 3)
                for e in (1, 2, 3):
                    c.access(e)
                self.assertEqual(c.route(route), 1)
                self.assertIn(1, c.entries)
                self.assertIn(4, c.entries)

    def test_benchmark_contamination(self):
        banned = [dict(prompt_id='bench', tokens=[1, 2, 3])]
        for p in [dict(prompt_id='bench', tokens=[8]),
                  dict(prompt_id='new', tokens=[9, 1, 2, 3, 8]),
                  dict(prompt_id='new', tokens=[2, 3])]:
            with self.assertRaises(ValueError):
                loc.no_benchmark_overlap(dict(prompts=[p]), banned)
        loc.no_benchmark_overlap(dict(prompts=[dict(prompt_id='new', tokens=[9, 4, 8])]), banned)

    def test_repeated_visits_draft_and_train_test_reset(self):
        # Synthetic accounting fixture, not model routes. Every prompt uses two
        # route visits to the same position. The second prompt must start from
        # training again, and repeated work must remain in the denominator.
        rows = [dict(prompt_id='train', split='train', role='target', layer=0,
                     phase='decode', position=0, ids=list(range(10)))]
        for pid in ('a', 'b'):
            rows += [dict(prompt_id=pid, split='test', role='target', layer=0,
                          phase='decode', position=0, ids=list(range(10, 20))) for _ in range(2)]
            rows += [dict(prompt_id=pid, split='test', role='draft', layer=0,
                          phase='decode', position=0, ids=list(range(20, 30)))]
        manifest = dict(prompts=[dict(prompt_id=p) for p in ('train', 'a', 'b')])
        summary = dict(requests=[dict(prompt_id=p, split='test', generated_tokens=1) for p in ('a', 'b')])
        with tempfile.TemporaryDirectory() as tmp:
            detail = Path(tmp) / 'detail.gz'
            with patch.object(loc, 'records', side_effect=lambda *args: iter(rows)), patch.object(loc, 'SIZES', (8,)):
                result = loc.analyze(None, manifest, summary, detail)
            for report in result['results']:
                s = report['phases']['decode']['overall']
                self.assertEqual(s['route_visits'], 4)
                # Static quota exceeds20 so unseen low IDs were preloaded;
                # adaptive caches only preload observed IDs and miss each first visit.
                missing = 0 if report['policy'] == 'static' else 20
                self.assertEqual(s['missing_experts'], missing)
                self.assertEqual(s['requested_bytes'], 40 * loc.packed(0))
                self.assertEqual(report['phases']['decode']['miss_bytes_per_observed_position']['count'], 2)
            self.assertEqual(result['draft']['route_visits_by_phase']['decode'], 2)
            with gzip.open(detail, 'rt') as f:
                positions = [json.loads(r) for r in f if 'observed_position' in r]
            self.assertTrue(all(p['route_visits'] == 2 for p in positions))

    def test_incomplete_trace_and_weights_refused(self):
        manifest = dict(prompts=[dict(prompt_id='a', split='test', prompt_tokens=1)])
        summary = dict(requests=[dict(records=1, generated_tokens=1)])
        row = dict(prompt_id='a', split='test', rank=0, role='target', layer=0,
                   position=0, phase='decode', ids=list(range(10)), weights=[.1]*10,
                   monotonic_ns=1, sequence=1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'r.gz'
            with gzip.open(path, 'wt') as f:
                f.write(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError, 'incomplete target coverage'):
                list(loc.records(path, manifest, summary))
            row['weights'][-1] = float('nan')
            with gzip.open(path, 'wt') as f:
                f.write(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError, 'route weights'):
                list(loc.records(path, manifest, summary))

    def test_nearest_rank_no_interpolation(self):
        self.assertEqual(loc.quantiles([1, 2, 3, 100])['p50'], 2)
        self.assertEqual(loc.quantiles([1, 2, 3, 100])['p95'], 100)
        self.assertIsNone(loc.quantiles([])['p50'])

    def test_converter_to_analysis_contract_and_tamper_refusal(self):
        # Temporary synthetic receipts exercise the real converter contract.
        # Their device flags imitate its input ABI, never actual device evidence.
        source_path = loc.PACKET / 'route/convert.py'
        spec = importlib.util.spec_from_file_location('p55_test_converter', source_path)
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)

        def write_json(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value) + '\n')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, window = root / 'packet55', root / 'window'
            prompts = [dict(prompt_id=f'synthetic-{i:02}', split='train' if i < 12 else 'test',
                            category=('code', 'prose', 'analysis', 'structured', 'multilingual', 'math')[(i % 12)//2],
                            text=f'Independent synthetic fixture {i}', max_new_tokens=256) for i in range(24)]
            canonical = dict(schema='packet55.calibration.v1', benchmark_training=False, token_cap=256, prompts=prompts)
            canonical_path = packet / 'route/calibration-prompts.json'
            write_json(canonical_path, canonical)
            tokenized = [dict(p, tokens=[1000+i, 2000+i], prompt_tokens=2,
                              prompt_sha256=hashlib.sha256(p['text'].encode()).hexdigest()) for i, p in enumerate(prompts)]
            manifest = dict(canonical, prompts=tokenized, source_sha256=loc.sha(canonical_path),
                            benchmark_prompt_overlap=False, synthetic_fixture=True)
            manifest_path = window / 'calibration-manifest.json'
            write_json(manifest_path, manifest)
            window_path = window / 'window.json'
            write_json(window_path, dict(passed=True, device_executed=True, synthetic_fixture=True))
            forbidden = []
            for i in range(12):
                bundle = root / f'benchmark-{i}'
                bundle.mkdir()
                (bundle / 'tokens.txt').write_text(f'{9000+i} {8000+i}\n')
                forbidden.append(dict(prompt_id=f'benchmark-{i}', input_bundle=bundle.name,
                                      input_bundle_hashes={'tokens.txt': loc.sha(bundle / 'tokens.txt')}))
            write_json(packet.parent / 'packet49c-round2/oracle/results/suite-manifest.json', dict(prompts=forbidden))
            for i, p in enumerate(prompts):
                request = window / 'requests' / p['prompt_id']
                write_json(request / 'result.json', dict(prompt_id=p['prompt_id'], passed=True,
                           completed=True, generated_tokens=1, synthetic_fixture=True))
                for rank in (0, 1):
                    path = request / f'rank{rank}/routes.p55bin'
                    path.parent.mkdir()
                    sequence = 0
                    ids = list(range(10 if i < 12 else 20))[-10:]
                    with path.open('wb') as f:
                        f.write(converter.MAGIC)
                        for pos in (0, 1):
                            for layer in (range(23) if rank == 0 else range(23, 48)):
                                f.write(converter.RECORD.pack(sequence, 10000*pos+10*layer,
                                        pos, layer, 0, 10, pos+1, 0, 1, *ids, *([.1]*10)))
                                sequence += 1
                        if rank == 1:
                            f.write(converter.RECORD.pack(sequence, 20000, 0, 0, 1, 10,
                                    3, 0, 1, *ids, *([.1]*10)))
            trace = root / 'routes.jsonl.gz'
            summary = converter.convert(window, trace)
            self.assertEqual(summary['records'], 24 * 97)
            self.assertFalse(summary['requested_scope_complete'])
            with patch.object(loc, 'PACKET', packet), patch.object(loc, 'ROOT', root):
                bound_manifest, bound_summary, bindings = loc.inputs(window, trace)
                self.assertEqual(bindings['trace_sha256'], loc.sha(trace))
                self.assertEqual(sum(1 for _ in loc.records(trace, bound_manifest, bound_summary)), 24*97)
                result = loc.analyze(trace, bound_manifest, bound_summary, root / 'positions.jsonl.gz')
                self.assertFalse(result['requested_scope_complete'])
                self.assertEqual(result['generated_tokens_test'], 12)
                self.assertEqual(result['draft']['route_visits_by_phase'], {'decode': 12})
                self.assertEqual(len(result['results']), 12)
                for report in result['results']:
                    prefill, decode = report['phases']['prefill'], report['phases']['decode']
                    self.assertEqual(prefill['overall']['route_visits'], 48*12)
                    self.assertEqual(decode['overall']['route_visits'], 48*12)
                    self.assertEqual(decode['overall']['miss_bytes'], 0)
                    misses = 0 if report['policy'] == 'static' else 949_760_000*12
                    self.assertEqual(prefill['overall']['miss_bytes'], misses)
                paths = [(trace, 'output_sha256'), (manifest_path, 'manifest_sha256'),
                         (window_path, 'window_sha256'), (canonical_path, 'calibration source binding'),
                         (window / 'requests/synthetic-00/result.json', 'request result binding'),
                         (window / 'requests/synthetic-00/rank0/routes.p55bin', 'native route binding')]
                for path, message in paths:
                    with self.subTest(tampered=path.name):
                        original = path.read_bytes()
                        try:
                            path.write_bytes(original + b' ')
                            with self.assertRaisesRegex(ValueError, message):
                                loc.inputs(window, trace)
                        finally:
                            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()

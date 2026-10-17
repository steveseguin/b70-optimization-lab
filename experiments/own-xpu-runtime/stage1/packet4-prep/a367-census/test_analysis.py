#!/usr/bin/env python3
"""Lean synthetic CPU tests; no accelerator modules or runtime imports."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('analyze_census', Path(__file__).with_name('analyze_census.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURES = Path(__file__).with_name('fixtures')
FEAS_MARKER = re.compile(r'PyTorch::A367Feas\|(eager|replay)\|i=([0-9]+)')


def real_trace_correlations(path):
    """Exercise production parsing/join with unchanged microtest marker names."""
    events = MODULE.chrome_events(path)
    spans = MODULE.itt_spans(events, 69448, FEAS_MARKER)
    devices = [{'event_ref': f'real:{i}', 'correlation_id': e.get('args', {}).get('id')}
               for i, e in enumerate(events) if e.get('ph') == 'X' and e.get('cat') == 'gpu_op']
    return events, MODULE.correlate_scopes(events, 69448, devices, spans)


def kernel(name='hc_gate_mix', start=100, duration=10, kid='1', pid=999, tid=5):
    return dict(ph='X', cat='gpu_op', name=name, ts=start, dur=duration,
                pid=pid, tid=tid, args={'id': kid})


def scope(kind='verify', m=2, seq=0, start=0, duration=10, pid=123, tid=7):
    return dict(ph='X', cat='cpu_op', name=f'A367|{kind}|M={m}|seq={seq}',
                ts=start, dur=duration, pid=pid, tid=tid)


def flow(kid=1, ts=2, pid=123, tid=7):
    return dict(ph='s', cat=f'Flow_H2D_{kid}_0', id=kid, ts=ts, pid=pid, tid=tid)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_case(self, events, **updates):
        trace = self.root / 'trace.json'
        trace.write_text(json.dumps({'traceEvents': events, 'displayTimeUnit': 'ns'}))
        receipt = self.root / 'marker-rank-0-pid-123.json'
        receipt.write_text(json.dumps({'schema': 'a367-census-marker-rank-v1', 'rank': 0, 'pid': 123}))
        manifest = {'schema': MODULE.SCHEMA, 'arm': 'eager-census', 'expected_ranks': [0],
                    'traces': [{'id': 'r0', 'path': 'trace.json', 'sha256': MODULE.sha(trace),
                                'rank': 0, 'worker_pid': 123, 'rank_evidence': 'marker-rank-0-pid-123.json', 'rank_evidence_sha256': MODULE.sha(receipt)}]}
        manifest.update(updates)
        path = self.root / 'map.json'
        path.write_text(json.dumps(manifest))
        return MODULE.analyze(path)

    def lifecycle_case(self, **updates):
        self.run_case([scope(), flow(), kernel(), scope('draft', 1, 1, 20),
                       flow(2, 22), kernel('generic', 120, 5, '2')], arm='graph-census')
        identity = self.root / 'identity.json'
        identity.write_text(json.dumps({'arm': 'graph-census'}))
        receipt = {'all_owners_gone': True, 'gap_complete': True, 'gpu_fault_lines': 0,
                   'client': {'returncode': 0}, 'passed': True, 'clean_exit': False,
                   'identity_sha256': MODULE.sha(identity),
                   'trace_capture': {'valid_for_graph_attribution': True},
                   'expected_tracer_exit_crash': {'evidence': 'data/2026-10-17-flash-next-trace-feasibility/'}}
        receipt.update(updates)
        lifecycle = self.root / 'lifecycle.json'
        lifecycle.write_text(json.dumps(receipt))
        manifest = json.loads((self.root / 'map.json').read_text())
        manifest.update(identity={'path': identity.name, 'sha256': MODULE.sha(identity)},
                        lifecycle={'path': lifecycle.name, 'sha256': MODULE.sha(lifecycle)})
        (self.root / 'map.json').write_text(json.dumps(manifest))
        return MODULE.analyze(self.root / 'map.json')

    def test_expected_exit_crash_does_not_invalidate_complete_census(self):
        result = self.lifecycle_case()
        self.assertTrue(result['segmentation_complete'])
        self.assertFalse(result['census_valid'])  # a one-rank fixture is not the census
        self.assertTrue(result['lifecycle_evidence_present'])
        self.assertIn('evidence', result['expected_tracer_exit_crash'])

    def test_missing_lifecycle_safety_fields_fail_closed(self):
        for field in ('all_owners_gone', 'gap_complete', 'gpu_fault_lines', 'client', 'passed'):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.lifecycle_case(**{field: None})

    def test_gpu_fault_or_failed_client_invalidates_lifecycle(self):
        for update in ({'gpu_fault_lines': 1}, {'gpu_fault_lines': False},
                       {'client': {'returncode': 1}}, {'client': {'returncode': False}}, {'client': {}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.lifecycle_case(**update)

    def test_late_resume_keeps_analysis_but_invalidates_graph_attribution(self):
        result = self.lifecycle_case(trace_capture={'valid_for_graph_attribution': False})
        self.assertFalse(result['segmentation_complete'])
        self.assertFalse(result['requested_scope_flow_coverage_complete'])
        self.assertEqual(len(result['timeline']), 2)
        self.assertTrue(any('before graph capture' in issue for issue in result['issues']))

    def test_missing_capture_receipt_invalidates_graph_attribution(self):
        result = self.lifecycle_case(trace_capture={})
        self.assertFalse(result['segmentation_complete'])

    def test_four_rank_census_valid_despite_unassigned_startup_work(self):
        self.lifecycle_case()
        path = self.root / 'map.json'
        manifest = json.loads(path.read_text())
        original = json.loads((self.root / 'trace.json').read_text())['traceEvents']
        manifest['expected_ranks'] = [0, 1, 2, 3]
        manifest['traces'] = []
        for rank in range(4):
            pid = 123 + rank
            events = [dict(e, pid=pid if e.get('cat') != 'gpu_op' else e['pid']) for e in original]
            events.append(kernel('startup_kernel', 200, 10, '99'))
            trace = self.root / f'trace-{rank}.json'
            trace.write_text(json.dumps({'traceEvents': events}))
            receipt = self.root / f'rank-{rank}.json'
            receipt.write_text(json.dumps({'schema': 'a367-census-marker-rank-v1', 'rank': rank, 'pid': pid}))
            manifest['traces'].append({'id': f'r{rank}', 'rank': rank, 'worker_pid': pid,
                                      'path': trace.name, 'sha256': MODULE.sha(trace),
                                      'rank_evidence': receipt.name, 'rank_evidence_sha256': MODULE.sha(receipt)})
        path.write_text(json.dumps(manifest))
        result = MODULE.analyze(path)
        self.assertTrue(result['census_valid'])
        self.assertTrue(result['requested_scope_flow_coverage_complete'])
        self.assertFalse(result['segmentation_complete'])
        self.assertFalse(result['whole_trace_assignment_complete'])
        manifest.pop('lifecycle')
        manifest.pop('identity')
        path.write_text(json.dumps(manifest))
        self.assertFalse(MODULE.analyze(path)['census_valid'])

    def test_copy_only_verify_scope_does_not_count_as_kernel_evidence(self):
        result = self.run_case([scope(), flow(), kernel('zeCommandListAppendMemoryCopy(D2D)'),
                                scope('draft', 1, 1, 20), flow(2, 22), kernel('generic', 120, 5, '2')])
        self.assertFalse(result['requested_scope_flow_coverage_complete'])
        self.assertFalse(result['census_valid'])
        self.assertTrue(any('no timestamped kernels' in issue for issue in result['issues']))

    def test_actual_unitrace_itt_fixture_correlates_eager_and_graph_replay(self):
        path = FIXTURES / 'unitrace-itt-graph-traced-excerpt.json'
        provenance = json.loads((FIXTURES / 'unitrace-itt-graph-traced-provenance.json').read_text())
        self.assertEqual(MODULE.sha(path), provenance['fixture_sha256'])
        self.assertLess(path.stat().st_size, 200_000)
        events, spans = real_trace_correlations(path)
        self.assertEqual([s['name'] for s in spans],
                         ['PyTorch::A367Feas|eager|i=0', 'PyTorch::A367Feas|replay|i=0'])
        self.assertEqual([len(s['event_refs']) for s in spans], [8, 8])
        self.assertEqual([s['unresolved_flow_sources'] for s in spans], [0, 0])
        self.assertEqual(MODULE.itt_spans(events, 69448), [])  # feasibility is not model verify
        self.assertEqual(MODULE.itt_spans(events, 123, FEAS_MARKER), [])

    def test_actual_fixture_never_guesses_attribution_without_flows(self):
        path = FIXTURES / 'unitrace-itt-graph-traced-excerpt.json'
        events = MODULE.chrome_events(path)
        events = [e for e in events if e.get('ph') != 's']
        spans = MODULE.itt_spans(events, 69448, FEAS_MARKER)
        devices = [{'event_ref': f'r:{i}', 'correlation_id': e.get('args', {}).get('id')}
                   for i, e in enumerate(events) if e.get('cat') == 'gpu_op']
        result = MODULE.correlate_scopes(events, 69448, devices, spans)
        self.assertEqual([s['event_refs'] for s in result], [[], []])

    def test_async_device_timestamp_joined_by_flow_not_host_interval(self):
        result = self.run_case([scope(), flow(), kernel(start=1000)])
        self.assertEqual(result['steps'][0]['kernel_count'], 1)
        self.assertEqual(result['steps'][0]['sum_device_us'], 10)

    def test_timestamp_overlap_without_flow_does_not_assign(self):
        result = self.run_case([scope(duration=100), kernel(start=5)])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 1)

    def test_itt_domain_prefix(self):
        mark = scope()
        mark['name'] = 'PyTorch::' + mark['name']
        result = self.run_case([mark, flow(), kernel()])
        self.assertEqual(result['steps'][0]['kernel_count'], 1)

    def test_rank_evidence_hash_mismatch(self):
        self.run_case([kernel()])
        (self.root / 'marker-rank-0-pid-123.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'rank evidence hash'):
            MODULE.analyze(self.root / 'map.json')

    def test_missing_rank_receipt(self):
        self.run_case([kernel()])
        (self.root / 'marker-rank-0-pid-123.json').unlink()
        with self.assertRaises(FileNotFoundError):
            MODULE.analyze(self.root / 'map.json')

    def test_swapped_rank_receipt_even_with_updated_hash(self):
        self.run_case([kernel()])
        receipt = self.root / 'marker-rank-0-pid-123.json'
        receipt.write_text(json.dumps({'schema': 'a367-census-marker-rank-v1', 'rank': 1, 'pid': 456}))
        manifest = json.loads((self.root / 'map.json').read_text())
        manifest['traces'][0]['rank_evidence_sha256'] = MODULE.sha(receipt)
        (self.root / 'map.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            MODULE.analyze(self.root / 'map.json')

    def test_batch_draft_scope_does_not_invent_model_rows(self):
        mark = scope('draft', 1)
        mark['name'] = 'PyTorch::A367|draft|B=1|seq=0'
        result = self.run_case([mark, flow(), kernel()])
        self.assertIsNone(result['steps'][0]['m'])
        self.assertEqual(result['steps'][0]['batch_size'], 1)

    def test_prefill_scope_excluded_without_damaging_requested_coverage(self):
        events = [scope(), flow(), kernel(), scope('draft', 1, 1, 20),
                  flow(2, 22), kernel('generic', 120, 5, '2'),
                  scope('target', 64, 2, 40), flow(3, 42), kernel('opaque', 150, 10, '3'),
                  kernel('sampling_outside_scope', 200, 2, '4')]
        result = self.run_case(events)
        self.assertEqual(len(result['excluded_scopes']), 1)
        self.assertTrue(result['requested_scope_flow_coverage_complete'])
        self.assertFalse(result['whole_trace_assignment_complete'])
        self.assertFalse(result['segmentation_complete'])

    def test_missing_device_flow_marks_requested_incomplete(self):
        result = self.run_case([scope(), flow(), flow(99, 3), kernel()])
        self.assertEqual(result['steps'][0]['unresolved_flow_sources'], 1)
        self.assertFalse(result['requested_scope_flow_coverage_complete'])

    def test_wrong_host_thread_remains_unassigned(self):
        result = self.run_case([scope(tid=8), flow(tid=7), kernel()])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 1)

    def test_synthetic_gpu_pid_does_not_become_rank(self):
        result = self.run_case([scope(), flow(), kernel(pid=432000)])
        self.assertEqual(result['timeline'][0]['rank'], 0)
        self.assertEqual(result['timeline'][0]['device_pid'], 432000)

    def test_wrong_os_pid_ignored(self):
        result = self.run_case([scope(pid=999), flow(pid=999), kernel()])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 1)

    def test_duplicate_kernel_correlation_ids_ambiguous(self):
        result = self.run_case([scope(), flow(), kernel(), kernel(start=120)])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 2)

    def test_multiple_host_flow_sources_ambiguous(self):
        result = self.run_case([scope(), flow(), flow(ts=3), kernel()])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 1)

    def test_overlapping_scopes_ambiguous(self):
        result = self.run_case([scope(), scope(seq=1), flow(), kernel()])
        self.assertEqual(result['rank_summaries'][0]['unassigned_kernels'], 1)

    def test_m1_target_is_not_verify(self):
        result = self.run_case([scope(m=1), flow(), kernel()])
        self.assertEqual(result['steps'], [])

    def test_copy_events_separate_from_kernel_count(self):
        result = self.run_case([scope(), flow(), flow(2, 3), kernel(),
                                kernel('zeCommandListAppendMemoryCopy(D2D)', 112, 3, '2')])
        step = result['steps'][0]
        self.assertEqual(step['device_event_count'], 2)
        self.assertEqual(step['kernel_count'], 1)
        self.assertEqual(step['copy_memset_count'], 1)

    def test_union_overlap_and_idle(self):
        rows = [dict(ts_us=0, duration_us=20), dict(ts_us=5, duration_us=10),
                dict(ts_us=30, duration_us=5)]
        stats = MODULE.interval_stats(rows)
        self.assertEqual(stats['sum_device_us'], 35)
        self.assertEqual(stats['busy_union_us'], 25)
        self.assertEqual(stats['wall_span_us'], 35)
        self.assertEqual(stats['idle_gaps_us'], [10])

    def test_nested_interval_ends_do_not_shorten_span(self):
        stats = MODULE.interval_stats([dict(ts_us=0, duration_us=100), dict(ts_us=90, duration_us=1)])
        self.assertEqual(stats['wall_span_us'], 100)
        self.assertEqual(stats['busy_union_us'], 100)

    def test_missing_boundaries_remain_unsegmented(self):
        result = self.run_case([kernel()])
        self.assertFalse(result['segmentation_complete'])
        self.assertEqual(result['rank_summaries'][0]['kernel_count'], 1)
        self.assertEqual(result['steps'], [])

    def test_host_calls_are_not_device_work(self):
        result = self.run_case([dict(ph='X', cat='cpu_op', name='zeCommandListAppendLaunchKernel', ts=0, dur=15)])
        self.assertEqual(result['rank_summaries'][0]['kernel_count'], 0)

    def test_unknown_family_preserved(self):
        result = self.run_case([scope(), flow(), kernel(name='opaque_gemm_123')])
        self.assertEqual(result['timeline'][0]['family'], 'unknown')
        self.assertIn('No fusion claim', result['ranked_time_sinks'][0]['exact_preserving_boundaries']['unknown'])

    def test_conflicting_family_rules_unknown(self):
        result = self.run_case([kernel()], family_rules=[dict(pattern='hc_gate_mix', family='QSA', evidence='synthetic conflict')])
        self.assertEqual(result['timeline'][0]['family'], 'unknown')

    def test_family_rule_requires_evidence(self):
        with self.assertRaisesRegex(ValueError, 'family rule'):
            self.run_case([kernel()], family_rules=[dict(pattern='.*', family='shared expert')])

    def test_missing_expected_rank_is_explicit(self):
        result = self.run_case([kernel()], expected_ranks=[0, 1, 2, 3])
        self.assertEqual(len(result['rank_summaries']), 4)
        self.assertIn('rank 3: no device timestamps', result['issues'])

    def test_graph_opaque_fails_completeness(self):
        result = self.run_case([], arm='graph-census', graph_opaque=True)
        self.assertIn('graph replay is opaque: no graph-internal attribution claim', result['issues'])
        self.assertFalse(result['speed_claim'])

    def test_complete_verify_draft(self):
        result = self.run_case([scope(), flow(), kernel(), scope('draft', 1, 1, 20),
                                flow(2, 22), kernel('generic', 120, 5, '2')])
        self.assertTrue(result['segmentation_complete'])
        self.assertFalse(result['census_valid'])  # no lifecycle evidence
        self.assertEqual(result['timeline'][1]['family'], 'MTP draft')
        self.assertEqual(result['timeline'][1]['intrinsic_family'], 'unknown')

    def test_explicit_mapping_can_resolve_missing_flow(self):
        result = self.run_case([kernel()], steps=[dict(id='manual', rank=0, kind='verify', m=2,
            event_refs=['r0:0'], evidence='audited device correlation fixture')])
        self.assertEqual(result['steps'][0]['kernel_count'], 1)

    def test_explicit_mapping_cannot_replace_required_itt_verify_markers(self):
        result = self.run_case([kernel(), kernel(kid='2')], steps=[
            dict(id='v', rank=0, kind='verify', m=2, event_refs=['r0:0'], evidence='synthetic'),
            dict(id='d', rank=0, kind='draft', m=1, event_refs=['r0:1'], evidence='synthetic')])
        self.assertFalse(result['segmentation_complete'])
        self.assertIn('rank 0: no ITT verify markers', result['issues'])

    def test_explicit_mapping_cannot_reference_host_event(self):
        with self.assertRaisesRegex(ValueError, 'non-device'):
            self.run_case([scope()], steps=[dict(id='bad', rank=0, kind='verify', m=2,
                event_refs=['r0:0'], evidence='bad fixture')])

    def test_duplicate_explicit_membership_rejected(self):
        step = dict(id='a', rank=0, kind='verify', m=2, event_refs=['r0:0'], evidence='fixture')
        with self.assertRaisesRegex(ValueError, 'multiple explicit'):
            self.run_case([kernel()], steps=[step, dict(step, id='b')])

    def test_hash_mismatch_rejected(self):
        self.run_case([kernel()])
        manifest = json.loads((self.root / 'map.json').read_text())
        manifest['traces'][0]['sha256'] = '0' * 64
        (self.root / 'map.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            MODULE.analyze(self.root / 'map.json')

    def test_negative_device_duration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'negative device'):
            self.run_case([kernel(duration=-1)])

    def test_nan_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, 'finite number'):
            self.run_case([kernel(start=float('nan'))])

    def test_clusters_include_boundaries_not_savings(self):
        result = self.run_case([scope(), flow(), flow(2, 3),
                                kernel(start=100), kernel('moe_sum', 112, 15, '2')])
        cluster = result['ranked_small_kernel_clusters'][0]
        self.assertEqual(cluster['kernel_count'], 2)
        self.assertEqual(cluster['wall_span_us'], 27)
        self.assertEqual(cluster['idle_us'], 2)
        self.assertIn('dispatch-audit', cluster['dispatch_audit'])
        self.assertNotIn('projected_saving_us', cluster)

    def test_clusters_do_not_cross_steps(self):
        result = self.run_case([scope(), flow(), kernel(), scope(seq=1, start=20),
                                flow(2, 22), kernel(start=111, kid='2')])
        self.assertEqual(result['ranked_small_kernel_clusters'], [])

    def test_cross_rank_sink_is_sum_not_union(self):
        result = self.run_case([kernel()])
        self.assertNotIn('wall_span_us', result['ranked_time_sinks'][0])

    def test_chrome_root_array_accepted(self):
        self.run_case([kernel()])
        (self.root / 'trace.json').write_text(json.dumps([kernel()]))
        manifest = json.loads((self.root / 'map.json').read_text())
        manifest['traces'][0]['sha256'] = MODULE.sha(self.root / 'trace.json')
        (self.root / 'map.json').write_text(json.dumps(manifest))
        self.assertEqual(MODULE.analyze(self.root / 'map.json')['rank_summaries'][0]['kernel_count'], 1)

    def test_cli_writes_diagnostic_outputs_and_refuses_overwrite(self):
        self.run_case([kernel()])
        cmd = [sys.executable, '-B', str(Path(MODULE.__file__)), '--manifest', str(self.root / 'map.json'), '--out-dir', str(self.root / 'out')]
        done = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.root / 'out/census.json').is_file())
        self.assertIn('no speed claim', (self.root / 'out/census.md').read_text())
        self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()

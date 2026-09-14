#!/usr/bin/env python3
"""Synthetic sampled-trace/source contracts; no profiler or native execution."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PATH = Path(__file__).with_name('summarize-multiblock-stack.py')
spec = importlib.util.spec_from_file_location('summary_tested', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = m.load_sources(m.PACKET)

    def frame(self, key, name):
        source = self.sources[key]
        return {'name': name.split('.')[-1], 'file': source['path'], 'line': source['spans'][name][0]}

    def trace(self):
        frames = [{'name': 'prompt_worker', 'file': '/source/main.py', 'line': 10},
                  {'name': 'get', 'file': '/source/execution.py', 'line': 10},
                  {'name': 'wait', 'file': '/python/threading.py', 'line': 10},
                  self.frame('adapter', '_CompilePreRun._validate'),
                  self.frame('adapter', 'CompiledBlockRoute._validate'),
                  self.frame('node_plugin', '_Gate.__call__'),
                  self.frame('node_plugin', 'write_json'),
                  {'name': 'call', 'file': '/server/inductor-cache/a/example.py', 'line': 10},
                  {'name': '<unknown>', 'file': '', 'line': 0},
                  {'name': 'foo', 'file': '/other.py', 'line': 30}]
        worker = {'name': 'Thread 10 "Thread-2 (prompt_worker)"', 'type': 'sampled', 'unit': 'seconds',
                  'startValue': 0, 'endValue': 4.5, 'samples': [[0, 1, 2], [], [0, 3, 4], [0, 3],
                   [0, 5, 6], [0, 5, 7], [0, 8], [0, 9], [0, 5]],
                  'weights': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]}
        idle = {'name': 'Other idle thread', 'type': 'sampled', 'unit': 'seconds', 'startValue': 0,
                'endValue': 1000, 'samples': [[1, 2]], 'weights': [1000]}
        return {'shared': {'frames': frames}, 'profiles': [worker, idle]}

    def test_exclusive_counts_and_weights(self):
        result = m.summarize(self.trace(), self.sources)
        self.assertEqual(result['sample_count'], 9)
        self.assertTrue(result['sample_conservation'] and result['weight_conservation'])
        self.assertAlmostEqual(result['weight_semantics']['total_weight'], 4.5)
        self.assertEqual(result['categories']['receipt_context_checks_writes']['samples'], 2)
        self.assertEqual(result['categories']['current_block_state_validation']['samples'], 1)
        self.assertEqual(result['categories']['aggregate_registry_lifecycle']['samples'], 1)
        self.assertEqual(result['categories']['queue_idle']['weight'], 0.1)
        self.assertEqual(result['profile_count_ignored'], 1)

    def test_ast_disambiguates_validate(self):
        state = self.frame('adapter', 'CompiledBlockRoute._validate')
        registry = self.frame('adapter', '_CompilePreRun._validate')
        self.assertEqual(state['name'], registry['name'])
        self.assertEqual(m.classify([state], self.sources), 'current_block_state_validation')
        self.assertEqual(m.classify([registry], self.sources), 'aggregate_registry_lifecycle')
        self.assertEqual(m.classify([registry, state], self.sources), 'current_block_state_validation')

    def test_same_name_other_source_not_claimed(self):
        frame = self.frame('adapter', 'CompiledBlockRoute._validate'); frame['file'] = '/unrelated.py'
        self.assertEqual(m.classify([frame], self.sources), 'other')

    def test_plugin_path_classified(self):
        self.assertEqual(m.classify([self.frame('node_plugin', 'graph_receipts')], self.sources), 'receipt_context_checks_writes')

    def test_context_descendants(self):
        context = self.frame('context', '_context')
        self.assertEqual(m.classify([context, {'name': 'read', 'file': '/stdlib.py', 'line': 1}], self.sources), 'receipt_context_checks_writes')

    def test_native_ancestor_does_not_swallow_gate(self):
        native = {'name': 'call', 'file': '/torch/_dynamo/eval_frame.py', 'line': 1}
        gate = self.frame('node_plugin', '_Gate.__call__')
        self.assertEqual(m.classify([native, gate], self.sources), 'receipt_context_checks_writes')
        self.assertEqual(m.classify([gate, native], self.sources), 'compiled_wrapper_native_calls')

    def test_direct_native_callsite_is_not_receipt_work(self):
        frame = self.frame('node_plugin', '_Gate.__call__')
        frame['line'] = self.sources['node_plugin']['native_callsite_lines'][0]
        self.assertEqual(m.classify([frame], self.sources), 'compiled_wrapper_native_calls')

    def test_native_without_route_not_claimed(self):
        self.assertEqual(m.classify([{'name': 'call', 'file': '/torch/_ops.py', 'line': 1}], self.sources), 'other')

    def test_idle_requires_specific_chain(self):
        wait = {'name': 'wait', 'file': '/python/threading.py', 'line': 1}
        self.assertEqual(m.classify([wait], self.sources), 'other')

    def test_unknown_and_empty_preserved(self):
        result = m.summarize(self.trace(), self.sources)
        self.assertEqual(result['categories']['empty_stack']['samples'], 1)
        self.assertEqual(result['categories']['unknown_leaf']['samples'], 1)
        self.assertEqual(result['unknown_leaf_audit']['samples'], 1)
        self.assertTrue(any(row['name'] == '<empty stack>' for row in result['top_nonidle_leaves']))

    def test_unknown_nested_state_stays_visible(self):
        trace = self.trace(); trace['profiles'][0]['samples'][2].append(8)
        result = m.summarize(trace, self.sources)
        self.assertEqual(result['unknown_leaf_audit']['samples'], 2)
        self.assertEqual(result['categories']['current_block_state_validation']['samples'], 1)

    def test_exact_worker_selection(self):
        trace = self.trace()
        with self.assertRaises(ValueError):
            m.summarize(trace, self.sources, 'prompt_worker')
        self.assertEqual(m.summarize(trace, self.sources, trace['profiles'][0]['name'])['sample_count'], 9)

    def test_ambiguous_workers_rejected(self):
        trace = self.trace(); trace['profiles'].append(copy.deepcopy(trace['profiles'][0]))
        with self.assertRaises(ValueError):
            m.summarize(trace, self.sources)

    def test_wrong_thread_rejected(self):
        with self.assertRaises(ValueError):
            m.summarize(self.trace(), self.sources, 'Other idle thread')

    def test_missing_weights_are_counts(self):
        trace = self.trace(); del trace['profiles'][0]['weights']
        result = m.summarize(trace, self.sources)
        self.assertEqual(result['weight_semantics']['weight_unit'], 'samples')
        self.assertEqual(result['weight_semantics']['total_weight'], 9)

    def test_bad_weights(self):
        for value in (-1, True, float('nan'), float('inf'), '1'):
            trace = self.trace(); trace['profiles'][0]['weights'][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.summarize(trace, self.sources)
        trace = self.trace(); trace['profiles'][0]['weights'].pop()
        with self.assertRaises(ValueError):
            m.summarize(trace, self.sources)

    def test_zero_weight_preserved(self):
        trace = self.trace(); trace['profiles'][0]['weights'][0] = 0
        result = m.summarize(trace, self.sources)
        self.assertEqual(result['categories']['queue_idle'], {'samples': 1, 'weight': 0.0})

    def test_bad_units_extents_and_type(self):
        for key, value in [('unit', 'minutes'), ('startValue', True), ('endValue', -1), ('type', 'evented')]:
            trace = self.trace(); trace['profiles'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.summarize(trace, self.sources, trace['profiles'][0]['name'])

    def test_bad_frame_index(self):
        for value in (True, -1, 999, '1'):
            trace = self.trace(); trace['profiles'][0]['samples'][0].append(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.summarize(trace, self.sources)

    def test_weight_extent_difference_reported(self):
        trace = self.trace(); trace['profiles'][0]['endValue'] = 10
        self.assertAlmostEqual(m.summarize(trace, self.sources)['weight_semantics']['weight_minus_extent'], -5.5)

    def test_actual_log_bounded_no_invented_count(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profiler.log'
            path.write_text('normal line\n' + 'warning synthetic\n' * 43)
            report = m.log_evidence(path)
            self.assertEqual(report['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(report['matching_line_count'], 43)
            self.assertEqual(len(report['matching_lines']), 40)
            self.assertEqual(report['truncated_matching_lines'], 3)
            self.assertNotIn('142', json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError(args.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report = {'passed': result.wasSuccessful(), 'tests': result.testsRun, 'errors': len(result.errors),
              'failures': len(result.failures), 'torch_imported': 'torch' in sys.modules,
              'scope': 'Synthetic traces and pinned source ASTs only; no profiling or runtime actions',
              'script_sha256': m.sha(PATH), 'test_sha256': m.sha(Path(__file__)),
              'adapter_sha256': m.ADAPTER_SHA, 'packet_manifest_sha256': m.MANIFEST_SHA}
    with args.output.open('x') as out:
        json.dump(report, out, indent=2); out.write('\n')
    raise SystemExit(not result.wasSuccessful() or report['torch_imported'])

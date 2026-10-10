"""CPU contract, evidence and source-closure checks for the packet125 lever."""
import ast
import copy
import os
from pathlib import Path
import unittest

import maintenance125
import stream_contract as c
import stream_receipts as receipts
from test_gate_receipts import passing, decide

HERE = Path(__file__).resolve().parent
LEVERS = ('cone', 1, 1)
OPTIONS = {'display_device': 'xpu:3', 'display_schedule': 'sampler-a',
           'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_worker': 'serial'}


class GCScope125(unittest.TestCase):
    def scope(self, interval=60, frames=145, placement='two-way20-28', anchor='frame',
              decoder_graph=0, levers=LEVERS, options=None):
        return c.check_gc_scope(interval, frames, placement, anchor, decoder_graph, levers,
                                OPTIONS if options is None else options)

    def test_contract_and_runtime_parse_same_values(self):
        for value in ('10', '60'):
            env = {maintenance125.ENV: value}
            self.assertEqual(c.launch_gc_interval(env), maintenance125.launch_interval(env))
        self.assertEqual(c.launch_gc_interval({}), 10)

    def test_contract_refuses_invalid_environment(self):
        for value in ('', '0', '10.0', ' 10', '600', 10, None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.launch_gc_interval({maintenance125.ENV: value})

    def test_parent_interval_keeps_other_admitted_variants_available(self):
        for frames in (49, 97, 121, 145, 169):
            self.scope(interval=10, frames=frames)

    def test_candidate_exact_configuration_admitted(self):
        self.scope()

    def test_candidate_each_changed_geometry_or_lever_refused(self):
        changes = [{'frames': 121}, {'frames': 169}, {'placement': 'other'}, {'anchor': 'latent'},
                   {'decoder_graph': 1}, {'levers': ('full', 1, 1)},
                   {'levers': ('cone', 0, 1)}, {'levers': ('cone', 1, 0)}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.scope(**change)

    def test_candidate_schedule_scope_refused(self):
        for key, value in [('display_device', 'xpu:2'), ('display_schedule', 'eager-display'),
                           ('display_schedule', 'sampler-b'), ('anchor_read_ahead', 1),
                           ('snapshot_schedule', 'a-xpu3-sync'), ('display_worker', 'parallel')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.scope(options=dict(OPTIONS, **{key: value}))

    def test_candidate_missing_required_scope_refused(self):
        for key in OPTIONS.keys() - {'display_worker'}:
            options = dict(OPTIONS)
            del options[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.scope(options=options)

    def test_interval_type_and_domain_refused(self):
        for value in (True, 10., '10', 0, 30, 600, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.scope(interval=value)

    def fixture(self, interval=None):
        rows, decodes, captures = passing(frames=145, anchor='frame', decoder_graph=0,
                                          levers=LEVERS, snapshot_mode='fingerprint')
        if interval is not None:
            for row in rows:
                row['server_options']['gc_interval_seconds'] = interval
        return rows, decodes, captures

    def verdict(self, data, **kwargs):
        return decide(*data, frames=145, anchor='frame', decoder_graph=0, levers=LEVERS, **kwargs)

    def test_historical_missing_option_means_parent(self):
        data = self.fixture()
        receipts.validate_measurements(data[0][0])
        result = self.verdict(data)
        self.assertTrue(result['passed'], result['failures'])

    def test_candidate_receipt_and_three_chain_gate_accept(self):
        data = self.fixture(60)
        for row in data[0]:
            receipts.validate_measurements(row)
        result = self.verdict(data)
        self.assertTrue(result['passed'], result['failures'])

    def test_invalid_receipt_option_refused(self):
        for value in (None, '60', True, 0, 11, 60.):
            data = self.fixture(value)
            data[0][0]['server_options']['gc_interval_seconds'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                receipts.validate_measurements(data[0][0])

    def test_candidate_cannot_reuse_parent_receipt_gate(self):
        data = self.fixture(60)
        data[0][4]['server_options']['gc_interval_seconds'] = 10
        result = self.verdict(data)
        self.assertFalse(result['passed'])
        self.assertTrue(any('options' in item for item in result['failures']), result['failures'])

    def test_missing_interval_not_accepted_as_candidate(self):
        data = self.fixture(60)
        del data[0][4]['server_options']['gc_interval_seconds']
        self.assertFalse(self.verdict(data)['passed'])

    def test_gate_rejects_out_of_scope_interval(self):
        data = self.fixture(60)
        for row in data[0]:
            row['server_options']['gc_interval_seconds'] = 30
        result = self.verdict(data)
        self.assertFalse(result['passed'])
        self.assertTrue(any('GC interval' in item for item in result['failures']), result['failures'])

    def test_run_namespace_off_and_candidate_are_distinct(self):
        tree = ast.parse((HERE / 'runtime_packet.py').read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'expected_run_name')
        key = '145/two-way20-28/frame/dg0/ad-cone/bo1/pa1/sm-fingerprint'
        scope = {'os': os, 'RUN_NAMES': {key: 'parent-namespace'}}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'actual-run-name', 'exec'), scope)
        env = dict(zip(('LTX_STREAM_FRAMES', 'LTX_SAMPLER_PLACEMENT', 'LTX_ANCHOR', 'LTX_DECODER_GRAPH',
                        'LTX_ANCHOR_DECODE', 'LTX_BENCODE_OVERLAP', 'LTX_PREP_AHEAD', 'LTX_SNAPSHOT_MODE'),
                       ('145', 'two-way20-28', 'frame', '0', 'cone', '1', '1', 'fingerprint')))
        self.assertEqual(scope['expected_run_name'](env), 'parent-namespace')
        self.assertEqual(scope['expected_run_name'](dict(env, LTX_GC_INTERVAL_SECONDS='10')), 'parent-namespace')
        self.assertEqual(scope['expected_run_name'](dict(env, LTX_GC_INTERVAL_SECONDS='60')), 'parent-namespace-gc60')

    def test_builder_closes_helper_and_transformed_main(self):
        tree = ast.parse((HERE / 'runtime_packet.py').read_text())
        assignments = {node.targets[0].id: node.value for node in tree.body if isinstance(node, ast.Assign)
                       and isinstance(node.targets[0], ast.Name)}
        components = ast.literal_eval(assignments['COMPONENTS'])
        self.assertIn('maintenance125.py', components)
        namespace = {'COMPONENTS': components}
        exec(compile(ast.Module(body=[next(node for node in tree.body if isinstance(node, ast.Assign)
                                          and isinstance(node.targets[0], ast.Name)
                                          and node.targets[0].id == 'MODULES')], type_ignores=[]), 'module-map', 'exec'), namespace)
        self.assertEqual(namespace['MODULES']['maintenance125.py'], 'maintenance125.py')
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'successor_files')
        source = ast.unparse(fn)
        self.assertIn("result['source/main.py'] = maintenance.transform_main(regular(PARENT / 'source/main.py'))", source)

    def test_launcher_propagates_checked_choice_without_execution(self):
        source = (HERE / 'launch-125.sh').read_text()
        self.assertIn('GC=${LTX_GC_INTERVAL_SECONDS:-10}', source)
        self.assertIn('LTX_GC_INTERVAL_SECONDS=$GC', source)
        self.assertIn('NAME=${NAME}-gc60', source)
        self.assertIn('145/frame/0/cone/1/1/sampler-a/0/full/xpu:3/serial', source)
        self.assertIn("*) echo 'REFUSE: GC interval'; exit 2", source)


if __name__ == '__main__':
    unittest.main()

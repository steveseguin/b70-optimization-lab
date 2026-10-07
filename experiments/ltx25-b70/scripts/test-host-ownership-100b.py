#!/usr/bin/env python3
"""CPU regression of real sealed100 host ownership, corrected via100b transform.

Extract actual functions with AST, execute them with model metadata mocks and the
real placement table. No Torch/Comfy imports, native modules, model reads or GPUs.
The positive control uses the builder's real host_source transform, not a copy.
"""
import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ownership100b_checker', HERE / 'check-runtime-100b.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
SOURCE = C.PARENT / 'source'
HOST = C.regular(SOURCE / 'scripts/host_embedding_resident_node.py')
CORRECTED = C.host_source(HOST)


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def extract(raw, functions=(), constants=(), env=None):
    selected = []
    for n in ast.parse(raw).body:
        if isinstance(n, ast.FunctionDef) and n.name in functions:
            selected.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets):
            selected.append(n)
    ns = dict(env or {})
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<actual sealed CPU functions>', 'exec'), ns)
    return ns


SHARD = extract(C.regular(SOURCE / 'scripts/ltx_layer_shard.py'),
                ('segment_plan',), ('PLACEMENTS', 'DECLARED_SPLIT_INDEX'))
PLACEMENTS = SHARD['PLACEMENTS']


def host(raw, layout):
    return extract(raw, ('shared_identity',), env={'require': require, 'PLACEMENTS': PLACEMENTS,
                   'SAMPLER_PLACEMENT': layout})['shared_identity']


def fixture(layout):
    seg = PLACEMENTS[layout]
    shards = [N(model=N(), load_device=d) for d, a, b in seg[1:]]
    report = {'segments': [list(x) for x in seg], 'devices': [x[0] for x in seg],
              'segment_bytes': [1024] * len(seg), 'split_index': None, 'block_count': 48}
    model = N(model=N(diffusion_model=N(_ltx_layer_shard_identity=report)), load_device='xpu:0',
              get_additional_models_with_key=lambda key: shards)
    return (model, N(), N(), N()), shards


class Ownership100b(unittest.TestCase):
    def test_original_reproduces_incident_corrected_two_segment_succeeds(self):
        shared, shards = fixture('two-way20-28')
        with self.assertRaisesRegex(RuntimeError, 'Shard owners'):
            host(HOST, 'two-way20-28')(shared)
        result = host(CORRECTED, 'two-way20-28')(shared)
        self.assertEqual(result['segments'], [['xpu:0', 0, 20], ['xpu:1', 20, 48]])
        self.assertEqual(result['shard_patchers'], [id(shards[0])])
        self.assertEqual(result['shard_models'], [id(shards[0].model)])

    def test_legacy_two_way_singular_receipt_unchanged(self):
        shared, shards = fixture('two-way')
        shared[0].model.diffusion_model._ltx_layer_shard_identity = {'split_index': 23}
        a, b = host(HOST, 'two-way')(shared), host(CORRECTED, 'two-way')(shared)
        self.assertEqual(a, b)
        self.assertEqual(b['shard_patcher'], id(shards[0]))
        self.assertNotIn('shard_patchers', b)

    def test_existing_multi_segment_receipts_unchanged(self):
        for layout in ('shard3-c', 'shard4-a'):
            with self.subTest(layout=layout):
                shared, _ = fixture(layout)
                self.assertEqual(host(HOST, layout)(shared), host(CORRECTED, layout)(shared))

    def test_real_segment_coverage_and_capture_lookup(self):
        capture = extract(C.regular(SOURCE / 'scripts/graph_capture_node.py'), ('check_shard_report',),
                          env={'require': require, 'DECLARED_SPLIT_INDEX': SHARD['DECLARED_SPLIT_INDEX']})
        with patch.dict(sys.modules, {'ltx_layer_shard': N(PLACEMENTS=PLACEMENTS)}):
            for layout in ('two-way20-28', 'shard3-c', 'shard4-a'):
                shared, _ = fixture(layout)
                report = shared[0].model.diffusion_model._ltx_layer_shard_identity
                self.assertEqual(capture['check_shard_report'](report), layout)
                plan = SHARD['segment_plan'](PLACEMENTS[layout])
                self.assertEqual(len(plan), 48)
                self.assertEqual([i for i, row in enumerate(plan) if row[2]], [47])
            shared, _ = fixture('two-way20-28')
            report = shared[0].model.diffusion_model._ltx_layer_shard_identity
            report['segments'][1][1] = 21
            with self.assertRaises(RuntimeError): capture['check_shard_report'](report)
            with self.assertRaises(ValueError): SHARD['segment_plan'](report['segments'])

    def test_named_placement_and_coverage_mismatch_refuse(self):
        for kind in ('gap', 'overlap', 'unknown-name', 'legacy-with-segments', 'missing-segments'):
            shared, _ = fixture('two-way20-28'); layout = 'two-way20-28'
            segments = shared[0].model.diffusion_model._ltx_layer_shard_identity['segments']
            if kind == 'gap': segments[1][1] = 21
            if kind == 'overlap': segments[1][1] = 19
            if kind == 'unknown-name': layout = 'unknown'
            if kind == 'legacy-with-segments': layout = 'two-way'
            if kind == 'missing-segments':
                shared[0].model.diffusion_model._ltx_layer_shard_identity.pop('segments')
            with self.subTest(kind=kind), self.assertRaises((RuntimeError, KeyError)):
                host(CORRECTED, layout)(shared)

    def test_missing_extra_and_wrong_device_owners_refuse(self):
        for kind in ('missing', 'extra', 'wrong-card'):
            shared, shards = fixture('two-way20-28')
            if kind == 'missing': shards.clear()
            if kind == 'extra': shards.append(N(model=N(), load_device='xpu:2'))
            if kind == 'wrong-card': shards[0].load_device = 'xpu:2'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                host(CORRECTED, 'two-way20-28')(shared)

    def test_aliased_secondary_and_primary_owners_refuse(self):
        for kind in ('secondary-patcher', 'secondary-model', 'primary-patcher', 'primary-model'):
            layout = 'shard3-c' if kind.startswith('secondary') else 'two-way20-28'
            shared, shards = fixture(layout)
            if kind == 'secondary-patcher': shards[1] = shards[0]
            if kind == 'secondary-model': shards[1].model = shards[0].model
            if kind == 'primary-patcher': shards[0] = shared[0]
            if kind == 'primary-model': shards[0].model = shared[0].model
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                host(CORRECTED, layout)(shared)

    def test_pipeline_freeze_residency_requires_one_secondary(self):
        ns = extract(C.regular(SOURCE / 'scripts/pipeline_sampler_node.py'),
                     ('placement_devices', 'expected_residents', 'residents_missing'))
        shared, _ = fixture('two-way20-28')
        devices = ns['placement_devices'](N(model_patcher=shared[0]))
        self.assertEqual(devices, ['xpu:0', 'xpu:1'])
        self.assertEqual([d for d in devices if d not in ('xpu:0', 'xpu:1')], [])
        expected = ns['expected_residents'](devices)
        self.assertEqual({x for x in expected if x[0] == '_Shard'}, {('_Shard', 'xpu:1')})
        resident = [(t, d, 1024) for t, d in expected]
        self.assertEqual(ns['residents_missing'](resident, devices), [])
        self.assertEqual(ns['residents_missing']([r for r in resident if r[0] != '_Shard'], devices), [('_Shard', 'xpu:1')])

    def test_only_shared_identity_changes_and_mirrors_agree(self):
        mirror = C.regular(SOURCE / 'custom_nodes/ltx_host_embedding_lab/__init__.py')
        self.assertEqual(HOST, mirror)
        self.assertEqual(CORRECTED, C.host_source(mirror))
        def rest(raw):
            return [ast.dump(n) for n in ast.parse(raw).body if not (isinstance(n, ast.FunctionDef) and n.name == 'shared_identity')]
        self.assertEqual(rest(HOST), rest(CORRECTED))
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    unittest.main(verbosity=2)

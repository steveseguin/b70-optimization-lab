"""CPU-only source/transport tests; no comparator import or device access."""
import ast
import copy
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from adapters import vllm_xpu_certified as adapter
from common import file_hash, load_tensor, token_hash
from extract_fixtures import Recorder
from mock_comparator import EAGER, mock_identity


SOURCE = '''class Boundary:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def forward(self, x, fail=False):
        self.calls += 1
        if fail:
            raise RuntimeError("synthetic operator failure")
        self.state.add_(1)
        return x

    @staticmethod
    def static(x):
        return x

    def in_place(self, x, out):
        self.calls += 1
        out.copy_(x)

class Other:
    def forward(self, x):
        return x

def native_boundary(x):
    return x
'''


def metadata(row, arguments):
    return dict(M=1, N=2, K=2, layer=0, rank=0,
                positions=[7], valid_rows=[True])


def graph_objects():
    class Wrapper:
        def __call__(self):
            return 'wrapper'
    class Graph:
        def capture_begin(self):
            return 'capture'
    api = SimpleNamespace(graph=lambda: 'graph', XPUGraph=Graph)
    return SimpleNamespace(xpu=api), Wrapper


class Spy:
    def __init__(self):
        self.config = dict(EAGER)
        self.records = []

    def observe(self, original, args, kwargs, spec, inputs, outputs, states):
        # CPU cloning here models the real Recorder's before/after serialization.
        before = copy.deepcopy(states())
        captured_inputs = inputs()
        result = original(*args, **kwargs)
        self.records.append((spec, captured_inputs, outputs(result),
                             before, copy.deepcopy(states())))
        return result


class ManifestTests(unittest.TestCase):
    def test_unique_symbols_and_all_u_rows(self):
        value = adapter.load_manifest()
        self.assertTrue(value['symbols'])
        self.assertEqual({u for r in value['symbols'] for u in r['u_rows']},
                         {f'U{i}' for i in range(1, 8)})
        for row in value['symbols']:
            self.assertEqual(len(row['sha256']), 64)
            self.assertGreater(row['line'], 0)
            self.assertTrue(row['inputs'] or row['outputs'])

    def test_image_and_archive_provenance_are_distinct(self):
        value = adapter.load_manifest()
        self.assertFalse(value['native_extraction_ready'])
        self.assertTrue(value['missing'])
        self.assertIsNone(value['sources']['a367']['image_digest'])
        self.assertEqual(value['sources']['a367']['commit'],
                         '6d8724577dabbee5fa0bbc70c4d927c6174c8d8a')
        self.assertFalse(value['sources']['reopen-image']['certified_as_A367'])
        self.assertFalse(value['sources']['reopen-image']['certified_as_27b'])
        archive = [r for r in value['symbols'] if r['source_id'] == 'a367']
        self.assertTrue(any(r.get('image_file_sha256') and
                            r['image_file_sha256'] != r['sha256'] for r in archive))

    def test_stage2_names_do_not_silently_replace_stage1_rows(self):
        rows = adapter.load_manifest()['symbols']
        self.assertTrue(any(r.get('stage2_u_rows') != r['u_rows']
                            for r in rows if r.get('stage2_u_rows')))
        gdn = next(r for r in rows if r['id'] ==
                   'flash.QwenGatedDeltaNetAttention.forward_xpu')
        self.assertIn('U4', gdn['u_rows'])
        self.assertIn('U1', gdn['stage2_u_rows'])

    def test_all_real_symbols_hashes_and_argument_selectors(self):
        names = {'a367': 'PACKET4_A367_SOURCE',
                 'reopen-image': 'PACKET4_IMAGE_SOURCE'}
        if not all(os.environ.get(name) for name in names.values()):
            self.skipTest('source trees not supplied; remaining tests still run')
        roots = {source: os.environ[name] for source, name in names.items()}
        manifest = adapter.load_manifest()
        counts = adapter.verify_sources(manifest, roots)
        self.assertTrue(all(counts.values()))
        for row in manifest['symbols']:
            with self.subTest(symbol=row['id']):
                fn = adapter.source_symbol(row, roots)
                actual = [a.arg for a in fn.args.posonlyargs + fn.args.args
                          + fn.args.kwonlyargs]
                self.assertEqual(row['arguments'], actual)
                self.assertEqual(row['sha256'],
                                 file_hash(Path(roots[row['source_id']]) / row['file']))


class BindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='packet4-adapter-cpu-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / 'packet4_synthetic_boundary.py'
        self.path.write_text(SOURCE)
        spec = importlib.util.spec_from_file_location('packet4_synthetic_boundary', self.path)
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(self.module)
        self.spy = Spy()
        self.fake_torch, self.wrapper = graph_objects()

    def row(self, method='forward', cls='Boundary'):
        tree = ast.parse(SOURCE)
        scope = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                     and n.name == cls) if cls else tree
        fn = next(n for n in scope.body if isinstance(n, ast.FunctionDef)
                  and n.name == method)
        return dict(id='synthetic.' + method, source_id='synthetic',
                    file=self.path.name, sha256=file_hash(self.path), line=fn.lineno,
                    module=self.module.__name__, **{'class': cls}, method=method,
                    inputs=['arg.x'], outputs=['result'], state=[],
                    u_rows=['U4'], operator='gdn_recurrence',
                    rounding='synthetic CPU only',
                    arguments=[a.arg for a in fn.args.args])

    def guard(self):
        return adapter.eager_guard(self.spy.config, self.fake_torch, self.wrapper)

    def bind(self, row=None, recorder=None, states=None, owner=None, meta=metadata):
        return adapter.bind(recorder or self.spy, row or self.row(),
                            owner or self.module.Boundary, meta, states,
                            verified_path=self.path)

    def test_output_identity_original_once_and_descriptor_restored(self):
        original = inspect.getattr_static(self.module.Boundary, 'forward')
        obj = self.module.Boundary(torch.zeros(1))
        x = torch.tensor([[1., 2.]])
        with self.guard(), self.bind():
            self.assertIs(obj.forward(x), x)
        self.assertEqual(obj.calls, 1)
        self.assertEqual(len(self.spy.records), 1)
        self.assertTrue(torch.equal(x, torch.tensor([[1., 2.]])))
        self.assertIs(inspect.getattr_static(self.module.Boundary, 'forward'), original)

    def test_staticmethod_binding_and_descriptor_restoration(self):
        original = inspect.getattr_static(self.module.Boundary, 'static')
        x = torch.ones(1, 2)
        with self.guard(), self.bind(self.row('static')):
            self.assertIs(self.module.Boundary.static(x), x)
        self.assertIs(inspect.getattr_static(self.module.Boundary, 'static'), original)
        self.assertIsInstance(original, staticmethod)

    def test_in_place_output_selector_preserves_none_return(self):
        row = self.row('in_place')
        row['outputs'] = ['arg.out']
        x, out = torch.ones(1, 2), torch.zeros(1, 2)
        obj = self.module.Boundary(torch.zeros(1))
        with self.guard(), self.bind(row):
            self.assertIsNone(obj.in_place(x, out))
        self.assertEqual(obj.calls, 1)
        self.assertIs(self.spy.records[0][2]['arg.out'], out)
        self.assertTrue(torch.equal(out, x))

    def test_exception_restores_original(self):
        original = inspect.getattr_static(self.module.Boundary, 'forward')
        obj = self.module.Boundary(torch.zeros(1))
        with self.assertRaisesRegex(RuntimeError, 'synthetic operator failure'):
            with self.guard(), self.bind():
                obj.forward(torch.ones(1, 2), fail=True)
        self.assertEqual(obj.calls, 1)
        self.assertIs(inspect.getattr_static(self.module.Boundary, 'forward'), original)

    def test_no_guard_refuses_before_wrapping(self):
        with self.assertRaisesRegex(ValueError, 'eager_guard'):
            with self.bind():
                self.fail('unguarded binding admitted')

    def test_graph_entry_is_blocked_before_metadata(self):
        called = []
        obj = self.module.Boundary(torch.zeros(1))
        graph_fn = self.fake_torch.xpu.graph
        def meta(*args):
            called.append(True)
            return metadata(*args)
        with self.guard(), self.bind(meta=meta):
            with self.assertRaisesRegex(RuntimeError, 'graph capture refused'):
                self.fake_torch.xpu.graph()
            with self.assertRaisesRegex(RuntimeError, 'graph capture refused'):
                self.fake_torch.xpu.XPUGraph().capture_begin()
            with self.assertRaisesRegex(RuntimeError, 'graph capture refused'):
                self.wrapper()()
        self.assertEqual(called, [])
        self.assertEqual(obj.calls, 0)
        self.assertIs(self.fake_torch.xpu.graph, graph_fn)

    def test_capture_config_change_refuses_before_metadata(self):
        called = []
        def meta(*args):
            called.append(True)
            return metadata(*args)
        obj = self.module.Boundary(torch.zeros(1))
        with self.guard(), self.bind(meta=meta):
            self.spy.config['graph_mode'] = 'FULL'
            with self.assertRaisesRegex(ValueError, 'eager only'):
                obj.forward(torch.ones(1, 2))
        self.assertEqual(called, [])
        self.assertEqual(obj.calls, 0)

    def test_compilation_refuses_before_metadata(self):
        obj = self.module.Boundary(torch.zeros(1))
        called = []
        def meta(*args):
            called.append(True)
            return metadata(*args)
        with self.guard(), self.bind(meta=meta):
            with patch('torch.compiler.is_compiling', return_value=True):
                with self.assertRaisesRegex(ValueError, 'compiled region'):
                    obj.forward(torch.ones(1, 2))
        self.assertEqual(called, [])
        self.assertEqual(obj.calls, 0)

    def test_guard_requires_torch_capture_targets(self):
        with self.assertRaisesRegex(ValueError, 'no torch capture'):
            with adapter.eager_guard(dict(EAGER), SimpleNamespace(), self.wrapper):
                self.fail('empty capture guard admitted')

    def test_source_hash_mismatch_refused(self):
        row = self.row()
        row['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            adapter.source_symbol(row, {'synthetic': self.root})
        with self.guard(), self.assertRaisesRegex(ValueError, 'source bytes changed'):
            with self.bind(row):
                self.fail('changed source admitted')

    def test_wrong_class_in_same_file_refused(self):
        with self.guard(), self.assertRaisesRegex(ValueError, 'symbol mismatch'):
            with self.bind(owner=self.module.Other):
                self.fail('different class admitted')

    def test_argument_selector_local_and_path_escape_refused(self):
        row = self.row()
        row['inputs'] = ['arg.local_intermediate']
        with self.assertRaisesRegex(ValueError, 'boundary argument'):
            adapter.source_symbol(row, {'synthetic': self.root})
        row = self.row()
        row['file'] = '../escape.py'
        with self.assertRaisesRegex(ValueError, 'unsafe source path'):
            adapter.source_symbol(row, {'synthetic': self.root})

    def test_unknown_source_line_refused(self):
        row = self.row()
        row['line'] += 1
        with self.assertRaisesRegex(ValueError, 'method/line missing'):
            adapter.source_symbol(row, {'synthetic': self.root})

    def test_stateful_binding_requires_bounded_callback(self):
        row = self.row()
        row['requires_state_views'] = True
        with self.guard(), self.assertRaisesRegex(ValueError, 'bounded touched-state'):
            with self.bind(row):
                self.fail('unbound state admitted')

    def test_state_before_after_uses_original_mutation(self):
        row = self.row()
        row['requires_state_views'] = True
        obj = self.module.Boundary(torch.zeros(3))
        def states(row, bound):
            return {'touched': bound['self'].state[:1]}
        with self.guard(), self.bind(row, states=states):
            obj.forward(torch.ones(1, 2))
        before, after = self.spy.records[0][3:]
        self.assertTrue(torch.equal(before['touched'], torch.zeros(1)))
        self.assertTrue(torch.equal(after['touched'], torch.ones(1)))

    def test_empty_state_view_refused_before_original(self):
        row = self.row()
        row['requires_state_views'] = True
        obj = self.module.Boundary(torch.zeros(1))
        with self.guard(), self.bind(row, states=lambda *args: {}):
            with self.assertRaisesRegex(ValueError, 'missing touched state'):
                obj.forward(torch.ones(1, 2))
        self.assertEqual(obj.calls, 0)

    def test_unadmitted_call_still_runs_original_once(self):
        obj = self.module.Boundary(torch.zeros(1))
        x = torch.ones(1, 2)
        with self.guard(), self.bind(meta=lambda *args: None):
            self.assertIs(obj.forward(x), x)
        self.assertEqual(obj.calls, 1)
        self.assertEqual(self.spy.records, [])

    def test_metadata_does_not_infer_missing_or_device_values(self):
        self.assertIsNone(adapter.make_spec(self.row(), None))
        for changes in ({'M': 3}, {'positions': torch.tensor([7])},
                        {'positions': [True]}, {'valid_rows': [1]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                adapter.make_spec(self.row(), dict(metadata(None, None), **changes))
        with self.assertRaisesRegex(ValueError, 'incomplete CPU'):
            adapter.make_spec(self.row(), {'M': 1})

    def test_select_nested_output_and_state(self):
        tensor = torch.ones(1)
        self.assertIs(adapter.select('result.0.value', {}, [{'value': tensor}]), tensor)
        obj = self.module.Boundary(tensor)
        self.assertIs(adapter.select('arg.self.state', {'self': obj}), tensor)
        with self.assertRaisesRegex(ValueError, 'unknown tensor selector'):
            adapter.select('locals.hidden', {})

    def test_install_validates_explicit_subset_and_restores(self):
        row = self.row()
        manifest = {'symbols': [row]}
        args = dict(source_id='synthetic', roots={'synthetic': self.root},
                    owners={self.module.__name__ + '.Boundary': self.module.Boundary},
                    metadata=metadata, manifest=manifest)
        obj = self.module.Boundary(torch.zeros(1))
        with self.guard(), adapter.install(self.spy, **args, symbol_ids=[row['id']]):
            self.assertIsInstance(obj.forward(torch.ones(1, 2)), torch.Tensor)
        with self.assertRaisesRegex(ValueError, 'unknown symbol selection'):
            with adapter.install(self.spy, **args, symbol_ids=['missing']):
                self.fail('unknown subset admitted')

    def test_real_cpu_torch_operator_alias_lazy_schema_and_identity(self):
        # This registers a synthetic CPU op only; no vLLM package is imported.
        library = torch.library.Library('vllm', 'FRAGMENT')
        name = 'packet4_adapter_cpu_identity'
        library.define(name + '(Tensor x) -> Tensor')
        calls = []
        def native(x):
            calls.append(True)
            return x
        library.impl(name, native, 'CPU')
        self.addCleanup(library._destroy)
        row = self.row('native_boundary', cls=None)
        row.update(runtime_owner='torch.ops.vllm', runtime_attribute=name,
                   arguments=['x'])
        x = torch.ones(1, 2)
        with self.guard(), self.bind(row, owner=torch.ops.vllm):
            self.assertIs(getattr(torch.ops.vllm, name)(x), x)
        self.assertEqual(len(calls), 1)
        self.assertEqual(getattr(torch.ops.vllm, name).default._schema.name,
                         'vllm::' + name)

    def test_real_recorder_boundary_and_state_artifacts(self):
        oracle = {'rows': [{'prompt_id': str(i), 'prompt_sha256': token_hash([i]),
                           'token_ids': [1], 'sha256': token_hash([1])}
                          for i in range(12)]}
        recorder = Recorder(self.root / 'recording', '27b', mock_identity(),
                            dict(EAGER), oracle, '0', 200000, 16)
        row = self.row()
        row['requires_state_views'] = True
        obj = self.module.Boundary(torch.zeros(1))
        x = torch.tensor([[1., 2.]])
        def states(row, bound):
            return {'touched': bound['self'].state[:1]}
        with self.guard(), self.bind(row, recorder=recorder, states=states):
            self.assertIs(obj.forward(x), x)
        result = recorder.finish([1])
        self.assertEqual(len(result['fixtures']), 1)
        fixture = json.loads((recorder.root / result['fixtures'][0]['path']).read_text())
        before = load_tensor(recorder.root, fixture['state_before'][0], 10000)
        after = load_tensor(recorder.root, fixture['state_after'][0], 10000)
        self.assertTrue(torch.equal(before, torch.zeros(1)))
        self.assertTrue(torch.equal(after, torch.ones(1)))
        self.assertIsNone(fixture['diagnostic']['reference_call'])
        self.assertEqual(fixture['status'], 'extracted-unverified')

    def test_driver_interface_refuses_missing_native_session(self):
        with self.assertRaisesRegex(RuntimeError, 'native session driver missing'):
            adapter.run(SimpleNamespace(), Recorder)


if __name__ == '__main__':
    unittest.main()

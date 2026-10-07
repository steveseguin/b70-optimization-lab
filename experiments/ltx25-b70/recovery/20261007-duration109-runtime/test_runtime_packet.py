#!/usr/bin/env python3
"""Read-only builder controls: never invoke a successful packet build."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('resolution_packet_review', HERE / 'runtime_packet.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def literal(raw, name):
    tree = ast.parse(raw)
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


class PacketControls(unittest.TestCase):
    def test_activation_keeps_original_receipt_baseline_and_checks_serializers(self):
        manifest = copy.deepcopy(B._parent_manifest)
        manifest['runtime']['files'].update(B.SERIALIZER_FILES)
        before = copy.deepcopy(manifest)
        activate = Mock(return_value='activated')
        adapter = SimpleNamespace(activate_dependencies=activate)
        with patch.object(B, 'BASE', adapter), patch.object(B, 'sha', side_effect=lambda p: B.SERIALIZER_FILES[str(p)]), \
                patch.object(B, 'verify_runtime', side_effect=AssertionError('premature Torch import')):
            self.assertEqual(B.activate_dependencies(B.PACKET, manifest), 'activated')
        activate.assert_called_once_with(B.PACKET, B._parent_manifest)
        self.assertEqual(manifest, before)

    def test_activation_refuses_missing_changed_extra_baseline_or_disk_identity(self):
        good = copy.deepcopy(B._parent_manifest)
        good['runtime']['files'].update(B.SERIALIZER_FILES)
        serializer = next(iter(B.SERIALIZER_FILES))
        for change in ('missing', 'changed', 'extra', 'baseline', 'disk'):
            with self.subTest(change=change):
                manifest = copy.deepcopy(good)
                if change == 'missing': del manifest['runtime']['files'][serializer]
                if change == 'changed': manifest['runtime']['files'][serializer] = '0' * 64
                if change == 'extra': manifest['runtime']['files']['/unbound.py'] = '0' * 64
                if change == 'baseline': manifest['runtime']['python_executable'] = '/another/python'
                activate = Mock()
                with patch.object(B, 'BASE', SimpleNamespace(activate_dependencies=activate)), \
                        patch.object(B, 'sha', side_effect=lambda p: '0' * 64 if change == 'disk' else B.SERIALIZER_FILES[str(p)]):
                    with self.assertRaises(RuntimeError): B.activate_dependencies(B.PACKET, manifest)
                activate.assert_not_called()

    def test_runtime_adapter_uses_exposed_verifier_not_private_fingerprint_api(self):
        baseline = copy.deepcopy(B._parent_manifest['runtime'])
        verify = Mock(side_effect=lambda value: copy.deepcopy(value))
        adapter = SimpleNamespace(verify_runtime=verify)
        self.assertFalse(hasattr(adapter, 'runtime_fingerprints'))
        with patch.object(B, 'BASE', adapter), patch.object(B, 'sha', side_effect=lambda p: B.SERIALIZER_FILES[str(p)]):
            actual = B.runtime_fingerprints()
            self.assertEqual(actual['files'], {**baseline['files'], **B.SERIALIZER_FILES})
            verify.assert_called_once_with(baseline)
            self.assertEqual(B.verify_runtime(actual), actual)
        self.assertEqual(B._parent_manifest['runtime'], baseline)

    def test_successor_identity_explicit_in_path_status_and_transition(self):
        self.assertEqual(B.PACKET.name, 'prepared-duration-pilot-109')
        self.assertEqual(B.RUN_NAME, 'encoder-server-duration-pilot-109-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49')
        self.assertIn(b'Packet109 three-fixture49-frame resource pilot', B.STATUS)
        tree=ast.parse(B.regular(HERE/'runtime_packet.py'))
        transitions=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Dict):
                fields={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant)}
                if 'schema' in fields and isinstance(fields['schema'],ast.Constant) and fields['schema'].value=='ltx.resolution101.transition.v1':
                    transitions.append(ast.literal_eval(fields['packet_revision']))
        self.assertEqual(transitions,['109','109'])

    def test_duration_guard_installed_and_all107_trace_runtime_absent(self):
        extras=B.extra_files(B.AUTHOR,B.regular(B.PLAN))
        self.assertEqual(B.RUNTIME_MODULES['duration_guard.py'],'ltx_duration_guard.py')
        self.assertEqual(extras['source/scripts/ltx_duration_guard.py'],B.regular(HERE/'duration_guard.py'))
        self.assertEqual(extras['resolution/components/duration_guard.py'],B.regular(HERE/'duration_guard.py'))
        for name in ('sparse_transport.py','transport_gate.py','sparse_transport_overlay.py',
                     'driver_accounting.py','driver_accounting_runner.py'):
            self.assertNotIn(name,B.COMPONENTS)
            self.assertNotIn(name,B.RUNTIME_MODULES)
        for path,raw in {**B.source_delta(B.AUTHOR),**extras}.items():
            if path.startswith('source/') and path.endswith('.py'):
                self.assertNotIn(b'ltx_sparse_transport107',raw,path)
                self.assertNotIn(b'_transport107',raw,path)

    def test_constructor99b_and_reviewed108b_provenance_are_distinct_and_bound(self):
        self.assertEqual(B.PARENT.name,'prepared-encoder-upstream-99b')
        self.assertEqual(B.PREDECESSOR.name,'prepared-duration-pilot-108b')
        extras=B.extra_files(B.AUTHOR,B.regular(B.PLAN))
        self.assertEqual(B.digest(extras['provenance/packet99b-manifest.json']),B.PARENT_SHA)
        self.assertEqual(B.digest(extras['provenance/reviewed-predecessor108b-manifest.json']),B.PREDECESSOR_SHA)
        prior=json.loads(extras['provenance/reviewed-predecessor108b-manifest.json'])
        self.assertEqual(prior['resolution101']['packet_revision'],'108b')
        self.assertEqual(prior['resolution101']['parent_manifest_sha256'],B.PARENT_SHA)
        self.assertEqual(prior['resolution101']['control']['workers'],2)
        self.assertEqual(prior['rope99b'],B._parent_manifest['rope99b'])
        schedule=json.loads(extras['resolution/setup-schedule.json'])['schedule']
        self.assertEqual(schedule['submitted_requests'],29)
        self.assertEqual(schedule['raw_capture_requests'],22)
        self.assertEqual(schedule['capture_cap'],22)
        tree=ast.parse(B.regular(HERE/'runtime_packet.py'))
        transitions=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Dict):
                fields={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant)}
                if 'schema' in fields and isinstance(fields['schema'],ast.Constant) and fields['schema'].value=='ltx.resolution101.transition.v1':
                    self.assertEqual(ast.literal_eval(fields['control'])['workers'],2)
                    transitions.append(ast.unparse(fields['reviewed_predecessor']))
        self.assertEqual(len(transitions),2)
        self.assertEqual(transitions[0],transitions[1])
        with tempfile.TemporaryDirectory() as tmp:
            predecessor=Path(tmp);(predecessor/'manifest.json').write_text('{}')
            with patch.object(B,'PREDECESSOR',predecessor):
                with self.assertRaisesRegex(RuntimeError,'predecessor manifest changed'):
                    B.extra_files(B.AUTHOR,B.regular(B.PLAN))

    def test_default_is_plan_only_with_no_build_or_packet_write(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['runtime_packet.py']), patch.object(B, 'build') as build, \
                patch.object(B, 'write_new') as write, contextlib.redirect_stdout(output):
            B.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'plan-only')
        self.assertIs(result['materialized'], False)
        self.assertEqual(result['model_requests'], 0)
        build.assert_not_called(); write.assert_not_called()

    def test_missing_component_refuses_inventory(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(B, 'AUTHOR', Path(tmp)):
            with self.assertRaisesRegex(RuntimeError, 'Integration incomplete'): B.input_inventory()

    def test_build_requires_explicit_stop_and_reviewed_inventory_before_write(self):
        with patch.object(B, 'write_new') as write:
            with self.assertRaisesRegex(RuntimeError, 'parent cleanly stopped'): B.build('a' * 64)
            with self.assertRaisesRegex(RuntimeError, 'Reviewed source inventory'): B.build('0' * 64, True)
        write.assert_not_called()

    def test_insufficient_disk_refuses_before_destination_creation(self):
        inventory = B.input_inventory()
        with tempfile.TemporaryDirectory() as tmp:
            packet = Path(tmp) / 'not-created'
            storage = Mock(inspect_destination=Mock(return_value={'admitted': False}))
            with patch.object(B, 'PACKET', packet), patch.object(B.BASE, 'verify_packet', return_value=B._parent_manifest), \
                    patch.object(B, 'module', return_value=storage), patch.object(B, 'source_delta') as delta:
                with self.assertRaisesRegex(RuntimeError, '50GiB reserve'): B.build(B.digest(B.canonical(inventory)), True)
                self.assertFalse(packet.exists())
                delta.assert_not_called()
                storage.inspect_destination.assert_called_once_with(packet, 50 * 1024**3, 384 * 1024**2)

    def test_delta_syntax_and_required_vae_tripwire_mirrors(self):
        delta = B.source_delta(B.AUTHOR)
        for path, raw in delta.items():
            if path.endswith('.py'): ast.parse(raw, filename=path)
        new_sd_sha = B.digest(delta['source/comfy/sd.py'])
        for path in ('source/scripts/na_axis_decode_node.py',
                     'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'):
            raw = delta.get(path, B.regular(B.PARENT / path))
            self.assertEqual(literal(raw, 'SD_SHA'), new_sd_sha,
                             'Native sd.py overlay must repin both NA startup tripwires')
        self.assertEqual(delta['source/scripts/na_axis_decode_node.py'],
                         delta['source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'])

    def test_launcher_preserves_preflight_rope_and_identity_order(self):
        result = B.launcher_source(B.regular(B.PARENT / B.LAUNCHER)).decode()
        ordered = [result.index('journal-after-preflight.txt'),
                   result.index('rope_compat = common.install_rope_compat(packet)'),
                   result.index("write_json(run / 'server-identity.json', identity)"),
                   result.index('resolution_integration.install('),
                   result.index("runpy.run_path(str(packet / 'source/main.py')")]
        self.assertEqual(ordered, sorted(ordered))
        self.assertIn(repr(B.RUN_NAME), result)
        self.assertIn('runtime99b_transition', result)
        self.assertIn('resolution101_transition', result)
        self.assertIn('torch.use_deterministic_algorithms(True, warn_only=False)', result)

    def test_explicit_environment_refuses_historical_configuration(self):
        good = {'LTX_OUTPUT_SIZE': '640x384', 'LTX_BUSY_WINDOWS': '0',
                'LTX_SAMPLER_PLACEMENT': 'two-way20-28', 'LTX_SAMPLER_WORKERS': '2',
                'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
        with patch.dict(B.os.environ, good, clear=True): B.check_control_environment()
        for field, value in [('LTX_SAMPLER_WORKERS', '1'), ('LTX_SAMPLER_WORKERS', '3'), ('LTX_OUTPUT_SIZE', '256x256'),
                             ('LTX_SAMPLER_PLACEMENT', 'two-way')]:
            with patch.dict(B.os.environ, dict(good, **{field: value}), clear=True):
                with self.assertRaises(RuntimeError): B.check_control_environment()

    def test_components_preverified_before_any_successor_import(self):
        # Build no packet: isolate the verification ordering on one deliberately
        # corrupted inventory entry. Parent verifier remains a CPU stub here.
        raw = json.dumps({'files': {'resolution/components/geometry_overlay.py': 'b' * 64}}).encode()
        with patch.object(B.BASE, 'verify_packet', return_value=B._parent_manifest), \
                patch.object(B, 'sha', side_effect=lambda p: 'a' * 64), \
                patch.object(B, 'regular', side_effect=lambda p: B.STATUS if p.name == 'STATUS.txt' else raw), \
                patch.object(B, 'source_delta') as delta, patch.object(B, 'extra_files') as extras:
            with self.assertRaisesRegex(RuntimeError, 'before component import'):
                B.verify_packet(B.PACKET, 'a' * 64)
            delta.assert_not_called(); extras.assert_not_called()

    def test_semantic_manifest_preserves_parent_and_updates_extensions(self):
        delta = B.source_delta(B.AUTHOR)
        files = dict(B._parent_manifest['files'])
        files.update({p: B.digest(raw) for p, raw in delta.items()})
        for name, target in B.RUNTIME_MODULES.items():
            files['source/scripts/' + target] = B.sha(HERE / name)
        files['resolution/components/runtime_packet.py'] = B.sha(HERE / 'runtime_packet.py')
        before = copy.deepcopy(B._parent_manifest)
        result = B.semantic_manifest(B._parent_manifest, files, {'qualification': False})
        self.assertEqual(B._parent_manifest, before)
        self.assertEqual(result['rope99b'], before['rope99b'])
        expected_runtime=copy.deepcopy(before['runtime'])
        expected_runtime['files'].update(B.SERIALIZER_FILES)
        self.assertEqual(result['runtime'], expected_runtime)
        self.assertEqual(result['sampler_placement']['placements']['two-way20-28'],
                         [['xpu:0', 0, 20], ['xpu:1', 20, 48]])
        self.assertEqual(result['graph_capture']['adapter_sha256'], B.PLACEMENT_FILES['source/scripts/ltx_graph_capture.py'])
        self.assertEqual(result['sampler_shared_pool']['adapter_sha256'], result['graph_capture']['adapter_sha256'])
        self.assertEqual({Path(p).name:h for p,h in B.SERIALIZER_FILES.items()}, {
            'torch.py':'f3f476d1f8c04fe65fa3797426556a0b7afa43f8c4db9db6b799c7cf84748f3d',
            '_safetensors_rust.abi3.so':'e6f17a9e9846bc2bc4ad94cc5431746b59785de3d2681ef2666e8890ae192dfb'})
        self.assertFalse(result['resolution101']['qualification'])
        for name in result['extension_sha256s']:
            if 'source/scripts/' + name in files:
                self.assertEqual(result['extension_sha256s'][name], files['source/scripts/' + name])
            else:
                self.assertEqual(result['extension_sha256s'][name], before['extension_sha256s'][name])


GRAPH_NODE = 'source/custom_nodes/ltx_graph_capture_lab/__init__.py'
GRAPH_HELPER = 'source/scripts/ltx_graph_capture.py'
GRAPH_WRAPPER = 'source/scripts/graph_capture_node.py'
MIRRORS = {
    'pipeline_node.py': 'ltx_pipeline_lab',
    'pipeline_sampler_node.py': 'ltx_pipeline_sampler_lab',
    'pipeline_decode_node.py': 'ltx_pipeline_decode_lab',
    'na_axis_decode_node.py': 'ltx_na_axis_decode_lab',
}


def registration(raw):
    """Read static exports, requiring every exported class to exist locally."""
    tree = ast.parse(raw)
    values = [n.value for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'NODE_CLASS_MAPPINGS'
                      for t in n.targets)]
    if len(values) != 1 or not isinstance(values[0], ast.Dict):
        raise ValueError('Missing unique static node registration')
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    result = {}
    for key, value in zip(values[0].keys, values[0].values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)
                and isinstance(value, ast.Name) and value.id in classes
                and key.value not in result):
            raise ValueError('Invalid or missing registered node class')
        result[key.value] = value.id
    return result


class BuilderRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # source_delta only returns bytes; never materialize or execute nodes.
        cls.delta = B.source_delta(B.AUTHOR)

    def effective(self, path):
        return self.delta[path] if path in self.delta else B.regular(B.PARENT / path)

    def test_graph_gate_wrapper_and_export_preserved(self):
        before = B.regular(B.PARENT / GRAPH_NODE)
        after = self.effective(GRAPH_NODE)
        self.assertEqual(before, B.regular(B.PARENT / GRAPH_WRAPPER))
        self.assertEqual(after, before)
        self.assertEqual(self.effective(GRAPH_WRAPPER), before)
        self.assertEqual(registration(after), registration(before))
        self.assertEqual(registration(after), {'LTXGraphCaptureGate': 'LTXGraphCaptureGate'})

    def test_preserved_wrapper_imports_canonical_duration_aware_adapter(self):
        imports = [(alias.name, alias.asname)
                   for n in ast.parse(self.effective(GRAPH_NODE)).body
                   if isinstance(n, ast.Import) for alias in n.names]
        self.assertIn(('ltx_graph_capture', 'adapter'), imports)
        helper = self.effective(GRAPH_HELPER)
        self.assertEqual(helper, B.regular(B.PLACEMENT_SOURCE / GRAPH_HELPER))
        # The qualified placement helper changes only its shard-source pin;
        # numerical graph logic and the actual registration wrapper stay intact.
        parent_helper = B.regular(B.PARENT / GRAPH_HELPER)
        self.assertEqual(helper, parent_helper.replace(
            b'9caaec0aeb68e9f391fab5ae9b6a63e464aa62a99e1ffc449775b3687d2149b2',
            b'a000ccd309e70b2f41167c84b73aae01caf50f9cd38d1256a21f6cc7b0dd2ef3'))
        helper_imports = [(alias.name, alias.asname)
                          for n in ast.parse(helper).body if isinstance(n, ast.Import)
                          for alias in n.names]
        self.assertIn(('ltx_output_size_98', 'size98'), helper_imports)
        self.assertEqual(B.RUNTIME_MODULES['duration_guard.py'], 'ltx_duration_guard.py')
        self.assertNotIn(b'ltx_sparse_transport107',helper)
        self.assertIn(b'FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = 49, 7, 51, 96480',
                      self.effective('source/scripts/ltx_output_size_98.py'))

    def test_old_helper_as_wrapper_error_is_rejected(self):
        # This is the precise failed107 substitution, not an invented mutation.
        with self.assertRaisesRegex(ValueError, 'node registration'):
            registration(self.effective(GRAPH_HELPER))

    def test_export_without_class_definition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'registered node class'):
            registration(b"NODE_CLASS_MAPPINGS = {'LTXGraphCaptureGate': LTXGraphCaptureGate}\n")

    def test_other_mirrors_are_actual_nodes_and_preserve_exports(self):
        for script, package in MIRRORS.items():
            with self.subTest(script=script):
                canonical = 'source/scripts/' + script
                node = 'source/custom_nodes/' + package + '/__init__.py'
                before = B.regular(B.PARENT / canonical)
                self.assertEqual(before, B.regular(B.PARENT / node))
                self.assertEqual(self.effective(canonical), self.effective(node))
                self.assertEqual(registration(before), registration(self.effective(node)))


if __name__ == '__main__': unittest.main()

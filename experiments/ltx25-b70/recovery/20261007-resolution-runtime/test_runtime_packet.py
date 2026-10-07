#!/usr/bin/env python3
"""Read-only builder controls: never invoke a successful packet build."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
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
    def test_successor_identity_explicit_in_path_status_and_transition(self):
        self.assertEqual(B.PACKET.name, 'prepared-resolution-w2-102')
        self.assertEqual(B.RUN_NAME, 'encoder-server-resolution-w2-102-two-way-w2-b1-p1-dxpu2-s640x384')
        self.assertIn(b'Packet102 W2 candidate after successful W1 packet101c', B.STATUS)
        tree=ast.parse(B.regular(HERE/'runtime_packet.py'))
        transitions=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Dict):
                fields={k.value:v for k,v in zip(node.keys,node.values) if isinstance(k,ast.Constant)}
                if 'schema' in fields and isinstance(fields['schema'],ast.Constant) and fields['schema'].value=='ltx.resolution101.transition.v1':
                    transitions.append(ast.literal_eval(fields['packet_revision']))
        self.assertEqual(transitions,['102','102'])

    def test_constructor99b_and_reviewed101c_provenance_are_distinct_and_bound(self):
        self.assertEqual(B.PARENT.name,'prepared-encoder-upstream-99b')
        self.assertEqual(B.PREDECESSOR.name,'prepared-resolution-reference-101c')
        extras=B.extra_files(B.AUTHOR,B.regular(B.PLAN))
        self.assertEqual(B.digest(extras['provenance/packet99b-manifest.json']),B.PARENT_SHA)
        self.assertEqual(B.digest(extras['provenance/reviewed-predecessor101c-manifest.json']),B.PREDECESSOR_SHA)
        prior=json.loads(extras['provenance/reviewed-predecessor101c-manifest.json'])
        self.assertEqual(prior['resolution101']['packet_revision'],'101c')
        self.assertEqual(prior['resolution101']['parent_manifest_sha256'],B.PARENT_SHA)
        self.assertEqual(prior['resolution101']['control']['workers'],1)
        self.assertEqual(prior['rope99b'],B._parent_manifest['rope99b'])
        schedule=json.loads(extras['resolution/setup-schedule.json'])['schedule']
        self.assertEqual(schedule['submitted_requests'],36)
        self.assertEqual(schedule['raw_capture_requests'],29)
        self.assertEqual(schedule['capture_cap'],32)
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
                'LTX_SAMPLER_PLACEMENT': 'two-way', 'LTX_SAMPLER_WORKERS': '2',
                'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
        with patch.dict(B.os.environ, good, clear=True): B.check_control_environment()
        for field, value in [('LTX_SAMPLER_WORKERS', '1'), ('LTX_SAMPLER_WORKERS', '3'), ('LTX_OUTPUT_SIZE', '256x256'),
                             ('LTX_SAMPLER_PLACEMENT', 'two-way20-28')]:
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
        self.assertEqual(result['runtime'], before['runtime'])
        self.assertFalse(result['resolution101']['qualification'])
        for name in result['extension_sha256s']:
            if 'source/scripts/' + name in files:
                self.assertEqual(result['extension_sha256s'][name], files['source/scripts/' + name])
            else:
                self.assertEqual(result['extension_sha256s'][name], before['extension_sha256s'][name])


if __name__ == '__main__': unittest.main()

"""CPU tests (packet114 builder): transforms of the sealed 113 files, pinned identities, node inputs,
and the launcher naming preflight on a fake results root."""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime_packet as rp  # noqa: E402
import stream_contract as c  # noqa: E402
import plan as plan_module  # noqa: E402

COMPONENT_COPIES = ('session.py', 'integration.py', 'stream_contract.py', 'stream_receipts.py', 'stream_preview.py',
                    'stream_decode.py', 'latent_anchor.py', 'qualification_gate.py')


def transformed(path, fn):
    return fn(rp.regular(rp.PARENT / path))


class Identities(unittest.TestCase):
    def test_plan_file_is_the_reconstructed_plan_and_pins_agree(self):
        envelope = json.loads((HERE / 'stream-plan.json').read_text())
        self.assertEqual(envelope, plan_module.build_plan())
        self.assertEqual(envelope['plan_sha256'], rp.PLAN_SHA)
        import session
        self.assertEqual(session.PLAN_SHA256, rp.PLAN_SHA)
        self.assertEqual(rp.QIDS, {c.variant(f, p, a): c.qualification_id(f, p, a)
                                   for f in c.FRAME_CHOICES for p in c.PLACEMENTS for a in c.ANCHORS})
        self.assertEqual(len(envelope['plan']['qualification'][0]['graph_sha256']), 16)
        self.assertEqual(envelope['plan']['naming']['fixed_names'], c.fixed_names())

    def test_inventory_and_assembly_fit_build_allowance(self):
        result = rp.inspect_assembly()
        self.assertLess(result['source_payload_bytes'], rp.BUILD_ALLOWANCE)
        changed = result['changed_files']
        self.assertEqual(set(changed), {
            'provenance/packet113-manifest.json', 'resolution/stream-plan.json',
            'launch/serve-encoder.py', 'launch/encoder_runtime_common.py',
            'source/scripts/ltx_output_size_98.py', 'source/scripts/ltx_duration_guard.py',
            *('resolution/components/' + n for n in COMPONENT_COPIES + ('qualify_client.py', 'plan.py',
                                                                        'runtime_packet.py')),
            *('source/scripts/' + rp.MODULES[n] for n in COMPONENT_COPIES)})
        # Everything numerical stays byte-identical to the sealed 113 packet: the sampler, the decoder,
        # the native conditioning node, the safety contract, guards and bindings.
        for path in ('source/comfy/sd.py', 'source/scripts/ltx_graph_capture.py', 'source/scripts/graph_capture_node.py',
                     'source/scripts/native_safety.py', 'source/scripts/native_adapter.py',
                     'source/scripts/executor_guard.py', 'source/comfy_extras/nodes_lt.py',
                     'source/comfy_extras/nodes_lt_audio.py', 'source/comfy_extras/nodes_lt_upsampler.py',
                     'source/comfy/model_management.py', 'source/nodes.py', 'source/execution.py',
                     'source/scripts/candidate_safety.py', 'source/scripts/conditioning_guard.py',
                     'source/scripts/native_bindings.py', 'source/scripts/continuation_anchor.py',
                     'source/scripts/setup_gates.py', 'source/scripts/pipeline_decode_node.py',
                     'source/scripts/capture_node.py', 'source/custom_nodes/ltx_baseline_capture/__init__.py',
                     'source/custom_nodes/ltx_resolution_lab/__init__.py',
                     'source/scripts/ltx_graph_vae.py', 'source/scripts/graph_vae_node.py',
                     'source/comfy/ldm/lightricks/vae/na_diffusion_decoder.py'):
            self.assertNotIn(path, changed)

    def test_no_previous_prefix_outside_provenance(self):
        """Naming rule 3: the 112/113 prefixes appear only in provenance strings and comments."""
        for name in COMPONENT_COPIES:
            text = (HERE / name).read_text()
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn('stream112-', node.value, name)
                    self.assertNotIn('stream113-', node.value, name)


class Transforms(unittest.TestCase):
    def run_module(self, name, raw, frames, code, placement='two-way', anchor='latent'):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / (name + '.py')).write_bytes(raw)
            env = {'PATH': '/usr/bin', 'LTX_OUTPUT_SIZE': '256x256', 'LTX_STREAM_FRAMES': frames,
                   'LTX_SAMPLER_PLACEMENT': placement, 'LTX_ANCHOR': anchor}
            out = subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.path.insert(0, %r); ' % tmp + code],
                                 capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_geometry_follows_launch_frames_and_anchor(self):
        raw = transformed('source/scripts/ltx_output_size_98.py', lambda r: rp.geometry_source(r, rp.PLAN_SHA, rp.QIDS))
        for frames in ('49', '97'):
            for anchor in c.ANCHORS:
                out = self.run_module('ltx_output_size_98', raw, frames,
                                      'import ltx_output_size_98 as g; print(g.FRAMES, g.latent_shape(), '
                                      'g.image_shape(), g.AUDIO_LATENTS, g.AUDIO_SAMPLES, g.TOKENS, '
                                      'g._RESOLUTION_QUALIFICATION_ID, g._RESOLUTION_MODE, g.MAX_SIGNATURES_PER_BLOCK, '
                                      'g._RESOLUTION_PLAN_SHA256)', anchor=anchor)
                geo = c.geometry(int(frames))
                self.assertIn('%s %s' % (frames, tuple(geo['tensor_shapes']['video_latent'])), out)
                self.assertIn(' %d %d ' % (geo['audio_latents'], geo['audio_samples']), out)
                self.assertIn('(%d, %d)' % (geo['stage_tokens']['A'], geo['stage_tokens']['B']), out)
                self.assertIn(c.qualification_id(int(frames), 'two-way', anchor), out)
                self.assertIn('stream-candidate-114-v1 8 ' + rp.PLAN_SHA, out)
        out = self.run_module('ltx_output_size_98', raw, '97', 'import ltx_output_size_98 as g; '
                              'print(g._RESOLUTION_QUALIFICATION_ID)', placement='two-way20-28', anchor='frame')
        self.assertEqual(out, c.qualification_id(97, 'two-way20-28', 'frame'))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'ltx_output_size_98.py').write_bytes(raw)
            bad = subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.path.insert(0, %r); '
                                  'import ltx_output_size_98' % tmp], capture_output=True, text=True,
                                 env={'PATH': '/usr/bin', 'LTX_OUTPUT_SIZE': '256x256', 'LTX_STREAM_FRAMES': '25'})
        self.assertNotEqual(bad.returncode, 0)

    def test_capture_guard_shapes_at_97(self):
        raw = transformed('source/scripts/ltx_duration_guard.py', rp.capture_guard_source)
        out = self.run_module('ltx_duration_guard', raw, '97',
                              'import ltx_duration_guard as d; print(d.FULL_SHAPES, d.FULL_PAYLOAD_BYTES, '
                              'd.STAGE_A, d.RAW_CAPTURE_BUDGET)')
        g = c.geometry(97)
        shapes = eval(out.split('}')[0] + '}')
        self.assertEqual({k: list(v) for k, v in shapes.items()}, g['tensor_shapes'])
        self.assertIn(' %d ' % g['full_payload_bytes'], out)
        self.assertIn(str(tuple(g['stage_shapes']['A'])), out)
        parent = rp.regular(rp.PARENT / 'source/scripts/ltx_duration_guard.py').decode()
        self.assertEqual(len(raw.decode().splitlines()), len(parent.splitlines()))

    def test_launcher(self):
        launcher = transformed('launch/serve-encoder.py', rp.launcher_source).decode()
        self.assertIn('common.require(run_name == common.expected_run_name(),', launcher)
        self.assertNotIn('continuation-stream-113-', launcher)
        self.assertNotIn('continuation-stream-112-', launcher)
        self.assertEqual(rp.RUN_NAMES['97/two-way20-28/latent'],
                         'encoder-server-continuation-stream-114-latent-two-way20-28-w1-b1-p1-dxpu2-s256x256-f97')
        self.assertEqual(rp.RUN_NAMES['49/two-way20-28/frame'],
                         'encoder-server-continuation-stream-114-frame-two-way20-28-w1-b1-p1-dxpu2-s256x256-f49')
        self.assertEqual(len(set(rp.RUN_NAMES.values())), 8)
        tree = ast.parse(launcher)
        prepare = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_start')
        body = [ast.unparse(s) for s in prepare.body]
        verify = next(i for i, s in enumerate(body) if 'common.verify_packet(packet, digest)' in s)
        self.assertEqual(body[verify + 1], 'common.check_name_collisions(packet)')
        storage = next(i for i, s in enumerate(body) if 'common.admit_storage' in s)
        self.assertLess(verify, storage)
        # --check-only runs prepare_start (so the naming preflight) before it returns, and before any lock.
        launch = ast.unparse(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'launch'))
        self.assertLess(launch.index('prepare_start(packet, digest, run_name)'), launch.index('if check_only:'))
        self.assertLess(launch.index('if check_only:'), launch.index('fcntl.flock'))

    def test_control_environment(self):
        env = dict(rp.CONTROL_ENVIRONMENT, LTX_STREAM_TEXT_REUSE='1', LTX_STREAM_FRAMES='97',
                   LTX_SAMPLER_PLACEMENT='two-way20-28', LTX_ANCHOR='latent')
        saved = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(env)
            rp.check_control_environment()
            self.assertEqual(rp.expected_run_name(), rp.RUN_NAMES['97/two-way20-28/latent'])
            for key, value in (('LTX_SAMPLER_WORKERS', '2'), ('LTX_STREAM_FRAMES', '25'), ('LTX_ANCHOR', 'pixel'),
                               ('LTX_SAMPLER_PLACEMENT', 'shard4-a'), ('LTX_STREAM_TEXT_REUSE', '')):
                os.environ.update(env)
                os.environ[key] = value
                with self.assertRaises(RuntimeError):
                    rp.check_control_environment()
            os.environ.update(env)
            del os.environ['LTX_ANCHOR']
            with self.assertRaises(RuntimeError):
                rp.check_control_environment()
            self.assertIsNone(rp.expected_run_name())
        finally:
            os.environ.clear()
            os.environ.update(saved)


class Naming(unittest.TestCase):
    """The 113 naming incident: a fake results root with colliding folders must refuse the launch."""
    def root(self, entries):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        for directory in rp.NAME_DIRECTORIES:
            (root / directory).mkdir(parents=True, exist_ok=True)
        for rel in entries:
            (root / rel).mkdir(parents=True)
        return tmp, root

    def check(self, root):
        # Same module the launcher loads from the verified packet; here the author copy.
        contract = rp.module(HERE / 'stream_contract.py', 'stream114_names_test')
        return rp.name_collisions(set(contract.fixed_names()), contract.RUN_PREFIX + '-', root)

    def test_clean_root_and_older_packets_pass(self):
        tmp, root = self.root(['output/stream112-s00000007', 'output/validation/stream112-qeager-c000000',
                               'output/stream113-other', 'requests/stream111-x'])
        with tmp:
            self.assertEqual(self.check(root), [])

    def test_each_collision_refuses(self):
        cases = ['output/validation/stream114-qeager-c000000', 'output/stream114-qgraph-c000002',
                 'requests/stream114-window-probe', 'output/stream114-s00000000', 'output/stream114-anything']
        for rel in cases:
            tmp, root = self.root([rel])
            with tmp:
                self.assertEqual(self.check(root), [rel])

    def test_check_name_collisions_raises_and_reports(self):
        tmp, root = self.root(['output/validation/stream114-qeager-c000000', 'output/stream114-s00000003'])
        with tmp:
            packet = Path(tmp.name) / 'packet'
            (packet / 'resolution/components').mkdir(parents=True)
            (packet / 'resolution/components/stream_contract.py').write_bytes((HERE / 'stream_contract.py').read_bytes())
            with self.assertRaises(RuntimeError) as ctx:
                rp.check_name_collisions(packet, root)
            self.assertIn('output/validation/stream114-qeager-c000000', str(ctx.exception))
            self.assertIn('output/stream114-s00000003', str(ctx.exception))
            for rel in ('output/validation/stream114-qeager-c000000', 'output/stream114-s00000003'):
                os.rmdir(root / rel)
            result = rp.check_name_collisions(packet, root)
            self.assertEqual(result['collisions'], [])
            self.assertEqual(len(result['fixed_names']), 11)

    def test_missing_directories_are_not_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rp.name_collisions({'stream114-prepare'}, 'stream114-', Path(tmp)), [])

    def test_live_root_is_clean_now(self):
        """The real results root holds no 114 names today (read-only listing)."""
        contract = rp.module(HERE / 'stream_contract.py', 'stream114_names_live')
        self.assertEqual(rp.name_collisions(set(contract.fixed_names()), 'stream114-', rp.ROOT), [])


class NodeInputs(unittest.TestCase):
    """Every graph node our contract emits must satisfy its node's declared inputs."""
    def declared(self):
        import integration
        result = {}
        for name, cls in integration.NODE_CLASS_MAPPINGS.items():
            spec = cls.INPUT_TYPES()
            result[name] = (set(spec.get('required', {})), set(spec.get('optional', {})), cls.RETURN_TYPES)
        return result

    def test_custom_node_inputs(self):
        declared = self.declared()
        graphs = [c.build_chunk_graph(p) for f in c.FRAME_CHOICES for r in (0, 1) for a in c.ANCHORS
                  for p in c.qualification_params(f, r, anchor=a)]
        for a in c.ANCHORS:
            graphs.append(c.build_chunk_graph(c.stream_params(97, 3, 'boat', 1, 'a' * 64, 's', 1, anchor=a)))
            graphs.append(c.build_chunk_graph(c.stream_params(49, 3, 'boat', 1, 'a' * 64, 's', 0, reset=1, anchor=a)))
        graphs += [row['graph'] for row in c.setup_graphs()]
        seen = set()
        for graph in graphs:
            for node in graph.values():
                if node['class_type'] in declared:
                    required, optional, _ = declared[node['class_type']]
                    provided = set(node['inputs'])
                    self.assertTrue(required <= provided, (node['class_type'], required - provided))
                    self.assertTrue(provided <= required | optional, (node['class_type'], provided - required - optional))
                    seen.add(node['class_type'])
                for value in node['inputs'].values():
                    if isinstance(value, list) and graph[value[0]]['class_type'] in declared:
                        self.assertLess(value[1], len(declared[graph[value[0]]['class_type']][2]))
        self.assertEqual(seen, set(declared))

    def test_output_node_ranges_admit_both_lengths(self):
        import integration
        spec = integration.LTXStreamChunk114.INPUT_TYPES()['required']
        self.assertEqual((spec['frames'][1]['min'], spec['frames'][1]['max']), (49, 97))
        self.assertEqual(spec['anchor'][0], list(c.ANCHORS))

    def test_integration_imports_without_torch(self):
        out = subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.path.insert(0, %r); import integration; '
                              'import stream_preview, stream_decode, latent_anchor; print("torch" in sys.modules)'
                              % str(HERE)], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), 'False', out.stderr)


if __name__ == '__main__':
    unittest.main()

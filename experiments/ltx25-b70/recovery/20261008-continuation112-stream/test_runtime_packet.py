"""CPU tests: builder transforms, pinned identities and node/contract input agreement."""
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


def transformed(path, fn):
    return fn(rp.regular(rp.PARENT / path))


class Identities(unittest.TestCase):
    def test_plan_file_is_the_reconstructed_plan_and_pins_agree(self):
        envelope = json.loads((HERE / 'stream-plan.json').read_text())
        self.assertEqual(envelope, plan_module.build_plan())
        self.assertEqual(envelope['plan_sha256'], rp.PLAN_SHA)
        import session
        self.assertEqual(session.PLAN_SHA256, rp.PLAN_SHA)
        self.assertEqual(rp.QIDS, {'%d/%s' % (f, p): c.qualification_id(f, p)
                                   for f in c.FRAME_CHOICES for p in c.PLACEMENTS})

    def test_inventory_and_assembly_fit_build_allowance(self):
        result = rp.inspect_assembly()
        self.assertLess(result['source_payload_bytes'], rp.BUILD_ALLOWANCE)
        changed = result['changed_files']
        for path in ('source/scripts/ltx_resolution_session.py', 'source/scripts/integration.py',
                     'source/scripts/candidate_safety.py', 'source/scripts/stream_contract.py',
                     'launch/serve-encoder.py', 'launch/encoder_runtime_common.py',
                     'source/scripts/ltx_output_size_98.py', 'source/scripts/ltx_duration_guard.py',
                     'source/scripts/setup_gates.py', 'resolution/stream-plan.json'):
            self.assertIn(path, changed)
        # Sealed numerical sources stay byte-identical to 111.
        for path in ('source/comfy/sd.py', 'source/scripts/ltx_graph_capture.py', 'source/scripts/graph_capture_node.py',
                     'source/scripts/native_safety.py', 'source/scripts/native_adapter.py',
                     'source/scripts/executor_guard.py', 'source/comfy_extras/nodes_lt.py'):
            self.assertNotIn(path, changed)


class Transforms(unittest.TestCase):
    def run_module(self, name, raw, frames, code, placement='two-way'):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / (name + '.py')).write_bytes(raw)
            env = {'PATH': '/usr/bin', 'LTX_OUTPUT_SIZE': '256x256', 'LTX_STREAM_FRAMES': frames,
                   'LTX_SAMPLER_PLACEMENT': placement}
            out = subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.path.insert(0, %r); ' % tmp + code],
                                 capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_geometry_follows_launch_frames(self):
        raw = transformed('source/scripts/ltx_output_size_98.py', lambda r: rp.geometry_source(r, rp.PLAN_SHA))
        for frames in ('49', '25'):
            out = self.run_module('ltx_output_size_98', raw, frames,
                                  'import ltx_output_size_98 as g; print(g.FRAMES, g.latent_shape(), g.image_shape(), '
                                  'g._RESOLUTION_QUALIFICATION_ID, g._RESOLUTION_MODE, g.MAX_SIGNATURES_PER_BLOCK)')
            geo = c.geometry(int(frames))
            self.assertIn('%s %s' % (frames, tuple(geo['tensor_shapes']['video_latent'])), out)
            self.assertIn(c.qualification_id(int(frames)), out)
            self.assertIn('stream-candidate-112-v1 8', out)
        out = self.run_module('ltx_output_size_98', raw, '49', 'import ltx_output_size_98 as g; '
                              'print(g._RESOLUTION_QUALIFICATION_ID)', placement='two-way20-28')
        self.assertEqual(out, c.qualification_id(49, 'two-way20-28'))
        text = raw.decode()
        self.assertIn("env = {'LTX_SAMPLER_WORKERS': '1'", text)
        self.assertNotIn("'640x384' and", text)

    def test_capture_guard_bounds(self):
        raw = transformed('source/scripts/ltx_duration_guard.py', rp.capture_guard_source)
        for frames in ('49', '25'):
            out = self.run_module('ltx_duration_guard', raw, frames,
                                  'import ltx_duration_guard as d; print(d.FULL_PAYLOAD_BYTES, d.RAW_CAPTURE_BUDGET)')
            payload = c.geometry(int(frames))['full_payload_bytes']
            self.assertEqual(out, '%d %d' % (payload, 9 * (payload + 65544)))
        self.assertIn("'capture_cap': 9", raw.decode())

    def test_setup_gates_and_launcher(self):
        gates = transformed('source/scripts/setup_gates.py', rp.setup_gates_source).decode()
        self.assertIn("report['output_size'] == '256x256'", gates)
        launcher = transformed('launch/serve-encoder.py', rp.launcher_source).decode()
        self.assertIn(repr(rp.RUN_NAMES), launcher)
        self.assertNotIn('continuation-native-111', launcher)

    def test_control_environment(self):
        env = dict(rp.CONTROL_ENVIRONMENT, LTX_STREAM_TEXT_REUSE='0', LTX_STREAM_FRAMES='49',
                   LTX_SAMPLER_PLACEMENT='two-way')
        saved = dict(os.environ)
        try:
            os.environ.update(env)
            rp.check_control_environment()
            os.environ['LTX_SAMPLER_WORKERS'] = '2'
            with self.assertRaises(RuntimeError):
                rp.check_control_environment()
            os.environ['LTX_SAMPLER_WORKERS'] = '1'
            os.environ['LTX_SAMPLER_PLACEMENT'] = 'two-way20-28'
            rp.check_control_environment()
            os.environ['LTX_SAMPLER_PLACEMENT'] = 'shard4-a'
            with self.assertRaises(RuntimeError):
                rp.check_control_environment()
            os.environ['LTX_SAMPLER_PLACEMENT'] = 'two-way'
            os.environ['LTX_STREAM_FRAMES'] = '97'
            with self.assertRaises(RuntimeError):
                rp.check_control_environment()
        finally:
            os.environ.clear()
            os.environ.update(saved)


class NodeInputs(unittest.TestCase):
    """Every graph node our contract emits must satisfy its node's declared inputs."""
    def declared(self):
        import integration
        result = {}
        for name, cls in integration.NODE_CLASS_MAPPINGS.items():
            spec = cls.INPUT_TYPES()
            result[name] = (set(spec.get('required', {})), set(spec.get('optional', {})))
        return result

    def test_custom_node_inputs(self):
        declared = self.declared()
        graphs = [c.build_chunk_graph(p) for f in c.FRAME_CHOICES for r in (0, 1) for p in c.qualification_params(f, r)]
        graphs.append(c.build_chunk_graph(c.stream_params(49, 3, 'boat', 1, 'a' * 64, 's', 1)))
        graphs += [row['graph'] for row in c.setup_graphs()]
        seen = set()
        for graph in graphs:
            for node in graph.values():
                if node['class_type'] in declared:
                    required, optional = declared[node['class_type']]
                    provided = set(node['inputs'])
                    self.assertTrue(required <= provided, (node['class_type'], required - provided))
                    self.assertTrue(provided <= required | optional, (node['class_type'], provided - required - optional))
                    seen.add(node['class_type'])
        self.assertEqual(seen, set(declared))

    def test_integration_imports_without_torch(self):
        out = subprocess.run([sys.executable, '-B', '-c', 'import sys; sys.path.insert(0, %r); import integration; '
                              'print("torch" in sys.modules)' % str(HERE)], capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), 'False', out.stderr)


if __name__ == '__main__':
    unittest.main()

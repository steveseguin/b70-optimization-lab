"""CPU launch identity and unchanged parent scope for packet128 maintenance."""
import ast
import copy
from pathlib import Path
import unittest
import stream_contract as c

HERE = Path(__file__).resolve().parent

class MaintenanceScope(unittest.TestCase):
    def options(self):
        return dict(snapshot_mode='fingerprint', snapshot_schedule='full',
                    aux_residency='legacy', anchor_read_ahead=0,
                    display_worker='serial', display_device='xpu:3', display_schedule='sampler-a')

    def check(self, mode='idle', frames=145, options=None, **kwargs):
        values = dict(placement='two-way20-28', anchor='frame', decoder_graph=0, levers=('cone', 1, 1))
        values.update(kwargs)
        return c.check_maintenance_scope(mode, frames, options=options or self.options(), **values)

    def test_default_parent(self):
        self.assertEqual(c.launch_maintenance_mode({}), 'parent')

    def test_exact_choices(self):
        for mode in ('parent', 'idle'):
            self.assertEqual(c.launch_maintenance_mode({'LTX_MAINTENANCE_MODE': mode}), mode)

    def test_bad_launch_values(self):
        for mode in ('', 'IDLE', 'off', '0', 0, 1, True, None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                c.launch_maintenance_mode({'LTX_MAINTENANCE_MODE': mode})

    def test_bad_mode_rejected(self):
        for mode in ('', 'off', 0, True, None):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.check(mode=mode)

    def test_parent_leaves_inherited_scope_alone(self):
        self.check(mode='parent', frames=49, anchor='mixed', decoder_graph=1, levers=('full', 0, 0))

    def test_145_serial_candidate(self):
        self.check()

    def test_parallel_candidate(self):
        options = dict(self.options(), display_worker='parallel', display_device='xpu:2', display_schedule='eager-display')
        for frames in (145, 169):
            self.check(frames=frames, options=options)

    def test_other_geometries_refuse(self):
        for frames in (49, 97, 121, 146):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                self.check(frames=frames)

    def test_altered_required_options_refuse(self):
        for key, value in dict(snapshot_mode='walk', snapshot_schedule='a-xpu3-sync', aux_residency='xpu2', anchor_read_ahead=1).items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(options=dict(self.options(), **{key: value}))

    def test_altered_model_path_refuses(self):
        for kwargs in (dict(placement='two-way'), dict(anchor='latent'), dict(decoder_graph=1), dict(levers=('cone', 0, 1)), dict(levers=('cone', 1, 0))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.check(**kwargs)

    def test_inconsistent_display_refuses(self):
        for key, value in dict(display_worker='parallel', display_device='xpu:2', display_schedule='eager-display').items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(options=dict(self.options(), **{key: value}))

    def test_names_keep_parent_form_and_distinguish_idle(self):
        tree = ast.parse((HERE / 'runtime_packet.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'expected_run_name')
        key = '145/two-way20-28/frame/dg0/ad-cone/bo1/pa1/sm-fingerprint'
        env = dict(zip(('LTX_STREAM_FRAMES', 'LTX_SAMPLER_PLACEMENT', 'LTX_ANCHOR', 'LTX_DECODER_GRAPH', 'LTX_ANCHOR_DECODE', 'LTX_BENCODE_OVERLAP', 'LTX_PREP_AHEAD', 'LTX_SNAPSHOT_MODE'), ('145', 'two-way20-28', 'frame', '0', 'cone', '1', '1', 'fingerprint')))
        scope = {'RUN_NAMES': {key: 'stream133-base'}}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<namespace>', 'exec'), scope)
        run_name = scope['expected_run_name']
        self.assertEqual(run_name(env), 'stream133-base')
        self.assertEqual(run_name(dict(env, LTX_MAINTENANCE_MODE='parent')), 'stream133-base')
        self.assertEqual(run_name(dict(env, LTX_MAINTENANCE_MODE='idle')), 'stream133-base-mi')
        self.assertEqual(run_name(dict(env, LTX_MAINTENANCE_MODE='idle', LTX_SNAPSHOT_DIGEST_CACHE='1', LTX_STORAGE_SCAN_MODE='background')), 'stream133-base-ssbackground-sdc1-mi')

    def test_launcher_exports_mode(self):
        source = (HERE / 'launch-133.sh').read_text()
        for text in ('MM=${LTX_MAINTENANCE_MODE:-parent}', 'LTX_MAINTENANCE_MODE=$MM', 'NAME=${NAME}-mi', 'PY=/home/steve/.venvs/ltx25-baseline/bin/python', 'ARGS=(-B '):
            self.assertIn(text, source)

    def test_plan_bound_to_parent132(self):
        import plan
        envelope = plan.build_plan()
        self.assertEqual(envelope['plan']['basis']['parent_manifest_sha256'], '67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad')
        option = envelope['plan']['launch_parameters']['LTX_MAINTENANCE_MODE']
        self.assertEqual(option['default'], 'parent')
        self.assertEqual(option['choices'], ['parent', 'idle'])
        self.assertIn('maximum60s age since previous collection', option['rule'])

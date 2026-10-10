"""CPU-only adversarial checks for the launch-bound replica reserve."""
import ast
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import stream_contract as c
import stream_schedule_gate as live
import stream_receipts as receipts
import runtime_packet as rp
import test_gate_receipts as qualification
from test_live_replica_gate import replica_fixture
import test_packet123_admission as admission
from test_runtime_flow import harness

GIB = 2**30
KEY = 'display_replica_transient_budget_bytes'
ENV = 'LTX_DISPLAY_REPLICA_TRANSIENT_GIB'


def live_fixture(frames=145, reserve=6*GIB):
    rows, decodes = replica_fixture()
    rows[0]['frames'] = frames
    rows[0]['server_options'][KEY] = reserve
    residency = decodes[0]['display_replica']['residency']
    residency['transient_budget_bytes'] = reserve
    residency['last_decode']['before'].update(
        free_bytes=11*GIB, transient_budget_bytes=reserve, margin_bytes=9*GIB-reserve)
    return rows, decodes


def qualification_fixture(frames=145, reserve=6*GIB):
    rows, decodes, captures = qualification.passing(frames=frames, anchor='frame', decoder_graph=0)
    _, reference = live_fixture(frames, reserve)
    for row in rows:
        row['server_options'].update(display_schedule='eager-display', display_device='xpu:2')
        row['server_options'][KEY] = reserve
        decode = decodes[row['run_name']]
        decode['display_device'] = 'xpu:3' if row['kind'] == 'qualify-eager' else 'xpu:2'
        proof = copy.deepcopy(reference[0]['display_replica'])
        digest = decode['tensors']['images']['sha256']
        proof.update(equal=True, images_sha256=digest, reference_images_sha256=digest)
        decode['display_replica'] = proof
    return rows, decodes, captures


class ParseBudget(unittest.TestCase):
    def test_default_reserves_are_unchanged(self):
        self.assertEqual(c.launch_display_transient_bytes(121, {}), 4*GIB)
        self.assertEqual(c.launch_display_transient_bytes(145, {}), 6056574976)

    def test_valid_explicit_reserves(self):
        for frames, value, expected in ((121, '4', 4*GIB), (145, '5.640625', 6056574976),
                                        (145, '6', 6*GIB), (145, '8', 8*GIB)):
            with self.subTest(frames=frames, value=value):
                self.assertEqual(c.launch_display_transient_bytes(frames,
                    {ENV: value, 'LTX_DISPLAY_DEVICE': 'xpu:2'}), expected)

    def test_invalid_decimal_values(self):
        for value in ('', 'bad', 'NaN', 'sNaN', 'Infinity', '-Infinity', '-1', '0',
                      '4', '5.640624', '8.000000001', '6.0000000001'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.launch_display_transient_bytes(145, {ENV: value, 'LTX_DISPLAY_DEVICE': 'xpu:2'})

    def test_reserve_is_replica_only(self):
        for device in ('xpu:0', 'xpu:1', 'xpu:3', None):
            env = {ENV: '6'}
            if device is not None:
                env['LTX_DISPLAY_DEVICE'] = device
            with self.subTest(device=device), self.assertRaises(ValueError):
                c.launch_display_transient_bytes(145, env)

    def test_receipt_requires_integer_bytes_and_bounds(self):
        for value in (True, 6.0*GIB, '6442450944', None, 4*GIB, 8*GIB+1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.receipt_display_transient_bytes(145, {KEY: value})

    def test_169_reserve_admits_only_six_and_half_gib_or_more(self):
        self.assertEqual(c.launch_display_transient_bytes(169, {}), 13*GIB//2)
        self.assertEqual(c.launch_display_transient_bytes(169, {ENV: '8', 'LTX_DISPLAY_DEVICE': 'xpu:2'}), 8*GIB)
        with self.assertRaises(ValueError):
            c.launch_display_transient_bytes(169, {ENV: '6', 'LTX_DISPLAY_DEVICE': 'xpu:2'})


class PrelaunchBudget(unittest.TestCase):
    def check(self, **updates):
        env = admission.Admission().env()
        env.update(LTX_STREAM_FRAMES='145', LTX_DECODER_GRAPH='0', **updates)
        env.pop('LTX_DECODER_GRAPH_POOL_CAP_GB', None)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, env, clear=True):
            rp.check_control_environment(Path(root))

    def test_valid_reserve_prelaunch(self):
        self.check(**{ENV: '6'})

    def test_explicit_reserve_does_not_depend_on_component_import_path(self):
        # The sealed checker is imported from launch/, before resolution/components
        # or source/scripts enter sys.path. An authored-suite import must not mask it.
        paths = [entry for entry in sys.path
                 if not (Path(entry or '.').resolve() / 'stream_contract.py').is_file()]
        with patch.object(sys, 'path', paths), patch.dict(sys.modules):
            sys.modules.pop('stream_contract', None)
            self.check(**{ENV: '6'})

    def test_deployed_checker_resolves_its_packet_contract(self):
        with tempfile.TemporaryDirectory() as root:
            packet = Path(root)
            component = packet / 'resolution/components/stream_contract.py'
            component.parent.mkdir(parents=True)
            component.write_bytes(Path(c.__file__).read_bytes())
            component.with_name('run_storage.py').write_bytes(Path(rp.__file__).with_name('run_storage.py').read_bytes())
            deployed = packet / 'launch/encoder_runtime_common.py'
            deployed.parent.mkdir()
            with patch.object(rp, '__file__', str(deployed)):
                self.check(**{ENV: '6'})

    def test_invalid_reserve_prelaunch(self):
        for value in ('4', 'NaN', '6.0000000001', '9'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.check(**{ENV: value})

    def test_other_device_prelaunch(self):
        with self.assertRaises(RuntimeError):
            self.check(**{ENV: '6', 'LTX_DISPLAY_DEVICE': 'xpu:3'})


class LiveBudget(unittest.TestCase):
    def test_explicit_reserve_passes(self):
        for frames, reserve in ((121, 5*GIB), (145, 6*GIB), (145, 8*GIB)):
            with self.subTest(frames=frames, reserve=reserve):
                result = live.check(*live_fixture(frames, reserve))
                self.assertTrue(result['passed'], result)

    def test_reduced_reserve_fails_even_when_all_records_agree(self):
        result = live.check(*live_fixture(145, 4*GIB))
        self.assertFalse(result['passed'])
        self.assertTrue(any('Invalid replica transient allowance' in s for s in result['failures']))

    def test_residency_cannot_claim_the_default_for_an_explicit_reserve(self):
        rows, decodes = live_fixture()
        decodes[0]['display_replica']['residency']['transient_budget_bytes'] = c.display_transient_bytes(145)
        self.assertFalse(live.check(rows, decodes)['passed'])

    def test_decode_cannot_claim_a_different_reserve(self):
        rows, decodes = live_fixture()
        decodes[0]['display_replica']['residency']['last_decode']['before']['transient_budget_bytes'] = 7*GIB
        self.assertFalse(live.check(rows, decodes)['passed'])

    def test_free_memory_must_cover_explicit_reserve(self):
        rows, decodes = live_fixture()
        before = decodes[0]['display_replica']['residency']['last_decode']['before']
        before.update(free_bytes=8*GIB-1, margin_bytes=-1)
        self.assertFalse(live.check(rows, decodes)['passed'])


class QualificationBudget(unittest.TestCase):
    def verdict(self, fixture):
        return qualification.decide(*fixture, frames=145, anchor='frame', decoder_graph=0)

    def test_explicit_reserve_passes_all_nine_proofs(self):
        result = self.verdict(qualification_fixture())
        self.assertTrue(result['passed'], result['failures'])
        self.assertEqual(len(result['display_replica_rows']), 9)

    def test_reduced_reserve_fails_even_when_all_records_agree(self):
        result = self.verdict(qualification_fixture(reserve=4*GIB))
        self.assertFalse(result['passed'])
        self.assertIn('Invalid replica transient allowance', result['failures'])

    def test_one_receipt_cannot_change_reserve(self):
        rows, decodes, captures = qualification_fixture()
        rows[5]['server_options'][KEY] = 7*GIB
        self.assertFalse(self.verdict((rows, decodes, captures))['passed'])

    def test_one_decode_cannot_change_reserve(self):
        rows, decodes, captures = qualification_fixture()
        decodes[rows[7]['run_name']]['display_replica']['residency']['transient_budget_bytes'] = 7*GIB
        result = self.verdict((rows, decodes, captures))
        self.assertFalse(result['passed'])
        self.assertTrue(result['display_replica_failures'])

    def test_explicit_reserve_without_replica_fails(self):
        rows, decodes, captures = qualification.passing(frames=145, anchor='frame', decoder_graph=0)
        for row in rows:
            row['server_options'][KEY] = 6*GIB
        self.assertFalse(self.verdict((rows, decodes, captures))['passed'])


class ReceiptBudget(unittest.TestCase):
    def test_explicit_reserve_validates_all_receipts(self):
        rows, _, _ = qualification_fixture()
        for row in rows:
            receipts.validate_measurements(row)
            receipts.validate_receipt(row)

    def test_invalid_reserve_refuses_receipt(self):
        for reserve in (None, True, '6442450944', 4*GIB, 8*GIB+1):
            rows, _, _ = qualification_fixture()
            rows[0]['server_options'][KEY] = reserve
            with self.subTest(reserve=reserve), self.assertRaises(ValueError):
                receipts.validate_measurements(rows[0])

    def test_explicit_reserve_requires_replica(self):
        rows, _, _ = qualification_fixture()
        rows[0]['server_options']['display_device'] = 'xpu:3'
        with self.assertRaises(ValueError):
            receipts.validate_measurements(rows[0])

    def test_explicit_reserve_requires_supported_length(self):
        for frames in (49, 97, 169):
            rows, _, _ = qualification_fixture()
            rows[0]['frames'] = frames
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                receipts.validate_measurements(rows[0])


class ExplicitBudgetRuntime(unittest.TestCase):
    def test_145_dg0_replica_explicit_reserve_qualifies_and_streams(self):
        with patch.dict(os.environ, {ENV: '6'}):
            data = harness('--frames', '145', '--anchor', 'frame', '--stream-chunks', '2',
                           '--decode-delay', '0.01', '--audio-delay', '0.01',
                           '--decoder-graph', '0',
                           '--display-device', 'xpu:2', '--display-schedule', 'eager-display')
        self.assertIsNone(data.get('error'), data.get('error'))
        self.assertIsNone(data.get('halted'), data.get('halted'))
        self.assertTrue(data['verdict']['passed'], data['verdict'])
        self.assertFalse(data['xpu_initialized'])
        self.assertEqual(len(data['chunks']), 11)
        self.assertEqual(len(data['verdict_file']['display_replica_rows']), 9)
        self.assertTrue(data['live_schedule_gate']['passed'], data['live_schedule_gate'])
        for chunk in data['chunks']:
            self.assertEqual(chunk['server_options'][KEY], 6*GIB)
            self.assertEqual(chunk['display_replica']['residency']['transient_budget_bytes'], 6*GIB)


class RealStatusBudget(unittest.TestCase):
    def response_and_client_options(self, explicit):
        here = Path(__file__).resolve().parent
        tree = ast.parse((here / 'integration.py').read_text())
        route = next(node for node in ast.walk(tree)
                     if isinstance(node, ast.AsyncFunctionDef) and node.name == 'status')
        route.decorator_list = []
        options = dict(snapshot_mode='fingerprint', decoder_graph_pool_cap_bytes=None,
                       display_device='xpu:2', display_schedule='eager-display',
                       anchor_read_ahead=0, snapshot_schedule='full', aux_residency='legacy',
                       residency_qualification_id=c.residency_qualification_id(
                           c.qualification_id(145, 'two-way20-28', 'frame', 0), 'legacy'))
        if explicit:
            options[KEY] = 6*GIB
        ctx = MagicMock()
        ctx.action_busy = False
        ctx.authority.status.return_value = {'server_options': options.copy()}
        ctx.authority.qid = 'q'*64
        ctx.identity_sha, ctx.manifest_sha = 'i'*64, 'm'*64
        ctx.session.PLAN_SHA256 = 'p'*64
        ctx.frames, ctx.anchor, ctx.decoder_graph_flag = 145, 'frame', 0
        ctx.anchor_decode, ctx.bencode_overlap, ctx.prep_ahead = 'cone', 1, 1
        ctx.server_options = options
        for key, value in options.items():
            setattr(ctx, key, value)
        ctx.pool_cap = None
        ctx.display_worker = 'serial'  # Packet124 status adds the configured worker;123 client ignores it.
        ctx.fault.return_value = None
        ctx.run, ctx.root = Path('/cpu-fake/run'), Path('/cpu-fake')
        ctx.qualified_windows = None
        ctx.decoder_graph = ctx.cone = ctx.inspector = None
        for worker in (ctx.precompute, ctx.decoder, ctx.preview):
            worker.summary.return_value = {}
        ctx.storage_check.return_value = {'admitted': True}
        namespace = {'ctx': ctx, 'contract': c, 'time': time,
                     'web': SimpleNamespace(json_response=lambda value, **kw: value)}
        exec(compile(ast.Module(body=[route], type_ignores=[]), 'actual-status-route', 'exec'), namespace)
        # This handler has no await points: drive it directly without creating an
        # event loop, listener, socket pair or HTTP server.
        with self.assertRaises(StopIteration) as done:
            namespace['status'](None).send(None)
        response = json.loads(json.dumps(done.exception.value))
        ctx.storage_check.assert_called_once_with(mutate=False)
        ctx.note_status_route.assert_called_once()
        client_tree = ast.parse((here.parents[1] / 'stream/ltx_continuation_client.py').read_text())
        extractor = next(node for node in ast.walk(client_tree)
                         if isinstance(node, ast.FunctionDef) and node.name == 'status_server_options')
        client_namespace = {}
        exec(compile(ast.Module(body=[extractor], type_ignores=[]), 'actual-client-options', 'exec'),
             client_namespace)
        client = SimpleNamespace(a=SimpleNamespace(packet=123))
        parsed = client_namespace['status_server_options'](client, response)
        return response, parsed

    def test_explicit_budget_reaches_real_route_and_client_options(self):
        response, parsed = self.response_and_client_options(True)
        self.assertEqual(response[KEY], 6*GIB)
        self.assertEqual(parsed, response['server_options'])
        self.assertEqual(parsed[KEY], 6*GIB)

    def test_default_route_and_client_omit_explicit_budget(self):
        response, parsed = self.response_and_client_options(False)
        self.assertNotIn(KEY, response)
        self.assertNotIn(KEY, response['server_options'])
        self.assertNotIn(KEY, parsed)
        self.assertEqual(parsed, response['server_options'])


if __name__ == '__main__':
    unittest.main()

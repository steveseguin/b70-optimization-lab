"""CPU launch/receipt/qualification scope gates; never invoke a launcher."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cone_memory131 as cone
import runtime_packet as packet
import stream_contract as contract
import stream_receipts as receipts
import test_gate_receipts as fixtures


class ConeScope131(unittest.TestCase):
    def environment(self):
        return dict(packet.CONTROL_ENVIRONMENT, **cone.SCOPE,
                    LTX_CONE_GRAPH_MEMORY='replica-release', LTX_STREAM_TEXT_REUSE='1',
                    LTX_GC_INTERVAL_SECONDS='60', LTX_SNAPSHOT_DIGEST_CACHE='1',
                    LTX_MAINTENANCE_MODE='idle', LTX_STORAGE_SCAN_MODE='background')

    def check(self, env):
        with tempfile.TemporaryDirectory(prefix='cone131-scope-') as root:
            with patch.dict(os.environ, env, clear=True):
                packet.check_control_environment(Path(root))

    def test_current_packet_namespace_is137_and_parent_is135(self):
        self.assertEqual(contract.PACKET, 138)
        self.assertEqual(contract.RUN_PREFIX, 'stream138')
        self.assertEqual(contract.COMPARISON_MODE, 'stream-candidate-138-v1')
        self.assertEqual(contract.QUALIFICATION_CLIP_BASE, 13800000)
        self.assertEqual(contract.STREAM_CLIP_BASE, 13801000)
        self.assertEqual(packet.PARENT.name, 'prepared-continuation-stream-137')

    def test_offline_residency_uses_explicit_option_without_server_environment(self):
        args = (145, 'two-way20-28', 'frame', 1, 'cone', 'legacy', 'xpu:2')
        with patch.dict(os.environ, {}, clear=True):
            contract.check_residency_scope(*args, cone_graph_memory='replica-release')
            with self.assertRaises(ValueError):
                contract.check_residency_scope(*args)
            with self.assertRaises(ValueError):
                contract.check_residency_scope(*args, cone_graph_memory='off')
        with patch.dict(os.environ, {cone.ENV: 'replica-release'}, clear=True):
            with self.assertRaises(ValueError):
                contract.check_residency_scope(*args)

    def test_full_candidate_admitted_without_device_or_launcher(self):
        self.check(self.environment())

    def test_every_scope_field_is_checked_at_runtime_boundary(self):
        for key in cone.SCOPE:
            env = self.environment(); env[key] = 'wrong'
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                self.check(env)

    def test_missing_required_scope_fields_cannot_inherit_an_unrelated_arm(self):
        for key in set(cone.SCOPE) - set(cone.DEFAULTS):
            env = self.environment(); del env[key]
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                self.check(env)

    def test_candidate_disallows_soft_pool_cap(self):
        for cap in ('1.0', '5', '0', ''):
            env = dict(self.environment(), LTX_DECODER_GRAPH_POOL_CAP_GB=cap)
            with self.subTest(cap=cap), self.assertRaises((ValueError, RuntimeError)):
                self.check(env)

    def test_off_preserves_parent145_arm_and_does_not_admit_candidate(self):
        candidate = self.environment()
        for explicit in (False, True):
            parent = dict(candidate, LTX_DECODER_GRAPH='0', LTX_DISPLAY_DEVICE='xpu:3',
                          LTX_DISPLAY_SCHEDULE='sampler-a')
            if explicit:
                parent['LTX_CONE_GRAPH_MEMORY'] = 'off'
            else:
                del parent['LTX_CONE_GRAPH_MEMORY']
            self.check(parent)
        candidate['LTX_CONE_GRAPH_MEMORY'] = 'off'
        with self.assertRaises((ValueError, RuntimeError)):
            self.check(candidate)

    def test_invalid_runtime_mode_refused(self):
        for mode in ('', 'on', 'replica', 'unknown'):
            with self.subTest(mode=mode), self.assertRaises((ValueError, RuntimeError)):
                self.check(dict(self.environment(), LTX_CONE_GRAPH_MEMORY=mode))

    def test_run_name_distinguishes_opt_in_and_keeps_off_form(self):
        env = self.environment()
        name = packet.expected_run_name(env)
        self.assertTrue(name.endswith('-cmreplica-release'))
        off = dict(env, LTX_CONE_GRAPH_MEMORY='off')
        unset = dict(off); del unset['LTX_CONE_GRAPH_MEMORY']
        self.assertEqual(packet.expected_run_name(off), packet.expected_run_name(unset))
        self.assertEqual(name, packet.expected_run_name(off) + '-cmreplica-release')

    def test_receipts_refuse_unknown_mode_and_candidate_on_wrong_arm(self):
        rows, _, _ = fixtures.passing()
        for mode in ('unknown', '', None, True, 'replica-release'):
            row = copy.deepcopy(rows[0]); row['server_options']['cone_graph_memory'] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                receipts.validate_measurements(row)

    def test_qualification_refuses_unknown_shared_mode(self):
        for mode in ('unknown', '', None, True):
            rows, decodes, captures = fixtures.passing()
            for row in rows:
                row['server_options']['cone_graph_memory'] = mode
            result = fixtures.decide(rows, decodes, captures)
            with self.subTest(mode=mode):
                self.assertFalse(result['passed'])
                self.assertTrue(any('cone' in message.lower() for message in result['failures']))

    def test_qualification_refuses_inconsistent_mode_identity(self):
        rows, decodes, captures = fixtures.passing()
        rows[4]['server_options']['cone_graph_memory'] = 'off'
        self.assertFalse(fixtures.decide(rows, decodes, captures)['passed'])


if __name__ == '__main__':
    unittest.main()

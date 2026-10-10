"""CPU evidence and namespace binding for the optional126 storage worker."""
import ast
import copy
import os
from pathlib import Path
import unittest
import test_gate_receipts as fixtures
import stream_receipts as receipts

HERE = Path(__file__).resolve().parent

class StorageScope(unittest.TestCase):
    def test_invalid_receipt_storage_mode_refused(self):
        rows, decodes, captures = fixtures.passing()
        row = copy.deepcopy(rows[0])
        row['server_options']['storage_scan_mode'] = 'invented'
        with self.assertRaises(ValueError):
            receipts.validate_measurements(row)

    def test_invalid_shared_storage_mode_refused(self):
        rows, decodes, captures = fixtures.passing()
        for row in rows:
            row['server_options']['storage_scan_mode'] = 'invented'
        self.assertFalse(fixtures.decide(rows, decodes, captures)['passed'])

    def test_candidate_option_must_match_all_qualification_receipts(self):
        rows, decodes, captures = fixtures.passing()
        rows[4]['server_options']['storage_scan_mode'] = 'background'
        self.assertFalse(fixtures.decide(rows, decodes, captures)['passed'])

    def test_run_namespace_preserves_parent_and_distinguishes_candidate(self):
        tree = ast.parse((HERE / 'runtime_packet.py').read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == 'expected_run_name')
        key = '145/two-way20-28/frame/dg0/ad-cone/bo1/pa1/sm-fingerprint'
        scope = {'os': os, 'RUN_NAMES': {key: 'stream133-base'}}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<namespace>', 'exec'), scope)
        env = dict(zip(('LTX_STREAM_FRAMES', 'LTX_SAMPLER_PLACEMENT', 'LTX_ANCHOR', 'LTX_DECODER_GRAPH',
                        'LTX_ANCHOR_DECODE', 'LTX_BENCODE_OVERLAP', 'LTX_PREP_AHEAD', 'LTX_SNAPSHOT_MODE'),
                       ('145', 'two-way20-28', 'frame', '0', 'cone', '1', '1', 'fingerprint')))
        self.assertEqual(scope['expected_run_name'](env), 'stream133-base')
        self.assertEqual(scope['expected_run_name'](dict(env, LTX_STORAGE_SCAN_MODE='request')), 'stream133-base')
        self.assertEqual(scope['expected_run_name'](dict(env, LTX_STORAGE_SCAN_MODE='background')), 'stream133-base-ssbackground')
        self.assertEqual(scope['expected_run_name'](dict(env, LTX_STORAGE_SCAN_MODE='background', LTX_GC_INTERVAL_SECONDS='60')), 'stream133-base-gc60-ssbackground')

    def test_launcher_exports_mode_and_uses_required_interpreter(self):
        text = (HERE / 'launch-133.sh').read_text()
        self.assertIn('SCAN=${LTX_STORAGE_SCAN_MODE:-request}', text)
        self.assertIn('LTX_STORAGE_SCAN_MODE=$SCAN', text)
        self.assertIn('NAME=${NAME}-ssbackground', text)
        self.assertIn('PY=/home/steve/.venvs/ltx25-baseline/bin/python', text)
        self.assertIn('ARGS=(-B ', text)

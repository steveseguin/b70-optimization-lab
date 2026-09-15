#!/usr/bin/env python3
"""Bounded text-only export failure tests; never invoke export()."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('screen02_export_tests', HERE / 'export-host-embedding-screen-02.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class Tests(unittest.TestCase):
    def tearDown(self):
        self.assertNotIn('torch', sys.modules)

    def test_failed_terminal_preserves_missing_running_and_corrupt_progress(self):
        for progress in ({'status': 'failed'}, {'status': 'running'}, {'export_missing': True}, {'export_parse_error': 'partial'}):
            frozen = copy.deepcopy(progress)
            e.terminal_gate(progress, 'failed')
            self.assertEqual(progress, frozen)
            with self.assertRaises(RuntimeError):
                e.terminal_gate(progress, 'passed')
        with self.assertRaises(RuntimeError):
            e.terminal_gate({'status': 'passed'}, 'failed')

    def test_partial_json_bytes_remain_in_archive_mapping(self):
        path = e.ROOT / e.CAMPAIGN / 'progress.json'
        text = {e.shared.archive_name(path): '{"status":'}
        self.assertIn('export_parse_error', e.document(text, path))
        self.assertEqual(text[e.shared.archive_name(path)], '{"status":')

    def test_actual_failed_memory_receipt_is_validated_without_pass_relabel(self):
        path = e.SERVER / 'host-components-02-host-table-before-construction-memory.json'
        report = json.loads(path.read_text())
        original = copy.deepcopy(report)
        self.assertEqual(e.refused_construction(report)['status'], 'validated-memory-refusal')
        self.assertEqual(report, original)
        for key, value in [('passed', True), ('required_available_bytes', 1), ('runtime_memory_settings_changed', True)]:
            changed = copy.deepcopy(report)
            changed[key] = value
            with self.assertRaises(RuntimeError):
                e.refused_construction(changed)

    def test_actual_partial_release_and_all_three_memory_receipts(self):
        names = ['server-identity.json', 'host-components-01-control-result.json',
            'host-embedding-placement-host-embedding-screen-02-r05-control-a-boat.json',
            *('host-components-02-host-table-' + name + '.json' for name in
              ('unload', 'retired-owner-release', 'before-restore-memory', 'after-release-memory', 'before-construction-memory', 'result'))]
        text = {e.shared.archive_name(e.SERVER / name): (e.SERVER / name).read_text() for name in names}
        original = dict(text)
        server = json.loads(text[e.shared.archive_name(e.SERVER / 'server-identity.json')])
        contract = json.loads((e.LANE / 'data/host-embedding-registered-contract-01.json').read_text())
        rows = e.partial_transition_checks(text, server, contract)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'validated-saved-transition-receipts')
        self.assertFalse(rows[0]['completed_new_component_proof'])
        self.assertFalse(rows[0]['construction']['passed'])
        self.assertEqual(text, original)
        text[e.shared.archive_name(e.SERVER / 'host-components-02-host-table-retired-owner-release.json')] = '{'
        self.assertEqual(e.partial_transition_checks(text, server, contract)[0]['status'], 'partial-receipt-validation-failed')


if __name__ == '__main__':
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    sys.stderr.write(stream.getvalue())
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
        'scope': 'Text-only failure/partial receipt checks; export not invoked', 'torch_imported': 'torch' in sys.modules,
        'exporter_sha256': e.digest((HERE / 'export-host-embedding-screen-02.py').read_bytes()),
        'test_sha256': e.digest(Path(__file__).read_bytes()),
        'failures': [message for _, message in result.failures], 'errors': [message for _, message in result.errors]}, indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)

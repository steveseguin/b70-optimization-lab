"""CPU/stdlib tests. Synthetic allowlist entries are test fixtures, never qualified runtimes."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


pf = module('preflight')
loader = module('probe_plugin_loader')


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        artifacts = {}
        for role in sorted(pf.FILES):
            path = self.root / role
            path.write_text('SYNTHETIC TEST FIXTURE: ' + role)
            artifacts[role] = {'path': str(path), 'sha256': pf.digest_file(path)}
        hashes = {role: row['sha256'] for role, row in artifacts.items()}
        image = 'sha256:' + '1' * 64
        activation = {'candidate': pf.CANDIDATE, 'plugin': pf.PLUGIN, 'image_id': image,
                      'artifact_hashes': hashes, 'enabled': True,
                      'discovered_entrypoints': [pf.PLUGIN['entrypoint']],
                      'module_marker': pf.CANDIDATE, 'builder_marker': pf.CANDIDATE,
                      'group_marker': pf.CANDIDATE, 'builder_parameters': pf.BUILDER_PARAMETERS,
                      'group_anchor_count': 1, 'register_failure_propagated': True,
                      'missing_plugin_rejected': True}
        qualification = self.root / 'qualification.json'
        qualification.write_text(json.dumps({'activation': activation}))
        self.manifest = {'schema': pf.SCHEMA, 'candidate': pf.CANDIDATE, 'status': 'qualified',
                         'plugin': pf.PLUGIN, 'image_id': image, 'artifacts': artifacts,
                         'qualification_path': str(qualification),
                         'qualification_sha256': pf.digest_file(qualification), 'activation': activation}
        self.fixture_allowlist = {image: {'artifacts': hashes,
                                 'qualification_sha256': pf.digest_file(qualification)}}

    def test_pending_template_valid_schema_but_refused_without_reading_artifacts(self):
        m = json.loads((HERE / 'runtime-manifest.pending.json').read_text())
        pf.validate_manifest(m)
        with patch.object(pf, 'digest_file', side_effect=AssertionError('must not read pending artifacts')):
            with self.assertRaisesRegex(pf.Refused, 'pending'):
                pf.check(m)

    def test_self_declared_qualified_hashes_cannot_authorize_runtime(self):
        self.assertEqual(pf.QUALIFIED_RUNTIMES, {})
        with self.assertRaisesRegex(pf.Refused, 'reviewed allowlist'):
            pf.check(self.manifest)

    def test_fixture_consistency_never_grants_serving_authority(self):
        with patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
            result = pf.check(self.manifest)
        self.assertEqual(result['status'], 'offline-evidence-consistent')
        self.assertIs(result['serving_authorized'], False)

    def test_wrong_kernel_bytes_refused(self):
        Path(self.manifest['artifacts']['kernel']['path']).write_text('OLD KERNEL')
        with patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
            with self.assertRaisesRegex(pf.Refused, 'artifact bytes differ: kernel'):
                pf.check(self.manifest)

    def test_changing_kernel_hash_to_match_wrong_bytes_does_not_help(self):
        row = self.manifest['artifacts']['kernel']
        Path(row['path']).write_text('OLD KERNEL')
        row['sha256'] = pf.digest_file(row['path'])
        with patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
            with self.assertRaisesRegex(pf.Refused, 'unreviewed artifact digest: kernel'):
                pf.check(self.manifest)

    def test_ignored_plugin_and_missing_markers_refused(self):
        for key, value in [('enabled', False), ('discovered_entrypoints', []),
                           ('discovered_entrypoints', [pf.PLUGIN['entrypoint']] * 2),
                           ('builder_marker', None), ('group_marker', None), ('module_marker', 'old')]:
            m = copy.deepcopy(self.manifest)
            m['activation'][key] = value
            with self.subTest(key=key, value=value), patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
                with self.assertRaises(pf.Refused):
                    pf.check(m)

    def test_wrong_plugin_version_and_source_contract_refused(self):
        m = copy.deepcopy(self.manifest)
        m['plugin']['version'] = 'unreviewed'
        with self.assertRaisesRegex(pf.Refused, 'plugin identity'):
            pf.check(m)
        for key, value in [('builder_parameters', []), ('group_anchor_count', 2),
                           ('register_failure_propagated', False), ('missing_plugin_rejected', False)]:
            m = copy.deepcopy(self.manifest)
            m['activation'][key] = value
            with self.subTest(key=key), patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
                with self.assertRaises(pf.Refused):
                    pf.check(m)

    def test_activation_from_another_image_or_file_tree_refused(self):
        for key, value in [('image_id', 'sha256:' + '2' * 64), ('artifact_hashes', {})]:
            m = copy.deepcopy(self.manifest)
            m['activation'][key] = value
            with self.subTest(key=key), patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
                with self.assertRaises(pf.Refused):
                    pf.check(m)

    def test_unbound_activation_receipt_refused(self):
        self.manifest['activation']['extra_unreviewed_claim'] = True
        with patch.object(pf, 'QUALIFIED_RUNTIMES', self.fixture_allowlist):
            with self.assertRaisesRegex(pf.Refused, 'not bound'):
                pf.check(self.manifest)

    def test_incomplete_artifact_set_refused(self):
        del self.manifest['artifacts']['gdn_library']
        with self.assertRaisesRegex(pf.Refused, 'artifact set'):
            pf.check(self.manifest)

    def test_cli_pending_exits_two_and_exposes_no_launch_flag(self):
        run = subprocess.run([sys.executable, str(HERE / 'preflight.py'), '--manifest',
                              str(HERE / 'runtime-manifest.pending.json')], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIs(json.loads(run.stdout)['serving_authorized'], False)
        run = subprocess.run([sys.executable, str(HERE / 'preflight.py'), '--manifest',
                              str(HERE / 'runtime-manifest.pending.json'), '--launch'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn('unrecognized arguments', run.stderr)


class LoaderProbeTests(unittest.TestCase):
    def test_inspected_source_distinguishes_failure_paths(self):
        with self.assertLogs('loader-probe', level='ERROR'):
            result = loader.probe((HERE / 'source-evidence/local-vllm-plugins.py').read_text())
        self.assertEqual(result['outcomes'], {
            'success': {'register_called': True, 'raised': None},
            'import_failure': {'register_called': False, 'raised': None},
            'register_failure': {'register_called': True, 'raised': 'RuntimeError'},
            'excluded': {'register_called': False, 'raised': None}})
        receipt = json.loads((HERE / 'source-evidence/loader-probe.json').read_text())
        self.assertEqual(result['source_sha256'], receipt['source_sha256'])
        self.assertIs(receipt['qualified_for_r314'], False)

    def test_module_level_code_is_not_executed(self):
        src = (HERE / 'source-evidence/local-vllm-plugins.py').read_text()
        with self.assertLogs('loader-probe', level='ERROR'):
            loader.probe('raise RuntimeError("module-level executed")\n' + src)

    def test_missing_loader_functions_refused(self):
        with self.assertRaises(ValueError):
            loader.probe('def unrelated(): pass')


if __name__ == '__main__':
    unittest.main()

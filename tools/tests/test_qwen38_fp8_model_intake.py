"""Offline controls for the shared 27B FP8 model intake (no network/weights)."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70'
REVISION = '017b9c7af6b5689d5dd426a76e0bc077eb5ca20a'
WEIGHTS_SHA256 = 'f4abd2d49d4d88d22fb60689be5249e1b896f776bc42ff6ede1dece353be5993'
REQUIRED = {
    'config.json', 'generation_config.json', 'model.safetensors.index.json',
    'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja',
    'vocab.json', 'merges.txt', 'preprocessor_config.json',
    'video_preprocessor_config.json',
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class IntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((RECIPE / 'model-direct.json').read_text())
        cls.receipt = json.loads((RECIPE / 'model-metadata-20261007.json').read_text())

    def test_original_weight_identity_is_unchanged(self):
        weights = [x for x in self.manifest['lfs_files'] if x['path'].endswith('.safetensors')]
        self.assertEqual(len(weights), 66)
        self.assertEqual(canonical_hash(weights), WEIGHTS_SHA256)
        self.assertEqual(sum(x['bytes'] for x in weights), 30866866928)
        self.assertEqual(self.manifest['total_weight_bytes'], 30866866928)
        self.assertEqual(self.manifest['revision'], REVISION)
        self.assertEqual(self.manifest['repository'], 'Qwen/Qwen3.8-27B-FP8')

    def test_manifest_covers_immutable_publisher_tree_and_runtime_inputs(self):
        receipt = self.receipt
        self.assertEqual(receipt['revision'], REVISION)
        self.assertIsNone(receipt['api_response_link'])
        self.assertEqual(len(receipt['api_entries']), 81)
        publisher = {r['path']: r for r in receipt['api_entries'] if r['type'] == 'file'}
        selected = {}
        for section, digest_key in [('lfs_files', 'sha256'), ('small_files', 'git_blob')]:
            for entry in self.manifest[section]:
                self.assertNotIn(entry['path'], selected)
                selected[entry['path']] = entry
                row = publisher[entry['path']]
                self.assertEqual(entry['bytes'], row['size'])
                self.assertEqual(entry[digest_key], row['lfs']['oid'] if 'lfs' in row else row['oid'])
        self.assertEqual(set(publisher) - set(selected), {'safetensors-md5sum.txt'})
        self.assertEqual(publisher['safetensors-md5sum.txt']['size'], 0)
        self.assertLessEqual(REQUIRED, selected.keys())
        self.assertEqual(set(receipt['weight_index_referenced_files']),
                         {p for p in selected if p.endswith('.safetensors')})
        checked = {x['path']: x for x in receipt['metadata_checks']}
        self.assertLessEqual(REQUIRED, checked.keys())
        self.assertEqual(receipt['model_weight_bytes_fetched'], 0)
        self.assertEqual(len(checked), 15)

    def test_existing_verifier_accepts_extended_manifest(self):
        path = ROOT / 'repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py'
        spec = importlib.util.spec_from_file_location('model_identity_verifier', path)
        verifier = importlib.util.module_from_spec(spec)
        # Loading definitions does not call main, direct IO, or any device tool.
        previous = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(verifier)
        finally:
            sys.dont_write_bytecode = previous
        self.assertEqual(verifier.validate_manifest(self.manifest), [])

    def download_selection(self, package, manifest=None):
        """Execute real wrappers/downloader with tiny stand-ins for HTTP clients."""
        with tempfile.TemporaryDirectory(prefix='qwen-fp8-intake-control-') as directory:
            base = Path(directory)
            binary = base / 'bin'; binary.mkdir()
            for name, target in [('bash', '/bin/bash'), ('dirname', '/usr/bin/dirname'),
                                 ('basename', '/usr/bin/basename'),
                                 ('mkdir', '/usr/bin/mkdir'), ('stat', '/usr/bin/stat'),
                                 ('python3', sys.executable)]:
                (binary / name).symlink_to(target)
            client = '#!' + sys.executable + '\n' + '''
import json, os, pathlib, sys
args = sys.argv[1:]
if pathlib.Path(sys.argv[0]).name == 'aria2c':
    target = pathlib.Path(args[args.index('--dir') + 1]) / args[args.index('--out') + 1]
else:
    target = pathlib.Path(args[args.index('-o') + 1])
url = args[-1]
assert url.startswith('https://huggingface.co/Qwen/Qwen3.8-27B-FP8/resolve/')
with open(os.environ['TEST_REQUESTS'], 'a') as stream:
    stream.write(json.dumps({'url': url, 'filename': target.name}) + '\\n')
target.write_bytes(b'offline selection fixture; not model data')
'''
            for name in ('curl', 'aria2c'):
                path = binary / name; path.write_text(client); path.chmod(0o755)
            env = {'PATH': str(binary), 'MODEL_DIR': str(base / 'model'),
                   'TEST_REQUESTS': str(base / 'requests.jsonl')}
            if manifest is not None:
                override = base / 'manifest.json'
                override.write_text(json.dumps(manifest))
                env['MODEL_MANIFEST'] = str(override)
            result = subprocess.run(['/bin/bash', str(ROOT / 'packages' / package / 'scripts/download-model.sh')],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in (base / 'requests.jsonl').read_text().splitlines()]
            self.assertTrue(all('/resolve/' + REVISION + '/' in row['url'] for row in rows))
            return [row['filename'] for row in rows]

    def test_both_actual_package_downloaders_select_all_runtime_files(self):
        expected = {r['path'] for section in ('lfs_files', 'small_files') for r in self.manifest[section]}
        for package in ('qwen38-27b-fp8-tp1-b70', 'qwen38-27b-fp8-tp2-b70'):
            with self.subTest(package=package):
                selected = self.download_selection(package)
                self.assertEqual(len(selected), 80)
                self.assertEqual(set(selected), expected)
                self.assertLessEqual(REQUIRED, set(selected))

    def test_old_weights_only_manifest_reproduces_missing_runtime_files(self):
        old = dict(self.manifest)
        old['lfs_files'] = [x for x in old['lfs_files'] if x['path'].endswith('.safetensors')]
        old['small_files'] = []
        selected = self.download_selection('qwen38-27b-fp8-tp2-b70', old)
        self.assertEqual(len(selected), 66)
        self.assertTrue(REQUIRED.isdisjoint(selected))


if __name__ == '__main__':
    unittest.main()

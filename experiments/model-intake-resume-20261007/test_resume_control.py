#!/usr/bin/env python3
"""Run frozen baseline/candidate with sparse fixtures and fake HTTP clients."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
EXPECTED_BYTES = 104857601  # Above the existing downloader's aria2 threshold.
EXPECTED_URL = 'https://huggingface.co/lab/offline-fixture/resolve/pinned-fixture/model.safetensors'


class ResumeControls(unittest.TestCase):
    def execute(self, variant, sidecar):
        with tempfile.TemporaryDirectory(prefix='model-intake-resume-control-') as directory:
            root = Path(directory)
            binary = root / 'bin'; binary.mkdir()
            for name, target in [('bash', '/bin/bash'), ('dirname', '/usr/bin/dirname'),
                                 ('basename', '/usr/bin/basename'), ('stat', '/usr/bin/stat'),
                                 ('mkdir', '/usr/bin/mkdir'), ('python3', sys.executable)]:
                (binary / name).symlink_to(target)
            client = '#!' + sys.executable + '\n' + '''
import json, os, pathlib, sys
with open(os.environ['CONTROL_LOG'], 'a') as stream:
    stream.write(json.dumps({'client': pathlib.Path(sys.argv[0]).name, 'args': sys.argv[1:]}) + '\\n')
'''
            for name in ('aria2c', 'curl'):
                path = binary / name; path.write_text(client); path.chmod(0o755)
            model = root / 'model'; model.mkdir()
            weight = model / 'model.safetensors'
            # Sparse size-matching preallocation: no weights or 100MB payload.
            with weight.open('wb') as stream: stream.truncate(EXPECTED_BYTES)
            self.assertLess(weight.stat().st_blocks * 512, 4096)
            if sidecar: Path(str(weight) + '.aria2').write_bytes(b'offline control sidecar')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'repository': 'lab/offline-fixture',
                'revision': 'pinned-fixture', 'lfs_files': [{'path': weight.name, 'bytes': EXPECTED_BYTES}],
                'small_files': []}))
            log = root / 'calls.jsonl'
            env = {'PATH': str(binary), 'MODEL_DIR': str(model), 'MODEL_MANIFEST': str(manifest),
                   'CONTROL_LOG': str(log)}
            result = subprocess.run(['/bin/bash', str(HERE / ('download-model.' + variant + '.sh'))],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(weight.stat().st_size, EXPECTED_BYTES)
            return ([json.loads(line) for line in log.read_text().splitlines()] if log.exists() else [],
                    result.stdout)

    def test_size_matching_partial_with_sidecar_resumes_only_in_candidate(self):
        baseline, output = self.execute('baseline', sidecar=True)
        self.assertEqual(baseline, [])  # Reproduces the original incorrect skip.
        self.assertIn('have  model.safetensors', output)
        candidate, output = self.execute('candidate', sidecar=True)
        self.assertEqual(len(candidate), 1)
        self.assertEqual(candidate[0]['client'], 'aria2c')
        self.assertIn('--continue=true', candidate[0]['args'])
        self.assertEqual(candidate[0]['args'][-1], EXPECTED_URL)
        self.assertIn('get   model.safetensors', output)

    def test_size_matching_complete_without_sidecar_still_skips(self):
        for variant in ('baseline', 'candidate'):
            with self.subTest(variant=variant):
                calls, output = self.execute(variant, sidecar=False)
                self.assertEqual(calls, [])
                self.assertIn('have  model.safetensors', output)

    def test_frozen_sources_match_provenance_and_patch_is_one_condition(self):
        provenance = json.loads((HERE / 'provenance.json').read_text())
        for variant in ('baseline', 'candidate'):
            self.assertEqual(hashlib.sha256((HERE / ('download-model.' + variant + '.sh')).read_bytes()).hexdigest(),
                             provenance[variant + '_sha256'])
        baseline = (HERE / 'download-model.baseline.sh').read_text()
        candidate = (HERE / 'download-model.candidate.sh').read_text()
        self.assertEqual(candidate.replace(' && ! -e "${out}.aria2"', '', 1), baseline)


if __name__ == '__main__':
    unittest.main()

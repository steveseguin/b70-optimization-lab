"""Offline regression checks for the draft's useful failure boundaries."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

import recipe


class RecipeTests(unittest.TestCase):
    def test_exact_workload_bytes(self):
        for name, work in recipe.read('workloads.json').items():
            tokens = json.loads(gzip.decompress((recipe.HERE / work['prompt']).read_bytes()))
            raw = struct.pack('<' + 'i' * len(tokens), *tokens)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), work['prompt_i32_sha256'])
            self.assertEqual(len(tokens), work['prompt_count'])
            self.assertEqual(len(recipe.read(work['expected'])), work['max_new'])

    def test_baseline_outputs_and_real_failures(self):
        for work in ('short', 'long'):
            expected = recipe.read(recipe.read('workloads.json')[work]['expected'])
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'tokens.jsonl'
                rows = [dict(index=i, token=t) for i, t in enumerate(expected)]
                def save():
                    path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
                save()
                self.assertTrue(recipe.check_output(path, work)['passed'])
                rows[-1]['token'] += 1
                save()
                self.assertFalse(recipe.check_output(path, work)['passed'])
                rows.pop()
                save()
                self.assertFalse(recipe.check_output(path, work)['passed'])
                rows[0]['index'] = 1
                save()
                with self.assertRaisesRegex(ValueError, 'indices'):
                    recipe.check_output(path, work)

    def test_configuration_no_oracle_or_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'draft.tsv'; manifest.write_text('test fixture only')
            adapter = root / 'adapter.json'
            adapter.write_text(json.dumps({'schema': 'ownrt.gsq.rank-adapter-plan.v1',
                                          'rank_argv': [['--draft-manifest', str(manifest)]]}))
            receipt = root / 'receipt.json'; receipt.write_text(json.dumps({'schema': 'ownrt.engine.build.v1'}))
            args = argparse.Namespace(profile='2plus1', workload='short', policy='qualification',
                adapter=adapter, receipt=receipt, target_bdf=['0000:23:00.0', '0000:47:00.0'],
                provider_bdf='0000:43:00.0', output=root / 'configuration')
            result = recipe.materialize(args)
            self.assertFalse(result['runtime_admitted'])
            config = json.loads((args.output / 'config.json').read_text())
            self.assertEqual(config['max_new'], 32)
            self.assertEqual(config['check_policy'], 'qualification')
            self.assertTrue(config['verify_restore'])
            self.assertFalse(config['measured_policy_admitted'])
            self.assertNotIn('expected', config)
            self.assertNotIn('oracle', config)
            self.assertFalse((args.output / 'run').exists())
            self.assertEqual(hashlib.sha256((args.output / 'prompt.i32').read_bytes()).hexdigest(),
                             config['dedicated_prefill_prompt_sha256'])
            with self.assertRaisesRegex(ValueError, 'must be new'):
                recipe.materialize(args)
            args.output = root / 'overlap'; args.provider_bdf = args.target_bdf[0]
            with self.assertRaisesRegex(ValueError, 'distinct'):
                recipe.materialize(args)
            self.assertFalse(args.output.exists())

    def test_model_download_paths_and_hashes(self):
        rows = recipe.read('model-downloads.json')['files']
        targets = [r for r in rows if r['component'] == 'target']
        self.assertEqual(len(targets), 2)
        self.assertTrue(all('/IQ3_S/' in r['url'] for r in targets))
        self.assertEqual(sum(r['bytes'] for r in targets), 83863586496)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "models with 'quote"
            script = recipe.download_plan(destination, ['target'])
            self.assertIn('sha256sum --check --status', script)
            self.assertNotIn('--retry', script)
            subprocess.run(['sh', '-n'], input=script, text=True, check=True)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()

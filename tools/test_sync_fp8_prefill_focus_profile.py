"""Protect profile identity and historical numbers while publishing new points."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('fp8sync', Path(__file__).with_name('sync-fp8-prefill-focus-profile.py'))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class Projection(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.patch = patch.object(M, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.data = {'complete': True, 'profiles': {'27b-fp8': {
            'complete': True, 'quality_exact': True,
            'identity': {'parent_image': 'sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2',
                         'tensor_parallel_size': 2, 'speculative_tokens': 1, 'quantization': 'FP8',
                         'max_model_len': 4096, 'max_num_batched_tokens': 4096},
            'points': [{'prompt_tokens': n, 'samples': 18,
                        'mean_controls': {'server_prefill_tokens_per_s': v}}
                       for n,v in [(512,2800),(2048,3300)]]}}}
        (self.root / M.SOURCE).parent.mkdir(parents=True)
        self.save()
    def save(self):
        (self.root / M.SOURCE).write_text(json.dumps(self.data))
    def test_capacity_and_draft_must_match(self):
        original = copy.deepcopy(self.data)
        for field, wrong in [('max_model_len',1024),('max_num_batched_tokens',1024),
                             ('speculative_tokens',5),('tensor_parallel_size',1),('quantization','INT4')]:
            with self.subTest(field=field):
                self.data=copy.deepcopy(original)
                self.data['profiles']['27b-fp8']['identity'][field]=wrong
                self.save()
                with self.assertRaises(ValueError):M.profiles()
    def test_missing_quality_cannot_publish(self):
        self.data['profiles']['27b-fp8']['quality_exact']=False
        self.save()
        with self.assertRaises(ValueError):M.profiles()
    def test_only_measured_baseline_points(self):
        result=M.profiles()['27b-fp8']
        self.assertEqual([(p['context_tokens'],p['value']) for p in result['points']],[(512,2800),(2048,3300)])
        self.assertFalse(result['promotion_qualified'])
        self.assertIn('4K capacity',result['public_label'])
    def test_preserve_history_and_homepage(self):
        manifest=self.root/M.DATA/'evidence/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'archives':[],'source_files':[]}))
        package=self.root/'packages/qwen38-27b-fp8-tp2-b70/package.json'
        package.parent.mkdir(parents=True)
        old=[{'id':'existing-prefill','points':[{'value':2884.6}]},{'id':'historical-decode','points':[{'value':54.9}]}]
        package.write_text(json.dumps({'dependencies':[],'performance_profiles':old}))
        homepage=self.root/'index.html';homepage.write_text('Preserve original measured headline')
        with patch('sys.argv',['sync']):M.main()
        self.assertEqual(json.loads(package.read_text())['performance_profiles'][:2],old)
        self.assertEqual(homepage.read_text(),'Preserve original measured headline')
        saved=package.read_bytes()
        with patch('sys.argv',['sync','--check']):M.main()
        self.assertEqual(saved,package.read_bytes())

if __name__=='__main__':unittest.main()

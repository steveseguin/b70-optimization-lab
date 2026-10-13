"""Synthetic long-checker contracts and mocked windows; no model/device loads."""
import copy, json, os, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import suite
from context_window_gate import ContextWindows

class LongSuite(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='long-suite-',dir=suite.P/'build')
        self.root=Path(self.tmp.name);self.oracle=self.root/'oracle';self.actual=self.root/'actual'
        self.oracle.mkdir();self.check=suite.checker_for_cap(32)
        self.prompt=[1]*2271;self.tokens=list(range(100,132))
        self.bundle=self.root/'bundle';self.bundle.mkdir()
        self.save(self.bundle/'input.json',dict(tokens=self.prompt,model_dir='/synthetic'))
        (self.bundle/'tokens.txt').write_text(' '.join(map(str,self.prompt)))
        for name in ('identity.tsv','plan.tsv','vocab.bin'):(self.bundle/name).write_bytes(b'synthetic')
        shutil.copyfile(self.bundle/'input.json',self.oracle/'input.json')
        self.save(self.oracle/'result.json',dict(schema='iq3-runtime-cpu-oracle.v1',status='token-cap',arithmetic='iq3-p17-detmath-v2',tokens=self.tokens))
        blob=self.root/'layer';blob.write_bytes(bytes(20480));fixtures={}
        for step in range(1,9):
            d=self.oracle/f'step{step}';d.mkdir();rows=[]
            for layer in range(48):
                f=d/f'layer-{layer:02}.bf16';os.link(blob,f);digest=suite.pipeline.sha(f)
                fixtures[str(f.relative_to(self.oracle))]=digest
                rows.append(dict(layer=layer,shape=[1,4,2560],dtype='BF16 little-endian',sha256=digest))
            (d/'layers.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        positions=[2040,2047,2048,2049,2050,2051,2100,2270]
        for pos in positions:
            d=self.oracle/'midprompt'/str(pos);d.mkdir(parents=True)
            for layer in range(3,48,4):(d/f'layer-{layer:02}.ids.i32').write_bytes(bytes(2051*4))
            os.link(blob,d/'layer-47.bf16')
        mid={str(f.relative_to(self.oracle)):suite.pipeline.sha(f) for f in (self.oracle/'midprompt').rglob('*') if f.is_file()}
        self.save(self.oracle/'validation.json',dict(fixture_hashes=fixtures,midprompt_hashes=mid))
        self.save(self.oracle/'receipt.json',dict(verified=True,input_sha256=suite.pipeline.sha(self.oracle/'input.json'),validation_sha256=suite.pipeline.sha(self.oracle/'validation.json'),result_sha256=suite.pipeline.sha(self.oracle/'result.json')))
        self.entry=dict(prompt_id='LONG-B',prompt_tokens=len(self.prompt),generated_tokens=32,ended_early=False,midprompt_positions=positions,
            input_bundle=str(self.bundle),input_bundle_hashes={f.name:suite.pipeline.sha(f) for f in self.bundle.iterdir()},
            oracle_directory=str(self.oracle),oracle_receipt_sha256=suite.pipeline.sha(self.oracle/'receipt.json'))
        shutil.copytree(self.oracle,self.actual,copy_function=os.link,ignore=shutil.ignore_patterns('midprompt','receipt.json'))
        self.result=dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic='iq3-p17-detmath-v2',tokens=self.tokens)
        self.save(self.actual/'receipt.json',self.result)
    def tearDown(self):self.tmp.cleanup()
    def save(self,path,value):
        if path.exists():path.unlink() # Never mutate hardlinked fixture/oracle bytes.
        path.write_text(json.dumps(value))
    def compare(self):return suite.compare_request(self.actual,self.result,self.entry,self.check)
    def test_manifest_admits_32_and_preserves_identity(self):
        m=dict(arithmetic='iq3-p17-detmath-v2',token_cap=32,context=4096,prompts=[self.entry])
        self.assertEqual(suite.validate_manifest(m,4096),32)
        for delta in (dict(arithmetic='other'),dict(token_cap=True),dict(token_cap=31)):
            with self.assertRaises(ValueError):suite.validate_manifest(m|delta,4096)
        with self.assertRaises(ValueError):suite.validate_manifest(m,256)
    def test_checker_selection(self):
        self.assertEqual(self.check.source_sha256,suite.pipeline.sha(suite.CHECKER32))
        self.assertIsInstance(suite.checker_for_cap(128),suite.RetainedFixtureChecker)
        self.assertEqual(suite.checker_for_cap(64).source_sha256,suite.pipeline.sha(suite.CHECKER))
    def test_absent_midprompt_explicit_receipt(self):
        r=self.compare();self.assertTrue(r['passed']);self.assertEqual(r['oracle_check']['tokens'],32)
        self.assertEqual(r['oracle_check']['fixture_files'],384)
        self.assertEqual(r['midprompt_comparison'],'not retained by this binary')
        self.assertIn('2,048',r['midprompt_comparison_comment'])
    def test_retained_midprompt_compared(self):
        shutil.copytree(self.oracle/'midprompt',self.actual/'midprompt',copy_function=os.link)
        self.assertEqual(self.compare()['midprompt_comparison'],'compared');self.assertTrue(self.result['passed'])
    def test_retained_midprompt_corruption_rejected(self):
        shutil.copytree(self.oracle/'midprompt',self.actual/'midprompt',copy_function=os.link)
        f=self.actual/'midprompt/2048/layer-03.ids.i32';f.unlink();f.write_bytes(b'x'*8204)
        self.assertFalse(self.compare()['passed']);self.assertIn('byte mismatch',self.result['exactness_error'])
    def test_empty_midprompt_rejected(self):
        (self.actual/'midprompt').mkdir();self.assertFalse(self.compare()['passed'])
    def test_oracle_midprompt_hash_binding_preserved(self):
        f=self.oracle/'midprompt/2048/layer-03.ids.i32';f.unlink();f.write_bytes(b'x'*8204)
        self.assertFalse(self.compare()['passed']);self.assertIn('oracle mid-prompt binding',self.result['exactness_error'])
    def test_oracle_validation_binding_preserved(self):
        self.save(self.oracle/'validation.json',{});self.assertFalse(self.compare()['passed'])
        self.assertIn('oracle fixture binding',self.result['exactness_error'])
    def test_tokens_unchanged(self):
        self.save(self.actual/'receipt.json',self.result|dict(tokens=[42]*32))
        self.assertFalse(self.compare()['passed']);self.assertIn('tokens differ',self.result['exactness_error'])
    def test_retained_fixture_bytes_unchanged(self):
        f=self.actual/'step1/layer-00.bf16';f.unlink();f.write_bytes(b'x'*20480)
        self.assertFalse(self.compare()['passed']);self.assertIn('hash differs',self.result['exactness_error'])
    def test_input_binding_preserved(self):
        (self.bundle/'tokens.txt').write_text('2')
        self.assertFalse(self.compare()['passed']);self.assertIn('input bundle binding',self.result['exactness_error'])
    def test_two_long_prompts_warmup_and_submission(self):
        prompts=[[2,5,3,7,1]+[1]*593,self.prompt]
        warm=suite.select_warmup(prompts,4096,248320)
        self.assertTrue(all(warm!=p[i:i+5] for p in prompts for i in range(len(p)-4)))
        row=dict(tokens=self.tokens,stats=dict(guesses=31,hits=25),
                 timing_rows=[dict(token_id=t,completed_monotonic=i+1.) for i,t in enumerate(self.tokens)])
        from types import SimpleNamespace
        result=suite.pipeline.request_timing_metadata(row,SimpleNamespace(device=True,work_start=0.,work_end=33.),self.prompt,32)
        self.assertEqual(result['decode_intervals'],31)
        self.assertFalse(result['submission_window_available']);self.assertIsNone(result['submission_tok_s'])

class LongPrerequisites(unittest.TestCase):
    def test_exact_parent_only_and_other_identity_fields_still_bound(self):
        import window
        with tempfile.TemporaryDirectory(dir=suite.P/'build') as temp:
            receipt=Path(temp)/'window.json'
            identity=dict(build_receipt_sha256='new',compatible_prerequisite_build_receipt_sha256='old',
                          boot_id='boot',artifacts_sha256={'binary':'bytes'},environment={'native':{}},card=0,context=4096)
            row=dict(identity,window='K0',passed=True,build_receipt_sha256='old',receipts={})
            receipt.write_text(json.dumps(row))
            self.assertTrue(window.prerequisites(receipt,'K0',identity)['passed'])
            for field,value in [('build_receipt_sha256','unrelated'),('boot_id','other'),('artifacts_sha256',{}),
                                ('environment',{}),('card',1),('context',32768)]:
                receipt.write_text(json.dumps(row|{field:value}))
                with self.subTest(field=field),self.assertRaises(ValueError):window.prerequisites(receipt,'K0',identity)
            receipt.write_text(json.dumps(row))
            strict=dict(identity);strict.pop('compatible_prerequisite_build_receipt_sha256')
            with self.assertRaises(ValueError):window.prerequisites(receipt,'K0',strict)
            receipt.write_text(json.dumps(row|dict(window='WS')))
            with self.assertRaises(ValueError):window.prerequisites(receipt,'WS',identity)

class LongWindows(ContextWindows):
    # Inherited cases are run separately; only add the two-prompt long WS arms.
    def test_long_ws_and_sequential_request_count(self):
        for name in ('WS','WSs'):
            with self.subTest(window=name):self.execute(name,4096,32)

if __name__=='__main__':
    tests=unittest.defaultTestLoader.loadTestsFromTestCase(LongSuite)
    tests.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(LongPrerequisites))
    tests.addTest(LongWindows('test_long_ws_and_sequential_request_count'))
    result=unittest.TextTestRunner(verbosity=2).run(tests)
    raise SystemExit(not result.wasSuccessful())

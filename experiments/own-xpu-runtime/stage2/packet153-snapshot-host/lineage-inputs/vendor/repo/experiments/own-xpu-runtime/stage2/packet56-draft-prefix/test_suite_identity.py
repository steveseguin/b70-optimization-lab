"""Record-scope admission and independently hand-computed timing metrics."""
import copy
import json
import unittest
import suite
import suite_metrics as m

class SuiteIdentityTests(unittest.TestCase):
    def manifest(self):
        path = suite.ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json'
        manifest = json.loads(path.read_text())
        manifest.update(arithmetic='iq3-p49-split32-v1',context=4096)
        return manifest

    def test_shared_identity_passes_both_admissions(self):
        manifest = self.manifest()
        self.assertEqual(len(manifest['prompts']),12)
        self.assertEqual(suite.validate_manifest(manifest,4096),128)
        self.assertEqual(m.admit_cap(manifest,128),128)

    def test_old_identity_rejected_by_both(self):
        manifest = self.manifest()
        manifest['arithmetic'] = 'iq3-p17-detmath-v2'
        for validate in (lambda: suite.validate_manifest(manifest,4096),lambda: m.admit_cap(manifest,128)):
            with self.assertRaises(ValueError):validate()

    def test_99_intervals_and_distinct_medians(self):
        rows=[]
        rates=[10.,20.,30.,40.,50.,60.,70.,80.,90.,100.,110.,120.]
        for entry,rate in zip(self.manifest()['prompts'],rates):
            result=dict(tokens=[7]*128,timing_rows=[dict(completed_monotonic=10+i/rate) for i in range(128)])
            metrics=m.request_metrics(result,entry['prompt_tokens'],128,'none',8,40,True)
            self.assertEqual(metrics['submission100']['event_count'],100)
            self.assertEqual(metrics['submission100']['interval_count'],99)
            self.assertEqual(metrics['submission100']['numerator'],99)
            self.assertAlmostEqual(metrics['submission100']['rate'],rate)
            rows.append(dict(metrics,prompt_id=entry['prompt_id'],prompt_class=m.PROMPT_CLASSES[entry['prompt_id']],passed=True,repeat=1))
        summary=m.aggregate(rows)
        # operations:50,code:30,prose:75,analysis:70,documentation:90,structured:100
        self.assertAlmostEqual(summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],72.5)
        self.assertAlmostEqual(summary['submission100_statistics']['median'],65.)
        self.assertEqual(summary['submission100_statistics']['count'],12)
        self.assertFalse(summary['realistic_final_gate']['passed'])

if __name__ == '__main__':
    unittest.main()

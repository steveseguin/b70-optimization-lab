import copy
import json
from pathlib import Path
import tempfile
import unittest
from finalize_persistent_rolling_suite import attest
from test_compare_persistent_ring_state import make_persistent


class SuiteFinalizerTests(unittest.TestCase):
    def test_actual_native_shaped_measured_attestation_and_mutations(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=make_persistent(root/'candidate','measured');spec=json.loads(path.read_text())
            for item in spec['stages']:
                meta=json.loads((path.parent/item['metadata']).read_text());att=json.loads((path.parent/item['quiescence']).read_text())
                att['reset_index']=1
                stage=dict(id=item['id'],first=meta['first'],final=meta['final']);position=spec['input_identity']['position']
                layout=(path.parent/item['dump']).parent/'ring-checkpoint-layout.json'
                attest(att,stage,spec['ring_request_sha256'],1,position,layout)
                for key,value in [('reset_index',2),('ring_epoch',0),('target_host_restore_checks',99),
                                  ('provider_all_restores_byte_verified',True),('checkpoint_layout_sha256','0'*64),
                                  ('active_slots',1),('snapshot_releases',999)]:
                    with self.subTest(stage=stage['id'],field=key),self.assertRaises(ValueError):
                        attest(dict(att,**{key:value}),stage,spec['ring_request_sha256'],1,position,layout)

    def test_old_target_reference_remains_existing_final571_only(self):
        from persistent_rolling_suite_audit import load_baseline
        d=load_baseline(Path(__file__).parent/'persistent-rolling-baseline-audit.json')
        spec=json.loads(d['final_state_path'].read_text())
        self.assertEqual(spec['input_identity'],d['final_identity'])
        self.assertEqual(spec['input_identity']['position'],571)
        self.assertEqual(len(spec['stages']),4)
        self.assertNotIn('draft_input_identity',spec)
        for stage in spec['stages']:self.assertTrue(Path(stage['dump']).is_dir())


if __name__=='__main__':unittest.main()

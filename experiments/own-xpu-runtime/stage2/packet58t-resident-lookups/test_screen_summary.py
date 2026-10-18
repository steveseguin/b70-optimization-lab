import json,tempfile,unittest
from pathlib import Path
import screen_views as V
import screen_driver as D
class SummaryTests(unittest.TestCase):
    """Replay actual 36-request checker with synthetic native receipts in scratch."""
    @classmethod
    def setUpClass(cls):cls.manifest=D.oracle_inputs()

    def fixture(self,out):
        run=out/'run';run.mkdir()
        native=dict(passed=True,safe_to_exit=True,device_executed=True,owner_cards=1,
            cpu_affinity=[0,1,2,3,16,17,18,19],observed_nice=0,native_nice=0,
            teardown=[dict(safe_to_exit=True,idle_marker_complete=True,exit_code=0,live_bytes=0,in_flight=0)])
        D.save(run/'receipt.json',native)
        for label,view in V.bracket('resident'):
            folder=run/label;folder.mkdir()
            D.save(folder/'boundary.json',dict(passed=True,selection_sha256=V.digest(view),allocation_ids_preserved=True,
                weight_uploads_during_switch=0,model_loads=1,context_extent=32,arena_descriptors_sha256='a'*64,weight_descriptors_sha256='b'*64))
            D.save(folder/'lookup-backing.json',dict(resident=view=='resident',copies=dict(enabled=True,bytes=29321610240,
                tensors=[dict(name=n,bytes=b,source_sha256='a'*64,resident_sha256='a'*64) for n,b in
                         [('token_embd.weight',521472000),('per_layer_token_embd.weight',28800138240)]])))
            for e in self.manifest['prompts']:
                actual=folder/e['prompt_id'];actual.mkdir()
                tokens=D.CHECK.token_record(D.ORACLE/'results'/e['prompt_id'])[:128]
                interval=.038 if label.startswith('B') else .04
                D.save(actual/'result.json',dict(passed=True,arithmetic=D.ARITHMETIC,tokens=tokens,cached_tokens=0,gpu_count=1,
                    decode_mode='plain',context=4096,requested_max_new=128,prompt_tokens=e['prompt_tokens'],
                    request_start_monotonic=10.,request_end_monotonic=20.,
                    timing_rows=[dict(completed_monotonic=11+i*interval) for i in range(len(tokens))]))
                (actual/'timings.jsonl').write_text(json.dumps(dict(prepare_major_faults=0,prepare_minor_faults=1,prepare_ms=.5))+'\n')
                D.save(actual/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))

    def test_all36_actual_oracle_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out)
            row=D.summarize_bracket(out,'resident',self.manifest)
            self.assertTrue(row['candidate_beats_all_controls'])
            self.assertEqual(row['request_count'],36)
            self.assertFalse(row['realistic_final_gate']['passed'])
            self.assertTrue(all(len(v['requests'])==12 for v in row['views']))
            self.assertTrue(all(r['submission100']['interval_count']==99 for v in row['views'] for r in v['requests'] if not r['early_end_before_100']))
            # Last token in the last view is checked, not merely a prefix/hash.
            path=out/'run/A1'/self.manifest['prompts'][-1]['prompt_id']/'result.json'
            bad=D.read(path);bad['tokens'][-1]+=1;D.save(path,bad)
            with self.assertRaisesRegex(ValueError,'token identity'):D.summarize_bracket(out,'resident',self.manifest)

    def test_boundary_and_reset_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out)
            path=out/'run/B0/boundary.json';original=D.read(path)
            for key,value in (('selection_sha256','bad'),('weight_uploads_during_switch',1),('model_loads',2),
                              ('allocation_ids_preserved',False),('context_extent',4096),('arena_descriptors_sha256','other')):
                D.save(path,dict(original,**{key:value}))
                with self.subTest(key=key),self.assertRaises(ValueError):D.summarize_bracket(out,'resident',self.manifest)
            D.save(path,original)
            path=out/'run/B0'/self.manifest['prompts'][0]['prompt_id']/'reset.json'
            D.save(path,dict(passed=True,cached_tokens=1,allocation_ids_preserved=True))
            with self.assertRaisesRegex(ValueError,'reset'):D.summarize_bracket(out,'resident',self.manifest)

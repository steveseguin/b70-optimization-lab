"""Validate per-view v4-schema reports and the smoke's timing gate without GPUs."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import common as C
import compare
from conditions import LANES
import test_v3

class BracketReportingTests(unittest.TestCase):
    def scenario(self,kind='bracket',drift=False,tamper=False,scales=None,acceptance_change=False,arm_loss=False):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            (output/'run').mkdir()
            config=C.read(C.HERE/'configs/bracket.json')
            if kind=='smoke':
                config['kind']='smoke'
                config['views']=[copy.deepcopy(config['views'][0]) for _ in range(3)]
            identity=dict(bracket=config,placement={},lane='B',conditions=LANES['B'])
            views=[]
            C.save(output/'run/device-isolation.json',dict(passed=True))
            for i,selection in enumerate(config['views']):
                dest=output/'run/views'/f'{i:02d}-{selection["choice"]}'
                (dest/'incident64').mkdir(parents=True)
                (dest/'boundary').mkdir()
                rows=test_v3.V3Tests().rows(scales[i] if scales else 1.1 if drift and i==2 else 1.)
                for row in rows:row.update(hits=56,guesses=70,cached_tokens=0,repeat=1)
                if (acceptance_change and i==1) or (arm_loss and i in (1,3)):rows[0].update(hits=55,acceptance=55/70)
                if tamper and i==1:rows[3]['tokens'][5]=999
                incident=dict(tokens=list(range(64)),cached_tokens=0,passed=True,exact_oracle=True)
                C.save(dest/'incident64/receipt.json',incident)
                proof=dict(passed=True,tokens_compared=64,receipt_sha256=C.sha(dest/'incident64/receipt.json'))
                boundary=[]
                for rank in (0,1):
                    r=dict(passed=True,total_reset=True,cached_tokens=0,weight_uploads_after_load=0,
                           selection_sha256=selection['selection_sha256'],arena_descriptors_sha256=str(rank),weight_descriptors_sha256=str(rank))
                    C.save(dest/'boundary'/f'boundary-rank{rank}.json',r);boundary.append(r)
                views.append(dict(passed=True,index=i,choice=selection['choice'],selection_sha256=selection['selection_sha256'],
                                  output=str(dest),started_utc_ns=i*10+1,finished_utc_ns=i*10+5,
                                  boundary=boundary,requests=rows,incident64=proof))
            C.save(output/'run/bracket-inputs.json',dict(passed=True,kind=kind,views=views))
            with patch.object(C.D.CHECK,'token_record',return_value=list(range(128))):
                result=compare.finish_bracket(output,dict(boot_id='mock',started_utc_ns=1),identity,{})
            self.assertEqual(len(result['views']),len(config['views']))
            self.assertEqual(result['model_lifetimes'],1)
            self.assertIsNone(result['device_wall_savings_seconds'])
            for view in views:
                summary=C.read(Path(view['output'])/'summary.json')
                self.assertEqual(summary['schema'],'own-runtime.screen.summary.v3')
                self.assertEqual(summary['request_count'],12)
                self.assertTrue(summary['shared_model_lifetime'])
            return result

    def test_five_view_adapter_preserves_v4_schema(self):
        result=self.scenario();self.assertEqual(len(result['candidates']),2)

    def test_smoke_requires_exact_timing_bound(self):
        self.assertTrue(self.scenario('smoke')['timing_equal_within_control_drift'])
        with self.assertRaisesRegex(ValueError,'control bound'):self.scenario('smoke',drift=True)

    def test_adapter_rechecks_tokens_instead_of_trusting_pass(self):
        with self.assertRaisesRegex(ValueError,'target output mismatch'):self.scenario(tamper=True)

    def test_mean_only_gain_is_not_a_win(self):
        result=self.scenario(scales=[1.1,1.05,1.,1.06,1.])
        self.assertFalse(result['both_candidates_faster_than_all_controls'])
        self.assertLess(result['strict_gain_percent'],0)
        self.assertTrue(all(r['diagnostic_gain_over_control_mean_percent']>0 for r in result['candidates']))

    def test_consistent_candidate_acceptance_loss_is_reported(self):
        result=self.scenario(arm_loss=True,scales=[1.,1.01,1.,1.01,1.])
        self.assertNotEqual(result['views'][0]['acceptance_counts'],result['views'][1]['acceptance_counts'])
        self.assertTrue(result['candidate_accepted'])
        self.assertEqual(result['decision'],'accept')

    def test_equal_speed_rejects_without_retuning(self):
        result=self.scenario()
        self.assertFalse(result['candidate_accepted'])
        self.assertEqual(result['decision'],'reject')
        self.assertFalse(result['retune_allowed'])

    def test_per_prompt_acceptance_change_refuses(self):
        with self.assertRaisesRegex(ValueError,'acceptance changed'):self.scenario(acceptance_change=True)

if __name__=='__main__':unittest.main()

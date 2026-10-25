import copy
from pathlib import Path
import unittest
from review_persistent_rolling_suite_run import row_metrics,aggregate,fixed_classes,ROOT


class WindowMetricTests(unittest.TestCase):
    def fixture(self,count=101):
        tokens=[dict(index=i,token=i+1,committed_monotonic_s=20+i*.25) for i in range(count)]
        outputs=[r['token'] for r in tokens];span=(count-1)*.25
        row=dict(output_ids=outputs,cached_tokens=0,request_started_monotonic_s=18.,request_finished_monotonic_s=20+span+1.,
            reset_seconds=10.,prompt_token_sha256='a'*64,output_token_sha256='b'*64,
            timing=dict(first_token_seconds=2.,decode_intervals=count-1,decode_tokens_per_second=4.))
        prompt=dict(id='code-review',prompt_tokens=[4,8],max_new=512)
        return prompt,row,tokens

    def test_exact_first100_events_use99_intervals_and_exclude_reset(self):
        prompt,row,tokens=self.fixture();value=row_metrics(prompt,row,tokens,'code')
        self.assertEqual(value['first99']['numerator'],99)
        self.assertEqual(value['first99']['seconds'],24.75)
        self.assertEqual(value['first99']['tokens_per_second'],4.)
        self.assertEqual(value['first99']['last_event_index'],99)
        self.assertEqual(value['ttft_seconds'],2.)
        self.assertEqual(value['reset_seconds'],10.)
        self.assertIsNone(value['pure_prefill_seconds']);self.assertIsNone(value['native_prefill_tokens_per_second'])
        self.assertIsNone(value['cap512_tokens_per_second'])

    def test_short_window_token_mismatch_and_reordered_timestamps_refused(self):
        for kind in ('short','token','order','stored-rate'):
            prompt,row,tokens=self.fixture(99 if kind=='short' else 101)
            if kind=='token':tokens[99]['token']=-1
            elif kind=='order':tokens[98]['committed_monotonic_s']=1000
            elif kind=='stored-rate':row['timing']['decode_tokens_per_second']=100/24.75
            with self.subTest(kind=kind),self.assertRaises(ValueError):row_metrics(prompt,row,tokens,'code')

    def test_fixed_class_balancing_is_not_all_prompt_median(self):
        template=row_metrics(*self.fixture(),'code');rows=[]
        for name,values in [('operations',[1,1,1]),('analysis',[2,2,2]),('code',[3,3]),('prose',[4,4]),('documentation',[9]),('structured-writing',[10])]:
            for value in values:
                row=copy.deepcopy(template);row['prompt_class']=name;row['first99']['tokens_per_second']=value
                row['cap512_tokens_per_second']=value;rows.append(row)
        value=aggregate(rows)
        self.assertEqual(value['primary']['median'],3.5)
        self.assertEqual(value['all_prompt_first99']['median'],2.5)
        classes=fixed_classes(ROOT/'scripts/qualify_realistic_window_metrics.py')
        self.assertEqual(classes['customer-email'],'prose');self.assertEqual(classes['technical-guide'],'documentation')
        self.assertEqual(len(classes),12)


if __name__=='__main__':unittest.main()

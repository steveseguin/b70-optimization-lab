import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import memory_plan as M
import screen_views as V
import screen_driver as D
import screen_window as W
from compare_bracket import compare

class ResidentPolicyTests(unittest.TestCase):
    def test_same_weights_different_backing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bracket';V.write_table(p,'resident');rows=[x.split() for x in p.read_text().splitlines()]
            self.assertEqual([x[0] for x in rows],['A0','B0','A1'])
            self.assertEqual([x[3] for x in rows],['0','1','0'])
            self.assertEqual(len({x[1] for x in rows}),1);self.assertEqual(len({x[2] for x in rows}),1)
        self.assertEqual(V.validate('resident')['choices'],dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16'))
    def test_window_budget_includes_all_copy_bytes(self):
        for w in ('KD','W2m','WS','WS128x','WS128','WSCREEN'):
            p=M.window_plan(w)
            categories=p.get('exact_host_categories',p['host_categories'])
            self.assertEqual(categories['resident_lookup_bytes'],29321610240)
            self.assertEqual(p['host_required_available_bytes'],sum(categories.values())+M.HOST_RESERVE)
        self.assertGreaterEqual(W.CONFIG['WSCREEN'][1],4*W.CONFIG['WSCREEN'][0])
        self.assertGreaterEqual(W.CONFIG['WSCREEN'][1],4*1500)
    def test_all_resident_anon_charged_and_one_byte_excess_refused(self):
        p=M.plan();h=p['host_categories'];pins=h['pinned_packed_experts'];shadow=h['gpuactive_shadow_bound']
        anon=sum(h[k] for k in ('resident_lookup_bytes','loader_staging_bound','process_workspace_bound','cache_metadata_bound'))
        snapshot=dict(MemAvailable=M.HOST_RESERVE,GPUActive=pins+shadow)
        row=W.account_memory(dict(anonymous_bytes=anon),snapshot,0,pins,p)
        self.assertEqual(row['host_accounted_bytes'],p['host_required_available_bytes']-M.HOST_RESERVE)
        with self.assertRaisesRegex(ValueError,'combined host'):W.account_memory(dict(anonymous_bytes=anon+1),snapshot,0,pins,p)
    def rows(self,rates=(25,26,25)):
        return [dict(label=label,passed=True,requests=[dict(exact_oracle=True,cached_tokens=0) for _ in range(12)],class_balanced_tok_s_1_100_intervals_after_ttft=dict(median=rate)) for label,rate in zip(('A0','B0','A1'),rates)]
    def test_bracket_threshold_and_failure(self):
        self.assertTrue(compare(self.rows())['candidate_beats_all_controls'])
        self.assertFalse(compare(self.rows((25,25.1,25)))['candidate_beats_all_controls'])
        self.assertFalse(compare(self.rows((24,26,25)))['control_drift_passed'])
        for field,value in (('exact_oracle',False),('cached_tokens',1)):
            rows=self.rows();rows[1]['requests'][-1][field]=value
            with self.assertRaises(ValueError):compare(rows)
        with self.assertRaises(ValueError):compare(self.rows()[:2])
        self.assertFalse(compare(self.rows())['fresh_process_repeat'])
    def test_fault_counters_missing_or_nonzero_are_not_erased(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'p').mkdir();f=root/'p/timings.jsonl';manifest=dict(prompts=[dict(prompt_id='p')])
            f.write_text(json.dumps(dict(prepare_major_faults=3,prepare_minor_faults=2,prepare_ms=8))+'\n')
            row=D.lookup_faults(root,manifest);self.assertEqual(row['major'],3);self.assertEqual(row['major_per_token'],3)
            f.write_text('{}\n')
            with self.assertRaises(ValueError):D.lookup_faults(root,manifest)

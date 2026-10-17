#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest
import p57_perturbation as p


def event(label='draft.blk.0.attention',category='attention',rank=1,position=15,event_id=1):
    return dict(schema='packet57.event.v1',rank=rank,fixture=position-6,position=position,
                speculative=False,label=label,**{'class':category},event=event_id,
                start_ns=1000*event_id,end_ns=1000*event_id+100,device_ms=.0001)


def fixture(scale=1, all_hit=False):
    from test_timeline import command
    def cmd(rank,op,pos,start,end,spec=False):
        return command(rank,op,pos,1+(start-1)*scale,1+(end-1)*scale,spec)
    trace=[];times=[1.];draft=[];stamp=1.
    for pos in range(8,135):
        hit=all_hit or pos%4!=0
        draft.append(dict(position=pos,hit=hit,target_completed_monotonic=1+(stamp-1)*scale,
                          draft_wall_ms=2*scale,rank0_idle_waiting_for_guess_ms=.01))
        trace.append(cmd(1,9,pos,stamp,stamp+.002))
        start=stamp+.002
        if not hit:
            trace.extend([cmd(0,3,pos,stamp,stamp+.001,True),cmd(0,1,pos,stamp+.001,stamp+.015)])
            start=stamp+.015
        trace.append(cmd(1,1,pos,start,start+.016))
        if pos<134:trace.append(cmd(0,1,pos+1,start,start+.017,True))
        stamp=start+(.017 if pos<134 else .016)
        times.append(1+(stamp-1)*scale)
    draft.append(dict(position=135,hit=None,target_completed_monotonic=times[-1],
                      draft_wall_ms=2*scale,rank0_idle_waiting_for_guess_ms=.01))
    return dict(generated_token_completion_timestamps=times,draft_rows=draft,rank_trace=trace,
                passed=True,oracle_check={'passed':True},cached_tokens=0,output_tokens=128,
                prompt_id='p',prompt_token_sha256='prompt',output_token_sha256='output',
                target_split=23,binary_sha256='binary',arithmetic='arithmetic')


def events():
    rows=[];index=1
    for pos in range(15,23):
        for cls in sorted(p.REQUIRED_DRAFT_CLASSES):
            rows.append(event('draft.'+cls,cls,1,pos,index));index+=1
        for layer in sorted(p.REQUIRED_TARGET_LAYERS):
            rank=0 if layer in {'blk.19','blk.22'} else 1
            for cls in sorted(p.REQUIRED_TARGET_CLASSES):
                rows.append(event(layer+('.ffn.combine' if cls=='moe_experts' else '.'+cls),cls,rank,pos,index));index+=1
    return rows


class PerturbationTests(unittest.TestCase):
    def test_zero_or_negative_events_fail(self):
        for duration in (0,-1):
            e=event();e['end_ns']=e['start_ns']+duration
            with self.assertRaises(ValueError):p.validate_event(e,1)

    def test_duration_mismatch_fails(self):
        e=event();e['device_ms']=.2
        with self.assertRaises(ValueError):p.validate_event(e,1)

    def test_missing_class_fails(self):
        rows=[e for e in events() if e['class']!='argmax']
        with self.assertRaisesRegex(ValueError,'missing draft event classes'):
            p.analyze_events(rows,{i:None for i in range(15,23)})

    def test_missing_fixture_and_wrong_owner_fail(self):
        rows=[e for e in events() if not (e['position']==22 and e['class']=='argmax')]
        with self.assertRaisesRegex(ValueError,'incomplete draft class inventory'):
            p.analyze_events(rows,{i:None for i in range(15,23)})
        rows=events();rows[0]['rank']=0
        with self.assertRaisesRegex(ValueError,'wrong rank'):
            p.analyze_events(rows,{i:None for i in range(15,23)})

    def test_speculative_half_maps_previous_cycle(self):
        rows=events();e=event('blk.22.attention','attention',0,15,100);e['speculative']=True;rows.append(e)
        *_,sampled=p.analyze_events(rows,{i:None for i in range(14,23)})
        self.assertEqual(sampled,set(range(14,23)))

    def test_pair_statistics_keep_empty_branch_null(self):
        x={'cycle_ms':10,'hit':True};y={'cycle_ms':15,'hit':True}
        result=p.paired_summary([(x,y)])
        self.assertEqual(result['hit']['ratio_instrumented_over_control'],1.5)
        self.assertIsNone(result['miss']['ratio_instrumented_over_control'])

    def test_complete_report_and_missing_branch_refusal(self):
        with tempfile.TemporaryDirectory(prefix='packet57-perturbation-') as temp:
            root=Path(temp)
            for arm,scale in [('control',1),('instrumented',1.2)]:
                for n in range(12):
                    d=root/arm/'repeat-1'/str(n);d.mkdir(parents=True)
                    r=fixture(scale);r['prompt_id']=str(n)
                    (d/'receipt.json').write_text(json.dumps(r))
                    if arm=='instrumented':
                        for rank in (0,1):
                            (d/f'rank{rank}').mkdir()
                            (d/f'rank{rank}/sites.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events() if e['rank']==rank))
            result=p.summarize(root/'control',root/'instrumented')
            self.assertTrue(result['passed']);self.assertTrue(result['no_speed_claim'])
            self.assertEqual(result['full_cycles']['all']['count'],1524)
            self.assertEqual(result['sampled_cycles']['hit']['count'],72)
            self.assertEqual(result['sampled_cycles']['miss']['count'],24)
            self.assertAlmostEqual(result['sampled_cycles']['all']['ratio_instrumented_over_control'],1.2)
            self.assertAlmostEqual(result['classes'][0]['scaling_factor'],1/1.2)
            self.assertAlmostEqual(result['sampled_draft_wall']['all']['ratio_instrumented_over_control'],1.2)
            self.assertAlmostEqual(result['sampled_draft_wall']['all']['paired_delta_median_ms'],.4)
            self.assertEqual(len(result['complete_target_layers']),4)
            self.assertEqual(result['complete_target_layers'][0]['complete_operation_count'],96)
            self.assertAlmostEqual(result['complete_target_layers'][0]['measured_device_sum_median_ms'],.0004)
            for f in (root/'instrumented').glob('repeat-1/*/rank*/sites.jsonl'):
                f.write_text(f.read_text().replace('.ffn.combine','.moe_experts'))
            partial=p.summarize(root/'control',root/'instrumented')['complete_target_layers'][0]
            self.assertEqual(partial['complete_operation_count'],0)
            self.assertEqual(partial['excluded_incomplete_operation_count'],96)
            self.assertIsNone(partial['measured_device_sum_median_ms'])
            for arm,scale in [('control',1),('instrumented',1.2)]:
                for n in range(12):
                    r=fixture(scale,all_hit=True);r['prompt_id']=str(n)
                    (root/arm/'repeat-1'/str(n)/'receipt.json').write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'both hit and miss'):
                p.summarize(root/'control',root/'instrumented')


if __name__=='__main__':unittest.main()

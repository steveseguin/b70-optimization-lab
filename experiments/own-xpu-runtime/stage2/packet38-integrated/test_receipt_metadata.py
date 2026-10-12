#!/usr/bin/env python3
"""Synthetic-clock metadata gates; no device or rank process is executed."""
import copy,json
from types import SimpleNamespace
import pipeline,suite

def run_gates():
    def row(rank,op,pos,token,start,end,fixture=0,spec=False):
        return dict(rank=rank,op=op,position=pos,token=token,rank_received=start,rank_completed=end,fixture=fixture,speculative=spec)
    trace=[row(0,pipeline.HALF,0,3,.1,.3,1),row(0,pipeline.ACCEPT,0,0,.31,.32),
           row(1,pipeline.HALF,0,3,.35,.6,1),row(0,pipeline.HALF,1,7,.4,.5,2,True),
           row(1,pipeline.ACCEPT,0,0,.61,.62),row(0,pipeline.ACCEPT,0,0,.63,.64),
           row(1,pipeline.HALF,1,7,.65,.9,2),row(0,pipeline.HALF,2,8,.7,.8,3,True),
           row(1,pipeline.ACCEPT,0,0,.91,.92),row(0,pipeline.ROLLBACK,0,0,.93,.96)]
    base=dict(stats=dict(hits=1,guesses=2),timing_rows=[dict(generated_index=1,token_id=7),dict(generated_index=2,token_id=8)])
    transport=SimpleNamespace(trace=trace,work_start=0.,work_end=1.,device=True,a=SimpleNamespace(timing='token'),metrics=[dict(gpu_ms=300.,busy_ms=100.),dict(gpu_ms=200.,busy_ms=100.)])
    result=pipeline.enrich_result(copy.deepcopy(base),transport);first,last=result['timing_rows']
    assert abs(first['rank0_to_rank1_handover_ms']-50)<1e-8
    assert first['rank1_to_rank0_overlapped'] and first['rank1_to_rank0_handover_ms']==0
    assert abs(first['rank1_to_rank0_start_minus_finish_ms']+200)<1e-8
    assert last['rank1_to_rank0_handover_ms'] is None  # terminal candidate was rolled back
    assert abs(transport.metrics[0]['gpu_idle_estimate_ms']-550)<1e-8
    assert not transport.metrics[0]['gpu_event_timing_available']
    assert transport.metrics[0]['gpu_idle_estimate_kind']=='lower bound from host command occupancy'
    assert abs(pipeline.command_occupancy_ms(trace+[trace[0]],0,0.,1.)-450)<1e-8  # union does not double-count
    transport.a.timing='class';pipeline.enrich_result(copy.deepcopy(base),transport)
    assert transport.metrics[0]['gpu_idle_estimate_ms']==700 and transport.metrics[0]['gpu_event_timing_available']
    transport.device=False;pipeline.enrich_result(copy.deepcopy(base),transport)
    assert transport.metrics[0]['gpu_idle_estimate_ms'] is None
    # EOS remains in exact tokens/fixtures but not the reference decode span.
    timed=dict(tokens=[7,8,suite.EOS[0]],rank_metrics=[dict(busy_ms=30.),dict(busy_ms=20.)],
        timing_rows=[dict(token_id=t,completed_monotonic=stamp) for t,stamp in ((7,1.),(8,1.05),(suite.EOS[0],1.10))])
    clocks=SimpleNamespace(work_start=0.,work_end=1.10,trace=[row(0,pipeline.HALF,0,0,.99,1.02),
        row(0,pipeline.DRAFT,0,0,1.04,1.08),row(1,pipeline.HALF,0,0,1.01,1.03)])
    suite.timing_metadata(timed,clocks)
    assert timed['tokens']==[7,8,suite.EOS[0]] and len(timed['timing_rows'])==3
    assert timed['decode_event_count']==2 and timed['decode_intervals']==timed['decode_numerator']==1
    assert abs(timed['decode_wall_ms']-50)<1e-8 and timed['decode_first_completed_monotonic']==1. and timed['decode_last_completed_monotonic']==1.05
    assert abs(suite.rate(timed,True)-timed['decode_numerator']*1000/timed['decode_wall_ms'])<1e-8
    assert abs(timed['decode_rank_metrics'][0]['busy_ms']-30)<1e-8 and abs(timed['decode_rank_metrics'][1]['busy_ms']-20)<1e-8
    assert timed['rank_metrics'][0]['busy_ms_per_output_token']==10. and abs(timed['rank_metrics'][0]['idle_ms_per_output_token']-1070./3)<1e-8
    immediate=dict(tokens=[suite.EOS[0]],timing_rows=[dict(token_id=suite.EOS[0],completed_monotonic=1.)],rank_metrics=[dict(busy_ms=0.),dict(busy_ms=0.)])
    suite.timing_metadata(immediate,clocks)
    assert immediate['decode_event_count']==immediate['decode_numerator']==immediate['decode_intervals']==immediate['decode_wall_ms']==0
    assert immediate['decode_first_completed_monotonic'] is None and immediate['decode_last_completed_monotonic'] is None and suite.rate(immediate,True) is None and 'decode_rank_metrics' not in immediate
    return dict(passed=True,device_executed=False,gates=18,synthetic_clocks=True,
                covers=['both handover directions','speculative overlap','terminal rollback exclusion','all-command idle lower bound','interval union','profiled timing retained','CPU never labeled GPU timing','suite EOS-excluded events/numerator/endpoints/rate','suite decode rank clipping','suite per-output rank fields','immediate EOS empty decode span'])
if __name__=='__main__':
    result=run_gates();pipeline.save(pipeline.P/'receipt-metadata-gates.json',result);print(json.dumps(result,indent=2))

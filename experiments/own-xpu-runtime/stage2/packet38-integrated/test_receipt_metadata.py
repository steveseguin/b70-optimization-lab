#!/usr/bin/env python3
"""Synthetic-clock metadata gates; no device or rank process is executed."""
import copy,json
from types import SimpleNamespace
import pipeline

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
    return dict(passed=True,device_executed=False,gates=10,synthetic_clocks=True,
                covers=['both handover directions','speculative overlap','terminal rollback exclusion','all-command idle lower bound','interval union','profiled timing retained','CPU never labeled GPU timing'])
if __name__=='__main__':
    result=run_gates();pipeline.save(pipeline.P/'receipt-metadata-gates.json',result);print(json.dumps(result,indent=2))

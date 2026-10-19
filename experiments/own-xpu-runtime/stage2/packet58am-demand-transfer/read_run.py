"""Offline smoke/v5 reader; all device streams must exist, no time-based abort."""
import argparse,json,statistics
from pathlib import Path
from packet_io import P,AH,sha,save
from analyze import request,stream,demand_stream,require
CLASSES={'incident-retrospective':'operations','code-review':'code','customer-email':'prose','sql-debugging':'code','release-plan':'operations','benchmark-analysis':'analysis','architecture-tradeoff':'analysis','bug-report-synthesis':'operations','technical-guide':'documentation','risk-register':'structured-writing','performance-hypotheses':'analysis','decision-memo':'prose'}
def summary(rows):
    groups={}
    for prompt,row in rows.items():groups.setdefault(CLASSES[prompt],[]).append(row['rate'])
    classes={k:statistics.median(v) for k,v in groups.items()}
    return dict(class_medians=classes,primary=statistics.median(classes.values()),pooled_median=statistics.median(r['rate'] for r in rows.values()))
def decision(rates):
    controls=[rates[k] for k in ('A1','A2')];candidates=[rates[k] for k in ('B0','B1')]
    strict=min(candidates)/max(controls)-1;drift=max(controls)/min(controls)-1
    each=all(b>=1.005*a for b in candidates for a in controls)
    return dict(each_B_beats_each_warm_A_by_half_percent=each,warm_control_drift=drift,strict_gain=strict,
                performance_candidate=each and drift<=.03 and strict>=.02,A0_excluded_from_speed_only=True)
def union(intervals):
    out=[]
    for start,end in sorted(intervals):
        if out and start<=out[-1][1]:out[-1][1]=max(out[-1][1],end)
        else:out.append([start,end])
    return out
def overlap(rows):
    total=0
    for row in rows:
        copies=union((e['start_ns'],e['end_ns']) for e in row['events'] if e['kind']=='packed-H2D')
        compute=union((e['start_ns'],e['end_ns']) for e in row['events'] if e['kind'] in ('resident-gate','missing-gate','resident-down'))
        total+=sum(max(0,min(b,d)-max(a,c)) for a,b in copies for c,d in compute)
    return total
def read(proposal_path,root):
    proposal=json.loads(proposal_path.read_text());cap=proposal['tokens_per_prompt'];rows={};pins={}
    native_path=root/'receipt.json';native=json.loads(native_path.read_text());pins[str(native_path)]=sha(native_path)
    require(native['passed'] and native['safe_to_exit'] and native['device_executed'] and not native['error'],'clean native closure')
    require(native['arithmetic']=='iq3-p49-split32-v1' and native['context']==4096 and native['owner_cards']==1,'native identity')
    require(native['profiling']==proposal['profiling'],'smoke/v5 profiling identity')
    require(native['demand_identity']==proposal['job_name'],'proposal-derived native identity')
    require(native['demand_variant']=='bcs-demand-retained32x2' and native['hc']=='p60fusion' and native['hc_geometry']=='hc-wide' and native['experts']=='wide64+halfcache' and native['other_fusion']=='fused' and native['retirement']=='ordered-foreground' and native['cache_bytes']==21552729600,'full parent composition')
    require(native['submission_data_deadline_enforced'] is False and native['submission_budget_ns'] is None,'no data-proof deadline')
    require(all(t['safe_to_exit'] and t['in_flight']==0 and t['live_bytes']==0 and t['idle_marker_complete'] for t in native['teardown']),'complete native owner teardown')
    # Resident-parent identity is a required part of this amended screen.
    import importlib.util
    spec=importlib.util.spec_from_file_location('demand_resident_receipt',P/'screen/resident_receipt.py')
    resident=importlib.util.module_from_spec(spec);spec.loader.exec_module(resident)
    resident.check_lookups(native)
    all_events=[]
    for view in proposal['views']:
        rows[view]={}
        for prompt in CLASSES:
            folder=root/view/prompt
            for name in ('result.json','timings.jsonl','prefill-timings.jsonl'):
                pins[str(folder/name)]=sha(folder/name)
            result=json.loads((folder/'result.json').read_text());generated=stream(folder/'timings.jsonl');prefill=stream(folder/'prefill-timings.jsonl')
            checked=request(result,generated,prefill);require(result['requested_max_new']==cap,'fixed response cap')
            expected=list(map(int,(P/f'inputs/{prompt}/oracle-{cap}.txt').read_text().split()))
            require(result['tokens']==expected,'unchanged packet49 oracle')
            event_count=64 if cap==64 else 100;times=result['timing_rows'];rate=(event_count-1)/(times[event_count-1]['completed_monotonic']-times[0]['completed_monotonic'])
            rows[view][prompt]=dict(rate=rate,intervals=event_count-1,events=event_count,numerator=event_count-1,
                first=times[0]['completed_monotonic'],last=times[event_count-1]['completed_monotonic'],
                TTFT_ms=(times[0]['completed_monotonic']-result['request_start_monotonic'])*1000,
                prefill_ms=result['prefill_ms'],cold_first_prefill_row=prefill[0],cold_first_generated_row=generated[0])
            for filename,key in [('demand-counters.json','byte_lease_counters'),('demand-bypass.json','fallback_counters')]:
                path=folder/filename;counter=json.loads(path.read_text());pins[str(path)]=sha(path)
                require(all(type(v) is int and v>=0 for k,v in counter.items() if k!='schema'),'integer counter format')
                rows[view][prompt][key]=counter
            rows[view][prompt]['counter_scope']='engine lifetime cumulative snapshot'
            rows[view][prompt]['wall_tok_s']=cap/(result['request_end_monotonic']-result['request_start_monotonic'])
            path=folder/'demand-events.jsonl'
            if cap==64:
                events=stream(path);pins[str(path)]=sha(path);demand_stream(events,proposal['job_name'],len(prefill)+cap)
                expected_mode='off' if view=='S0' else 'bcs-demand-retained32x2'
                require(all(e['mode']==expected_mode for e in events),'smoke view identity')
                if view=='S1':all_events.extend(events)
            else:require(not path.exists() or path.stat().st_size==0,'v5 detailed profiling forbidden')
    report=dict(exact=True,device_executed=True,promotable=False,proposal_sha256=sha(proposal_path),
        job_name=proposal['job_name'],release_condition='coordinator direct-screen release (RELEASE-AMENDMENT.md)',release_amendment_sha256=sha(P/'RELEASE-AMENDMENT.md'),census_gate_superseded=True,views={k:dict(requests=v,**summary(v)) for k,v in rows.items()},evidence_hashes=pins)
    if cap==128:report.update(decision({k:v['primary'] for k,v in report['views'].items()}))
    else:
        parent={}
        for prompt in CLASSES:
            result=json.loads((P.parent/f'packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/run/run/{prompt}/result.json').read_text());t=result['timing_rows'];parent[prompt]=dict(rate=63/(t[63]['completed_monotonic']-t[0]['completed_monotonic']))
        anchor=summary(parent)['primary'];overhead=report['views']['S0']['primary']/anchor-1
        report.update(same_parent=True,observed_overlap_ns=overlap(all_events),eligible_staged_entries=sum(e['staged_entries'] for e in all_events),
            overhead_vs_frozen_parent_fraction=overhead,overhead_qualified=abs(overhead)<=.02,
            overhead_limitations='different process/session; frozen 58aj resident first-64 intervals, not a new primary ceiling or record',
            screening_indices='2..64 only; never the census 2..100 primary bound',
            storage_volume_measured=True,actual_volume_bytes=sum(f.stat().st_size for f in root.rglob('*') if f.is_file()))
        report['smoke_passed']=report['observed_overlap_ns']>0 and report['eligible_staged_entries']>0 and report['overhead_qualified']
    for path,digest in pins.items():require(sha(Path(path))==digest,'evidence edited during analysis')
    return report
def main():
    parser=argparse.ArgumentParser();parser.add_argument('proposal',type=Path);parser.add_argument('root',type=Path);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args();save(a.output,read(a.proposal,a.root))
if __name__=='__main__':main()

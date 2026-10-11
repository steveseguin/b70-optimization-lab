#!/usr/bin/env python3
"""Bounded CPU receipt tests: event execution, omissions and failed owners."""
import copy
import json
from pathlib import Path
import tempfile
import k2

def main():
    base=k2.HERE/'build';base.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='k2-parser-',dir=base) as temp:
        run=Path(temp)
        manifest={'groups':[{'label':'blk.0.route','class':'route','groups_per_token':48}]}
        receipt={'passed':True,'device_executed':True,'safe_to_exit':True,'teardown':[{'safe_to_exit':True,'in_flight':0,'live_bytes':0}]}
        k2.save(run/'manifest.json',manifest);k2.save(run/'receipt.json',receipt)
        rows=[];event=1
        for version in ('v1','v2'):
            for rep in range(200):
                events=[{'event':event,'command_start_ns':100,'command_end_ns':1100},{'event':event+1,'command_start_ns':100000,'command_end_ns':102000}];event+=2
                rows.append({'kernels':version,'label':'blk.0.route','class':'route','groups_per_token':48,'repetition':rep,'events':events})
        def write(rows): (run/'events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        walls=[{'kernels':v,'layer':f'blk.{i}','repetitions':200,'waits':1,'issue_wall_ms':1,'completion_wall_ms':2} for v in ('v1','v2') for i in range(4)]
        (run/'sequence-wall.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in walls));write(rows)
        assert k2.summarize(run)==2
        summary=json.loads((run/'summary.json').read_text());assert all(r['median_execution_us']==3 and r['p90_execution_us']==3 and r['weighted_ms_per_token']==.144 for r in summary['rows'])
        checks=1
        for kind in ('missing','duplicate','wrong_class','wrong_frequency','duplicate_event','zero_duration','failed_receipt','bad_teardown'):
            bad=copy.deepcopy(rows);r=copy.deepcopy(receipt)
            if kind=='missing': bad.pop()
            elif kind=='duplicate': bad.append(bad[-1])
            elif kind=='wrong_class': bad[0]['class']='gather'
            elif kind=='wrong_frequency': bad[0]['groups_per_token']=1
            elif kind=='duplicate_event': bad[1]['events'][0]['event']=bad[0]['events'][0]['event']
            elif kind=='zero_duration': bad[0]['events'][0]['command_end_ns']=100
            elif kind=='failed_receipt': r['passed']=False
            elif kind=='bad_teardown': r['teardown'][0]['in_flight']=1
            write(bad);k2.save(run/'receipt.json',r)
            try: k2.summarize(run)
            except ValueError: checks+=1
            else: raise AssertionError('accepted '+kind)
        print(json.dumps({'gate':'K2 event execution receipt and coverage','checks':checks,'passed':True,'device_executed':False}))
    return 0
if __name__=='__main__': raise SystemExit(main())

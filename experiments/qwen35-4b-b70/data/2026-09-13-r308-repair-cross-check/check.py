#!/usr/bin/env python3
"""Compare unchanged numeric-ID oracles and repaired R307 failures, without GPUs."""
import argparse
import hashlib
import json
from pathlib import Path


def run(old, new):
    archived=old/'evidence/r307-single-request-qualification-20260913'
    if archived.is_dir():old=archived
    paths={'old_oracle':old/'9b-oracle/result.json','old_spec':old/'9b-mtp3-a/result.json',
           'new_oracle':new/'9b-oracle/result.json','new_spec':new/'9b-mtp3-a/result.json'}
    repo=Path(__file__).resolve().parents[4]
    summary={'schema':'r308-repair-cross-check-v1','passed':False,'qualification_complete':False,
             'scope':'9B TP1 depth3 one active request; first R308 speculative server only',
             'sources':{}}
    try:
        data={}
        for key,path in paths.items():
            raw=path.read_bytes();data[key]=json.loads(raw)
            summary['sources'][key]={'path':str(path.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),
                'repo_relative_path':str(path.resolve().relative_to(repo)) if path.resolve().is_relative_to(repo) else None}
            assert data[key]['status']=='complete',f'{key}: incomplete'
        a,b,oa,ob=[data[k] for k in ('old_spec','new_spec','old_oracle','new_oracle')]
        assert a['passed'] is False and all(d['passed'] is True for d in (b,oa,ob))
        assert a['oracle_sha256']==summary['sources']['old_oracle']['sha256']
        assert b['oracle_sha256']==summary['sources']['new_oracle']['sha256']
        for oracle in (oa,ob):
            keys={(r['case'],r['repeat']) for r in oracle['rows']}
            assert len(oracle['rows'])==len(keys)==60
            assert keys=={(f'L{i}',repeat) for i in range(8,28) for repeat in (-1,0,1)}
        ac={c['id']:c for c in a['cases']};bc={c['id']:c for c in b['cases']}
        oac={c['id']:c for c in oa['cases']};obc={c['id']:c for c in ob['cases']}
        assert set(oac)==set(obc)=={f'L{i}' for i in range(8,28)}
        assert set(ac)==set(bc)==set(oac)|{f'L14-tail{i}' for i in range(236,242)}
        for left,right in ((ac,bc),(oac,obc)):
            for key in left:
                assert left[key]['prompt_ids']==right[key]['prompt_ids']
                assert left[key]['expected_ids']==right[key]['expected_ids']
                assert left[key]['max_tokens']==right[key]['max_tokens']
        for d in (a,b,oa,ob):
            cases={c['id']:c for c in d['cases']}
            for case in cases.values():
                assert all(type(x)is int and x>=0 for x in case['prompt_ids']+case['expected_ids'])
            for row in d['rows']:
                case=cases[row['case']]
                assert all(type(x)is int and x>=0 for x in row['token_ids'])
                assert len(row['token_ids'])==len(case['expected_ids'])==case['max_tokens']==row['usage']['completion_tokens']
                assert row['usage']['prompt_tokens']==len(case['prompt_ids']) and row['cached_tokens']==[0]
                assert row['concurrency']==1
                if d is not a:assert row['token_ids']==case['expected_ids']
        lookup={(r['case'],r['repeat'],r['concurrency']):r for r in b['rows']}
        assert len(lookup)==len(b['rows'])==52
        repaired=[]
        for row in a['rows']:
            want=ac[row['case']]['expected_ids']
            if row['token_ids']==want:continue
            fixed=lookup[(row['case'],row['repeat'],row['concurrency'])]
            assert fixed['token_ids']==want
            repaired.append({'case':row['case'],'repeat':row['repeat'],'old_last_id':row['token_ids'][-1],
                'new_last_id':fixed['token_ids'][-1],'oracle_last_id':want[-1],
                'complete_ids_exact':True,'cache_zero':True,'usage_exact':True})
        assert len(repaired)==10
        assert {(r['case'],r['repeat']) for r in repaired}=={(c,i) for c in ('L13','L14','L16','L17','L14-tail238') for i in (0,1)}
        summary.update(passed=True,oracle_cases_unchanged=20,comparison_cases_unchanged=26,repaired_rows=10,repairs=repaired,
                       old_identity=oa['identity'],new_identity=ob['identity'])
    except Exception as exc:
        summary['error']=f'{type(exc).__name__}: {exc}'
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-root',type=Path,required=True,help='Raw campaign root or archived negative packet directory')
    p.add_argument('--new-root',type=Path,required=True,help='R308 qualification root containing9b-oracle and9b-mtp3-a')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();summary=run(a.old_root,a.new_root)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':summary['passed'],'repaired_rows':summary.get('repaired_rows'),'error':summary.get('error')}))
    return 0 if summary['passed'] else 1


if __name__=='__main__':raise SystemExit(main())

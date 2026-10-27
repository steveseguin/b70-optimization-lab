#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
BIN=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/dev/shm/ownrt-depth2/native_controller_depth2_test')

def config(prompt,count,eos=(),dumps=0,start=0,prefill=0,overlap=1,mode=3):
    fields=[mode,count,overlap,dumps,len(prompt),0,len(eos),*prompt,*eos]
    if prefill:fields += ['prefill',prefill]
    if start:fields += ['start',start]
    return ' '.join(map(str,fields))

def invoke(configs,proposals,depth,head_split=False):
    rows=[f'{position} {token}' for position,token in sorted(proposals.items())]
    text=str(len(rows))+' '+' '.join(rows)+'\n'+'\n'.join(configs)+'\n'
    env=dict(os.environ,OWNRT_DRAFT_DEPTH2=str(depth),MOCK_HEAD_SPLIT='1' if head_split else '0')
    run=subprocess.run([str(BIN)],input=text,text=True,capture_output=True,env=env,timeout=30)
    if run.returncode:raise RuntimeError(f'depth {depth} failed: {run.stderr}\ninput:\n{text}')
    return [json.loads(line) for line in run.stdout.splitlines()]

def canonical(result):
    return {key:result[key] for key in ('tokens','state','draft','fixtures','dump_states')}

def proposals_for(result,prompt_length,kind):
    tokens=result['tokens']
    def wrong(token):return (token+1)%31
    if kind=='none':return {}
    first=tokens[0]
    second=tokens[1] if len(tokens)>1 else first
    d2=second if kind in ('both','eos1','eos2','cap','near','continuation','dump','prefill_overlap') else wrong(second)
    d1=first if kind not in ('first','p105') else wrong(first)
    return {prompt_length:d1,prompt_length+1:d2}

cases=[
    ('both-hit',[config([2,3,4],6)],'both'),
    ('second-miss-cancel',[config([2,3,4],6)],'second'),
    ('first-miss-cancel',[config([2,3,4],6)],'first'),
    ('first-miss-cancel-p105',[config([2,3,4],6)],'p105'),
    ('no-guess',[config([2,3,4],5)],'none'),
    ('eos-first-target',[config([2,3,4],6)],'eos1'),
    ('first-miss-p105-confirmed-rank1',[config([2,3,4],6)],'p105'),
    ('eos-second-target',[config([2,3,4],6)],'eos2'),
    ('output-cap-after-pair',[config([2,3,4],3)],'cap'),
    ('output-cap-depth1-tail',[config([2,3,4],4)],'both'),
    ('single-output-empty-lookahead',[config([2,3,4],1)],'both'),
    ('near-end-exact-pair',[config([2,3,4],2)],'near'),
    ('dump-finish-boundaries',[config([2,3,4],5,dumps=1)],'dump'),
    ('non-overlap-depth1',[config([2,3,4],5,overlap=0)],'nonoverlap'),
    ('target-only-depth1',[config([2,3,4],5,mode=0)],'target_only'),
    ('prefill-token-by-token-depth1',[config([2,3,4],5,prefill=1,overlap=0)],'nonoverlap'),
    ('prefill-control-overlap-depth2',[config([2,3,4],5,prefill=1)],'prefill_overlap'),
]
records=[]
for name,configs,kind in cases:
    seed=invoke(configs,{},0)
    proposals=proposals_for(seed[0],3,kind)
    if kind=='eos1':configs=[config([2,3,4],6,eos=(seed[0]['tokens'][0],))]
    elif kind=='eos2':configs=[config([2,3,4],6,eos=(seed[0]['tokens'][1],))]
    baseline=invoke(configs,proposals,0,head_split=kind=='p105')
    candidate=invoke(configs,proposals,1,head_split=kind=='p105')
    assert len(baseline)==len(candidate)
    for index,(b,d) in enumerate(zip(baseline,candidate)):
        assert canonical(b)==canonical(d),f'{name}[{index}] canonical mismatch\n{canonical(b)}\n{canonical(d)}'
    assert candidate[0]['protocol']['rank1_speculative_rows']==0,name
    if kind in ('nonoverlap','target_only'):assert candidate[0]['protocol']['depth2_draft_calls']==0 and candidate[0]['protocol']['depth2_target_rows']==0,name
    if kind=='prefill_overlap':assert candidate[0]['protocol']['depth2_draft_calls']>0 and candidate[0]['protocol']['depth2_target_rows']>0,name
    stats=candidate[0]['stats']
    if name in ('both-hit','output-cap-depth1-tail'):assert stats['hits']>=2,(name,stats)
    if kind=='second':assert stats['hits']>=1 and stats['misses']>=1
    if kind in ('first','p105'):
        protocol=candidate[0]['protocol']
        assert stats['misses']>=1 and protocol['redo_checks']>=1 and protocol['cancelled_verification_writes']==0
        if kind=='p105':assert protocol['head_service_abandons']==0 and protocol['head_merges']>0
    records.append({'name':name,'passed':True,'requests':len(configs),'proposals':proposals,
                    'baseline_tokens':[r['tokens'] for r in baseline],'candidate_stats':stats,
                    'protocol':candidate[0]['protocol'],
                    'dump_positions':[row['position'] for row in candidate[0]['dump_states']]})

seed_configs=[config([1,2,3],1),config([1,2,3,4,5],4,start=3)]
seed=invoke(seed_configs,{},0)
continuation_tokens=seed[1]['tokens']
proposals={5:continuation_tokens[0],6:continuation_tokens[1]}
baseline=invoke(seed_configs,proposals,0)
candidate=invoke(seed_configs,proposals,1)
for index,(b,d) in enumerate(zip(baseline,candidate)):
    assert canonical(b)==canonical(d),f'continuation[{index}] mismatch\n{canonical(b)}\n{canonical(d)}'
records.append({'name':'continuation-checkpoint-stage-finish','passed':True,'requests':2,
                'proposals':proposals,'baseline_tokens':[r['tokens'] for r in baseline],
                'candidate_stats':candidate[-1]['stats'],'dump_positions':[]})

bad=subprocess.run([str(BIN)],input='0\n'+config([2,3,4],1)+'\n',text=True,capture_output=True,
                   env=dict(os.environ,OWNRT_DRAFT_DEPTH2='invalid'),timeout=30)
assert bad.returncode!=0 and 'OWNRT_DRAFT_DEPTH2 must be 0 or 1' in bad.stderr
report={'schema':'ownrt.depth2-controller-tests.v1','binary':str(BIN),'passed':True,
        'invalid_switch_refused':True,'cases':records}
out=ROOT/'controller-test-results.json'
out.write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS {len(records)} differential cases; tokens/target/draft/fixtures/per-dump states identical')

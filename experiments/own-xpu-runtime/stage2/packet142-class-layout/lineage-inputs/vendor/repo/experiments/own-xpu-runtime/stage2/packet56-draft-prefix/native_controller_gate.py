#!/usr/bin/env python3
"""Exhaustive native/Python controller comparison using the same tiny model."""
import argparse, hashlib, itertools, json, random, statistics, subprocess, time
from pathlib import Path
from pipeline import Controller, Draft
from test_state_machine import Mock

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    cases=[];prompt=[1,2,1,2,3];base=Controller(Mock(),Draft()).run(prompt,8)['tokens']
    for n in range(7):
        for pattern in itertools.product((0,1,2),repeat=n):
            guesses=[base[i] if x==1 else (base[i]+1)%31 if x==0 else -1 for i,x in enumerate(pattern)]
            cases.append((prompt,8,'script',guesses,True,[]))
    for seed in range(24):
        rng=random.Random(seed);p=[rng.randrange(31) for _ in range(15)];tokens=Controller(Mock(),Draft()).run(p,128)['tokens']
        cases.append((p,128,'script',[t if rng.randrange(3) else (t+1)%31 for t in tokens],True,[]))
    for overlap in (False,True):
        for mode in ('none','ngram'):
            cases.append(([1,2,7,1,2,9,1,2],64,mode,[],overlap,[]))
        first=Controller(Mock(),Draft()).run([1,2,3],1)['tokens'][0]
        cases.append(([1,2,3],8,'script',[17],overlap,[first]))
    records=[];expected=[]
    for p,count,mode,script,overlap,eos in cases:
        mock=Mock();provider=Draft(mode,script);guesses=[];original=provider.guess
        def record(history,position):
            value=original(history,position);guesses.append(value);return value
        provider.guess=record;out=Controller(mock,provider,overlap).run(p,count,eos)
        expected.append((mock,out,list(guesses)));records.append(' '.join(map(str,[{'none':0,'ngram':1,'script':2}[mode],count,int(overlap),0,len(p),len(script),len(eos),*p,*script,*eos])))
    start=time.monotonic();run=subprocess.run(['nice','-n','19','ionice','-c','3',str(a.binary)],input='\n'.join(records)+'\n',capture_output=True,text=True,timeout=300)
    if run.returncode:raise RuntimeError(f'native controller return {run.returncode}: {run.stderr[:2000]}')
    outputs=[json.loads(line) for line in run.stdout.splitlines()];assert len(outputs)==len(cases)
    handovers=[];wake_latencies=[]
    for actual,(mock,ref,guesses) in zip(outputs,expected):
        assert actual['guess_sequence']==guesses
        expected_hits=[g==ref['tokens'][i] for i,g in enumerate(guesses[:len(ref['tokens'])-1]) if g is not None]
        assert [g['hit'] for g in actual['guess_rows']]==expected_hits
        assert actual['tokens']==ref['tokens']
        assert actual['state']==mock.state
        assert actual['fixtures']==json.loads(json.dumps(mock.fixtures))
        for key in ('guesses','hits','misses','no_guess'):assert actual['stats'][key]==ref['stats'][key],key
        for row in actual['guess_rows']:assert row['hit']==(row['guess']==row['actual'])
        trace=actual['rank_trace']
        for row in trace:
            if row['rank']==1:wake_latencies.append((row['rank_received']-row['sent'])*1e6)
        previous=[None,None]
        for row in sorted(trace,key=lambda r:r['rank_received']):
            if row['op']==1:
                other=previous[1-row['rank']]
                if other is not None and row['rank_received']>=other:handovers.append((row['rank_received']-other)*1e6)
                previous[row['rank']]=row['rank_completed']
    def summary(rows):return {'samples':len(rows),'median_us':statistics.median(rows),'p95_us':sorted(rows)[int(len(rows)*.95)]}
    result=dict(passed=True,device_executed=False,cases=len(cases),ternary_patterns=sum(3**n for n in range(7)),long_random_cases=24,comparison=['tokens','guess_sequence','hit_miss_sequence','guess_counts','hit_miss_counts','final_state','fixtures'],wall_seconds=time.monotonic()-start,bounded_spin_iterations=0,cpu_handover=summary(handovers),cpu_mailbox_wakeup=summary(wake_latencies),binary=str(a.binary),binary_sha256=hashlib.sha256(a.binary.read_bytes()).hexdigest())
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()

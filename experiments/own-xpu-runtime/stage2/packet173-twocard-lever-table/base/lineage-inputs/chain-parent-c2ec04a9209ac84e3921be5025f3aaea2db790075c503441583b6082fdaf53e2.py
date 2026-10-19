#!/usr/bin/env python3
"""CPU exact-output/full-state gates for packet40 retention and cancellation.

Mini mode visits every launch boundary, including before first/after last.
Real mode uses reproducible random plan indices. Never starts a device binary.
"""
import argparse, hashlib, json, os, random, time
from pathlib import Path
import pipeline
from storage import admit, discard
P=Path(__file__).resolve().parent

def state(root):
    return {str(p.relative_to(root)):pipeline.sha(p) for rank in (0,1)
            for p in sorted((root/f'rank{rank}/state-2147483647').rglob('*')) if p.is_file()}

def invoke(binary,root,mini,controller,retain,cap,inputs,script=None,cut=-1):
    admit(550_000_000 if not mini else 25_000_000)
    argv=['--binary',str(binary),'--output',str(root),'--controller',controller,
          '--draft','script' if script else 'none','--tokens',str(cap),'--context','256',
          '--retain-steps',retain,'--cancel-launch',str(cut),'--seconds','172800','--wait-seconds','7200']
    argv+=['--mini'] if mini else ['--input',str(inputs)]
    if script:argv+=['--script',str(script)]
    a=pipeline.parser().parse_args(argv);a.native_nice=19
    a.dispatch=P/('dispatch-all-new.json' if mini else 'dispatch-p38.json')
    a.host_memory='resident' if mini else 'layer-streaming'
    result=pipeline.run(a)
    assert result['passed'] and not result['device_executed']
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True)
    ap.add_argument('--real',action='store_true');ap.add_argument('--input',type=Path,default=P/'build/input')
    ap.add_argument('--controller',choices=('native','python'),default='native')
    ap.add_argument('--random-count',type=int,default=4);a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    assert a.binary.resolve().is_relative_to((P/'build').resolve()) and 'device' not in a.binary.parts
    admit(550_000_000)
    root=P/'build'/('p40-cancellation-'+str(time.time_ns()));root.mkdir()
    cap=2 if a.real else 8
    ref=invoke(a.binary,root/'reference',not a.real,a.controller,'none',cap,a.input)
    expected=ref['tokens'];canonical=state(root/'reference');assert len(expected)==cap and canonical
    plan=json.loads((root/'reference/rank0/launch-plan.json').read_text());
    timed=[json.loads(line) for line in (root/'reference/rank0/timings.jsonl').read_text().splitlines()]
    n=next(row['launches_issued'] for row in timed if row['fixture']>0)
    retained=invoke(a.binary,root/'retained',not a.real,a.controller,'1-8,97-104',cap,a.input)
    assert retained['tokens']==expected and state(root/'retained')==canonical,'retention changed token or full state'
    for rank in (0,1):
        assert json.loads((root/f'retained/rank{rank}/request-state-inventory.json').read_text())==json.loads((root/f'reference/rank{rank}/request-state-inventory.json').read_text()),'retention altered standalone mutable/host state'
    fixture_count=len(list((root/'retained').glob('rank*/step*/layer-*.bf16')))
    assert fixture_count==cap*(48 if a.real else 4)
    discard(root/'retained');discard(root/'reference')
    script=root/'forced-misses.txt';script.write_text(' '.join(str((x+1)%(248320 if a.real else 16)) for x in expected[:-1]))
    cuts=sorted(random.Random(4001).sample(range(n+1),min(a.random_count,n+1))) if a.real else list(range(n+1))
    rows=[]
    for cut in cuts:
        out=root/f'cut-{cut}';r=invoke(a.binary,out,not a.real,a.controller,'none',cap,a.input,script,cut)
        assert r['tokens']==expected and state(out)==canonical,('cancellation changed full state',cut)
        timings=[json.loads(line) for line in (out/'rank0/timings.jsonl').read_text().splitlines()]
        events=[row for row in timings if row['speculative']]
        assert events and all(row['cancelled'] and row['launches_issued']==cut for row in events),(cut,events)
        rows.append(dict(launch_boundary=cut,cancelled_halves=len(events),tokens_equal=True,final_state_hashes_equal=True))
        discard(out)
        print('CPU cancellation boundary',cut,'/',n,'PASS',flush=True)
    result=dict(passed=True,device_executed=False,binary_sha256=pipeline.sha(a.binary),real_model=a.real,
                controller=a.controller,plan_sites=len(plan['launches']),actual_compute_launches=n,gate_count=len(rows)+1,retention_independence=True,
                retained_fixture_files=fixture_count,retention_modes=['none','1-8,97-104'],
                every_launch_boundary=not a.real,random_seed=4001 if a.real else None,
                final_state_sha256=canonical,tokens=expected,rows=rows)
    dest=P/('cancellation-retention-real-' if a.real else 'cancellation-retention-mini-')
    dest=Path(str(dest)+a.controller+'.json');pipeline.save(dest,result);discard(root)
    print(json.dumps(dict(passed=True,receipt=str(dest),gates=result['gate_count'])))
if __name__=='__main__':main()

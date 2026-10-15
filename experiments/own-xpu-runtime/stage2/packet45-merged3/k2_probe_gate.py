"""Mini-only equality proof for the diagnostic second draft, including a bucket boundary."""
import json, os, subprocess, time
from pathlib import Path
import pipeline as pipe
from cpu_merged_gate import assert_host_build, target_state, draft_state, fixtures
from k2_probe_analyze import samples, summarize
from storage import admit, discard
P=Path(__file__).resolve().parent
E=P/'evidence/k2-probe'

def case(root, binary, controller, probe, prompt):
    root.mkdir(); transport=None
    args=pipe.parser().parse_args(['--binary',str(binary),'--output',str(root),'--mini',
        '--context','64','--draft','mtp','--draft-rank','1','--target-split','23',
        '--controller',controller,'--tokens','5','--retain-steps','1-5',
        '--dispatch',str(P/'dispatch-all-new.json')]+(['--diagnostic-unsealed','--mtp-k2-probe'] if probe else []))
    args.host_memory='resident'
    try:
        transport=pipe.Transport.__new__(pipe.Transport);transport.__init__(args,root)
        result=pipe.request_run(transport,pipe.Draft('mtp'),prompt,5)
        for rank in (0,1):transport.call(rank,pipe.DUMP,position=2147483647)
        transport.close(True);transport=None
        result.update(passed=True,device_executed=False,prompt_tokens=len(prompt))
        pipe.save(root/'receipt.json',result)
        state,events=target_state(root)
        signature=dict(tokens=result['tokens'],target_state=state,draft_state=draft_state(root,1),fixtures=fixtures(root),
            guesses=result['guess_sequence'],stats={k:v for k,v in result['stats'].items() if k!='redo_ms'})
        row=dict(controller=controller,probe=probe,prompt_tokens=len(prompt),signature=signature,events=events,raw_stats=result['stats'])
        if probe:
            logs=[json.loads(x) for x in (root/'rank1/mtp-k2-probe.jsonl').read_text().splitlines()]
            rows,censored=samples(result,logs)
            assert len(logs)==5 and all(r['state_restored'] for r in logs)
            row.update(probes=logs,analysis=summarize(rows),end_censored=censored)
        pipe.save(root/'gate-case.json',row)
        row['archive']=discard(root)
        return row
    finally:
        if transport is not None and hasattr(transport,'stop_write') and not transport.closed:
            transport.stop('k2 mini gate cleanup');transport.close(False)

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
    admit(150_000_000)
    binary=P/'build/gnu-host/own-rt-iq3';build=assert_host_build(binary)
    root=P/'build'/('k2-probe-mini-'+str(time.time_ns()));root.mkdir()
    rows=[]
    for controller in ('native','python'):
        for length in (5,31):
            prompt=([2,5,3,7,1]*7)[:length]
            control=case(root/f'{controller}-{length}-off',binary,controller,False,prompt)
            probe=case(root/f'{controller}-{length}-on',binary,controller,True,prompt)
            rows += [control,probe]
            assert control['signature']==probe['signature'], 'probe changed emitted tokens, controller decision or full model state'
            print(json.dumps(dict(controller=controller,prompt_tokens=length,identical=True)),flush=True)
    # Real entrypoint refusal, before output creation or any device contact.
    refuse=root/'must-not-exist'
    commands=[['python3','-B',str(P/'window.py'),'--authorized-device-window','--window','WS',
        '--card','0','--context','4096','--draft-rank','1','--target-split','23','--mtp-k2-probe','--output',str(refuse)],
        [str(binary),'--mtp-k2-probe','--draft-mtp','--rank','1','--draft-rank','1','--target-split','23',
         '--context','4096','--output',str(refuse)]]
    refusals=[]
    for cmd in commands:
        r=subprocess.run(cmd,text=True,capture_output=True)
        assert r.returncode!=0 and 'diagnostic-unsealed' in r.stdout+r.stderr and not refuse.exists()
        refusals.append(dict(argv=cmd,returncode=r.returncode,output=r.stdout+r.stderr))
    receipt=dict(passed=True,device_executed=False,mini_only=True,cases=len(rows),equal_pairs=4,
        probe_samples=sum(len(r.get('probes',[])) for r in rows),qualifying_entrypoint_refusals=refusals,build=build,rows=rows,
        sources={n:pipe.sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','pipeline.py','window.py','k2_probe.py','k2_probe_analyze.py','k2_probe_gate.py')})
    pipe.save(E/'mini-gates.json',receipt)
    root.rmdir()
    print(json.dumps({k:receipt[k] for k in ('passed','cases','equal_pairs','probe_samples')}))
if __name__=='__main__':main()

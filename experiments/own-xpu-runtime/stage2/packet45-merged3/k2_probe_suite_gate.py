"""Persistent mini suite checks reset/log scoping and the real offline analyzer."""
import json,os,time
from pathlib import Path
import pipeline as pipe
from suite import retained_state
from k2_probe_analyze import analyze
from cpu_merged_gate import assert_host_build
from storage import admit,discard
P=Path(__file__).resolve().parent;E=P/'evidence/k2-probe'
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
    admit(150_000_000);binary=P/'build/gnu-host/own-rt-iq3';proof=assert_host_build(binary)
    root=P/'build'/('k2-probe-suite-'+str(time.time_ns()));root.mkdir()
    manifest=dict(arithmetic='iq3-p17-detmath-v2',token_cap=32,context=256,complete=False,prompts=[
        dict(prompt_id='decision-memo',mini_tokens=[2,5,3,7,1],mini_count=5,input_bundle='unused'),
        dict(prompt_id='code-review',mini_tokens=([2,5,3,7,1]*7)[:31],mini_count=5,input_bundle='unused')])
    pipe.save(root/'manifest.json',manifest);results=[]
    for probe in (False,True):
        out=root/('on' if probe else 'off')
        args=pipe.parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--context','256',
            '--draft','mtp','--draft-rank','1','--target-split','23','--controller','native','--tokens','5',
            '--retain-steps','1-5','--dispatch',str(P/'dispatch-all-new.json'),'--suite-manifest',str(root/'manifest.json')]
            +(['--mtp-k2-probe','--diagnostic-unsealed'] if probe else []))
        args.host_memory='resident';summary=pipe.run(args);assert summary['passed']
        signatures={}
        for entry in manifest['prompts']:
            dest=out/'repeat-1'/entry['prompt_id'];r=json.loads((dest/'receipt.json').read_text())
            signatures[entry['prompt_id']]=dict(tokens=r['tokens'],guesses=r['guess_sequence'],
                draft_state=retained_state(dest)['rank1/draft-final-state/all-state.json']['sha256'])
            if probe:assert r['mtp_k2_probe'] and r['diagnostic_unsealed'] and not r['qualifying'] and not r['speed_evidence_eligible']
        results.append(signatures)
        if probe:
            analysis=analyze(out);assert analysis['requests']==2 and set(analysis['per_class'])=={'code','prose'}
            assert analysis['all']['paired_samples']==8 and analysis['end_of_request_g2_censored']==2
            pipe.save(E/'mini-analyzer-example.json',analysis)
            assert summary['qualifying'] is False and summary['diagnostic_unsealed'] is True
    assert results[0]==results[1], 'request reset changed tokens/guesses/draft state'
    archive=discard(root)
    row=dict(passed=True,mini_only=True,device_executed=False,fresh_suites=2,requests_per_suite=2,
        paired_samples=8,prompt_classes=2,unchanged=results[0],archive=archive,build=proof,
        source_sha256={n:pipe.sha(P/n) for n in ('k2_probe_suite_gate.py','k2_probe_analyze.py','k2_probe.py','suite.py','pipeline.py')})
    pipe.save(E/'mini-suite-gates.json',row);print(json.dumps({k:row[k] for k in ('passed','fresh_suites','requests_per_suite','paired_samples')}))
if __name__=='__main__':main()

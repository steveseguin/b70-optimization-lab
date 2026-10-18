#!/usr/bin/env python3
"""Coordinator-reduced Intel real-model gate; diagnostic guess injection only."""
import hashlib,json,os,time
from unittest.mock import patch
import capacity_cpu_gate as cg
import pipeline as pp
import storage
P=cg.P; B=cg.B

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    binary=B/'icpx-host/own-rt-iq3';cg.host_binary(binary)
    _,entry=cg.entries(json.loads(cg.MANIFEST.read_text()))
    inp,oracle,tokens,expected=cg.expected(entry);tokens=tokens[:4]
    expected={k:v for k,v in expected.items() if int(k.split('/')[0][4:])<=4}
    admission=cg.admit(4096);root=B/('intel-composite-'+str(time.time_ns()));root.mkdir()
    a=cg.args_for(binary,root/'run',4096,'mtp','python','icpx-host');a.tokens=4;a.input=inp;a.oracle=oracle
    # The existing native controller has no MTP-script override. Intercept only
    # the Python controller's provider mailbox result after the real draft ran.
    # Target arithmetic, compiled model and verification remain unchanged.
    guesses=[(tokens[0]+1)%248320,(tokens[1]+1)%248320,tokens[2]]
    (root/'guess-script.json').write_text(json.dumps(guesses)+'\n')
    prompt=list(map(int,(inp/'tokens.txt').read_text().split()));injections=[]
    original=pp.Transport.draft_result
    def inject(transport,position):
        row=original(transport,position)
        index=position-len(prompt)
        if 0<=index<len(guesses):
            injections.append(dict(position=position,original=row.get('guess'),forced=guesses[index]))
            row['guess']=guesses[index]
        return row
    watch=cg.MemoryWatch();start=time.monotonic()
    result=None
    try:
        with patch.object(pp.Transport,'draft_result',inject):result=pp.run(a,check=watch.check,launch_hook=watch.launch)
        observed={}
        for rank in (0,1):
            base=a.output/f'rank{rank}'
            for f in base.glob('step*/layer-*.bf16'):
                key=str(f.relative_to(base));assert key not in observed;observed[key]=storage.digest(f)
        assert result['passed'] and not result['device_executed']
        assert result['tokens']==tokens and observed==expected
        assert result['stats']['misses']==2 and result['stats']['hits']==1 and len(injections)==3
        row=dict(passed=True,device_executed=False,no_speed_claim=True,compiler='icpx-host',controller='python',draft='mtp',context=4096,
            token_matches=4,layer_matches=192,tokens=tokens,oracle_tokens=tokens,fixture_sha256=observed,oracle_fixtures=expected,
            binary_sha256=storage.digest(binary),source_sha256=cg.source_identity(),harness_sha256=storage.digest(P/'resume_intel_composite.py'),
            manifest_sha256=storage.digest(cg.MANIFEST),stats=result['stats'],guess_script=guesses,injections=injections,
            injection_scope='diagnostic Python provider mailbox after executing real MTP; no compiled arithmetic/controller edits',
            seconds=time.monotonic()-start,peak_aggregate_rss_anon_bytes=watch.peak,admission=admission,
            pipeline_receipt_sha256=storage.digest(a.output/'receipt.json'))
        cg.save(P/'intel-composite-gate.json',row)
        row['archive']=storage.discard(root);cg.save(P/'intel-composite-gate.json',row)
        print('PASS Intel composite: 4 tokens, 192 layers, two misses and one hit',flush=True)
    except BaseException as error:
        cg.save(P/'intel-composite-failure.json',dict(passed=False,device_executed=False,error=str(error),root=str(root)))
        raise
if __name__=='__main__':main()

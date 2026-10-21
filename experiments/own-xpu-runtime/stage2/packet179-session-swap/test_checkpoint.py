"""Synthetic worker checkpoint arm: three mocked native launches, merged-equality gates.

Orchestration logic only (launch argv, completion/reset gates, determinism and
merged-equality assertions). Synthetic token streams are never model or timing evidence.
The native CPU round trip is covered separately by checkpoint_probe.py.
"""
import copy,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent;p=P/sys.argv[1];sys.path.insert(0,str(p))
import worker,measurement as MEAS
read=lambda f:json.loads(f.read_text())
K,M=worker.CHECKPOINT_K,worker.CHECKPOINT_M
oracle=read(p/'lineage/oracle128'/(worker.CHECKPOINT_PROMPT+'.json'))['tokens']
reference=(oracle+[42]*512)[:512]
prompt=list(map(int,(p/'inputs'/worker.CHECKPOINT_PROMPT/'tokens.txt').read_text().split()))
drain=dict(passed=True,device_executed=True,teardown=[dict(safe_to_exit=True,idle_marker_complete=True,live_bytes=0,in_flight=0,exit_code=0)])

def result(leg,tokens,start):
    r=dict(passed=True,arithmetic=MEAS.ARITHMETIC,cached_tokens=0,requested_max_new=len(tokens),
        prompt_tokens=len(prompt),tokens=tokens,
        timing_rows=[dict(completed_monotonic=start+1+i*.1) for i in range(len(tokens))],
        request_start_monotonic=start,request_end_monotonic=start+90.,prefill_ms=500. if leg=='save' else 0)
    if leg.startswith('restore'):r['checkpoint_restore_ms']=123.4
    return r

def run_arm(mutate=None):
    with tempfile.TemporaryDirectory(prefix='p179-checkpoint-') as td:
        root=Path(td);out=root/'run'
        worker.save(root/'window.json',dict(synthetic=True));worker.save(root/'identity.json',dict(lane='A'))
        ref=root/'ref';dest=ref/'run/native'/worker.CHECKPOINT_PROMPT;dest.mkdir(parents=True)
        worker.save(dest/'result.json',dict(tokens=reference,
            timing_rows=[dict(completed_monotonic=10+i*.1) for i in range(512)],
            request_start_monotonic=9.,request_end_monotonic=70.))
        launches=[]
        class Child:
            returncode=0
            def __init__(self,argv,**kw):
                argv=list(argv);launches.append(argv)
                assert argv[:2]==['/usr/bin/ionice','-c3'],'idle ionice prefix retained'
                assert argv[2]==str(p/'build/device/own-rt-iq3')
                mode=next(a for a in argv if a in ('--checkpoint-save','--checkpoint-restore'))
                assert '--suite-inputs' not in argv,'checkpoint is single-request mode'
                assert argv[argv.index('--checkpoint-id')+1]=='gate'
                assert Path(argv[argv.index('--input')+1])==p/'inputs'/worker.CHECKPOINT_PROMPT/'tokens.txt'
                outpath=Path(argv[argv.index('--output')+1]);outpath.mkdir(parents=True,exist_ok=True)
                max_new=int(argv[argv.index('--max-new')+1])
                leg='save' if mode=='--checkpoint-save' else 'restore'+str(sum(1 for l in launches if '--checkpoint-restore' in l))
                tokens=(reference[:K] if leg=='save' else reference[K:K+M])
                if mutate and leg in mutate:tokens=mutate[leg](list(tokens))
                assert len(tokens)==max_new
                ckroot=Path(argv[argv.index(mode)+1])
                worker.save(outpath/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))
                (outpath/'timings.jsonl').write_text(json.dumps(dict(request=leg,sensor='synthetic'))+'\n')
                (outpath/'prefill-timings.jsonl').write_text(json.dumps(dict(request=leg,sensor='synthetic'))+'\n' if leg=='save' else '')
                worker.save(outpath/'result.json',result(leg,tokens,1000. if leg=='save' else 2000. if leg=='restore1' else 3000.))
                worker.save(outpath/'lookup-request-complete.json',{})
                worker.save(outpath/'receipt.json',drain)
                if leg=='save':
                    gate=ckroot/'gate';gate.mkdir(parents=True,exist_ok=True)
                    worker.save(gate/'manifest.json',dict(format='ownrt.session-checkpoint.v1',label='experimental',
                        measurements=dict(save_seconds=1.5,save_bytes=123456789)))
            def poll(self):return 0
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker.subprocess,'Popen',Child))
            stack.enter_context(patch.object(worker.exec_limits,'check'))
            stack.enter_context(patch.object(sys,'argv',['worker','--output',str(out),'--lane','A','--kind','checkpoint','--reference',str(ref)]))
            rc=worker.main()
        return rc,read(out/'checkpoint-receipt.json'),read(out/'teardown.json'),launches

rc,receipt,teardown,launches=run_arm()
assert rc==0 and len(launches)==3
assert receipt['passed'] and receipt['device_executed'] is False
assert receipt['merged_tokens']==K+M and receipt['repeat_restore_identical'] and receipt['save_eos_free']
assert receipt['oracle_check']['passed'] and receipt['save_bytes']==123456789 and receipt['save_seconds']==1.5
assert receipt['restore_ms']==123.4 and receipt['cold_prefix_ms']>0
assert teardown['drained'] is True
def refuses(fn):
    try:fn()
    except (ValueError,KeyError,AssertionError):return
    raise AssertionError('invalid checkpoint evidence accepted')
# Repeat-restore determinism gate.
refuses(lambda:run_arm(mutate={'restore2':lambda t:t[:5]+[t[5]^1]+t[6:]}))
# Save EOS-free gate (EOS inside the K save tokens is refused by the leg stream check).
refuses(lambda:run_arm(mutate={'save':lambda t:t[:100]+[248046]+t[101:]}))
# Merged-equality gate vs the reference row.
refuses(lambda:run_arm(mutate={'restore1':lambda t:t[:5]+[t[5]^1]+t[6:],'restore2':lambda t:t[:5]+[t[5]^1]+t[6:]}))
worker.save(p/'evidence/checkpoint-test.json',dict(passed=True,device_executed=False,synthetic=True,
    launches=3,merged_tokens=K+M,oracle_cap=128,
    gates=['save K tokens EOS-free','repeat restore determinism','merged == full512 row-A reference [0:K+M)','oracle-128 prefix on merged stream','reset/drain discipline per leg'],
    refusals=['restore2 divergence','EOS inside save tokens','continuation mismatch vs reference'],
    native_transport_mocked=True,scope='real Python worker checkpoint orchestration with synthetic streams; no arithmetic/performance claim; native CPU round trip in checkpoint_probe.py'))
print(p.name,'checkpoint worker arm PASS')

"""CPU real queue main sequence; only process/host admission boundaries simulated."""
import contextlib,json,pathlib,sys,tempfile
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P/'screen'))
import queue_runner as Q, release_gate as G, fault_review as F
records=[]
for kind in ('smoke','v5'):
    proposal=json.loads((P/'proposals'/f'{kind}.json').read_text())
    output=pathlib.Path(proposal['output'])
    with tempfile.TemporaryDirectory(prefix='p58ame-sequence-') as tmp:
        root=pathlib.Path(tmp);out=root/kind;review=root/'review.json';review.write_text('{}')
        calls=[];checks=[]
        class Child:
            returncode=0
            def __init__(self,argv,**kwargs):
                target=pathlib.Path(argv[argv.index('--output')+1]);name=target.name;target.mkdir(parents=True)
                assert name==Q.ORDER[len(calls)]
                assert argv[argv.index('--card')+1]=='0'
                row=dict(window='K1' if name.startswith('K1') else name,passed=True,device_executed=True,
                    child_still_running=False,gpu_count=1,card=0,context=4096,qualifying=False,stop_reasons=[],boot_id='synthetic',
                    lane_admission=dict(passed=True,card=0,scope=Q.W.A.window_scope('K1' if name.startswith('K1') else name),
                                        timing_claim_eligible=False,reservation=dict(boot_id='synthetic')))
                Q.W.save(target/'window.json',row)
                if name=='WSCREEN':
                    (target/'run').mkdir();Q.W.save(target/'run/summary.json',dict(candidate_beats_all_controls=False,synthetic=True))
                calls.append(name)
            def wait(self):return 0
            def poll(self):return 0
        real_read=pathlib.Path.read_text
        def read(path,*a,**kw):
            if path==P/'proposals'/f'{kind}.json':return json.dumps(dict(proposal,output=str(out)))
            return real_read(path,*a,**kw)
        with contextlib.ExitStack() as stack:
            for p in [patch.object(pathlib.Path,'read_text',read),patch.object(Q.subprocess,'Popen',Child),
                      patch.object(Q,'GAP_SECONDS',0),patch.object(Q,'check_exec_limits'),
                      patch.object(Q.W,'storage'),patch.object(Q.W,'user_unit_gate'),patch.object(Q.W,'closed_environment'),
                      patch.object(Q.os,'getpriority',return_value=0),
                      patch.object(Q.os,'sched_getaffinity',return_value={0,1,2,3,16,17,18,19}),
                      patch.object(F,'validate',return_value=({'through_us':1},None,None,None)),
                      patch.object(F,'window_boundary',return_value='synthetic'),
                      patch.object(Q.W.S,'journal',return_value=('',None)),
                      patch.object(G,'authorize',side_effect=lambda k:checks.append(k))]:stack.enter_context(p)
            status=Q.main(['--arm',kind,'--output',str(out),'--fault-review',str(review),
                           '--library-path',proposal['environment']['LD_LIBRARY_PATH'],'--authorized-device-window'])
            assert status==0,(out/'queue.json').read_text()
        state=json.loads((out/'queue.json').read_text())
        assert calls==list(Q.ORDER) and state['passed'] and state['completed']==calls and checks==[kind]
        records.append(dict(kind=kind,order=calls,actual_queue_main=True,actual_verify_success=True,passed=True))
(P/'evidence/p58ame-real-arm-sequence.json').write_text(json.dumps(dict(passed=True,device_executed=False,
    synthetic_transport=True,real_report_test='test_report_recovery.py uses unpatched real output',records=records),indent=2)+'\n')
print('Real queue main K1a/K1b/WSCREEN sequence PASS for smoke and v5; synthetic transport only')

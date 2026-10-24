#!/usr/bin/env python3
"""Two tiny HOST_ONLY rank pairs through the original native controller protocol.
No real model, native device binary, service, or automatic retry is permitted.
"""
import hashlib,importlib.util,inspect,json,os,resource,sys,textwrap,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[3]
PARENT=R/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet/pipeline.py'
PARENT_SHA='4abadf40aa7bdab9400707f0dc9bbb13b104c1278f56b126bf767716459b63e3'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def load_parent():
    assert sha(PARENT)==PARENT_SHA
    spec=importlib.util.spec_from_file_location('gsq_host_pipeline',PARENT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # Preserve the actual protocol/ownership methods. Only isolated CPU launch
    # plumbing differs from the historical coordinator's operational defaults.
    source=textwrap.dedent(inspect.getsource(m.Transport.__init__))
    old='''        rank_home=P/"build"/"driver-cache"/("rank"+str(rank));rank_home.mkdir(parents=True,exist_ok=True)
        cache_warm=any(f.is_file() for f in rank_home.rglob("*"))
        env["HOME"]=str(rank_home)'''
    new='''        rank_home=Path(os.environ["HOME"]);cache_warm=False
        env["HOME"]=os.environ["HOME"]'''
    assert source.count(old)==1;source=source.replace(old,new)
    old='cmd=[str(args.binary),"--rank",str(rank)';assert source.count(old)==1
    source=source.replace(old,'cmd=[str(args.binary),"--gsq-packed","--rank",str(rank)')
    namespace=dict(m.__dict__);exec(compile(source,str(P/'host-transport-constructor.py'),'exec'),namespace)
    class Transport(m.Transport):pass
    Transport.__init__=namespace['__init__'];return m,Transport,source

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
    assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    build=json.loads((P/'evidence/full-host-build.json').read_text());assert build['passed'] and build['mode']=='host'
    binary=Path(build['binary']);assert sha(binary)==build['binary_sha256']
    for f,h in build['source_sha256'].items():assert sha(R/f)==h,f
    m,Transport,constructor=load_parent();out=P/'build'/('host-lifecycle-'+str(time.time_ns()));out.mkdir(mode=0o700)
    (out/'transport-constructor.py').write_text(constructor)
    receipt=dict(passed=False,scope='synthetic HOST_ONLY actual Engine/native-controller initialization and lifecycle',device_executed=False,real_model_loaded=False,source_sha256={str(PARENT):PARENT_SHA,str(Path(__file__).resolve()):sha(__file__)},build_receipt_sha256=sha(P/'evidence/full-host-build.json'),binary_sha256=sha(binary),cases=[])
    try:
        for mode in ('none','mtp'):
            dest=out/mode;dest.mkdir(mode=0o700)
            args=m.parser().parse_args(['--output',str(dest),'--binary',str(binary),'--mini','--draft',mode,'--draft-rank','0','--target-split','24','--context','64','--tokens','4','--seconds','120','--wait-seconds','30','--native-nice','19','--controller','native'])
            args.host_memory='resident';transport=Transport.__new__(Transport);first=None
            try:
                transport.__init__(args,dest,dict(os.environ))
                result=m.NativeController(transport,m.Draft(mode),True,False).run([2,5,3],4,())
                for rank in (0,1):transport.call(rank,m.DUMP,position=2147483647)
                transport.close(True)
                states={str(rank):{str(f.relative_to(dest/f'rank{rank}/state-2147483647')):sha(f) for f in sorted((dest/f'rank{rank}/state-2147483647').rglob('*')) if f.is_file()} for rank in (0,1)}
                assert all(states.values());row=dict(mode=mode,result=result,state_sha256=states,owners=[json.loads((dest/f'rank{r}/receipt.json').read_text()) for r in (0,1)])
                receipt['cases'].append(row);save(dest/'result.json',row)
            except BaseException as error:
                first=error
                if hasattr(transport,'stop_write'):
                    try:transport.stop(error);transport.close(False)
                    except BaseException as cleanup:receipt['cleanup_error']=repr(cleanup)
                receipt['retained_pids']=[p.pid for p in getattr(transport,'children',[]) if p.poll() is None]
                if receipt['retained_pids']:
                    receipt['error']=repr(error);save(out/'receipt.json',receipt)
                    # Keep uncertain synthetic owner resources reachable; root
                    # handles any incident. No hard kill or retry here.
                    while any(p.poll() is None for p in transport.children):time.sleep(1)
                raise first
        a,b=receipt['cases'];assert a['result']['tokens']==b['result']['tokens'],'MTP changed confirmed tokens'
        assert a['state_sha256']==b['state_sha256'],'MTP changed final target state'
        assert len(a['result']['tokens'])==4
        receipt['passed']=True;dest=P/'evidence/host-lifecycle.json';assert not dest.exists();save(dest,receipt)
    except BaseException as error:receipt['error']=repr(error);raise
    finally:save(out/'receipt.json',receipt)
    print(json.dumps({'passed':True,'receipt':str(out/'receipt.json'),'rank_processes':4,'device_executed':False}))
if __name__=='__main__':main()

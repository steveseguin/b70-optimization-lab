"""One root-authorized same-pair HOST_ONLY qualification; never a GPU launcher."""
import hashlib,importlib.util,json,os,resource,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
assert all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'))
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(P/'adapter.py')=='68538b214b7bda9c2fa5cd87534bad2243745b8a1af0dc82b43f01da48b06a01'
spec=importlib.util.spec_from_file_location('gsq_same_pair_adapter',P/'adapter.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
parent=P/'build'/('same-pair-'+str(time.time_ns()));parent.mkdir(mode=0o700)
plan=A.build_plan(parent/'run',mini=True,max_new=4,seconds=120)
A.validate_plan(plan)
A.save(parent/'plan.json',plan)
(parent/'adapter.py.txt').write_bytes((P/'adapter.py').read_bytes())
(parent/'test_adapter.py.txt').write_bytes((P/'test_adapter.py').read_bytes())
(parent/'run.py.txt').write_bytes(Path(__file__).read_bytes())
receipt={'schema':'ownrt.gsq.same-pair-host.v1','passed':False,'device_executed':False,'real_model_loaded':False,'output':str(parent),'plan_sha256':sha(parent/'plan.json'),'adapter_sha256':sha(P/'adapter.py'),'runner_sha256':sha(__file__),'pids':[],'scope':'actual tiny HOST_ONLY Engine with P195 NativeController, same pair target-only/RESET/MTP'}
def admit(p):
    assert p==plan and p['mini'] and not p['native_admitted']
    assert '--authorized-device-window' not in p['rank_argv'][0]
def check():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
def launched(pid):
    receipt['pids'].append(pid)
    (parent/'launch-progress.json').write_text(json.dumps(receipt,indent=2)+'\n')
try:
    result=A.qualification(plan,[2,5,3],4,admit=admit,check=check,launch_hook=launched)
    receipt.update(passed=True,result=result,rank_processes=len(receipt['pids']))
except A.RetainedOwner as error:
    receipt.update(error=repr(error.original),retained=True,secondary=error.secondary)
    A.save(parent/'receipt.json',receipt)
    print(json.dumps({'passed':False,'retained':True,'receipt':str(parent/'receipt.json')}),flush=True)
    # The coordinator remains alive; root owns passive diagnosis/drain. Never
    # silently unwind retained owners, retry, send hard signals or restart.
    while True:time.sleep(1)
except BaseException as error:
    receipt.update(error=type(error).__name__+': '+str(error));A.save(parent/'receipt.json',receipt)
    print(json.dumps({'passed':False,'receipt':str(parent/'receipt.json')}),flush=True)
    raise
else:
    A.save(parent/'receipt.json',receipt)
    A.save(P/'evidence/host-pair.json',receipt)
    print(json.dumps({'passed':True,'receipt':str(parent/'receipt.json'),'rank_processes':len(receipt['pids']),'device_executed':False}))

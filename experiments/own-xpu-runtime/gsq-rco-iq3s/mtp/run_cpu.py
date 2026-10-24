"""Only metadata/stat and in-process synthetic tests; exclusive evidence output."""
from pathlib import Path
import hashlib
import io
import json
import os
import resource
import sys
import unittest

P=Path(__file__).resolve().parent


def main():
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(120,120))
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or not set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32)):
        raise ValueError('nice19/helper CPU placement required')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='2':raise ValueError('thread limit2 required')
    out=P/'evidence'
    out.mkdir(exist_ok=False)
    def save(name,value):
        raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode()+b'\n'
        if len(raw)>5*1024**2:raise ValueError('evidence file bound')
        with (out/name).open('xb') as f:f.write(raw)
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    sources=sorted(P.glob('*.py'))+[P/'source-audit.json',P/'target-bindings.json',P/'draft-manifest.tsv',P/'README.md']
    before={p.name:digest(p) for p in sources}
    save('started.json',dict(source_sha256=before,device_executed=False))
    # Tests use no subprocess/network/model reader. Reject those operations even
    # if an inherited import unexpectedly attempts them in a future version.
    def audit(event,args):
        if event.startswith(('subprocess.','socket.','os.exec','os.spawn','ctypes.dlopen')):
            raise RuntimeError('CPU bridge prohibited operation: '+event)
        if event=='open' and isinstance(args[0],(str,bytes)):
            path=os.fsdecode(args[0])
            if path.endswith(('.gguf','.safetensors')) or path.startswith(('/dev/dri/','/dev/accel/')):
                raise RuntimeError('CPU bridge prohibits model/device opens')
    # unittest.mock imports stdlib ctypes indirectly on some interpreters;
    # initialize test dependencies before installing operation backstop.
    import unittest.mock
    sys.addaudithook(audit)
    import contract
    import bridge
    save('draft-file-metadata.json',contract.draft_inventory())
    save('target-contract.json',contract.bound_contract())
    summaries=[bridge.exercise([1,2,3,4,2],40,m) for m in
               ('hit','miss','mixed','missing','garbage','stale-position',
                'stale-sequence','pre-error','late-error')]
    save('synthetic-cases.json',dict(scope='Injected proposal controls, inherited Python controller and target-state mock; no neural arithmetic',cases=summaries))
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.discover(str(P),pattern='test_*.py'))
    (out/'tests.log').write_text(log.getvalue())
    after={p.name:digest(p) for p in sources}
    stable=before==after
    save('receipt.json',dict(schema='ownrt.gsq-rco.mtp-cpu-bridge.v1',passed=result.wasSuccessful() and stable,
          tests=result.testsRun,source_sha256=after,source_stable=stable,
          artifacts={p.name:dict(sha256=digest(p),bytes=p.stat().st_size) for p in sorted(out.iterdir())},
          cpu_affinity=sorted(os.sched_getaffinity(0)),nice=19,address_space_limit=4*1024**3,
          cpu_seconds_limit=120,tensor_payload_bytes_read=0,native_executed=False,
          device_executed=False,neural_draft_executed=False,new_model_acceptance_qualified=False,
          scope='Metadata compatible plus synthetic Python controller/state and real publication-validator tests; does not attest native kernel arithmetic, timing, GPU lifetime or actual MTP quality',
          write_bytes_before_final_receipt=sum(p.stat().st_size for p in out.iterdir())))
    print(log.getvalue(),end='')
    print(json.dumps(dict(passed=result.wasSuccessful() and stable,tests=result.testsRun)))
    return 0 if result.wasSuccessful() and stable else 1


if __name__=='__main__':raise SystemExit(main())

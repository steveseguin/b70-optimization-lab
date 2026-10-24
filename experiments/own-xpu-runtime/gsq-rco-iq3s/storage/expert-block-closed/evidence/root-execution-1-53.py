"""Root's explicit finite archive phase list, after batch0 fully passed. No retries."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent
helper=P.parent/'closed_expert_bundles.py'
assert hashlib.sha256(helper.read_bytes()).hexdigest()=='614fb7ad65c255b1f26077565749893df97e0b4cc9540ba4d8bbfc951fcf38ee'
assert json.loads((P/'chunk-00-release.json').read_text())['passed']
record={'passed':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'steps':[],'retries':0}
start=time.monotonic()
try:
    for batch in range(1,54):
        for phase in ('archive','prune-verified','offload-verified','release-local-verified'):
            command=[sys.executable,'-B',str(helper),'--'+phase,'--batch',str(batch)]
            r=subprocess.run(command,capture_output=True,text=True)
            record['steps'].append({'batch':batch,'phase':phase,'returncode':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest(),'stderr':r.stderr})
            if r.returncode:raise RuntimeError(f'batch{batch} {phase}: '+r.stderr+r.stdout)
            if not json.loads(r.stdout)['passed']:raise RuntimeError('phase did not pass')
        print(json.dumps({'completed_batch':batch}),flush=True)
    record['passed']=True
finally:
    record['elapsed_seconds']=time.monotonic()-start
    with (P/'root-execution-1-53.json').open('x') as f:json.dump(record,f,indent=2);f.write('\n')

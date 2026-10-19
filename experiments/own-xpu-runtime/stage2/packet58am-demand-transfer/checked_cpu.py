"""Prepare and seal the inert checked row, without GPU or live queue access."""
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
Q=P.parents[1]/'ops/lane-queue'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    proposal=Q/'proposed-p58am-checked-A.txt'
    row=json.loads(next(l for l in proposal.read_text().splitlines() if l.startswith('{')))
    v=json.loads((P/'proposals/checked.json').read_text())
    assert v['views']==['S1'] and v['prompts']==1 and '--checked' in v['native_argv']
    assert '--bracket-inputs' not in v['native_argv'] and '--suite-inputs' not in v['native_argv']
    assert not Path(v['output']).exists()
    # Refresh only adapted harness source pins; compiled source/artifacts stay unchanged.
    receipt=json.loads((P/'build-receipt.json').read_text())
    for f in (P/'screen').glob('*.py'):receipt['sources'][str(f.relative_to(P))]=sha(f)
    package=json.loads((P/'screen-packaging.json').read_text())
    for f in (P/'screen').glob('*.py'):package['files'][str(f.relative_to(ROOT))]=sha(f)
    package['ready_for_device']=False
    package['checked_localization_only']=True
    audit='evidence/p58an-analyzer-audit.json'
    receipt['proofs'][audit]=package['proofs'][audit]=sha(P/audit)
    save(P/'screen-packaging.json',package)
    receipt['ready_for_device']=False
    receipt['queue_packaging_sha256']=sha(P/'screen-packaging.json')
    save(P/'build-receipt.json',receipt)
    seal=json.loads((P/'seal.json').read_text())
    seal['proofs'][audit]=sha(P/audit)
    seal['build_receipt_sha256']=sha(P/'build-receipt.json')
    seal['queue_packaging_sha256']=sha(P/'screen-packaging.json')
    save(P/'seal.json',seal)
    records=[]
    import re
    for label,cmd in [('model',v['native_argv']),('queue',row['argv']),*[(x['stage'],x['argv']) for x in v['pre_stage_commands']]]:
        helpcmd=cmd[:3] if label=='queue' else cmd[:1]
        r=subprocess.run(helpcmd+['--help'],env={'PATH':'/usr/bin:/bin',**v['environment']},stdin=subprocess.DEVNULL,capture_output=True,text=True)
        assert r.returncode==0 and {x for x in cmd if x.startswith('--')}<=set(re.findall(r'--[a-zA-Z0-9-]+',r.stdout))
        (P/f'evidence/p58amd-checked-{label}-help.log').write_text(r.stdout+r.stderr)
        records.append(dict(check=label+'-flags',returncode=0))
    with tempfile.TemporaryDirectory(prefix='p58amd-checked-plan-') as tmp:
        Path(tmp,'queue-A.txt').write_text(proposal.read_text())
        with (P/'evidence/p58amd-checked-plan.log').open('w') as log:
            r=subprocess.run(['python3','-B',str(Q/'lanequeue.py'),'plan','--lane','A','--directory',tmp],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        records.append(dict(check='plan',returncode=r.returncode))
    with (P/'evidence/p58amd-checked-rehearse.json').open('w') as log,(P/'evidence/p58amd-checked-rehearse.log').open('w') as err:
        r=subprocess.run(['python3','-B',str(Q.parent/'rehearse_entry.py'),str(proposal),'--report','--json'],stdin=subprocess.DEVNULL,stdout=log,stderr=err)
    records.append(dict(check='rehearse',returncode=r.returncode))
    assert all(x['returncode']==0 for x in records),records
    save(P/'evidence/p58amd-checked-checks.json',dict(passed=True,device_executed=False,records=records,
        report_scope='shared rehearsal tests inherited smoke/bracket report routes; checked native failure is diagnostic only'))
    files={str(f.relative_to(ROOT)):sha(f) for f in (P/'screen').glob('*.py')}
    for f in [proposal,P/'proposals/checked.json',P/'build/device/own-rt-iq3',P/'build-receipt.json',P/'evidence/p58amd-checked-checks.json',P/'evidence/p58amd-checked-plan.log',P/'evidence/p58amd-checked-rehearse.json']:
        files[str(f.relative_to(ROOT))]=sha(f)
    save(P/'checked-READY.json',dict(ready_for_device=True,diagnostic_only=True,job_name=v['job_name'],
        proposal=str(proposal.relative_to(ROOT)),device_executed=False,queued=False,files=files,
        views=['S1'],prompts=1,model_loads=1,checked=True,final_marker_written_last=True))
    print('Checked localization READY; inert row only')
if __name__=='__main__':main()

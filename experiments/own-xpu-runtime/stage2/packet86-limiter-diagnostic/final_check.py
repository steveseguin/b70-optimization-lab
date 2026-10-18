"""CPU-only seal, source, import and startup-evidence audit; no device execution."""
import json
import subprocess
import sys
from build_engine import P,ROOT,B,sha,save,limits
from policy import VIEWS

def main():
    limits();rows=[]
    for name,h in json.loads((P/'parent-source-manifest.json').read_text()).items():assert sha(ROOT/name)==h,name
    from run_screen import view_path,verify_dependencies
    verify_dependencies()
    # Execute actual imports under the worker's closed environment, without a device.
    cmd=[sys.executable,'-B','-c','import sys; sys.path.insert(0, '+repr(str(P))+'); import worker, policy, report; print("imports PASS")']
    cp=subprocess.run(cmd,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60);cp.check_returncode()
    for lane in ('A','B'):
        for view in VIEWS:
            output=P.parent/'screen/v4-lanes/evidence'/f'packet86-{lane}-a'/view
            cmd=[sys.executable,'-B',str(P/'run_screen.py'),'--view',view,'--lane',lane,'--output',str(output),'--plan']
            cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60);cp.check_returncode();plan=json.loads(cp.stdout)
            assert not plan['device_executed'] and plan['supported'] and plan['identity']['placement']['memory_admitted']
            seal=view_path(view)/'screen-seal.json';row=json.loads(seal.read_text());assert row['diagnostic_nonexact'] and not row['submission_eligible']
            rows.append(dict(lane=lane,view=view,seal_sha256=sha(seal),plan=plan))
    full=json.loads((P/'evidence/fullshape.json').read_text());assert len(full['results'])==16
    assert {(r['choice'],r['result']['rank']) for r in full['results']}=={(v,r) for v in VIEWS for r in (0,1)}
    assert all(r['result']['passed'] and r['result']['prepared_commands']>500 and r['result']['backing_bytes']<8*1024**3 for r in full['results'])
    size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<1_000_000_000
    save(P/'evidence/screen-plans.json',dict(passed=True,device_executed=False,rows=rows))
    save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,diagnostic_nonexact=True,model_payload_read=False,
            closed_environment_imports=True,frozen_parent_hashes_unchanged=True,views=8,fullshape_cases=16,lane_plans=16,
            build_logical_bytes=size,device_binary_sha256=sha(B/'device/own-rt-iq3'),
            evidence={n:sha(P/'evidence'/n) for n in ('cpu-gates.json','operators.json','fullshape.json','fullshape-admission.json','python-tests.log','queue-plans.json','screen-plans.json')}))
    print('eight seals, sixteen real lane plans, full startup evidence and closed imports PASS; build bytes',size)
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Bounded one-shot final CPU gates after both preregistered rank streams."""
import argparse,json,os,time
from cpu_campaign import P,B,PY,execute
from resume_qualification import await_process
from storage import discard

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native-pid',type=int,required=True);ap.add_argument('--suite-pid',type=int,required=True);a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    rows=[]
    def run(name,*args):rows.append(execute(name,[PY,'-B',*args]))
    # Once native's pair has ended, at most the Intel/suite pair remains.
    await_process(a.native_pid,P/'resume-sequence-after-gnu.json')
    root=B/('final-available-oracles-'+str(time.time_ns()))
    run('final-available-oracles',P/'suite_gates.py','--output',root);discard(root)
    await_process(a.suite_pid,P/'resume-sequence-after-mini.json')
    run('final-draft-agreement',P/'cpu_campaign.py','draft-final')
    run('final-integration-inventory',P/'integration_inventory.py')
    run('final-integrity',P/'integrity_audit.py')
    run('seal-bootstrap',P/'seal.py','--bootstrap')
    run('seal-window-admission',P/'test_window_seal_admission.py','--build-receipt',P/'build-admission-candidate.json')
    run('final-seal',P/'seal.py')
    (P/'finish-sequence.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
if __name__=='__main__':main()

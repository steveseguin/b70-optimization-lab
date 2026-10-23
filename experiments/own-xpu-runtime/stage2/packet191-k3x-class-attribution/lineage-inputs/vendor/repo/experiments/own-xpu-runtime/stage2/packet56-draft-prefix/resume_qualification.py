#!/usr/bin/env python3
"""Resume qualification once, with two bounded CPU rank streams and no retries."""
import argparse,json,os,time
from pathlib import Path
from cpu_campaign import execute,P,B,PY
from storage import discard

def await_process(pid,receipt):
 deadline=time.monotonic()+14400
 while Path('/proc',str(pid)).exists():
  if time.monotonic()>deadline:raise RuntimeError('bounded prerequisite wait expired')
  time.sleep(2)
 r=json.loads(receipt.read_text());assert r.get('passed') is True,('prerequisite failed',str(receipt))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('stream',choices=['after-mini','after-gnu']);ap.add_argument('--wait-pid',type=int,required=True);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 prerequisite=P/('native-mini-cpu.json' if a.stream=='after-mini' else 'campaign-real-gnu.json')
 await_process(a.wait_pid,prerequisite);rows=[]
 def run(name,*args):rows.append(execute(name,[PY,'-B',*args]))
 if a.stream=='after-mini':
  for script,phase in [('suite_gates.py','suite'),('window_cpu_gate.py','fixtures'),('window_cpu_gate.py','models')]:
   root=B/('resume-final-'+phase+'-'+str(time.time_ns()))
   args=[P/script,'--output',root]
   if script=='window_cpu_gate.py':args+=['--phase',phase]+(['--skip-wrapper-tests'] if phase=='fixtures' else [])
   run('resume-'+phase,*args);discard(root)
  run('resume-captures',P/'cpu_campaign.py','captures')
  run('resume-real-intel',P/'cpu_campaign.py','real-intel')
  run('resume-suite-real',P/'cpu_campaign.py','suite')
 else:
  run('resume-real-native',P/'cpu_campaign.py','real-native')
 (P/('resume-sequence-'+a.stream+'.json')).write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
if __name__=='__main__':main()

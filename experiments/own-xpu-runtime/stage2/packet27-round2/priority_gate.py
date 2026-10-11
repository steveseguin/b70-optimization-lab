"""Run the host-only entry through the wrapper command path at nice 0 and 19.
The user manager creates fresh CPU children so an inherited nice19 process never
tries to raise its own priority. No device-linked executable is started.
"""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
import window
from cpu_gates import host,sha
P=Path(__file__).resolve().parent;B=P/'build'
def child(binary,output,priority):
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 host(binary);identity=window.priority_gate(priority)
 # Reuse the actual wrapper builder, then substitute the CPU priority probe.
 cfg=dict(card=0,cards=1,timing='token',memory='layer-streaming',stage='decode',gemv='r5',count=8,context=256)
 cmd=window.native_command(binary,cfg,B/'input','unused',B/'unused',output,600,native_nice=priority)
 cmd.remove('--authorized-device-window');cmd+=['--priority-probe']
 result=subprocess.run(['ionice','-c','3']+cmd,capture_output=True,text=True)
 assert result.returncode==0,result.stderr
 receipt=json.loads((output/'run/priority.json').read_text());assert receipt['actual_nice']==receipt['requested_nice']==priority
 bad=list(cmd);bad[bad.index('--native-nice')+1]=str(19 if priority==0 else 0)
 rejected=subprocess.run(['ionice','-c','3']+bad,capture_output=True,text=True)
 assert rejected.returncode==1 and 'native priority differs' in rejected.stderr
 receipt['mismatched_priority_rejected']=True
 (output/'wrapper-priority.json').write_text(json.dumps(dict(**identity,**receipt,argv=cmd),indent=2)+'\n')
 return receipt
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--child',type=int);parser.add_argument('--output',type=Path);a=parser.parse_args()
 binary=B/'host/own-rt-iq3'
 if a.child is not None:child(binary,a.output,a.child);return
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 root=B/('priority-'+str(time.time_ns()));root.mkdir();rows=[]
 for priority in (0,19):
  out=root/str(priority)
  cmd=['systemd-run','--user','--quiet','--wait','--pipe','--collect','--property=Nice='+str(priority),'--property=IOSchedulingClass=idle','--setenv=OMP_NUM_THREADS=2','--setenv=PYTHONDONTWRITEBYTECODE=1','/home/steve/.venvs/vllm-xpu/bin/python','-B',str(P/'priority_gate.py'),'--child',str(priority),'--output',str(out)]
  result=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
  assert result.returncode==0,result.stderr
  rows.append(json.loads((out/'wrapper-priority.json').read_text()))
 (P/'priority-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,binary_sha256=sha(binary),tests=rows),indent=2)+'\n')
if __name__=='__main__':main()

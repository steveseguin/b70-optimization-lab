"""CPU-only native comparisons and exact device-argv preparation/refusal tests."""
from pathlib import Path
import sys,subprocess,json,tempfile,hashlib
from analyze import limits
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn
from launch_env import environment

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 limits()
 with turn():
  for name,file,shape in [('synthetic','synthetic','synthetic'),('real',str(P/'build/micro-inputs'),'all')]:
   cmd=[str(P/'build/micro-host'),'--rank','0','--rows-file',file,'--shape',shape,'--repeats','200','--coordinator-admitted-device-window']
   with (P/f'evidence/micro-prep/{name}-cpu.jsonl').open('w') as f:
    subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True)
 proposal=P.parents[1]/'ops/lane-queue/proposed-p162-micro-B.txt'
 job=json.loads(proposal.read_text());spec=job['plan']['entry_rehearsal'];h=sha(P/'build/micro-device')
 spec['binaries'][0]['sha256']=h;spec['prepare_probe']['sha256']=h
 spec['prepare_probe']['sources'][str((P/'micro.cpp').relative_to(ROOT))]=sha(P/'micro.cpp')
 proposal.write_text(json.dumps(job)+'\n')
 cmd=spec['prepare_probe']['command'];env=environment();env['ENTRY_PREPARE_OUTPUT']='/tmp/packet162b-cpu-probe'
 checks=[]
 for label,argv in [('exact',cmd),('rank',[*cmd[:2],'0junk',*cmd[3:]]),('repeat',[*cmd[:8],'200junk',*cmd[9:]]),('truncated',cmd[:-1]),('unknown',cmd+['--unknown','1'])]:
  cp=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  assert cp.returncode==(0 if label=='exact' else 1),(label,cp.returncode)
  checks.append(dict(case=label,returncode=cp.returncode,passed=True))
 with tempfile.TemporaryDirectory() as tmp:
  bad=Path(tmp)/'rows.bin';bad.write_bytes(b'bad')
  args=[str(P/'build/micro-host'),'--rank','0','--rows-file',str(bad),'--shape','layer0','--repeats','200','--coordinator-admitted-device-window']
  cp=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  assert cp.returncode==1 and 'raw extent' in cp.stderr
  checks.append(dict(case='truncated rows rejected on CPU',passed=True))
 (P/'evidence/micro-prep/parser-tests.json').write_text(json.dumps(dict(passed=True,device_executed=False,checks=checks,binary_sha256=h,host_binary_sha256=sha(P/'build/micro-host')),indent=2)+'\n')
if __name__=='__main__':main()

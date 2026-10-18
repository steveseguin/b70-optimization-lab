"""Host-only negative admission/exit checks; native binaries are never executed."""
import hashlib,json,os,subprocess,time
from pathlib import Path
from cpu_gates import host
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 root=P/'build'/('entry-codes-'+str(time.time_ns()));root.mkdir();rows=[]
 for name in ('own-rt-iq3','nongemv-fixtures','k2-fixtures'):
  binary=P/'build/gnu-host'/name;host(binary)
  for kind in ('missing-arguments','device-authorization-refusal'):
   args=[] if kind=='missing-arguments' else ['--authorized-device-window','--output',str(root/(name+'-'+kind))]
   if name=='own-rt-iq3' and args:args+=['--mini']
   result=subprocess.run([str(binary),*args],capture_output=True,text=True,timeout=10)
   assert result.returncode==1,(name,kind,result.returncode)
   rows.append(dict(entry=name,case=kind,returncode=result.returncode,binary_sha256=sha(binary),stderr=result.stderr[:500]))
 (P/'entry-codes.json').write_text(json.dumps(dict(passed=True,device_executed=False,checks=rows,success_exit_evidence=['integration-gates.json','fixture-gates.json','entry-smoke.json'],native_K2_success_execution='pending coordinator K2'),indent=2)+'\n')
 print(len(rows),'negative entry checks passed')
if __name__=='__main__':main()

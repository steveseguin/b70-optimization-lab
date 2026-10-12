"""All dense template instantiations; two fresh owners per compiler, CPU only."""
import hashlib,json,os,subprocess,time
from pathlib import Path
from cpu_gates import host
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 root=B/f'linked-fixtures-{time.time_ns()}';root.mkdir();rows=[];expected=None
 for compiler in ('gnu-host','icpx-host','asan'):
  binary=B/compiler/'p33-linked-fixtures';host(binary)
  for repeat in range(2):
   out=root/f'{compiler}-{repeat}'
   r=subprocess.run([str(binary),'--output',str(out)],capture_output=True,text=True)
   assert r.returncode==0,r.stderr
   receipt=json.loads((out/'receipt.json').read_text())
   assert receipt['passed'] and receipt['reference_exact'] and not receipt['device_executed']
   assert receipt['checks']==216 and receipt['split_instantiations']==36 and receipt['output_rows']==1512
   assert receipt['teardown']['safe_to_exit'] and receipt['teardown']['exit_code']==0
   digest=sha(out/'output.bin');assert digest==receipt['output_sha256']
   assert expected is None or digest==expected;expected=digest
   rows.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),receipt=receipt,cases_sha256=sha(out/'cases.jsonl')))
   print(compiler,repeat,'PASS',flush=True)
 (P/'p33-linked-fixture-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows,checks=1296,output_rows=9072,output_sha256=expected),indent=2)+'\n')
if __name__=='__main__':main()

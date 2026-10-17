"""Small arithmetic fixtures only, under GNU and Intel host compilers."""
import hashlib,json,os,resource,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 rows=[]
 for mode in ('gnu-host','intel-host'):
  command=[str(P/'build'/f'{mode}-batch-fixture'),str(P/'fixture'/mode)]
  env=dict(os.environ,LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
  r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env)
  (P/'evidence'/f'{mode}-fixture.log').write_text(r.stdout+r.stderr);r.check_returncode()
  result=json.loads(r.stdout);assert result['passed'] and result['byte_checks']>100
  expected=P/'fixture'/f'{mode}-expected.bin';actual=P/'fixture'/f'{mode}-actual.bin'
  assert sha(expected)==sha(actual)
  rows.append(dict(compiler=mode,command=command,result=result,expected_sha256=sha(expected),actual_sha256=sha(actual)))
 # Cross-compiler bytes must also agree, in addition to each compiler's oracle.
 assert rows[0]['expected_sha256']==rows[1]['expected_sha256']
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('cpu_gate.py','batch_fixture.cpp','batched_rows.hpp','batched_hc.hpp','batched_experts.hpp','batch_probe.hpp')}
 receipt=dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,model_executed=False,changed_class='paired dense GEMV, HC and routed expert union exact ordered arithmetic',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(P/'build-device-receipt.json'),sources=sources,compilers=rows)
 for key in ('expected','actual'):
  p=P/'fixture'/f'gnu-host-{key}.bin';receipt[key]=dict(path=str(p.relative_to(P)),sha256=sha(p))
 (P/'fixture/receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(passed=True,compilers=rows),indent=2))
if __name__=='__main__':main()

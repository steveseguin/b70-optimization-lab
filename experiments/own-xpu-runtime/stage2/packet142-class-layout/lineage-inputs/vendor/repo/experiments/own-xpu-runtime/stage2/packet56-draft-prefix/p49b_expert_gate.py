"""Two fresh owner processes per CPU compiler mode, including actual M=2 rows."""
import json,os,subprocess,time
from pathlib import Path
import build
from cpu_gates import host
from storage import digest
from p49_cpu_gate import summarize_receipt
P=Path(__file__).resolve().parent;B=P/'build'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 root=B/('p49b-expert-'+str(time.time_ns()));root.mkdir()
 rows=[]
 for mode in ('gnu-host','asan'):
  binary=B/mode/'p49b-expert-fixtures';host(binary)
  assert json.loads((P/f'build-{mode}-receipt.json').read_text())['compiled_sources_sha256']==build.compiled_sources()
  env=dict(os.environ,ASAN_OPTIONS='halt_on_error=1:detect_leaks=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
  for repeat in range(2):
   out=root/(mode+'-'+str(repeat));log=out.with_suffix('.log')
   with log.open('w') as stream:run=subprocess.run([str(binary),'--output',str(out)],env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
   assert run.returncode==0,str(log)
   assert 'runtime error:' not in log.read_text() and 'ERROR: AddressSanitizer' not in log.read_text()
   receipt=json.loads((out/'receipt.json').read_text());assert receipt['passed'] and receipt['reference_exact'] and not receipt['device_executed'] and receipt['checks']==48
   rows.append(dict(mode=mode,sanitizer_options={k:env[k] for k in ('ASAN_OPTIONS','UBSAN_OPTIONS')},output=str(out),binary_sha256=digest(binary),output_sha256=digest(out/'output.bin'),native_receipt_sha256=digest(out/'receipt.json'),receipt=summarize_receipt(receipt)))
 assert len({row['output_sha256'] for row in rows})==1
 (P/'p49b-expert-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,compiled_sources_sha256=build.compiled_sources(),rows=rows),indent=2)+'\n')
 print('192 expert owner checks passed across GNU and ASAN/UBSAN')
if __name__=='__main__':main()

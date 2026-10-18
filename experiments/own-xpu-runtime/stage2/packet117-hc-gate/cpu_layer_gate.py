"""Execute only the GNU host mock of the complete copied layer harness."""
import json,os,subprocess
from build_engine import P,limits
from build_layer import sha

def main():
 limits();out=P/'evidence/full-gnu-host';out.mkdir(exist_ok=True)
 receipt=json.loads((P/'evidence/build-gnu-host.json').read_text())
 binary=P/'build/gnu-host/layer-bench'
 assert receipt['passed'] and receipt['mode']=='gnu-host' and sha(binary)==receipt['artifacts']['build/gnu-host/layer-bench']
 command=[str(binary),'--cpu-test','--mode','exact','--layer','both','--output',str(out)]
 with (P/'evidence/full-gnu-host.log').open('w') as log:
  subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OMP_NUM_THREADS':'2','OMP_THREAD_LIMIT':'2'},check=True,timeout=600)
 row=json.loads((out/'receipt.json').read_text())
 assert row['passed'] and row['cpu_mock'] and not row['device_executed'] and row['safe_to_exit'] and row['checks']>800
 (P/'evidence/cpu-layer.json').write_text(json.dumps(dict(passed=True,device_executed=False,command=command,binary_sha256=sha(binary),receipt_sha256=sha(out/'receipt.json'),native=row),indent=2)+'\n')
 print('full QSA/GDN host mock, all mutable state and exceptional HC cases: PASS',row['checks'])
if __name__=='__main__':main()

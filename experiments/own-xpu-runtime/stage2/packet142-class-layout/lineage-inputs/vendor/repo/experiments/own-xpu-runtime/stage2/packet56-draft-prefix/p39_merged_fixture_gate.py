"""Actual CPU owner-path epilogue exactness; never enters an accelerator binary."""
import gzip,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert shutil.disk_usage('/').free>=8_000_000_000,'root below 8 GB free'
 root=B/('p39-actual-'+str(time.time_ns()));root.mkdir()
 binary=B/'gnu-host/p39-merged-fixtures';report=P/'p39-merged-fixture-gates.json'
 command=['nice','-n','19','ionice','-c','3',str(binary),str(root)]
 receipt=dict(schema='packet45.merged-p39-fixture.v1',passed=False,device_executed=False,command=command,binary_sha256=sha(binary))
 try:
  result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
  receipt['log']=result.stdout.decode(errors='replace');receipt['exit_code']=result.returncode
  if result.returncode:raise RuntimeError('actual merged p39 helper failed')
  actual=json.loads((root/'receipt.json').read_text());assert actual['passed'] and actual['checks']==56 and not actual['device_executed']
  receipt.update(actual);receipt['output_sha256']=sha(root/'output.bin')
  from build import compiled_sources
  receipt['compiled_sources_sha256']=compiled_sources()
  report.write_text(json.dumps(receipt,indent=2)+'\n')
  shutil.rmtree(root)
 except BaseException as error:
  receipt.update(passed=False,error=str(error));report.write_text(json.dumps(receipt,indent=2)+'\n');raise
 print(json.dumps({'passed':True,'checks':56,'binary_sha256':receipt['binary_sha256']}))
if __name__=='__main__':main()

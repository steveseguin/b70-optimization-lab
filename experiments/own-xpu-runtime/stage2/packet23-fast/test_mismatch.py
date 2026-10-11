"""CPU-only wrong-fixture rejection; both arithmetic paths must fail closed."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile
HERE=Path(__file__).resolve().parent

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 binary=HERE/'build/host/own-rt-iq3'
 libs=subprocess.check_output(['readelf','-d',str(binary)],text=True,timeout=5).lower()
 assert not any(x in libs for x in ['libsycl','libze_loader','libur_loader','libopencl'])
 scratch=Path(tempfile.mkdtemp(prefix='mismatch-',dir=HERE/'build'));rows=[]
 try:
  base=scratch/'base'
  subprocess.run([str(binary),'--mini','--tokens','1','--nongemv','core','--output',str(base)],check=True,capture_output=True,timeout=30)
  oracle=scratch/'oracle/step1';oracle.mkdir(parents=True)
  raw=bytearray((base/'step1/layer-00.bf16').read_bytes());raw[0]^=1
  (oracle/'layer-00.bf16').write_bytes(raw)
  for mode in ['core','parallel']:
   out=scratch/mode
   result=subprocess.run([str(binary),'--mini','--tokens','1','--nongemv',mode,'--oracle',str(oracle.parent),'--output',str(out)],capture_output=True,text=True,timeout=30)
   receipt=json.loads((out/'receipt.json').read_text())
   assert result.returncode and receipt['passed'] is False and receipt['oracle_exact'] is False and receipt['error']=='first differing layer 0 step 1'
   assert all(t['safe_to_exit'] and t['live_bytes']==0 for t in receipt['teardown'])
   rows.append(dict(nongemv=mode,passed=True,expected_rejection=receipt['error'],oracle_exact=False))
  receipt=dict(passed=True,device_executed=False,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),tests=rows)
  (HERE/'cpu-mismatch-rejection.json').write_text(json.dumps(receipt,indent=2)+'\n')
  print('2/2 CPU wrong-fixture rejections pass')
 finally:shutil.rmtree(scratch)
if __name__=='__main__':main()

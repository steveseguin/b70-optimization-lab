"""Fresh CPU comparison of --fusion off with the sealed packet18 control."""
import hashlib,json,os,subprocess,time
from pathlib import Path
import test
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 current=B/'host/own-rt-iq3';baseline=P.parent/'packet18-decode-v2/build/host/own-rt-iq3'
 for binary in (current,baseline):
  elf=subprocess.check_output(['readelf','-d',str(binary)],text=True)
  assert not any(x in elf.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
 assert sha(baseline)==json.loads((P.parent/'packet18-decode-v2/build-receipt.json').read_text())['artifacts_sha256']['host/own-rt-iq3']
 root=B/f'control-{time.time_ns()}';root.mkdir();os.environ['PACKET21_FUSION']='off'
 result=test.run(current,root/'integration',B/'input','parallel');comparisons=[]
 for cards in (1,2):
  for n in (1,3,8):
   args=['--mini','--card','0','--cards',str(cards),'--memory','resident' if cards==2 else 'layer-streaming','--tokens',str(n),'--nongemv','parallel']
   if n==8:args+=['--input',str(root/'integration/single-token.txt')]
   out=root/f'baseline-{cards}-{n}';subprocess.run([str(baseline),*args,'--output',str(out)],check=True,stdout=subprocess.DEVNULL)
   control=root/f'integration/mini-{cards}-{n}'
   for path in [out/'buffers.json',*out.glob('step*/layer-*.bf16')]:
    assert path.read_bytes()==(control/path.relative_to(out)).read_bytes()
   a=json.loads((out/'receipt.json').read_text());b=json.loads((control/'receipt.json').read_text());assert a['tokens']==b['tokens'] and a['passed'] and b['passed']
   comparisons.append(dict(cards=cards,tokens=n,buffers_sha256=sha(out/'buffers.json'),fixture_hashes={str(x.relative_to(out)):sha(x) for x in out.glob('step*/layer-*.bf16')}))
 result.update(baseline_sha256=sha(baseline),control_comparisons=comparisons,passed=True)
 (P/'cpu-control.json').write_text(json.dumps(result,indent=2)+'\n')
 print('control integration',len(result['tests']),'packet18 comparisons',len(comparisons),'PASS',flush=True)
if __name__=='__main__':main()

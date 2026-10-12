"""Build only the host adapter; never discover or open devices."""
import hashlib,json,os,subprocess,re,difflib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
P=ROOT/'experiments/own-xpu-runtime/stage2/packet17-detmath'
S=P.parent; OWNER=S.parent/'stage1/packet3-prep/src'
PREFIX=['nice','-n','19','ionice','-c','3']
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert int(subprocess.check_output(PREFIX+['df','-B1','/'],text=True).splitlines()[-1].split()[3])>=8_000_000_000
 sealed=json.loads((HERE.parent/'arithmetic-v2-detmath-20261011/receipt.json').read_text())
 for name,digest in sealed['arithmetic']['arithmetic_sources'].items():assert sha(ROOT/name)==digest,name
 B=HERE/'build'; B.mkdir(exist_ok=True)
 overlay=B/'overlay';overlay.mkdir(exist_ok=True)
 names=('runtime_main.cpp','runtime_kernels.hpp','runtime_kernels.cpp','performance.hpp','performance.cpp')
 changes={'runtime_main.cpp':('scratch.push_back(allocate(c, "operator-scratch", 256ull * 1024 * 1024,','scratch.push_back(allocate(c, "operator-scratch", 512ull * 1024 * 1024,'),'runtime_kernels.hpp':('c.pool = {scratch, 0, 64ull * 1024 * 1024, 0};','c.pool = {scratch, 0, 128ull * 1024 * 1024, 0};')}
 overlay_receipt={};patch=[]
 for name in names:
  original=(P/name).read_text();changed=original
  if name in changes:
   old,new=changes[name];assert changed.count(old)==1;changed=changed.replace(old,new)
   patch.extend(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='packet17/'+name,tofile='host-overlay/'+name))
  def include(match):
   target=match.group(1)
   if target in names:return '#include "'+str(overlay/target)+'"'
   resolved=(P/target).resolve()
   return '#include "'+str(resolved)+'"' if resolved.exists() else match.group(0)
  generated=re.sub(r'#include "([^"\n]+)"',include,changed)
  (overlay/name).write_text(generated)
  overlay_receipt[name]=dict(original_sha256=sha(P/name),generated_sha256=sha(overlay/name),change='scratch allocation/bounds only' if name in changes else 'include relocation only')
 (HERE/'scratch-capacity.patch').write_text(''.join(patch))
 base=['g++' ,'-std=c++20','-O2','-mfma','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-fopenmp']
 inc=['-I'+str(q) for q in (overlay,OWNER,S/'packet2/kernels',S/'packet2/loader',P)]
 src=[HERE/'oracle_long.cpp',overlay/'performance.cpp',overlay/'runtime_kernels.cpp',S/'packet4/owner_retire.cpp',S/'packet2/loader/gguf.cpp',OWNER/'owner.cpp']
 command=PREFIX+base+inc+list(map(str,src))+['-lcrypto','-o',str(B/'oracle.tmp')]
 subprocess.run(command,check=True,timeout=240,env={**os.environ,'TMPDIR':str(B)})
 deps=subprocess.check_output(PREFIX+['readelf','-d',str(B/'oracle.tmp')],text=True)
 assert not any(x in deps for x in ('libsycl','libze_loader','libOpenCL','libcuda'))
 (B/'oracle.tmp').rename(B/'oracle')
 receipt=dict(host_scratch_bytes=512*1024*1024,host_overlay=overlay_receipt,overlay_patch_sha256=sha(HERE/'scratch-capacity.patch'),passed=True,device_executed=False,command=command,binary_sha256=sha(B/'oracle'),source_sha256=sha(HERE/'oracle_long.cpp'),sealed_binary_sha256=sealed['binary_sha256'],arithmetic=sealed['arithmetic'],dynamic_dependencies=deps,compiler=subprocess.check_output(PREFIX+['g++','--version'],text=True))
 temp=HERE/'build-receipt.json.tmp';temp.write_text(json.dumps(receipt,indent=2)+'\n');temp.replace(HERE/'build-receipt.json')
if __name__=='__main__':main()

"""Build only the host adapter; never discover or open devices."""
import hashlib,json,os,subprocess
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
 base=['g++','-std=c++20','-O2','-mfma','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-fopenmp']
 inc=['-I'+str(q) for q in (OWNER,S/'packet2/kernels',S/'packet2/loader',P)]
 src=[HERE/'oracle128.cpp',P/'performance.cpp',P/'runtime_kernels.cpp',S/'packet4/owner_retire.cpp',S/'packet2/loader/gguf.cpp',OWNER/'owner.cpp']
 command=PREFIX+base+inc+list(map(str,src))+['-lcrypto','-o',str(B/'oracle.tmp')]
 subprocess.run(command,check=True,timeout=240,env={**os.environ,'TMPDIR':str(B)})
 deps=subprocess.check_output(PREFIX+['readelf','-d',str(B/'oracle.tmp')],text=True)
 assert not any(x in deps for x in ('libsycl','libze_loader','libOpenCL','libcuda'))
 (B/'oracle.tmp').rename(B/'oracle')
 receipt=dict(passed=True,device_executed=False,command=command,binary_sha256=sha(B/'oracle'),source_sha256=sha(HERE/'oracle128.cpp'),sealed_binary_sha256=sealed['binary_sha256'],arithmetic=sealed['arithmetic'],dynamic_dependencies=deps,compiler=subprocess.check_output(PREFIX+['g++','--version'],text=True))
 temp=HERE/'build-receipt.json.tmp';temp.write_text(json.dumps(receipt,indent=2)+'\n');temp.replace(HERE/'build-receipt.json')
if __name__=='__main__':main()

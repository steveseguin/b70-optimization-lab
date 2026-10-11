"""CPU-only v2 oracle build. Independent rows use exactly two CPU threads."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];S=P.parent;OWNER=S.parent/'stage1/packet3-prep/src';B=P/'build/oracle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
B.mkdir(exist_ok=True)
base=['g++','-std=c++20','-O2','-mfma','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-fopenmp']
includes=['-I'+str(q) for q in (OWNER,S/'packet2/kernels',S/'packet2/loader',P)]
sources=[P/'oracle.cpp',P/'performance.cpp',P/'runtime_kernels.cpp',S/'packet4/owner_retire.cpp',S/'packet2/loader/gguf.cpp',OWNER/'owner.cpp']
cmd=base+includes+list(map(str,sources))+['-lcrypto','-o',str(B/'oracle')]
subprocess.run(cmd,check=True,timeout=240)
deps=subprocess.check_output(['readelf','-d',str(B/'oracle')],text=True)
assert not any(x in deps for x in ('libsycl','ze_loader','OpenCL','cuda'))
# Compiler emits the transitive project dependencies; bind all of them.
dependency=set()
for source in sources:
 raw=subprocess.check_output(base+includes+['-MM',str(source)],text=True).replace('\\\n',' ')
 for name in raw.split()[1:]:
  q=Path(name).resolve()
  if q.is_file() and q.is_relative_to(ROOT):dependency.add(q)
hashes={str(q.relative_to(ROOT)):sha(q) for q in sorted(dependency)}
identity=dict(schema='iq3.arithmetic-identity.v2',arithmetic='iq3-p17-detmath-v2',gemv_order='r234-sg32-split4-bf16 unchanged',arithmetic_sources=hashes,rope_sha256=sha(P/'rope.bf16'),device_qualified=False)
(P/'arithmetic.json').write_text(json.dumps(identity,indent=2)+'\n')
receipt=dict(passed=True,device_executed=False,command=cmd,binaries={'oracle':sha(B/'oracle')},sources=hashes,compiler=subprocess.check_output(['g++','--version'],text=True),dynamic_dependencies=deps,threads=2)
(P/'oracle-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

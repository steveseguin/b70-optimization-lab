"""Two CPU compiler exact-array gates through the128-output suite context span."""
import hashlib,json,subprocess
from pathlib import Path
from storage import admit,digest
P=Path(__file__).resolve().parent
rows=[]
for compiler,name in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','icpx')]:
 admit(100_000_000)
 binary=P/'build'/('p38-qsa-cpu-'+name)
 cmd=['nice','-n','19','ionice','-c','3',compiler,'-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY']
 if name=='icpx':cmd+=['-fdenormal-fp-math=ieee']
 for include in [P,P.parents[1]/'stage1/packet3-prep/src',P.parent/'packet2/kernels',P.parent/'packet2/loader']:cmd+=['-I',str(include)]
 cmd+=[str(P/'p38_qsa_cpu.cpp'),'-o',str(binary)]
 subprocess.run(cmd,check=True)
 r=subprocess.run(['nice','-n','19','ionice','-c','3',str(binary)],capture_output=True,text=True,check=True)
 receipt=json.loads(r.stdout);assert receipt['passed'] and receipt['device_executed'] is False
 rows.append(dict(compiler=name,binary=str(binary.relative_to(P)),binary_sha256=digest(binary),command=cmd,receipt=receipt))
assert rows[0]['receipt']==rows[1]['receipt']
sources={f.name:digest(f) for pat in ('p33*','p30*','round2*','core_v2.hpp','arithmetic.hpp') for f in P.glob(pat) if f.suffix in ('.cpp','.hpp')}
row=dict(passed=True,device_executed=False,checks=sum(r['receipt']['checks'] for r in rows),workloads_per_compiler=rows[0]['receipt']['workloads'],compilers=2,full_arrays_identical=True,rows=rows,sources_sha256=sources,context_lengths='88..218 inclusive and256')
(P/'p38-qsa-capacity-gates.json').write_text(json.dumps(row,indent=2)+'\n')
print(json.dumps(dict(passed=True,checks=row['checks'])))

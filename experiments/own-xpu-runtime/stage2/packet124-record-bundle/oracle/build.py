#!/usr/bin/env python3
"""Build one host-only oracle; frozen p17 graph with independent split32 QSA."""
import hashlib,json,os,re,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[4]
STAGE=ROOT/'experiments/own-xpu-runtime/stage2'
OLD=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-suite128'
OUT=Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 OUT.mkdir(parents=True,exist_ok=True);build=OUT/'build';build.mkdir(exist_ok=True)
 src=build/'src';src.mkdir(exist_ok=True)
 original=json.loads((OLD/'build-receipt.json').read_text())
 for n,h in original['arithmetic']['arithmetic_sources'].items():assert sha(ROOT/n)==h,n
 names=('runtime_main.cpp','performance.cpp','performance.hpp','runtime_kernels.cpp','runtime_kernels.hpp','arithmetic.hpp','core_v2.hpp','detmath.hpp','rope.hpp')
 provenance={str((OLD/'oracle128.cpp').relative_to(ROOT)):sha(OLD/'oracle128.cpp'),str((STAGE/'suite-inputs-20261012-cap128/suite-manifest.json').relative_to(ROOT)):sha(STAGE/'suite-inputs-20261012-cap128/suite-manifest.json')}
 for name in names:
  source=STAGE/'packet17-detmath'/name;text=source.read_text();provenance[str(source.relative_to(ROOT))]=sha(source)
  def include(m):
   rel=m.group(1)
   return '#include "'+(rel if rel in names or not (source.parent/rel).exists() else str((source.parent/rel).resolve()))+'"'
  text=re.sub(r'#include "([^"]+)"',include,text)
  if name=='arithmetic.hpp':text=text.replace('iq3-p17-detmath-v2','iq3-p49-split32-v1')
  if name=='core_v2.hpp':
   # detmath must be defined before the scalar attention specification.
   text=text.replace('#include "detmath.hpp"','#include "detmath.hpp"\n#include "'+str(P/'split32_scalar.hpp')+'"')
   start=text.index('        float m = *std::max_element(scores.begin(), scores.end());',text.index('} else if (op == Op::qsa_attention)'))
   end=text.index('\n      }\n      out(0) = y;',start)
   text=text[:start]+'''        auto values=p49oracle::split32(int(ids.size()),g.ad,
            [&](int j){return scores[j];},
            [&](int j,int d){return in(3)[(int(ids[j])*g.kvh+kh)*g.ad+d];});
        for(int k=0;k<g.ad;++k)
          y[h*g.ad+k]=bf(bf(values[k])*sigmoid(in(1)[h*g.ad+k]));'''+text[end:]
  (src/name).write_text(text)
 oracle=(OLD/'oracle128.cpp').read_text().replace('a.context=256;','a.context=4096;')
 oracle=oracle.replace('          int layer=std::stoi(l.label.substr(4));','          int layer=std::stoi(l.label.substr(4));\n          if(layer==47 && getenv("P49_CAPTURE")) {\n            fs::create_directories(out/"capture-streams");\n            auto raw=engine->readback(0,engine->buffers[0].at("streams").id,4*p.g.h*2);\n            std::ofstream stream(out/"capture-streams"/("streams-"+std::to_string(position)+".bf16"),std::ios::binary);\n            stream.write(reinterpret_cast<char*>(raw.data()),raw.size());require(bool(stream),"capture stream write");\n          }')
 (src/'oracle.cpp').write_text(oracle)
 owner=ROOT/'experiments/own-xpu-runtime/stage1/packet3-prep/src'
 cmd=['g++','-std=c++20','-O2','-mfma','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-fopenmp','-I'+str(owner),'-I'+str(STAGE/'packet2/kernels'),'-I'+str(STAGE/'packet2/loader'),'-I'+str(src),str(src/'oracle.cpp'),str(src/'performance.cpp'),str(src/'runtime_kernels.cpp'),str(STAGE/'packet4/owner_retire.cpp'),str(STAGE/'packet2/loader/gguf.cpp'),str(owner/'owner.cpp'),'-lcrypto','-o',str(build/'oracle')]
 with (OUT/'build.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0,'see oracle/build.log'
 deps=subprocess.check_output(['readelf','-d',str(build/'oracle')],text=True)
 assert not any(s in deps.lower() for s in ('libsycl','ze_loader','opencl','libcuda'))
 sources={str(f.relative_to(ROOT)):sha(f) for f in P.iterdir() if f.suffix in ('.py','.hpp','.cpp')}
 identity=dict(schema='iq3.arithmetic-identity.v49',arithmetic='iq3-p49-split32-v1',qsa='iq3-p47-qsa-split32-v1',arithmetic_sources=original['arithmetic']['arithmetic_sources'],overlay_sources=sources,inherited_identity='iq3-p17-detmath-v2',scope='Frozen p17 full CPU graph except independent fixed32 QSA; BF16 state/KV; unchanged packed GEMV order',device_qualified=False)
 (P/'arithmetic.json').write_text(json.dumps(identity,indent=2)+'\n')
 receipt=dict(passed=True,device_executed=False,command=cmd,binary_sha256=sha(build/'oracle'),sources=sources,frozen_sources=provenance,generated_sources={f.name:sha(f) for f in src.iterdir()},arithmetic_sha256=sha(P/'arithmetic.json'),dependencies=deps,compiler=subprocess.check_output(['g++','--version'],text=True))
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(passed=True,binary_sha256=receipt['binary_sha256'])))
if __name__=='__main__':main()

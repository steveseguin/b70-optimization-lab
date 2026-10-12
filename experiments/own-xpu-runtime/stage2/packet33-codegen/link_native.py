#!/usr/bin/env python3
"""Link prepared native timing/K0; CPU-only, never execute either artifact."""
import json,shlex,subprocess,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';OLD=P.parent/'packet29-merged/build/device'
def main():
 a=json.loads((P/'link-command.json').read_text());a=[x for x in a if not x.startswith('-fsycl-dump-device-code=')]
 a=[x for x in a if not any(x.endswith(v) for v in ('k2-fixtures-entry.cpp.o','/gemv_timing.cpp.o','/adapter_fixture.cpp.o'))]
 a[a.index('-o')+1]=str(B/'p33-timing')
 objs=[str(B/(n+'.o')) for n in ('p33_submit','p33_gemv_timing','p33_round2_submit','timing_adapter','timing_main')]
 dumps=B/'candidate-spv';dumps.mkdir(exist_ok=True)
 a+=objs+['-fsycl-dump-device-code='+str(dumps)]
 logs=[]
 with (B/'link-native.log').open('w') as f:r=subprocess.run(a,stdout=f,stderr=subprocess.STDOUT)
 logs.append(dict(argv=a,returncode=r.returncode))
 if r.returncode:raise RuntimeError('link-native.log')
 # The unchanged K0 source builds all linked kernel images without submitting them.
 k0=OLD/'CMakeFiles/jit-smoke.dir/build/checked/experiments/own-xpu-runtime/stage2/packet29-merged/jit_smoke.cpp.o'
 if not k0.exists():raise RuntimeError('K0 object missing')
 a=[x for x in a if x!=str(B/'timing_main.o') and not x.startswith('-fsycl-dump-device-code=')];a[a.index('-o')+1]=str(B/'p33-k0');a.append(str(k0))
 with (B/'link-k0.log').open('w') as f:r=subprocess.run(a,stdout=f,stderr=subprocess.STDOUT)
 logs.append(dict(argv=a,returncode=r.returncode))
 if r.returncode:raise RuntimeError('link-k0.log')
 (P/'native-links.json').write_text(json.dumps(logs,indent=2)+'\n')
 print('linked timing and K0; not executed')
if __name__=='__main__':main()

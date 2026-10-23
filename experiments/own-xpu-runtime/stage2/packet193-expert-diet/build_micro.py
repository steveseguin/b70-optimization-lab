"""Build the micro (GNU host twin, Intel host twin, device) against native-pinned only; 0 warnings.

Record identity flags: packet192's build.json flags = packet189 v5's device compile flags (-fno-fast-math
-ffp-contract=off -O2 -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -fsycl); the GNU host
flags are its gnu-host flags (-DOWN_RT_HOST_ONLY -march=native -fopenmp). One compiler at a time under the shared
turn; units polled before each compile. The dependency closure must lie inside this packet (plus toolchain).
"""
import json,resource,shlex,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,NATIVE,BUILD,EV,limits,sha,rel,units_idle,build_bytes
sys.path.insert(0,str(P.parents[1]/'ops'));from compile_turn import turn
ICPX='/opt/intel/oneapi/compiler/2026.0/bin/icpx';GXX='/usr/bin/g++'
INC=['-I'+str(NATIVE/'checked/experiments/own-xpu-runtime/stage2/packet189-twocard-k3x'),'-I'+str(NATIVE/'root'),'-I'+str(P)]
COMMON=['-std=gnu++20','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-O2']
MODES={'gnu-host':(GXX,['-DOWN_RT_HOST_ONLY','-march=native','-fopenmp']),
       'intel-host':(ICPX,['-DOWN_RT_HOST_ONLY','-march=native','-fiopenmp']),
       'device':(ICPX,['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl','-Werror=deprecated-this-capture'])}
SOURCES=('micro.cpp','p193_diet.hpp')
def main():
 limits();modes=[m for m in MODES if not sys.argv[1:] or m in sys.argv[1:]];BUILD.mkdir(exist_ok=True);EV.mkdir(exist_ok=True)
 receipt=EV/'build.json';records={r['mode']:r for r in json.loads(receipt.read_text())['records']} if receipt.exists() else {}
 sources={rel(p):sha(p) for p in (*(P/n for n in SOURCES),*sorted(NATIVE.rglob('*.hpp')))}
 for mode in modes:
  compiler,extra=MODES[mode];out=BUILD/('micro-'+mode);dep=BUILD/('micro-'+mode+'.d');log=BUILD/('micro-'+mode+'.log')
  cmd=[compiler,*COMMON,*extra,*INC,'-MMD','-MF',str(dep),str(P/'micro.cpp'),'-o',str(out)]
  units=units_idle();t=time.monotonic()
  with turn(),log.open('w') as f:subprocess.run(['nice','-n','19',*cmd],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
  text=log.read_text();warnings=[l for l in text.splitlines() if 'warning:' in l];assert not warnings,mode+' warnings: '+str(warnings[:3])
  deps=[Path(x).resolve() for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]) if x]
  inside=[d for d in deps if d.is_relative_to(ROOT)];assert all(d.is_relative_to(P) for d in inside),'closure outside packet193: '+str([str(d) for d in inside if not d.is_relative_to(P)][:3])
  records[mode]=dict(mode=mode,command=cmd,path=rel(out),sha256=sha(out),seconds=round(time.monotonic()-t,1),warning_lines=len(warnings),log=rel(log),log_sha256=sha(log),
   closure={rel(d):sha(d) for d in inside},closure_count=len(inside),toolchain_headers=len(deps)-len(inside),units=units)
  print(mode,'built',records[mode]['sha256'][:16],records[mode]['seconds'],'s',flush=True)
 json.dump(dict(passed=True,device_executed=False,warning_lines=sum(r['warning_lines'] for r in records.values()),sources=sources,records=list(records.values()),
  build_bytes=build_bytes(),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),receipt.open('w'),indent=1);receipt.write_text(receipt.read_text()+'\n')
if __name__=='__main__':main()

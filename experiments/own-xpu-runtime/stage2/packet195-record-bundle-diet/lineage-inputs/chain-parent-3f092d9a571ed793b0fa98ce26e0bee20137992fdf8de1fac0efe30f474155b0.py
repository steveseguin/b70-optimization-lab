#!/usr/bin/env python3
"""Six host compiler arms through actual fused owner submission; never SYCL."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from storage import admit,digest,discard
from math_gate import closure
from capacity_fixture_gate import host
P=Path(__file__).resolve().parent
E=P/'evidence/route-gather-fix'
SOURCES=('fusion_matrix.cpp','adapter.cpp','route42_submit.cpp','round2_submit.cpp',
 'specialised_submit.cpp','p42_submit.cpp','p30_submit.cpp','p33r2.cpp',
 'p39_fixture.cpp','p39_submit.cpp','p28/submit.cpp','p33_submit.cpp',
 'expert_down.cpp','small_gemv_fixture.cpp','small_gemv.cpp','performance.cpp','owner.cpp','owner_retire.cpp')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--label',choices=('before','after'),required=True);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 E.mkdir(parents=True,exist_ok=True);tmp=P/'build/fusion-matrix';tmp.mkdir(exist_ok=True)
 (tmp/'device_validation.hpp').write_text('#pragma once\nnamespace fixture_validation {inline bool only=false,inject=false;}\n')
 (tmp/'owner.hpp').write_text('#include "'+str(P/'owner_api.hpp')+'"\n')
 sources=set(closure())|{P/n for n in SOURCES}|{Path(__file__).resolve()}
 pins={str(f.relative_to(P.parents[3])):digest(f) for f in sorted(sources)}
 rows=[]
 for compiler,label in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','icpx')]:
  for opt,flags in [('O0',['-O0']),('O2',['-O2']),('O3-native',['-O3','-march=native'])]:
   admit(200_000_000);binary=tmp/(label+'-'+opt)
   cmd=[compiler,'-std=c++20','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(tmp),'-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),*flags,*[str(P/n) for n in SOURCES],'-lcrypto','-o',str(binary)]
   print('COMPILE',a.label,label,opt,flush=True)
   log=E/(a.label+'-'+label+'-'+opt+'.compile.log')
   with log.open('w') as stream:r=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT)
   if r.returncode:raise RuntimeError(str(log))
   host(binary);out=tmp/(a.label+'-'+label+'-'+opt);out.mkdir(exist_ok=True)
   r=subprocess.run([str(binary),str(out)],text=True,capture_output=True)
   log=E/(a.label+'-'+label+'-'+opt+'.log');log.write_text(r.stdout+r.stderr)
   result=json.loads(r.stdout)
   assert all(digest(P.parents[3]/n)==h for n,h in pins.items()),'source changed during matrix'
   archive=discard(out)
   rows.append(dict(compiler=label,optimization=opt,command=cmd,binary_sha256=digest(binary),exit_code=r.returncode,result=result,log=str(log.relative_to(P)),log_sha256=digest(log),archive=archive))
   print(a.label,label,opt,result,flush=True)
 gate=dict(schema='packet45.fusion-matrix.v1',passed=all(r['exit_code']==0 and r['result']['passed'] for r in rows),device_executed=False,compiled_sources_sha256=pins,rows=rows,checks=sum(r['result']['checks'] for r in rows))
 (E/(a.label+'.json')).write_text(json.dumps(gate,indent=2)+'\n')
 if a.label=='after':
  (P/'fusion-matrix-gates.json').write_text(json.dumps(gate,indent=2)+'\n')
  if not gate['passed']:raise SystemExit(1)
if __name__=='__main__':main()

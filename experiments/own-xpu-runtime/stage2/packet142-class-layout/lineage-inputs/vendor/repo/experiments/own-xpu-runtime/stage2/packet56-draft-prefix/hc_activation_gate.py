#!/usr/bin/env python3
"""Run the actual K1a HC inputs and NaN payload contract across host codegen."""
import argparse,json,os,subprocess,sys
from pathlib import Path
from storage import admit,digest
from math_gate import closure
P=Path(__file__).resolve().parent
PREFIX=['nice','-n','19','ionice','-c','3']
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--label',choices=('before','after'),required=True);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 root=P/'evidence/hc-activation-fix';root.mkdir(exist_ok=True,parents=True)
 tmp=P/'build/hc-activation-gate';admit(20_000_000);tmp.mkdir(exist_ok=True)
 (tmp/'device_validation.hpp').write_text('#pragma once\nnamespace fixture_validation {inline bool only=false,inject=false;}\n')
 (tmp/'owner.hpp').write_text('#include "'+str(P/'owner_api.hpp')+'"\n')
 sources=set(closure())|{P/'hc_activation_gate.cpp',Path(__file__).resolve()}
 source_sha256={str(f.relative_to(P.parents[3])):digest(f) for f in sorted(sources)}
 rows=[]
 for compiler,label in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','icpx')]:
  for optimization,flags in [('O0',['-O0']),('O2',['-O2']),('O3-native',['-O3','-march=native'])]:
   admit(20_000_000);binary=tmp/(label+'-'+optimization)
   cmd=PREFIX+[compiler,'-std=c++20','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DOWN_RT_HOST_ONLY','-I'+str(tmp),'-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),*flags,str(P/'hc_activation_gate.cpp'),'-o',str(binary)]
   r=subprocess.run(cmd,text=True,capture_output=True)
   if r.returncode:raise RuntimeError(r.stderr)
   from capacity_fixture_gate import host
   host(binary)
   r=subprocess.run(PREFIX+[str(binary)],text=True,capture_output=True)
   log=root/(a.label+'-'+label+'-'+optimization+'.log');log.write_text(r.stdout+r.stderr)
   assert all(digest(P.parents[3]/n)==h for n,h in source_sha256.items()),'source changed during gate'
   result=json.loads(r.stdout)
   rows.append(dict(compiler=label,optimization=optimization,command=cmd,binary_sha256=digest(binary),exit_code=r.returncode,result=result,log=str(log.relative_to(P)),log_sha256=digest(log)))
   print(a.label,label,optimization,result,flush=True)
 result=dict(schema='packet45.hc-activation-cpu.v1',passed=all(r['exit_code']==0 and r['result']['passed'] for r in rows),device_executed=False,compiled_sources_sha256=source_sha256,rows=rows,checks=sum(r['result']['checks'] for r in rows))
 (root/(a.label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 if a.label=='after':
  (P/'hc-activation-gates.json').write_text(json.dumps(result,indent=2)+'\n')
  if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()

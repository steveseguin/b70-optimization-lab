#!/usr/bin/env python3
"""No platform nonlinear-math calls in the local device include closure."""
import hashlib,json,re,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
 roots=[P/'timing.cpp',P/'k0.cpp'];pending=roots[:];seen=set()
 includes=[P,P.parent/'packet29-merged',P.parent/'packet2/kernels',P.parent/'packet2/loader',P.parents[1]/'stage1/packet3-prep/src']
 while pending:
  f=pending.pop().resolve()
  if f in seen:continue
  seen.add(f)
  for name in re.findall(r'^\s*#include\s*"([^"\n]+)"',f.read_text(),re.M):
   match=next((d/name for d in [f.parent,*includes] if (d/name).is_file()),None)
   if match is None:raise RuntimeError(str(f)+': unresolved '+name)
   pending.append(match)
 pattern=r'(std::|sycl::(native::|half_precision::)?|__builtin_)(exp|log|pow|sin|cos)(2|10|1p|m1)?f?\s*\('
 r=subprocess.run(['rg','-n',pattern,*map(str,sorted(seen))],capture_output=True,text=True)
 out=dict(passed=r.returncode==1,device_executed=False,pattern=pattern,findings=r.stdout+r.stderr,sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(seen)})
 (P/'math-gate.json').write_text(json.dumps(out,indent=2)+'\n')
 if not out['passed']:raise RuntimeError(out['findings'])
 print('math grep PASS',len(seen),'files')
if __name__=='__main__':main()

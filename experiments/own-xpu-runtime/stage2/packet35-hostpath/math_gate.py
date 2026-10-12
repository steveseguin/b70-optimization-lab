"""Build-time grep over the actual device translation units' local include closure."""
import json, re, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OWNER=HERE.parents[1]/'stage1/packet3-prep/src'
SOURCES=['p28/submit.cpp','expert_down.cpp','round2_submit.cpp','small_gemv.cpp','small_gemv_fixture.cpp','p25_bridge.cpp','gemv_timing.cpp','adapter_fixture.cpp','nongemv_fixture.cpp','k2_fixture.cpp','jit_smoke.cpp','specialised_submit.cpp','main.cpp','performance.cpp','adapter.cpp','runtime_kernels.cpp','owner.cpp','native.cpp',
 'owner_retire.cpp','../packet2/loader/gguf.cpp','../packet2/kernels/device.cpp',
 '../packet6-kopt/kernels.cpp','../packet7-kopt2/kernels.cpp','../packet8-kopt3/kernels.cpp',
 '../packet9-kopt4/kernels.cpp','../packet10-kopt5/kernels.cpp']
def closure():
 pending=[HERE/x for x in SOURCES]+[OWNER/'sycl_device.cpp']+[HERE/x for x in ('prepared_invalidation_test.cpp','authority_test.cpp','../packet4/owner_test.cpp','chain_test.cpp','queue_test.cpp','lifetime_test.cpp')];seen=set()
 while pending:
  path=pending.pop().resolve()
  if path in seen:continue
  seen.add(path)
  for name in re.findall(r'^\s*#include\s*"([^"\n]+)"',path.read_text(),re.M):
   options=[path.parent/name,HERE/name,OWNER/name,HERE.parent/'packet2/kernels'/name,HERE.parent/'packet2/loader'/name]
   match=next((p for p in options if p.is_file()),None)
   if match is None:raise RuntimeError(f'unresolved project include {name} in {path}')
   pending.append(match)
 return sorted(seen)
def check():
 paths=closure()
 # Restrict forbidden names to platform/builtin spellings. detmath::exp/log
 # and rope_constants::sin/cos are the intended local definitions.
 pattern=r'(std::|sycl::(native::|half_precision::)?|__builtin_)(exp|log|pow|sin|cos)(2|10|1p|m1)?f?\s*\('
 result=subprocess.run(['rg','-n',pattern,*map(str,paths)],capture_output=True,text=True)
 assert result.returncode==1, 'platform math in device include closure: '+result.stdout+result.stderr
 return dict(passed=True,grep_argv=['rg','-n',pattern],translation_units=len(SOURCES)+1,files=[str(p.relative_to(ROOT)) for p in paths])
if __name__=='__main__':print(json.dumps(check(),indent=2))

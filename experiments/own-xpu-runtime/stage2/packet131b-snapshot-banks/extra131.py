"""Production recurrence and reset regressions under both compilers, CPU only."""
import json,subprocess
from build131 import P,ROOT,B,sha,save,cpu_main,limits,run
def main():
 try:
  recurrence=json.loads((P/'evidence/recurrence131.json').read_text());reset=json.loads((P/'evidence/reset-regression.json').read_text())
  assert recurrence['passed'] and reset['passed'] and len(recurrence['runs'])==len(reset['runs'])==4
  for report in (recurrence,reset):
   for path,h in report['sources'].items():assert sha(ROOT/path)==h
  assert reset['gate_sha256']==sha(P/'reset_regression.py')
  for row in recurrence['runs']:assert sha(B/('recurrence131-'+row['compiler']))==row['binary_sha256']
  for row in reset['runs']:assert sha(B/('reset-'+row['compiler']))==row['binary_sha256']
 except (OSError,KeyError,AssertionError):pass
 else:print('Unchanged production recurrence/reset receipts and binaries verified');return
 commands=[];runs=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('recurrence131-'+compiler)
  cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'recurrence131.cpp'),'-o',str(binary),'-lcrypto']
  commands.append(run(cmd,'recurrence-'+compiler))
  for repeat in (1,2):
   cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=180)
   runs.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),**json.loads(cp.stdout)))
  print(compiler,'production recurrence all six banks PASS',flush=True)
 save(P/'evidence/recurrence131-localization.json',dict(device_executed=False,runs=runs,commands=commands,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'recurrence131.cpp',P/'extra131.py']}))
 for compiler in ('GNU','Intel'):
  assert len({r['canonical_sha256'] for r in runs if r['compiler']==compiler})==1,'same-compiler repeat differs'
 a,b=runs[0]['case_hashes'],runs[2]['case_hashes'];differences=[]
 for x,y in zip(a,b):
  assert {k:v for k,v in x.items() if k not in ('sha256','nan_diagnostic_sha256')}=={k:v for k,v in y.items() if k not in ('sha256','nan_diagnostic_sha256')}
  if x['sha256']!=y['sha256']:
   assert x['scenario']==6 and x['nan_count']>0 and x['nan_diagnostic_sha256']==y['nan_diagnostic_sha256'],'non-NaN compiler reference mismatch'
   differences.append(dict(scenario=x['scenario'],packed=x['packed'],active=x['active'],spare=x['spare'],GNU=x['sha256'],Intel=y['sha256'],nan_diagnostic_sha256=x['nan_diagnostic_sha256']))
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'extra131.py',P/'recurrence131.cpp',P/'p82_cpu.cpp',P/'p82_recurrence.hpp',P/'p82b_recurrence.hpp']}
 save(P/'evidence/recurrence131.json',dict(passed=True,device_executed=False,same_compiler_raw_bank_equality=True,raw_repeat_equality=True,cross_compiler_reference_equal=not differences,cross_compiler_reference_differences=differences,scope='All bank outputs/state compare RAW against unchanged same-compiler recurrence. Cross-compiler control differences are confined to NaN payloads; diagnostic normalization never qualifies candidate/reference equality or alters runtime bytes.',runs=runs,commands=commands,sources=sources))
 import reset_regression
 reset_regression.main();limits()
if __name__=='__main__':cpu_main();main()

import os,subprocess
from pathlib import Path
from build import P,B,PY,run,save,read
for tag in ('host','device'):run(['cmake','--build',B/tag,'-j2'],'build-final-'+tag+'.log')
for timing in ('token','drain','launch'):
 os.environ['PACKET23_TIMING']=timing
 for mode in ('core','parallel'):
  run([PY,'-B',P/'test.py','--binary',B/'host/own-rt-iq3','--scratch',B/f'final-mini-{timing}-{mode}','--input',B/'input','--receipt',P/f'cpu-mini-{timing}-{mode}.json','--nongemv',mode],f'mini-{timing}-{mode}.log')
os.environ.pop('PACKET23_TIMING',None)
run([PY,'-B',P/'stream_gate.py'],'streaming.log')
run([PY,'-B',P/'guard_tests.py'],'guard-tests.log')
run([PY,'-B',P/'test_window.py'],'window-tests.log')
for tag,src in [('before',P.with_name('packet21-fused')),('after',P)]:
 run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-I'+str(src),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),P/'submission_bench.cpp',src/'owner.cpp',src/'owner_retire.cpp','-o',B/('bench-'+tag)],'build-bench-'+tag+'.log')
 run([B/('bench-'+tag)],'bench-'+tag+'.json')
save('submission-benchmark.json',dict(before=read(P/'bench-before.json'),after=read(P/'bench-after.json'),device_executed=False))
run([PY,'-B',P/'test_mismatch.py'],'mismatch-tests.log')
run([PY,'-B',P/'seal.py'],'seal.log')
print('FINAL GATES PASS',flush=True)

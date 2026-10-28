#!/usr/bin/env python3
"""Small isolated actual-loader fixture; no real model reads or device work."""
import hashlib,json,os,pathlib,subprocess,sys,time
here=pathlib.Path(__file__).resolve().parent
src=here.parents[2]/'engine/src'
fixture=here.parent/'lookup-view-candidate'
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert set(os.sched_getaffinity(0))<=set(range(8,16))
out=pathlib.Path(sys.argv[1]);out.mkdir(exist_ok=False)
command=['g++','-std=c++20','-O1','-g0','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections','-I',str(src),'-I',str(fixture),str(here/'test_sparse.cpp'),str(src/'stage2/packet2/loader/gguf.cpp'),'-Wl,--gc-sections','-o',str(out/'fixture')]
inputs=[here/'sparse_rows.hpp',here/'test_sparse.cpp',here/'run_cpu.py',fixture/'test_lookup_view.cpp',fixture/'weights_methods.inc',src/'stage2/packet2/loader/gguf.cpp',src/'stage2/packet2/loader/gguf.hpp',src/'gsq-rco-iq3s/integration/build/private/additive/device_formats.hpp']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r={'schema':'ownrt.sparse-lookup-cpu-fixture.v1','compile_argv':command,'sources':{str(p):sha(p) for p in inputs},'model_payload_reads':False,'device_calls':0,'nice':os.getpriority(os.PRIO_PROCESS,0),'affinity':sorted(os.sched_getaffinity(0))}
for label,cmd in [('compile',command),('run',[str(out/'fixture'),str(out/'synthetic')])]:
 start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True);r[label+'_rc']=p.returncode;r[label+'_seconds']=time.monotonic()-start
 (out/(label+'.stdout')).write_text(p.stdout);(out/(label+'.stderr')).write_text(p.stderr)
 if p.returncode:break
r['passed']=r.get('run_rc')==0
if r['passed']:r['binary_sha256']=sha(out/'fixture')
(out/'receipt.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'passed':r['passed'],'receipt':str(out/'receipt.json')}))
sys.exit(0 if r['passed'] else 1)

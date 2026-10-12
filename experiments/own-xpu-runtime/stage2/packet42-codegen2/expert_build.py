"""CPU-only expert compile, gates and offline disassembly. Never execute device code."""
import hashlib,json,os,resource,shlex,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/expert';S=P.parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
B.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,label):
 if __import__('shutil').disk_usage('/').free<8*1024**3:raise RuntimeError('STOP: less than 8 GiB root space')
 r=subprocess.run(cmd,capture_output=True,text=True);(B/(label+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(label+': '+r.stderr[-3000:])
 return r
if '--cpu' in sys.argv:
 rows=[]
 for label,cc in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=B/('expert-cpu-'+label);cmd=[cc,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(S/'packet29-merged'),'-I'+str(S.parent/'stage1/packet3-prep/src'),'-I'+str(S/'packet2/kernels'),'-I'+str(S/'packet2/loader'),str(P/'expert_cpu.cpp'),'-o',str(binary)]
  run(cmd,label+'-compile')
  for repeat in range(2):
   r=run([str(binary)],label+'-'+str(repeat));rows.append(dict(compiler=label,repeat=repeat,command=cmd,binary_sha256=sha(binary),receipt=json.loads(r.stdout)))
 report=dict(device_executed=False,passed=all(r['receipt']['passed'] for r in rows),rows=rows,fresh_repeat_identical=rows[0]['receipt']==rows[1]['receipt'] and rows[2]['receipt']==rows[3]['receipt'])
 report['finite_cross_compiler_identical']=all(rows[0]['receipt']['candidates'][k]['hash']==rows[2]['receipt']['candidates'][k]['hash'] for k in rows[0]['receipt']['candidates']);report['passed']=report['passed'] and report['fresh_repeat_identical'] and report['finite_cross_compiler_identical'];report['nonfinite_policy']='packet29 finite production qualification; nonfinite raw reference differences retained, never accepted as equal';(P/'expert-gates.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
else:
 entries=json.loads((S/'packet29-merged/build/device/compile_commands.json').read_text());cmd=shlex.split(next(r['command'] for r in entries if r['file'].endswith('/gemv_timing.cpp')));cmd=cmd[:cmd.index('-o')]
 cmd+=['-fsycl-dump-device-code='+str(B),'-c',str(P/'expert_submit.cpp'),'-o',str(B/'expert_submit.o')]
 run(cmd,'device-compile');(P/'expert-build.json').write_text(json.dumps(dict(command=cmd,device_executed=False,object_sha256=sha(B/'expert_submit.o')),indent=2)+'\n');print('offline object compiled')

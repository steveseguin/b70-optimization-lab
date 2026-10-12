import hashlib,json,os,resource,subprocess,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/route42';R=P.parent/'packet29-merged'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
I=['-I'+str(x) for x in [P,R,R/'../../stage1/packet3-prep/src',R/'../packet2/kernels',R/'../packet2/loader']];F=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off'];IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,name):
 if shutil.disk_usage('/').free<8_000_000_000:raise RuntimeError('STOP root below8GB')
 r=subprocess.run(cmd,capture_output=True,text=True);(B/(name+'.log')).write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(name+': '+r.stderr[-3000:])
 return r
if '--cpu' in sys.argv:
 rows=[]
 for tag,cc in [('gcc','/usr/bin/g++'),('icpx',IC)]:
  binary=B/('route42-cpu-'+tag);cmd=[cc,*F,*I,'-DOWN_RT_HOST_ONLY',str(P/'route42_cpu.cpp'),'-o',str(binary)];run(cmd,tag+'-compile')
  for repeat in range(2):
   r=run([str(binary)],tag+str(repeat));rows.append(dict(compiler=tag,repeat=repeat,binary_sha256=sha(binary),receipt=json.loads(r.stdout),command=cmd))
 passed=all(r['receipt']['passed'] for r in rows) and all(r['receipt']==rows[0]['receipt'] for r in rows)
 (P/'route42-gates.json').write_text(json.dumps(dict(device_executed=False,passed=passed,rows=rows),indent=2)+'\n');print('CPU gates',passed)
 if not passed:raise SystemExit(1)
else:
 F+=['-Werror=return-type','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl'];commands=[];objects=[]
 for name in ['route42_submit','route42_timing','route42_native']:
  obj=B/(name+'.o');cmd=[IC,*F,*I,'-c',str(P/(name+'.cpp')),'-o',str(obj)];run(cmd,name);commands.append(cmd);objects.append(str(obj))
 old=json.loads((P.parent/'packet33-codegen/link-command.json').read_text());old=[x for x in old if x.endswith('.o') and 'k2-fixtures-entry' not in x]
 (B/'spv').mkdir(exist_ok=True);binary=B/'p42-route';cmd=[IC,*F,*objects,*old,'-o',str(binary),'-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu','/usr/lib/x86_64-linux-gnu/libcrypto.so','-lze_loader','-fsycl-dump-device-code='+str(B/'spv')];run(cmd,'link');commands.append(cmd)
 (P/'route42-build.json').write_text(json.dumps(dict(device_executed=False,commands=commands,binary=str(binary.relative_to(P)),binary_sha256=sha(binary),source_sha256={x.name:sha(x) for x in P.glob('route42*') if x.is_file() and x.suffix in ('.hpp','.cpp','.py')},external_objects={x:sha(x) for x in old}),indent=2)+'\n');print(sha(binary))

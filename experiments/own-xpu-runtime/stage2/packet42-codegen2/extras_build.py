"""CPU-only builds and host fixture gates; device executables are never run."""
import hashlib,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/extras';B.mkdir(parents=True,exist_ok=True)
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
if shutil.disk_usage('/').free<8*1024**3:raise SystemExit('STOP: root filesystem below 8 GiB free')
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));os.environ['TMPDIR']=str(B)
old=P.parent/'packet29-merged';owner=P.parents[1]/'stage1/packet3-prep/src';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
flags=['-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-Werror=return-type','-I'+str(owner),'-I'+str(old),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader')]
rows=[];gates=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command(cmd,log):
 start=time.monotonic()
 with (B/log).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 rows.append(dict(argv=cmd,returncode=r.returncode,seconds=time.monotonic()-start))
 (P/'extras-build-receipt.json').write_text(json.dumps(dict(device_executed=False,commands=rows),indent=2)+'\n')
 if r.returncode:raise SystemExit(str(B/log))
for compiler,name in ([] if os.environ.get('P42_NATIVE_ONLY') else [('g++','gcc'),(IC,'icpx')]):
 binary=B/('extras-cpu-'+name);command([compiler,*flags,*(['-fp-model=strict'] if name=='icpx' else []),str(P/'extras_cpu.cpp'),'-o',str(binary)],name+'-build.log')
 for repeat in range(2):
  cmd=[str(binary)];r=subprocess.run(cmd,text=True,capture_output=True)
  if r.returncode:raise SystemExit(r.stderr)
  gate=json.loads(r.stdout);gate.update(compiler=name,repeat=repeat,binary_sha256=sha(binary));gates.append(gate)
  print(name,repeat,gate['fixture_checks'],flush=True)
if gates:(P/'extras-cpu-gates.json').write_text(json.dumps(dict(passed=all(g['passed'] for g in gates),device_executed=False,runs=gates),indent=2)+'\n')
flags+=['-fsycl','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
(B/'spv').mkdir(exist_ok=True)
command([IC,*flags,'-c',str(P/'extras_timing.cpp'),'-o',str(B/'extras.o'),'-fsycl-dump-device-code='+str(B/'spv')],'extras-native.log')
cmd=json.loads((P.parent/'packet33-codegen/link-command.json').read_text());cmd=[x for x in cmd if not x.startswith('-fsycl-dump-device-code=') and not any(x.endswith(z) for z in ('k2-fixtures-entry.cpp.o','/gemv_timing.cpp.o','/adapter_fixture.cpp.o','/entry-main.cpp.o','/entry-nongemv_fixture.cpp.o','/entry-k2_fixture.cpp.o'))];cmd[cmd.index('-o')+1]=str(B/'p42-extras');cmd += [str(B/'extras.o'),'-fsycl-dump-device-code='+str(B/'spv')];command(cmd,'link.log')
receipt=dict(device_executed=False,commands=rows,binary_sha256=sha(B/'p42-extras'),peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,source_hashes={f.name:sha(f) for f in P.glob('extras*') if f.suffix in ('.hpp','.cpp')})
(P/'extras-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['binary_sha256'])

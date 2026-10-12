import hashlib,json,os,shlex,subprocess,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/parallel';OLD=P.parent/'packet29-merged'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 if shutil.disk_usage('/').free<8*1024**3:raise RuntimeError('STOP: root below 8GB free')
 resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));B.mkdir(exist_ok=True,parents=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 rows=[];flags=['-std=gnu++20','-O2','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl'];incs=['-I'+str(x.resolve()) for x in (P,OLD,OLD/'../../stage1/packet3-prep/src',OLD/'../packet2/kernels',OLD/'../packet2/loader')]
 for name in (() if os.environ.get('P42_LINK_ONLY') else ('parallel_native',) if os.environ.get('P42_NATIVE_ONLY') else ('parallel_submit','parallel_native')):
  cmd=['/opt/intel/oneapi/compiler/2026.0/bin/icpx',*flags,*incs,'-c',str(P/(name+'.cpp')),'-o',str(B/(name+'.o'))]
  with (B/(name+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
  rows.append(dict(command=cmd,returncode=r.returncode));print(name,r.returncode,flush=True)
  if r.returncode:raise RuntimeError((B/(name+'.log')).read_text()[-5000:])
 cmd=json.loads((P.parent/'packet33-codegen/link-command.json').read_text());cmd=[x for x in cmd if not x.startswith('-fsycl-dump-device-code=') and not any(x.endswith(z) for z in ('k2-fixtures-entry.cpp.o','/gemv_timing.cpp.o','/adapter_fixture.cpp.o','/entry-main.cpp.o','/entry-nongemv_fixture.cpp.o','/entry-k2_fixture.cpp.o'))];cmd[cmd.index('-o')+1]=str(B/'parallel-native');cmd += [str(B/'parallel_submit.o'),str(B/'parallel_native.o'),'-fsycl-dump-device-code='+str(B/'spv')];(B/'spv').mkdir(exist_ok=True)
 with (B/'link.log').open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 rows.append(dict(command=cmd,returncode=r.returncode));print('link',r.returncode,flush=True)
 if r.returncode:raise RuntimeError((B/'link.log').read_text()[-5000:])
 out=dict(device_executed=False,commands=rows,binary=str(B/'parallel-native'),sha256=hashlib.sha256((B/'parallel-native').read_bytes()).hexdigest());(P/'parallel-build.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()

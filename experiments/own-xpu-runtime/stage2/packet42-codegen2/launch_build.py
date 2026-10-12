"""Offline compile only. Never invoke the resulting native program."""
import hashlib,json,os,shutil,subprocess,time,resource
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/'build/launch'; B.mkdir(parents=True,exist_ok=True)
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
if shutil.disk_usage('/').free<8*1024**3:raise SystemExit('STOP: root filesystem below 8 GiB free')
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
os.environ['TMPDIR']=str(B)
IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
owner=P.parents[1]/'stage1/packet3-prep/src'; old=P.parent/'packet29-merged'
flags=['-std=c++20','-O2','-fsycl','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-Werror=return-type','-I'+str(owner),'-I'+str(old)]
rows=[]
for name,src in [('owner',old/'owner.cpp'),('retire',old/'owner_retire.cpp'),('sycl_device',owner/'sycl_device.cpp'),('floor',P/'launch_floor.cpp')]:
 out=B/(name+'.o');cmd=[IC,*flags,'-c',str(src),'-o',str(out)]
 if name=='floor':
  (B/'spv').mkdir(exist_ok=True);cmd+=['-fsycl-dump-device-code='+str(B/'spv')]
 start=time.monotonic()
 with (B/(name+'.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 rows.append(dict(argv=cmd,returncode=r.returncode,seconds=time.monotonic()-start,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
 (P/'launch-build-receipt.json').write_text(json.dumps(dict(device_executed=False,commands=rows),indent=2)+'\n')
 if r.returncode:raise SystemExit(str(B/(name+'.log')))
cmd=[IC,*flags,*[str(B/(n+'.o')) for n in ['owner','retire','sycl_device','floor']],'-fsycl-dump-device-code='+str(B/'spv'),'-lze_loader','-o',str(B/'p42-launch-floor')]
with (B/'link.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
rows.append(dict(argv=cmd,returncode=r.returncode))
receipt=dict(device_executed=False,commands=rows,peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
if not r.returncode:receipt['binary_sha256']=hashlib.sha256((B/'p42-launch-floor').read_bytes()).hexdigest()
(P/'launch-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if r.returncode:raise SystemExit(str(B/'link.log'))
print(receipt['binary_sha256'])

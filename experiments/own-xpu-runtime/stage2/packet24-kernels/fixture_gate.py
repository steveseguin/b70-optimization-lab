"""Two fresh processes under each host compiler; never execute device builds."""
import hashlib,json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 root=B/f'fixture-runs-{time.time_ns()}';root.mkdir();rows=[];identities={}
 for compiler in ('host','icpx-host'):
  for name in ('fused-fixtures','nongemv-fixtures'):
   binary=B/compiler/name;elf=subprocess.check_output(['readelf','-d',str(binary)],text=True)
   assert not any(x in elf.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
   for kernels,repeat in ((k,r) for k in ('v1','v2') for r in range(2)):
    out=root/f'{compiler}-{name}-{kernels}-{repeat}'
    with (root/f'{compiler}-{name}-{kernels}-{repeat}.log').open('w') as log:subprocess.run([str(binary),'--kernels',kernels,'--output',str(out)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
    r=json.loads((out/'receipt.json').read_text());assert r['passed'] and not r['device_executed']
    h=sha(out/'output.bin');assert h==r['fixture_output_sha256']
    if name in identities:assert identities[name]==h
    else:identities[name]=h
    extra={}
    if name=='nongemv-fixtures':extra={n:json.loads((out/n).read_text()) for n in ('kernel-fixture.json','route-fixture.json')}
    rows.append(dict(extra=extra,compiler=compiler,component=name,kernels=kernels,repeat=repeat,receipt=r,binary_sha256=sha(binary),output_sha256=h,output_bytes=(out/'output.bin').stat().st_size))
    print(compiler,name,repeat,'PASS',flush=True)
 result=dict(passed=True,device_executed=False,rows=rows,outputs=identities,fixture_inputs={x.name:sha(x) for x in (B/'fusion-fixtures').iterdir() if x.is_file()})
 (P/'fixture-gates.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 main()
 from compact_fixtures import main as compact
 compact()

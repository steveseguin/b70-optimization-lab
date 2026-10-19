"""Bounded native builds through the frozen shared compiler turn."""
import hashlib,json,os,resource,shutil,subprocess,sys,time,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=27_000_000_000,'CPU disk floor'
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert sum(p.stat().st_size for p in (P/'build').rglob('*') if p.is_file())<=300_000_000
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare_assets():
 packed=P/'rope.bf16.gz';expected=json.loads((P/'evidence/runtime-assets.json').read_text())['assets'];assert sha(packed)==expected[str(packed.relative_to(ROOT))]
 raw=gzip.decompress(packed.read_bytes());assert hashlib.sha256(raw).hexdigest()==expected[str((P/'rope.bf16').relative_to(ROOT))]
 (P/'build').mkdir(exist_ok=True);(P/'build/rope.bf16').write_bytes(raw)
def main():
 limits();prepare_assets();records=[];history=P/"evidence"/("build-"+str(time.time_ns()));history.mkdir()
 modes=[('gnu-host','/usr/bin/g++',['-DOWN_RT_HOST_ONLY']),('intel-host','/opt/intel/oneapi/compiler/2026.0/bin/icpx',['-DOWN_RT_HOST_ONLY']),('device','/opt/intel/oneapi/compiler/2026.0/bin/icpx',['-fsycl','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fdenormal-fp-math=ieee'])]
 if len(sys.argv)>1:modes=[m for m in modes if m[0] in sys.argv[1:]]
 for mode,compiler,extra in modes:
  out=P/'build'/('micro-'+mode);log=history/('build-'+mode+'.log')
  cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-Werror=return-type',*extra,'-DP166_ROOT="'+str(P)+'"',str(P/'micro.cpp'),'-lcrypto','-o',str(out)]
  with turn(),log.open('w') as f:
   sources={str(p.relative_to(ROOT)):sha(p) for p in P.rglob('*') if p.is_file() and p.suffix in ('.hpp','.cpp')}
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
   assert all(sha(ROOT/p)==h for p,h in sources.items()),'sources changed during compile'
  records.append(dict(mode=mode,command=cmd,path=str(out.relative_to(ROOT)),sha256=sha(out),sources=sources,log=str(log.relative_to(ROOT))))
  print(mode,'built',flush=True)
 receipt=dict(passed=True,device_executed=False,records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (history/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'evidence/build.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()

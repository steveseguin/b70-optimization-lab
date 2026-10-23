from pathlib import Path
import datetime,hashlib,json,os,resource,shlex,shutil,subprocess,sys,time
root=Path('/home/steve/llm-optimizations');p=root/'experiments/own-xpu-runtime/stage2/packet204-prefill-row-bindings'
sys.path.insert(0,str(root/'experiments/own-xpu-runtime/ops'))
from compile_turn import turn
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
assert shutil.disk_usage('/').free>=27_000_000_000
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
(p/'build').mkdir(exist_ok=True);(p/'evidence').mkdir(exist_ok=True)
a=p/'evidence'/('cache-build-'+str(time.time_ns()));a.mkdir()
source=p/'cache_contract_probe.cpp';(a/source.name).write_bytes(source.read_bytes())
(a/'build-script.py').write_bytes(Path(__file__).read_bytes())
binary=p/'build/cache-contract-probe';dep=p/'build/cache-contract.d'
command=['/usr/bin/g++','-std=c++20','-O2','-Wall','-Wextra','-Werror=return-type','-MMD','-MF',str(dep),str(source),'-o',str(binary)]
row={'schema':'packet204.cache-metadata-fixture.v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':False,'device_executed':False,'production_policy_implemented':False,'completion_facts':'simulated','command':command,'nice':os.getpriority(os.PRIO_PROCESS,0),'affinity':sorted(os.sched_getaffinity(0)),'compiler_version':subprocess.check_output(['/usr/bin/g++','--version'],text=True).splitlines()[0]}
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
with turn(),(a/'compile.log').open('x') as f:r=subprocess.run(command,cwd=root,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
row['compile_returncode']=r.returncode
if r.returncode:
 (a/'receipt.json').write_text(json.dumps(row,indent=2)+'\n');raise SystemExit(r.returncode)
words=shlex.split(dep.read_text().replace('\\\n',' '));files=[Path(s) for s in words[1:]]
assert all(f.is_relative_to(root) for f in files)
row['source_sha256']={str(f.relative_to(root)):sha(f) for f in files};row['binary_sha256']=sha(binary)
with (a/'stdout.json').open('x') as out,(a/'stderr.log').open('x') as err:r=subprocess.run([str(binary)],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
row['run_returncode']=r.returncode
if not r.returncode:
 row['result']=json.loads((a/'stdout.json').read_text());assert row['result']['passed']
 for name,digest in row['source_sha256'].items():assert sha(root/name)==digest
 assert sha(binary)==row['binary_sha256'];row['passed']=True
row['artifacts_sha256']={str(f.relative_to(root)):sha(f) for f in a.iterdir() if f.is_file()}
(a/'receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
if row['passed']:(p/'evidence/cache-metadata-tests.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
print(json.dumps({'passed':row['passed'],'receipt':str(a/'receipt.json'),'groups':row.get('result',{}).get('groups')}))
raise SystemExit(r.returncode)

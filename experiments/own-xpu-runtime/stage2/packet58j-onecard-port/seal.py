#!/usr/bin/env python3
"""Seal immutable CPU inputs and binaries; never pin a queue or live ops receipt."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
GATES=('evidence/byte-gates.json','evidence/fullshape-submit-cpu.json','evidence/budget-cpu.json',
       'evidence/postload-allocation-cpu.json','evidence/python-cpu-gates.json',
       'evidence/admission-cpu.json','evidence/mask-cpu.json','evidence/cache-cpu-gates.json',
       'evidence/copy-queue-cpu.json','k1-cpu.json','request-reset-cpu.json')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def require(v,s):
 if not v:raise ValueError(s)
def verify_files(root,items):
 require(bool(items),'empty pins')
 for n,h in items.items():
  path=(root/n).resolve();require(path.is_relative_to(ROOT) and sha(path)==h,'changed immutable input: '+n)
def create():
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
 require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
 sources={};artifacts={};gates={}
 for mode in ('gnu-host','device'):
  leaf=f'build-{mode}-receipt.json';r=read(P/leaf)
  require(r.get('passed') is True and r.get('device_executed') is False,'build failed')
  verify_files(ROOT,r['sources_sha256']);verify_files(P,r['binaries'])
  sources.update(r['sources_sha256']);artifacts.update(r['binaries']);gates[leaf]=sha(P/leaf)
 for leaf in GATES:
  r=read(P/leaf);require(r.get('passed') is True and r.get('device_executed') is False,'gate failed: '+leaf)
  pins=r.get('sources',r.get('dependencies',r.get('source_sha256',{})))
  if pins:verify_files(ROOT,pins);sources.update(pins)
  gates[leaf]=sha(P/leaf)
 full=read(P/'evidence/fullshape-submit-cpu.json')
 require(full['checks']==80 and full['binary_sha256']==sha(P/'build/gnu-host/fullshape-submit'),'fullshape binary/check count')
 from views import VIEWS,digest
 expected={(v,w,m) for v in VIEWS for w in ('KD','W2m','WS','WS128x','WS128') for m in ('zero-copy','streamed')}
 require({(r['view'],r['window'],r['miss_path']) for r in full['records']}==expected,'fullshape coverage')
 for r in full['records']:
  require(r['passed'] and r['legacy_refused'] and r['sites']==1486 and r['contexts']==[32,4096] and r['allocation_rows']==3446 and r['selection_sha256']==digest(r['view']),'incomplete extent proof')
  require(r['arena_totals']=={'device':24287732980,'host-pinned':48633091712},'one-card arena changed')
 bytes_=read(P/'evidence/byte-gates.json');require(len(bytes_['records'])==12,'both compilers/repeats required')
 require({(r['compiler'],r['fixture'],r['repeat']) for r in bytes_['records']}=={(c,f,r) for c in ('gnu','intel') for f in ('p100_cpu','p82_cpu','p58j_route_cpu') for r in (0,1)},'byte coverage')
 budget=read(P/'evidence/budget-cpu.json');require(budget['unchanged_budget'] and len(budget['records'])==56 and not budget['E1']['admitted'],'budget coverage')
 k1=read(P/'k1-cpu.json');require(k1['checks']==48 and k1['binary_sha256']==sha(P/'build/gnu-host/p58-cache-fixtures'),'K1 coverage/binary')
 for leaf in ('request-reset-cpu.json','evidence/postload-allocation-cpu.json'):
  require(read(P/leaf)['binary_sha256']==sha(P/'build/gnu-host/own-rt-iq3'),'stale engine gate')
 # These parent manifests contain only frozen source/input snapshots, never
 # selections/ready.json/queue.json from a changing parent orchestrator.
 for name in ('parent58g-source-manifest.json','port-source-manifest.json'):
  verify_files(ROOT,read(P/name))
 for f in [*P.glob('*.py'),P/'CMakeLists.txt',P/'views.json',P/'dispatch-speed6.json',P/'oracle-binding.json',P/'record-threshold.json',P/'parent58g-source-manifest.json',P/'port-source-manifest.json',P/'rope.bf16',*P.glob('launch-*.sh'),*(P/'selections').glob('*.json')]:sources[str(f.relative_to(ROOT))]=sha(f)
 for n in ('packet56-draft-prefix/p56_head_support.py','packet56-draft-prefix/suite_metrics.py','packet34-replay-bench/window.py','packet49-integrate/oracle/suite_check.py'):
  f=P.parent/n;sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (P/'evidence/58c-supervisor').glob('*'):sources[str(f.relative_to(ROOT))]=sha(f)
 import memory_plan as M
 plan=M.plan();sources.update(plan['allocation_inventory']['sources']);sources[plan['census']['source_path']]=plan['census']['source_sha256']
 # Oracle binding is immutable; all real requests recheck its complete closure.
 sources.update(read(P/'oracle-binding.json')['files_sha256'])
 record=read(P/'record-threshold.json')['measurement'];sources[record['path']]=record['sha256']
 for n in ('window.json','run/run/host-memory.jsonl','run/run/progress.jsonl'):
  f=P.parent/'packet58g-onecard/evidence/58b-kd'/n;sources[str(f.relative_to(ROOT))]=sha(f)
 for f in (P/'evidence/58c-kd/run').glob('*'):sources[str(f.relative_to(ROOT))]=sha(f)
 verify_files(ROOT,sources)
 require(not any('/ops/' in n or '/queue.json' in n or n.endswith('/ready.json') for n in sources),'mutable orchestration in source seal')
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());require(size<=300_000_000,'300 MB build cap')
 row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,
   runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',
   sources=sources,artifacts=artifacts,gates=gates,retained_build_bytes=size,views=list(VIEWS),
   immutable_inputs_only=True,qualification='CPU preparation; device exactness, speed and external promotion pending')
 (P/'build-receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n');return row

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');args=ap.parse_args()
 if args.verify:
  row=read(P/'build-receipt.json');verify_files(ROOT,row['sources']);verify_files(P,row['artifacts']);verify_files(P,row['gates'])
 else:row=create()
 print(json.dumps(dict(passed=True,device_executed=False,build_bytes=row['retained_build_bytes'],views=len(row['views']),sources=len(row['sources']))))
if __name__=='__main__':main()

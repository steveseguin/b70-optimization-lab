#!/usr/bin/env python3
"""Metadata-only actual backing FD micro; no payload reads, hashing or advice."""
import json,os,pathlib,statistics,time
HERE=pathlib.Path(__file__).resolve().parent
PLAN=pathlib.Path('/dev/shm/sc117-dedicated-bounded-count-2plus1-128k-long512-20261028-r1/output/plan.json')
META=HERE.parents[2]/'gsq-rco-iq3s/metadata/new-census.json'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))
plan=json.loads(PLAN.read_text());meta=json.loads(META.read_text());argv=plan['stages'][0]['argv'];model=pathlib.Path(argv[argv.index('--model-dir')+1]);assert str(model)==meta['root']
paths=[model/meta['tensors'][name]['shard'] for name in ['token_embd.weight','per_layer_token_embd.weight']]
def ident(s):return dict(dev=s.st_dev,ino=s.st_ino,size=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
def stats(v):return dict(samples=len(v),median_us=statistics.median(v)/1000,p95_us=sorted(v)[int(.95*(len(v)-1))]/1000,total_us=sum(v)/1000)
fds=[os.open(p,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW) for p in paths]
try:
 before=[ident(os.fstat(fd))for fd in fds];times=[[],[]];groups=[];start=time.monotonic()
 for _ in range(500):
  group=time.perf_counter_ns()
  for _phase in range(2):
   for i,fd in enumerate(fds):
    t=time.perf_counter_ns();s=os.fstat(fd);times[i].append(time.perf_counter_ns()-t)
    assert ident(s)==before[i]
  groups.append(time.perf_counter_ns()-group)
 elapsed=time.monotonic()-start
 assert [ident(os.fstat(fd))for fd in fds]==before
 assert [ident(os.stat(p,follow_symlinks=False))for p in paths]==before
 result={'scope':'Python os.fstat elapsed includes Python object/instrumentation overhead, not native guard benchmark or cold filesystem claim; observed identity stable',
  'payload_reads':0,'payload_hashes':0,'cache_advice_or_settings_changes':False,'cpu_affinity':sorted(os.sched_getaffinity(0)),'nice':19,
  'source_plan':str(PLAN),'source_metadata':str(META),'backings':[{**stats(v),'path':str(p),'identity':i}for p,i,v in zip(paths,before,times)],
  'four_fstat_command_groups':stats(groups),'wall_seconds':elapsed,'loop':'500 command groups; each pre/post checks both2held FDs (1000samples perFD); no warmup'}
 target=HERE/'fstat-backings-r2.json'
 with target.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result,indent=2))
finally:
 for fd in fds:os.close(fd)

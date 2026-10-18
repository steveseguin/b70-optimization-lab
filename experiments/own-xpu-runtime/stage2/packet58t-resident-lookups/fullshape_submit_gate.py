#!/usr/bin/env python3
"""All views, model windows and miss paths use actual full one-card arena rows."""
import hashlib,json,os,resource,subprocess,tempfile,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 binary=P/'build/gnu-host/fullshape-submit';sources=dict(json.loads((P/'parent-build-gnu-host-receipt.json').read_text())['sources_sha256'])
 for f in [Path(__file__),P/'views.json',P/'dispatch-speed6.json',P.parent/'suite-inputs-20261012/incident-retrospective/plan.tsv',*(P/'selections').glob('*.json')]:sources[str(f.relative_to(ROOT))]=sha(f)
 assert all(sha(ROOT/n)==h for n,h in sources.items());records=[];start=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='fullshape-',dir=P/'build') as tmp:
  for view in json.loads((P/'views.json').read_text()):
   for window in ('KD','W2m','WS','WS128x','WS128','WSCREEN'):
    for miss in ('zero-copy','streamed'):
     out=Path(tmp)/f'{view}-{window}-{miss}'
     cmd=[str(binary),'--fullshape-submit-test',str(out),str(P/'selections'/f'{view}.json'),window,miss]
     run=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
     assert run.returncode==0,(cmd,run.stdout,run.stderr)
     row=json.loads((out/'result.json').read_text());assert row['passed'] and row['legacy_refused'] and row['sites']==1486 and row['contexts']==[32,4096]
     census=json.loads((out/'census.json').read_text())['allocations'];totals={m:sum(x['bytes'] for x in census if x['memory']==m) for m in ('device','host-pinned')}
     assert len(census)==3446 and totals=={'device':24287732980,'host-pinned':48633091712},totals
     row.update(view=view,window=window,miss_path=miss,allocation_rows=len(census),arena_totals=totals,selection_sha256=sha(P/'selections'/f'{view}.json'))
     records.append(row)
     if len(records)==1:
      for leaf in ('census.json','58f-refusal.txt','prepared-arguments-parity0.jsonl','teardown.json'):(P/'evidence'/('fullshape-'+leaf)).write_bytes((out/leaf).read_bytes())
     # Remove only this gate's own scratch, keeping digests and the reference census.
     import shutil;shutil.rmtree(out)
   print(view,'all model windows and both miss paths PASS',flush=True)
 rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<8*1024**3
 assert all(sha(ROOT/n)==h for n,h in sources.items())
 row=dict(schema='packet58j.fullshape.v1',passed=True,device_executed=False,model_reads=False,legacy_refused=True,sites=1486,contexts=[32,4096],records=records,checks=len(records),peak_rss_bytes=rss,sources=sources,binary_sha256=sha(binary),elapsed_seconds=time.monotonic()-start)
 (P/'evidence/fullshape-submit-cpu.json').write_text(json.dumps(row,indent=2)+'\n');print('fullshape checks',len(records),flush=True)
if __name__ == '__main__':
    # The CPU mock reserves full-size sparse virtual arenas (over 8 GB), but
    # touches only bounded backing. Check physical peak RSS above; an AS cap
    # would reject the virtual census before testing real production extents.
    main()

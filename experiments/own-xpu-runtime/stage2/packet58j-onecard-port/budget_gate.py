#!/usr/bin/env python3
"""Metadata-only equivalence to 58g. No pin, sysfs write or device open."""
import importlib.util,json,hashlib
from pathlib import Path
import memory_plan as M
from views import VIEWS
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 f=P.parent/'packet58g-onecard/memory_plan.py';spec=importlib.util.spec_from_file_location('frozen58g_memory',f);parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
 records=[]
 for window in ('K1a','K1b','KD','W2m','WS','WS128x','WS128'):
  before=parent.window_plan(window);after=M.window_plan(window);assert before==after
  for view in VIEWS:records.append(dict(view=view,window=window,required_bytes=after['host_required_available_bytes'],reserve_bytes=after['host_reserve_bytes'],expert_cache_bytes=M.CACHE_BYTES,passed=True))
 # Loader chunks are capped at 4 MiB and tile aligned, including the last chunk.
 rows=2560*512;stride=360;chunk=(4*1024*1024//stride//16)*16
 assert chunk==11648
 for start in range(0,rows,chunk):assert start%16==0 and min(chunk,rows-start)%16==0
 assert 3*4*1024*1024 < M.plan()['host_categories']['loader_staging_bound']
 sources={str(x.relative_to(ROOT)):sha(x) for x in (Path(__file__),P/'memory_plan.py',P/'main.cpp',P/'views.json',f)}
 row=dict(passed=True,device_executed=False,model_reads=False,records=records,unchanged_budget=True,pin_bytes=M.census_inventory()['pinned_expert_bytes'],cache_bytes=M.CACHE_BYTES,loader_extra_scratch_bound=4*1024*1024,chunk_rows=chunk,E1=dict(admitted=False,extra_pinned_bytes=47*2*512*640*20,reason='exceeds frozen pinned-bank allocation; no cache or reserve reduction'),sources=sources)
 (P/'evidence/budget-cpu.json').write_text(json.dumps(row,indent=2)+'\n');print('56 view/window budgets equal frozen58g; E1 excluded')
if __name__=='__main__':main()

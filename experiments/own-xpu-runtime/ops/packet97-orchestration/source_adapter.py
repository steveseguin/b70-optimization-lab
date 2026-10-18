"""Read frozen source comparisons in their own import namespace; never writes."""
import contextlib,io,json,sys,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];STAGE=ROOT/'experiments/own-xpu-runtime/stage2'
PACKETS={'90':'packet90-expert-hc','91':'packet91-record-bundle','92':'packet92-rank1-reply-first','93':'packet93-packed-head2','94':'packet94-hc-norm-fusion','95':'packet95-expert-dequant'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(number):
 p=STAGE/PACKETS[number];sys.path.insert(0,str(p));import screen_jobs as jobs;import compare as comp
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();result=dict(packet=int(number),status='pending',receipts={},sources={},directions={})
 def pin(f,category):
  if f.is_file():result[category][str(f.relative_to(ROOT))]=sha(f)
 try:
  seal=jobs.verify()
  result['sources'].update(seal['sources'])
  for leaf in ('screen-jobs-seal.json','compare.py','screen_jobs.py'):pin(p/leaf,'sources')
  qualified=jobs.qualified_candidates() if number=='93' else None
  if number=='93':
   for f in (p/'evidence/micro-B2').rglob('*'):pin(f,'receipts')
   pin(p/'evidence/microbench-build.json','receipts')
  for direction in ('A-grid','B-grid'):
   source,other=('A','B') if direction=='A-grid' else ('B','A');rows_by_lane={};d=dict(status='pending',lanes=rows_by_lane)
   def load_rows(lane,entries):
    rows=[]
    for j in entries:
     r=comp.load(j) if number=='91' else comp.load(j,lane)
     root=(jobs.output(j) if j['mode']=='grid' else jobs.WRAPPER/'evidence'/f'p91-{lane}-confirm-{j["index"]}') if number=='91' else jobs.WRAPPER/'evidence'/j['out']
     w=json.loads((root/'window.json').read_text());assert r['exact'] is True,'13/13 exact required'
     assert w['boot_id']==boot,'stale source screen boot'
     r.update(exact_count=13,all_13_exact=True,lane=lane,boot_id=boot,started_utc_ns=w['started_utc_ns'],finished_utc_ns=w['finished_utc_ns'],output=str(root))
     assert math.isfinite(r['rate']) and r['rate']>0
     for f in root.rglob('*.json'):pin(f,'receipts')
     rows.append(r)
    assert all(r['started_utc_ns']<r['finished_utc_ns'] for r in rows)
    assert all(a['finished_utc_ns']<b['started_utc_ns'] for a,b in zip(rows,rows[1:])),'overlapping/out-of-order bracket'
    assert all(r['acceptance_counts']==rows[0]['acceptance_counts'] for r in rows),'acceptance changed'
    rows_by_lane[lane]=rows;return rows
   try:
    kwargs={'direction':direction}
    if number=='93':kwargs['qualified']=qualified
    if number=='95':kwargs['grid']='exp-grid-prefetch'
    grid=load_rows(source,jobs.jobs(source) if number=='91' else jobs.jobs(source,**kwargs))
    if number=='91':comp.compare(grid)
    try:best=jobs.choose(grid,qualified) if number=='93' else jobs.choose(grid,'exp-grid-prefetch') if number=='95' else jobs.choose(grid)
    except ValueError as e:
     if str(e).startswith('no candidate beats both'):d.update(status='no-winner',reason=str(e));continue
     raise
    if number=='91':
     errors=[];confirmation=None
     for mode in ('confirm','grid'):
      try:
       candidate=load_rows(other,jobs.jobs(other,best['choice'],mode));comp.compare(candidate,tuple(j['choice'] for j in jobs.jobs(other,best['choice'],mode)));confirmation=candidate;break
      except FileNotFoundError as e:errors.append(str(e))
     if confirmation is None:raise FileNotFoundError('; '.join(errors))
    else:
     confirmation=load_rows(other,jobs.jobs(other,best['choice'],**kwargs))
     # Invoke exactly the source's compare logic as well as its load/choose.
     try:
      if number=='95':comp.compare_direction(direction,'exp-grid-prefetch')
      else:comp.compare_direction(direction)
     except ValueError as e:
      if str(e).startswith('confirmation winner must beat both'):d.update(status='no-winner',reason=str(e));continue
      raise
    confirmed=next(r for r in confirmation[1:-1] if r['choice']==best['choice'])
    assert confirmed['acceptance_counts']==grid[0]['acceptance_counts'],'cross-lane acceptance changed'
    ratios={source:best['rate']/max(grid[0]['rate'],grid[-1]['rate']),other:confirmed['rate']/max(confirmation[0]['rate'],confirmation[-1]['rate'])}
    d.update(status='winner' if min(ratios.values())>1 else 'no-winner',choice=best['choice'],ratios=ratios)
   except FileNotFoundError as e:d.update(status='pending',reason=str(e))
   except (ValueError,AssertionError,KeyError,TypeError,OSError) as e:d.update(status='failed',reason=str(e))
   finally:result['directions'][direction]=d
  complete=[d for d in result['directions'].values() if d['status']=='winner'];failed=[d for d in result['directions'].values() if d['status']=='failed']
  if failed:result.update(status='failed',reason=failed[0]['reason'])
  elif complete:
   assert len({d['choice'] for d in complete})==1,'conflicting directional winners'
   result.update(status='winner',winner=complete[0]['choice'],lanes=complete[0]['lanes'],ratios=complete[0]['ratios'])
  elif any(d['status']=='no-winner' for d in result['directions'].values()):result['status']='no-winner'
 except FileNotFoundError as e:result['reason']=str(e)
 except (ValueError,AssertionError,KeyError,TypeError,OSError) as e:result.update(status='failed',reason=str(e))
 return result
if __name__=='__main__':
 with contextlib.redirect_stdout(io.StringIO()):r=collect(sys.argv[1])
 print(json.dumps(r))

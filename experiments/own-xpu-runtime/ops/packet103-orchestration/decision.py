"""CPU source decision; no model import, launcher, queue mutation or device work."""
import json, math
from pathlib import Path
O=Path(__file__).resolve().parent
DEFAULTS=dict(dense='production',hc='hc-wide',experts='wide64',host='ordered',route='production',norm='production',recurrence='rec-parallel',draft_head='production',head='production',hc_norm='production',down='production',draft_attention='production')
DIMENSIONS={'91':('route','recurrence'),'93':('head',),'92':('host',),'94':('hc_norm',),'95':('experts',),'90':('experts',),'100':('down',),'101':('draft_attention',)}
SOURCE_CHOICES={'91':{'route-fast':dict(route='fast'),'rec-both-plus':dict(recurrence='rec-both-plus'),'route-fast-rec-both-plus':dict(route='fast',recurrence='rec-both-plus')},'93':{'head-transpose':dict(head='head-transpose')},'92':{'reply-first':dict(host='ordered+reply-first')},'94':{'hc-normfuse':dict(hc_norm='normfuse')},'100':{'down-tile16':dict(down='tile16')},'101':{'draft_attention':dict(draft_attention='split32')}}
def check_winner(r):
 assert r['status']=='winner' and r['lanes'] and set(r['lanes'])<={'A','B'}
 assert not r.get('record_lane_veto'), 'record lane A excludes source'
 assert set(r['ratios'])==set(r['lanes'])
 boots=set()
 for lane,rows in r['lanes'].items():
  assert len(rows)>=3 and rows[0]['choice']==rows[-1]['choice']
  assert all(x.get('exact') is True and x.get('exact_count')==13 for x in rows)
  assert all(x['lane']==lane for x in rows)
  assert all(math.isfinite(x['rate']) and x['rate']>0 for x in rows)
  assert all(x['started_utc_ns']<x['finished_utc_ns'] for x in rows)
  assert all(a['finished_utc_ns']<b['started_utc_ns'] for a,b in zip(rows,rows[1:]))
  assert all(x['acceptance_counts']==rows[0]['acceptance_counts'] for x in rows)
  matched=[x for x in rows[1:-1] if x['choice']==r['winner']];assert len(matched)==1
  ratio=matched[0]['rate']/max(rows[0]['rate'],rows[-1]['rate']);assert ratio>1
  assert math.isclose(ratio,r['ratios'][lane],rel_tol=1e-12)
  boots.update(x['boot_id'] for x in rows)
 assert len(boots)==1
 if len(r['lanes'])==2:assert r['lanes']['A'][0]['acceptance_counts']==r['lanes']['B'][0]['acceptance_counts']
def select(screens):
 assert set(screens)==set(DIMENSIONS)
 control=dict(DEFAULTS);candidate=dict(control);confirmed=[]
 for n,r in screens.items():
  if r['status']=='failed':raise ValueError('source '+n+' invalid: '+r.get('reason',''))
  assert r['status'] in ('pending','excluded','no-winner','winner')
  if r['status']=='winner':check_winner(r)
 for n,options in SOURCE_CHOICES.items():
  r=screens[n]
  if r['status']=='winner':
   assert r['winner'] in options,'unregistered source winner'
   candidate.update(options[r['winner']]);confirmed.append(n)
 parts=['wide64']
 for n,choice,part in [('95','exp-grid-prefetch','grid-prefetch'),('90','exp-halfcache','halfcache')]:
  r=screens[n]
  if r['status']=='winner':
   assert r['winner']==choice
   parts.append(part);confirmed.append(n)
 candidate['experts']='+'.join(parts)
 return control,candidate,confirmed
def main():
 from read_screens import collect,require_current
 screens=collect();require_current(screens)
 (O/'screens-current.json').write_text(json.dumps(screens,indent=2)+'\n')
 row=dict(schema='packet103.source-decision-dry-run.v1',passed=False,ready=False,device_executed=False)
 try:
  control,candidate,confirmed=select(screens)
  row.update(passed=True,control=control,candidate=candidate,confirmed_sources=confirmed,
             deferred_sources=[n for n,r in screens.items() if r['status']=='pending'],
             excluded_sources={n:r.get('reason') for n,r in screens.items() if r['status'] in ('excluded','no-winner')},
             reason='CPU decision only; composition brackets and sealed chain gates required')
 except (ValueError,AssertionError) as e:row['reason']=str(e)
 (O/'decision-dry-run.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2))
 return 0 if row['passed'] else 2
if __name__=='__main__':raise SystemExit(main())

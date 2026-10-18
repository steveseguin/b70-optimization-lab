"""CPU-only source decision, composition proposals and sealed chain readiness."""
import argparse,json,math,shlex,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;O=HERE.parent;sys.path.insert(0,str(O));ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet97-record-bundle'
sys.path.insert(0,str(P))
from build_engine import sha,save,limits
from bundle_selection import KEYS,name
from screen_jobs import DEFAULTS
PREFIX=['nice','-n','19','ionice','-c3','taskset','-c','8-15,24-31','/home/steve/.venvs/deepseek-v4-xpu/bin/python','-B']
DIMENSIONS={'91':('route','recurrence'),'93':('head',),'92':('host',),'94':('hc_norm',),'95':('experts',),'90':('experts',)}
SOURCE_CHOICES={'93':{'head-transpose':{'head':'head-transpose'}},'92':{'reply-first':{'host':'ordered+reply-first'}},'94':{'hc-normfuse':{'hc_norm':'normfuse'}}}
def check_winner(r):
 assert r['status']=='winner' and r['lanes'] and set(r['lanes'])<={'A','B'},'at least one source lane required'
 assert set(r['ratios'])==set(r['lanes']),'ratio lanes differ'
 boots=set()
 for lane,rows in r['lanes'].items():
  assert len(rows)>=3 and rows[0]['choice']==rows[-1]['choice'],'fresh bracket required'
  assert all(x.get('exact') is True and x.get('exact_count')==13 for x in rows),'13/13 exact required'
  assert all(x['lane']==lane for x in rows),'same lane controls required'
  assert all(math.isfinite(x['rate']) and x['rate']>0 for x in rows),'invalid rate'
  assert all(x['started_utc_ns']<x['finished_utc_ns'] for x in rows)
  assert all(a['finished_utc_ns']<b['started_utc_ns'] for a,b in zip(rows,rows[1:])), 'overlap'
  assert all(x['acceptance_counts']==rows[0]['acceptance_counts'] for x in rows),'acceptance changed'
  matched=[x for x in rows[1:-1] if x['choice']==r['winner']];assert len(matched)==1
  ratio=matched[0]['rate']/max(rows[0]['rate'],rows[-1]['rate']);assert ratio>1,'must beat both controls'
  assert math.isclose(ratio,r['ratios'][lane],rel_tol=1e-12),'reported ratio differs'
  boots.update(x['boot_id'] for x in rows)
 assert len(boots)==1,'same boot required'
 if len(r['lanes'])==2:assert r['lanes']['A'][0]['acceptance_counts']==r['lanes']['B'][0]['acceptance_counts'],'cross-lane acceptance changed'
def select(screens):
 control=dict(DEFAULTS);candidate=dict(control);confirmed=[]
 for n,r in screens.items():
  if r['status']=='failed':raise ValueError('source '+n+' invalid: '+r.get('reason',''))
  if r['status']=='winner':check_winner(r)
 r=screens['91']
 if r['status']=='winner':
  options={'route-fast':dict(route='fast'),'rec-both-plus':dict(recurrence='rec-both-plus'),'route-fast-rec-both-plus':dict(route='fast',recurrence='rec-both-plus')}
  if r['winner'] not in options:raise ValueError('unregistered packet91 winner')
  candidate.update(options[r['winner']]);confirmed.append('91')
 for n,options in SOURCE_CHOICES.items():
  r=screens[n]
  if r['status']=='winner':
   if r['winner'] not in options:raise ValueError('closed/unregistered source winner '+n)
   candidate.update(options[r['winner']]);confirmed.append(n)
 experts=[]
 for n,choice,part in [('95','exp-grid-prefetch','grid-prefetch'),('90','exp-halfcache','halfcache')]:
  r=screens[n]
  if r['status']=='winner':
   if r['winner']!=choice:raise ValueError('closed/unregistered expert winner '+n)
   experts.append(part);confirmed.append(n)
 candidate['experts']='+'.join(['wide64',*experts]);name(*(candidate[k] for k in KEYS))
 return control,candidate,confirmed

def apply_pins(choice,values):
 choice=dict(choice);pins={}
 for value in values:
  if value.count('=')!=1:raise ValueError('pin must be key=value')
  k,v=value.split('=')
  if k not in DEFAULTS or k in pins or v!=DEFAULTS[k]:raise ValueError('pin must revert one registered dimension to baseline: '+k)
  pins[k]=v;choice[k]=v
 return choice,pins

def close_packets(screens,choice,pins,values):
 closed={}
 for value in values:
  if '=' not in value:raise ValueError('closure must be packet=reason')
  n,reason=value.split('=',1)
  if n not in DIMENSIONS or n in closed or not reason.strip():raise ValueError('unknown/duplicate/unexplained closure')
  if screens[n]['status']!='pending':raise ValueError('only pending source evidence may be closed')
  if any(pins.get(k)!=DEFAULTS[k] or choice[k]!=DEFAULTS[k] for k in DIMENSIONS[n]):raise ValueError('closure requires affected dimensions explicitly reverted')
  closed[n]=dict(reason=reason,previous_status='pending',dimensions={k:choice[k] for k in DIMENSIONS[n]})
  screens[n]=dict(screens[n],status='no-winner',coordinator_closure=closed[n])
 return closed

def pin_path(path):
 path=Path(path).resolve();return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
def command():
 args=['systemd-run','--user','--unit=packet97-chain','--property=Restart=no','--property=Nice=0','--property=CPUAffinity=0-3 16-19','--property=KillMode=process','--property=SendSIGKILL=no','--property=ExitType=cgroup','--property=TimeoutStopSec=infinity','--property=StandardOutput=append:'+str(O/'chain.log'),'--property=StandardError=append:'+str(O/'chain.log'),'--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/bash',str(HERE/'device-entry-review15.sh'),'chain']
 return shlex.join(args)+' </dev/null'
def run(label,args):
 with (O/(label+'.log')).open('w') as log:r=subprocess.run([*PREFIX,*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 if r.returncode:raise ValueError(label+' failed: '+str(O/(label+'.log')))
def source_pins(screens):
 pins={}
 for r in screens.values():
  for category in ('receipts','sources'):pins.update(r.get(category,{}))
 for f in [*O.glob('*.py'),*HERE.glob('*.py')]:pins[pin_path(f)]=sha(f)
 return pins

def composition(screens,control,candidate,confirmed,pins,closures):
 assert candidate!=control,'no new selected candidate'
 # Count each confirmed source selection once. Packet91's winning composition
 # is one confirmed source arm, not two inferred independent confirmations.
 selected=[n for n in confirmed if all(k not in pins for k in DIMENSIONS[n])]
 # A partially reverted packet91 source is not qualified as that winning arm.
 if '91' in confirmed and '91' not in selected:
  for k in DIMENSIONS['91']:candidate[k]=control[k]
 assert candidate!=control,'no retained qualified source'
 qualified={n:screens[n] for n in selected}
 return dict(schema='packet97.composition-selection.v1',status='confirmed-sources',
  qualification='one first-lane exact win per source; composite requires both lanes',
  control=control,candidate=candidate,confirmed_levers=selected,coordinator_pins=pins,
  coordinator_closures=closures,deferred_sources=[n for n,r in screens.items() if r['status']=='pending'],
  source_ratios={n:r['ratios'] for n,r in qualified.items()},qualified_screens=qualified,evidence_pins=source_pins({n:r for n,r in screens.items() if n in selected or r.get('record_lane_veto')}),
  **(dict(excluded_sources={n:r for n,r in screens.items() if r.get('record_lane_veto')})
     if any(r.get('record_lane_veto') for r in screens.values()) else {}))
def chain_policy(ratios,levers):
 assert set(ratios)=={'A','B'} and all(type(r) in (int,float) and math.isfinite(r) and r>1 for r in ratios.values()),'both lanes must improve'
 assert len(levers)==len(set(levers)) and set(levers)<=set(SOURCE_CHOICES)|{'90','95','91'},'unknown/duplicate lever'
 return min(ratios.values())>=1.015 or len(levers)>=2
def freeze_decision(config,screens=None):
 from composite_jobs import validate,identity
 validate(config)
 # Validation can take time. Check even pending/missing source windows after
 # it, immediately before freezing, for both decision-only and proposal modes.
 if screens is not None:
  from read_screens_review15 import require_current
  require_current(screens)
 decision=O/'decisions'/(identity(config)+'.json')
 decision.parent.mkdir(parents=True,exist_ok=True)
 if decision.exists():assert json.loads(decision.read_text())==config,'decision collision'
 else:
  with decision.open('x') as stream:stream.write(json.dumps(config,indent=2)+'\n')
 return decision
def matched_composition(config):
 from composite_jobs import read_brackets
 lanes=read_brackets(config);from compare import compare
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();ratios={};receipts={}
 for lane,rows in lanes.items():
  compare(rows);assert all(r['boot_id']==boot for r in rows),'stale composition boot'
  ratio=rows[1]['rate']/max(rows[0]['rate'],rows[-1]['rate']);ratios[lane]=ratio
  for row in rows:
   for f in Path(row['output']).rglob('*.json'):receipts[pin_path(f)]=sha(f)
 assert lanes['A'][0]['acceptance_counts']==lanes['B'][0]['acceptance_counts'],'composition acceptance changed across lanes'
 improved=all(r>1 for r in ratios.values())
 eligible=improved and chain_policy(ratios,config['confirmed_levers'])
 from composite_jobs import leave_one_out_required
 loo=leave_one_out_required(ratios,config)
 return dict(passed=improved,lanes=lanes,ratios=ratios,confirmed_levers=config['confirmed_levers'],chain_policy_passed=eligible,leave_one_out=loo,receipts=receipts)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--snapshot-only',action='store_true');ap.add_argument('--decision-only',action='store_true');ap.add_argument('--decision',type=Path);ap.add_argument('--pin',action='append',default=[]);ap.add_argument('--closed',action='append',default=[]);a=ap.parse_args();limits()
 row=dict(schema='packet97.ready.v1',ready=False,composition_ready=False,device_executed=False,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),chain_command=command())
 try:
  from read_screens_review15 import collect
  frozen=None
  if a.decision:
   assert not a.pin and not a.closed,'a frozen decision cannot be repinned or closed'
   frozen=json.loads(a.decision.read_text())
   from composite_jobs import validate
   validate(frozen)
   screens={n:frozen['qualified_screens'].get(n,frozen.get('excluded_sources',{}).get(n,dict(status='pending' if n in frozen['deferred_sources'] else 'no-winner',receipts={},sources={}))) for n in DIMENSIONS}
  else:screens=collect()
  if not a.decision_only:save(O/'screens-current.json',screens);row['screens']=screens
  control,candidate,confirmed=select(screens)
  candidate,pins=apply_pins(candidate,[k+'='+v for k,v in frozen['coordinator_pins'].items()] if frozen else a.pin)
  closures=frozen['coordinator_closures'] if frozen else close_packets(screens,candidate,pins,a.closed)
  row.update(control=control,selection=candidate,coordinator_pins=pins,coordinator_closures=closures)
  config=composition(screens,control,candidate,confirmed,pins,closures)
  if not frozen:
   from read_screens_review15 import require_current
   require_current(screens)
  if frozen:
   assert config['candidate']==frozen['candidate'] and config['confirmed_levers']==frozen['confirmed_levers'],'frozen selection differs'
   config=frozen  # Preserve the original decision and its pins exactly.
  row.update(composition_ready=True,qualified_sources=config['confirmed_levers'],deferred_sources=config['deferred_sources'])
  assert not (a.decision_only and a.snapshot_only),'choose decision-only or snapshot-only'
  if a.snapshot_only:raise ValueError('snapshot only; no preparation changed')
  decision=freeze_decision(config,None if frozen else screens)
  if a.decision_only:
   print(json.dumps(dict(decision=str(decision),confirmed_sources=config['confirmed_levers'],excluded_sources={n:r['reason'] for n,r in config.get('excluded_sources',{}).items()},device_executed=False,live_queue_modified=False),indent=2))
   return 0
  from composite_jobs import prepare_proposals
  row['proposals']=prepare_proposals(config)
  row['composition']=matched_composition(config)
  if row['composition']['leave_one_out']['required']:
   row['leave_one_out_proposals']=prepare_proposals(config,leave_one_out=True)
   raise ValueError('composite below best single source or +0.5%; run proposed leave-one-out brackets')
  assert row['composition']['chain_policy_passed'],'chain policy needs >=1.5% on both lanes or >=2 qualified selected sources'
  from stopped_archive import require_fresh_chain
  require_fresh_chain(P/'build')
  previous=json.loads((P/'composition-selection.json').read_text())
  if previous!=config:save(P/'composition-selection.json',config)
  run('composition-queue-plan',[P/'queue_plan.py'])
  run('reseal',[P/'fast_reseal.py',*[x for k,v in candidate.items() for x in ('--'+k,v)]])
  checks=[('cpu-dry-run',[P/'dry_run.py']),('seal',[P/'chain_seal.py','--verify']),('inputs',[P/'check_inputs.py']),('storage',[P/'storage_precheck.py']),('queue-plan',[P/'queue_runner.py','--plan','--output-root',P/'build/device-cards01-a'])]
  for label,args in checks:run(label,args)
  row['checks']={label:sha(O/(label+'.log')) for label,_ in checks}
  row['pins']={pin_path(f):sha(f) for f in [P/'build-receipt.json',P/'bundle-selection.json',P/'submission-pins.json',P/'screen-jobs-seal.json',P/'composition-selection.json',P/'evidence/dry-run.json',P/'evidence/selection-dry-run.json',*O.glob('*.py'),*HERE.glob('*.py'),HERE/'device-entry-review15.sh']}
  row.update(preparation_passed=True,ready=True)
 except (ValueError,OSError,AssertionError,KeyError,subprocess.SubprocessError) as error:row['reason']=str(error)
 save(O/('review15-decision-error.json' if a.decision_only else 'ready.json'),row);print(json.dumps({k:row.get(k) for k in ('ready','reason','selection','chain_command')},indent=2));return 0 if row['ready'] else 2
if __name__=='__main__':raise SystemExit(main())

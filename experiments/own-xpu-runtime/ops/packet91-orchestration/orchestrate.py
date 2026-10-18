"""CPU-only matched selection, seal and readiness. Prints, never runs, the chain."""
import argparse,json,os,shlex,subprocess,sys,math,resource
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet91-record-bundle'
sys.path.insert(0,str(P))
from build_engine import sha,save,limits
from screen_jobs import VIEWS
PREFIX=['nice','-n','19','taskset','-c','8-15,24-31',sys.executable,'-B']
DEFAULTS=dict(VIEWS['control'],expert_hc='none')
def select(screens):
 chosen=dict(DEFAULTS);r=screens.get('91',{})
 if r.get('status')=='winner':
  if set(r.get('lanes',{}))!={'A','B'} or not all(r['lanes'].values()):raise ValueError('both matched lanes required')
  if not all(x.get('exact_count')==13 and x.get('exact') is True for rows in r['lanes'].values() for x in rows):raise ValueError('13/13 exact required')
  if len({x['boot_id'] for rows in r['lanes'].values() for x in rows})!=1:raise ValueError('both lanes must share the same boot')
  a,b=r['best'],r['confirmation'];c=a['choice']
  if c not in VIEWS or c=='control' or c!=b['choice']:raise ValueError('same registered composition required')
  if not all(type(x) in (int,float) and math.isfinite(x) and x>1 for x in (a['ratio'],b['ratio'])):raise ValueError('both lanes must improve')
  # Recompute controls from raw screened rows; reported ratios alone cannot win.
  from compare import compare
  from screen_jobs import ORDER
  for lane,rows in r['lanes'].items():
   order=ORDER if len(rows)==len(ORDER) else ('control',c,'control')
   compare(rows,order)
   matched=[x for x in rows[1:-1] if x['choice']==c]
   if len(matched)!=1 or matched[0]['rate']<=max(rows[0]['rate'],rows[-1]['rate']):raise ValueError('candidate must beat both controls')
  chosen.update(VIEWS[c])
 if screens.get('90',{}).get('status')=='winner':raise ValueError('packet90 slot empty: evidence and composition qualification required')
 return chosen

def apply_pins(choice,values):
 choice=dict(choice);pins={}
 for value in values:
  if value.count('=')!=1:raise ValueError('pin must be key=value')
  k,v=value.split('=')
  if k not in DEFAULTS or k in pins:raise ValueError('unknown or duplicate pin '+k)
  if v!=DEFAULTS[k]:raise ValueError('pins may only revert to default: '+k)
  pins[k]=v;choice[k]=v
 return choice,pins

def close_packets(screens,choice,pins,values):
 dimensions={'91':('route','recurrence'),'90':('expert_hc',)};closed={}
 for value in values:
  if '=' not in value:raise ValueError('closure must be packet=reason')
  n,reason=value.split('=',1)
  if n not in dimensions or n in closed or not reason.strip():raise ValueError('unknown, duplicate or unexplained closure '+n)
  if screens.get(n,{}).get('status')!='pending':raise ValueError('only a pending packet may be closed: '+n)
  if any(pins.get(k)!=DEFAULTS[k] or choice[k]!=DEFAULTS[k] for k in dimensions[n]):raise ValueError('closure requires its dimensions pinned to default: '+n)
  closed[n]=dict(reason=reason,previous_status='pending',dimensions={k:choice[k] for k in dimensions[n]})
  screens[n]=dict(screens[n],status='no-winner',coordinator_closure=closed[n])
 return closed

def command():
 args=['systemd-run','--user','--unit=packet91-chain','--property=Restart=no','--property=Nice=0','--property=CPUAffinity=0-3 16-19','--property=KillMode=process','--property=SendSIGKILL=no','--property=ExitType=cgroup','--property=TimeoutStopSec=infinity','--property=StandardOutput=append:'+str(O/'chain.log'),'--property=StandardError=append:'+str(O/'chain.log'),'--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19','/usr/bin/bash',str(O/'device-entry.sh'),'chain']
 return shlex.join(args)+' </dev/null'
def pin_path(path):
 # Test roots may be outside ROOT; absolute paths retain an exact binding too.
 path=Path(path).resolve()
 return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
def run(name,args):
 with (O/(name+'.log')).open('w') as log:r=subprocess.run([*PREFIX,*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise ValueError(name+' failed; see '+str(O/(name+'.log')))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--snapshot-only',action='store_true');ap.add_argument('--pin',action='append',default=[]);ap.add_argument('--closed',action='append',default=[]);a=ap.parse_args();limits()
 row=dict(schema='packet91.ready.v1',ready=False,device_executed=False,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),chain_command=command())
 try:
  r=subprocess.run([*PREFIX,str(O/'read_screens.py')],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  screens={'91':json.loads(r.stdout),'90':dict(status='no-winner',reason='empty reserved expert/HC slot',receipts={},sources={})}
  row['screens']=screens;save(O/'screens-current.json',screens)
  choice,pins=apply_pins(select(screens),a.pin)
  if pins:row['coordinator_pins']=pins
  closures=close_packets(screens,choice,pins,a.closed)
  if closures:row['coordinator_closures']=closures
  row['selection']=choice
  if a.snapshot_only:raise ValueError('snapshot only; prechecks not run')
  # Reverting part of a measured composition cannot authorize a new unconfirmed
  # composition. Full default reversion is always the control.
  s=screens['91']
  if choice!=DEFAULTS and (s.get('status')!='winner' or choice!=dict(VIEWS[s['best']['choice']],expert_hc='none')):raise ValueError('pinned combination lacks matched confirmation')
  run('reseal',[P/'fast_reseal.py',*[s for k,v in choice.items() if k!='expert_hc' for s in ('--'+k,v)]])
  checks=[('cpu-dry-run',[P/'dry_run.py']),('seal',[P/'chain_seal.py','--verify']),('inputs',[P/'check_inputs.py']),('storage',[P/'storage_precheck.py']),('queue-plan',[P/'queue_runner.py','--plan','--output-root',P/'build/device-cards01-a'])]
  for name,args in checks:run(name,args)
  row['checks']={name:sha(O/(name+'.log')) for name,_ in checks}
  row['pins']={pin_path(f):sha(f) for f in [P/'build-receipt.json',P/'bundle-selection.json',P/'submission-pins.json',P/'shared-wrapper-pin.json',P/'extension-slots.json',P/'evidence/dry-run.json',P/'evidence/selection-dry-run.json',*sorted(O.glob('*.py')),O/'device-entry.sh']}
  row['preparation_passed']=True
  if any(r['status'] not in ('winner','no-winner') for r in screens.values()):raise ValueError('matched packet91 screens pending; CPU preparation passed')
  row['ready']=True
 except (ValueError,OSError,AssertionError,subprocess.SubprocessError) as error:row['reason']=str(error)
 save(O/'ready.json',row);print(json.dumps(dict(ready=row['ready'],reason=row.get('reason'),selection=row.get('selection'),chain_command=row['chain_command']),indent=2))
 return 0 if row['ready'] else 2
if __name__=='__main__':raise SystemExit(main())

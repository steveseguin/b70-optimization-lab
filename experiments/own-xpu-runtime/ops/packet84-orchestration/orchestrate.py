#!/usr/bin/env python3
"""Read both completed screens, seal and check packet84, write command. Never launch."""
import argparse,hashlib,json,os,shlex,subprocess,sys,math,resource
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet84-record-bundle'
PREFIX=['nice','-n','19','taskset','-c','8-15,24-31',sys.executable,'-B']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def select(screens):
    chosen=dict(json.loads((P/'baseline-pins.json').read_text())['selection'])
    for number in ('81','82','83'):
        r=screens.get(number,{})
        # Missing, failed or unfinished evidence is never borrowed from another packet.
        if r.get('status')!='winner':continue
        if set(r.get('lanes',{}))!={'A','B'} or not all(r['lanes'].values()):raise ValueError('both lane grids required')
        if not all(x.get('exact_count')==13 and x.get('exact') is True for rows in r['lanes'].values() for x in rows):raise ValueError('13/13 exact required')
        if not (all(type(x) in (int,float) and math.isfinite(x) and x>1 for x in (r['best']['ratio'],r['confirmation']['ratio'])) and r['best']['choice']==r['confirmation']['choice']):raise ValueError('both lanes must improve')
        c=r['best']['choice']
        key,allowed={'81':('experts',('gate-input-packed','down-input-packed','input-packed')),'82':('recurrence',('rec-gates','rec-parallel')),'83':('draft_head',('q4-g32','prefix990','prefix985'))}[number]
        if c not in allowed:raise ValueError('unknown candidate '+number)
        chosen[key]=c
    return chosen
def apply_pins(choice,values):
    choice=dict(choice);pins={};defaults=dict(dense='production',hc='production',experts='wide64',host='production',route='production',norm='production',placement='1',recurrence='production',draft_head='production')
    for value in values:
        if value.count('=')!=1:raise ValueError('pin must be key=value')
        k,v=value.split('=')
        if k not in choice or k in pins:raise ValueError('unknown or duplicate pin '+k)
        if v not in (choice[k],defaults[k]):raise ValueError('pins may only revert to production/default: '+k)
        pins[k]=v;choice[k]=v
    return choice,pins
def close_packets(screens,choice,pins,values):
    # Coordinator closure of a lever closed elsewhere (DO-NOT-REPEAT): only a pending packet whose
    # dimension is pinned to production/default may be treated as no-winner; never a winner or conflict.
    keys={'81':'experts','82':'recurrence','83':'draft_head'};defaults=dict(experts='wide64',recurrence='production',draft_head='production');closed={}
    for value in values:
        if value.count('=')!=1:raise ValueError('closure must be packet=reason')
        n,reason=value.split('=')
        if n not in keys or n in closed or not reason.strip():raise ValueError('unknown, duplicate or unexplained closure '+n)
        if screens[n].get('status')!='pending':raise ValueError('only a pending packet may be closed: '+n)
        if pins.get(keys[n])!=defaults[keys[n]] or choice[keys[n]]!=defaults[keys[n]]:raise ValueError('closure requires its dimension pinned to default: '+n)
        closed[n]=dict(reason=reason,previous_status='pending',dimension=keys[n],value=choice[keys[n]])
        screens[n]=dict(screens[n],status='no-winner',coordinator_closure=closed[n])
    return closed
def command():
    args=['systemd-run','--user','--unit=packet84-chain','--property=Restart=no',
          '--property=Nice=0','--property=CPUAffinity=0-3 16-19','--property=KillMode=process',
          '--property=SendSIGKILL=no','--property=ExitType=cgroup','--property=TimeoutStopSec=infinity',
          '--property=StandardOutput=append:'+str(O/'chain.log'),
          '--property=StandardError=append:'+str(O/'chain.log'),
          '--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19',
          '/usr/bin/bash',str(O/'device-entry.sh'),'chain']
    return shlex.join(args)+' </dev/null'
def run(name,args):
    with (O/(name+'.log')).open('w') as log:
        r=subprocess.run([*PREFIX,*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    if r.returncode:raise ValueError(name+' failed; see '+str(O/(name+'.log')))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot-only',action='store_true');ap.add_argument('--closed',action='append',default=[],help='coordinator closure packet=reason for a pending packet whose dimension is pinned to default');ap.add_argument('--pin',action='append',default=[],help='coordinator pin key=value applied after evidence selection (subset only: a pinned key may only be set to production/its default)');a=ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    row=dict(schema='packet84.ready.v1',ready=False,device_executed=False,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),chain_command=command())
    try:
        screens={}
        for packet in (81,82,83):
            r=subprocess.run([*PREFIX,str(O/'read_screens.py'),str(packet)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
            screens[str(packet)]=json.loads(r.stdout)
        row['screens']=screens;save(O/'screens-current.json',screens)
        choice,pins=apply_pins(select(screens),a.pin)
        if pins:row['coordinator_pins']=pins
        closures=close_packets(screens,choice,pins,a.closed)
        if closures:row['coordinator_closures']=closures
        row['selection']=choice
        if a.snapshot_only:raise ValueError('snapshot only; prechecks not run')
        run('reseal',[P/'fast_reseal.py',*[s for k,v in choice.items() for s in ('--'+k,v)]])
        checks=[('cpu-dry-run',[P/'dry_run.py']),('seal',[P/'chain_seal.py','--verify']),('inputs',[P/'check_inputs.py']),('storage',[P/'storage_precheck.py']),('queue-plan',[P/'queue_runner.py','--plan','--output-root',P/'build/device-cards01-a'])]
        for name,args in checks:run(name,args)
        row['checks']={name:sha(O/(name+'.log')) for name,_ in checks}
        row['pins']={str(f.relative_to(ROOT)):sha(f) for f in [P/'build-receipt.json',P/'bundle-selection.json',P/'submission-pins.json',P/'shared-wrapper-pin.json',P/'evidence/dry-run.json',P/'evidence/selection-dry-run.json',*sorted(O.glob('*.py')),O/'device-entry.sh']}
        row['preparation_passed']=True
        if any(r['status'] not in ('winner','no-winner') for r in screens.values()):raise ValueError('screen confirmations pending or conflicting; CPU preparation passed')
        row['ready']=True
    except (ValueError,OSError,AssertionError,subprocess.SubprocessError) as error:row['reason']=str(error)
    save(O/'ready.json',row)
    print(json.dumps(dict(ready=row['ready'],reason=row.get('reason'),selection=row.get('selection'),chain_command=row['chain_command']),indent=2))
    return 0 if row['ready'] else 2
if __name__=='__main__':raise SystemExit(main())

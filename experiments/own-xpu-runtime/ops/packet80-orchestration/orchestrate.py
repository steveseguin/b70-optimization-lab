#!/usr/bin/env python3
"""Read both completed screens, seal and check packet80, write command. Never launch."""
import argparse,hashlib,json,os,shlex,subprocess,sys,math,resource
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet80-record-bundle'
PREFIX=['nice','-n','19','taskset','-c','8-15,24-31',sys.executable,'-B']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def select(screens):
    chosen=dict(dense='production',hc='production',experts='wide64',host='production',route='production',norm='production',placement='1')
    for number in ('73','76','78','79'):
        r=screens.get(number,{})
        # Missing, failed or unfinished evidence is never borrowed from another packet.
        if r.get('status')!='winner':continue
        if set(r.get('lanes',{}))!={'A','B'} or not all(r['lanes'].values()):raise ValueError('both lane grids required')
        if not all(x.get('exact_count')==13 and x.get('exact') is True for rows in r['lanes'].values() for x in rows):raise ValueError('13/13 exact required')
        if not (all(type(x) in (int,float) and math.isfinite(x) and x>1 for x in (r['best']['ratio'],r['confirmation']['ratio'])) and r['best']['choice']==r['confirmation']['choice']):raise ValueError('both lanes must improve')
        c=r['best']['choice']
        if number=='73':
            if c=='hc-wide':chosen['hc']='hc-wide'
            # experts2 arms, including their combined view, are outside this brief.
        elif number=='76':
            if c!='ordered':raise ValueError('unknown host candidate')
            chosen['host']=c
        elif number=='78':
            mapping={'route-fast':('fast','production',None),'norm-fused':('production','fused',None),'small-combined':('fast','fused',None),'small+hc-wide':('fast','fused','hc-wide')}
            if c not in mapping:raise ValueError('unknown small-kernel candidate')
            route,norm,hc=mapping[c];chosen.update(route=route,norm=norm)
            if hc:chosen['hc']=hc
        else:
            if c not in ('0','0-split23'):raise ValueError('unknown placement candidate')
            chosen['placement']=c
    return chosen
def command():
    args=['systemd-run','--user','--unit=packet80-chain','--property=Restart=no',
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
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot-only',action='store_true');a=ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    row=dict(schema='packet80.ready.v1',ready=False,device_executed=False,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),chain_command=command())
    try:
        screens={}
        for packet in (73,74,76,78,79):
            r=subprocess.run([*PREFIX,str(O/'read_screens.py'),str(packet)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
            screens[str(packet)]=json.loads(r.stdout)
        row['screens']=screens;save(O/'screens-current.json',screens)
        choice=select(screens);row['selection']=choice
        if a.snapshot_only:raise ValueError('snapshot only; prechecks not run')
        if choice==dict(dense='production',hc='production',experts='wide64',host='production',route='production',norm='production',placement='1'):raise ValueError('no confirmed change; no record chain proposed')
        run('reseal',[P/'fast_reseal.py',*[s for k,v in choice.items() for s in ('--'+k,v)]])
        checks=[('cpu-dry-run',[P/'dry_run.py','--verify']),('seal',[P/'chain_seal.py','--verify']),('inputs',[P/'check_inputs.py']),('storage',[P/'storage_precheck.py']),('plans',[P/'plan_gate.py']),('queue-plan',[P/'queue_runner.py','--plan','--output-root',P/'build/device-cards01-a'])]
        for name,args in checks:run(name,args)
        row['checks']={name:sha(O/(name+'.log')) for name,_ in checks}
        row['pins']={str(f.relative_to(ROOT)):sha(f) for f in [P/'build-receipt.json',P/'bundle-selection.json',P/'submission-pins.json',P/'shared-wrapper-pin.json',P/'evidence/dry-run.json',*sorted(O.glob('*.py')),O/'device-entry.sh']}
        row['ready']=True
    except (ValueError,OSError,subprocess.SubprocessError) as error:row['reason']=str(error)
    save(O/'ready.json',row)
    print(json.dumps(dict(ready=row['ready'],reason=row.get('reason'),selection=row.get('selection'),chain_command=row['chain_command']),indent=2))
    return 0 if row['ready'] else 2
if __name__=='__main__':raise SystemExit(main())

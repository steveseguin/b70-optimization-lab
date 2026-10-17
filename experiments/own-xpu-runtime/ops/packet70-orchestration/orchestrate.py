"""Packet70 CPU preparation; never launches a chain. Dry mode cannot invoke external programs."""
import argparse
import ast
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = Path('experiments/own-xpu-runtime/stage2')
PACKET = STAGE / 'packet70-record-bundle'
OUT = Path('/home/steve/own-xpu-runtime-results/packet70-record-bundle/build/device-cards01-a')
DRIVER = Path('experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py')
CPU = ['nice', '-n', '19', 'taskset', '-c', '8-15,24-31', 'python3', '-B']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Backend:
    def __init__(self, root, log, mock=None):
        self.root, self.log, self.mock = root, log, mock
        self.tick = 0
        self.launched = {}
        self.patterns = {}
        for node in ast.parse((ROOT / DRIVER).read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                        self.patterns[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
        require(set(self.patterns) == {'FAULT', 'DELETED'}, 'authoritative fault patterns unavailable')
        self.boot = mock['boot_id'] if mock is not None else Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def run(self, command):
        self.log(('MOCK ' if self.mock is not None else '') + 'RUN ' + shlex.join(map(str, command)))
        if self.mock is not None:
            require(not self.mock.get('fail_command') or self.mock['fail_command'] not in ' '.join(map(str, command)),
                    'injected command failure')
            return
        with (HERE / 'orchestrate.log').open('a') as output:
            subprocess.run(command, cwd=self.root, check=True, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)

    def faults(self):
        if self.mock is not None:
            counts = self.mock.get('fault_counts', [2])
            count = counts[min(self.tick, len(counts)-1)]
        else:
            require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot changed')
            result = subprocess.run(['journalctl', '-k', '-b', '--no-pager'], capture_output=True,
                                    text=True, check=True, timeout=15)
            require(result.stdout.strip(), 'kernel journal empty/unavailable')
            count = sum(bool(self.patterns['FAULT'].search(line)) and not self.patterns['DELETED'].search(line)
                        for line in result.stdout.splitlines())
        require(count == 2, f'fault count changed: expected exactly 2, found {count}; no new launches')

    def state(self, unit):
        if self.mock is not None:
            seq = self.mock.get('lane_states', ['active', 'inactive'])
            return dict(LoadState='loaded', ActiveState=seq[min(self.tick, len(seq)-1)],
                        Result='success', ExecMainStatus='0')
        result = subprocess.run(['systemctl', '--user', 'show', unit, '--property=LoadState',
                                 '--property=ActiveState', '--property=Result', '--property=ExecMainStatus'],
                                capture_output=True, text=True, timeout=15)
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        require(props.get('LoadState') in ('loaded', 'not-found') and props.get('ActiveState'),
                f'cannot inspect unit {unit}: rc={result.returncode}')
        return props

    def pause(self):
        self.tick += 1
        if self.mock is None:
            time.sleep(10)


QUICK = STAGE / 'packet65-expert-occupancy/screen/quick'
EXPERTS = ('production', 'wide64', 'wg64', 'wg128', 'prefetch64')
ORDERS = {'A': ('production','wide64','wg64','wg128','prefetch64','production'),
          'B': ('production','prefetch64','wg128','wg64','wide64','production')}


def select(data):
    """All twelve screens exact; strict same-lane wins against BOTH control means."""
    rows = data['lanes']
    errors = dict(data.get('errors', {}))
    controls = {}
    for lane in 'AB':
        lane_rows = rows.get(lane, [])
        if ([r.get('choice') for r in lane_rows] != list(ORDERS[lane])
                or not all(r.get('exact') is True and r.get('exact_count') == 13
                           and type(r.get('rate')) in (int,float)
                           and math.isfinite(r['rate']) and r['rate'] > 0 for r in lane_rows)):
            errors[lane] = 'incomplete, invalid rate, or not all 13/13 exact'
        else:
            controls[lane] = sum(r['rate'] for r in lane_rows if r['choice']=='production')/2
    eligible=[];gains={}
    if not errors:
        for expert in EXPERTS[1:]:
            gains[expert]={lane:next(r['rate'] for r in rows[lane] if r['choice']==expert)/controls[lane]-1 for lane in 'AB'}
            if all(value>0 for value in gains[expert].values()):
                eligible.append((min(gains[expert].values()), -EXPERTS.index(expert), expert))
    return dict(experts=max(eligible)[2] if eligible else 'production',
                all_screens_exact=not errors,errors=errors,controls=controls,gains=gains,
                rule='strictly faster on both lanes versus mean of two same-lane controls; all 12 screens exact 13/13; maximin tie-break',
                diagnostic=True,promotion_eligible=False,evidence=data)


def chain_command():
    args=['systemd-run','--user','--unit=packet70-chain','--property=Restart=no',
          '--property=Nice=0','--property=CPUAffinity=0-3 16-19','--property=KillMode=process',
          '--property=SendSIGKILL=no','--property=ExitType=cgroup','--property=TimeoutStopSec=infinity',
          '--property=StandardOutput=append:'+str(HERE/'chain.log'),
          '--property=StandardError=append:'+str(HERE/'chain.log'),
          '--working-directory='+str(ROOT),'/usr/bin/taskset','-c','0-3,16-19',
          '/usr/bin/bash',str(HERE/'device-entry.sh'),'chain']
    return shlex.join(args)+' </dev/null'


def terminal(state):
    return state['ActiveState'] in ('inactive','failed')


def read_screens(backend):
    if backend.mock is not None:
        return backend.mock['screens']
    # Retain the requested compare.py output, and reuse its exact validation API
    # for machine-readable selection. Neither call writes the frozen packet65 tree.
    with (HERE/'compare.log').open('w') as log:
        subprocess.run(CPU+[str(QUICK/'compare.py')],cwd=ROOT,stdin=subprocess.DEVNULL,
                       stdout=log,stderr=subprocess.STDOUT,check=False)
    result=subprocess.run(CPU+[str(HERE/'read_screens.py')],cwd=ROOT,stdin=subprocess.DEVNULL,
                          capture_output=True,text=True,check=True)
    return json.loads(result.stdout)


def orchestrate(backend, log, wait_seconds=14400):
    start=time.monotonic()
    while True:
        backend.faults()
        chain=backend.state('packet64-chain')
        lanes={lane:backend.state('screen-p65-quick-'+lane) for lane in 'AB'}
        if backend.mock is not None:
            completed=backend.mock.get('screens_complete',True)
        else:
            # Actual names are read from pinned jobs, not guessed. A failed batch
            # is terminal but cannot qualify a new expert choice.
            paths=[]
            for lane in 'AB':
                names=[line.split('|')[0] for line in (ROOT/QUICK/('jobs-'+lane+'.txt')).read_text().splitlines()
                       if line.strip() and not line.startswith('#')]
                paths.append(all((ROOT/STAGE/'packet65-expert-occupancy/screen/evidence'/name/'window.json').exists() for name in names)
                             or lanes[lane]['ActiveState']=='failed')
            completed=all(paths)
        if terminal(chain) and all(terminal(state) for state in lanes.values()) and completed:
            break
        require(time.monotonic()-start<wait_seconds,'screens not finished; readiness remains false')
        log('WAIT packet64 chain and packet65 A/B screens; no launch')
        backend.pause()
    data=read_screens(backend)
    selection=select(data)
    log('SELECTION '+selection['experts']+' all_screens_exact='+str(selection['all_screens_exact']))
    for script,args in [
        ('fast_reseal.py',['--experts',selection['experts']]),
        ('chain_seal.py',['--verify']),
        ('check_inputs.py',['--output-root',str(OUT)]),
        ('storage_precheck.py',[]),('plan_gate.py',[]),
        ('queue_runner.py',['--phase','all','--output-root',str(OUT),'--plan'])]:
        backend.faults();backend.run(CPU+[str(PACKET/script),*args])
    backend.faults()
    ready=dict(schema='packet70.ready.v1',ready=True,device_executed=False,chain_launched=False,
               boot_id=backend.boot,selection=selection,command=chain_command(),
               dry_run=backend.mock is not None,requires_coordinator_launch=True)
    if backend.mock is None:
        ready['build_receipt_sha256']=digest(ROOT/PACKET/'build-receipt.json')
        ready['selection_sha256']=digest(ROOT/PACKET/'selection.json')
        ready['orchestration_sources']={p.name:digest(p) for p in [*HERE.glob('*.py'), *HERE.glob('*.sh')]}
    log('CHAIN COMMAND (PRINT ONLY): '+ready['command'])
    return ready


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run',type=Path,metavar='MOCK_JSON')
    ap.add_argument('--wait-seconds',type=float,default=14400)
    a=ap.parse_args()
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)), 'CPU helper nice/affinity required')
    require(math.isfinite(a.wait_seconds) and a.wait_seconds>0,'invalid deadline')
    target=HERE/('dry-run-ready.json' if a.dry_run else 'ready.json')
    with (HERE/'orchestration.lock').open('a') as lock, (HERE/'orchestrate.log').open('a',buffering=1) as output:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Only the lock owner may revoke or publish readiness.
        target.write_text(json.dumps(dict(ready=False,chain_launched=False,dry_run=bool(a.dry_run),command=chain_command()),indent=2)+'\n')
        def log(message):
            print(message,flush=True);output.write(message+'\n')
        try:
            backend=Backend(ROOT,log,read(a.dry_run) if a.dry_run else None)
            ready=orchestrate(backend,log,a.wait_seconds)
            target.write_text(json.dumps(ready,indent=2)+'\n')
            return 0
        except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
            log('REFUSED: '+str(error));return 1

if __name__=='__main__':raise SystemExit(main())

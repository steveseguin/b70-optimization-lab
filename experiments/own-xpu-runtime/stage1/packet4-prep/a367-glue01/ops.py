#!/usr/bin/env python3
"""Future coordinator actions. Preparation never launches a device job."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import a367_glue01 as c
import resolved_fault as rf
w = c.w

def campaign_path():
    path = Path(os.environ['FN_CAMPAIGN'])
    w.require(path == w.REPO / 'data/2026-10-17-flash-next-a367-glue01-build/campaign.json', 'fixed campaign path required')
    return path

def environment():
    names = ('FN_RECEIPTS', 'FN_OUTPUT', 'FN_UNIT', 'FN_HEALTH', 'FN_OWNER', 'FN_PAYLOAD', 'FN_ARM')
    env = {name: os.environ[name] for name in names}
    w.require(env['FN_ARM'] in c.ARMS, 'arm required')
    plan = w.read(campaign_path())
    w.require(plan['arms'][env['FN_ARM']] == env['FN_OUTPUT'], 'campaign output binding')
    w.require(plan['seal_sha256'] == w.sha(c.SEAL) and plan['preregistration_sha256'] == w.sha(c.REG), 'campaign seal binding')
    return env

def resolution(boot):
    spec = w.read(rf.RESOLUTION)
    return spec if spec['boot_id'] == boot else None

def pending(env):
    template = w.read(c.HERE / 'owner-approval.pending.json')
    w.require(template['glue_memory_exception']['owner_approval_text'] == c.glue_approval_text(), 'stale approval sentence')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return dict(schema='own-xpu-runtime.packet4.owner-window.v1', authorized=False, halt_resolved=False,
        host='steve-b70s', boot_id=boot, issued_unix=0, expires_unix=0, previous_teardown_completed_unix=0,
        preregistration_sha256=w.sha(w.PREREG), purpose='a367-glue01-screen', glue_arm=env['FN_ARM'],
        glue_preregistration_sha256=w.sha(c.REG), glue_seal_sha256=w.sha(c.SEAL), admission_revision_sha256=None,
        health_path=env['FN_HEALTH'], health_sha256=w.sha(env['FN_HEALTH']), payload_sha256=w.sha(env['FN_PAYLOAD']),
        output=env['FN_OUTPUT'], firmware='OBSERVED-FIRMWARE-REQUIRED',
        pci_ids=['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'],
        glue_memory_exception=template['glue_memory_exception'], resolved_fault=resolution(boot),
        campaign_path=str(campaign_path()), campaign_sha256=w.sha(campaign_path()))

def previous_stop(env):
    if env['FN_ARM'] == 'control':
        value = float(os.environ['FN_PREVIOUS_TEARDOWN'])
        w.require(value > 0 and time.time() - value >= c.GAP, 'observed control stop and 305s gap required')
        return value
    plan = w.read(campaign_path())
    root = Path(plan['arms']['control'])
    life = w.read(root / 'glue01-run.json')
    w.require(life.get('passed') is True and life.get('mock') is False and life.get('gap_complete') is True
              and life.get('all_owners_gone') is True and life.get('clean_exit') is True, 'control failed/incomplete')
    w.require(life['identity_sha256'] == w.sha(root / 'identity.json') and life['stop_sha256'] == w.sha(root / 'stop.json'), 'control receipt hashes')
    identity = w.read(root / 'identity.json')
    w.require(identity['campaign_sha256'] == w.sha(campaign_path()) and identity['seal_sha256'] == w.sha(c.SEAL), 'control identity')
    from compare import check_arm
    check_arm(root, 'control')
    stop = w.read(root / 'stop.json')['completed_unix']
    w.require(time.time() >= stop + c.GAP, 'control 305s gap incomplete')
    return stop

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','output','audit','health','pending','fill','check','compare'))
    parser.add_argument('--exclusive', action='store_true')
    parser.add_argument('--halt-resolved', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        path = campaign_path()
        if os.environ['FN_ARM'] == 'control':
            c.verify_seals()
            stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
            plan = {'schema':'a367-glue01-campaign.v1', 'preregistration_sha256':w.sha(c.REG),
                    'seal_sha256':w.sha(c.SEAL), 'arms':{arm:f'/mnt/raid-models/bench-results/a367g-{stamp}-{arm[0]}' for arm in c.ARMS}}
            with path.open('x') as stream:
                json.dump(plan, stream, indent=2); stream.write('\n')
        else:
            w.require(os.environ['FN_ARM'] == 'candidate' and path.is_file(), 'control campaign first')
        return
    if args.action == 'output':
        print(w.read(campaign_path())['arms'][os.environ['FN_ARM']]); return
    env = environment()
    root, receipts = Path(env['FN_OUTPUT']), Path(env['FN_RECEIPTS'])
    if args.action == 'audit':
        reg = c.verify_seals()
        audit = {'exports': c.verify_export()}
        w.verify_environment(c.paths(env['FN_ARM']), c.source_preregistration(reg, env['FN_ARM']), audit, calibration=True)
        audit['passed'] = True
        w.write(receipts / 'environment-preflight.json', audit)
    elif args.action == 'health':
        w.require(args.exclusive and args.halt_resolved, 'coordinator exclusive ownership and resolved halt required')
        previous_stop(env)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        spec = resolution(boot)
        historical = w.read(w.REPO / spec['probe_receipt_path']) if spec else {'fault_lines_earlier_this_boot':0}
        rf.validate_resolution({'resolved_fault':spec}, historical, boot, rf.journal())
        w.verify_fault_latches(c.fault_paths(root), boot, root)
        w.require(not w.conflicts(w.processes()), 'conflicting device owner')
        w.require(not (c.claim_directory() / (env['FN_ARM'] + '.claimed.json')).exists(), 'arm already launched')
        # One health attempt per arm/seal, no retry even if a new campaign is made.
        c.claim_directory().mkdir(parents=True, exist_ok=True)
        with (c.claim_directory() / (env['FN_ARM'] + '.health-claimed.json')).open('x') as stream:
            json.dump({'unix':time.time(), 'output':env['FN_OUTPUT']}, stream)
        command = ['systemd-run','--user','--unit='+env['FN_UNIT']+'-health','--wait','--pipe',
            '--property=Restart=no','--property=KillMode=process','--property=KillSignal=SIGINT',
            '--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=RuntimeMaxSec=infinity',
            '--working-directory='+str(w.REPO),'/usr/bin/nice','-n','19','/usr/bin/taskset','-c',c.CLIENT_CORES,
            '/usr/bin/env','OMP_NUM_THREADS=2','/home/steve/.venvs/vllm-xpu/bin/python3','-B',
            str(w.REPO/'experiments/ltx25-b70/scripts/check-four-card-health.py'),env['FN_HEALTH']]
        with (receipts/'health.log').open('xb') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        health = w.read(env['FN_HEALTH'])
        rf.validate_resolution({'resolved_fault':spec}, health, boot, rf.journal())
        w.verify_health(dict(health, fault_lines_earlier_this_boot=0), boot, time.time())
    elif args.action == 'pending':
        with Path(env['FN_OWNER']).open('x') as stream:
            json.dump(pending(env), stream, indent=2); stream.write('\n')
    elif args.action == 'fill':
        w.require(args.exclusive and args.halt_resolved, 'coordinator must record exclusive ownership and halt resolution')
        owner = w.read(env['FN_OWNER'])
        w.require(owner['authorized'] is False, 'do not renew/rewrite an authorized window')
        owner.update(authorized=True, halt_resolved=True, issued_unix=time.time(),
                     expires_unix=time.time()+3600, previous_teardown_completed_unix=previous_stop(env),
                     firmware=os.environ['FN_FIRMWARE'])
        owner['expires_unix'] = owner['issued_unix'] + 3600
        owner['glue_memory_exception']['approved'] = True
        owner['approval_recorded_by'] = 'coordinator under owner standing instruction in glue01 build brief'
        c.verify_seals()
        c.verify_admission(owner, w.read(env['FN_HEALTH']), owner['boot_id'], time.time(), root,
                w.processes(), c.fault_paths(root), c.snapshot()['mem_available_bytes']//1024, env['FN_ARM'])
        w.write(Path(env['FN_OWNER']), owner)
        print(c.glue_approval_text())
    elif args.action == 'check':
        subprocess.run(['systemctl','--user','show',env['FN_UNIT'],'-p','ActiveState','-p','SubState','-p','Result','-p','ExecMainStatus'],check=True)
        with (receipts/'unit.log').open('w') as log:
            subprocess.run(['journalctl','--user','-u',env['FN_UNIT'],'--no-pager'],stdout=log,check=True)
        life = w.read(root/'glue01-run.json')
        w.require(life['passed'] is True and life['mock'] is False, 'arm did not pass')
        from compare import check_arm
        print(json.dumps(check_arm(root, env['FN_ARM']), indent=2))
    else:
        plan = w.read(campaign_path())
        subprocess.run(['/usr/bin/python3','-B',str(c.HERE/'compare.py'),'--control',plan['arms']['control'],
            '--candidate',plan['arms']['candidate'],'--output',str(campaign_path().parent/'comparison.json')], check=True)

if __name__ == '__main__':
    main()

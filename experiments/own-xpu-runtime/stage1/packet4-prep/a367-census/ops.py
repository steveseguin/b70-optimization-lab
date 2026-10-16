#!/usr/bin/env python3
"""Future coordinator actions; invoke this file so shell argv stays conflict-safe."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import a367_census as c
w = c.w


def environment():
    names = ('FN_RECEIPTS', 'FN_OUTPUT', 'FN_UNIT', 'FN_HEALTH', 'FN_OWNER', 'FN_PAYLOAD', 'FN_ARM')
    values = {name: os.environ[name] for name in names}
    w.require(values['FN_ARM'] in c.ARMS, 'arm required')
    w.require(Path(values['FN_OUTPUT']).is_absolute() and Path(values['FN_OUTPUT']).name.startswith('a367c-'),
              'absolute short census output required')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'health', 'pending', 'check', 'analyze'))
    args = parser.parse_args()
    env = environment()
    root, receipts = Path(env['FN_OUTPUT']), Path(env['FN_RECEIPTS'])
    if args.action == 'audit':
        audit = {}
        reg = c.verify_seals()
        w.verify_environment(c.paths(), reg, audit, calibration=True)
        if env['FN_ARM'] != 'graph-reference':
            c.verify_tracer()
        audit['passed'] = True
        w.write(receipts / 'environment-preflight.json', audit)
    elif args.action == 'health':
        # Future device action, only via the runbook after exclusive owner admission.
        command = ['systemd-run', '--user', '--unit=' + env['FN_UNIT'] + '-health', '--wait', '--pipe',
                   '--property=Restart=no', '--property=KillMode=process', '--property=KillSignal=SIGINT',
                   '--property=SendSIGKILL=no', '--property=TimeoutStopSec=infinity',
                   '--property=RuntimeMaxSec=infinity', '--working-directory=' + str(w.REPO),
                   '/usr/bin/nice', '-n', '19', '/usr/bin/taskset', '-c', c.CLIENT_CORES,
                   '/usr/bin/env', 'OMP_NUM_THREADS=2',
                   '/home/steve/.venvs/vllm-xpu/bin/python3', '-B',
                   str(w.REPO / 'experiments/ltx25-b70/scripts/check-four-card-health.py'), env['FN_HEALTH']]
        with (receipts / 'health.log').open('xb') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
    elif args.action == 'pending':
        pending = w.read(c.HERE / 'owner-approval.pending.json')
        w.require(pending['census_memory_exception']['owner_approval_text'] == c.census_approval_text(),
                  'stale pending sentence')
        owner = dict(schema='own-xpu-runtime.packet4.owner-window.v1', authorized=False,
            halt_resolved=False, host='steve-b70s',
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            issued_unix=0, expires_unix=0, previous_teardown_completed_unix=0,
            preregistration_sha256=w.sha(w.PREREG), purpose='a367-diagnostic-census',
            census_arm=env['FN_ARM'], census_preregistration_sha256=w.sha(c.REG),
            census_seal_sha256=w.sha(c.SEAL), admission_revision_sha256=None,
            health_path=env['FN_HEALTH'], health_sha256=w.sha(env['FN_HEALTH']),
            payload_sha256=w.sha(env['FN_PAYLOAD']), output=str(root),
            firmware='OBSERVED-FIRMWARE-REQUIRED',
            pci_ids=['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'],
            census_memory_exception=pending['census_memory_exception'])
        with Path(env['FN_OWNER']).open('x') as stream:
            json.dump(owner, stream, indent=2); stream.write('\n')
    elif args.action == 'check':
        # No process patterns are placed in a command's argv.
        subprocess.run(['systemctl', '--user', 'show', env['FN_UNIT'], '-p', 'ActiveState', '-p', 'SubState',
                        '-p', 'Result', '-p', 'ExecMainStatus'], check=True)
        with (receipts / 'unit.log').open('w') as log:
            subprocess.run(['journalctl', '--user', '-u', env['FN_UNIT'], '--no-pager'], stdout=log, check=True)
        for name in ('census-run.json', 'comparison.json', 'write-budget.json'):
            path = root / name
            print(name + ': ' + (path.read_text() if path.exists() else 'pending'))
    else:
        # Analyzer and builder enforce clean exit/watch; never parse bulky JSON beside the server.
        for script, flags in [
            ('build_manifest.py', ['--run-dir', str(root), '--arm', env['FN_ARM'], '--output', str(root / 'census-map.json')]),
            ('analyze_census.py', ['--manifest', str(root / 'census-map.json'), '--out-dir', str(root)]),
        ]:
            subprocess.run(['/usr/bin/nice', '-n', '19', '/usr/bin/taskset', '-c', c.CLIENT_CORES,
                            sys.executable, '-B', str(c.HERE / script)] + flags, check=True)


if __name__ == '__main__':
    main()

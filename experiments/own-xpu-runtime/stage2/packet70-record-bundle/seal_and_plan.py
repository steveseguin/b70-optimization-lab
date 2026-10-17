#!/usr/bin/env python3
"""Seal CPU evidence, bind the inherited chain, and plan both v3 lanes only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
BASE = P.parent / 'packet61-spin-hcfusion'
WAIT = P.parent / 'packet56x-wait'
V = P.parent / 'screen/v3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, row):
    path.write_text(json.dumps(row, indent=2) + '\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert not (P / 'screen-seal.json').exists(), 'never overwrite a sealed packet'
    # Recheck every source in the retained source audit and every inherited
    # object against packet61's link command, before sealing the claim.
    audit = json.loads((P / 'evidence/source-identity.json').read_text())
    for leaf, digest in audit['unchanged_packet61_sources'].items():
        assert sha(BASE / leaf) == sha(P / leaf) == digest, leaf
    for leaf, digest in audit['wait_sources'].items():
        assert sha(WAIT / leaf) == sha(P / leaf) == digest, leaf
    old = json.loads((BASE / 'engine-commands.json').read_text())
    new = json.loads((P / 'engine-commands.json').read_text())
    inherited = []
    for mode in ('gnu-host', 'device'):
        old_args = next(x['command'] for x in old if x['name'] == mode + '-link')
        new_args = next(x['command'] for x in new if x['name'] == mode + '-link')
        old_objects = [Path(x) for x in old_args if x.endswith('.o')]
        new_objects = [Path(x) for x in new_args if x.endswith('.o')]
        assert len(new_objects) == len(old_objects) + 1
        for a, b in zip(old_objects, new_objects):
            if a in (BASE / 'build' / mode / 'entry-main.o', BASE / 'build' / mode / 'single_device.o'):
                continue
            assert sha(a) == sha(b), str(a)
            assert a.stat().st_ino == b.stat().st_ino and a.stat().st_dev == b.stat().st_dev
            inherited.append(dict(parent=str(a.relative_to(ROOT)), current=str(b.relative_to(ROOT)), sha256=sha(a)))
    save(P / 'evidence/object-identity.json', dict(passed=True, device_executed=False, objects=inherited,
         rebuilt_host_objects=['entry-main.o', 'single_device.o', 'host_wait_mode.o'],
         kernel_objects='All packet61 kernel objects retained as identical hardlinks'))
    fixture_path = P / 'integrated-fixture/receipt.json'
    fixture = json.loads(fixture_path.read_text())
    fixture['changed_class'] = 'Packet56x(a) mailbox/device/progress waits; packet61 HC unchanged; packet56 target fixtures exact'
    for path in (Path(__file__).resolve(), P / 'evidence/source-identity.json', P / 'evidence/object-identity.json'):
        fixture['sources'][str(path.relative_to(ROOT))] = sha(path)
    save(fixture_path, fixture)

    def run(args, log=None):
        command = [sys.executable, '-B', *map(str, args)]
        if log:
            with (P / 'evidence' / log).open('x') as output:
                subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        else:
            subprocess.run(command, cwd=ROOT, check=True)

    run([P.parent / 'screen/seal.py', '--profile', 'tp2', '--lineage', P,
         '--build-receipt', P / 'build-device-receipt.json', '--fixture', fixture_path,
         '--binary', P / 'build/device/own-rt-iq3', '--dispatch', P / 'dispatch-speed6.json',
         '--output', P / 'screen-seal.json'])
    for lane in ('A', 'B'):
        run([V / 'screen.py', '--profile', 'tp2', '--lane', lane, '--lineage', P,
             '--seal', P / 'screen-seal.json', '--binary', P / 'build/device/own-rt-iq3',
             '--dispatch', P / 'dispatch-speed6.json', '--output', V / 'evidence' / ('packet61x-' + lane + '-01'),
             '--plan'], 'screen-v3-plan-' + lane + '.json')
    binding = json.loads((BASE / 'chain-binding.json').read_text())
    binding.update(screen_seal_sha256=sha(P / 'screen-seal.json'),
                   packet61_parent_seal_sha256=sha(BASE / 'screen-seal.json'),
                   wait_parent_seal_sha256=sha(WAIT / 'screen-seal-spin.json'))
    save(P / 'chain-binding.json', binding)
    run([P / 'prepare_chain.py'], 'prepare-chain.json')
    run([P / 'chain_seal.py'], 'chain-seal.json')
    run([P / 'chain_seal.py', '--verify'], 'chain-seal-verify.json')
    run([P / 'plan_gate.py', '--output', P / 'evidence/chain-plan.json'], 'chain-plan-summary.json')
    run([P / 'queue_runner.py', '--phase', 'all', '--output-root',
         '/home/steve/own-xpu-runtime-results/packet61x-spin-hcfusion-wait/build/device-cards01-a',
         '--plan'], 'queue-plan.json')
    print('Both v3 lane plans and full-chain CPU admission PASS; no GPU launched')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Derive a PROPOSAL from completed A367 samples; never approve or edit admission."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import a367_calibrate_load as c

w = c.w
RESERVE_KIB = 12_000_000
FIXTURE_KIB = 8 * 1024**2


def derive(run):
    receipt = w.read(run / 'calibration.json')
    identity = w.read(run / 'identity.json')
    w.require(receipt.get('schema') == 'own-xpu-runtime.packet4.a367-calibration.v1', 'not an A367 calibration receipt')
    w.require(receipt.get('passed') is True and receipt.get('mock') is False
              and receipt.get('failure') is None and receipt.get('generation_requests') == 0
              and all(receipt.get(k) is True for k in ('ready', 'clean_exit', 'gap_complete')), 'incomplete/failed/mock calibration')
    w.require(identity.get('schema') == 'own-xpu-runtime.packet4.a367-calibration-identity.v1'
              and identity.get('recipe') == 'A367' and identity.get('mock') is False, 'not certified A367 identity')
    w.require(identity['preregistration_sha256'] == w.sha(c.REG) and identity['seal_sha256'] == w.sha(c.SEAL), 'calibration identity drift')
    command, env = c.command_and_environment(run.resolve())
    w.require(identity['command'] == command and identity['environment'] == env
              and identity['identity_deltas'] == w.read(c.REG)['identity_deltas'], 'runtime command/environment/deltas differ')
    for name, field in [('samples.jsonl', 'samples_sha256'), ('identity.json', 'identity_sha256'), ('stop.json', 'stop_sha256')]:
        w.require(w.sha(run / name) == receipt[field], 'receipt hash differs: ' + name)
    for name, field in [('environment.json', 'audit_sha256'), ('owner-window.json', 'owner_sha256'), ('payload.json', 'payload_sha256')]:
        w.require(w.sha(run / name) == identity[field], 'identity hash differs: ' + name)
    w.require(w.read(run / 'environment.json').get('passed') is True, 'environment audit failed')
    owner = w.read(run / 'owner-window.json')
    w.require(identity.get('calibration_memory_exception') == owner.get('calibration_memory_exception')
              and identity.get('minimum_mem_available_kib') == c.calibration_floor(owner),
              'calibration admission delta differs')
    w.require(not any((run / name).exists() for name in ('FAULT.json', 'STOP.json', 'teardown-incomplete.json', 'scratch-retained.json')), 'failed run latch')
    stop = w.read(run / 'stop.json')
    w.require(stop['all_owners_gone'] is True and stop['returncode'] == 0
              and stop['next_launch_not_before_unix'] - stop['completed_unix'] >= c.GAP, 'incomplete stop receipt')
    samples = [json.loads(line) for line in (run / 'samples.jsonl').read_text().splitlines()]
    summary = c.summarize(samples)
    w.require(summary == receipt['summary'], 'summary does not recompute')
    floor = summary['observed_need_kib'] + RESERVE_KIB + FIXTURE_KIB
    return {'schema': 'own-xpu-runtime.packet4.a367-derived-floor.v1', 'approved': False,
            'calibration': w.artifact(run / 'calibration.json'), 'identity': w.artifact(run / 'identity.json'),
            'samples': w.artifact(run / 'samples.jsonl'), 'host': identity['host'], 'boot_id': identity['boot_id'],
            'summary': summary, 'need_kib': summary['observed_need_kib'], 'reserve_kib': RESERVE_KIB,
            'fixture_allowance_kib': FIXTURE_KIB, 'proposed_minimum_mem_available_kib': floor,
            'delta_from_a367_kib': floor - 120_000_000,
            'sampling_interval_seconds': c.INTERVAL, 'generation_demand_measured': False,
            'scope': 'sampled load/ready/shutdown need plus existing reserve and planned fixture allowance; not a guaranteed serving peak'}


def write_proposal(result, output):
    w.require(not output.exists(), 'proposal output exists')
    original = w.REVISION_DOC.read_text()
    w.require(len(re.findall(r'^proposed_minimum_mem_available_kib: [0-9]+$', original, re.M)) == 1, 'expected one existing proposal')
    floor = result['proposed_minimum_mem_available_kib']
    # Preserve the old document as explicitly superseded history. No canonical edit.
    history = re.sub(r'^proposed_minimum_mem_available_kib:', 'historical_proposed_minimum_mem_available_kib:', original, flags=re.M)
    proposed = (f'# A367 matched-load admission proposal — owner review pending\n\n'
        f'This section supersedes the historical proposal below only after review and\n'
        f'installation of this exact document at packet4-prep/MEMORY-ADMISSION-REVISION.md.\n'
        f'No approval or fixture launch is implied. Attempt 8 remains unmatched.\n\n'
        f'Calibration: `{result["calibration"]["path"]}`\n'
        f'SHA256: `{result["calibration"]["sha256"]}`\n'
        f'Samples SHA256: `{result["samples"]["sha256"]}`\n\n'
        f'Observed availability decline (ceil to KiB): {result["need_kib"]}\n'
        f'+ existing A367 reserve: {RESERVE_KIB} KiB\n'
        f'+ fixture allowance (4 × 2 GiB): {FIXTURE_KIB} KiB\n'
        f'= proposed floor: {floor} KiB ({floor * 1024} bytes).\n\n'
        f'```text\nproposed_minimum_mem_available_kib: {floor}\n```\n\n'
        f'This measures startup, 20 seconds ready and shutdown, with no generated\n'
        f'answers or fixtures. The reserve and fixture allowance are budgets, not\n'
        f'measurements. No counters are added to the whole-host decline. Peaks\n'
        f'between 0.5-second samples remain unknown. Review any calibration-only\n'
        f'admission exception, OMP=2, host state, and all recorded identity deltas.\n'
        f'Capacity, halt, health and owner-window gates remain required.\n\n'
        f'## Superseded historical document (retained)\n\n' + history)
    digest = hashlib.sha256(proposed.encode()).hexdigest()
    output.mkdir()
    (output / 'MEMORY-ADMISSION-REVISION.proposed.md').write_text(proposed)
    w.write(output / 'derivation.json', result)
    pending = {'schema': 'own-xpu-runtime.packet4.admission-revision.v1',
               'approved': False, 'approved_by': 'owner', 'owner_approval_text': '',
               'revision_document_sha256': digest, 'minimum_mem_available_kib': floor,
               'host': result['host'], 'boot_id': result['boot_id']}
    w.write(output / 'admission-revision.pending.json', pending)
    (output / 'owner-approval-sentence.txt').write_text(w.approval_text(floor, digest) + '\n')
    return digest


def main(argv=None):
    import os
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(argv)
    w.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2', 'nice19 OMP2 required')
    c.verify_seals()
    result = derive(a.run.resolve())
    digest = write_proposal(result, a.output)
    print(json.dumps({'proposed_floor_kib': result['proposed_minimum_mem_available_kib'],
                      'proposed_document_sha256': digest, 'approved': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        sys.exit(2)

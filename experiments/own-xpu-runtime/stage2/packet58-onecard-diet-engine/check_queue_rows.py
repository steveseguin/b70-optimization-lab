#!/usr/bin/env python3
"""Packet58-onecard-diet-engine queue-row checks AFTER the seal (plan after seal). CPU only; never a live queue.

1. refuse unless the seal verifies, evidence/package-rows.json matches it, and READY is absent;
2. device-path imports in the closed launch environment -> evidence/entry-imports.json;
3. temporary lanequeue plan of the proposal (plan_queue.py) -> evidence/queue-plans.json;
4. shared ops/rehearse_entry.py --report -> evidence/shared-entry-report(-final).json;
5. real pin guard (pin_guard.check_job) on the job -> evidence/pin-guard.json.
"""
import json, os, subprocess, sys
from pathlib import Path
from build_engine import P, ROOT, sha, save, limits

OPS = P.parents[1] / 'ops'; LQ = OPS / 'lane-queue'
PROPOSAL = LQ / 'proposed-p58-dietengine-one-card-A.txt'
JOB = 'packet58dietengine-one-card-v5-A'
LDP = json.loads((P / 'library-path.json').read_text())['LD_LIBRARY_PATH']


def job():
    rows = [json.loads(s) for s in PROPOSAL.read_text().splitlines() if s.strip() and not s.startswith('#')]
    assert len(rows) == 1 and rows[0]['name'] == JOB and rows[0]['lane'] == 'A'
    return rows[0]


def preconditions():
    assert not (P / 'READY-FOR-DEVICE.json').exists(), 'READY exists'
    cp = subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'], cwd=P, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert cp.returncode == 0, 'seal does not verify: ' + cp.stderr[-800:]
    pkg = json.loads((P / 'evidence/package-rows.json').read_text())
    assert pkg['seal']['sha256'] == sha(P / 'screen/build-receipt.json'), 'seal changed after package_rows'
    assert pkg['proposal']['sha256'] == sha(PROPOSAL), 'proposal changed after package_rows'


def imports():
    code = ('import sys;sys.path.insert(0,%r);import queue_runner,window,suite_driver,mechanism,compare_bracket,views,fault_review,live_check;'
            'import json;print(json.dumps(dict(modules=sorted(m for m in sys.modules if m in ("queue_runner","window","suite_driver","mechanism","compare_bracket","views","fault_review","live_check")))))') % str(P / 'screen')
    cp = subprocess.run(['/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'OMP_NUM_THREADS=2', 'LD_LIBRARY_PATH=' + LDP, '/usr/bin/python3', '-B', '-c', code],
                        cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, cp.stderr[-2000:]
    mods = json.loads(cp.stdout.splitlines()[-1])['modules']; assert len(mods) == 8, mods
    save(P / 'evidence/entry-imports.json', dict(passed=True, device_executed=False, environment='env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH=<library-path.json>',
                                                cwd='repository root', python='/usr/bin/python3 -B', modules=mods, model_reads=False))


def plan():
    cp = subprocess.run([sys.executable, '-B', str(P / 'plan_queue.py')], cwd=P, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
    assert cp.returncode == 0, cp.stdout[-2000:] + cp.stderr[-2000:]
    rows = json.loads((P / 'evidence/queue-plans.json').read_text())['records'][0]['plan']
    assert rows[0]['plan'] == 'passed' and rows[0]['storage_admission']['passed']


def report():
    cmd = [sys.executable, '-B', str(OPS / 'rehearse_entry.py'), str(PROPOSAL), '--report', '--json']
    cp = subprocess.run(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
    try:
        row = json.loads(cp.stdout)
    except ValueError:
        row = dict(passed=False, raw_stdout=cp.stdout[-4000:])
    save(P / 'evidence/shared-entry-report.json', dict(row, returncode=cp.returncode, stderr_tail=cp.stderr[-2000:]))
    jobrow = (row.get('jobs') or [{}])[0]; limits_ = []
    ok = cp.returncode == 0 and row.get('passed') is True
    if ok:
        assert all(b['passed'] for b in jobrow['binaries']) and jobrow['report']['passed'] and jobrow['shared_environment_matches']
        assert jobrow['storage_floor']['passed'] and jobrow['wall_deadlines']['passed'] and jobrow['gate_identity']['status'] != 'FAIL'
        limits_.append('Shared --report passes. Its generic report rehearsal is synthetic only; no separate smoke row exists.')
    if 'preparation_path' in jobrow and jobrow['preparation_path'].get('status') != 'PASS':
        limits_.append('Shared preparation adapter has no unranked one-card CPU transport probe. preparation_dietengine.py ran the real WSCREEN argv '
                       'with the max23/max23+diet bracket through the device-define CPU probe under Landlock (evidence/preparation.json); synthetic transport/weights, no GPU.')
    save(P / 'evidence/shared-entry-report-final.json', dict(passed=ok, device_executed=False, proposal=str(PROPOSAL.relative_to(ROOT)), proposal_sha256=sha(PROPOSAL),
                                                              returncode=cp.returncode, shared_report='evidence/shared-entry-report.json',
                                                              shared_tool_limitations=limits_, jobs=row.get('jobs')))
    assert ok, 'shared rehearse_entry --report failed; see evidence/shared-entry-report.json'


def pins():
    sys.path.insert(0, str(LQ)); import pin_guard
    result = pin_guard.check_job(job(), pin_guard.ROOT, pin_guard.STAGE)
    save(P / 'evidence/pin-guard.json', dict(passed=True, device_executed=False, shared_pin_guard='ops/lane-queue/pin_guard.check_job passed on ' + JOB,
                                            pins=result['pins'], manifests=result['manifests'], model_hashes_deferred=result['model_hashes_deferred'],
                                            phase='after seal, before READY (final_checks.py --ready repeats it on the READY closure)'))


if __name__ == '__main__':
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    limits(); preconditions()
    for name, fn in (('imports', imports), ('plan', plan), ('report', report), ('pins', pins)):
        fn(); print('PASS', name, flush=True)

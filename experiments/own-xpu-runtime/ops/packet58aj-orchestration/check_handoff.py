"""Read-only admission checks, with a local summary for the final marker."""
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

O = Path(__file__).resolve().parent
R = O.parents[3]
P = R / 'experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'


def read(p):
    return json.loads(p.read_text())


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000
    subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'], check=True, stdin=subprocess.DEVNULL)
    assert read(O / 'resume-frozen-audit.json')['passed']
    assert read(P / 'evidence/python-cpu-gates.json')['tests'] == 134
    assert read(P / 'screen/evidence/python-cpu-gates.json')['checks'] == 103
    assert read(P / 'evidence/argument-gate.json')['checks'] == 7
    assert len(read(P / 'evidence/argument-gate.json')['negative_records']) == 28
    assert read(P / 'screen/evidence/argument-gate.json')['checks'] == 6
    rehearsal = read(P / 'evidence/submission-rehearsal.json')
    assert rehearsal['passed'] and rehearsal['final_location_cli_passed'] and not rehearsal['network_used']
    assert not rehearsal['cli_root_overridden'] and not rehearsal['new_chain_measurement']
    loader = (O / 'loader-check.log').read_text().splitlines()
    assert len(loader) == 2 and all(s.startswith('PASS ') for s in loader)
    sys.path.insert(0, str(R / 'experiments/own-xpu-runtime/ops/lane-queue'))
    import pin_guard
    pins = []
    for tag in ('smoke', 'v5'):
        proposal = R / 'experiments/own-xpu-runtime/ops/lane-queue' / f'proposed-p58aj-{tag}-A.txt'
        assert proposal.read_bytes() == (P / 'screen/proposals' / proposal.name).read_bytes()
        job = json.loads(next(s for s in proposal.read_text().splitlines() if s.startswith('{')))
        sizes=read(P / 'payload-sizes.json')['records']
        assert job['planned_write_bytes'] <= 3*sum(sizes[k]['measured_bytes'] for k in ('K1a','K1b',tag))
        saved=next(r for r in read(P / 'evidence/queue-plans.json')['records'] if r['proposal'].endswith(proposal.name))
        assert saved['plan'][0]['storage_admission']['planned_write_bytes']==job['planned_write_bytes']
        pins.append(pin_guard.check_job(job))
        entry = read(P / 'screen/evidence' / f'ops-entry-report-{tag}.json')
        assert entry['passed'] and entry['jobs'][0]['report']['passed']
        declared = next(r for r in read(P / 'screen/evidence/entry-gates.json')['records'] if r['proposal'].endswith(proposal.name))
        assert declared['proposal_sha256'] == sha(proposal)
    assert read(P / 'evidence/queue-plans.json')['passed']
    assert read(P / 'evidence/plan-check.json')['passed']
    ready = read(P / 'ready.json')
    assert not ready['ready'] and 'smoke/v5 pending' in ready['reason']
    timeouts = []
    for f in [*P.glob('*.py'), *(P / 'screen').glob('*.py')]:
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Call) and any(k.arg == 'timeout' for k in n.keywords):
                timeouts.append(str(f.relative_to(R)) + ':' + str(n.lineno))
    assert not timeouts, timeouts
    assert not (P / 'evidence/card0-58aj-a').exists()
    assert not (P / 'screen/evidence/card0-58aj-screen-a').exists()
    row = dict(passed=True, device_executed=False, python_tests=237, fresh_passive_tests=236, retained_native_parser_tests=1,
        real_intercepted_entries=13, chain_wrong_unit_environment_refusals=28,
        pin_admission=pins, shared_entry_report_passed=True, shared_loader_passed=True,
        submission_rehearsal_passed=True, chain_refuses_pending_device_gates=True,
        wall_clock_subprocess_timeouts=timeouts, root_free_bytes=shutil.disk_usage('/').free,
        build_bytes=read(P / 'build-receipt.json')['retained_build_bytes'],
        whole_host_device_work_performed=False, queued=False,
        notes='Retained GNU/Intel exactness and unchanged native builds; refreshed affected Python checks. New device parity and warm neutrality remain pending.')
    (O / 'final-checks.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(row))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    main()

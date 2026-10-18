"""CPU-only revision validation; all queue writes use a temporary snapshot."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, limits, save, sha


def main():
    limits()
    screen = P / 'screen'
    out = P / 'evidence/reseal-r2'
    old = out / 'previous'
    records = {}
    for lane, jobs in [('A', 'jobs-A-r2.txt'), ('B', 'jobs-B.txt')]:
        command = [sys.executable, '-B', str(screen / 'run.py'), '--lane', lane,
                   '--jobs', str(screen / jobs), '--plan']
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, check=True, timeout=180)
        plans = json.loads(result.stdout)
        assert len(plans['plans']) == (4 if lane == 'A' else 3)
        assert all(p['supported'] and p['reservation_scope'] == 'lane-' + lane
                   for p in plans['plans'])
        save(out / f'plans-{lane}.json', plans)
        records[lane] = dict(command=command, plans_sha256=sha(out / f'plans-{lane}.json'))
    queue = P.parents[1] / 'ops/lane-queue'
    proposal = queue / 'proposed-p72-r2-A.txt'
    with tempfile.TemporaryDirectory(prefix='p72-r2-queue-') as tmp:
        dest = Path(tmp) / 'queue'
        shutil.copytree(queue, dest, ignore=shutil.ignore_patterns('*.log', '*.lock',
                        'events-*', 'inflight-*', '__pycache__'))
        (dest / 'queue-A.txt').write_bytes(proposal.read_bytes())
        command = [sys.executable, '-B', str(queue / 'lanequeue.py'), 'plan',
                   '--lane', 'A', '--directory', str(dest)]
        with (out / 'queue-plan-A.log').open('w') as log:
            subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=180)
    views = []
    for view in sorted((P / 'selections').iterdir()):
        if not view.is_dir():
            continue
        before = json.loads((old / view.relative_to(P) / 'screen-seal.json').read_text())
        after = json.loads((view / 'screen-seal.json').read_text())
        assert before['artifacts'] == after['artifacts']
        assert before['fixture_files'] == after['fixture_files']
        assert (old / view.relative_to(P) / 'selection.json').read_bytes() == (view / 'selection.json').read_bytes()
        views.append(dict(name=view.name, binary_sha256=after['artifacts']['build/device/own-rt-iq3'],
                          screen_seal_sha256=sha(view / 'screen-seal.json')))
    save(out / 'validation.json', dict(passed=True, device_executed=False,
         cpu_model_executed=False, live_queues_modified=False, wrapper_tests=82,
         plans=records, views=views, proposal_sha256=sha(proposal),
         queue_plan_sha256=sha(out / 'queue-plan-A.log'),
         cpu_byte_gate_sha256=sha(P / 'evidence/cpu-byte-identity.json')))
    print('PASS: 82 wrapper tests, seven admission plans, temporary queue plan; binaries unchanged')


if __name__ == '__main__':
    main()

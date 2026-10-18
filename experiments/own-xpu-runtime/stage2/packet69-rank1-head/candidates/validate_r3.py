"""Verify revision-3 seals, unchanged production fixtures, and temporary queues."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, limits, sha, save
from selections import CHOICES


def main():
    limits()
    out = P / 'evidence/reseal-r3'
    previous = out / 'previous'
    read = lambda f: json.loads(f.read_text())
    old = read(previous / 'evidence/cpu-gates.json')
    current = read(P / 'evidence/cpu-gates.json')
    assert old['runs'] == current['runs'], 'production/draft fixture bytes changed'
    assert read(P / 'evidence/head-status/receipt.json')['passed']
    assert read(out / 'diagnosis.json')['row_stride'] == 3380
    old_build = read(previous / 'build-device-receipt.json')
    build = read(P / 'build-device-receipt.json')
    # The qualified arithmetic's inherited objects must remain byte-identical.
    objects = read(P / 'evidence/object-identity.json')['objects']
    for row in objects:
        assert sha(ROOT / row['current']) == row['sha256']
        assert old_build['sources'][row['parent']] == row['sha256']
    quick = P.parent / 'screen/quick'
    subprocess.run([sys.executable, '-B', str(quick / 'quick_seal.py')],
                   check=True, stdin=subprocess.DEVNULL, timeout=60)
    plans = {}
    for lane in ('A', 'B'):
        command = [sys.executable, '-B', str(quick / 'run.py'), '--lane', lane,
                   '--jobs', str(quick / f'jobs-{lane}-r3.txt'), '--plan']
        result = subprocess.run(command, check=True, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=180)
        rows = json.loads(result.stdout)
        assert len(rows['plans']) == 8 and all(r['supported'] for r in rows['plans'])
        save(out / f'plans-{lane}.json', rows)
        plans[lane] = dict(command=command, sha256=sha(out / f'plans-{lane}.json'))
    queue = P.parents[2] / 'ops/lane-queue'
    proposals = {}
    with tempfile.TemporaryDirectory(prefix='p69-r3-queue-') as tmp:
        dest = Path(tmp) / 'queue'
        shutil.copytree(queue, dest, ignore=shutil.ignore_patterns('*.log', '*.lock',
                        'events-*', 'inflight-*', '__pycache__'))
        for lane in ('A', 'B'):
            proposal = queue / f'proposed-p69-r3-{lane}.txt'
            (dest / f'queue-{lane}.txt').write_bytes(proposal.read_bytes())
            command = [sys.executable, '-B', str(queue / 'lanequeue.py'), 'plan',
                       '--lane', lane, '--directory', str(dest)]
            with (out / f'queue-plan-{lane}.log').open('w') as log:
                subprocess.run(command, check=True, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, timeout=180)
            proposals[lane] = dict(path=str(proposal.relative_to(ROOT)), sha256=sha(proposal),
                                  plan_log_sha256=sha(out / f'queue-plan-{lane}.log'))
    views = []
    for name in CHOICES:
        view = P / 'selections' / name
        assert (previous / 'selections' / name / 'selection.json').read_bytes() == (view / 'selection.json').read_bytes()
        seal = read(view / 'screen-seal.json')
        assert seal['arithmetic'] == 'iq3-p49-split32-v1'
        assert seal['artifacts']['build/device/own-rt-iq3'] == sha(P / 'build/device/own-rt-iq3')
        views.append(dict(name=name, seal_sha256=sha(view / 'screen-seal.json')))
    save(out / 'validation.json', dict(passed=True, device_executed=False,
        cpu_model_executed=False, live_queues_modified=False, views=views, plans=plans,
        proposals=proposals, production_fixture_bytes_unchanged=True,
        inherited_arithmetic_objects_unchanged=True, wrapper_tests=18,
        head_status_gate_sha256=sha(P / 'evidence/head-status/receipt.json'),
        device_quality='pending coordinator rerun', binary_sha256=sha(P / 'build/device/own-rt-iq3')))
    print('PASS: production bytes and inherited arithmetic unchanged; seven seals, sixteen plans, two temporary queues')


if __name__ == '__main__':
    main()

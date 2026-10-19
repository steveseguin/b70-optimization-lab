"""Validate the minimal delta and all gates, then write READY markers last."""
import time
from pathlib import Path

from check_launch import HERE, ROOT, OPS, read, save, sha
from build_engine import limits

limits()
launch = read(HERE / 'evidence/launch-checks.json')
native = read(HERE / 'evidence/native-sensors.json')
proposals = read(HERE / 'evidence/proposal-checks.json')
assert all(r['passed'] and not r['device_executed'] for r in (launch, native, proposals))
assert len(launch['results']) == len(native['results']) == len(proposals['checks']) == 4
for row in native['results']:
    assert row['passed'] and row['reset_count'] == 14 and len(row['sensor_checks']) == 56
    assert row['peak_rss_bytes'] < 4_000_000_000
assert native['build_bytes'] < 300_000_000
for path, digest in native['source_sha256'].items():
    assert sha(ROOT / path) == digest, path
for row in proposals['checks']:
    assert sha(ROOT / row['path']) == row['sha256']
    assert sha(ROOT / row['proposal']) == row['proposal_sha256']
pending = []
for number, folder in ((163, 'packet163-full-gate'), (165, 'packet165-warm-prefill')):
    packet = HERE.parent / folder
    child = packet / 'one-card'
    previous = HERE / 'lineage' / str(number)
    assert (child / 'worker.py').read_text() == (previous / 'worker.py').read_text().replace(
        ' return cmd\n', " return ['/usr/bin/ionice','-c3',*cmd]\n")
    seal = read(child / 'seal.json')
    original_seal = read(previous / 'seal.json')
    assert set(seal['files']) == set(original_seal['files'])
    assert [key for key in seal['files'] if seal['files'][key] != original_seal['files'][key]] == ['worker.py']
    for path, digest in seal['files'].items():
        assert sha(child / path) == digest, path
    proposal = OPS / 'lane-queue' / f'proposed-p{number}-one-card-A.txt'
    jobs = [row for row in launch['results'] if row['job'].startswith(f'packet{number}-')]
    assert len(jobs) == 2
    for job in jobs:
        assert job['proposal_sha256'] == sha(proposal)
        assert job['worker_sha256'] == sha(child / 'worker.py')
        assert job['launch']['priority']['io_class'] == 3
        assert job['launch']['missing_wrapper_refused']
        assert job['stream_checks'] == 26 and not job['device_executed']
    ready = read(child / 'READY-FOR-DEVICE.json')
    # Replace superseded row/import/orchestration gate references; preserve
    # original receipts byte-for-byte in their existing evidence locations.
    for key in list(ready['checks']):
        if key in ('evidence/flags.json', 'evidence/device-path-imports.json',
                   'evidence/real-arm-sequence.json', 'shared-report-A', 'lanequeue-plan-A') or 'packet165b/' in key or 'packet165c-ionice/' in key:
            del ready['checks'][key]
    for leaf in ('launch-checks.json', 'native-sensors.json', 'proposal-checks.json'):
        path = HERE / 'evidence' / leaf
        # Local immutable gate snapshots keep the current launch closure
        # private. The repair packet retains runnable tests and source pins.
        retained = child / 'lineage/packet165c' / leaf
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(path.read_bytes())
        ready['checks'][str(retained.relative_to(child))] = sha(retained)
    ready['checks']['seal.json'] = sha(child / 'seal.json')
    ready.update(ready=True, ready_for_device=True, seal_sha256=sha(child / 'seal.json'),
        created_utc_ns=time.time_ns(), preparation='packet165c CPU gates passed',
        native_io_class='idle (ionice -c3)', proposal_sha256=sha(proposal))
    for path, digest in ready['checks'].items():
        target = ROOT / path if path.startswith('experiments/') else child / path
        assert sha(target) == digest, path
    root_ready = read(packet / 'READY-FOR-DEVICE.json')
    root_ready.update(ready=True, ready_for_device=True, created_utc_ns=time.time_ns(),
        preparation='packet165c one-card launch repair; two-card markers unchanged')
    for row in root_ready['proposals']:
        assert sha(ROOT / row['path']) == row['sha256']
    pending.append((packet, ready, root_ready))

# No evidence or source file is written after this point.
for packet, ready, root_ready in pending:
    target = packet / 'one-card/READY-FOR-DEVICE.json'
    save(target, ready)
    root_ready['packets'].pop('one-card', None)
    root_ready['packets']['one-card/READY-FOR-DEVICE.json'] = sha(target)
    save(packet / 'READY-FOR-DEVICE.json', root_ready)
save(HERE / 'READY-FOR-DEVICE.json', dict(ready_for_device=True, device_executed=False,
    queued=False, scope='One-card launch preparation only; no performance or quality promotion',
    packets={str((packet / 'READY-FOR-DEVICE.json').relative_to(ROOT)): sha(packet / 'READY-FOR-DEVICE.json')
             for packet, _, _ in pending},
    checks={str((HERE / 'evidence' / name).relative_to(ROOT)): sha(HERE / 'evidence' / name)
            for name in ('launch-checks.json', 'native-sensors.json', 'proposal-checks.json')},
    scripts={path.name: sha(path) for path in HERE.glob('*.py')}))
print('READY written last: both one-card packets ready_for_device; no queue action')

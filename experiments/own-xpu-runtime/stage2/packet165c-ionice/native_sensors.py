"""Replay real native resets/sensors for both orders on CPU marker transport.

Only a test-order admission assertion changes. Production source and device
binaries remain unchanged. Landlock denies model and GPU access.
"""
import importlib.util
import json
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import time

from check_launch import HERE, ROOT, OPS, read, save, sha
from build_engine import limits

sys.path.append(str(OPS))
from compile_turn import turn
spec = importlib.util.spec_from_file_location('sandbox', OPS / 'rehearse_entry.py')
sandbox = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sandbox)
limits()
old = HERE.parent / 'packet163-full-gate/one-card'
warm = HERE.parent / 'packet165-warm-prefill/one-card'
original_build = warm / 'build/native-sequence165'
source = HERE / 'lineage/native-fixture'
build = HERE / 'build'
build.mkdir(exist_ok=True)
pins = {}
for leaf in ('fixture.cpp', 'probe-main.cpp', 'mock_device.hpp', 'native_sequence_helpers.hpp'):
    path = source / leaf
    pins[str(path.relative_to(ROOT))] = sha(path)
    text = path.read_text()
    if leaf == 'native_sequence_helpers.hpp':
        before = 'ids.size()==13&&ids[0]=="incident-retrospective"&&ids[1]=="prefill512"'
        after = 'ids.size()==13&&((ids[0]=="incident-retrospective"&&ids[1]=="prefill512")||(ids[0]=="prefill512"&&ids[1]=="incident-retrospective"))'
        assert text.count(before) == 1
        text = text.replace(before, after)
    (build / leaf).write_text(text)
commands = [[arg.replace(str(original_build), str(build)) for arg in cmd]
            for cmd in read(warm / 'evidence/native-sequence.json')['commands']]
for index, command in enumerate(commands):
    with turn(), (build / f'compile-{index}.log').open('w') as log:
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            check=True, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4_000_000_000,) * 2))
    assert sum(f.stat().st_size for f in build.rglob('*') if f.is_file()) <= 300_000_000
binary = build / 'prepare-probe'
dependency = (build / 'fixture.d').read_text().replace('\\\n', ' ').split(':', 1)[1]
for filename in shlex.split(dependency):
    path = Path(filename).resolve()
    if path.is_relative_to(ROOT):
        if path.parent == build:
            retained = HERE / 'sources' / path.name
            retained.parent.mkdir(exist_ok=True)
            retained.write_bytes(path.read_bytes())
            path = retained
        pins[str(path.relative_to(ROOT))] = sha(path)
results = []
launches = read(HERE / 'evidence/launch-checks.json')['results']
for row in launches:
    limits()
    packet = old if row['job'].startswith('packet163-') else warm
    output = build / (row['job'] + '-' + str(time.time_ns()))
    output.mkdir()
    ids = row['execution_order']
    sequence = output / 'sequence.txt'
    sequence.write_text('\n'.join(ids) + '\n')
    for ident in ['', *ids, 'after-suite']:
        dest = output / ident
        dest.mkdir(exist_ok=True)
        (dest / 'state-2147483647').mkdir()
    metadata = [f for p in (old, warm) for f in (p / 'inputs').rglob('*') if f.is_file()]
    metadata += [p / leaf for p in (old, warm) for leaf in ('selection.json', 'dispatch.json', 'memory-plan.json')]
    metadata += list((old / 'native-source').rglob('*.bf16'))
    metadata += list((old / 'native-source').rglob('*manifest*.json'))
    metadata += [sequence]
    table = output / 'suite-inputs.tsv'
    table.write_text(''.join(ident + ' ' + str(packet / 'inputs' / ident / 'tokens.txt') + '\n' for ident in ids))
    metadata.append(table)
    argv = [str(binary), *row['launch']['argv'][3:]]
    for flag, value in (('--suite-inputs', table), ('--output', output)):
        argv[argv.index(flag) + 1] = str(value)
    env = row['launch']['closed_environment'].copy()
    env.update(ENTRY_PREPARE_OUTPUT=str(output), SEQUENCE_INPUTS=str(sequence))
    peak = 0
    with turn(), (output / 'stdout.log').open('w') as stdout, (output / 'stderr.log').open('w') as stderr:
        child = subprocess.Popen(['/usr/bin/ionice', '-c3', *argv], env=env,
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            preexec_fn=lambda: sandbox.prepare_restrict(binary, metadata, output))
        while child.poll() is None:
            try:
                status = Path(f'/proc/{child.pid}/status').read_text()
                rss = next(int(s.split()[1]) * 1024 for s in status.splitlines() if s.startswith('VmRSS:'))
                peak = max(peak, rss)
                if rss > 4_000_000_000:
                    child.terminate()
                    child.wait()
                    raise AssertionError('CPU probe exceeds 4 GB')
            except (FileNotFoundError, StopIteration):
                pass
            time.sleep(.05)
    assert child.returncode == 0, (output / 'stderr.log').read_text()
    assert 'PASS native sequence' in (output / 'stdout.log').read_text()
    checks = []
    for ident in [*ids, 'after-suite']:
        reset = read(output / ident / 'reset.json')
        assert reset['passed'] and reset['allocation_ids_preserved'] and reset['cached_tokens'] == 0
        for leaf in ('timings.jsonl', 'prefill-timings.jsonl', 'sites.jsonl', 'progress.jsonl'):
            path = output / ident / leaf
            sensors = [json.loads(s) for s in path.read_text().splitlines() if s]
            sensors = [s for s in sensors if s.get('cpu_sequence_sensor')]
            assert len(sensors) == 1 and sensors[0]['request_id'] == ident
            checks.append(dict(request_id=ident, stream=leaf, sha256=sha(path)))
    results.append(dict(job=row['job'], passed=True, proposal_sha256=row['proposal_sha256'],
        sequence=ids, reset_count=14, sensor_checks=checks, peak_rss_bytes=peak,
        binary_sha256=sha(binary), stdout=(output / 'stdout.log').read_text()))
    print(row['job'], '14 real native resets, 56 sensor checks PASS', flush=True)
save(HERE / 'evidence/native-sensors.json', dict(passed=True, device_executed=False,
    model_reads=False, commands=commands, source_sha256=pins, results=results,
    scope='Real reset/preparation functions, CPU marker transport and sparse synthetic weights; no device arithmetic claim',
    test_delta='Allow either registered cold or warm order; no production source changes',
    build_bytes=sum(f.stat().st_size for f in build.rglob('*') if f.is_file()),
    peak_children_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024))

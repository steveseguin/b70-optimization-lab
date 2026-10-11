"""Packet6 CPU preparation and packet2 bounded watcher reuse; no device query."""
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]
BASE = HERE.parent / 'packet2'
ROOT = HERE.parents[3]
BUILD = HERE / 'build'
INPUTS = BUILD / 'timing-input'
FIXTURES = BUILD / 'fixtures'
MANIFEST = BUILD / 'prepared.json'
LATCH = BUILD / 'device-fault-latch.json'
MODES = ('baseline', 'kopt_sg16', 'kopt_sg32', 'kopt_fused_sg16')

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Import our frozen lab baseline, never a third-party runtime implementation.
for name in ('device_window', 'timing_plan'):
    sys.modules[name] = load('_packet2_' + name, BASE / 'tests' / (name + '.py'))
p2 = load('_packet2_timing', BASE / 'tests/device_timing.py')
planlib = sys.modules['timing_plan']
sha, save, priority = planlib.sha, planlib.save, p2.priority
p2.LATCH = LATCH
watch = p2.watch


def sources():
    files = [HERE / 'CMakeLists.txt', BASE / 'CMakeLists.txt', BASE / 'roofline.json', planlib.CENSUS]
    for folder in (HERE, HERE / 'tests', BASE / 'kernels', BASE / 'tests', planlib.OWNER / 'src'):
        files += [p for p in folder.iterdir() if p.is_file() and p.suffix in ('.py', '.cpp', '.hpp')]
    return sorted(set(files))


def plan():
    result = planlib.make_plan()
    result['schema'] = 'own-runtime.iq3.packet6.timing-plan.v1'
    result['variants'] = list(MODES)
    result['scope'] = 'warm packed-fixture GEMV diagnostic; altered fixed reduction tree, not target-model parity or headline'
    for layer in result['layers']:
        count = 1 + sum(math.ceil(j['weight_bytes'] / planlib.CHUNK) + 1 + (2 if j['experts'] == 512 else 0)
            + 3 * (21 + (1 if j['experts'] == 512 else 0)) for j in layer['jobs'])
        if layer['layer'] == 0:
            count += 2 * 21 * len(layer['jobs']) + 21 + 20 * 4
        if count >= 4096:
            raise ValueError('bounded per-layer owner ledger exceeded')
        layer['event_count_upper_bound'] = count
    result['event_count_upper_bound'] = max(l['event_count_upper_bound'] for l in result['layers'])
    result['owner_sessions'] = 4
    return result


def prepare():
    priority()
    if BUILD.is_symlink() or MANIFEST.exists() or FIXTURES.exists() or INPUTS.exists():
        raise ValueError('fresh prepared manifest/fixtures/timing-input required')
    binaries = {n: BUILD / 'device' / n for n in ('device-test', 'device-timing')}
    for p in binaries.values():
        if not p.is_file():
            raise ValueError('build native target first: ' + str(p))
    cpu = json.loads((BASE / 'cpu-receipt.json').read_text())
    if cpu['passed'] is not True:
        raise ValueError('baseline CPU oracle not passed')
    known = {r['label'] + '.fixture': r['fixture_sha256'] for r in cpu['fixtures']
             if r['label'].startswith(('random', 'real-'))}
    source = BASE / 'build/fixtures/device-fixtures'
    FIXTURES.mkdir(parents=True)
    if source.is_dir():
        if {p.name for p in source.glob('*.fixture')} != set(known):
            raise ValueError('baseline fixture coverage')
        for name in known:
            shutil.copyfile(source / name, FIXTURES / name)
    else:
        from fixtures import regenerate
        regenerate(cpu['fixtures'])
    for name, digest in known.items():
        if sha(FIXTURES / name) != digest:
            raise ValueError('baseline fixture digest: ' + name)
    host = BUILD / 'device' / 'host-tests'
    test = subprocess.run([str(host), str(FIXTURES)], capture_output=True, text=True, check=True)
    repeat = subprocess.run([str(host), str(FIXTURES)], capture_output=True, text=True, check=True)
    if repeat.stdout != test.stdout:
        raise ValueError('fresh CPU process repeat differs')
    own_cpu = json.loads(test.stdout)
    own_cpu['fresh_process_repeats'] = 1
    own_cpu['host_binary_sha256'] = sha(host)
    if own_cpu.get('passed') is not True:
        raise ValueError('packet6 CPU oracle failed')
    save(BUILD / 'cpu-receipt.json', own_cpu)
    INPUTS.mkdir()
    current = plan()
    save(INPUTS / 'plan.json', current)
    seeds = {}
    seed_provenance = []
    for layer in current['layers']:
        lines = []
        for j in layer['jobs']:
            path = planlib.MODEL / j['shard']
            with path.open('rb', buffering=0) as f:
                before = os.fstat(f.fileno())
                data = os.pread(f.fileno(), j['seed_bytes'], j['absolute_offset'])
                after = os.fstat(f.fileno())
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if len(data) != j['seed_bytes'] or identity(before) != identity(after):
                raise ValueError('short/changing packed input')
            name = j['name'] + '.packed'
            (INPUTS / name).write_bytes(data)
            seeds[name] = sha(INPUTS / name)
            seed_provenance.append(dict(name=name, source=str(path), offset=j['absolute_offset'],
                sampled_bytes=len(data), source_stat=list(identity(before)), sha256=seeds[name]))
            lines.append(' '.join(map(str, [layer['layer'], j['name'], j['type_id'], j['rows'],
                j['columns'], j['experts'], j['weight_bytes'], len(data), name])))
        (INPUTS / ('layer%d.tsv' % layer['layer'])).write_text('\n'.join(lines) + '\n')
    manifest = dict(schema='own-runtime.iq3.packet6.prepared.v1', passed=True, device_executed=False,
        source_sha256={str(p.relative_to(ROOT)): sha(p) for p in sources()},
        binary_sha256={n: sha(p) for n, p in binaries.items()}, fixtures=known,
        cpu_receipt_sha256=sha(BUILD / 'cpu-receipt.json'), cpu=own_cpu, seeds=seed_provenance,
        inputs={p.name: sha(p) for p in INPUTS.iterdir()}, baseline_cpu_receipt_sha256=sha(BASE / 'cpu-receipt.json'),
        fixture_cases={m: len(known) * (4 if m == 'baseline' else 2) + (2 if m == 'kopt_fused_sg16' else 0) for m in MODES})
    save(MANIFEST, manifest)
    return manifest


def check():
    m = json.loads(MANIFEST.read_text())
    if m.get('passed') is not True or m.get('device_executed') is not False:
        raise ValueError('preparation not passed')
    if set(m['source_sha256']) != {str(p.relative_to(ROOT)) for p in sources()}:
        raise ValueError('source coverage changed')
    for name, digest in m['source_sha256'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('source changed: ' + name)
    if sha(BUILD / 'cpu-receipt.json') != m['cpu_receipt_sha256']:
        raise ValueError('CPU receipt changed')
    for name, digest in m['binary_sha256'].items():
        if sha(BUILD / 'device' / name) != digest:
            raise ValueError('binary changed')
    for directory, field in ((FIXTURES, 'fixtures'), (INPUTS, 'inputs')):
        if {p.name for p in directory.iterdir()} != set(m[field]):
            raise ValueError('input coverage changed')
        for name, digest in m[field].items():
            if sha(directory / name) != digest:
                raise ValueError('input changed')
    if json.loads((INPUTS / 'plan.json').read_text()) != plan():
        raise ValueError('plan changed')
    return m


def admit(card, output):
    priority()
    out = output.resolve()
    if card != 3 or BUILD.is_symlink() or BUILD not in out.parents or out.exists():
        raise ValueError('card3 and fresh packet6/build output required')
    if LATCH.exists():
        raise ValueError('fault latch present; coordinator recovery required')
    return out, check()


def teardown_ok(raw):
    t = raw.get('teardown', {})
    return (raw.get('error') == '' and t.get('safe_to_exit') is True and t.get('idle_marker_complete') is True
        and t.get('live_bytes') == t.get('in_flight') == t.get('exit_code') == 0
        and t.get('status') == 'complete' and t.get('error') == '' and 'context-released' in t.get('sequence', []))

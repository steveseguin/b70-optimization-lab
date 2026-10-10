#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Synthetic CPU digest mechanism timing; never a measured stream period.

Archived receipts expose signature hashes and argument-type census, not raw
signature keys. This builds representative described tuples with that census:
48 routes, four signatures, 18 mirrored tensors, 48 infrastructure route pins.
Dimensions and identity integers are fixtures. No actual key reconstruction or
model execution is claimed. Cache correctness is separately mutation-tested.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
LANE = HERE.parent.parent
SOURCE = LANE / 'recovery/20261010-continuation127-stream'
PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-126')
ARCHIVE = PARENT.parent / ('encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-'
    'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T054956Z')
REPORT = ARCHIVE / 'graph-capture-stream121-qgraph-c000002.json'
GUARD_EVENTS = []


def audit(event, args):
    if event in ('subprocess.Popen', 'socket.connect', 'os.system'):
        GUARD_EVENTS.append(event)
        raise RuntimeError('CPU-only benchmark denied: ' + event)
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        name = os.fsdecode(args[0])
        if name == '/dev/dri' or name.startswith('/dev/dri/'):
            GUARD_EVENTS.append(name)
            raise RuntimeError('CPU-only benchmark denied device open')


sys.addaudithook(audit)
sys.path.insert(0, str(SOURCE))
from signature_cache127 import SignatureDigestCache


def tensor(device, n=304):
    return ('T', (1, n, 4096), 'torch.bfloat16', device,
            (n * 4096, 4096, 1), True, False)


def signature(device, n, anchored):
    t = tensor(device, n)
    route_pins = tuple((repr(('double_block', i)),
        ('identity', 'ltx_graph_capture', 'GraphBlockRoute', 100000000000000 + i)) for i in range(48))
    infra = ('dict', (
        ("'patches_replace'", ('dict', (("'dit'", ('dict', route_pins)),))),
        ("'callbacks'", ('dict', (("'on_pre_run'", ('list', (
            ('identity', 'graph_capture_node', 'guard', 200000000000000),))),))),
        ("'wrappers'", ('dict', (("'diffusion_model'", ('list', (
            ('identity', 'ltx_layer_shard', 'forward', 300000000000000),))),)))))
    return (('tuple', (t, tensor(device, 151))), tuple(t for _ in range(16)),
        ('dict', (("'cond_or_uncond'", ('list', (('S', '0'),))),
          ("'prefetch_dynamic_vbars'", ('S', 'False')),
          ("'sample_sigmas'", ('T', (9,), 'torch.float32', device, (1,), True, False)),
          ("'sigmas'", ('T', (1,), 'torch.float32', device, (1,), True, False)),
          ("'uuids'", ('list', (('valueless', 'uuid', 'UUID'),))),
          ("'anchored_fixture'", ('S', repr(anchored))))), infra)


def summary(values):
    return {'n': len(values), 'median_s': statistics.median(values),
            'min_s': min(values), 'max_s': max(values), 'mean_s': statistics.mean(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=HERE / 'continuation127-signature-cpu.json')
    out = parser.parse_args().output
    assert not out.exists(), 'Never overwrite existing evidence'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    assert sys.dont_write_bytecode and Path(sys.executable).name == 'python'
    assert 'torch' not in sys.modules
    census = json.loads(REPORT.read_bytes())['capture_summary']
    assert census['captured_graphs'] == 192 and census['blocks_captured'] == list(range(48))
    assert census['chain'] == 1
    parent_source = PARENT / 'source/scripts/candidate_safety.py'
    tree = ast.parse(parent_source.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_signature_digest')
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    namespace = {'hashlib': hashlib}
    exec(compile(module, str(parent_source), 'exec'), namespace)
    digest = namespace['_signature_digest']
    per_device = {d: [signature(d, n, a) for n in (304, 1216) for a in (False, True)]
                  for d in ('xpu:0', 'xpu:1')}
    groups = [per_device['xpu:0' if i < 20 else 'xpu:1'] for i in range(48)]
    cache = SignatureDigestCache()
    for keys in groups:
        assert cache.digest(keys, digest) == digest(keys)
    times = {'parent': [], 'cached': []}
    for batch in range(50):
        for arm in (('parent', 'cached') if batch % 2 == 0 else ('cached', 'parent')):
            fn = digest if arm == 'parent' else lambda keys: cache.digest(keys, digest)
            started = time.perf_counter()
            for snapshot in range(6):
                for keys in groups:
                    fn(list(keys))
            times[arm].append(time.perf_counter() - started)
    saved = [a - b for a, b in zip(times['parent'], times['cached'])]
    paths = [Path(__file__), SOURCE / 'signature_cache127.py', parent_source,
             PARENT / 'source/scripts/ltx_graph_capture.py', REPORT]
    result = {'schema': 'ltx.continuation127.signature-cpu-mechanism.v1',
        'scope': 'synthetic CPU digest mechanism, not actual snapshot time or live chunk period',
        'fixture': 'source-shaped immutable tuples; actual raw signature keys were not saved',
        'census': {'routes': 48, 'signatures_per_route': 4, 'mirrored_tensors': 18,
                   'repr_bytes_per_signature': len(repr(groups[0][0]))},
        'method': '50 paired batches, alternating order; 48 routes times six snapshots per batch; warmed cache',
        'batches': 50, 'digests_per_batch': 288,
        'timings': {key: summary(value) for key, value in times.items()},
        'paired_saving': summary(saved), 'raw_seconds': times, 'cache': cache.summary(),
        'python': sys.executable, 'nice': os.getpriority(os.PRIO_PROCESS, 0),
        'omp_num_threads': os.environ['OMP_NUM_THREADS'], 'dont_write_bytecode': sys.dont_write_bytecode,
        'forbidden_operations': GUARD_EVENTS, 'torch_imported': 'torch' in sys.modules,
        'sources_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    assert not GUARD_EVENTS and 'torch' not in sys.modules
    with out.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('timings', 'paired_saving', 'cache')}, indent=2))


if __name__ == '__main__':
    main()

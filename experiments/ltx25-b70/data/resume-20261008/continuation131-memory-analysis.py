"""Regular-file-only packet131 memory census; pinned Python -B, nice19, OMP2."""
import hashlib
import json
import statistics
from pathlib import Path

BASE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
GIB = 2 ** 30
sources = {}

def read(path):
    raw = path.read_bytes()
    sources[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)

def summary(values):
    return {'n': len(values), 'minimum': min(values), 'maximum': max(values), 'median': statistics.median(values)} if values else None

runs = []
for packet in (124, 127, 128, 129):
    for root in sorted(BASE.glob(f'encoder-server-continuation-stream-{packet}-*f145*')):
        receipts, decodes = [], []
        for category, dest in [('receipt', receipts), ('decode', decodes)]:
            for path in sorted((root / 'receipts').glob(category + '-*.json')):
                if path.stem.rsplit('-s', 1)[-1].isdigit() and int(path.stem.rsplit('-s', 1)[1]) > 200:
                    continue
                dest.append(read(path))
        phases = {}
        for phase in ('before', 'A-before', 'A-after', 'B-before', 'B-after', 'after'):
            free = []
            for row in receipts:
                memory = row.get('memory', {})
                value = memory.get(phase, {}).get('free')
                if '-' in phase:
                    stage, edge = phase.split('-')
                    value = next((x.get('free_' + edge) for x in memory.get('conditioning', []) if x['stage'] == stage), None)
                if value:
                    free.append(value['xpu:3'])
            phases[phase] = summary(free)
        allocator = {}
        for phase in ('before', 'after'):
            values = [r['memory'][phase]['peaks']['xpu:3'] for r in receipts if phase in r.get('memory', {})]
            allocator[phase] = {key: summary([r[key] for r in values]) for key in ('allocated', 'reserved', 'peak')}
            allocator[phase]['reserved_minus_allocated'] = summary([r['reserved'] - r['allocated'] for r in values])
        cone = {kind: summary([r['xpu3_free_before_decode'] for r in decodes if r['kind'] == kind]) for kind in ('qualify-eager', 'qualify-graph', 'qualify-repeat', 'stream')}
        replicas = [r['display_replica']['residency']['last_decode'] for r in decodes if r.get('display_replica')]
        runs.append({'packet': packet, 'run': str(root), 'receipt_count': len(receipts), 'decode_count': len(decodes), 'selection': 'all qualification plus stream_seq <= 200', 'physical_free_xpu3_bytes': phases, 'allocator_xpu3_bytes': allocator, 'cone_before_free_xpu3_bytes_by_kind': cone, 'replica': None if not replicas else {'observed_growth_bytes': summary([r['observed_peak_or_reservation_growth_bytes'] for r in replicas]), 'before_free_xpu2_bytes': summary([r['before']['free_bytes'] for r in replicas]), 'margin_after_floor_and_transient_bytes': summary([r['before']['margin_bytes'] for r in replicas])}})
captures = []
for packet in (119, 120):
    root = next(BASE.glob(f'encoder-server-continuation-stream-{packet}-*dg1*'))
    row = read(root / 'stream-freeze.json')['decoder_graph']
    captures.append({'packet': packet, 'run': str(root), 'pool': row['pool'], 'signatures': row['signatures'], 'captures': row['captures']})
prior = Path(__file__).with_name('continuation130-residency.json')
static = read(prior)
growth = captures[0]['pool']['growth_bytes']
assert growth == captures[1]['pool']['growth_bytes'] == 3430940672
quadratic = growth * 19 ** 2 // 16 ** 2
result = {'schema': 'ltx.continuation131.memory-census.v1', 'scope': 'CPU regular files only; no GPU import, device access, runtime operation, or existing-run write', 'unit': 'bytes; GiB = 2**30', 'sources': sources, 'runs': runs, 'capture121': captures, 'growth_estimate145': {'measured121_reserved_growth_bytes': growth, 'latent_ratio': '19/16', 'linear_bytes': growth * 19 // 16, 'temporal_squared_bytes': quadratic, 'temporal_squared_gib': quadratic / GIB, 'status': 'engineering estimate, not exact 145 measurement or proven upper bound; includes warmup/proof allocations'}, 'static_inventory': static['parent_static_inventory'], 'text_secondary_bytes': static['text_secondary_bytes'], 'known_limits': ['Physical free is sampled, not a phase-complete peak trace.', 'Reserved minus allocated is not guaranteed releasable.', 'Display growth counters on xpu2 are device-global, not isolated xpu3 savings.', 'Cone graph already captures forward_pre_diffusion only into a decoder-private pool.', 'Qualification retains native full-display references on xpu3; replica movement alone does not remove their reservation tail.', 'No 145 decoder-graph measurement exists in these sources.']}
out = Path(__file__).with_name('continuation131-memory-analysis.json')
out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'output': str(out), 'input_files': len(sources), 'runs': len(runs), 'growth_estimate145_bytes': quadratic, 'growth_estimate145_gib': quadratic/GIB}, sort_keys=True))

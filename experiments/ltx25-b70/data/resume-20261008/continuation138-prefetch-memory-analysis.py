#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Read-only CPU source/receipt census. Emits JSON to stdout; imports no runtime."""
import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-137')
SOURCES = {}


def read(path):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return json.loads(raw)


def source(path):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return raw.decode()


def frees(value, path='memory'):
    if isinstance(value, dict):
        for key in ('free', 'free_before', 'free_after'):
            if isinstance(value.get(key), dict):
                yield path + '.' + key, value[key]
        for key, item in value.items():
            yield from frees(item, path + '.' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from frees(item, path + f'[{index}]')


oracle = read(REPO / 'experiments/ltx25-b70/data/resume-20261008/continuation133-text-oracle.json')
historical = read(REPO / 'experiments/ltx25-b70/data/resume-20261008/continuation134-evidence.json')
ledger = read(REPO / 'data/ltx25-continuation-stream-2026-10-10-pacing-v2.json')
rows = []
for prompt_sha, entry in sorted(oracle['prompts'].items()):
    assert all(t['dtype'] == 'torch.float32' for t in entry['tensors'])
    rows.append({'prompt_sha256': prompt_sha, 'tensors': entry['tensors'],
                 'logical_bytes': sum(math.prod(t['shape']) * 4 for t in entry['tensors'])})
assert len(rows) == 12
maximum = max(r['logical_bytes'] for r in rows)
run = next(r for r in ledger['runs'] if r['work_dir'].endswith('/s135-gc10-live01'))
minimum = {}
for seq in range(31):
    path = Path(run['saved_run_dir']) / f'receipts/receipt-stream135-s{seq:08d}.json'
    receipt = read(path)
    for phase, free in frees(receipt['memory']):
        for card, value in free.items():
            if card not in minimum or value < minimum[card]['bytes']:
                minimum[card] = {'bytes': value, 'phase': phase, 'stream_seq': seq}
floors = {'xpu:0': 8, 'xpu:1': 8, 'xpu:2': 2, 'xpu:3': 9}
for card, row in minimum.items():
    row['margin_over_floor_gib'] = row['bytes'] / 2**30 - floors[card]
    row['margin_over_floor_and_screen_gib'] = row['margin_over_floor_gib'] - .75
for relative in ('source/comfy/sd1_clip.py', 'source/comfy/text_encoders/lt.py',
                 'source/comfy/model_management.py', 'source/scripts/pipeline_node.py',
                 'source/scripts/ltx_graph_text_encoder.py', 'launch/serve-encoder.py',
                 'resolution/components/integration.py'):
    source(PACKET / relative)
out = {
    'schema': 'ltx.continuation138.prefetch-memory.v1',
    'scope': 'CPU-only logical-buffer census and saved sampled minima; no candidate native peak or memory-fit claim',
    'parent_manifest_sha256': '18c80d25c2ba4992d8c6dff24779737a056a325389a84486d24da674ef7e463e',
    'conditioning': {
        'prompts': rows, 'max_one_buffer_logical_bytes': maximum,
        'max_one_buffer_mib': maximum / 2**20,
        'one_buffer_allocation_device': 'cpu (source-derived; oracle rows omit device)',
        'device_reason': 'sd1_clip returns intermediate_device; model_management returns cpu without gpu_only; '
                         'sealed server_args does not select gpu_only; lt.py remembers that out_device and '
                         'returns projected float32 conditioning there',
        'resident_increment': 'one additional retained conditioning value, at most max_one_buffer_logical_bytes; no ten-scene cache',
        'transient_clone_budget': {'two_live_conditioning_values_logical_bytes': 2 * maximum,
                                   'three_live_conditioning_values_logical_bytes': 3 * maximum,
                                   'reason': 'deepcopy at reuse/cache handoff can temporarily coexist with prefetch and active value; '
                                             'these are logical payload totals, not measured allocator peaks or necessarily incremental bytes'},
        'text_computation_devices': 'xpu:2 primary layers0..35/embedding/projection; xpu:3 secondary layers36..47',
        'new_graph_pool_budget': 'none admitted; dispatch must reuse an already-qualified encode worker and its existing graph entries',
        'graph_buffer_caveat': 'GraphedLayer static inputs/output are per thread, output aliases static hidden input; '
                              'a new decode-thread graph owner or copying all graph state is not included in the one-conditioning-buffer budget',
    },
    'saved133b_stream31': historical['stream_memory'],
    'saved135_gc10_stream31': {'sequence_inclusive': [0, 30], 'independent_sampled_minima': minimum},
    'limits': ['Sampled minima are not simultaneous and do not bound overlap peaks.',
               'The additional retained conditioning is CPU; overlapping a fresh encoder pass still uses XPU temporary buffers.',
               'No candidate graph-static-state clone or new graph pool has been measured or admitted.',
               'Floors8/8/2/9GiB, cone allowances and existing runtime fresh-memory checks remain unchanged.'],
    'source_files': SOURCES,
}
print(json.dumps(out, indent=2, sort_keys=True))

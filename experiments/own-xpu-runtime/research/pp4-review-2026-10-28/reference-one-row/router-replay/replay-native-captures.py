"""Replay captured native router logits through existing host and ggml kernels."""
from pathlib import Path
import hashlib
import json
import math
import struct
import subprocess

HERE = Path(__file__).resolve().parent
CAPTURE = Path('/dev/shm/sc117-router-all48-target244-20261028-r1/output/router-captures')
BINARY = Path('/dev/shm/sc117-router-fixture-cpu-20261028-r2/replay')
OUT = HERE / 'native-input-r1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def values(p, kind='f'):
    raw = p.read_bytes()
    assert len(raw) % 4 == 0
    return struct.unpack('<' + kind * (len(raw) // 4), raw)

def difference(a, b):
    x, y = a.read_bytes(), b.read_bytes()
    assert len(x) == len(y)
    return sum(x[i:i+4] != y[i:i+4] for i in range(0, len(x), 4))

identity = json.loads((HERE / 'fixture-r2/result.json').read_text())
assert sha(BINARY) == identity['binary_sha256']
assert sha(HERE / 'replay.cpp') == identity['source_sha256']
OUT.mkdir(exist_ok=False)
rows = []
for layer in range(48):
    captured = CAPTURE / f'layer{layer}'
    extraction = json.loads((captured / 'extraction.json').read_text())
    assert extraction['full_seal_verified'] and extraction['layer'] == layer
    for name, digest in extraction['selected'].items():
        assert sha(captured / name) == digest
    logits = captured / f'blk.{layer}.router.bin'
    assert len(logits.read_bytes()) == 2048
    assert all(math.isfinite(x) for x in values(logits))
    dest = OUT / f'layer{layer}'
    argv = ['nice', '-n', '19', 'taskset', '-c', '8-15', str(BINARY), str(logits), str(dest)]
    with (OUT / f'layer{layer}.log').open('w') as log:
        rc = subprocess.call(argv, stdout=log, stderr=subprocess.STDOUT)
    assert rc == 0
    checks = {}
    for native, replayed in [('ids', 'native-ids.i32'), ('prob', 'native-weights.f32'),
                             ('routes', 'native-routes.i32'), ('routes.down', 'native-routes-down.i32')]:
        checks[native] = difference(captured / f'blk.{layer}.{native}.bin', dest / replayed)
    host_ids = values(dest / 'native-ids.i32', 'i')
    cpu_ids = values(dest / 'ggml-ids.i32', 'i')
    probabilities = values(dest / 'native-probs.f32')
    ordered = sorted(range(512), key=lambda i: (-probabilities[i], i))
    tenth, eleventh = ordered[9:11]
    rows.append(dict(layer=layer, argv=argv, returncode=rc,
        input_sha256=sha(logits), capture_vs_host_unequal_words=checks,
        host_vs_ggml_id_slot_differences=sum(x != y for x, y in zip(host_ids, cpu_ids)),
        host_vs_ggml_selected_set_equal=set(host_ids) == set(cpu_ids),
        native_ids=host_ids, ggml_ids=cpu_ids,
        host_vs_ggml_probability_unequal_words=difference(dest/'native-probs.f32', dest/'ggml-probs.f32'),
        host_vs_ggml_weight_unequal_words=difference(dest/'native-weights.f32', dest/'ggml-weights.f32'),
        native_cutoff_probability_tie=probabilities[tenth] == probabilities[eleventh],
        native_cutoff_logit_gap=values(logits)[tenth] - values(logits)[eleventh],
        output_sha256={p.name: sha(p) for p in dest.iterdir() if p.is_file()}))
summary = dict(binary_sha256=sha(BINARY), script_sha256=sha(Path(__file__)),
    scope='Position243 native logits only; real production host route and actual ggml kernels on same input. No earlier history or causal final-output conclusion.',
    native_capture_host_exact_layers=[r['layer'] for r in rows if not any(r['capture_vs_host_unequal_words'].values())],
    same_input_selected_set_difference_layers=[r['layer'] for r in rows if not r['host_vs_ggml_selected_set_equal']],
    cutoff_tie_layers=[r['layer'] for r in rows if r['native_cutoff_probability_tie']], rows=rows)
(OUT / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k:v for k,v in summary.items() if k != 'rows'}))

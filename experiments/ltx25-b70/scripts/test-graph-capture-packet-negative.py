#!/usr/bin/env python3
"""Negative tests: the packet14 checker must reject tampering, including a
manifest regenerated to match the tampered tree."""
import hashlib, json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PK = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'prepared-encoder-graph-capture-21')
PYEXE = '/home/steve/.venvs/ltx25-baseline/bin/python'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check(pk, digest=None):
    r = subprocess.run([PYEXE, '-B', str(pk / 'launch/serve-encoder.py'), '--packet', str(pk),
                        '--manifest-sha256', digest or sha(pk / 'manifest.json'),
                        '--run-name', 'encoder-server-negative-probe', '--check-only'],
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stderr.strip().splitlines() or [''])[-1]

def regen(pk):
    m = json.loads((pk / 'manifest.json').read_text())
    files = {}
    for p in sorted(pk.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(pk))
            if rel in ('manifest.json', 'STATUS.txt'): continue
            files[rel] = sha(p)
    m['files'] = files
    m['startup_tools'] = {'encoder_runtime_common.py': files['launch/encoder_runtime_common.py'],
                          'serve-encoder.py': files['launch/serve-encoder.py']}
    m['extension_sha256s'] = {k: files['source/scripts/' + k] for k in m['extension_sha256s']}
    m['graph_capture']['adapter_sha256'] = files['source/scripts/ltx_graph_capture.py']
    m['graph_capture']['node_sha256'] = files['source/scripts/graph_capture_node.py']
    with (pk / 'manifest.json').open('w') as h:
        json.dump(m, h, indent=2, sort_keys=True); h.write('\n')

made, cases = [], []
try:
    # 1. wrong pinned digest
    cases.append(('pinned manifest digest does not match', *check(PK, '0' * 64)))
    # 2. numerical source edited, manifest regenerated
    pk1 = ROOT / 'prepared-encoder-negative-gc-one'; made.append(pk1); shutil.copytree(PK, pk1)
    t = pk1 / 'source/comfy/ldm/lightricks/av_model.py'
    t.write_text(t.read_text().replace('run_vx = transformer_options.get("run_vx", True)',
                                       'run_vx = transformer_options.get("run_vx", True)  # tampered', 1))
    regen(pk1); cases.append(('numerical source edited, manifest regenerated', *check(pk1)))
    # 3. gate graph quality recipe altered
    pk2 = ROOT / 'prepared-encoder-negative-gc-two'; made.append(pk2); shutil.copytree(PK, pk2)
    g = pk2 / 'graphs/graph-capture-all48-graph.json'
    d = json.loads(g.read_text()); d['356']['inputs']['width'] = 64
    g.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    regen(pk2); cases.append(('gate graph resolution altered', *check(pk2)))
    # 4. gate node rewired to skip the capture gate
    pk3 = ROOT / 'prepared-encoder-negative-gc-three'; made.append(pk3); shutil.copytree(PK, pk3)
    g = pk3 / 'graphs/graph-capture-all48-graph.json'
    d = json.loads(g.read_text()); d['422']['inputs']['selection'] = 'single24'
    g.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    regen(pk3); cases.append(('gate node selection changed', *check(pk3)))
    # 4b. the axis-cache decode node swapped for something else
    pk3b = ROOT / 'prepared-encoder-negative-gc-threeb'; made.append(pk3b); shutil.copytree(PK, pk3b)
    g = pk3b / 'graphs/graph-capture-all48-graph-axis-cache.json'
    d = json.loads(g.read_text()); d['374']['inputs']['mode'] = 'original'
    g.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    regen(pk3b); cases.append(('axis-cache decode mode changed', *check(pk3b)))
    # 4c. the axis-cache graph given a different latent source
    pk3c = ROOT / 'prepared-encoder-negative-gc-threec'; made.append(pk3c); shutil.copytree(PK, pk3c)
    g = pk3c / 'graphs/graph-capture-all48-graph-axis-cache.json'
    d = json.loads(g.read_text()); d['374']['inputs']['samples'] = ['367', 0]
    g.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    regen(pk3c); cases.append(('axis-cache decode rewired to another latent', *check(pk3c)))
    # 5. custom-node copy diverges from its scripts/ helper
    pk4 = ROOT / 'prepared-encoder-negative-gc-four'; made.append(pk4); shutil.copytree(PK, pk4)
    n = pk4 / 'source/custom_nodes/ltx_graph_capture_lab/__init__.py'
    n.write_text(n.read_text() + '\n# divergent copy\n')
    regen(pk4); cases.append(('custom-node copy diverges from helper', *check(pk4)))
    # 6. extra uninventoried file
    pk5 = ROOT / 'prepared-encoder-negative-gc-five'; made.append(pk5); shutil.copytree(PK, pk5)
    (pk5 / 'source/scripts/sneaky.py').write_text('x = 1\n')
    regen(pk5); cases.append(('extra file added to source/scripts', *check(pk5)))
finally:
    for p in made:
        shutil.rmtree(p, ignore_errors=True)

ok = all(rc != 0 for _, rc, _ in cases)
for name, rc, err in cases:
    print(f'{"REJECTED" if rc else "ACCEPTED!!":10s} rc={rc}  {name}\n           -> {err[:160]}')
print('\nALL NEGATIVE CASES REJECTED:', ok)
sys.exit(0 if ok else 1)

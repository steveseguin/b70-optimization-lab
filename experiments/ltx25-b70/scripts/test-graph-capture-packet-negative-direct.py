#!/usr/bin/env python3
"""Negative tests for the packet checker, calling verify_packet directly.

The launcher's --check-only path refuses everything while FAULT.json is
latched, which would make every tampering case "rejected" for the wrong
reason. This variant imports the tampered packet's own checker and calls
verify_packet in-process, so each rejection is the checker's. Adds cases for
the upsampler gate. Usage: test ... <packet-name>
"""
import hashlib, importlib.util, json, shutil, sys
from pathlib import Path
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PK = ROOT / (sys.argv[1] if len(sys.argv) > 1 else 'prepared-encoder-graph-capture-61')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(pk, digest=None):
    spec = importlib.util.spec_from_file_location('erc_' + pk.name.replace('-', '_'),
                                                  pk / 'launch/encoder_runtime_common.py')
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    try:
        mod.verify_packet(pk, digest or sha(pk / 'manifest.json'))
        return 0, 'accepted'
    except Exception as e:  # noqa: BLE001
        return 1, type(e).__name__ + ': ' + str(e)


def regen(pk):
    m = json.loads((pk / 'manifest.json').read_text())
    files = {}
    for p in sorted(pk.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(pk))
            if rel in ('manifest.json', 'STATUS.txt'):
                continue
            files[rel] = sha(p)
    m['files'] = files
    m['startup_tools'] = {'encoder_runtime_common.py': files['launch/encoder_runtime_common.py'],
                          'serve-encoder.py': files['launch/serve-encoder.py']}
    m['extension_sha256s'] = {k: files['source/scripts/' + k] for k in m['extension_sha256s']}
    gc = m['graph_capture']
    for key, f in (('adapter_sha256', 'ltx_graph_capture.py'), ('node_sha256', 'graph_capture_node.py'),
                   ('vae_adapter_sha256', 'ltx_graph_vae.py'), ('vae_node_sha256', 'graph_vae_node.py'),
                   ('upsampler_adapter_sha256', 'ltx_graph_upsampler.py'),
                   ('upsampler_node_sha256', 'graph_upsampler_node.py'),
                   ('phase_node_sha256', 'phase_timed_upsampler_node.py'),
                   ('fast_node_sha256', 'resident_fastpath_node.py'),
                   ('pipe_adapter_sha256', 'ltx_pipeline.py'), ('pipe_node_sha256', 'pipeline_node.py'),
                   ('na_candidate_sha256', 'ltx_na_axis_candidate.py'),
                   ('na_router_sha256', 'ltx_na_axis_router.py'),
                   ('na_decode_node_sha256', 'na_axis_decode_node.py')):
        gc[key] = files['source/scripts/' + f]
    with (pk / 'manifest.json').open('w') as h:
        json.dump(m, h, indent=2, sort_keys=True); h.write('\n')


def edit_graph(pk, arm, fn):
    g = pk / ('graphs/graph-capture-all48-' + arm + '.json')
    d = json.loads(g.read_text()); fn(d)
    g.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')


made, cases = [], []
try:
    cases.append(('untampered packet', *check(PK)))
    cases.append(('pinned manifest digest does not match', *check(PK, '0' * 64)))
    n = 0

    def tampered(label, fn, pinned=False):
        global n
        n += 1
        pk = ROOT / f'prepared-encoder-negative-direct-{n:02d}'
        made.append(pk); shutil.copytree(PK, pk)
        fn(pk); regen(pk)
        # An edited lab extension with a regenerated manifest is internally
        # consistent by construction; what pins it is the manifest digest the
        # launch command and server identity carry. Such cases are checked
        # under the ORIGINAL digest.
        cases.append((label, *check(pk, sha(PK / 'manifest.json') if pinned else None)))

    def src(pk, rel, old, new):
        t = pk / rel; s = t.read_text(); assert old in s, (rel, old); t.write_text(s.replace(old, new, 1))

    tampered('numerical source edited', lambda pk: src(
        pk, 'source/comfy/ldm/lightricks/av_model.py',
        'run_vx = transformer_options.get("run_vx", True)',
        'run_vx = transformer_options.get("run_vx", True)  # tampered'))
    tampered('gate graph resolution altered', lambda pk: edit_graph(
        pk, 'graph', lambda d: d['356']['inputs'].__setitem__('width', 64)))
    tampered('upsampler gate silently disabled in pipe-up', lambda pk: edit_graph(
        pk, 'pipe-up', lambda d: d['429']['inputs'].__setitem__('mode', 'original')))
    tampered('upsampler node rewired around the gate', lambda pk: edit_graph(
        pk, 'pipe-up', lambda d: d['348']['inputs'].__setitem__('upscale_model', ['420', 4])))
    tampered('upsampler gate fed a different model output', lambda pk: edit_graph(
        pk, 'pipe-up', lambda d: d['429']['inputs'].__setitem__('upscale_model', ['420', 2])))
    tampered('upsampler adapter edited under the pinned digest', lambda pk: src(
        pk, 'source/scripts/ltx_graph_upsampler.py', "METHOD = 'forward'", "METHOD = 'forward'  # x"), pinned=True)
    tampered('upsampler node copy diverges from helper', lambda pk: (pk / 'source/custom_nodes/ltx_graph_upsampler_lab/__init__.py').write_text(
        (pk / 'source/custom_nodes/ltx_graph_upsampler_lab/__init__.py').read_text() + '\n# divergent\n'))
    tampered('pipeline text-encode edge changed in pipe', lambda pk: edit_graph(
        pk, 'pipe', lambda d: d['365']['inputs'].__setitem__('positive', ['364', 0]) or d['365']['inputs'].__setitem__('negative', ['420', 1])))
    tampered('phase-timed node silently set to original in pipe-upphase', lambda pk: edit_graph(
        pk, 'pipe-upphase', lambda d: d['348']['inputs'].__setitem__('mode', 'original')))
    tampered('save-record node rewired to a different decode output', lambda pk: edit_graph(
        pk, 'pipe-up-save', lambda d: d['430']['inputs'].__setitem__('saved_file', ['426', 0])))
    tampered('fast-path node silently set to original in pipe-fast', lambda pk: edit_graph(
        pk, 'pipe-fast', lambda d: d['431']['inputs'].__setitem__('mode', 'original')))
    tampered('fusion gate rewired around the fast-path node', lambda pk: edit_graph(
        pk, 'pipe-fast', lambda d: d['424']['inputs'].__setitem__('model', ['420', 0])))
    tampered('extra file added to source/scripts', lambda pk: (pk / 'source/scripts/sneaky.py').write_text('x = 1\n'))
finally:
    for pk in made:
        shutil.rmtree(pk, ignore_errors=True)

ok = True
for label, rc, msg in cases:
    expect_accept = label == 'untampered packet'
    good = (rc == 0) if expect_accept else (rc == 1)
    ok &= good
    print(('ACCEPTED ' if rc == 0 else 'REJECTED ') + ('ok  ' if good else 'BAD ') + label)
    print('           -> ' + msg[:160])
print('\nALL CASES AS EXPECTED:', ok)
sys.exit(0 if ok else 1)

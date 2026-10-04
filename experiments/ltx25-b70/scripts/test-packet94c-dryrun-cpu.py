#!/usr/bin/env python3
"""Packet 94c offline dry run (CPU only; no XPU, no server, nothing loaded to a card).

For each layout (two-way, shard3-c, shard4-a), with a stand-in 48-block bf16 model:
1. Component loader (real host_embedding_resident_node, reloaded with
   LTX_SAMPLER_PLACEMENT set): the layout is selected from the environment, the
   transformer is placed by the same apply_* call load() makes, and the real
   shared_identity() and the load receipt's shard report run and serialise.
   Unknown layouts refuse at import.
2. Graph-capture gate (real graph_capture_node.check_shard_report and
   ltx_graph_capture.validate_patcher on the placed patcher, with the native class
   check pointed at the stand-in): accepted for the three layouts; a tampered
   report is refused.
3. Sampler node (real pipeline_sampler_node): placement_devices, the extra
   streams list, the freeze's expected-resident check and verdict.
4. Decode probe prerequisite: the real lookup pipeline_decode_node uses for the
   fast path's load lock fails before LTXResidentFastPath('fast') is installed and
   succeeds after (the 94b control failure).
5. The 94c runner order and the graphs: what installs what precedes what needs it.

Not covered (needs the real server): ComfyUI's executor and prompt validation,
checkpoint loading and the model manager moving weights to cards, any XPU
memory, graph capture/replay of real blocks, and the apply() bodies of the
loader, text gate, window probe, decode probe and freeze nodes.
"""
import importlib
import json
import os
import re
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-shard4-94b/source')  # shipped ComfyUI tree (packet 89 av_model)
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram']
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import torch  # noqa: E402
from torch import nn  # noqa: E402
from comfy.model_patcher import ModelPatcher  # noqa: E402
sys.modules['host_embedding_clip'] = importlib.import_module('host_embedding_clip_threadsafe')
import ltx_layer_shard as shard  # noqa: E402
import ltx_graph_capture as gcap  # noqa: E402
import graph_capture_node as gnode  # noqa: E402
import pipeline_sampler_node as snode  # noqa: E402
import pipeline_decode_node as dnode  # noqa: E402
import resident_fastpath_node as fast  # noqa: E402

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-shard4-94f')
LAYOUTS = ('two-way', 'shard3-c', 'shard4-a')
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-3:])))


def raises(fn, text=None):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        assert text is None or text in str(error), (text, str(error))
        return
    raise AssertionError('expected a refusal')


class StandInDiffusion(nn.Module):
    def __init__(self):
        super().__init__()
        self.transformer_blocks = nn.ModuleList([nn.Linear(2, 2, dtype=torch.bfloat16) for _ in range(48)])
        self.proj = nn.Linear(2, 2, dtype=torch.bfloat16)


class StandInModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.diffusion_model = StandInDiffusion()

    def get_dtype(self):
        return torch.bfloat16


def loader_for(layout):
    os.environ['LTX_SAMPLER_PLACEMENT'] = layout
    try:
        import host_embedding_resident_node as h
        h = importlib.reload(h)
    finally:
        os.environ.pop('LTX_SAMPLER_PLACEMENT', None)
    assert h.SAMPLER_PLACEMENT == layout
    return h


def placed(layout, h):
    """Exactly the branch load() runs for the layout."""
    saved = shard.LTXAVModel
    shard.LTXAVModel = StandInDiffusion
    try:
        model = ModelPatcher(StandInModel(), torch.device('cpu'), torch.device('cpu'))
        if h.SAMPLER_PLACEMENT == 'two-way':
            return h.apply_layer_shard(model, secondary_device='xpu:1', split_index=h.DECLARED_SPLIT_INDEX)
        return h.apply_layer_segments(model, h.SAMPLER_PLACEMENT)
    finally:
        shard.LTXAVModel = saved


def loader_case():
    for layout in LAYOUTS:
        h = loader_for(layout)
        model = placed(layout, h)
        ident = h.shared_identity((model, object(), object(), object()))
        json.dumps(ident)
        json.dumps(model.ltx_layer_shard_report)
        n = len(model.get_additional_models_with_key('ltx_layer_shard'))
        if layout == 'two-way':
            assert n == 1 and set(ident) == {'model_patcher', 'model', 'shard_patcher', 'shard_model',
                                             'video_vae', 'audio_vae', 'upscaler'}, ident
        else:
            assert n == len(shard.PLACEMENTS[layout]) - 1 == len(ident['shard_patchers']), ident
        devices = [str(model.load_device)] + [str(s.load_device) for s in
                                              model.get_additional_models_with_key('ltx_layer_shard')]
        assert devices == [seg[0] for seg in shard.PLACEMENTS[layout]], devices
    # a two-way report with an extra owner is refused, as before
    h = loader_for('two-way')
    model = placed('two-way', h)
    model.additional_models['ltx_layer_shard'].append(model.get_additional_models_with_key('ltx_layer_shard')[0])
    raises(lambda: h.shared_identity((model, 1, 2, 3)), 'too many values')
    os.environ['LTX_SAMPLER_PLACEMENT'] = 'shard9'
    try:
        import host_embedding_resident_node as hh
        raises(lambda: importlib.reload(hh), 'Unknown LTX_SAMPLER_PLACEMENT')
    finally:
        os.environ.pop('LTX_SAMPLER_PLACEMENT', None)
        importlib.reload(hh)


case('component loader: layout from the environment, placement, shared identity and receipt', loader_case)


def gate_case():
    saved = gcap.av_model.LTXAVModel
    gcap.av_model.LTXAVModel = StandInDiffusion
    try:
        for layout in LAYOUTS:
            model = placed(layout, loader_for(layout))
            assert gnode.check_shard_report(model.ltx_layer_shard_report) == layout
            diffusion, registry = gcap.validate_patcher(model)
            devs = [str(registry[('double_block', i)].device) for i in range(48)]
            want = [d for d, a, b in shard.PLACEMENTS[layout] for _ in range(a, b)]
            assert devs == want, layout
            runs = gcap.chain_runs(range(48), registry, 1)
            assert len(runs) == 48
            bad = dict(model.ltx_layer_shard_report)
            if layout == 'two-way':
                bad['split_index'] = 21
            else:
                bad['segments'] = [list(s) for s in shard.PLACEMENTS[layout]][:-1]
            raises(lambda: gnode.check_shard_report(bad))
    finally:
        gcap.av_model.LTXAVModel = saved


case('graph-capture gate: each layout accepted by the real checks; tampered reports refused', gate_case)


def sampler_case():
    for layout in LAYOUTS:
        model = placed(layout, loader_for(layout))
        guider = types.SimpleNamespace(model_patcher=model)
        devs = snode.placement_devices(guider)
        if layout == 'two-way':
            assert devs == []
            seg_devices = ['xpu:0', 'xpu:1']
        else:
            seg_devices = [s[0] for s in shard.PLACEMENTS[layout]]
            assert devs == seg_devices
        extra = [d for d in devs if d not in ('xpu:0', 'xpu:1')]
        assert extra == seg_devices[2:] if layout != 'two-way' else extra == []
        resident = [('LTXAV', 'xpu:0', 1), ('LatentUpsampler', 'xpu:0', 1), ('LTXAVTEModel_', 'xpu:2', 1),
                    ('_TextShard', 'xpu:3', 1), ('CausalDiffusionVAE', 'xpu:3', 1), ('AudioVAE', 'xpu:3', 1)]
        resident += [('_Shard', d, 1) for d in seg_devices[1:]]
        assert snode.residents_missing(resident, seg_devices) == []
        G = 2**30
        free = {'xpu:%d' % i: 3 * G for i in range(4)}
        assert snode.freeze_verdict(free, 0, True, missing=snode.residents_missing(resident, seg_devices)) == \
            (True, 'frozen')
        evicted = [r for r in resident if r[0] != 'LTXAVTEModel_']          # text encoder evicted
        miss = snode.residents_missing(evicted, seg_devices)
        assert miss == [('LTXAVTEModel_', 'xpu:2')]
        assert snode.freeze_verdict(free, 0, True, missing=miss) == (False, 'residents-missing')
        if layout != 'two-way':
            lost = [r for r in resident if r != ('_Shard', seg_devices[-1], 1)]
            assert snode.residents_missing(lost, seg_devices) == [('_Shard', seg_devices[-1])]


case('sampler: placement devices, extra streams, expected residents and freeze verdict per layout',
     sampler_case)


def decode_prereq_case():
    import comfy.model_management as mm
    saved = mm.load_models_gpu
    lookup = lambda: getattr(mm.load_models_gpu, '__globals__', {}).get('_LOAD_LOCK')
    try:
        mm.load_models_gpu = fast._original
        assert lookup() is None, 'without the fast path the decode probe must refuse (94b control)'
        mm.load_models_gpu = fast.fast_load_models_gpu
        assert lookup() is fast._LOAD_LOCK
    finally:
        mm.load_models_gpu = saved
    src = (HERE / 'pipeline_decode_node.py').read_text()
    assert "load_lock = getattr(mm.load_models_gpu, '__globals__', {}).get('_LOAD_LOCK')" in src


case('decode probe: needs the resident fast path, which only a pipelined prompt installs', decode_prereq_case)


def vae_residency_case():
    """94d: the serial capture pass decodes nothing (every prompt is a fill), so the VAEs
    stay on their offload device; the decode probe must load them explicitly first."""
    import ltx_decode_replica as rep
    run = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-shard4-94c-control')
    if run.is_dir():   # what the real 94c capture pass left: no VAE among the loaded models
        last = json.loads((run / 'pipeline-sampler-f94c-ctl-cap1-00.json').read_text())['loaded_models']
        assert not any('VAE' in m['model'] for m in last), last
        dec = [json.loads(p.read_text()) for p in sorted(run.glob('pipeline-decode-f94c-ctl-cap*.json'))]
        assert all(d['detail'].get('upstream_fill') for d in dec), 'a capture prompt decoded something'

    class StandInVAE:
        def __init__(self):
            self.first_stage_model = nn.Sequential(nn.Linear(2, 2), nn.Linear(2, 2))
            self.device = torch.device('meta')        # its card; weights still on the offload device (CPU)
            self.patcher = types.SimpleNamespace(model=self.first_stage_model)

    vaes = (StandInVAE(), StandInVAE())
    for v in vaes:
        assert rep.placement_offenders(v.first_stage_model, v.device), 'stand-in should start off its card'
    try:
        rep.build_replica(vaes[0], 'xpu:1', None, None)
        raise AssertionError('copied a moving model')
    except RuntimeError as error:
        assert 'not wholly on its device' in str(error)
    loads = []

    def fake_load(patchers, force_full_load=False):
        loads.append((len(patchers), force_full_load))
        for p in patchers:
            p.model.to('meta')

    for idle, frozen, text in ((False, False, 'idle pipeline'), (True, True, 'before the freeze')):
        try:
            rep.ensure_vaes_resident(fake_load, vaes, idle, frozen)
            raise AssertionError('residency step ran when it must not')
        except RuntimeError as error:
            assert text in str(error)
    assert loads == []
    out = rep.ensure_vaes_resident(fake_load, vaes, True, False)
    assert loads == [(2, True)] and not any(out['offending_tensors_after'].values())
    assert all(not rep.placement_offenders(v.first_stage_model, v.device) for v in vaes)
    src = (HERE / 'pipeline_decode_node.py').read_text()
    assert src.index('placement.ensure_vaes_resident(') < src.index('placement.build_replica(source')


case('decode probe precondition: VAEs left off-card by the capture pass are loaded explicitly first',
     vae_residency_case)


def frozen_vae_load_case():
    """94f, with ComfyUI's real model_management and LoadedModel bookkeeping on CPU: the
    VAE decode's own forced no-op load after the freeze (94e failure)."""
    import comfy.model_management as mm
    import ltx_graph_capture as g
    vae_module = nn.Sequential(nn.Conv2d(3, 4, 3), nn.Conv2d(4, 3, 3))
    patcher = ModelPatcher(vae_module, load_device=torch.device('cpu'), offload_device=torch.device('cpu'))
    calls = []
    saved_orig = fast._original
    fast._original = lambda models, *a, **k: (calls.append((len(models), k)), saved_orig(models, *a, **k))[1]
    try:
        g.LOADS_FROZEN[0] = False
        # the explicit residency step: a real full load through ComfyUI's loader
        fast.fast_load_models_gpu([patcher], memory_required=1 << 20, force_full_load=True)
        entry = next(l for l in mm.current_loaded_models if l.model is patcher)
        assert patcher.loaded_size() == patcher.model_size() > 0 and not entry.is_dead()
        assert fast.residency_reasons([patcher]) == []
        n_before = len(calls)
        g.LOADS_FROZEN[0] = True
        # exactly the decode's call: comfy/sd.py VAE.decode, force_full_load=self.disable_offload
        assert fast.fast_load_models_gpu([patcher], memory_required=1 << 20, force_full_load=True) is None
        assert fast.fast_load_models_gpu([patcher], 1 << 20) is None             # positional, not forced
        assert len(calls) == n_before, 'a frozen no-op load reached ComfyUI\'s loader'
        assert entry.currently_used is True
        # the loader would have to free memory: refused, nothing freed
        saved_gfm, saved_cpu = mm.get_free_memory, mm.is_device_cpu
        mm.get_free_memory = lambda dev=None, torch_free_too=False: 0
        mm.is_device_cpu = lambda dev: False
        try:
            raises(lambda: fast.fast_load_models_gpu([patcher], memory_required=1 << 20, force_full_load=True),
                   'would have to free memory')
        finally:
            mm.get_free_memory, mm.is_device_cpu = saved_gfm, saved_cpu
        # a model that is not wholly loaded: refused, never loaded
        other = ModelPatcher(nn.Linear(4, 4), load_device=torch.device('cpu'), offload_device=torch.device('cpu'))
        raises(lambda: fast.fast_load_models_gpu([other], force_full_load=True), 'not fully resident')
        raises(lambda: fast.fast_load_models_gpu([patcher], force_patch_weights=True), 'weight re-patch')
        # partially unloaded after the freeze (what an eviction would leave): refused
        patcher.partially_unload(patcher.offload_device, patcher.model_size() // 2) if hasattr(patcher, 'partially_unload') else None
        if patcher.loaded_size() != patcher.model_size():
            raises(lambda: fast.fast_load_models_gpu([patcher], force_full_load=True), 'loaded')
        assert len(calls) == n_before
    finally:
        g.LOADS_FROZEN[0] = False
        fast._original = saved_orig
        for l in list(mm.current_loaded_models):
            if l.model is patcher:
                mm.current_loaded_models.remove(l)


case('post-freeze VAE decode load (real ComfyUI bookkeeping on CPU): resident no-op passes without the loader; '
     'memory shortfall, partial or missing models refused', frozen_vae_load_case)


def quiescence_case():
    import threading
    import time as _t
    import ltx_pipeline as p
    p.clear()
    gate = threading.Event()
    p.submit('decode', 945000, lambda: gate.wait(5))
    _t.sleep(0.2)
    assert p.busy() == 1 and p.running() == 1
    p.clear()                                   # a latched failure drops the job ...
    assert p.busy() == 0 and p.running() == 1   # ... but its worker is still executing it
    gate.set()
    for _ in range(50):
        if p.running() == 0:
            break
        _t.sleep(0.05)
    assert p.running() == 0
    sh = (HERE / 'run-campaign-94f.sh').read_text()
    assert "d.get('pipeline_busy')==0 and d.get('pipeline_running')==0" in sh
    body = sh[sh.index('stop_when_proven() {'):sh.index('summarize() {')]
    assert body.index('if pipeline_idle_stable; then') < body.index('kill -INT $PID')


case('stop after a failed arm: running() still counts a dropped job; the runner needs 3 idle readings',
     quiescence_case)


def selfcheck_case():
    import importlib.util as iu
    sp = iu.spec_from_file_location('sc94f', HERE / 'selfcheck-94f.py')
    sc = iu.module_from_spec(sp)
    sp.loader.exec_module(sc)
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        root, run = Path(t), Path(t) / 'run'
        run.mkdir()
        for i, msg in enumerate((None, 'Decode-ahead failed: Model load refused after the capture freeze: '
                                       "['CausalDiffusionVAE']: not fully resident")):
            req = root / 'requests' / ('f94f-ctl-self-%02d' % i)
            req.mkdir(parents=True)
            msgs = [] if msg is None else [['execution_error', {'exception_message': msg, 'node_type': 'LTXPipelineDecode'}]]
            (req / 'history.json').write_text(json.dumps({'status': {'status_str': 'success' if msg is None else 'error',
                                                                     'messages': msgs}}))
        (run / 'load-refused-1-2.json').write_text(json.dumps({'time': 100.0, 'models': ['CausalDiffusionVAE'],
                                                               'reason': 'not fully resident'}))
        probs = sc.check(root, run, 'f94f-ctl-self', 50.0)
        kinds = sorted(p['kind'] for p in probs)
        assert kinds == ['load refused', 'load refused'], probs
        assert any(p.get('models') == ['CausalDiffusionVAE'] for p in probs)
        assert sc.check(root, run, 'f94f-ctl-self', 200.0)[0]['prompt'] == 'f94f-ctl-self-01'
        assert sc.classify('Block 3: captures are frozen for timed arms') == 'sampler capture refused'


case('self-check report names the refused model or graph', selfcheck_case)


def order_case():
    sh = (HERE / 'run-campaign-94f.sh').read_text()
    body = sh[sh.index('# ---- 1. text-window probe'):]
    marks = ['run-text-window-probe.py', 'arm f94f-$TAG-cap$k pipe-samp2-tsh-win', 'sampler-capture-coverage.json',
             'run-decode-probe.py', 'sampler-capture-freeze.json', 'arm f94f-$TAG-self pipe-samp2-tsh-rep-wlean',
             'selfcheck-94f.py', 'arm f94f-$TAG-probe pipe-samp2-tsh-win',
             'arm f94f-$TAG-timed pipe-samp2-tsh-rep-wlean']
    pos = [body.index(m) for m in marks]
    assert pos == sorted(pos), list(zip(marks, pos))
    if PACKET.is_dir():
        g = lambda n: json.loads((PACKET / 'graphs' / n).read_text())
        classes = lambda n: {v['class_type']: v['inputs'] for v in g(n).values()}
        win = classes('graph-capture-all48-pipe-samp2-tsh-win.json')
        assert win['LTXResidentFastPath']['mode'] == 'fast' and win['LTXGraphCaptureGate']['mode'] == 'graph'
        assert win['LTXPipelineTextEncode']['mode'] == 'pipeline-window'
        assert 'LTXResidentFastPath' not in classes('decode-replica-probe.json')
        assert 'LTXResidentFastPath' not in classes('text-window-probe.json')
        assert classes('text-window-probe.json')['LTXTextEncoderGraphGate']['mode'] == 'graph-shard'
        assert set(classes('sampler-capture-coverage.json')) == {'LTXSamplerCaptureCoverage'}
        rep = classes('graph-capture-all48-pipe-samp2-tsh-rep-wlean.json')
        assert rep['LTXPipelineDecode']['mode'] == 'pipeline-replica'   # needs the decode probe
        assert rep['LTXPipelineSampler']['mode'] == 'pipeline-lean'


case('runner order: text probe < capture pass < coverage < decode probe < freeze < placement probe < timed',
     order_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)

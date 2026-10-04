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

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-shard4-94c')
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


def order_case():
    sh = (HERE / 'run-campaign-94c.sh').read_text()
    body = sh[sh.index('# ---- 1. text-window probe'):]
    marks = ['run-text-window-probe.py', 'arm f94c-$TAG-cap$k pipe-samp2-tsh-win', 'sampler-capture-coverage.json',
             'run-decode-probe.py', 'sampler-capture-freeze.json', 'arm f94c-$TAG-probe pipe-samp2-tsh-win',
             'arm f94c-$TAG-timed pipe-samp2-tsh-rep-wlean']
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

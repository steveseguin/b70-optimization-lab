#!/usr/bin/env python3
"""Prepare source-only loader deltas; never import Torch or touch a runtime."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-02')
OUT = LANE / 'data/loader-memory-candidate-02'
manifest_bytes = (PACKET / 'manifest.json').read_bytes()
EXPECTED_PARENT_MANIFEST = 'f1fc467a4620caabac9065e72fb7fd1628db437d1c977c86237bb0378ef8f952'
assert hashlib.sha256(manifest_bytes).hexdigest() == EXPECTED_PARENT_MANIFEST, 'parent packet identity changed'
manifest = json.loads(manifest_bytes)
OUT.mkdir(exist_ok=False)


def replace_once(text, old, new):
    assert text.count(old) == 1, ('source anchor count', text.count(old), old)
    return text.replace(old, new, 1)


def prepare(relative, change, patch_name):
    original = (PACKET / relative).read_bytes()
    assert hashlib.sha256(original).hexdigest() == manifest['files'][relative]
    before = original.decode()
    after = change(before)
    ast.parse(after)
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(after)
    patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                       fromfile='a/' + relative, tofile='b/' + relative))
    patch_path = OUT / patch_name
    patch_path.write_text(patch)
    return {'path': relative, 'before_sha256': hashlib.sha256(original).hexdigest(),
            'after_sha256': hashlib.sha256(after.encode()).hexdigest(),
            'patch': patch_name, 'patch_sha256': hashlib.sha256(patch.encode()).hexdigest()}


def diffusion_change(text):
    old = '    model.load_model_weights(new_sd, "", assign=model_patcher.is_dynamic())\n'
    new = '''    native_assign = model_options.get("ltx_native_bf16_assign", False)
    if native_assign:
        if (model_patcher.is_dynamic() or comfy.memory_management.aimdo_enabled
            or custom_operations is not None or model_config.quant_config is not None
            or model_config.unet_config.get("image_model") != "ltxav"
            or unet_dtype != torch.bfloat16 or offload_device.type != "cpu"):
            raise RuntimeError("Native LTX assignment requires static CPU BF16 construction")
        targets = model.diffusion_model.state_dict()
        if targets.keys() != new_sd.keys():
            raise RuntimeError("Native LTX assignment requires complete matching state keys")
        report = {"policy": "ltx_native_bf16_assign", "assigned_source_bytes": 0,
                  "converted_destination_bytes": 0, "dtype_conversions": {}}
        for key, value in new_sd.items():
            target = targets[key]
            if (type(value) is not torch.Tensor or value.device.type != "cpu"
                or target.device.type != "cpu" or value.shape != target.shape
                or value.layout != torch.strided or target.layout != torch.strided
                or value.stride() != target.stride()):
                raise RuntimeError("Native LTX assignment layout mismatch: " + key)
            if value.dtype != target.dtype:
                report["dtype_conversions"][key] = [str(value.dtype), str(target.dtype)]
                report["converted_destination_bytes"] += target.nbytes
                # Preserve assign=False's destination dtype, including F32 tables.
                new_sd[key] = value.to(dtype=target.dtype)
            else:
                report["assigned_source_bytes"] += value.nbytes
        del targets
        model_patcher._ltx_native_assign_report = report
    model.load_model_weights(new_sd, "", assign=model_patcher.is_dynamic() or native_assign)
'''
    return replace_once(text, old, new)


def resident_change(text):
    text = replace_once(text, '\n_encoder_variant = None\n', '\n_encoder_variant = None\n_loader_policy = None\n')
    text = replace_once(text,
        "'optional': {'encoder_variant': (['control', 'crop', 'small_state', 'combined'], {'default': 'control'})}}",
        "'optional': {'encoder_variant': (['control', 'crop', 'small_state', 'combined'], {'default': 'control'}),\n"
        "                             'loader_policy': (['baseline', 'assign', 'assign_preload'], {'default': 'baseline'})}}")
    text = replace_once(text, 'def load(self, placement, encoder_variant="control"):',
                        'def load(self, placement, encoder_variant="control", loader_policy="baseline"):')
    text = replace_once(text,
        'global _components, _placement, _encoder_variant, _generation, _verification_sha256',
        'global _components, _placement, _encoder_variant, _loader_policy, _generation, _verification_sha256')
    text = replace_once(text, "        assert placement in ['single', 'separate', 'split']\n",
        "        assert placement in ['single', 'separate', 'split']\n"
        "        assert loader_policy in ['baseline', 'assign', 'assign_preload']\n"
        "        assert loader_policy == 'baseline' or placement == 'split', 'loader candidate requires split placement'\n")
    text = replace_once(text, 'and encoder_variant == _encoder_variant:',
                        'and encoder_variant == _encoder_variant and loader_policy == _loader_policy:')
    text = replace_once(text, '            _encoder_variant = None\n',
                        '            _encoder_variant = None\n            _loader_policy = None\n')
    text = replace_once(text,
        "        model = nodes.UNETLoader().load_unet('ltx-2.5-22b-distilled-transformer-bf16.safetensors', 'default')[0]\n",
        '''        if loader_policy == 'baseline':
            model = nodes.UNETLoader().load_unet('ltx-2.5-22b-distilled-transformer-bf16.safetensors', 'default')[0]
        else:
            model_path = folder_paths.get_full_path_or_raise(
                'diffusion_models', 'ltx-2.5-22b-distilled-transformer-bf16.safetensors')
            model = comfy.sd.load_diffusion_model(model_path,
                model_options={'ltx_native_bf16_assign': True}, disable_dynamic=True)
        if loader_policy == 'assign_preload':
            model = apply_layer_shard(model, secondary_device='xpu:1')
            # Free CPU transformer storage before constructing the large encoder.
            comfy.model_management.load_models_gpu(
                [model] + model.get_nested_additional_models(), force_full_load=True)
            model.verify_placement()
''')
    text = replace_once(text, "        if placement == 'split':\n            model = apply_layer_shard(model, secondary_device='xpu:1')",
                        "        if placement == 'split' and loader_policy != 'assign_preload':\n            model = apply_layer_shard(model, secondary_device='xpu:1')")
    text = replace_once(text, '        _encoder_variant = encoder_variant\n',
                        '        _encoder_variant = encoder_variant\n        _loader_policy = loader_policy\n')
    text = replace_once(text, "        receipt = {'placement': placement, 'encoder_variant': encoder_variant,\n",
                        "        receipt = {'placement': placement, 'encoder_variant': encoder_variant,\n"
                        "                   'loader_policy': loader_policy,\n"
                        "                   'native_assign': getattr(model, '_ltx_native_assign_report', None),\n")
    return text


changes = [prepare('source/comfy/sd.py', diffusion_change, 'ltx-native-bf16-assign.patch'),
           prepare('source/scripts/resident_node.py', resident_change, 'ltx-transformer-preload.patch')]
graphs = {}
for policy in ('baseline', 'assign', 'assign_preload'):
    graph = json.loads((PACKET / 'graphs/compiler-eager.json').read_text())
    graph['420']['inputs']['loader_policy'] = policy
    name = 'graph-' + policy + '.json'
    content = json.dumps(graph, indent=2) + '\n'
    (OUT / name).write_text(content)
    graphs[name] = hashlib.sha256(content.encode()).hexdigest()
report = {'status': 'source-only-candidate-not-deployed-not-numerically-tested',
          'parent_packet': str(PACKET), 'parent_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
          'source_commit': manifest['source_commit'], 'changes': changes, 'graphs': graphs,
          'checks': ['parent source SHA256s match pinned packet manifest', 'candidate Python AST parses'],
          'torch_imported': False, 'weights_loaded': False, 'runtime_touched': False,
          'required_before_runtime': ['review candidate patches', 'small CPU mixed-dtype copy-versus-assignment exactness test',
              'independent resolution of active device fault; no automatic retry',
              'prepare a separately pinned runtime packet, bind loader policy in run identity',
              'unique capture/preview/diagnostic names in each graph',
              'all original four-output parity gates and RSS/VmHWM comparison']}
(OUT / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'output': str(OUT), 'status': report['status'], 'changes': changes}, indent=2))

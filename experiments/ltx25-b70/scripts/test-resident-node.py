"""CPU-only retention/gate test with model loading and device work mocked."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, '/home/steve/src/ComfyUI-ltx25-baseline')
sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram']
import comfy.options
comfy.options.enable_args_parsing()
import torch
import resident_node as mod

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / 'speed-server').mkdir()
    gate = root / 'model-verification.json'
    gate.write_text(json.dumps({'status': 'passed'}))
    model = lambda *a, **k: (SimpleNamespace(load_device=torch.device('xpu:0')),)
    clip = lambda **k: SimpleNamespace(patcher=SimpleNamespace(load_device=k['model_options'].get('load_device', torch.device('xpu:0'))))
    vae = lambda *a, **k: (SimpleNamespace(device=torch.device('xpu:0')),)
    def separate_vae(**kwargs):
        return SimpleNamespace(device=kwargs['device'], throw_exception_if_invalid=lambda: None)
    with patch.object(mod, 'ROOT', root), \
         patch.object(mod.nodes.UNETLoader, 'load_unet', side_effect=model) as model_load, \
         patch.object(mod.comfy.sd, 'load_clip', side_effect=clip), \
         patch.object(mod.nodes.VAELoader, 'load_vae', side_effect=vae), \
         patch.object(mod.comfy.sd, 'VAE', side_effect=separate_vae), \
         patch.object(mod.comfy.utils, 'load_torch_file', return_value=({}, {})), \
         patch.object(mod.folder_paths, 'get_full_path_or_raise', side_effect=lambda category, name: '/verified/' + name), \
         patch.object(mod.folder_paths, 'get_folder_paths', return_value=[]), \
         patch.object(mod.LatentUpscaleModelLoader, 'execute', return_value=(object(),)), \
         patch.object(mod.comfy.model_management, 'unload_all_models') as unload, \
         patch.object(mod.comfy.model_management, 'cleanup_models_gc'):
        node = mod.LTXResidentComponents()
        a = node.load('single')
        b = node.load('single')
        assert a is b and model_load.call_count == 1
        assert len(a) == 5
        c = node.load('separate')
        assert model_load.call_count == 2 and unload.call_count == 1
        assert c is node.load('separate')
        assert str(c[1].patcher.load_device) == 'xpu:2'
        assert [str(v.device) for v in c[2:4]] == ['xpu:3', 'xpu:3']
        gate.write_text(json.dumps({'status': 'passed', 'changed': True}))
        try:
            node.load('separate')
        except AssertionError:
            pass
        else:
            raise AssertionError('stale verification accepted')
        assert model_load.call_count == 2
print('PASS: only component objects retained; deliberate placement change reloads; stale verification rejected; no GPU work')

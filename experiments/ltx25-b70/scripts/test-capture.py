"""CPU-only evidence roundtrip test, including native BF16 preservation."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types

import torch
from safetensors.torch import load_file

with tempfile.TemporaryDirectory() as directory:
    sys.modules['folder_paths'] = types.SimpleNamespace(get_output_directory=lambda: directory)
    sys.modules['server'] = types.SimpleNamespace(PromptServer=types.SimpleNamespace(
        instance=types.SimpleNamespace(app=types.SimpleNamespace(middlewares=[]))))
    path = Path(__file__).with_name('capture_node.py')
    spec = importlib.util.spec_from_file_location('capture_node', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    node = mod.LTXBaselineCapture()
    image = torch.arange(24, dtype=torch.float32).reshape(2, 2, 2, 3) / 23
    latent = torch.tensor([1.0, 1.0078125, -2.5], dtype=torch.bfloat16)
    wave = torch.tensor([[[0.1, -0.1]]])
    for name in ['a', 'b']:
        node.capture(image, {'samples': latent}, {'samples': latent.clone()},
                     {'waveform': wave, 'sample_rate': 24000}, name)
    root = Path(directory) / 'validation'
    a, b = [json.loads((root / name / 'summary.json').read_text()) for name in ['a', 'b']]
    assert a['tensors'] == b['tensors']
    restored = load_file(str(root / 'a/tensors.safetensors'))
    assert torch.equal(restored['images'], image)
    assert restored['video_latent'].dtype == torch.bfloat16
    assert torch.equal(restored['video_latent'], latent)
    changed = latent.clone()
    changed[1] = 1.015625
    node.capture(image, {'samples': changed}, {'samples': latent},
                 {'waveform': wave, 'sample_rate': 24000}, 'c')
    c = json.loads((root / 'c/summary.json').read_text())
    assert c['tensors']['video_latent']['sha256'] != a['tensors']['video_latent']['sha256']
    try:
        node.capture(image, {'samples': latent}, {'samples': latent},
                     {'waveform': wave, 'sample_rate': 24000}, 'a')
    except FileExistsError:
        pass
    else:
        raise AssertionError('existing evidence was overwritten')
print('PASS: exact BF16/FP32 roundtrip, repeat identity, one-ULP detection, overwrite refusal')

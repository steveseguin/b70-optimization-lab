"""Local output node: retain exact tensors without modifying generation."""
import hashlib
import json
from pathlib import Path

import torch
import folder_paths
from safetensors.torch import save_file


class LTXBaselineCapture:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'images': ('IMAGE',), 'video_latent': ('LATENT',),
                             'audio_latent': ('LATENT',), 'audio': ('AUDIO',),
                             'run_name': ('STRING', {'default': 'baseline-01'})}}

    RETURN_TYPES = ()
    FUNCTION = 'capture'
    OUTPUT_NODE = True
    CATEGORY = 'lab/validation'

    def capture(self, images, video_latent, audio_latent, audio, run_name):
        if not run_name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in run_name):
            raise ValueError('run_name must be a simple lowercase identifier')
        out = Path(folder_paths.get_output_directory()) / 'validation' / run_name
        out.mkdir(parents=True, exist_ok=False)
        tensors = {'images': images.detach().cpu().contiguous(),
                   'video_latent': video_latent['samples'].detach().cpu().contiguous(),
                   'audio_latent': audio_latent['samples'].detach().cpu().contiguous(),
                   'waveform': audio['waveform'].detach().cpu().contiguous()}
        report = {'run_name': run_name, 'sample_rate': audio['sample_rate'],
                  'deterministic_enabled': torch.are_deterministic_algorithms_enabled(),
                  'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
                  'tensors': {}}
        for name, t in tensors.items():
            report['tensors'][name] = {
                'dtype': str(t.dtype), 'shape': list(t.shape),
                'sha256': hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest(),
                'finite': bool(torch.isfinite(t).all()),
                'min': float(t.min()), 'max': float(t.max()), 'std': float(t.float().std()),
            }
        save_file(tensors, str(out / 'tensors.safetensors'))
        (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
        if not all(v['finite'] for v in report['tensors'].values()):
            raise RuntimeError('nonfinite generated output; evidence saved')
        return {'ui': {'text': [str(out / 'summary.json')]}}


NODE_CLASS_MAPPINGS = {'LTXBaselineCapture': LTXBaselineCapture}

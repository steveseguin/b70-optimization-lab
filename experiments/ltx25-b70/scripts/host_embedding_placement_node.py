"""Inactive post-encode metadata gate. Conditioning is returned unchanged."""
from pathlib import Path

from encoder_diagnostics import ROOT, _context, _exclusive_json, _identifier
from host_embedding_clip import HostEmbeddingCLIP, MODES


class LTXHostEmbeddingPlacementCheck:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',), 'conditioning': ('CONDITIONING',),
                'run_name': ('STRING', {'default': 'assign-unique-request-name'}),
                'encoder_mode': (list(MODES),)}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'check'
    CATEGORY = 'lab/validation'

    def check(self, clip, conditioning, run_name, encoder_mode):
        _identifier(run_name)
        run_dir, identity = _context(ROOT)
        if not isinstance(clip, HostEmbeddingCLIP) or clip._host_embedding.mode != encoder_mode:
            raise RuntimeError('Unexpected CLIP adapter/mode')
        group = clip._host_embedding
        if group.encodes != group.last_checked_encode + 1:
            raise RuntimeError('Each placement receipt requires exactly one new completed encoding')
        report = group.inventory(clip, require_loaded=True)
        report.update(identity)
        report.update(stage='post_encode', run_name=run_name,
                      passed=True, generated_output_cache=False, prompt_encoding_cache=False)
        _exclusive_json(run_dir / f'host-embedding-placement-{run_name}.json', report, ROOT)
        group.last_checked_encode = group.encodes
        return (conditioning,)


NODE_CLASS_MAPPINGS = {'LTXHostEmbeddingPlacementCheck': LTXHostEmbeddingPlacementCheck}

#!/usr/bin/env python3
"""Capture/numerics unit gate for actual LTXAV block, tiny CPU-only dimensions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import traceback

SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    os.environ['TORCHINDUCTOR_COMPILE_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    report = {
        'scope': 'Actual native LTXAV block class with synthetic tiny CPU weights; capture/unit gate only',
        'not_claimed': ['XPU qualification', 'full checkpoint quality', 'generation speed', 'output resolution change'],
        'source': str(SOURCE),
        'source_commit': subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_hashes': {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in (
            'comfy/ldm/lightricks/av_model.py', 'comfy/ldm/lightricks/model.py', 'comfy/ops.py')},
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'passed': False, 'rows': [], 'phase': 'import',
        'block_dimensions': {'video': 32, 'audio': 32, 'heads': 1, 'head_dim': 32, 'context_tokens': 8},
        'requested_video_tokens': [64, 256], 'audio_tokens': 26,
        'fullgraph': True, 'dynamic': False, 'guard_filter': None,
        'options': {'compile_threads': 1, 'emulate_precision_casts': True,
                    'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
                    'max_autotune': False, 'max_autotune_gemm': False},
    }
    with tempfile.TemporaryDirectory(prefix='ltx-native-block-cpu-') as cache:
        os.environ['TORCHINDUCTOR_CACHE_DIR'] = cache
        os.environ['TRITON_CACHE_DIR'] = str(Path(cache) / 'triton')
        try:
            sys.path.insert(0, str(SOURCE))
            sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram',
                        '--disable-comfy-compiler', '--use-pytorch-cross-attention', '--disable-xformers']
            import comfy.options
            comfy.options.enable_args_parsing()
            import torch
            import comfy.ops
            import comfy.model_management
            from torch._dynamo.utils import counters
            from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            torch.use_deterministic_algorithms(True, warn_only=False)
            report['torch'] = torch.__version__
            report['phase'] = 'instantiate'
            block = BasicAVTransformerBlock(
                v_dim=32, a_dim=32, v_heads=1, a_heads=1, vd_head=32, ad_head=32,
                v_context_dim=32, a_context_dim=32, apply_gated_attention=True,
                cross_attention_adaln=True, dtype=torch.bfloat16, device='cpu',
                operations=comfy.ops.manual_cast).eval()
            generator = torch.Generator(device='cpu').manual_seed(20260913)
            with torch.no_grad():
                for name, parameter in block.named_parameters():
                    value = torch.randn(parameter.shape, generator=generator, dtype=torch.float32) * 0.02
                    if name.endswith('q_norm.weight') or name.endswith('k_norm.weight'):
                        value += 1
                    parameter.copy_(value)
            report['parameter_count'] = sum(p.numel() for p in block.parameters())
            report['parameter_bytes'] = sum(p.numel() * p.element_size() for p in block.parameters())
            report['in_training'] = comfy.model_management.in_training
            counters.clear()
            compiled = torch.compile(block, backend='inductor', options=report['options'],
                                     fullgraph=True, dynamic=False)

            def inputs(tokens, seed):
                gen = torch.Generator(device='cpu').manual_seed(seed)
                def rand(*shape):
                    return torch.randn(shape, generator=gen, dtype=torch.bfloat16, device='cpu') * 0.1
                def rope(n):
                    angle = torch.randn((1, n, 1, 16), generator=gen, dtype=torch.float32)
                    c, s = angle.cos(), angle.sin()
                    return (torch.stack((torch.stack((c, -s), -1), torch.stack((s, c), -1)), -2), True)
                def video_time(width):
                    return CompressedTimestep(rand(1, 4, width), tokens // 4, per_frame=True)
                return ((rand(1, tokens, 32), rand(1, 26, 32)), {
                    'v_context': rand(1, 8, 32), 'a_context': rand(1, 8, 32),
                    'v_timestep': video_time(9 * 32), 'a_timestep': rand(1, 26, 9 * 32),
                    'v_pe': rope(tokens), 'a_pe': rope(26),
                    'v_cross_pe': rope(tokens), 'a_cross_pe': rope(26),
                    'v_cross_scale_shift_timestep': video_time(4 * 32),
                    'a_cross_scale_shift_timestep': rand(1, 26, 4 * 32),
                    'v_cross_gate_timestep': video_time(32),
                    'a_cross_gate_timestep': rand(1, 26, 32),
                    'v_prompt_timestep': rand(1, 1, 2 * 32),
                    'a_prompt_timestep': rand(1, 1, 2 * 32),
                    'transformer_options': {},
                })

            with torch.inference_mode():
                for tokens in (64, 256):
                    for seed in (17, 123):
                        x, kw = inputs(tokens, seed)
                        report['current_case'] = {'video_tokens': tokens, 'seed': seed}
                        report['phase'] = 'eager'
                        expected = block(tuple(t.clone() for t in x), **kw)
                        report['phase'] = 'compile_and_execute'
                        actual = compiled(tuple(t.clone() for t in x), **kw)
                        report['phase'] = 'repeat'
                        repeat = compiled(tuple(t.clone() for t in x), **kw)
                        outputs = []
                        for name, ref, got, again in zip(('video', 'audio'), expected, actual, repeat):
                            outputs.append({'name': name, 'shape': list(got.shape),
                                'dtype': str(got.dtype), 'finite': bool(torch.isfinite(got).all()),
                                'exact_eager': torch.equal(ref.view(torch.uint8), got.view(torch.uint8)),
                                'exact_repeat': torch.equal(got.view(torch.uint8), again.view(torch.uint8)),
                                'unequal_values': int((ref != got).sum()),
                                'max_abs_diff': float((ref.float() - got.float()).abs().max())})
                        report['rows'].append({**report['current_case'], 'outputs': outputs})
                report['phase'] = 'completed'
                report['dynamo_counters'] = {group: dict(count) for group, count in counters.items()}
                report['compiled_graphs'] = counters['stats']['unique_graphs']
                report['passed'] = all(o['finite'] and o['exact_eager'] and o['exact_repeat']
                                       for row in report['rows'] for o in row['outputs']) and report['compiled_graphs'] >= 2
        except Exception as exc:
            report['error_type'] = type(exc).__name__
            report['error'] = str(exc)
            report['traceback'] = traceback.format_exc()
        finally:
            report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as handle:
                json.dump(report, handle, indent=2)
                handle.write('\n')
    print(json.dumps({k: report[k] for k in ('passed', 'phase', 'max_rss_kib')}, indent=2))
    if report.get('error'):
        print(report['error'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

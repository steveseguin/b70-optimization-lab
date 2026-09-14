#!/usr/bin/env python3
"""Prepared CPU-only full tiny LTXAV block gate with opaque native RMS/activations and Inductor."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import traceback

SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')

def check_fault():
    if FAULT.exists():
        raise RuntimeError('Existing fault latch prohibits native work')



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True, help='New exclusive directory retaining compiler caches and graph receipts')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.evidence_dir.exists():
        raise FileExistsError(args.evidence_dir)
    os.environ['TORCHINDUCTOR_COMPILE_THREADS'] = '1'
    os.environ['TORCHINDUCTOR_CACHE_DIR'] = str(args.evidence_dir.resolve() / 'inductor-cache')
    os.environ['TRITON_CACHE_DIR'] = str(args.evidence_dir.resolve() / 'triton-cache')
    os.environ['OMP_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'
    options_path = Path(__file__).with_name('ltx_block_compile.py')
    options_ast = ast.parse(options_path.read_text())
    options = ast.literal_eval(next(n.value for n in options_ast.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'OPTIONS' for t in n.targets)))
    if options.get('compile_threads') != 1 or options.get('emulate_precision_casts') is not True or options.get('eager_numerics.division_rounding') is not True:
        raise RuntimeError('Original compiler options no longer match the reviewed precision policy')
    report = {
        'scope': 'Actual tiny CPU BF16 LTXAV block with private native RMS/activations FX rewrite and Inductor; unit gate only',
        'not_claimed': ['XPU qualification', 'full checkpoint quality', 'generation speed', 'output resolution change'],
        'source': str(SOURCE),
        'source_commit': subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_hashes': {p: hashlib.sha256((SOURCE / p).read_bytes()).hexdigest() for p in (
            'comfy/ldm/lightricks/av_model.py', 'comfy/ldm/lightricks/model.py', 'comfy/ops.py')},
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'passed': False, 'rows': [], 'graphs': [], 'torch_imported': False, 'phase': 'fault-gate',
        'block_dimensions': {'video': 32, 'audio': 32, 'heads': 1, 'head_dim': 32, 'context_tokens': 8},
        'requested_video_tokens': [64, 256], 'audio_tokens': 26,
        'fullgraph': True, 'dynamic': False, 'guard_filter': None,
        'backend': 'private-native-activations-inductor', 'fixture_script_sha256': hashlib.sha256(Path(__file__).with_name('census-ltx-rms-fx-cpu.py').read_bytes()).hexdigest(),
        'backend_source_sha256': hashlib.sha256(Path(__file__).with_name('ltx_native_activations_backend.py').read_bytes()).hexdigest(),
        'options_source_sha256': hashlib.sha256(options_path.read_bytes()).hexdigest(),
        'options': options, 'expected_rms_per_graph': 15,
        'rms_dependency_sha256': hashlib.sha256(Path(__file__).with_name('ltx_native_rms_backend.py').read_bytes()).hexdigest(),
        'expected_activations_per_graph': {'sigmoid': 6, 'gelu': 2},
        'evidence_directory': str(args.evidence_dir.resolve()),
        'compiler_environment': {k: os.environ[k] for k in ('TORCHINDUCTOR_COMPILE_THREADS', 'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')},
    }
    try:
        check_fault()
        args.evidence_dir.mkdir(parents=True, exist_ok=False)
        report['phase'] = 'import'
        sys.path.insert(0, str(SOURCE))
        sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram',
                    '--disable-comfy-compiler', '--disable-pinned-memory', '--disable-async-offload', '--use-pytorch-cross-attention', '--disable-xformers']
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        report['torch_imported'] = True
        import comfy.ops
        import comfy.model_management
        from torch._dynamo.utils import counters
        from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report['determinism'] = {'enabled': torch.are_deterministic_algorithms_enabled(),
                                 'warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
                                 'cpu_threads': torch.get_num_threads(),
                                 'interop_threads': torch.get_num_interop_threads()}
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
        import ltx_native_activations_backend as native_backend
        backend = native_backend.make_backend(options, args.evidence_dir / 'graphs', expected_count=15)
        compiled = torch.compile(block, backend=backend, fullgraph=True, dynamic=False)

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
                    check_fault()
                    x, kw = inputs(tokens, seed)
                    report['current_case'] = {'video_tokens': tokens, 'seed': seed}
                    report['phase'] = 'eager'
                    expected = block(tuple(t.clone() for t in x), **kw)
                    check_fault()
                    report['phase'] = 'native_activations_inductor_execute'
                    actual = compiled(tuple(t.clone() for t in x), **kw)
                    check_fault()
                    report['phase'] = 'repeat'
                    repeat = compiled(tuple(t.clone() for t in x), **kw)
                    outputs = []
                    for name, ref, got, again in zip(('video', 'audio'), expected, actual, repeat):
                        outputs.append({'name': name, 'shape': list(got.shape),
                            'dtype': str(got.dtype), 'stride': list(got.stride()), 'device': str(got.device), 'finite': bool(torch.isfinite(got).all()),
                            'exact_eager': torch.equal(ref.view(torch.uint8), got.view(torch.uint8)),
                            'exact_repeat': torch.equal(got.view(torch.uint8), again.view(torch.uint8)),
                            'unequal_values': int((ref != got).sum()),
                            'max_abs_diff': float((ref.float() - got.float()).abs().max())})
                    report['rows'].append({**report['current_case'], 'outputs': outputs})
                    if not all(o['finite'] and o['exact_eager'] and o['exact_repeat'] for o in outputs):
                        raise RuntimeError('Native RMS/activations tiny block failed exact eager/repeat parity')
            check_fault()
            report['phase'] = 'completed'
            report['dynamo_counters'] = {group: dict(count) for group, count in counters.items()}
            report['compiled_graphs'] = counters['stats']['unique_graphs']
            for path in sorted((args.evidence_dir / 'graphs').glob('graph-*.json')):
                row = json.loads(path.read_text())
                report['graphs'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                         'status': row['status'], 'rms_count': len(row.get('replacements', [])),
                                         'activation_counts': {kind: sum(r['kind'] == kind for r in row.get('activation_replacements', [])) for kind in ('sigmoid', 'gelu')}})
            if len(report['graphs']) != report['compiled_graphs'] or not all(g['status'] == 'compiled-native-activations-boundary' and g['rms_count'] == 15 and g['activation_counts'] == {'sigmoid': 6, 'gelu': 2} for g in report['graphs']):
                raise RuntimeError('Compiled graph receipts do not match the 15 RMS + 6 sigmoid + 2 GELU gate')
            report['passed'] = all(o['finite'] and o['exact_eager'] and o['exact_repeat']
                                   for row in report['rows'] for o in row['outputs']) and report['compiled_graphs'] == 2
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        report['error'] = str(exc)
        report['traceback'] = traceback.format_exc()
        if FAULT.exists():
            report['fault_sha256'] = hashlib.sha256(FAULT.read_bytes()).hexdigest()
    finally:
        report['torch_present_in_sys_modules'] = 'torch' in sys.modules
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

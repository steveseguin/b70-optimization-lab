#!/usr/bin/env python3
"""One bounded CPU capture case with the final native-pre_run lifecycle guard."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import traceback
import types

LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
PATCHES = ('ltx-block-compile-ownership-guard.patch', 'ltx-block-compile-pre-run-lifecycle-v2.patch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    os.environ.update(TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    report = {'scope': 'CPU lifecycle gate with native ModelPatcher.pre_run; one tiny native block compiled; no GPU/checkpoint/speed claim',
              'passed': False, 'phase': 'prepare', 'checks': [], 'patch_order': list(PATCHES)}
    paths = [Path(__file__), LANE / 'scripts/ltx_block_compile.py', LANE / 'scripts/ltx_layer_shard.py',
             LANE / 'scripts/test-ltx-block-compile-route.py', LANE / 'scripts/test-ltx-block-compile-cpu.py',
             SOURCE / 'comfy/model_patcher.py', SOURCE / 'comfy/ldm/lightricks/av_model.py']
    paths += [LANE / 'patches' / p for p in PATCHES]
    report['sha256s'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with tempfile.TemporaryDirectory(prefix='ltx-lifecycle-cpu-') as temporary:
        root = Path(temporary)
        os.environ['TORCHINDUCTOR_CACHE_DIR'] = str(root / 'inductor')
        os.environ['TRITON_CACHE_DIR'] = str(root / 'triton')
        try:
            (root / 'scripts').mkdir()
            target = root / 'scripts/ltx_block_compile.py'
            target.write_bytes((LANE / 'scripts/ltx_block_compile.py').read_bytes())
            for patch in PATCHES:
                path = LANE / 'patches' / patch
                subprocess.run(['git', 'apply', '--check', str(path)], cwd=root, check=True, timeout=30)
                subprocess.run(['git', 'apply', str(path)], cwd=root, check=True, timeout=30)
            candidate_source = target.read_text()
            report['effective_adapter_sha256'] = hashlib.sha256(candidate_source.encode()).hexdigest()
            sys.path.insert(0, str(SOURCE))
            sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                        '--disable-async-offload', '--disable-pinned-memory', '--use-pytorch-cross-attention', '--disable-xformers']
            import comfy.options
            comfy.options.enable_args_parsing()
            import torch
            from torch import nn
            import comfy.ops
            from comfy.model_patcher import ModelPatcher
            from comfy.patcher_extension import CallbacksMP
            from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep, LTXAVModel
            from ltx_layer_shard import LTXLayerShardedPatcher, _Shard, KEY, CACHE_KEY, _forward_transfers, _verify_placement
            from torch._dynamo.utils import counters
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            torch.use_deterministic_algorithms(True, warn_only=False)
            report['torch'] = torch.__version__
            report['seed'] = 17
            report['video_tokens'] = 64
            report['audio_tokens'] = 26
            report['compilation_executed'] = False
            mod = types.ModuleType('ltx_block_compile_lifecycle_candidate')
            mod.__file__ = str(target)
            sys.modules[mod.__name__] = mod
            exec(compile(candidate_source, str(target), 'exec'), mod.__dict__)
            ns = {'torch': torch, 'nn': nn, 'comfy': comfy,
                  'BasicAVTransformerBlock': BasicAVTransformerBlock, 'CompressedTimestep': CompressedTimestep}
            for file, name in [('test-ltx-block-compile-route.py', 'make_block'),
                               ('test-ltx-block-compile-cpu.py', 'inputs')]:
                tree = ast.parse((LANE / 'scripts' / file).read_text())
                function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
                exec(compile(ast.Module(body=[function], type_ignores=[]), file, 'exec'), ns)
            make_block, inputs = ns['make_block'], ns['inputs']
            cpu = torch.device('cpu')
            class TinyDiffusion(LTXAVModel):
                def __init__(self):
                    nn.Module.__init__(self)
                    self.transformer_blocks = nn.ModuleList([make_block() for _ in range(48)])
            class TinyModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.diffusion_model = TinyDiffusion()
                    self.current_patcher = None
                def get_dtype(self):
                    return torch.bfloat16
            parent = LTXLayerShardedPatcher.install(ModelPatcher(TinyModel(), cpu, cpu), cpu, cpu, 24)
            def check(value, label):
                if not value:
                    raise AssertionError(label)
                report['checks'].append(label)
            x, kwargs = inputs(64, 17)
            # One bounded capture case with the real bound guard/owner registry.
            # Compiler settings and numerical mapping are unchanged from CPU02.
            report['phase'] = 'one_bound_native_capture'
            mod.CompiledBlockRoute.__init__.__kwdefaults__['compiler'] = torch.compile
            real = mod.apply_block_compile(parent, 24)
            real_route = real.model_options['transformer_options']['patches_replace']['dit'][('double_block', 24)]
            check(type(real).pre_run is ModelPatcher.pre_run, 'native_pre_run_method')
            real.pre_run()
            check(real.model.current_patcher is real, 'current_executing_patcher_bound')
            options = __import__('comfy.utils', fromlist=['deepcopy_list_dict']).deepcopy_list_dict(real.model_options['transformer_options'])
            options['callbacks'] = real.callbacks
            options['wrappers'] = real.wrappers
            options.update(cond_or_uncond=[0], sigmas=torch.tensor([1.0]), sample_sigmas=torch.tensor([1., .5, 0.]))
            tree = ast.parse((SOURCE / 'comfy/ldm/lightricks/av_model.py').read_text())
            closure = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'block_wrap')
            native_ns = {'block': real_route.block}
            exec(compile(ast.Module(body=[closure], type_ignores=[]), 'native-block-wrap', 'exec'), native_ns)
            def run(chosen):
                def execute(*positional):
                    opts = positional[5]
                    opts[CACHE_KEY][('prior', cpu)] = (x[0], x[0])
                    values = {'img': tuple(t.clone() for t in x), 'attention_mask': None,
                              **kwargs, 'transformer_options': opts}
                    return chosen(values, {'original_block': native_ns['block_wrap']})['img']
                with torch.inference_mode():
                    return _forward_transfers(execute, None, None, None, None, None, options)
            report['options'] = mod.OPTIONS
            report['lifecycle_callback_present'] = options['callbacks'][CallbacksMP.ON_PRE_RUN][mod.LIFECYCLE_KEY][0] is real_route._lifecycle
            check(report['lifecycle_callback_present'], 'actual_lifecycle_callback_in_capture_registry')
            counters.clear()
            eager = run(real_route.original_route)
            report['compilation_executed'] = True
            actual = run(real_route)
            repeated = run(real_route)
            report['capture_case'] = {'video_tokens': 64, 'audio_tokens': 26, 'seed': 17, 'outputs': []}
            for name, expected, got, again in zip(('video', 'audio'), eager, actual, repeated):
                report['capture_case']['outputs'].append({'name': name,
                    'exact_eager': torch.equal(expected.view(torch.uint8), got.view(torch.uint8)),
                    'exact_repeat': torch.equal(got.view(torch.uint8), again.view(torch.uint8)),
                    'finite': bool(torch.isfinite(got).all())})
            check(all(r['exact_eager'] and r['exact_repeat'] and r['finite'] for r in report['capture_case']['outputs']),
                  'actual_bound_lifecycle_capture_exact_and_repeatable')
            check(counters['stats']['unique_graphs'] == 1 and counters['aot_autograd']['ok'] == 1 and not counters['graph_break'],
                  'one_compiled_graph_without_fallback')
            report['dynamo_counters'] = {k: dict(v) for k, v in counters.items()}
            real.cleanup()
            check(real.model.current_patcher is None, 'native_cleanup_clears_execution')
            report.update(passed=True, phase='completed')
        except Exception as error:
            report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
            if 'counters' in locals():
                report['dynamo_counters'] = {k: dict(v) for k, v in counters.items()}
        finally:
            report['max_parent_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as handle:
                json.dump(report, handle, indent=2)
                handle.write('\n')
    print(json.dumps({k: report[k] for k in ('passed', 'phase', 'max_parent_rss_kib')}, indent=2))
    if 'error' in report:
        print(report['error'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Bounded CPU metadata/dispatch attribution; no numerical block execution.

The private CPU process uses actual tiny native48-block registration and the
pinned adjacent-state adapter with an identity dispatch spy. This measures
metadata checks and CPU routing, not XPU generation or native kernel speed.
"""
import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import pstats
import resource
import statistics
import sys
import time
import traceback
import types

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
ADAPTER = LANE / 'patches/multiblock-adjacent-state-03/candidate.py'
ADAPTER_SHA = '79b4e76b10f49094f3ad11cc70ba62334c2ccf10e50960ac209fb5a0cdd2a584'
CALLS = 48 * 11


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true', required=True,
                        help='Required admission before any Torch/Comfy import')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--rounds', type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    require(args.cpu, 'Explicit --cpu required before native imports')
    output = args.output_dir.absolute()
    require(output.parent == ROOT and output.name.startswith('metadata-dispatch-cpu-') and
            not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)),
            'Use a fresh metadata-dispatch-cpu-* directory under the evidence root')
    require(not (ROOT / 'FAULT.json').exists(), 'Recorded fault prohibits native imports')
    require(sha(ADAPTER) == ADAPTER_SHA, 'Selected adjacent-state source changed')
    require('torch' not in sys.modules, 'Torch was imported before the CPU admission')
    output.mkdir(exist_ok=False)
    (output / 'tested-harness.py').write_bytes(Path(__file__).read_bytes())
    (output / 'tested-adapter.py').write_bytes(ADAPTER.read_bytes())
    paths = [Path(__file__), ADAPTER, LANE / 'scripts/ltx_layer_shard.py',
             LANE / 'scripts/ltx_native_activations_backend.py', LANE / 'scripts/ltx_native_rms_backend.py',
             SOURCE / 'comfy/model_patcher.py', SOURCE / 'comfy/ldm/lightricks/av_model.py',
             LANE / 'scripts/test-adjacent-state-reuse-cpu.py']
    report = {'schema': 'ltx.adjacent-metadata-cpu.v1', 'status': 'running', 'phase': 'before-native-import',
              'source_sha256s': {str(p): sha(p) for p in paths}, 'calls_per_round': CALLS,
              'timing_rounds': args.rounds, 'scope': 'Actual tiny native module metadata with fake compute and CPU-only routing; excludes node filesystem/JSON/census/counters and model kernels',
              'native_block_forward_executed': False, 'actual_compilation_executed': False,
              'xpu_generation_speed_qualified': False, 'stages': [{'video_tokens': 64, 'steps': 8}, {'video_tokens': 256, 'steps': 3}]}
    os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', TORCHINDUCTOR_COMPILE_THREADS='1',
                     TORCHINDUCTOR_CACHE_DIR=str(output / 'inductor'),
                     TRITON_CACHE_DIR=str(output / 'triton'))
    # Establish the same CPU guard used by the passed adjacent-state lifecycle
    # fixture before importing any Comfy module which can consult device state.
    sys.argv = [sys.argv[0], '--cpu', '--disable-dynamic-vram', '--disable-comfy-compiler',
                '--disable-async-offload', '--disable-pinned-memory',
                '--use-pytorch-cross-attention', '--disable-xformers']
    report['guard_argv'] = list(sys.argv)
    write(output / 'preregistration.json', report)
    candidate = None
    try:
        sys.path.insert(0, str(SOURCE))
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        from torch import nn
        import comfy.ops
        from comfy.model_patcher import ModelPatcher
        from comfy.ldm.lightricks.av_model import BasicAVTransformerBlock, CompressedTimestep, LTXAVModel
        from ltx_layer_shard import LTXLayerShardedPatcher, CACHE_KEY, KEY
        report['xpu_initialized_after_import'] = torch.xpu.is_initialized()
        require(not report['xpu_initialized_after_import'], 'XPU initialized unexpectedly')
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True, warn_only=False)
        report['torch'] = torch.__version__
        report['phase'] = 'construct-cpu-metadata'
        mod = types.ModuleType('adjacent_metadata_cpu_candidate')
        mod.__file__ = str(output / 'tested-adapter.py')
        sys.modules[mod.__name__] = mod
        exec(compile(ADAPTER.read_text(), mod.__file__, 'exec'), mod.__dict__)

        def make_block():
            # Same native class and32-wide architecture as the passed lifecycle
            # fixture. Values are never read by compute, so no RNG initialization.
            return BasicAVTransformerBlock(v_dim=32, a_dim=32, v_heads=1, a_heads=1,
                vd_head=32, ad_head=32, v_context_dim=32, a_context_dim=32,
                apply_gated_attention=True, cross_attention_adaln=True, dtype=torch.bfloat16,
                device='cpu', operations=comfy.ops.manual_cast).eval()

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

        cpu = torch.device('cpu')
        parent = LTXLayerShardedPatcher.install(ModelPatcher(TinyModel(), cpu, cpu), cpu, cpu, 21)
        blocks = parent.model.diffusion_model.transformer_blocks
        state = [tuple(block.parameters()) + tuple(block.buffers()) for block in blocks]
        require(all(len(values) == 84 for values in state), 'Tiny native block state census changed')
        require(all(t.device.type == 'cpu' and t.dtype == torch.bfloat16 for values in state for t in values),
                'Expected native BF16 metadata on CPU only')
        total_bytes = sum(t.numel() * t.element_size() for values in state for t in values)
        require(total_bytes <= 64 * 1024**2, 'Tiny model state exceeded64 MiB')
        report['tiny_state_bytes'] = total_bytes
        report['per_block_parameter_buffer_count'] = [len(values) for values in state]
        report['per_block_module_count'] = [sum(1 for _ in block.modules()) for block in blocks]
        created = []
        def fake_compiler(target, **kwargs):
            created.append(target)
            def identity_spy(x, **kw):
                return x
            return identity_spy
        candidate = mod.apply_blocks_compile(parent, tuple(range(48)),
            receipt_root=output / 'unused-native-graph-receipts', compiler=fake_compiler)
        require(len(created) == 48, 'Expected48 private compile targets passed only to the spy factory')
        registry = candidate.model_options['transformer_options']['patches_replace']['dit']
        routes = [registry[('double_block', i)] for i in range(48)]
        def gate_for(route):
            spy = route.compiled
            def simulated_gate(x, **kwargs):
                route._validate_execution()
                return spy(x, **kwargs)
            return simulated_gate
        for route in routes:
            route.compiled = gate_for(route)

        def inputs(tokens):
            def empty(*shape):
                return torch.empty(shape, dtype=torch.bfloat16, device='cpu')
            def video_time(width):
                return CompressedTimestep(empty(1, 4, width), tokens // 4, per_frame=True)
            def rope(length):
                return (torch.empty((1, length, 1, 16, 2, 2), dtype=torch.float32, device='cpu'), True)
            return {'img': (empty(1, tokens, 32), empty(1, 26, 32)),
                'attention_mask': None, 'v_context': empty(1, 8, 32), 'a_context': empty(1, 8, 32),
                'v_timestep': video_time(9 * 32), 'a_timestep': empty(1, 26, 9 * 32),
                'v_pe': rope(tokens), 'a_pe': rope(26), 'v_cross_pe': rope(tokens), 'a_cross_pe': rope(26),
                'v_cross_scale_shift_timestep': video_time(4 * 32),
                'a_cross_scale_shift_timestep': empty(1, 26, 4 * 32),
                'v_cross_gate_timestep': video_time(32), 'a_cross_gate_timestep': empty(1, 26, 32),
                'v_prompt_timestep': empty(1, 1, 2 * 32), 'a_prompt_timestep': empty(1, 1, 2 * 32),
                'transformer_options': {}}
        stage_inputs = (inputs(64), inputs(256))
        def dispatch_clip():
            for step in range(11):
                values = stage_inputs[0 if step < 8 else 1]
                values = {**values, 'transformer_options': {CACHE_KEY: {}}}
                for route in routes:
                    route(values, {})

        with torch.inference_mode():
            report['phase'] = 'separate-count-gate'
            candidate.pre_run()
            original_validate, original_bindings = mod.CompiledBlockRoute._validate, mod._registered_bindings
            counts = {'state': 0, 'registry': 0}
            def counted_validate(instance, **kwargs):
                counts['state'] += 1
                return original_validate(instance, **kwargs)
            def counted_bindings(*arguments, **keywords):
                counts['registry'] += 1
                return original_bindings(*arguments, **keywords)
            mod.CompiledBlockRoute._validate = counted_validate
            mod._registered_bindings = counted_bindings
            try:
                dispatch_clip()
            finally:
                mod.CompiledBlockRoute._validate = original_validate
                mod._registered_bindings = original_bindings
            require(counts == {'state': 3 * CALLS, 'registry': 3 * CALLS},
                    'Expected all three state/registry validation boundaries per invocation')
            report['separate_count_gate'] = counts
            write(output / 'count-gate.json', counts)
            candidate.pre_run()
            dispatch_clip()  # One full untimed warmup after removing count wrappers.
            timings = []
            report['phase'] = 'uninstrumented-timing'
            for number in range(args.rounds):
                require(not (ROOT / 'FAULT.json').exists(), 'Fault appeared; halt attribution')
                candidate.pre_run()  # Explicitly outside route-only timing.
                cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
                dispatch_clip()
                elapsed = time.perf_counter_ns() - wall_start
                cpu_elapsed = time.process_time_ns() - cpu_start
                row = {'round': number + 1, 'calls': CALLS, 'wall_ns': elapsed, 'process_cpu_ns': cpu_elapsed}
                timings.append(row)
                write(output / f'timing-{number+1:02d}.json', row)
            report['timings'] = timings
            report['median_route_dispatch_seconds'] = statistics.median(r['wall_ns'] for r in timings) / 1e9
            report['phase'] = 'separate-cprofile'
            require(not (ROOT / 'FAULT.json').exists(), 'Fault appeared; halt attribution')
            candidate.pre_run()
            profiler = cProfile.Profile()
            profiler.runcall(dispatch_clip)
            stats = pstats.Stats(profiler)
            profile_rows = [{'file': key[0], 'line': key[1], 'function': key[2],
                             'primitive_calls': value[0], 'total_calls': value[1],
                             'self_seconds': value[2], 'cumulative_seconds': value[3]}
                            for key, value in stats.stats.items()]
            profile_rows.sort(key=lambda r: r['cumulative_seconds'], reverse=True)
            write(output / 'cprofile-functions.json', profile_rows)
            with (output / 'cprofile-top.txt').open('x') as stream:
                pstats.Stats(profiler, stream=stream).sort_stats('cumulative').print_stats(50)
            report['profile_scope'] = 'One additional528-call pass; profiler times are not the uninstrumented timing samples'
            candidate.cleanup()
            candidate = None
        report['xpu_initialized_after_work'] = torch.xpu.is_initialized()
        require(not report['xpu_initialized_after_work'], 'XPU initialized unexpectedly')
        require(all(sha(path) == expected for path, expected in report['source_sha256s'].items()),
                'Pinned source changed during attribution')
        report.update(status='passed', phase='completed', total_dispatch_calls=CALLS * (3 + args.rounds))
    except BaseException as error:
        report.update(status='failed', error=repr(error), traceback=traceback.format_exc())
    finally:
        if candidate is not None:
            try:
                candidate.cleanup()
            except BaseException as error:
                report['cleanup_error'] = repr(error)
        report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write(output / 'result.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'phase', 'max_rss_kib')}, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

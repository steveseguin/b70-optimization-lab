"""Inactive CPU-only FX retargeting to the qualified private C++ ATen binary."""
import hashlib
import json
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve().parent
PARENTS = HERE.parent / 'native-cpp-ops-01/parents'
PINS = {'ltx_native_rms_backend.py': '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb',
        'ltx_native_activations_backend.py': '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'}
BINARY = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/native-cpp-ops-cpu-01/ltx_exact_cpp_cpu01.so')
BINARY_SHA = '6eee2a1379b818921a1bdf980493a6eab6746dc52e885deba39c9ccfe3870280'
OPTIONS = {'compile_threads': 1, 'emulate_precision_casts': True,
           'eager_numerics.division_rounding': True, 'triton.cudagraphs': False,
           'max_autotune': False, 'max_autotune_gemm': False}
FAULT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initialize():
    require(not FAULT.exists(), 'Fault latch prohibits native work')
    require(not torch.xpu.is_initialized(), 'CPU gate must not initialize XPU')
    for name, digest in PINS.items():
        require(sha(PARENTS / name) == digest, 'Frozen Python parent changed')
    require(sha(BINARY) == BINARY_SHA, 'Qualified CPU binary changed')
    sys.path.insert(0, str(PARENTS))
    import ltx_native_rms_backend as rms
    import ltx_native_activations_backend as activations
    require(Path(rms.__file__).resolve() == PARENTS / 'ltx_native_rms_backend.py' and
            Path(activations.__file__).resolve() == PARENTS / 'ltx_native_activations_backend.py', 'Python parent resolves elsewhere')
    require(not hasattr(torch.ops.ltx_exact_cpp_cpu01, 'rms'), 'Private CPU operators already registered')
    torch.ops.load_library(str(BINARY))
    torch.library.register_fake('ltx_exact_cpp_cpu01::rms')(rms._fake_native_rms)
    torch.library.register_fake('ltx_exact_cpp_cpu01::sigmoid')(activations._fake_native_sigmoid)
    torch.library.register_fake('ltx_exact_cpp_cpu01::gelu')(activations._fake_native_gelu)
    return rms, activations


def rewrite_cpp(gm):
    mapping = {torch.ops.ltx_exact_rms.native.default: ('rms', torch.ops.ltx_exact_cpp_cpu01.rms.default),
               torch.ops.ltx_exact_activations.sigmoid.default: ('sigmoid', torch.ops.ltx_exact_cpp_cpu01.sigmoid.default),
               torch.ops.ltx_exact_activations.gelu.default: ('gelu', torch.ops.ltx_exact_cpp_cpu01.gelu.default)}
    graph, environment, census = torch.fx.Graph(), {}, []
    original_code = gm.code
    for old in gm.graph.nodes:
        new = graph.node_copy(old, lambda node: environment[node])
        new.meta = dict(old.meta)
        environment[old] = new
        if old.op == 'call_function' and old.target in mapping:
            kind, target = mapping[old.target]
            new.target = target
            census.append({'node': old.name, 'kind': kind, 'before': str(old.target), 'after': str(target)})
    require({kind: sum(row['kind'] == kind for row in census) for kind in ('rms', 'sigmoid', 'gelu')} ==
            {'rms': 15, 'sigmoid': 6, 'gelu': 2}, 'C++ boundary replacement count changed')
    result = torch.fx.GraphModule(gm, graph)
    result.graph.lint(); result.recompile()
    require(gm.code == original_code, 'Original graph mutated')
    require({name: id(value) for name, value in gm.named_parameters()} ==
            {name: id(value) for name, value in result.named_parameters()}, 'Graph parameter identity changed')
    require({name: id(value) for name, value in gm.named_buffers()} ==
            {name: id(value) for name, value in result.named_buffers()}, 'Graph buffer identity changed')
    return result, census


def make_backend(options, directory, rms, activations):
    require(options == OPTIONS, 'Original compiler options required')
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=False)
    count = 0
    def compile_graph(gm, example_inputs, **kwargs):
        nonlocal count
        require(not FAULT.exists(), 'Fault latch prohibits compilation')
        require(not kwargs and not torch.is_grad_enabled(), 'Explicit backend options and inference required')
        require(not torch.xpu.is_initialized(), 'XPU unexpectedly initialized')
        require(sha(BINARY) == BINARY_SHA, 'CPU binary changed')
        count += 1
        require(count <= 2, 'Unexpected C++ graph recompile')
        report = {'schema': 'ltx.cpp-cpu-block-graph.v1', 'graph': count, 'status': 'started',
                  'options': dict(options), 'binary_sha256': BINARY_SHA, 'source_sha256': sha(Path(__file__))}
        original_code = gm.code
        try:
            normalized, rms_census = rms.rewrite_rms(gm, expected_count=15)
            python_graph, activation_census = activations.rewrite_activations(normalized, expected_activation_counts={'sigmoid': 6, 'gelu': 2})
            cpp_graph, cpp_census = rewrite_cpp(python_graph)
            require(gm.code == original_code, 'Dynamo graph mutated')
            report.update(replacements=rms_census, activation_replacements=activation_census, cpp_replacements=cpp_census)
            for name, text in [('before', gm.code), ('python-boundaries', python_graph.code), ('cpp-boundaries', cpp_graph.code)]:
                with (directory / f'graph-{count:03d}-{name}.py').open('x') as out:
                    out.write(text)
            result = torch._inductor.compile(cpp_graph, example_inputs, options=dict(options))
            report['status'] = 'compiled-cpp-cpu-boundaries'
            return result
        except BaseException as error:
            report.update(status='failed', error=repr(error)); raise
        finally:
            with (directory / f'graph-{count:03d}.json').open('x') as out:
                json.dump(report, out, indent=2); out.write('\n')
    return compile_graph

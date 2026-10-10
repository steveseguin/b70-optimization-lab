"""Small torch CPU module graph for transport tests, NEVER real model evidence.

Arithmetic uses the existing references deliberately: these tests check hooks,
state snapshots and replay/classification, not an independent math oracle.
Full model/MTP transactions, paged caches and TP/EP are not simulated.
"""
from contextlib import ExitStack
from pathlib import Path

import torch

from common import evaluate, flatten, token_hash
from extract_fixtures import Recorder

EAGER = {'enforce_eager': True, 'graph_mode': 'NONE', 'compile_mode': 'NONE', 'prefix_caching': False}


def mock_identity():
    # These labels cannot be accepted by native CLI (mock must be false there).
    artifact = {'path': 'pending.json', 'sha256': '0' * 64}
    return {'mock': True, 'comparator': {
        'runtime_commit': '0' * 40, 'image_digest': None,
        'build_manifest': artifact, 'overlay_manifest': artifact, 'kernel_binaries': [artifact],
        'compiler': 'synthetic CPU torch only', 'libraries': {'torch': torch.__version__},
        'environment': {'OMP_NUM_THREADS': '2'}, 'launch_flags': [],
        'dispatch': 'synthetic torch CPU modules; not vLLM', 'device_topology': 'CPU'},
        'model': 'synthetic', 'execution': EAGER}


class Operator(torch.nn.Module):
    def __init__(self, model, name, function, u, args, state_index=None):
        super().__init__()
        self.model, self.op_name, self.function, self.u = model, name, function, u
        self.arguments = args
        self.state_index = state_index
        if state_index is not None:
            self.register_buffer('state', args[state_index].clone())

    def normalized(self):
        args = list(self.arguments)
        if self.state_index is not None:
            args[self.state_index] = self.state
        return args

    def forward(self):
        result = evaluate(self.model, self.function, self.normalized(), {})
        if self.state_index is not None:
            # Deliberate in-place update tests that pre-hook snapshots survive.
            self.state.copy_(result[1])
        return result


def sample(shape, dtype, seed=7):
    return (torch.randn(shape, generator=torch.Generator(device='cpu').manual_seed(seed)) * .02).to(dtype)


class MockComparator(torch.nn.Module):
    def __init__(self, model, m):
        super().__init__()
        self.model, self.m = model, m
        d = torch.float16 if model == '27b' else torch.bfloat16
        x, w = sample((m, 8), d), sample((8, 8), torch.bfloat16)
        modules = []
        def add(name, func, u, args, state=None):
            modules.append(Operator(model, name, func, u, args, state))
        add('w8a16', 'linear', ['U1'] if model == '27b' else ['U2'],
            [x, (w.float()*32).to(torch.float8_e4m3fn), torch.full((1,1), 1/32, dtype=torch.bfloat16)])
        add('excluded_linear', 'linear', ['U2'], [x, w])
        add('rmsnorm', 'rmsnorm' if model == '27b' else 'norm', ['U3'] if model == '27b' else ['U1'], [x, w[0]])
        add('silu', 'silu', ['U3'] if model == '27b' else ['U1'], [x])
        # Width-4 convolution is one row per invocation. M here is the outer
        # graph's batch; the saved function has an explicit row-0 view.
        add('conv', 'conv_step' if model == '27b' else 'conv', ['U3', 'U4'] if model == '27b' else ['U1'],
            [x[0], sample((8,3), d), sample((8,1,4), torch.bfloat16)], 1)
        state_dtype = torch.float32 if model == '27b' else d
        add('gdn_recurrence', 'gdn_recurrence' if model == '27b' else 'recurrence', ['U4'] if model == '27b' else ['U1'],
            [sample((m,16,128), d), sample((m,16,128), d, 8), sample((m,48,128), d),
             sample((m,48), d), sample((m,48), d), sample((48,), torch.bfloat16),
             sample((48,), torch.bfloat16), sample((48,128,128), state_dtype)], 7)
        add('rope', 'rope', ['U5'] if model == '27b' else ['U3'],
            [sample((m,2,256), d), torch.arange(7, 7+m, dtype=torch.int64)])
        if model == '27b':
            add('residual', 'residual_add', ['U3'], [x, x.float()])
            add('attention', 'attention_output_gate', ['U5'], [x, x])
            add('argmax', 'stable_argmax', ['U6'], [x])
        else:
            add('qsa_pool', 'compress', ['U3'], [sample((8,128), d)])
            add('qsa_select', 'select', ['U3'], [sample((4,128), d), sample((2,128), d), 7, 8])
            add('router', 'route', ['U4'], [sample((m,512), d)])
            add('hc_combine', 'hc_combine', ['U5'], [sample((m,4,8), d), x, sample((m,4), d)])
            add('ple_ids', 'ple_ids', ['U6'], [list(range(10,10+m)), [5,6], [3,5,7], [11]*16, list(range(16))])
            ids = torch.arange(m*16, dtype=torch.int64).reshape(m,16)
            rows = {f'0:{i}': sample((160,), torch.float32).to(torch.float8_e4m3fn) for i in range(m*16)}
            # Callable PLE row lookup is represented declaratively for replay.
            op = Operator(model, 'ple_lookup', 'ple_lookup', ['U6'], [1, ids, {'$rows': rows}, torch.ones(1,dtype=d)])
            def ple_forward():
                values = op.arguments[2]['$rows']
                return evaluate(model, 'ple_lookup', [1, ids, lambda part, row: values[f'{part}:{row}'], op.arguments[3]], {})
            op.forward = ple_forward
            modules.append(op)
        # A draft projection, not a fake full MTP implementation; U7 remains
        # unqualified even when this recorded projection is exact.
        add('mtp_forward', 'linear', ['U7'], [x, w])
        self.ops = torch.nn.ModuleList(modules)

    def forward(self):
        outputs = [op() for op in self.ops]
        last = outputs[-1]
        # Tokens really derive from the output, not a hard-coded oracle return.
        return torch.argmax(last.float(), dim=-1).tolist()


def run_mock(root, model='27b', max_bytes=512*1024**2, chunk_bytes=1024**2):
    controls = [MockComparator(model, m) for m in (1,2,6)]
    expected_tokens = sum((c() for c in controls), [])
    oracle = {'rows': [{'prompt_id': f'mock-{i}', 'prompt_sha256': token_hash([i]),
                       'token_ids': expected_tokens, 'sha256': token_hash(expected_tokens)} for i in range(12)]}
    identity = mock_identity()
    recorder = Recorder(root, model, identity, dict(EAGER), oracle, 'mock-0', max_bytes, chunk_bytes)
    tokens = []
    for m in (1,2,6):
        graph = MockComparator(model, m)
        with ExitStack() as stack:
            for layer, op in enumerate(graph.ops):
                # Map every tensor output and recurrent state independently.
                # A dry reference call here is CPU-mock construction ONLY.
                preview = op()
                if op.state_index is not None:
                    op.state.copy_(op.arguments[op.state_index])
                names = flatten(preview)
                expected = {name: 'outputs:' + name for name in names}
                if op.state_index is not None:
                    # Same reference state is checked twice: returned output and
                    # the module buffer actually committed in place.
                    expected['result.1'] = 'state_after:state.value'
                    names.pop('result.1')
                spec = {'name': op.op_name, 'layer': layer, 'M': m, 'N': 8, 'K': 8,
                        'rows': list(range(m)), 'positions': list(range(7,7+m)), 'valid_rows': [True]*m,
                        'arithmetic_order': 'synthetic CPU reference, see reference hash; not device arithmetic',
                        'rounding_points': ['reference-defined; synthetic dimensions'], 'census_items': op.u,
                        'reference': op.function, 'expected': expected, 'location': f'mock.ops.{layer}', 'rank': 0}
                keep = set(names)
                stack.enter_context(recorder.hook(
                    op, spec, lambda mod,a,kw: (mod.normalized(), {}),
                    lambda mod,a,kw,result,keep=keep: {k:v for k,v in flatten(result).items() if k in keep},
                    lambda mod: {} if mod.state_index is None else {'value': mod.state}))
            tokens += graph()
    return recorder.finish(tokens)


if __name__ == '__main__':
    raise SystemExit('Use extract_fixtures.py --mock')

"""Patch01 byte gate. Import and --cpu do not import torch or touch devices.

The CPU check executes the actual source methods against byte-buffer mocks.
It proves copy/control behavior only. Candidate warmup runs the separate XPU
gate on the already-created TP communicator, before any client request. The
candidate selector is never changed underneath a captured graph.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from functools import wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[5]
CLEAN = Path('/home/steve/src/vllm-flashnext-a367-clean-20261016')
CANDIDATE = Path('/home/steve/src/vllm-flashnext-a367-glue01-20261017')
RELATIVE = 'vllm/distributed/device_communicators/xpu_communicator.py'
CLEAN_SHA = '8a30e5973e8025a68eb36cbb4438ca017ddfc58f18400fcc30dde2775acd7c3d'
CANDIDATE_SHA = '535aece99342e578a9785beb63e4bbe86dcc737269da6a7335061bf0b83bb5e2'
PATCH = ROOT / 'patches/flash-next-m2-glue-fusion-01-row-copy.patch'
PATCH_SHA = '9a31076b55f5e6298226c9caa8c2ddf34a0ed479508512ad70be7de089c1c912'
CCL_ENV = {'CCL_SYCL_ALLREDUCE_LL': 'twoshots',
           'CCL_SYCL_ALLREDUCE_LL_THRESHOLD': '4096',
           'CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD': '4294967296'}
WORKER_PINS = {
    'vllm/v1/worker/xpu_worker.py': 'dc0aa8e7a0e303e38fdaf2729d878e2c23678be1a2e56fd2d46599cf5181ad11',
    'vllm/v1/worker/gpu_worker.py': 'e7d59285879d3dce70d891b99e0e6892bd96ef93c3a4746b3fc723b5086df4d5',
}
PATTERNS = (
    ('zero', (0x0000,)), ('negative_zero', (0x8000,)),
    ('signed_zero', (0x0000, 0x8000)),
    ('positive', (0x3f80, 0x4000, 0x4040)),
    ('cancellation', (0x3f80, 0xbf80, 0x4000, 0xc000)),
    ('subnormal', (0x0001, 0x8001, 0x007f, 0x807f)),
    ('normal_boundary', (0x0080, 0x8080, 0x0081, 0x8081)),
    ('rounding', (0x3f80, 0x3b80, 0xbf80, 0xbb80)),
    ('large_finite', (0x7f7f, 0xff7f, 0x7e80, 0xfe80)),
    ('infinity', (0x7f80, 0xff80)),
    ('quiet_nan_payload', (0x7fc1, 0x7fff, 0xffc2, 0xffff)),
    ('signaling_nan_payload', (0x7f81, 0x7fbf, 0xff82, 0xffbf)),
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def method(source, namespace):
    """Compile only all_reduce, without importing the source module."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'XpuCommunicator')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                and n.name == 'all_reduce')
    for arg in node.args.args:
        arg.annotation = None
    node.returns = None
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<sealed-all-reduce>', 'exec'), namespace)
    return namespace['all_reduce']


def sources():
    old = (CLEAN / RELATIVE).read_bytes()
    new = (CANDIDATE / RELATIVE).read_bytes()
    require(digest(old) == CLEAN_SHA, 'clean communicator hash changed')
    require(digest(new) == CANDIDATE_SHA, 'candidate communicator hash changed')
    require(digest(PATCH.read_bytes()) == PATCH_SHA, 'patch01 hash changed')
    # The full export identity is enforced by the packet seal. Additionally
    # reverse precisely the two patch01 insertions, so a different candidate
    # method cannot silently become the CPU or runtime oracle.
    old_tree, new_tree = ast.parse(old), ast.parse(new)
    old_fn = next(n for n in ast.walk(old_tree) if isinstance(n, ast.FunctionDef)
                  and n.name == 'all_reduce')
    new_fn = next(n for n in ast.walk(new_tree) if isinstance(n, ast.FunctionDef)
                  and n.name == 'all_reduce')
    require(isinstance(new_fn.body[1], ast.If), 'candidate branch missing')
    del new_fn.body[1]
    require(ast.dump(old_fn) == ast.dump(new_fn), 'candidate fallback changed')
    return old.decode(), new.decode()


def payload(pattern, rows, width, rank=0):
    words = PATTERNS[pattern][1]
    # Rank shifts exercise cancellation across ranks; row shifts prevent an
    # accidental row swap from passing. Preserve all bit patterns verbatim.
    return b''.join(struct.pack('<H', words[(i + rank + i // width) % len(words)])
                    for i in range(rows * width))


class ByteTensor:
    """Minimal raw-byte mock, including views with a nonzero storage offset."""
    def __init__(self, data, shape, *, contiguous=True, device='xpu', dtype='bf16',
                 backing=None, offset=0, counters=None):
        self.shape, self.contiguous = shape, contiguous
        self.device, self.dtype = SimpleNamespace(type=device), dtype
        self.backing = bytearray(data) if backing is None else backing
        self.offset = offset
        self.counters = counters if counters is not None else {'clone': 0, 'copy': 0}

    def raw(self):
        return bytes(self.backing[self.offset:self.offset + 2 * self.shape[0] * self.shape[1]])

    def dim(self):
        return len(self.shape)

    def is_contiguous(self):
        return self.contiguous

    def clone(self):
        self.counters['clone'] += 1
        return ByteTensor(self.raw(), self.shape, contiguous=self.contiguous,
                          device=self.device.type, dtype=self.dtype, counters=self.counters)

    def __getitem__(self, item):
        start, stop, step = item.indices(self.shape[0])
        require(step == 1, 'mock only supports row slices')
        return ByteTensor(b'', (stop - start, self.shape[1]), contiguous=self.contiguous,
                          device=self.device.type, dtype=self.dtype, backing=self.backing,
                          offset=self.offset + start * self.shape[1] * 2,
                          counters=self.counters)

    def copy_(self, other):
        self.counters['copy'] += 1
        self.backing[self.offset:self.offset + len(other.raw())] = other.raw()
        return self


def cpu_gate():
    old, new = sources()
    variants = (
        ('eligible', {}), ('m1', {'rows': 1}), ('m3', {'rows': 3}),
        ('width', {'width': 128}), ('noncontiguous', {'contiguous': False}),
        ('world2', {'world': 2}), ('selector_off', {'selector': False}),
        ('dtype', {'dtype': 'fp32'}), ('cpu', {'device': 'cpu'}),
        ('threshold0', {'threshold': 0}), ('threshold1', {'threshold': 1}),
        ('threshold3', {'threshold': 3}),
    )
    rows = []
    for name, options in variants:
        config = dict(rows=2, width=2560, contiguous=True, world=4,
                      selector=True, dtype='bf16', device='xpu', threshold=2)
        config.update(options)
        for pattern in range(len(PATTERNS)):
            outcomes = []
            for source in (old, new):
                calls = []
                data = payload(pattern, config['rows'], config['width'])
                value = ByteTensor(data, (config['rows'], config['width']),
                                   contiguous=config['contiguous'], dtype=config['dtype'],
                                   device=config['device'])
                def reduce(tensor, group):
                    calls.append((tensor.shape, tensor.raw(), group))
                    # This is an exact byte transform, not a simulation or
                    # claim about floating-point/CCL reduction arithmetic.
                    raw = bytes(b ^ 0x5a for b in tensor.raw())
                    tensor.backing[tensor.offset:tensor.offset + len(raw)] = raw
                torch_mock = SimpleNamespace(bfloat16='bf16', empty_like=lambda x:
                    ByteTensor(bytes(len(x.raw())), x.shape, counters=x.counters,
                               dtype=x.dtype, device=x.device.type, contiguous=x.contiguous))
                fn = method(source, dict(torch=torch_mock,
                    dist=SimpleNamespace(all_reduce=reduce),
                    envs=SimpleNamespace(VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS=config['threshold']),
                    _Q38_M2_GLUE_ROW_COPY=config['selector']))
                result = fn(SimpleNamespace(world_size=config['world'], device_group='existing-tp'), value)
                require(value.raw() == data, f'{name}: input changed')
                require(result.backing is not value.backing, f'{name}: output aliases input')
                outcomes.append((result.raw(), calls, value.counters))
            require(outcomes[0][:2] == outcomes[1][:2], f'{name}: byte/row/call mismatch')
            if name == 'eligible':
                require(outcomes[0][2] == {'clone': 2, 'copy': 2}, 'reference copy counts')
                require(outcomes[1][2] == {'clone': 1, 'copy': 0}, 'candidate copy counts')
            else:
                require(outcomes[0][2] == outcomes[1][2], f'{name}: fallback counts changed')
            rows.append({'variant': name, 'pattern': PATTERNS[pattern][0], 'passed': True})
    return {'schema': 'a367-glue01-cpu-operator.v1', 'passed': True,
            'cases': rows, 'case_count': len(rows), 'device_qualified': False,
            'scope': 'Actual AST methods, byte-buffer mock; no CCL/device arithmetic proof',
            'clean_sha256': digest(old.encode()), 'candidate_sha256': digest(new.encode()),
            'patch_sha256': PATCH_SHA}


def validate_receipts(directory):
    records = []
    for rank in range(4):
        record = json.loads((Path(directory) / f'operator-rank-{rank}.json').read_text())
        require(record.get('rank') == rank and record.get('passed') is True,
                f'operator rank {rank} missing or failed')
        require(record.get('schema') == 'a367-glue01-device-operator.v1', 'operator schema')
        require(record.get('case_count') == 72 and record.get('all_ranks_passed') is True,
                'operator coverage incomplete')
        require(record.get('patch_sha256') == PATCH_SHA, 'operator patch mismatch')
        require(record.get('candidate_sha256') == CANDIDATE_SHA, 'operator candidate mismatch')
        require(record.get('clean_sha256') == CLEAN_SHA, 'operator reference mismatch')
        require(record.get('ccl_environment') == CCL_ENV, 'operator CCL configuration mismatch')
        require(record.get('graph_sizes') == [1, 2], 'operator graph sizes mismatch')
        cases = record.get('cases', [])
        expected = {(m, pattern, phase, repeat) for m in (1, 2)
                    for pattern, _ in PATTERNS
                    for phase, repeat in (('eager', None),
                        ('graph_replay_changed_input', 0), ('graph_replay_changed_input', 1))}
        require(len(cases) == 72 and {(row.get('rows'), row.get('pattern'), row.get('phase'),
                row.get('replay_index')) for row in cases} == expected, 'operator case matrix mismatch')
        for row in cases:
            require(row.get('passed') is True and row.get('input_immutable') is True
                    and row.get('output_fresh') is True, 'operator byte/alias failure')
            hashes = row.get('row_sha256_reference', [])
            require(len(hashes) == row['rows'] and hashes == row.get('row_sha256_candidate')
                    and all(isinstance(h, str) and len(h) == 64 and
                            all(c in '0123456789abcdef' for c in h) for h in hashes),
                    'operator row hash mismatch')
            require(isinstance(row.get('input_sha256'), str) and len(row['input_sha256']) == 64,
                    'operator input hash missing')
            if row['replay_index'] == 1:
                first = next(r for r in cases if r['rows'] == row['rows']
                             and r['pattern'] == row['pattern'] and r['replay_index'] == 0)
                require(first['row_sha256_reference'] == hashes
                        and first['input_sha256'] == row['input_sha256'], 'operator replay nondeterminism')
        metadata = record.get('collective_metadata', [])
        require(len(metadata) == 52, 'operator collective metadata missing')
        for label in ('reference', 'candidate'):
            for m in (1, 2):
                entries = [e for e in metadata if e.get('path') == label and e.get('rows') == m]
                offsets = [0, 5120] if m == 2 and label == 'candidate' else [0] * m
                expected_calls = [{'shape': [1, 2560], 'stride': [2560, 1],
                    'storage_offset_bytes': offset, 'payload_bytes': 5120,
                    'alignment_mod256': 0, 'same_group': True} for offset in offsets]
                require(len(entries) == 13 and all(e.get('calls') == expected_calls for e in entries),
                        'operator collective shape/stride/offset/group mismatch')
        require(record.get('failures') == [], 'operator failure list not empty')
        records.append(record)
    require(len({r['candidate_sha256'] for r in records}) == 1, 'rank source mismatch')
    return records


def run_device_gate(comm, directory):
    """Called only inside the admitted candidate server's existing 4-rank TP."""
    import torch
    import torch.distributed as dist
    import vllm.distributed.device_communicators.xpu_communicator as module

    old, new = sources()
    require(Path(module.__file__).resolve() == (CANDIDATE / RELATIVE).resolve(),
            'operator communicator import shadowed candidate source')
    require(comm.world_size == 4, 'operator gate requires exactly four ranks')
    require(module._Q38_M2_GLUE_ROW_COPY is True, 'candidate selector not active')
    require(module.envs.VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS == 2, 'row threshold changed')
    require({k: os.environ.get(k) for k in CCL_ENV} == CCL_ENV, 'CCL algorithm settings changed')
    reference = method(old, dict(module.__dict__))
    candidate = type(comm).all_reduce
    rank = dist.get_rank(group=comm.cpu_group)
    require(rank in range(4), 'operator rank out of range')
    cases, failures, metadata = [], [], []

    def raw(value):
        return value.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()

    def cpu_value(index, rows):
        data = payload(index, rows, 2560, rank)
        words = struct.unpack('<' + 'h' * (rows * 2560), data)
        return torch.tensor(words, dtype=torch.int16).reshape(rows, 2560).view(torch.bfloat16)

    @contextmanager
    def inspect_calls(label, rows):
        original = dist.all_reduce
        calls = []
        def observed(value, *args, **kwargs):
            calls.append({'shape': list(value.shape), 'stride': list(value.stride()),
                          'storage_offset_bytes': value.storage_offset() * value.element_size(),
                          'payload_bytes': value.numel() * value.element_size(),
                          'alignment_mod256': value.data_ptr() % 256,
                          'same_group': kwargs.get('group') is comm.device_group})
            return original(value, *args, **kwargs)
        dist.all_reduce = observed
        try:
            yield
        finally:
            dist.all_reduce = original
        offsets = [0, 5120] if rows == 2 and label == 'candidate' else [0] * rows
        expected = [{'shape': [1, 2560], 'stride': [2560, 1],
                     'storage_offset_bytes': offset, 'payload_bytes': 5120,
                     'alignment_mod256': 0, 'same_group': True} for offset in offsets]
        if calls != expected:
            failures.append(f'{label} M={rows} collective metadata differs: {calls}')
        metadata.append({'path': label, 'rows': rows, 'calls': calls})

    def check(index, rows, phase, input_, expected_input, a, b, replay_index=None):
        input_bytes, old_bytes, new_bytes = raw(input_), raw(a), raw(b)
        passed = (input_bytes == expected_input and old_bytes == new_bytes
                  and a.data_ptr() != input_.data_ptr()
                  and b.data_ptr() != input_.data_ptr())
        entry = {'rows': rows, 'pattern': PATTERNS[index][0], 'phase': phase,
                 'passed': passed, 'input_immutable': input_bytes == expected_input,
                 'output_fresh': a.data_ptr() != input_.data_ptr() and b.data_ptr() != input_.data_ptr(),
                 'replay_index': replay_index,
                 'row_sha256_reference': [digest(old_bytes[r*5120:(r+1)*5120]) for r in range(rows)],
                 'row_sha256_candidate': [digest(new_bytes[r*5120:(r+1)*5120]) for r in range(rows)],
                 'input_sha256': digest(expected_input)}
        if replay_index == 1:
            prior = cases[-1]
            if (prior['row_sha256_reference'] != entry['row_sha256_reference'] or
                    prior['row_sha256_candidate'] != entry['row_sha256_candidate']):
                passed = entry['passed'] = False
        cases.append(entry)
        if not passed:
            failures.append(f'byte/alias mismatch {phase} M={rows} {PATTERNS[index][0]}')

    for rows in (1, 2):
        input_ = cpu_value(0, rows).to(comm.device)
        for index in range(len(PATTERNS)):
            host = cpu_value(index, rows)
            input_.copy_(host)
            with inspect_calls('reference', rows):
                a = reference(comm, input_)
            with inspect_calls('candidate', rows):
                b = candidate(comm, input_)
            torch.xpu.synchronize()
            check(index, rows, 'eager', input_, raw(host), a, b)

        # Keep graph/input/output lifetimes stable. No host transfer, tensor
        # reads, synchronization, tracing or event timing occurs in capture.
        stream = torch.xpu.Stream()
        graphs, outputs = [], []
        for label, fn in (('reference', reference), ('candidate', candidate)):
            torch.xpu.synchronize()
            dist.barrier(group=comm.cpu_group)
            graph = torch.xpu.XPUGraph()
            with inspect_calls(label, rows):
                with torch.xpu.graph(graph, stream=stream):
                    output = fn(comm, input_)
            torch.xpu.synchronize()
            graphs.append(graph)
            outputs.append(output)
        for index in range(len(PATTERNS)):
            host = cpu_value(index, rows)
            for repeat in range(2):
                input_.copy_(host)
                torch.xpu.synchronize()
                for graph in graphs:
                    graph.replay()
                torch.xpu.synchronize()
                check(index, rows, 'graph_replay_changed_input', input_, raw(host),
                      *outputs, replay_index=repeat)

    statuses = [None] * 4
    dist.all_gather_object(statuses, not failures, group=comm.cpu_group)
    record = {'schema': 'a367-glue01-device-operator.v1', 'rank': rank,
              'passed': not failures and all(statuses), 'all_ranks_passed': all(statuses),
              'case_count': len(cases), 'cases': cases, 'failures': failures,
              'collective_metadata': metadata, 'graph_sizes': [1, 2],
              'ccl_environment': CCL_ENV, 'patch_sha256': PATCH_SHA,
              'clean_sha256': digest(old.encode()), 'candidate_sha256': digest(new.encode()),
              'scope': 'same initialized TP communicator; byte equality on every rank; no timed-client hooks',
              'algorithm_evidence': 'Frozen twoshots/4096 environment and unchanged row payload/stride/group; no device profiler',
              'pid': os.getpid()}
    path = Path(directory) / f'operator-rank-{rank}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)
    require(record['passed'], 'candidate byte operator gate failed; do not run clients')


def patch_worker(cls, get_comm, directory, run_gate=run_device_gate):
    if getattr(cls.compile_or_warm_up_model, '_a367_glue_gate', False):
        return
    original = cls.compile_or_warm_up_model
    @wraps(original)
    def warmup(self, *args, **kwargs):
        require(not getattr(self, '_a367_glue_gate_ran', False), 'operator gate may run only once')
        self._a367_glue_gate_ran = True
        run_gate(get_comm(), directory)
        return original(self, *args, **kwargs)
    warmup._a367_glue_gate = True
    cls.compile_or_warm_up_model = warmup


def install():
    if os.environ.get('Q38_M2_GLUE_ROW_COPY') != '1':
        return
    directory = os.environ.get('A367_GLUE_OPERATOR_RECEIPTS')
    require(bool(directory), 'candidate requires retained operator receipt directory')
    from vllm.distributed.parallel_state import get_tp_group
    from vllm.v1.worker.xpu_worker import XPUWorker
    for relative, expected in WORKER_PINS.items():
        require(digest((CANDIDATE / relative).read_bytes()) == expected, 'operator worker source drift')
    require(Path(inspect.getfile(XPUWorker)).resolve() ==
            (CANDIDATE / 'vllm/v1/worker/xpu_worker.py').resolve(), 'operator worker import shadowed source')
    patch_worker(XPUWorker, lambda: get_tp_group().device_communicator, directory)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu', action='store_true', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = cpu_gate()
    rendered = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, sort_keys=True))

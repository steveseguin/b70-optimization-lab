"""CPU metadata-only SPLIT1 audit. Run with python3 -B; stdout only.

No repository module is imported. No model payload, device, compiler or child
process is opened. Counts describe the proposed layout, not a device result.
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet45-merged3'
RUN = P / 'build/speed7-c4096-dr1-s23-cards01-gpu'
INPUTS = {}


def readonly(event, args):
    if event in ('subprocess.Popen', 'os.system', 'os.remove', 'os.rename',
                 'os.mkdir', 'os.rmdir', 'socket.__new__'):
        raise RuntimeError('metadata-only audit')
    if event == 'open':
        path, mode, flags = args
        if (mode and any(c in mode for c in 'wax+')) or flags & (1 | 2 | 64 | 512 | 1024):
            raise RuntimeError('writes forbidden')
        if isinstance(path, (str, bytes)) and os.fsdecode(path).startswith('/dev/'):
            raise RuntimeError('device paths forbidden')


sys.addaudithook(readonly)
assert sys.dont_write_bytecode, 'use python3 -B'
assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'use nice -n 19'
assert os.sched_getaffinity(0) <= set(range(4, 16)) | set(range(20, 32)), 'use taskset'


def read(path):
    data = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data


def load(path):
    return json.loads(read(path))


plans = [load(RUN / f'WS/run/ranks/rank{rank}/launch-plan.json') for rank in (0, 1)]
# SPEED6 headline and SPEED7 have the same logical DAG and buffer extents.
for rank in (0, 1):
    previous = load(P / f'build/speed6-c4096-dr1-s23-cards01-gpu/WS128/run/ranks/rank{rank}/launch-plan.json')
    assert plans[rank] == previous
launches = [node for plan in plans for node in plan['launches']]
by_label = {node['label']: node for node in launches}
buffers = {}
for plan in plans:
    for b in plan['buffers']:
        if b['name'] in buffers:
            assert buffers[b['name']] == b['bytes']
        buffers[b['name']] = b['bytes']

# Version every writer, including streams. Ignore error/active edges here:
# the dependency witness is numeric data, not the global sticky-error chain.
parents = collections.defaultdict(set)
for plan in plans:
    producer = {}
    for node in plan['launches']:
        label = node['label']
        for name in node['inputs']:
            if name not in ('active', 'error') and name in producer:
                parents[label].add(producer[name])
        for name in node['outputs']:
            producer[name] = label


def depends(later, earlier):
    todo, seen = [later], set()
    while todo:
        current = todo.pop()
        if current == earlier:
            return True
        if current not in seen:
            seen.add(current)
            todo.extend(parents[current])
    return False


kinds = collections.Counter()
witnesses = {}
for layer in range(48):
    prefix = f'blk.{layer}.'
    is_gdn = prefix + 'gdn.recurrence' in by_label
    kinds['gdn' if is_gdn else 'qsa'] += 1
    first = prefix + ('gdn.gated' if is_gdn else 'qsa.attention')
    chain = [first, prefix+'attention', prefix+'hc.f.norm', prefix+'hc.f.low',
             prefix+'hc.f.gate', prefix+'hc.f.mix', prefix+'router', prefix+'route',
             prefix+'expsgate', prefix+'expsact', prefix+'expsdown',
             prefix+'moe', prefix+'ffn.combine']
    assert all(depends(b, a) for a, b in zip(chain, chain[1:])), chain
    assert by_label[prefix+'attention']['outputs'] == [prefix+'attention', 'streams']
    assert by_label[prefix+'route']['outputs'] == [prefix+s for s in ('ids','prob','routes','routes.down')]
    if layer in (0, 1, 2, 3):
        witnesses[str(layer)] = chain
assert kinds == {'gdn': 36, 'qsa': 12}
assert 'blk.1.ple.add' in by_label
assert [n['label'] for n in launches if n['label'].endswith('expsgate.check')] == ['blk.2.expsgate.check']
assert 'blk.2.expsup.check' in by_label
assert 'blk.0.expsgate.check' not in by_label
assert depends('argmax', 'logits') and depends('logits', 'final.mix')

metadata = {}
for line in read(P / 'build/input/plan.tsv').decode().splitlines():
    row = line.split()
    if len(row) >= 10:
        metadata[row[1]] = dict(type=int(row[3]), dimensions=list(reversed(list(map(int, row[9:])))))
assert metadata['blk.0.ffn_gate_exps.weight']['type'] == 22
assert metadata['blk.2.ffn_gate_exps.weight']['type'] == 21
assert metadata['blk.2.attn_qkv.weight']['type'] == 8
assert metadata['blk.2.ssm_out.weight']['type'] == 14
assert collections.Counter(metadata[f'blk.{i}.ffn_gate_exps.weight']['type']
                           for i in range(48)) == {22: 47, 21: 1}
assert sum(node['label'].endswith(('.hc.a.low', '.hc.f.low'))
           or node['label'] == 'final.low' for node in launches) == 97
for node in launches:
    if node['label'].endswith(('.hc.a.low', '.hc.f.low')) or node['label'] == 'final.low':
        assert node['outputs'] == [node['label'], node['label'][:-3]+'act']

# Explicit head partition with the CURRENT packed h % 16 relationship.
head_owners = [[h for h in range(48) if (h % 16 < 8) == (rank == 0)] for rank in (0, 1)]
assert len(head_owners[0]) == len(head_owners[1]) == 24
assert sorted(head_owners[0] + head_owners[1]) == list(range(48))
for rank in (0, 1):
    assert {h % 16 for h in head_owners[rank]} == set(range(rank*8, (rank+1)*8))

header = 32  # epoch:u64, token/position/layer/phase/active/error:u32
route = sum(buffers['blk.0.'+s] for s in ('ids','prob','routes','routes.down'))
status = sum(buffers['blk.0.'+s+'.status'] for s in ('expsgate','expsup','expsdown'))
phases = [
    dict(name='E1 gated/y allgather', copies=2, ab=buffers['blk.0.gdn.gated']//2+header,
         ba=buffers['blk.0.gdn.gated']//2+header),
    dict(name='E2 fused streams allgather', copies=2, ab=buffers['streams']//2+header,
         ba=buffers['streams']//2+header),
    dict(name='E3 route agreement', copies=2, ab=route+header, ba=route+header),
    # No host route readback: both copy sizes must cover all ten local slots.
    dict(name='E4 expert slot allgather, fixed envelope', copies=2,
         ab=buffers['blk.0.expsdown']+status+header,
         ba=buffers['blk.0.expsdown']+status+header),
]
wire_layer = sum(r['ab']+r['ba'] for r in phases)
useful_layer = buffers['blk.0.gdn.gated'] + buffers['streams'] + buffers['blk.0.expsdown']
assert useful_layer == 83968 and wire_layer == 136304
head_wire = buffers['logits'] + 2*header
completion_wire = 2*(header+4)  # next_token plus header's sticky error

peer = load(ROOT / 'experiments/own-xpu-runtime/stage2/packet12-peer/cards2-3-20261011/native.json')
assert peer['passed'] and all(c['exact'] for c in peer['cases'])
medians = {}
for c in peer['cases']:
    key = ':'.join(str(c.get(k, '')) for k in ('kind','mode','bytes','direction'))
    medians[key] = statistics.median(s['wall_ns'] for s in c['samples']) / 1000
ab = medians['copy:peer:10240:A->B']
ba = medians['copy:peer:10240:B->A']
round_us = medians['exchange:peer:10240:'] / 60

summary = load(RUN / 'K2/run0/summary.json')
dispatch = load(RUN / 'K2/run0/dispatch-measured.json')
assert summary['passed'] and summary['final_dispatch'] == dispatch


def selected_ns(name, workload=None):
    c = summary['classes'][name]
    comparison = c['comparisons'][c['selected']]
    assert comparison['selection_timing_mode'] == 'reread'
    if workload:
        return comparison['workloads'][workload]['variants']['specialised']['execution_sum']['median_ns']
    return comparison['reread']['specialised']['execution_sum']['median_ns']


# Only shape-specific projection/route receipts; no generic norm/mix proxy.
replicated = [
    ('HC low + activation', 97, selected_ns('fusion:p39.hc-low-act')),
    ('HC attention gate', 48, selected_ns('gemv:hc.a.gate')),
    ('HC FFN gate', 48, selected_ns('gemv:hc.f.gate')),
    ('final HC gate', 1, selected_ns('gemv:final.gate')),
    ('HC attention inject', 48, selected_ns('gemv:hc.a.inject')),
    ('HC FFN inject', 48, selected_ns('gemv:hc.f.inject')),
    ('route + gather', 48, selected_ns('route+gather')),
    ('small.ffn.q6 tuple', 47, selected_ns('fusion:small.ffn', 'small.ffn.q6')),
    ('small.ffn.q8 tuple', 1, selected_ns('fusion:small.ffn', 'small.ffn.q8')),
    ('shared down', 48, selected_ns('gemv:shexpdown')),
]
R = sum(count*ns for _, count, ns in replicated)/1e6
# This is a calibration sensitivity, NOT a wall-time lower-bound theorem.
base = 37.1
ideal_half = base/2
serial4 = 48*4*(ab+ba)/1000
serial3 = 48*3*(ab+ba)/1000
ideal_duplex3 = 48*3*max(ab, ba)/1000
# Give the entire route epoch free and allow a delayed HC-attention inject
# to hide its entire measured duration under E1: this favors the candidate.
hide_inject = 48*selected_ns('gemv:hc.a.inject')/1e6

sources = ['main.cpp','rank.hpp','arithmetic.hpp','core_v2.hpp','kernels.hpp',
           'round2.hpp','p30_attention.hpp','p30_small.hpp','p39_plan.hpp',
           'p39_fused.hpp','performance.cpp','request_state_inventory.hpp',
           'strict_snapshot.hpp']
for name in sources:
    read(P / name)
for name in ('packet3/step/plan.hpp','packet3/kernels/api.hpp','packet9-kopt4/dispatch.hpp'):
    read(P.parent / name)
read(ROOT / 'notes/2026-10-15-p45-after-speed6-levers.md')
read(ROOT / 'notes/2026-10-15-p45-roofline-and-structural-levers.md')

print(json.dumps(dict(
    scope='read-only CPU metadata; no arithmetic/device execution or speed claim',
    census=dict(kinds, ordinary_gdn=34, ple_gdn=1, upgraded_gdn=1),
    dependency_witnesses=witnesses, packed_gdn_head_owners=head_owners,
    exchanges=dict(data_epochs_per_layer=3, agreement_epochs_per_layer=1,
                   phases=phases, useful_data_bytes_per_layer=useful_layer,
                   fixed_wire_bytes_per_layer=wire_layer,
                   head_data_epoch_bytes=head_wire, final_completion_epoch_bytes=completion_wire,
                   full_step_epochs=48*4+2, full_step_copies=48*8+4,
                   full_step_wire_bytes=48*wire_layer+head_wire+completion_wire),
    measured_transport_medians_us=medians,
    selected_replicated_proxy=[dict(name=n,count=c,ns_per_site=t,ms=c*t/1e6) for n,c,t in replicated],
    planning=dict(base_ms=base, ideal_half_ms=ideal_half,
                  communication_allowance_ms={str(t):t-ideal_half for t in (23.5,24)},
                  serial4_ms=serial4, serial4_plus_ideal_compute_ms=ideal_half+serial4,
                  serial3_ms=serial3, ordered_rounds4_ms=48*4*round_us/1000,
                  replicated_subset_ms=R, ideal_duplex3_ms=ideal_duplex3,
                  hidden_inject_ms=hide_inject,
                  optimistic_duplex_total_ms=ideal_half+R/2+ideal_duplex3-hide_inject,
                  maximum_mean_epoch_us_even_perfect_compute={str(t):(t-ideal_half)*1000/192 for t in (23.5,24)},
                  note='medians and K2 isolated sums are planning proxies, not physical lower bounds'),
    input_sha256=INPUTS), indent=2, sort_keys=True))

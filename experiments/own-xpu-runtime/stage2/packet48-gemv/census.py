#!/usr/bin/env python3
"""Metadata-only byte census. Does not open GGUF payloads or use a device."""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
TABLE = STAGE / 'suite-inputs-20261012/architecture-tradeoff/plan.tsv'
FORMATS = {0: ('F32', 1, 4), 8: ('Q8_0', 32, 34), 14: ('Q6_K', 256, 210),
           18: ('IQ3_XXS', 256, 98), 20: ('IQ4_NL', 32, 18),
           21: ('IQ3_S', 256, 110), 22: ('IQ2_S', 256, 82)}
INPUTS = {}


def read(path):
    raw = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def main():
    for source in ('packet45-merged3/p28/expert.hpp', 'packet45-merged3/p28/dense.hpp',
                   'packet45-merged3/p33_candidates.hpp', 'packet45-merged3/p39_fused.hpp',
                   'packet45-merged3/p39_sycl.hpp', 'packet45-merged3/p30_small.hpp',
                   'packet45-merged3/route42.hpp', 'packet10-kopt5/expanded.hpp'):
        read(STAGE / source)
    tensors = {}
    for line in read(TABLE).splitlines():
        s = line.split()
        if s[1].startswith('blk.') and 0 <= int(s[6]) < 48:
            tensors[s[1]] = dict(type=int(s[3]), stored=int(s[5]), dims=list(map(int, s[9:])), layer=int(s[6]))
    timings = {}
    for window in (1, 2):
        path = STAGE / f'packet46-specialized/evidence/p46-a-t{window}/run/iterations.jsonl'
        records = [json.loads(s) for s in read(path).splitlines()]
        records = [r for r in records if r['layer'] == 4 and r['mode'] == 'current' and not r['warmup']]
        assert len(records) == 200
        timings[window] = {k: statistics.median(r['classes_ns'][k] for r in records) / 1000
                           for k in records[0]['classes_ns']}
        timings[window]['HC set'] = statistics.median(sum(v for k, v in r['classes_ns'].items() if k.startswith('hc.')) for r in records) / 1000
    # Names from the actual fused dispatch: small.ffn includes the router matrix;
    # route is the subsequent four-kernel softmax/rank/normalization sequence.
    specs = [
        ('expsgate', ['ffn_gate_exps.weight', 'ffn_up_exps.weight'], True),
        ('expsdown', ['ffn_down_exps.weight'], True),
        ('gdn.qkv', ['attn_qkv.weight'], False),
        ('gdn.z', ['attn_gate.weight'], False),
        ('attention', ['ssm_out.weight'], False),
        ('small.ffn.q6', ['ffn_gate_inp.weight', 'ffn_gate_shexp.weight', 'ffn_up_shexp.weight', 'ffn_gate_inp_shexp.weight'], False),
        ('shexpdown', ['ffn_down_shexp.weight'], False),
        ('HC set', [f'hc_{side}_{part}.weight' for side in ('attn', 'ffn') for part in ('down', 'up', 'inject', 'norm')], False),
    ]
    def sizes(t, routed):
        typ, d = t['type'], t['dims']
        n = math.prod(d)
        assert typ in FORMATS
        _, block, size = FORMATS[typ]
        assert n // block * size == t['stored']
        if routed:
            return t['stored'] * 10 // 512, t['stored'] * 10 // 512
        if typ in (8, 14):
            group, meta = (16, 18) if typ == 14 else (32, 2)
            useful = n + n // group * 4
            return useful, useful + n // block * meta
        return t['stored'], t['stored']
    # Core GEMV operand traffic before compiler/cache reuse: finite weights,
    # ordinary full routes, excluding status/control and fused epilogues.
    core = {
        'expsgate': (5120, 25600, 32768000, 24576000, 32768000),
        'expsdown': (12800, 51200, 32768000, 20480000, 0),
        'gdn.qkv': (5120, 20480, 52428800, 39321600, 0),
        'gdn.z': (5120, 12288, 31457280, 23592960, 0),
        'attention': (12288, 5120, 31457280, 23592960, 0),
        'small.ffn.q6': (5120, 3586, 9180160, 10168320, 0),
        'shexpdown': (1280, 5120, 3276800, 2457600, 0),
    }
    rows = []
    for name, suffixes, routed in specs:
        ts = [tensors['blk.4.' + s] for s in suffixes]
        useful = sum(sizes(t, routed)[0] for t in ts)
        extent = sum(sizes(t, routed)[1] for t in ts)
        packed = sum(t['stored'] * 10 // 512 if routed else t['stored'] for t in ts)
        compatible = []
        for layer in range(48):
            alt = ['attn_output.weight' if layer % 4 == 3 and s == 'ssm_out.weight' else s for s in suffixes]
            candidates = [tensors.get(f'blk.{layer}.{s}') for s in alt]
            if all(c and c['type'] == t['type'] and c['dims'] == t['dims'] for c, t in zip(candidates, ts)):
                compatible.append(layer)
        t1, t2 = timings[1][name], timings[2][name]
        floor = useful / 550000
        savings = max(0, t1 - floor)
        rows.append(dict(klass=name, tensors=[dict(name='blk.4.'+s, **t) for s, t in zip(suffixes, ts)],
            gguf_selected_bytes=packed, runtime_selected_extent_bytes=extent,
            m1_useful_weight_bytes=useful, m2_unique_weight_bytes_min=useful,
            m2_unique_weight_bytes_max=2*useful if routed else useful,
            m2_current_serial_weight_read_bytes=2*useful,
            m2_timing_us=None, m2_effective_GB_s=None,
            m1_gpu_us_t1=t1, m1_gpu_us_t2=t2, m1_useful_weight_GB_s=useful/(t1*1000),
            gap_to_550_GB_s=550-useful/(t1*1000), weight_floor_us_at_550=floor,
            optimistic_recoverable_us=savings, same_shape_format_layers=compatible,
            compatible_layer_count=len(compatible), rank0_compatible_layers=sum(i<23 for i in compatible),
            rank1_compatible_layers=sum(i>=23 for i in compatible),
            optimistic_saved_us_all_matching_layers=savings*len(compatible),
            caveat='Weight-only useful bytes, not measured physical DRAM traffic; excludes repeated loads, cache lines, activations, scratch, epilogue and controls.'))
    for row in rows:
        if row['klass'] in core:
            x, y, xl, wl, codebook = core[row['klass']]
            row['core_operand_accounting'] = dict(
                m1_unique_input_bytes=x, m1_output_bytes=y,
                m1_compulsory_core_bytes=row['m1_useful_weight_bytes']+x+y,
                m2_compulsory_core_bytes_min=row['m2_unique_weight_bytes_min']+2*(x+y),
                m2_compulsory_core_bytes_max=row['m2_unique_weight_bytes_max']+2*(x+y),
                m1_source_logical_input_bytes=xl, m1_source_logical_weight_bytes=wl,
                m1_source_logical_codebook_bytes=codebook,
                m2_serial_source_logical_input_bytes=2*xl, m2_serial_source_logical_weight_bytes=2*wl,
                scope='Core GEMV only. Counts source expressions before compiler hoisting/broadcast and cache reuse; excludes scratch, control/status and epilogues. IQ2 codebook is constant storage, not 32.8 MB of compulsory DRAM traffic.')
    # Route weights are already counted in small.ffn. These are separate counts
    # for its transient buffers, and source-level loads before compiler/cache reuse.
    route_logical = 1024+128 + 4096+1024+2048+128 + 512*32*32*4+512*32*4+512*512*4 + 10*(32*4+4+32) + 120
    route = dict(klass='route', m1_weight_bytes=0, m2_weight_bytes=0,
        m1_buffer_address_extent_bytes=1024+2304+320,
        m2_buffer_address_extent_bytes=2*(1024+2304+320),
        m1_compulsory_payload_bytes_lower_bound=6072,
        m2_compulsory_payload_bytes_lower_bound=12144,
        m1_source_logical_payload_bytes=route_logical,
        m2_source_logical_payload_bytes=2*route_logical,
        m1_gpu_us_t1=timings[1]['route'], m1_gpu_us_t2=timings[2]['route'],
        m1_compulsory_payload_effective_GB_s=6072/(timings[1]['route']*1000),
        m1_source_logical_GB_s=route_logical/(timings[1]['route']*1000),
        m2_timing_us=None, m2_effective_GB_s=None,
        caveat='Four launch softmax/top-k pipeline, not GEMV. Logical loads may be subgroup broadcast, compiler-hoisted, or cache hits; do not call their quotient DRAM bandwidth. Excludes repeated active/error control loads.')
    variants = []
    for suffix in ['ffn_gate_exps.weight','ffn_down_exps.weight','attn_qkv.weight','attn_gate.weight','ffn_gate_shexp.weight','ssm_out.weight','attn_output.weight']:
        groups = {}
        for name, t in tensors.items():
            if name.endswith('.'+suffix):
                key = (t['type'], tuple(t['dims']))
                groups.setdefault(key, []).append(t['layer'])
        for (typ, dims), layers in groups.items():
            n = math.prod(dims); selected=n*10//512 if len(dims)==3 else n
            variants.append(dict(suffix=suffix, format=FORMATS[typ][0], dims=dims,layers=layers,
                selected_elements=selected, selected_packed_bytes=selected//FORMATS[typ][1]*FORMATS[typ][2]))
    assert sum(x['selected_packed_bytes']*len(x['layers'])*(2 if x['suffix']=='ffn_gate_exps.weight' else 1)
               for x in variants if x['suffix'] in ('ffn_gate_exps.weight','ffn_down_exps.weight')) == 949760000
    return dict(schema='own-runtime.packet48.byte-census.v1', device_executed=False,
        physical_DRAM_bytes_measured=False, bandwidth_reference_GB_s=550,
        format_blocks={name:dict(elements=n, bytes=b) for name,n,b in FORMATS.values()},
        rows=rows, route=route, tensor_variants=variants,
        ranking_weight_only=[r['klass'] for r in sorted(rows,key=lambda r:r['optimistic_saved_us_all_matching_layers'],reverse=True)],
        input_sha256=INPUTS,
        m2_semantics='Two changing token rows. Current serial calls read weights twice logically. A reuse kernel can read dense weights once; routed expert union is 10..20 experts, depending on overlap. No M2 timing is present in packet46.',
        qualification='Layer-4 timing is a representative isolated fixture, not a full-model speed measurement; layer multiplication and 550 GB/s floors are optimistic planning arithmetic.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    text = json.dumps(main(), indent=2, sort_keys=True)+'\n'
    if args.output: args.output.write_text(text)
    else: print(text,end='')

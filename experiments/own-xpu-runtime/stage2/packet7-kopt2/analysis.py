#!/usr/bin/env python3
"""CPU-only resource accounting and explicitly hypothetical bandwidth forecasts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from common import plan, ceiling_summary


def calculate(ceiling=None):
    receipt = HERE.parent / 'packet6-kopt/receipts-card3-20261011/timing/layer0/native.json'
    native = json.loads(receipt.read_text())
    properties = native['device_properties']
    measured = ceiling is not None
    if measured:
        raw = json.loads(ceiling.read_text());rows = ceiling_summary(raw)
        capacity = raw['device_properties']
        bandwidth = statistics.median(r['payload_GB_s'] for r in rows if r['variant']=='stream16_sum_u64_v1' and r['packed_bytes']==256*1024**2)
    else:
        capacity = dict(threads_per_eu=8, eus_per_subslice=8, subslices_per_slice=4, slices=8)
        bandwidth = 507.0
    eus = capacity['eus_per_subslice'] * capacity['subslices_per_slice'] * capacity['slices']
    cores = eus / capacity['eus_per_subslice']
    # SIMD16 capacity remains a stated scheduling model, not measured occupancy.
    hardware_threads = eus * capacity['threads_per_eu']
    resident_lanes = hardware_threads * 16
    max_sg32 = resident_lanes // 32
    max_groups = max_sg32 // 4
    occupancy = []
    for n in (5120,10240,17408):
        occupancy.append(dict(rows=n,sg32=n,work_groups=math.ceil(n/4),logical_work_items=n*32,
            conditional_group_waves=math.ceil(n/4)/max_groups,
            split2_groups=math.ceil(n*2/4),split4_groups=math.ceil(n*4/4),wide2_groups=math.ceil(n/8)))
    fractions = {'Q6_K':(.30,.50),'Q8_0':(.40,.65),'IQ2_S':(.22,.40),'IQ3_S':(.25,.45),'IQ4_NL':(.35,.60),'F32':(.40,.70),'BF16':(.40,.70)}
    predictions = []
    for layer in plan()['layers']:
        for j in layer['jobs']:
            lo,hi=fractions[j['type']];w=j['packed_active_bytes']
            def forecast(passes):
                return [w/(passes*17000+w/(bandwidth*f)) for f in (lo,hi)]
            predictions.append(dict(name=j['name'],type=j['type'],rows=j['rows'],columns=j['columns'],
                active_weight_bytes=w,row_bytes=j['row_bytes'],stage16_mean_loads_per_lane=j['row_bytes']/512,
                stage16_mean_bytes_per_lane=j['row_bytes']/32,
                round1_slm_bytes_per_group=math.ceil(j['row_bytes']/16)*16*4 if j['type'] not in ('F32','BF16') else 64,
                wide2_slm_bytes_per_group=math.ceil(j['row_bytes']/64)*64*8 if j['type'] not in ('F32','BF16') else 512,
                wide2_predicted_GB_s=forecast(1),splitk_predicted_GB_s=forecast(2),stream_fraction_hypothesis=[lo,hi]))
    fused=native['fused']
    span=lambda e:(e[-1]['end_ns']-e[0]['start_ns'])/1e6
    fused_ms=statistics.median(span([e]) for e in fused['events'])
    separate_ms=statistics.median(span(e) for e in fused['separate_iterations'])
    return dict(schema='own-runtime.iq3.packet7.analysis.v1',measured=False,
        source_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),round1_properties=properties,
        round1_fused=dict(median_ms=fused_ms,separate_ms=separate_ms,separate_over_fused=separate_ms/fused_ms),
        round1_sequence={s['variant']:statistics.median(span(i['events']) for i in s['iterations']) for s in native['sequence']},
        missing_round1_properties=['threads_per_eu','eus_per_subslice','subslices_per_slice','slices','global_mem_cache_line_bytes','register_usage','resident_occupancy'],
        capacity_inputs=capacity,capacity_inputs_measured=measured,
        conditional_capacity=dict(eus=eus,xe_core_like_subslices=cores,simd_width_assumption=16,hardware_thread_slots=hardware_threads,
            logical_lanes=resident_lanes,sg32=max_sg32,groups128=max_groups,one_vec16_per_lane_bytes_in_flight=resident_lanes*16),
        occupancy=occupancy,
        forecasts=dict(ceiling_GB_s=bandwidth,ceiling_measured=measured,
            definition='W / (passes*17000 ns + W/(C*f)); f is an unmeasured efficiency hypothesis; 17us is an observed small-op floor, not isolated launch latency',
            scope='per-kernel hypotheses, not performance evidence, bounds, guaranteed improvements or token-rate predictions',kernels=predictions))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ceiling',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();data=calculate(a.ceiling);text=json.dumps(data,indent=2,allow_nan=False)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')

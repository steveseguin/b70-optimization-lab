#!/usr/bin/env python3
"""CPU-only accounting of frozen packet77 events and packet56 text coverage."""
import collections
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
sys.path.insert(0, str(STAGE / 'packet77-attribution'))
from timeline import extract


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    hashes = {}

    def read(path):
        raw = path.read_bytes()
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        return raw

    for name in ('census.py', 'PREREGISTRATION.md', 'coverage.json'):
        read(P / name)
    for name in ('timeline.py',):
        read(STAGE / 'packet77-attribution' / name)
    for path in ('packet75-record-bundle/mtp.hpp',
                 'packet75-record-bundle/arithmetic.hpp',
                 'packet10-kopt5/expanded.hpp', 'packet3/kernels/api.hpp'):
        read(STAGE / path)
    run = STAGE / 'screen/v4-lanes/evidence/packet77-attribution-B-a/run/attribution'
    samples = []
    for directory in sorted(run.iterdir()):
        receipt = directory / 'receipt.json'
        if not receipt.is_file():
            continue
        cycles = {c['position']: c for c in extract(json.loads(read(receipt)))}
        groups = collections.defaultdict(list)
        for line in read(directory / 'rank1/sites.jsonl').splitlines():
            e = json.loads(line)
            if e['label'].startswith('draft.'):
                groups[e['position']].append(e)
        for position, events in sorted(groups.items()):
            if not cycles[position]['hit']:
                continue
            classes = collections.defaultdict(float)
            for e in events:
                classes[e['class']] += (e['end_ns'] - e['start_ns']) / 1000
            positive = [e for e in events if e['end_ns'] > e['start_ns']]
            event_us = sum(classes.values())
            span_us = (max(e['end_ns'] for e in positive)
                       - min(e['start_ns'] for e in positive)) / 1000
            wall_us = cycles[position]['D_wall_ms'] * 1000
            samples.append(dict(prompt_id=directory.name, position=position,
                                classes_us=dict(classes), event_us=event_us,
                                wall_us=wall_us, envelope_gap_us=span_us-event_us,
                                residual_us=wall_us-event_us, events=len(events)))
    assert len(samples) == 76 and {s['events'] for s in samples} == {62}
    mean = lambda key: statistics.mean(s[key] for s in samples)
    times = {key: mean(key) for key in ('wall_us', 'event_us', 'envelope_gap_us', 'residual_us')}
    times['classes_us'] = {key: statistics.mean(s['classes_us'][key] for s in samples)
                          for key in sorted(samples[0]['classes_us'])}
    weights = collections.Counter()
    for line in read(STAGE / 'packet75-record-bundle/mtp-manifest.tsv').decode().splitlines():
        fields = line.split()
        name, size, dtype = fields[0], int(fields[3]), fields[4]
        if '.experts.' in name:
            continue
        category = ('attention' if '.self_attn.' in name else
                    'hc' if 'hyper_connection' in name or 'fc_hidden' in name or 'pre_fc_norm_hidden' in name else
                    'shared' if 'shared_expert' in name else
                    'router' if '.mlp.gate.' in name else 'embedding')
        weights[category] += size * (2 if 'norm' in name and dtype == 'BF16' else 1)
    weights['hc_logical_four_hidden_streams'] = weights['hc'] + 3*2560*2560*2
    weights['selected_experts_top10'] = 3*10*640*(2560+2560//16*4)
    weights['all_experts_resident'] = 3*512*640*(2560+2560//16*4)
    calibration = json.loads(read(STAGE / 'packet56-draft-prefix/calibration/selection.json'))
    histogram = {int(k): v for k, v in calibration['histogram'].items()}
    head_us = times['classes_us']['head_prefix']
    candidates = [dict(name='q4g32', rows=91392,
                       coverage=calibration['coverage'], acceptance_proxy=None,
                       extra_allocation_bytes=91392*1600,
                       logical_weight_read_bytes=91392*1600,
                       projected_saved_us=head_us/2)]
    for threshold in (990, 985):
        n = next(n for n in range(256, 248321, 256)
                 if sum(v for k, v in histogram.items() if k < n)*1000 >= calibration['tokens']*threshold)
        covered = sum(v for k, v in histogram.items() if k < n)
        candidates.append(dict(name=f'prefix{threshold}', rows=n, covered_tokens=covered,
                               coverage=covered/calibration['tokens'],
                               acceptance_proxy=.787*covered/calibration['covered_tokens'],
                               extra_allocation_bytes=0, logical_weight_read_bytes=n*3200,
                               projected_saved_us=head_us*(1-n/91392)))
    for c in candidates:
        c['projected_hit_cycle_saving_percent'] = 100*c['projected_saved_us']/16100
    memory = json.loads(read(STAGE / 'packet75-record-bundle/memory-plan.json'))
    rank1 = memory['placements']['1']['capacities']['4096']['ranks'][1]
    result = dict(schema='packet83.cpu-draft-byte-census.v1', sampled_hit_count=len(samples),
                  measured=True, measurement_scope='historical packet77 diagnostic events only',
                  mean=times, weight_bytes=dict(weights),
                  head=dict(rows=91392, columns=2560, gguf_type='Q6_K',
                            source_bytes_per_row=2100, logical_read_bytes_per_row=3200,
                            allocated_bytes_per_row=3380, logical_prefix_bytes=91392*3200,
                            equivalent_prefix_allocation_bytes=91392*3380,
                            full_shared_head_allocation_bytes=248320*3380,
                            q4_group_size=32, q4_bytes_per_row=1600),
                  candidates=candidates,
                  rank1_model=dict(context=4096, capacity_bytes=memory['capacity_bytes'],
                                   baseline_free_bytes=rank1['free_with_mtp_bytes'],
                                   baseline_arena_headroom_bytes=rank1['arena_headroom_bytes'],
                                   q4_free_bytes=rank1['free_with_mtp_bytes']-91392*1600,
                                   q4_arena_headroom_bytes=rank1['arena_headroom_bytes']-91392*1600,
                                   actual_startup_gate_required=True),
                  sources=hashes, samples=samples,
                  limitations=[
                      'Residual is not pure fixed launch overhead: includes CPU embedding access, waits, submission and instrumentation.',
                      'Useful weight reads are not measured DRAM traffic; activations and context-dependent KV reads are additional.',
                      'HC logical reads count four hidden projection streams; cache may reuse their common weights.',
                      'Head allocated stride includes 180 bytes of source metadata beyond 3200 useful bytes per row.',
                      'Saving projections assume unchanged bandwidth and acceptance, and exclude kernel overhead.',
                      'Coverage acceptance proxies are conditional illustrations, not measured or predicted acceptance.',
                      'Q4 derives the authenticated existing Unsloth Q6_K GGUF, not original BF16 weights.',
                      'Rank1 memory is inherited modeling, not a new device measurement.'])
    output = P / 'evidence/census.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(samples=len(samples), mean=times, candidates=candidates)))


if __name__ == '__main__':
    main()

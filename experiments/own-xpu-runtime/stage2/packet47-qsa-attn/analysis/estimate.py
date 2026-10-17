#!/usr/bin/env python3
"""CPU-only structural bounds and conditional estimates; never benchmark rows."""
import hashlib
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
P46 = ROOT / 'experiments/own-xpu-runtime/stage2/packet46-specialized'
SUITE = ROOT / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012'


def pin(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def selected(c):
    return min(2048, 4 * (c // 4)) + c % 4


def main():
    evidence = []
    inputs = []
    for trial in (1, 2):
        path = P46 / f'evidence/p46-a-t{trial}/run/iterations.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows = [r for r in rows if r['mode'] == 'current' and not r['warmup'] and 'qsa.attention' in r['classes_ns']]
        assert len(rows) == 200 and all(r['occupied_context'] == 4096 for r in rows)
        classes = {}
        for cls in ('qsa.attention', 'qsa.select', 'qsa.qgate'):
            events = [[e['end_ns'] - e['start_ns'] for e in r['events'] if e['class'] == cls] for r in rows]
            assert all(len(e) == len(events[0]) for e in events)
            classes[cls] = {'median_total_us': statistics.median(r['classes_ns'][cls] for r in rows) / 1000,
                            'median_subevents_us': [statistics.median(e[i] for e in events) / 1000 for i in range(len(events[0]))]}
        evidence.append({'trial': trial, 'classes': classes, 'pin': pin(path)})
    base_us = statistics.mean(x['classes']['qsa.attention']['median_total_us'] for x in evidence)
    manifest = json.loads((SUITE / 'suite-manifest.json').read_text())
    cap_manifest_path = SUITE.parent / 'suite-inputs-20261012-cap128/suite-manifest.json'
    cap_manifest = json.loads(cap_manifest_path.read_text())
    caps = {p['prompt_id']: p for p in cap_manifest['prompts']}
    for p in manifest['prompts']:
        path = SUITE / p['prompt_id'] / 'input.json'
        n = len(json.loads(path.read_text())['tokens'])
        assert n == p['prompt_tokens'] == caps[p['prompt_id']]['prompt_tokens']
        assert pin(path)['sha256'] == p['input_bundle_hashes']['input.json']
        assert caps[p['prompt_id']]['generated_tokens'] == 128
        inputs.append({'prompt_id': p['prompt_id'], 'prompt_tokens': n, 'pin': pin(path)})
    floors = []
    for context in (1024, 2048, 4096, 8192, 32768):
        n = selected(context)
        unique_bytes = 2 * 2 * 256 * 2 * n + 3 * 24 * 256 * 2 + 4 * n
        per_head_bytes = 24 * 2 * 256 * 2 * n + 3 * 24 * 256 * 2 + 4 * n
        # 256 products plus 255 adds per score; N products plus N-1 adds per value.
        dot_flops = 24 * n * 511 + 24 * 256 * (2 * n - 1)
        floors.append({'occupied_context': context, 'selected_tokens': n,
                       'unique_kv_plus_q_gate_output_ids_bytes': unique_bytes,
                       'head_reloaded_kv_plus_q_gate_output_ids_bytes': per_head_bytes,
                       'dot_product_flops_no_softmax': dot_flops,
                       'ideal_unique_memory_us_at_assumed_550GBps': unique_bytes / 550e3,
                       'ideal_head_reloaded_memory_us_at_assumed_550GBps': per_head_bytes / 550e3,
                       'dot_flop_us_at_illustrative_20TFps': dot_flops / 20e6,
                       'selection_rank_comparisons': (context // 4) ** 2})
    positions = []
    # Output #1 comes from final prefill; output #2 processes first generated token.
    # Position rows include #1 as a hypothetical scalar equivalent, explicitly not TTFT.
    for inp in inputs:
        for output in range(1, 129):
            occupied = inp['prompt_tokens'] + output - 1
            n = selected(occupied)
            for fixed_us in (0, 50, 100):
                old = fixed_us + (base_us - fixed_us) * n / 2048
                # Only variable work accelerates. Extra launches/merge overhead unknown.
                for speedup in (3, 5):
                    new = fixed_us + (old - fixed_us) / speedup
                    positions.append({'prompt_id': inp['prompt_id'], 'output_token': output,
                                      'occupied_context': occupied, 'selected_tokens': n,
                                      'assumed_fixed_us': fixed_us, 'assumed_variable_speedup': speedup,
                                      'before_attention_per_layer_us': round(old, 6),
                                      'after_attention_per_layer_us': round(new, 6),
                                      'before_12_layer_attention_us': round(12 * old, 6),
                                      'after_12_layer_attention_us': round(12 * new, 6),
                                      'saved_rank0_5_qsa_us': round(5 * (old - new), 6),
                                      'saved_rank1_7_qsa_us': round(7 * (old - new), 6)})
    # Conventional 99 intervals between output timestamps 1 and 100 use outputs2..100.
    summaries = []
    for fixed_us in (0, 50, 100):
        for speedup in (3, 5):
            rows = [r for r in positions if 2 <= r['output_token'] <= 100 and r['assumed_fixed_us'] == fixed_us and r['assumed_variable_speedup'] == speedup]
            old = statistics.mean(r['before_attention_per_layer_us'] for r in rows)
            new = statistics.mean(r['after_attention_per_layer_us'] for r in rows)
            saved_serial_ms = 12 * (old - new) / 1000
            saved_rank1_ms = 7 * (old - new) / 1000
            record_ms = 1000 / 39.42
            summaries.append({'fixed_us': fixed_us, 'variable_speedup': speedup,
                              'mean_before_per_layer_us': old, 'mean_after_per_layer_us': new,
                              'mean_saved_serial_12_ms': saved_serial_ms, 'mean_saved_rank1_7_ms': saved_rank1_ms,
                              'illustrative_tps_from_39_42_full_serial_savings': 1000 / (record_ms - saved_serial_ms),
                              'illustrative_tps_from_39_42_rank1_only_savings': 1000 / (record_ms - saved_rank1_ms)})
    result = {'schema': 'packet47.conditional-qsa-estimate.v1', 'measurement': False,
              'warning': 'Conditional analytical extrapolation, not measured performance or a promoted curve. Unknown launch floor, new short-context latency, MTP miss/overlap and acceptance changes preclude a prediction.',
              'assumed_memory_GBps': 550, 'illustrative_dot_TFps': 20,
              'source_timings': evidence, 'source_manifest': pin(SUITE / 'suite-manifest.json'),
              'cap128_manifest': pin(cap_manifest_path), 'inputs': inputs, 'floor_rows': floors,
              'suite_prompt_mean': statistics.mean(p['prompt_tokens'] for p in inputs),
              'mean_occupied_outputs_1_128': statistics.mean(p['prompt_tokens'] + 63.5 for p in inputs),
              'mean_occupied_outputs_2_100': statistics.mean(p['prompt_tokens'] + 50 for p in inputs),
              'interval99_sensitivity': summaries}
    (HERE / 'estimate.json').write_text(json.dumps(result, indent=2) + '\n')
    # Compact, reusable per-position values rather than duplicating source fixtures.
    keys = list(positions[0])
    (HERE / 'per-position-estimate.csv').write_text(','.join(keys) + '\n' + '\n'.join(','.join(str(r[k]) for k in keys) for r in positions) + '\n')
    print(json.dumps({'passed': True, 'prompt_count': len(inputs), 'prompt_mean': result['suite_prompt_mean'],
                      'position_scenario_rows': len(positions), 'interval99_sensitivity': summaries}, indent=2))


if __name__ == '__main__':
    main()

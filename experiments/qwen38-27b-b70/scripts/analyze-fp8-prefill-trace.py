#!/usr/bin/env python3
"""Analyze the bounded FP8 serving trace on CPU, preserving all source bytes."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path


def duration_ms(events):
    return round(sum(e['dur'] for e in events) / 1000, 6)


def union_ms(events):
    intervals = sorted((e['ts'], e['ts'] + e['dur']) for e in events)
    total = 0
    end = float('-inf')
    for start, finish in intervals:
        total += max(0, finish - max(start, end))
        end = max(end, finish)
    return round(total / 1000, 6)


def external(event):
    return event.get('args', {}).get('External id')


def descendants(cpu, roots):
    """CPU interval nesting identifies launches; GPU timestamp containment does not."""
    by_thread = defaultdict(list)
    for root in roots:
        by_thread[(root['pid'], root['tid'])].append(root)
    return [e for e in cpu if any(
        r['ts'] <= e['ts'] and e['ts'] + e['dur'] <= r['ts'] + r['dur'] + 0.001
        for r in by_thread[(e['pid'], e['tid'])])]


def rank_analysis(path):
    trace = json.loads(gzip.decompress(path.read_bytes()))
    events = [e for e in trace['traceEvents'] if e.get('ph') == 'X' and 'dur' in e]
    cpu = [e for e in events if e.get('cat') == 'cpu_op']
    kernels = [e for e in events if e.get('cat') == 'kernel']
    copies = [e for e in events if e.get('cat') == 'gpu_memcpy']
    if not cpu or not kernels or not trace.get('record_shapes'):
        raise ValueError(f'Expected CPU/device events with recorded shapes: {path}')
    cpu_by_id = {external(e): e for e in cpu if external(e) is not None}
    if len(cpu_by_id) != sum(external(e) is not None for e in cpu):
        raise ValueError('Ambiguous CPU External ids within one worker trace')
    # Direct External id is primary. A unique runtime correlation with an
    # External id supplies a fallback for kernels without that field.
    correlations = defaultdict(set)
    for event in events:
        args = event.get('args', {})
        if event.get('cat') in ('xpu_runtime', 'xpu_driver'):
            if args.get('correlation') is not None and external(event) is not None:
                correlations[args['correlation']].add(external(event))
    attribution = {}
    methods = Counter()
    for index, kernel in enumerate(kernels):
        ident = external(kernel)
        method = 'external_id'
        if ident not in cpu_by_id:
            candidates = correlations[kernel.get('args', {}).get('correlation')]
            if len(candidates) == 1 and next(iter(candidates)) in cpu_by_id:
                ident = next(iter(candidates))
                method = 'unique_runtime_correlation'
            else:
                ident = None
                method = 'unattributed'
        attribution[index] = ident
        methods[method] += 1

    def device_for(operators):
        ids = {external(e) for e in operators if external(e) is not None}
        return [e for i, e in enumerate(kernels) if attribution[i] in ids]

    total = duration_ms(kernels)

    def device_fields(selected):
        milliseconds = duration_ms(selected)
        return {'kernel_count': len(selected), 'kernel_sum_ms': milliseconds,
                'kernel_pct_of_rank_kernel_sum': round(100 * milliseconds / total, 4)}

    by_name = defaultdict(list)
    for event in cpu:
        by_name[event['name']].append(event)
    operator_summary = []
    for name, selected in by_name.items():
        direct = device_for(selected)
        if direct or any(part in name.lower() for part in ('rowchunk', 'w8a16', 'fp8', 'gdn', 'allreduce', 'allgather')):
            operator_summary.append({'operator': name, 'cpu_call_count': len(selected),
                'cpu_inclusive_ms': duration_ms(selected), 'direct_device': device_fields(direct)})
    operator_summary.sort(key=lambda r: (-r['direct_device']['kernel_sum_ms'], r['operator']))

    groups = {}
    selectors = {
        'fp16_rowchunk': lambda n: n == 'vllm::xpu_fp16_linear_rowchunk',
        'fp8_w8a16': lambda n: '::' in n and ('w8a16' in n.lower() or 'fp8' in n.lower()),
        'gdn': lambda n: n == '_xpu_C::gdn_attention',
        'allreduce': lambda n: 'allreduce' in n.lower(),
        'allgather': lambda n: 'allgather' in n.lower(),
    }
    rowchunk_descendants = descendants(cpu, [e for e in cpu if selectors['fp16_rowchunk'](e['name'])])
    rowchunk_ids = {external(e) for e in rowchunk_descendants}
    shapes = []
    for group, selector in selectors.items():
        roots = [e for e in cpu if selector(e['name'])]
        children = descendants(cpu, roots)
        groups[group] = {'root_operator_names': sorted({e['name'] for e in roots}),
                         'root_cpu_call_count': len(roots),
                         'root_cpu_inclusive_ms': duration_ms(roots),
                         'including_descendant_device': device_fields(device_for(children))}
    shape_groups = defaultdict(list)
    for event in cpu:
        if event['name'] == 'aten::mm' or any(selector(event['name']) for selector in selectors.values()):
            args = event.get('args', {})
            key = (event['name'], json.dumps(args.get('Input Dims')), json.dumps(args.get('Input type')))
            shape_groups[key].append(event)
    for (name, dims, types), selected in sorted(shape_groups.items()):
        shapes.append({'operator': name, 'input_dims': json.loads(dims), 'input_dtype': json.loads(types),
                       'cpu_call_count': len(selected), 'cpu_inclusive_ms': duration_ms(selected),
                       'direct_device': device_fields(device_for(selected)),
                       'calls_within_fp16_rowchunk': sum(external(e) in rowchunk_ids for e in selected)})
    return {'trace_file': path.name, 'rank': trace.get('distributedInfo', {}).get('rank'),
            'record_shapes': trace.get('record_shapes'),
            'device_kernel_count': len(kernels), 'device_kernel_sum_ms': total,
            'device_kernel_interval_union_ms': union_ms(kernels),
            'device_memcpy_count': len(copies), 'device_memcpy_sum_ms': duration_ms(copies),
            'attribution_kernel_counts': dict(sorted(methods.items())),
            'execute_context_annotations': [
                {'name': e['name'], 'cpu_inclusive_ms': round(e['dur'] / 1000, 6)}
                for e in events if e['name'].startswith('execute_context_')],
            'operator_summary': operator_summary, 'inclusive_groups': groups, 'operator_shapes': shapes}


def analyze(raw_root):
    raw_root = Path(raw_root).resolve()
    stage = raw_root / '27b-fp8'
    profile = stage / 'profile'
    rank_paths = sorted(profile.glob('rank*.pt.trace.json.gz'))
    if len(rank_paths) != 2:
        raise ValueError(f'Expected exactly two worker traces in {profile}')
    source_paths = sorted(profile.glob('*.pt.trace.json.gz')) + sorted(profile.glob('*.txt'))
    source_paths += [stage / name for name in ('identity.json', 'container-inspect.json',
                                              'profile-request/request.json', 'profile-request/response.json')]
    identity = json.loads((stage / 'identity.json').read_text())
    container = json.loads((stage / 'container-inspect.json').read_text())[0]
    request = json.loads((stage / 'profile-request/request.json').read_text())
    response = json.loads((stage / 'profile-request/response.json').read_text())
    argv = container['Args']
    env = dict(item.split('=', 1) for item in container['Config']['Env'])
    def flag(name):
        return argv[argv.index(name) + 1]
    draft = json.loads(flag('--speculative-config'))
    if (container['Image'] != identity['parent_image'] or flag('--quantization') != 'fp8'
            or flag('--dtype') != 'float16' or int(flag('--tensor-parallel-size')) != 2
            or draft['num_speculative_tokens'] != 1
            or env.get('VLLM_XPU_DRAFT_LM_HEAD_INT4') != '1'
            or env.get('VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST', '0') != '0'
            or len(request['prompt']) != 512 or request['max_tokens'] != 1
            or response['usage']['prompt_tokens'] != 512
            or response['usage']['prompt_tokens_details']['cached_tokens'] != 0):
        raise ValueError('FP8 profile setup differs from the bounded campaign contract')
    sources = []
    for path in source_paths:
        raw = path.read_bytes()
        sources.append({'path': str(path), 'raw_relative_path': path.relative_to(raw_root).as_posix(),
                        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    ranks = [rank_analysis(path) for path in rank_paths]
    if sorted(r['rank'] for r in ranks) != [0, 1]:
        raise ValueError('Expected ranks zero and one')
    return {
        'schema': 'neural.download.fp8-prefill-trace-analysis.v1', 'date_utc': '2026-09-14',
        'status': 'diagnostic_only_no_optimization_promoted',
        'setup': {'model': 'Qwen3.8 27B', 'quantization': 'FP8 W8A16', 'gpu_count': 2,
                  'runtime_identity': 'Published R304; see campaign image contract',
                  'image_id': container['Image'],
                  'draft': 'fixed MTP depth 1, full-vocabulary INT4 draft head; no shortlist',
                  'fp16_linear_mode': 'CLASSPAD' + env['VLLM_XPU_FP16_LINEAR_CLASSPAD']
                                      + ', rowchunk' + env['VLLM_XPU_FP16_LINEAR_ROWCHUNK'],
                  'max_model_len': int(flag('--max-model-len')),
                  'max_num_batched_tokens': int(flag('--max-num-batched-tokens')),
                  'max_num_seqs': int(flag('--max-num-seqs')),
                  'input_tokens': len(request['prompt']), 'requested_output_tokens': request['max_tokens'],
                  'cached_tokens': response['usage']['prompt_tokens_details']['cached_tokens'],
                  'profiled_requests': 1},
        'source_files': sources,
        'methodology': {
            'trace_format': 'Original gzip-compressed PyTorch Chrome JSON is decoded in memory, never rewritten.',
            'units': 'Trace timestamps and durations are microseconds, divided by 1000 for milliseconds.',
            'cpu': 'Complete cpu_op events. Inclusive CPU intervals overlap nested operators; do not add them.',
            'device': 'Complete kernel events, each counted once per worker. Copies are separate. Percentages divide by the same rank kernel-duration sum. Never sum ranks into request latency.',
            'attribution': 'Join kernel External id to CPU External id. Only if missing/unmatched, use a unique xpu_runtime/xpu_driver correlation-to-External-id match. Unattributed events remain in totals.',
            'parentage': 'Inclusive groups collect CPU intervals fully contained within root intervals on the same pid/tid (0.001 us end tolerance), then attribute kernels through those CPU launches. Asynchronous kernel timestamp containment is not used.',
            'shapes': 'Actual CPU Input Dims and Input type fields; aten::mm B dimensions are post-transpose. No FLOP counts inferred.',
            'aggregation': 'One diagnostic request, two tensor-parallel ranks. No repetition, speed comparison or extrapolation.',
            'reproduction': 'python3 experiments/qwen38-27b-b70/scripts/analyze-fp8-prefill-trace.py --raw-root RAW_ROOT --out OUTPUT_JSON'},
        'ranks': ranks,
        'findings': [
            'The FP8/W8A16 custom operator is the largest directly attributed device group on both ranks. Its actual Input Dims use 512 activation rows; these are not a chain of 32-row FP16 GEMMs.',
            'Only two FP16 rowchunk custom-op calls appear per rank: a 512-row projection expanded into sixteen 32-row GEMMs, and a one-row full-vocabulary projection. The detailed shapes are retained below each rank.',
            'The 4B small-FP16-GEMM bottleneck therefore does not describe this preferred FP8 model. Its FP16 rowchunk descendants represent only about two percent of the per-rank kernel-duration sums.',
            'The most costly W8A16 shape is [512,5120] times [5120,17408], with 65 calls per rank. Changing its geometry or implementation is a kernel arithmetic and qualification task, not an established cheap dispatch fix.',
            'GDN and allreduce remain substantial separate device groups. Rank differences in allreduce do not establish pure transport cost or an available communication speedup.',
            'No new small same-arithmetic candidate is established by this trace. Preserve the closed allocation screen and the source-review conclusions about existing scale preparation and primitive caching.'],
        'limitations': [
            'Profiling and shape recording change host overhead and scheduling. These timings must not become public prefill throughput.',
            'CPU inclusive intervals nest. Device sums can overlap across streams and ranks; they are not server prefill duration, HTTP TTFT or a critical-path decomposition.',
            'Collective durations may include synchronization waiting; their sum is not isolated wire-transfer cost.',
            'Inclusive groups can overlap each other and direct operator rows. Do not add those different views.',
            'One returned token may still execute MTP work; this is the configured serving path, not an isolated target forward.',
            'This trace alone cannot establish arithmetic equivalence, repeatability, quality, decode regression or the speed of an unimplemented optimization.'],
        'conclusion': {'new_small_same_arithmetic_candidate_established': False,
                       'optimization_implemented': False, 'serving_defaults_changed': False,
                       'decision': 'Diagnostic profile only. No optimization benefit is inferred from attributed durations; candidate decisions require source review and qualification.'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.raw_root)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'ranks': len(result['ranks']), 'sources': len(result['source_files']), 'out': str(args.out)}))

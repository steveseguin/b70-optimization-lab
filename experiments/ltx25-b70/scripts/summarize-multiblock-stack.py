#!/usr/bin/env python3
"""Summarize one prompt worker's sampled occupancy; never kernel/CPU utilization."""
import argparse
import ast
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-compiler-08')
ADAPTER_SHA = 'ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b'
NODE_SHA = 'e7d6e69ff44d5b727dba27f52142647a06afe6d494abb043af49fa132a005d2f'
MANIFEST_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
UNITS = {'none', 'nanoseconds', 'microseconds', 'milliseconds', 'seconds', 'bytes'}
CATEGORIES = ('queue_idle', 'empty_stack', 'current_block_state_validation',
              'aggregate_registry_lifecycle', 'receipt_context_checks_writes',
              'compiled_wrapper_native_calls', 'unknown_leaf', 'other')
PRIORITY = ['queue idle', 'empty stack', 'current-block state validation',
            'aggregate registry/lifecycle', 'explicit receipt/context helpers',
            'compiled/native wrapper', 'remaining gate control', 'unknown leaf', 'other']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def spans(text):
    """Qualified AST function spans: disambiguate identically named methods."""
    result = {}
    def walk(nodes, prefix=''):
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                if not isinstance(node, ast.ClassDef):
                    result[name] = [min([node.lineno] + [n.lineno for n in node.decorator_list]), node.end_lineno]
                walk(node.body, name + '.')
    walk(ast.parse(text).body)
    return result


def load_sources(packet):
    require(sha(packet / 'manifest.json') == MANIFEST_SHA, 'Packet08 manifest pin changed')
    manifest = json.loads((packet / 'manifest.json').read_text())
    names = {'adapter': 'source/scripts/ltx_multiblock_compile.py',
             'node': 'source/scripts/multiblock_compile_node.py',
             'node_plugin': 'source/custom_nodes/ltx_multiblock_compile_lab/__init__.py',
             'context': 'source/scripts/encoder_diagnostics.py',
             'context_plugin': 'source/custom_nodes/ltx_encoder_diagnostics/__init__.py'}
    sources = {}
    for key, name in names.items():
        path = packet / name
        require(not path.is_symlink() and sha(path) == manifest['files'][name], 'Source pin changed: ' + name)
        text = path.read_text()
        callsites = [list(range(n.lineno, n.end_lineno + 1)) for n in ast.walk(ast.parse(text))
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'self'
                     and n.func.attr in ('compiled', 'native')]
        sources[key] = {'path': str(path), 'sha256': sha(path), 'spans': spans(text),
                        'native_callsite_lines': sorted({line for lines in callsites for line in lines})}
    require(sources['adapter']['sha256'] == ADAPTER_SHA, 'Wrong adapter version')
    for key in ('node', 'node_plugin'):
        require(sources[key]['sha256'] == NODE_SHA, 'Wrong native gate source')
    return sources


def within(frame, source, names):
    line = frame.get('line')
    if frame.get('file') != source['path'] or type(line) is not int:
        return False
    return any(name in source['spans'] and source['spans'][name][0] <= line <= source['spans'][name][1]
               for name in names)


def classify(entries, sources):
    if not entries:
        return 'empty_stack'
    leaf = entries[-1]
    if (leaf.get('name') == 'wait' and str(leaf.get('file', '')).endswith('/threading.py') and
        any(f.get('name') == 'get' and str(f.get('file', '')).endswith('/execution.py') for f in entries)):
        return 'queue_idle'
    adapter = sources['adapter']
    if any(within(f, adapter, ['CompiledBlockRoute._validate']) for f in entries):
        return 'current_block_state_validation'
    lifecycle = ['_routes', '_registered_bindings', '_CompilePreRun._validate',
                 '_CompilePreRun._validate_selection', '_CompilePreRun.__call__',
                 '_CompilePreRun.validate_current_execution', 'CompiledBlockRoute._validate_execution']
    if any(within(f, adapter, lifecycle) for f in entries):
        return 'aggregate_registry_lifecycle'
    receipt = ['write_json', 'graph_receipts', 'census', 'signature', 'tensor_meta',
               'counter_snapshot', 'counter_delta', 'exact_pair', 'require_exact', 'independent_streams']
    explicit = any(within(f, sources[key], receipt) for f in entries for key in ('node', 'node_plugin'))
    context = any(within(f, sources[key], ['_context']) for f in entries for key in ('context', 'context_plugin'))
    if explicit or context:
        return 'receipt_context_checks_writes'
    # Only call this compiled/native occupancy inside a proven adapter/gate path.
    # In particular, _call_native alone does not establish a native call: it wraps gate work too.
    gate = any(within(f, sources[key], ['_Gate.__call__']) for f in entries for key in ('node', 'node_plugin'))
    routed = gate or any(within(f, adapter, ['CompiledBlockRoute._call_native']) for f in entries)
    native_paths = ('/torch/_inductor/', '/torch/_dynamo/eval_frame.py', '/torch/_ops.py',
                    '/comfy/ldm/lightricks/av_model.py', '/ltx_native_rms_backend.py',
                    '/ltx_native_activations_backend.py', '/inductor-cache/')
    route_indices = [i for i, f in enumerate(entries) if within(f, adapter, ['CompiledBlockRoute._call_native']) or
                     any(within(f, sources[key], ['_Gate.__call__']) for key in ('node', 'node_plugin'))]
    descendants = entries[max(route_indices) + 1:] if route_indices else []
    native_callsite = gate and any(leaf.get('file') == sources[key]['path'] and
                                    leaf.get('line') in sources[key]['native_callsite_lines']
                                    for key in ('node', 'node_plugin'))
    if native_callsite or (routed and any(any(part in str(f.get('file', '')) for part in native_paths) for f in descendants)):
        return 'compiled_wrapper_native_calls'
    if gate:
        return 'receipt_context_checks_writes'
    if not leaf.get('file') or type(leaf.get('line')) is not int or leaf['line'] <= 0 or leaf.get('name') in (None, '', '<unknown>', 'unknown'):
        return 'unknown_leaf'
    return 'other'


def profile_data(trace, worker_name=None):
    frames = trace['shared']['frames']
    require(isinstance(frames, list) and all(isinstance(f, dict) for f in frames), 'Malformed shared frames')
    for frame in frames:
        require(isinstance(frame.get('name', ''), str) and
                (frame.get('file') is None or isinstance(frame.get('file'), str)) and
                (frame.get('line') is None or type(frame.get('line')) is int), 'Malformed frame location')
    profiles = trace['profiles']
    require(isinstance(profiles, list), 'Malformed profiles')
    if worker_name is None:
        candidates = []
        for p in profiles:
            if p.get('type') != 'sampled':
                continue
            indices = {i for sample in p.get('samples', []) for i in sample if type(i) is int and 0 <= i < len(frames)}
            if any(frames[i].get('name') == 'prompt_worker' for i in indices):
                candidates.append(p)
    else:
        candidates = [p for p in profiles if p.get('name') == worker_name]
    require(len(candidates) == 1, 'Require exactly one prompt_worker profile; use exact --worker-name if ambiguous')
    profile = candidates[0]
    require(profile.get('type') == 'sampled', 'Only sampled speedscope profiles supported')
    samples = profile.get('samples')
    require(isinstance(samples, list), 'Missing samples')
    for sample in samples:
        require(isinstance(sample, list) and all(type(i) is int and 0 <= i < len(frames) for i in sample), 'Invalid sample/frame index')
    require(any(frames[i].get('name') == 'prompt_worker' for sample in samples for i in sample), 'Selected profile lacks exact prompt_worker frame')
    unit = profile.get('unit')
    require(unit in UNITS, 'Unsupported speedscope unit')
    start, end = profile.get('startValue'), profile.get('endValue')
    require(number(start) and number(end) and end >= start, 'Invalid profile start/end')
    explicit = 'weights' in profile
    weights = profile.get('weights', [1] * len(samples))
    require(isinstance(weights, list) and len(weights) == len(samples), 'Weights must align with samples')
    require(all(number(w) and w >= 0 for w in weights), 'Weights must be finite nonnegative numbers')
    total = math.fsum(weights)
    require(math.isfinite(total), 'Nonfinite total weight')
    return frames, profile, samples, weights, {'declared_unit': unit,
        'weight_unit': unit if explicit else 'samples', 'explicit_weights': explicit,
        'startValue': start, 'endValue': end, 'profile_extent': end - start,
        'total_weight': total, 'weight_minus_extent': total - (end - start) if explicit else None,
        'weights_missing_note': None if explicit else 'Counts only; missing weights are assigned equal unit sample weight, not duration.'}


def summarize(trace, sources, worker_name=None):
    frames, profile, samples, weights, semantics = profile_data(trace, worker_name)
    buckets = {k: {'samples': 0, 'weights': []} for k in CATEGORIES}
    leaves = defaultdict(lambda: {'samples': 0, 'weights': []})
    unknown_frames = set()
    unknown_leaf_weights = []
    for indices, weight in zip(samples, weights):
        entries = [frames[i] for i in indices]
        category = classify(entries, sources)
        if entries and (not entries[-1].get('file') or not entries[-1].get('line') or
                        entries[-1].get('name') in ('', '<unknown>', 'unknown')):
            unknown_leaf_weights.append(weight)
        bucket = buckets[category]; bucket['samples'] += 1; bucket['weights'].append(weight)
        if category != 'queue_idle':
            leaf = entries[-1] if entries else {'name': '<empty stack>', 'file': None, 'line': None}
            key = (leaf.get('name'), leaf.get('file'), leaf.get('line'))
            leaves[key]['samples'] += 1; leaves[key]['weights'].append(weight)
        unknown_frames.update(i for i in indices if not frames[i].get('file') or not frames[i].get('line'))
    for bucket in buckets.values():
        bucket['weight'] = math.fsum(bucket.pop('weights'))
    top = [{'name': k[0], 'file': k[1], 'line': k[2], 'samples': v['samples'], 'weight': math.fsum(v['weights'])}
           for k, v in leaves.items()]
    top.sort(key=lambda row: (-row['weight'], -row['samples'], repr((row['name'], row['file'], row['line']))))
    return {'profile_name': profile['name'], 'profile_count_ignored': len(trace['profiles']) - 1,
            'sample_count': len(samples), 'weight_semantics': semantics, 'categories': buckets,
            'priority': PRIORITY, 'top_nonidle_leaves': top[:40], 'unique_nonidle_leaf_count': len(top),
            'unknown_location_frame_ids': sorted(unknown_frames),
            'unknown_leaf_audit': {'samples': len(unknown_leaf_weights), 'weight': math.fsum(unknown_leaf_weights),
                                   'scope': 'Nonadditive diagnostic; these samples remain in exclusive categories above.'},
            'sample_conservation': sum(v['samples'] for v in buckets.values()) == len(samples),
            'weight_conservation': math.isclose(math.fsum(v['weight'] for v in buckets.values()), semantics['total_weight'], rel_tol=1e-12, abs_tol=1e-12)}


def log_evidence(path):
    lines = path.read_text(errors='replace').splitlines()
    matches = [(n, line) for n, line in enumerate(lines, 1) if re.search(r'warn|error|fail|drop|miss', line, re.I)]
    return {'path': str(path), 'sha256': sha(path), 'line_count': len(lines),
            'matching_line_count': len(matches), 'matching_lines': [{'line': n, 'text': line[:1000]} for n, line in matches[:40]],
            'truncated_matching_lines': max(0, len(matches) - 40),
            'interpretation': 'Keyword-matching log lines, not a count of profiler sampling errors.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--profiler-log', type=Path, required=True)
    parser.add_argument('--worker-name', help='Exact speedscope profile name, not a substring')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink(), 'Output must be new')
    require(args.trace.stat().st_size <= 128 * 1024**2 and args.profiler_log.stat().st_size <= 16 * 1024**2, 'Input exceeds bounded size')
    sources = load_sources(PACKET)
    trace_sha, log_sha = sha(args.trace), sha(args.profiler_log)
    result = summarize(json.loads(args.trace.read_text()), sources, args.worker_name)
    result.update(schema='ltx.multiblock-stack-summary.v1', trace={'path': str(args.trace), 'sha256': sha(args.trace)},
        profiler_log=log_evidence(args.profiler_log), source_identity=sources,
        script_sha256=sha(Path(__file__)), packet_manifest_sha256=MANIFEST_SHA,
        limitations=['Exclusive whole-stack occupancy categories use the listed priority; nested work is not separately additive.',
          'State validation has priority over its registry/lifecycle ancestors. Explicit receipt/context helpers precede native wrappers.',
          'Compiled/native wrapper occupancy includes dispatch, synchronization and waits; it is not kernel time or CPU utilization.',
          'Sampled stacks may miss short calls or contain incomplete/unknown frames; profiler error lines are preserved without invented counts.',
          'Only the selected prompt worker contributes counts or weights; other threads, including idle threads, are ignored.',
          'Queue idle requires the execution queue get plus threading wait call chain; unmatched waiting remains in its sampled category.',
          'Missing weights imply counts only. Supplied weights and declared units are reported without assuming wall-clock coverage.',
          'Source classification requires exact pinned paths and AST spans; relocated or unrecognized code can remain other.',
          'No native speed, uninstrumented latency, sustained streaming, or CPU/GPU utilization claim.'])
    require(sha(args.trace) == trace_sha and sha(args.profiler_log) == log_sha, 'Trace/log changed during analysis')
    with args.output.open('x') as out:
        json.dump(result, out, indent=2, allow_nan=False); out.write('\n')
    print(json.dumps({'output': str(args.output), 'profile_name': result['profile_name'], 'sample_count': result['sample_count'], 'categories': result['categories']}, indent=2))


if __name__ == '__main__':
    main()

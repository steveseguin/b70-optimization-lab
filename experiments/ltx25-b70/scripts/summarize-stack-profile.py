#!/usr/bin/env python3
"""Rank recorded Python stacks; do not interpret stack counts as GPU timings."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('trace', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    trace = json.loads(args.trace.read_text())
    frames = trace['shared']['frames']
    workers = [p for p in trace['profiles'] if 'prompt_worker' in p['name']]
    assert len(workers) == 1
    worker = workers[0]
    idle, active, leaves, copies = 0, [], Counter(), Counter()
    for stack in worker['samples']:
        entries = [frames[index] for index in stack]
        queue_wait = any(f['name'] == 'get' and f.get('file', '').endswith('/execution.py') for f in entries)
        if queue_wait and entries[-1]['name'] == 'wait':
            idle += 1
            continue
        active.append(stack)
        leaf = entries[-1]
        leaves[(leaf['name'], leaf.get('file'), leaf.get('line'))] += 1
        if leaf['name'] == 'cast_to' and leaf.get('file', '').endswith('/model_management.py'):
            if any(f['name'] == 'rms_norm' and f.get('file', '').endswith('/comfy/rmsnorm.py') for f in entries):
                copies['RMSNorm weight cast/copy'] += 1
            elif any(f['name'] == 'cast_to_input' for f in entries) and any(f.get('file', '').endswith('/text_encoders/gemma4.py') and f.get('line') == 361 for f in entries):
                copies['Gemma4 per-layer scalar cast/copy'] += 1
            elif any(f['name'] == 'cast_bias_weight' for f in entries):
                copies['Linear weight cast/copy'] += 1
            else:
                copies['Other cast/copy'] += 1
    result = {'scope': 'nonblocking Python stack samples; not synchronized GPU kernel or copy durations',
              'worker': worker['name'], 'worker_sample_count': len(worker['samples']),
              'queue_idle_samples': idle, 'non_queue_idle_samples': len(active),
              'cast_to_leaf_groups': dict(copies),
              'top_nonidle_leaves': [{'name': key[0], 'file': key[1], 'line': key[2], 'samples': count}
                                    for key, count in leaves.most_common(30)],
              'limitations': ['Profiler reported142 sampling errors; nonblocking reads can miss frames',
                              'Synchronous copy stack occupancy can include waiting for previously queued GPU work',
                              'Idle-thread samples are excluded by their actual queue-wait call chain',
                              'Profiled request latency is not an uninstrumented speed result']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'top_nonidle_leaves'}, indent=2))


if __name__ == '__main__':
    main()

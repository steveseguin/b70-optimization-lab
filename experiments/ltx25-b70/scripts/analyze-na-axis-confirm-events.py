#!/usr/bin/env python3
"""Offline decomposition of completed confirmation event timings; stdlib only."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
CAMPAIGN = 'na-axis-confirm-01'
bindings = {}


def read(relative, lines=False):
    data = (ROOT / relative).read_bytes()
    bindings[str(relative)] = hashlib.sha256(data).hexdigest()
    return [json.loads(line) for line in data.splitlines()] if lines else json.loads(data)


progress = read(Path(CAMPAIGN) / 'progress.json')
assert progress['status'] == 'passed' and progress['completed_requests'] == 18
rows = []
for number, completed in enumerate(progress['rows'], 1):
    assert completed['status'] == 'passed'
    directory = Path('requests') / completed['run']
    profile = read(directory / 'profile.json')
    events = read(directory / 'events.jsonl', lines=True)
    nodes = {node['node']: node for node in profile['nodes']}
    event_time = lambda kind: next(event['seconds'] for event in events if event['type'] == kind)
    times = {
        'preview': profile['preview_ready_seconds'],
        'submit_to_execution_start': event_time('execution_start'),
        'submit_to_first_node': profile['nodes'][0]['start_seconds'],
        'encoder': nodes['364']['seconds'],
        'placement': nodes['421']['seconds'],
        'sampler1': nodes['344']['seconds'],
        'sampler2': nodes['368']['seconds'],
        'audio_decode': nodes['358']['seconds'],
        'video_decode': nodes['374']['seconds'],
        'capture': nodes['414']['seconds'],
        'savevideo_until_preview': profile['preview_ready_seconds'] - nodes['75']['start_seconds'],
        'preview_to_execution_success': event_time('execution_success') - profile['preview_ready_seconds'],
        'execution_success_to_result': profile['seconds'] - event_time('execution_success'),
    }
    decomposition = ['submit_to_first_node', 'encoder', 'placement', 'sampler1', 'sampler2',
                     'audio_decode', 'video_decode', 'capture', 'savevideo_until_preview']
    times['other_until_preview'] = times['preview'] - sum(times[key] for key in decomposition)
    assert abs(sum(times[key] for key in decomposition + ['other_until_preview']) - times['preview']) < 1e-10
    rows.append({'number': number, 'run': completed['run'], 'mode': completed['mode'],
        'fixture': completed['fixture'], 'seconds': times,
        'other_nodes_over_8ms': [node for node in profile['nodes']
            if node['node'] not in {'364', '421', '344', '368', '358', '374', '414', '75'}
            and node['seconds'] > .008]})

pairs = []
for offset in range(0, 18, 3):
    left, middle, right = rows[offset:offset + 3]
    assert left['fixture'] == middle['fixture'] == right['fixture']
    assert left['mode'] == right['mode'] != middle['mode']
    sign = 1 if middle['mode'] == 'axis-cache' else -1
    effects = {key: sign * (middle['seconds'][key] -
        (left['seconds'][key] + right['seconds'][key]) / 2) for key in times}
    expected = progress['paired_results']['triples'][offset // 3]['metrics']
    assert abs(effects['preview'] - expected['preview_ready_seconds']['cache_minus_original']) < 1e-10
    assert abs(effects['video_decode'] - expected['decoder_node_seconds']['cache_minus_original']) < 1e-10
    pairs.append({'fixture': left['fixture'], 'order': 'OCO' if sign == 1 else 'COC',
                  'cache_minus_original_seconds': effects})

print(json.dumps({'schema': 'ltx.na-axis-confirm-event-attribution.v1', 'status': 'passed',
    'native_requests': 0, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'input_sha256s': bindings, 'rows': rows, 'pairs': pairs,
    'scope': 'Client-received event intervals, not synchronized kernels. Pre-request admission is outside the timer. '
             'The final SaveVideo node interval includes preview-to-success delay; split here at the executed preview event. '
             'No causal attribution to GC, device work, filesystem, or scheduling is possible from these events alone.'}, indent=2))

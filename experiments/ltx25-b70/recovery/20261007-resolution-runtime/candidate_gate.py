#!/usr/bin/env python3
"""Offline exact comparison against independently verified same-size native captures."""
import importlib.util
import json
import math
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location('resolution_reference_gate', Path(__file__).with_name('reference_gate.py'))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
require = R.require


def request_evidence(e, root, row, identity, previous_end, seen):
    folder = root / 'requests' / row['name']
    graph = e.json(folder / 'prompt.json')
    require(graph == row['graph'] and R.sha(R.canonical(graph)) == row['graph_sha256'], 'Submitted graph differs')
    sub = e.json(folder / 'submission.json'); history = e.json(folder / 'history.json')
    result = e.json(folder / 'result.json'); pid = sub['prompt_id']
    require(isinstance(pid, str) and pid and pid not in seen and not sub.get('node_errors'), 'Duplicate/failed submission')
    seen.add(pid)
    require(history['prompt'][:3] == [sub['number'], pid, graph] and result['prompt_id'] == pid and
            result['name'] == row['name'] and result['status'] == history['status'], 'Request/history identity differs')
    status = history['status']; messages = status['messages']
    require(status['status_str'] == 'success' and status['completed'] is True and
            all(m[1].get('prompt_id') == pid for m in messages), 'Incomplete execution')
    require(not any(m[0] in ('execution_error', 'execution_interrupted') or
                    (m[0] == 'execution_cached' and m[1].get('nodes')) for m in messages), 'Failed/cached execution')
    starts = [m[1]['timestamp'] for m in messages if m[0] == 'execution_start']
    ends = [m[1]['timestamp'] for m in messages if m[0] == 'execution_success']
    require(len(starts) == len(ends) == 1 and all(type(t) is int for t in starts + ends) and
            previous_end <= starts[0] < ends[0], 'Request time ordering differs')
    events = [R.strict_json(line) for line in e.raw(folder / 'events.jsonl').splitlines()]
    require(events and events[-1]['type'] == 'execution_success' and
            all(v['data'].get('prompt_id') == pid for v in events), 'Event identity/completion differs')
    require(all(type(v.get('seconds')) in (int, float) and math.isfinite(v['seconds']) and v['seconds'] >= 0 for v in events) and
            all(a['seconds'] <= b['seconds'] for a, b in zip(events, events[1:])), 'Event clock differs')
    require(not any(v['type'] in ('execution_error', 'execution_interrupted') or
                    (v['type'] == 'execution_cached' and v['data'].get('nodes')) for v in events), 'Failed/cached event')
    require([v['data'].get('timestamp') for v in events if v['type'] == 'execution_start'] == starts and
            [v['data'].get('timestamp') for v in events if v['type'] == 'execution_success'] == ends, 'Event/history time differs')
    nodes = [v['data'].get('node') for v in events if v['type'] == 'executing']
    required = ['364', '428', '426', '414']
    require(all(nodes.count(n) == 1 for n in required) and
            [nodes.index(n) for n in required] == sorted(nodes.index(n) for n in required), 'Optimized node execution/order differs')
    require(e.json(folder / 'identity.json') == identity, 'Request source/runtime/process differs')
    return pid, starts[0], ends[0]


def phase_binding(value, role, name, phase, reference, reference_sha, candidate_sha=None):
    auth = value.get('phase_authorization') if role != 'auxiliary' else value.get('session_observation')
    require(isinstance(auth, dict), 'Missing phase binding')
    require(auth.get('role') == role and auth.get('run_name') == name and
            auth.get('phase') == ('optimized_preparation' if phase == 'candidate-check' else 'timing') and
            auth.get('qualification_id') == R.QUALIFICATION_ID and auth.get('plan_sha256') == R.PLAN_SHA and
            auth.get('comparison_mode') == 'same-size-native-v1' and
            auth.get('runtime_manifest_sha256') == reference['runtime_manifest_sha256'] and
            auth.get('server_identity_sha256') == reference['server_identity_sha256'] and
            auth.get('reference_receipt_sha256') == reference_sha, 'Phase identity differs')
    if phase == 'timed':
        require(auth.get('candidate_receipt_sha256') == candidate_sha, 'Timing candidate binding differs')
    require(value.get('output_size') == '640x384' and value.get('speed_only') is False and
            value.get('output_parity_claimed') is False, 'Geometry or premature parity claim differs')


def _verify(root, plan_path, reference_receipt_path, reference_sha256, phase,
            candidate_receipt_path=None, candidate_sha256=None):
    require(phase in ('candidate-check', 'timed'), 'Unknown verification phase')
    root = R.safe_path(root); require(not (root / 'FAULT.json').exists(), 'Fault present')
    e = R.Evidence(); plan = R.load_plan(plan_path, e)
    reference = R.verify_receipt(reference_receipt_path, reference_sha256)
    require(str(root) == reference['inputs']['root'], 'Native/candidate evidence roots differ')
    e.raw(reference_receipt_path)
    contract = e.json(Path(reference['inputs']['runtime_contract_path']))
    server = R.safe_path(contract['server_run']); identity = e.json(server / 'server-identity.json')
    require(R.sha(R.canonical(identity)) == R.sha(R.canonical(e.json(root / 'requests' / plan['requests'][0]['name'] / 'identity.json'))), 'Native identity differs')
    require(not (server / 'FAULT.json').exists() and not (server / 'resolution-halt.json').exists(), 'Server fault/halt present')
    candidate = None
    if phase == 'timed':
        require(candidate_receipt_path is not None and candidate_sha256 is not None, 'Timing needs verified candidate')
        candidate = verify_candidate_receipt(candidate_receipt_path, candidate_sha256)
        require(candidate['reference_receipt_sha256'] == reference_sha256 and candidate['inputs']['root'] == str(root), 'Candidate basis differs')
        e.raw(candidate_receipt_path)
    else:
        require(candidate_receipt_path is None and candidate_sha256 is None, 'Unexpected candidate input')
    rows = R.request_groups(plan)[phase]
    require(len(rows) == (14 if phase == 'candidate-check' else 44), 'Request count differs')
    base = rows[0]['clip_index']; expected_count = len(rows) - 4
    references = {r['name']: r for r in reference['executions'][:10]}
    seen = {r['prompt_id'] for r in reference['executions']}
    if candidate:
        seen.update(r['prompt_id'] for r in candidate['executions'])
    previous_end = (candidate or reference)['executions'][-1]['success_ms']
    executions = []; emitted = []
    for i, row in enumerate(rows):
        name = row['name']; pid, start, end = request_evidence(e, root, row, identity, previous_end, seen)
        previous_end = end
        text = e.json(server / ('pipeline-' + name + '.json'))
        sampler = e.json(server / ('pipeline-sampler-' + name + '.json'))
        decode = e.json(server / ('pipeline-decode-' + name + '.json'))
        for value, role, schema in ((text, 'text', None), (sampler, 'sampler', 'ltx.pipeline-sampler-request.v1'),
                                    (decode, 'decode', 'ltx.pipeline-decode-request.v1')):
            require(value.get('passed') is True and value.get('run_name') == name and
                    value.get('server_identity_sha256') == reference['server_identity_sha256'] and
                    value.get('model_verification_sha256') == identity['model_verification_sha256'], 'Pipeline request identity/failure')
            if schema:
                require(value.get('schema') == schema, 'Pipeline schema differs')
            phase_binding(value, role, name, phase, reference, reference_sha256, candidate_sha256)
        # Actual pipeline_node._job_tag namespaces window-conditioning jobs.
        text_sha = R.sha(('pipeline-window\n' + row['graph']['364']['inputs']['text']).encode('utf-8'))
        require(text['clip_index'] == row['clip_index'] and text['mode'] == 'pipeline-window' and text['depth'] == 2 and
                text['detail'].get('text_sha256') == text_sha and text['detail'].get('tag') == text_sha and
                text['detail'].get('speculation_miss') is False and
                text['detail']['window_encode']['window'] == 64 and
                text['detail']['window_encode']['clip_index'] == row['clip_index'], 'Conditioning provenance differs')
        sample_index = -1 if i < 2 else row['clip_index'] - 2
        emit_index = -1 if i < 4 else base + row['expected_emitted_index']
        require(sampler['clip_index'] == row['clip_index'] and sampler['mode'] == 'pipeline-lean' and
                sampler['depth'] == 2 and sampler['sampler_batch'] == 1 and sampler['sampler_workers'] == 2 and
                sampler['detail']['emitted_index'] == sample_index, 'Sampler emission differs')
        require(decode['clip_index'] == sample_index and decode['mode'] == 'pipeline-replica' and
                decode['depth'] == 2 and decode['upstream_depth'] == 0 and
                decode['detail']['emitted_index'] == emit_index and not decode.get('save_failures'), 'Decode emission/failure differs')
        record = {'name': name, 'prompt_id': pid, 'start_ms': start, 'success_ms': end,
                  'graph_sha256': row['graph_sha256'], 'fill': i < 4,
                  'emitted_index': None if i < 4 else row['expected_emitted_index']}
        if phase == 'timed':
            expected_scope = ('unscored-fill' if i < 4 else 'full-suite-pass' if i < 14 else 'bounded-continuity')
            require(row['timing_scope'] == expected_scope and
                    row.get('emitted_suite_pass') == (None if i < 4 else (i-4)//10+1),
                    'Timing block mapping differs')
            record.update(timing_scope=expected_scope, emitted_suite_pass=row.get('emitted_suite_pass'))
        if i < 4:
            require(row['reference'] is None and row['expected_emitted_fixture'] is None, 'Fill cannot have oracle')
            record['parity_status'] = 'not-scored-fill'
        else:
            ref = references[row['reference']]
            require(ref['fixture'] == row['expected_emitted_fixture'], 'Fixture/reference mapping differs')
            out = root / 'output/validation' / name
            meta = e.json(out / 'summary.json')
            require(meta.get('run_name') == name and meta.get('sample_rate') == 48000 and
                    meta.get('deterministic_enabled') is True and meta.get('deterministic_warn_only') is False, 'Capture identity/determinism differs')
            tensors = R.tensor_inventory(e.raw(out / 'tensors.safetensors'), meta['tensors'])
            require(tensors == ref['tensors'], 'Four-tensor native equality failed')
            times = {}
            for stage in ('sample', 'decode', 'save'):
                done = e.json(server / ('pipeline-done-%s-%d.json' % (stage, emit_index)))
                require(done.get('stage') == stage and done.get('index') == emit_index and
                        type(done.get('finished_unix')) in (int, float) and math.isfinite(done['finished_unix']), 'Worker completion differs')
                phase_binding(done, 'auxiliary', None, phase, reference, reference_sha256, candidate_sha256)
                times[stage] = done['finished_unix']
                if stage == 'sample': require(done.get('finite') is True, 'Sampler sentry nonfinite')
                if stage == 'decode': require(done.get('slot') == ('native', 'replica')[emit_index % 2], 'Decoder slot differs')
                if stage == 'save': saved = done.get('saved')
            require(times['sample'] <= times['decode'] <= times['save'] and times['decode'] <= end / 1000,
                    'Worker completion ordering differs')
            # W2 samples run two prompts behind; the decode is queued on producer+2.
            # The current emitting prompt is producer+4; raw capture holds that clip.
            prefix = rows[row['expected_emitted_index'] + 2]['name'] + '/preview'
            save = e.json(server / ('pipeline-save-' + name + '.json'))
            require(save.get('schema') == 'ltx.pipeline-save-record.v2' and save.get('run_name') == name and
                    save.get('status') == 'queued-to-writer' and save.get('prefix') == prefix and
                    save.get('saved_file') is None and isinstance(saved, str) and saved.startswith(prefix + '_') and
                    saved.endswith('.mp4') and '..' not in Path(saved).parts and not Path(saved).is_absolute(), 'Preview completion/prefix differs')
            e.raw(root / 'output' / saved)
            emitted.append(row['expected_emitted_index'])
            record.update(fixture=ref['fixture'], reference=row['reference'], tensors=tensors,
                          parity_status='four-tensors-exact', worker_finished_unix=times, preview=saved)
        executions.append(record)
    require(emitted == list(range(expected_count)), 'Emitted sequence differs')
    e.recheck()
    require(not (root / 'FAULT.json').exists() and not (server / 'FAULT.json').exists() and
            not (server / 'resolution-halt.json').exists(), 'Fault/halt before receipt')
    result = {'schema': 'ltx.same-size-optimized-evidence.v1',
              'status': 'candidate_verified' if phase == 'candidate-check' else 'timed_verified',
              'phase': phase, 'plan_sha256': R.PLAN_SHA, 'qualification_id': R.QUALIFICATION_ID,
              'runtime_manifest_sha256': reference['runtime_manifest_sha256'],
              'server_identity_sha256': reference['server_identity_sha256'],
              'reference_receipt_sha256': reference_sha256, 'candidate_receipt_sha256': candidate_sha256,
              'four_tensor_exact_clips': expected_count, 'distinct_fixtures': 10, 'fills_not_scored': 4,
              'executions': executions, 'evidence_sha256': e.hashes,
              'inputs': {'root': str(root), 'plan_path': str(plan_path), 'reference_receipt_path': str(reference_receipt_path),
                         'candidate_receipt_path': str(candidate_receipt_path) if candidate_receipt_path else None},
              'claim': 'Exact native-reference bytes for ten original fixtures only; fills excluded. Repeated timing/continuity clips do not establish broader visual quality, resolution, duration or a speed record.'}
    if phase == 'timed':
        ends = [r['success_ms'] for r in executions if not r['fill']]
        require(len(ends) == 40, 'Forty timed/continuity emissions required')
        intervals = lambda values: [(b-a)/1000 for a,b in zip(values, values[1:])]
        result['completion_intervals_seconds'] = intervals(ends[:10])
        result['continuity_completion_intervals_seconds'] = intervals(ends[10:])
        result['aggregate_completion_intervals_seconds'] = intervals(ends)
        result['boundary_interval_seconds'] = (ends[10]-ends[9])/1000
        result['timing_definition'] = ('Nine server-success intervals between the initial ten emitted original fixtures, '
            'each once; preview completion checked separately. This is the initial full-suite screen.')
        result['continuity_timing_definition'] = ('Twenty-nine server-success intervals within the subsequent thirty '
            'emissions, three original-suite repetitions. Boundary from initial screen excluded; continuity evidence only.')
        result['aggregate_timing_definition'] = ('All thirty-nine intervals, including the initial-to-continuity boundary; '
            'diagnostic aggregate only, not a headline or record.')
        result['timing_blocks'] = {'initial': {'emissions': 10, 'intervals': 9, 'fixture_passes': 1},
                                   'continuity': {'emissions': 30, 'intervals': 29, 'fixture_passes': 3}}
    return result


def verify_outputs(root, plan_path, reference_receipt_path, reference_sha256, phase, output_path,
                   candidate_receipt_path=None, candidate_sha256=None):
    output_path = R.safe_path(output_path); require(not output_path.exists(), 'Receipt already exists')
    result = _verify(root, plan_path, reference_receipt_path, reference_sha256, phase, candidate_receipt_path, candidate_sha256)
    with output_path.open('xb') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n')
        stream.flush(); os.fsync(stream.fileno())
    fd = os.open(output_path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return result


def verify_candidate_receipt(path, expected_sha256):
    raw = R.read_file(path); require(R.sha(raw) == R.digest(expected_sha256), 'Candidate receipt digest differs')
    receipt = R.strict_json(raw)
    require(receipt.get('status') == 'candidate_verified' and receipt.get('phase') == 'candidate-check', 'Not a candidate receipt')
    inputs = receipt['inputs']
    actual = _verify(Path(inputs['root']), Path(inputs['plan_path']), Path(inputs['reference_receipt_path']),
                     receipt['reference_receipt_sha256'], 'candidate-check')
    require(R.canonical(actual) == R.canonical(receipt), 'Candidate receipt differs from actual evidence')
    return actual

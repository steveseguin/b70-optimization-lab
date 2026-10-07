#!/usr/bin/env python3
"""CPU-only, fail-closed native reference gate. No request submission or phase authority."""
import argparse
import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys

PLAN_SHA = '5973dddeed7f1af0324c87aab04ad9b95c0e452181a7c92e81134fcd075479dd'
PARENT_SHA = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
MODEL_VERIFICATION_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
QUALIFICATION_ID = '007ffea2b24009bb6ae84f03cac7372a708e2dc193da0661562ffb1ddedca534'
SHAPES = {'images': [25, 384, 640, 3], 'video_latent': [1, 128, 4, 12, 20],
          'audio_latent': [1, 8, 26, 16], 'waveform': [1, 2, 48480]}
REQUIRED_NODES = {'364', '344', '348', '368', '374', '358', '414'}
MAX_FILE_BYTES = 90 * 1024**2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid digest')
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def safe_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe path')
    return path


def read_file(path):
    path = safe_path(path)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size <= MAX_FILE_BYTES, 'Nonregular, linked or oversized evidence')
        raw = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(stream.fileno())
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(fields(before) == fields(after) == fields(path.stat()) and len(raw) == before.st_size,
            'Evidence changed during read')
    return raw


class Evidence:
    def __init__(self):
        self.hashes = {}

    def raw(self, path):
        raw = read_file(path)
        name = str(path)
        require(name not in self.hashes or self.hashes[name] == sha(raw), 'Evidence changed')
        self.hashes[name] = sha(raw)
        return raw

    def json(self, path):
        return strict_json(self.raw(path))

    def recheck(self):
        for path, expected in self.hashes.items():
            require(sha(read_file(path)) == expected, 'Evidence changed before receipt')


def tensor_inventory(raw, metadata):
    """Read actual safetensors F32 bytes, shape/layout, hashes and every value's finiteness."""
    require(len(raw) >= 8, 'Truncated archive')
    header_size = struct.unpack('<Q', raw[:8])[0]
    require(0 < header_size <= 65536 and 8 + header_size <= len(raw), 'Invalid tensor header')
    header = strict_json(raw[8:8 + header_size])
    header.pop('__metadata__', None)
    require(set(header) == set(metadata) == set(SHAPES), 'Four tensor set differs')
    payload = memoryview(raw)[8 + header_size:]
    cursor = 0
    result = {}
    ordered = sorted(header.items(), key=lambda kv: kv[1]['data_offsets'][0])
    for key, entry in ordered:
        require(set(entry) == {'dtype', 'shape', 'data_offsets'} and entry['dtype'] == 'F32', 'Tensor dtype/header differs')
        require(entry['shape'] == SHAPES[key] and all(type(v) is int for v in entry['shape']), 'Tensor shape differs')
        offsets = entry['data_offsets']
        size = math.prod(SHAPES[key]) * 4
        require(len(offsets) == 2 and all(type(v) is int for v in offsets) and
                offsets == [cursor, cursor + size] and cursor + size <= len(payload), 'Tensor offsets differ')
        part = payload[cursor:cursor + size]
        values = array.array('f'); values.frombytes(part)
        if sys.byteorder != 'little':
            values.byteswap()
        require(all(math.isfinite(v) for v in values), 'Nonfinite tensor bytes')
        item = {'dtype': 'torch.float32', 'shape': SHAPES[key], 'sha256': sha(part), 'finite': True}
        require(all(metadata[key].get(k) == v for k, v in item.items()), 'Tensor metadata differs from bytes')
        result[key] = item
        cursor += size
    require(cursor == len(payload), 'Unclaimed tensor bytes')
    return result


def load_plan(path, evidence):
    envelope = evidence.json(path)
    require(set(envelope) == {'plan', 'plan_sha256'} and envelope['plan_sha256'] == PLAN_SHA and
            sha(canonical(envelope['plan'])) == PLAN_SHA, 'Unreviewed plan')
    plan = envelope['plan']
    require(plan['qualification_id'] == QUALIFICATION_ID and
            plan['basis']['parent_manifest_sha256'] == PARENT_SHA and not plan['runtime_qualified'], 'Plan basis differs')
    return plan


def native_state(value, identity_hash, qualification_id):
    # Required NEW runtime observation schema, not inferred from historical success receipts.
    require(value.get('schema') == 'ltx.native-reference-state.v1' and
            value.get('phase') == 'native_reference' and
            value.get('server_identity_sha256') == identity_hash and
            value.get('qualification_id') == qualification_id, 'Native phase identity differs')
    for key in ('sampler_routes', 'lean_sampler_installs', 'decode_replicas', 'oom_fallback_attempts'):
        require(type(value.get(key)) is int and value[key] == 0, 'Optimized/fallback state present')
    for key in ('queue_running', 'queue_pending', 'pending_encode', 'pending_sample', 'pending_decode', 'pending_save'):
        require(value.get(key) == [], 'Native phase not quiescent')
    require(value.get('native_residency_admitted') is True and value.get('no_owner_eviction') is True and
            value.get('oom_to_tiled_refusal_installed') is True, 'Native safety admission missing')
    require(type(value.get('timestamp_ms')) is int and value['timestamp_ms'] > 0, 'Native phase timestamp missing')
    return value['timestamp_ms']


def _verify_references(root, plan_path, runtime_contract_path, runtime_contract_sha256, output_path=None):
    root = safe_path(root)
    if output_path is not None:
        output_path = safe_path(output_path)
        require(not output_path.exists(), 'Receipt already exists')
    require(not (root / 'FAULT.json').exists(), 'Fault present')
    evidence = Evidence(); plan = load_plan(plan_path, evidence)
    contract_raw = evidence.raw(runtime_contract_path)
    require(sha(contract_raw) == digest(runtime_contract_sha256), 'Unbound runtime contract')
    contract = strict_json(contract_raw)
    require(contract.get('schema') == 'ltx.native-reference-runtime-contract.v1' and
            contract.get('plan_sha256') == PLAN_SHA and contract.get('parent_manifest_sha256') == PARENT_SHA,
            'Runtime contract basis differs')
    server_dir = safe_path(contract['server_run'])
    require(not (server_dir / 'resolution-halt.json').exists(), 'Native session halted')
    identity_raw = evidence.raw(server_dir / 'server-identity.json')
    identity_hash = sha(identity_raw)
    require(identity_hash == digest(contract['server_identity_sha256']), 'Runtime server identity differs')
    identity = strict_json(identity_raw)
    require(identity['source_packet_manifest_sha256'] == digest(contract['successor_manifest_sha256']) and
            identity['model_verification_sha256'] == digest(contract['model_verification_sha256']) ==
            MODEL_VERIFICATION_SHA256, 'Source/model binding differs')
    for key in ('pid', 'proc_start_ticks', 'boot_id', 'source_commit', 'runtime', 'rope_compatibility'):
        require(identity.get(key) is not None, 'Incomplete server identity: ' + key)
    # Runtime launch must hash-bind its observation implementation/admission inputs in this contract.
    require(isinstance(contract.get('runtime_evidence'), dict) and contract['runtime_evidence'], 'Missing runtime evidence')
    for path, expected in contract['runtime_evidence'].items():
        require(sha(evidence.raw(safe_path(path))) == digest(expected), 'Runtime evidence binding differs')
    states = []
    for key in ('before_native', 'after_native'):
        binding = contract[key]; raw = evidence.raw(safe_path(binding['path']))
        require(sha(raw) == digest(binding['sha256']), 'Native state binding differs')
        states.append(native_state(strict_json(raw), identity_hash, QUALIFICATION_ID))
    require(states[0] < states[1], 'Native state ordering differs')
    native = plan['requests'][:6]
    require(contract.get('request_names') == [row['name'] for row in native], 'Native request order differs')
    executions = []; seen_ids = set(); previous_end = states[0]
    for row in native:
        name = row['name']; request = root / 'requests' / name
        graph = evidence.json(request / 'prompt.json')
        require(graph == row['graph'] and sha(canonical(graph)) == row['graph_sha256'], 'Submitted graph differs')
        submission = evidence.json(request / 'submission.json')
        history = evidence.json(request / 'history.json')
        result = evidence.json(request / 'result.json')
        pid = submission['prompt_id']
        require(isinstance(pid, str) and pid and pid not in seen_ids and not submission.get('node_errors'), 'Duplicate/failed submission')
        seen_ids.add(pid)
        require(history['prompt'][1] == result['prompt_id'] == pid and history['prompt'][2] == graph and
                history['prompt'][0] == submission['number'] and result['name'] == name, 'Request/history identity differs')
        require(result['status'] == history['status'] and history['status']['status_str'] == 'success' and
                history['status'].get('completed') is True, 'Incomplete native execution')
        messages = history['status']['messages']
        require(all(msg[1].get('prompt_id') == pid for msg in messages), 'History message identity differs')
        require(not any(msg[0] == 'execution_cached' and msg[1].get('nodes') for msg in messages), 'Cached native execution')
        starts = [m[1]['timestamp'] for m in messages if m[0] == 'execution_start']
        ends = [m[1]['timestamp'] for m in messages if m[0] == 'execution_success']
        require(len(starts) == len(ends) == 1 and all(type(t) is int for t in starts + ends) and
                previous_end <= starts[0] < ends[0] <= states[1], 'Native execution timestamps reordered/overlapping')
        previous_end = ends[0]
        event_raw = evidence.raw(request / 'events.jsonl')
        events = [strict_json(line) for line in event_raw.splitlines()]
        require(events and all(e['data'].get('prompt_id') == pid for e in events), 'Event identity differs')
        require(all(isinstance(e.get('seconds'), (int, float)) and math.isfinite(e['seconds']) and e['seconds'] >= 0 for e in events) and
                all(a['seconds'] <= b['seconds'] for a, b in zip(events, events[1:])), 'Event clock differs')
        require(events[-1]['type'] == 'execution_success' and
                not any(e['type'] in ('execution_error', 'execution_interrupted') for e in events), 'Native event failure')
        require([e['data'].get('timestamp') for e in events if e['type'] == 'execution_start'] == starts and
                [e['data'].get('timestamp') for e in events if e['type'] == 'execution_success'] == ends,
                'Event/history timestamps differ')
        require(not any(e['type'] == 'execution_cached' and e['data'].get('nodes') for e in events),
                'Cached event stream')
        nodes = [e['data'].get('node') for e in events if e['type'] == 'executing']
        require(REQUIRED_NODES <= set(nodes) and all(nodes.count(n) == 1 for n in REQUIRED_NODES), 'Missing/duplicate native sampler/decode execution')
        require(nodes.index('364') < nodes.index('344') < nodes.index('348') < nodes.index('368') < nodes.index('414') and
                nodes.index('368') < nodes.index('374') < nodes.index('414') and
                nodes.index('368') < nodes.index('358') < nodes.index('414'), 'Native node order differs')
        request_identity = evidence.json(request / 'identity.json')
        require(request_identity == identity, 'Native source/runtime/process differs')
        pipeline = evidence.json(server_dir / ('pipeline-' + name + '.json'))
        # Pinned pipeline_node._job_tag separates window jobs from full-text
        # jobs. detail.text_sha256 is that job tag, not the raw text digest.
        detail = pipeline['detail']
        text_sha = sha(('pipeline-window\n' + graph['364']['inputs']['text']).encode('utf-8'))
        require(pipeline.get('passed') is True and pipeline['run_name'] == name and
                pipeline['clip_index'] == row['clip_index'] and pipeline['depth'] == 2 and
                pipeline['mode'] == 'pipeline-window', 'Conditioning request differs')
        require(pipeline.get('server_identity_sha256') == identity_hash and
                pipeline.get('model_verification_sha256') == identity['model_verification_sha256'] and
                pipeline.get('output_size') == '640x384' and pipeline.get('speed_only') is False,
                'Conditioning server/model/geometry differs')
        require(detail.get('text_sha256') == text_sha and detail.get('tag') == text_sha and
                detail.get('started_ahead') == [] and detail.get('pending_after') == [] and
                detail.get('speculation_miss') is False, 'Native conditioning/ahead state differs')
        require(detail['window_encode']['window'] == 64 and
                detail['window_encode']['clip_index'] == row['clip_index'], 'Conditioning window/index differs')
        conditioning = digest(detail['conditioning_fingerprint'])
        output = root / 'output/validation' / name
        meta = evidence.json(output / 'summary.json')
        require(meta.get('run_name') == name and meta.get('sample_rate') == 48000 and
                meta.get('deterministic_enabled') is True and meta.get('deterministic_warn_only') is False,
                'Capture determinism/identity differs')
        inventory = tensor_inventory(evidence.raw(output / 'tensors.safetensors'), meta['tensors'])
        executions.append({'name': name, 'fixture': row['fixture'], 'clip_index': row['clip_index'],
                           'prompt_id': pid, 'graph_sha256': row['graph_sha256'],
                           'start_ms': starts[0], 'success_ms': ends[0],
                           'conditioning_sha256': conditioning, 'tensors': inventory})
    for first, repeat in zip(executions[:3], executions[3:]):
        require(first['fixture'] == repeat['fixture'] and first['tensors'] == repeat['tensors'] and
                first['conditioning_sha256'] == repeat['conditioning_sha256'], 'Native repeat differs')
    evidence.recheck()
    require(not (root / 'FAULT.json').exists() and not (server_dir / 'resolution-halt.json').exists(),
            'Fault/session halt before reference receipt')
    receipt = {'schema': 'ltx.same-size-native-reference.v1', 'status': 'reference_verified',
               'plan_sha256': PLAN_SHA, 'qualification_id': QUALIFICATION_ID,
               'parent_manifest_sha256': PARENT_SHA, 'server_identity_sha256': identity_hash,
               'runtime_manifest_sha256': contract['successor_manifest_sha256'],
               'runtime_contract_sha256': runtime_contract_sha256, 'executions': executions,
               'inputs': {'root': str(root), 'plan_path': str(plan_path),
                          'runtime_contract_path': str(runtime_contract_path)},
               'four_tensor_repeat_pairs_exact': 3, 'evidence_sha256': evidence.hashes,
               'claim': 'Three native sampler/decode fixture repeats with accepted graph-sharded window encoder; no optimized candidate or timing qualification.'}
    if output_path is None:
        return receipt
    raw = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False).encode() + b'\n'
    with output_path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(output_path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return receipt


def verify_references(root, plan_path, runtime_contract_path, runtime_contract_sha256, output_path):
    require(output_path is not None, 'Exclusive output path required')
    return _verify_references(root, plan_path, runtime_contract_path, runtime_contract_sha256, output_path)


def verify_receipt(path, expected_sha256):
    """Reconstruct proof from retained source artifacts, not a receipt's self-asserted status."""
    raw = read_file(path)
    require(sha(raw) == digest(expected_sha256), 'Reference receipt digest differs')
    receipt = strict_json(raw)
    require(receipt.get('schema') == 'ltx.same-size-native-reference.v1' and
            receipt.get('status') == 'reference_verified' and receipt.get('plan_sha256') == PLAN_SHA and
            receipt.get('qualification_id') == QUALIFICATION_ID and
            digest(receipt.get('runtime_manifest_sha256')) and
            receipt.get('four_tensor_repeat_pairs_exact') == 3 and len(receipt.get('executions', [])) == 6,
            'Reference receipt contract differs')
    require(receipt.get('evidence_sha256'), 'Reference evidence missing')
    for source, expected in receipt['evidence_sha256'].items():
        require(sha(read_file(source)) == digest(expected), 'Reference evidence changed')
    inputs = receipt['inputs']
    reconstructed = _verify_references(Path(inputs['root']), Path(inputs['plan_path']),
                                       Path(inputs['runtime_contract_path']),
                                       receipt['runtime_contract_sha256'])
    require(canonical(reconstructed) == canonical(receipt), 'Reference receipt differs from actual evidence')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--runtime-contract', type=Path, required=True)
    parser.add_argument('--runtime-contract-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify_references(args.root, args.plan, args.runtime_contract,
                               args.runtime_contract_sha256, args.output)
    print(json.dumps({'status': result['status'], 'executions': len(result['executions'])}))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Plan/apply exact duplicate retirement after a complete arm and server exit.

No service/model/device operations. Only registered tensors.safetensors files
are eligible; metadata, previews, references and first clips per fixture stay.
Default mode writes an exclusive reviewable plan, never deletes anything.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
KEYS = {'images', 'video_latent', 'audio_latent', 'waveform'}
NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,150}\Z')
MAX_JSON = 16 * 1024**2


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe(path, *, exists=True):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute normalized path required')
    for parent in [path, *path.parents]:
        need(not parent.is_symlink(), 'symlink refused: ' + str(parent))
    if exists:
        need(path.exists(), 'missing path: ' + str(path))
    return path


def fingerprint(path):
    path = safe(path)
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'regular unlinked file required: ' + str(path))
    sha = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(block)
    after = path.stat()
    attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
    need(all(getattr(before, k) == getattr(after, k) for k in attrs), 'file changed while hashing')
    return {'path': str(path), 'sha256': sha.hexdigest(),
            **{k: getattr(after, k) for k in attrs}}


def read_json(path, evidence):
    path = safe(path)
    need(path.stat().st_size <= MAX_JSON, 'JSON exceeds bounded input size')
    record = fingerprint(path)
    value = json.loads(path.read_bytes())
    need(fingerprint(path) == record, 'JSON changed during read')
    evidence[str(path)] = record
    return value


def process_exists(pid):
    # No signals: absence is conservative, including PID reuse and zombies.
    return Path('/proc', str(pid)).exists()


def server_gone(identity):
    pid = identity.get('pid')
    need(type(pid) is int and pid > 1, 'invalid server PID')
    need(str(identity.get('proc_start_ticks', '')).isdigit(), 'missing server start ticks')
    need(not process_exists(pid), 'server PID still exists; retirement is post-shutdown only')


def request_binding(root, name, evidence, server=None):
    request = root / 'requests' / name
    docs = {key: read_json(request / (key + '.json'), evidence)
            for key in ('prompt', 'history', 'submission', 'result', 'identity')}
    h, sub, result = docs['history'], docs['submission'], docs['result']
    need(h['prompt'][1] == sub['prompt_id'] == result['prompt_id'], 'request ID binding differs')
    need(h['prompt'][2] == docs['prompt'], 'history prompt differs')
    need(h['status']['status_str'] == 'success' and h['status'].get('completed') is True,
         'request not completed successfully')
    need(not any(m[0] == 'execution_error' or
                 (m[0] == 'execution_cached' and m[1].get('nodes'))
                 for m in h['status']['messages']), 'cached/failed request')
    if server is not None:
        for key in ('pid', 'proc_start_ticks', 'boot_id', 'source_packet_manifest_sha256'):
            need(docs['identity'].get(key) == server.get(key) and key in server, 'candidate server identity differs: ' + key)
    return docs


def build_plan(root, throughput):
    root = safe(root)
    evidence = {}
    result = read_json(throughput, evidence)
    need(result.get('schema') == 'ltx.throughput-fixtures-96.v1', 'unsupported throughput schema')
    need(result.get('all_exact') is True and result.get('emission_sequence_ok') is True,
         'complete exact arm required')
    # Packet97 successful receipts omit exit_code; packet98's writer adds it.
    # Absence is admitted only with all structural success proofs below.
    need(('exit_code' not in result or
          (type(result['exit_code']) is int and result['exit_code'] == 0)) and not result.get('emission_problems') and
         not result.get('shape_problems') and result.get('references_from'), 'failed/incomplete/no-oracle arm')
    prefix = result.get('prefix')
    need(isinstance(prefix, str) and NAME.fullmatch(prefix), 'invalid arm prefix')
    server_path = safe(Path(result['server_run']))
    need(server_path.is_relative_to(root) and server_path != root, 'server directory outside root')
    server = read_json(server_path / 'server-identity.json', evidence)
    server_gone(server)
    need(not (root / 'FAULT.json').exists() and not (server_path / 'FAULT.json').exists(), 'fault evidence present; preserve outputs')
    prereg = read_json(Path(result['references_from']), evidence)
    fixtures = prereg['fixtures']
    refs = {f['id']: f['reference'] for f in fixtures}
    need(len(refs) == len(fixtures) == result['fixture_count'], 'fixture census differs')
    need(all(NAME.fullmatch(k) and NAME.fullmatch(v) for k, v in refs.items()), 'unsafe fixture/reference')
    rows = result['rows']
    need(type(result['count']) is int and result['count'] > 0 and len(rows) == result['count'], 'incomplete row census')
    need([r['index'] for r in rows] == list(range(result['count'])), 'prompt index sequence differs')
    need(len(result['fixture_order']) == result['count'], 'fixture order census differs')
    emitted = [r for r in rows if r.get('fill') is False]
    expected = max(0, result['count'] - result['sampler_depth'] - result['decode_depth'])
    need(expected > 0 and expected == result['expected_clips'] == result['distinct_clips_emitted'] == len(emitted), 'emission count differs')
    need([r['emitted_index'] for r in emitted] == list(range(expected)), 'emitted clips not unique/in order')
    registered = {r['prompt'] for r in rows}
    need(len(registered) == len(rows) and not registered.intersection(refs.values()), 'duplicate/protected request names')
    need(all(r['prompt'] == f"{prefix}-{r['index']:02d}" for r in rows), 'unregistered prompt name')
    for r in rows:
        need(r.get('fill') is False or (r.get('fill') is True and r.get('emitted_index') == -1 and
             r.get('parity_status') == 'fill' and r.get('exact') is True), 'malformed fill row')
    kept, retire, seen, raw_records = [], [], set(), {}
    for row in emitted:
        name, fixture = row['prompt'], row['emitted_fixture']
        need(row.get('exact') is True and row.get('parity_status') == 'passed' and not row.get('duplicate'), 'nonexact row')
        need(fixture in refs and result['fixture_order'][row['emitted_index']] == fixture and
             row.get('reference') == refs[fixture], 'fixture/reference binding differs')
        reference = refs[fixture]
        parity = read_json(Path(throughput).parent / (name + '-parity.json'), evidence)
        need(parity.get('status') == 'passed' and set(parity.get('comparisons', {})) == KEYS and
             all(v.get('bitwise_equal') is True and v.get('same_layout') is True
                 for v in parity['comparisons'].values()), 'parity receipt incomplete/nonexact')
        need([e['name'] for e in parity['executions']] == [reference, name], 'parity names differ')
        candidate_req = request_binding(root, name, evidence, server)
        reference_req = request_binding(root, reference, evidence)
        need(candidate_req['submission']['prompt_id'] != reference_req['submission']['prompt_id'], 'same execution as reference')
        need(candidate_req['identity']['model_verification_sha256'] ==
             reference_req['identity']['model_verification_sha256'], 'model identities differ')
        for label in (name, reference):
            meta = read_json(root / 'output/validation' / label / 'summary.json', evidence)
            need(meta.get('deterministic_enabled') is True and meta.get('deterministic_warn_only') is False and
                 set(meta['tensors']) == KEYS and all(v.get('finite') is True for v in meta['tensors'].values()),
                 'invalid/nonfinite capture summary')
        candidate_path = root / 'output/validation' / name / 'tensors.safetensors'
        reference_path = root / 'output/validation' / reference / 'tensors.safetensors'
        candidate = fingerprint(candidate_path)
        ref = fingerprint(reference_path)
        need(candidate['sha256'] == ref['sha256'] and candidate['st_size'] == ref['st_size'],
             'whole candidate archive differs from retained reference')
        need((candidate['st_dev'], candidate['st_ino']) != (ref['st_dev'], ref['st_ino']), 'candidate aliases reference')
        record = {'fixture': fixture, 'candidate': candidate, 'reference': ref}
        raw_records[str(candidate_path)] = candidate
        raw_records[str(reference_path)] = ref
        if fixture not in seen:
            kept.append(record)
            seen.add(fixture)
        else:
            retire.append(record)
    return {'schema': 'ltx.verified-output-retirement-plan.v1', 'root': str(root),
            'throughput': str(Path(throughput)), 'server_identity': server, 'prefix': prefix,
            'helper_sha256': fingerprint(Path(__file__).resolve())['sha256'],
            'validation': {'all_exact': True, 'emission_sequence_ok': True, 'completed_prompts': len(rows),
                           'exact_emitted_clips': len(emitted), 'server_pid_absent': True},
            'protected_references': sorted(set(refs.values())), 'keep_first_per_fixture': kept,
            'retire': retire, 'retire_bytes': sum(r['candidate']['st_size'] for r in retire),
            'evidence': list(evidence.values()), 'raw_files': list(raw_records.values()),
            'limits': 'post-shutdown exact whole-archive duplicates only; all metadata, previews and fill captures retained'}


def sync_json(path, value):
    path = safe(path, exists=False)
    need(path.parent.is_dir(), 'output parent missing')
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def unlink_exact(record):
    path = Path(record['path'])
    need(fingerprint(path) == record, 'candidate changed immediately before deletion')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        current = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        need(stat.S_ISREG(current.st_mode) and all(getattr(current, k) == record[k] for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')), 'candidate replaced before unlink')
        os.unlink(path.name, dir_fd=fd)
        os.fsync(fd)
    finally:
        os.close(fd)


def apply_plan(plan_path, expected_sha, receipt):
    plan_path = safe(plan_path)
    need(re.fullmatch(r'[0-9a-f]{64}', expected_sha or ''), 'explicit plan SHA256 required')
    need(fingerprint(plan_path)['sha256'] == expected_sha, 'plan hash mismatch')
    need(plan_path.stat().st_size <= MAX_JSON, 'plan too large')
    plan_bytes = plan_path.read_bytes()
    need(hashlib.sha256(plan_bytes).hexdigest() == expected_sha, 'plan changed during read')
    plan = json.loads(plan_bytes)
    need(plan == build_plan(Path(plan['root']), Path(plan['throughput'])), 'plan or underlying evidence changed')
    receipt = safe(receipt, exists=False)
    need(not receipt.exists(), 'receipt already exists')
    intent = receipt.with_name(receipt.name + '.intent.json')
    sync_json(intent, {'status': 'intent-before-any-deletion', 'plan_sha256': expected_sha, 'plan': plan})
    completed = []
    events = receipt.with_name(receipt.name + '.events.jsonl')
    # An exclusive event journal records each completed unlink durably. A crash
    # leaves the full intent plus the completed prefix; never resume automatically.
    with events.open('x') as f:
        f.flush(); os.fsync(f.fileno())
    directory = os.open(events.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    try:
        for row in plan['retire']:
            server_gone(plan['server_identity'])
            need(not (Path(plan['root']) / 'FAULT.json').exists(), 'new fault; preserve remaining outputs')
            need(fingerprint(Path(row['reference']['path'])) == row['reference'], 'reference changed immediately before deletion')
            unlink_exact(row['candidate'])
            completed.append(row['candidate'])
            with events.open('a') as f:
                f.write(json.dumps({'phase': 'deleted', 'candidate': row['candidate'],
                                    'reference': row['reference'], 'plan_sha256': expected_sha}) + '\n')
                f.flush(); os.fsync(f.fileno())
        sync_json(receipt, {'status': 'completed', 'plan_sha256': expected_sha, 'deleted': completed,
                           'reclaimed_logical_bytes': sum(r['st_size'] for r in completed),
                           'events': fingerprint(events)})
    except BaseException as error:
        if not receipt.exists():
            sync_json(receipt, {'status': 'incomplete-no-automatic-retry', 'plan_sha256': expected_sha,
                               'deleted': completed, 'error': repr(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--throughput', type=Path)
    parser.add_argument('--plan', type=Path, help='new output plan (default dry-run mode)')
    parser.add_argument('--apply-plan', type=Path)
    parser.add_argument('--plan-sha256')
    parser.add_argument('--receipt', type=Path)
    a = parser.parse_args()
    if a.apply_plan:
        need(a.receipt is not None and a.throughput is None and a.plan is None, 'apply requires receipt and no planning inputs')
        apply_plan(a.apply_plan, a.plan_sha256, a.receipt)
    else:
        need(a.throughput is not None and a.plan is not None and a.receipt is None and a.plan_sha256 is None,
             'dry-run requires --throughput and new --plan')
        plan = build_plan(a.root, a.throughput)
        sync_json(a.plan, plan)
        print(json.dumps({'plan': str(a.plan), 'plan_sha256': fingerprint(a.plan)['sha256'],
                          'retire_files': len(plan['retire']), 'retire_bytes': plan['retire_bytes'], 'deleted': False}))


if __name__ == '__main__':
    main()

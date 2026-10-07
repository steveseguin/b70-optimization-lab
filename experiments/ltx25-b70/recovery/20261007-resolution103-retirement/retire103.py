#!/usr/bin/env python3
"""Exact packet103 duplicate retirement. No service, device or endpoint operations."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PACKET = ROOT / 'prepared-resolution-full-103'
RUN = ROOT / 'encoder-server-resolution-full-103-two-way-w2-b1-p1-dxpu2-s640x384'
CLOSEOUT = REPO / 'experiments/ltx25-b70/data/resume-20261007/resolution103-closeout'
MANIFEST_SHA = 'a8b78c0a73a3045f902a2cf7f6ff55dff1931f4f4872b12576e976399708b5cb'
IDENTITY_SHA = '3685d61a1a62cbaae3d746a6008b7066520bc5c5725accdc1d910d43f409a218'
PLAN_SHA = '84bdccba3e2fe39b9bf5bcd1cd074c6ee74bbd8ade2a9be7aa63e945f5b07e1d'
PREFIX = 'resolution-full-20261007-'
FIXTURES = ['boat', 'marble', 'bird', 'pendulum', 'rain', 'paper', 'candle', 'pour', 'fabric', 'wheel']
SCHEMA = 'ltx.resolution103.duplicate-retirement.v1'
FLOOR = 50 * 1024**3


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def safe(path, exists=True):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts, 'absolute normalized path required')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink refused')
    if exists:
        need(path.exists(), 'missing path: ' + str(path))
    return path


STAT_KEYS = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink', 'st_blocks')


def fp(path):
    path = safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'regular nlink1 file required')
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
        after = os.fstat(stream.fileno())
        current = safe(path).stat()
        need(all(getattr(before, k) == getattr(after, k) == getattr(current, k) for k in STAT_KEYS), 'file changed while hashing')
    return {'path': str(path), 'sha256': digest.hexdigest(), **{k: getattr(after, k) for k in STAT_KEYS}}


def read_json(path, evidence=None):
    record = fp(path)
    need(record['st_size'] <= 32 * 1024**2, 'JSON too large')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                       parse_constant=lambda _: need(False, 'nonfinite JSON'))
    need(fp(path) == record, 'JSON changed during read')
    if evidence is not None:
        evidence[str(path)] = record
    return value


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fault_free():
    need(not any(p.exists() for p in (ROOT / 'FAULT.json', RUN / 'FAULT.json', RUN / 'resolution-halt.json')), 'fault/halt; preserve artifacts')


def reconstruct_proof():
    """Expensive, read-only: unchanged sealed verifier, never mutable author code."""
    evidence = {}
    manifest = read_json(PACKET / 'manifest.json', evidence)
    need(evidence[str(PACKET / 'manifest.json')]['sha256'] == MANIFEST_SHA, 'packet manifest differs')
    for name in ('reference_gate.py', 'candidate_gate.py'):
        path = PACKET / 'resolution/components' / name
        evidence[str(path)] = fp(path)
        need(evidence[str(path)]['sha256'] == manifest['files']['resolution/components/' + name], 'sealed verifier changed')
    gate = load(PACKET / 'resolution/components/candidate_gate.py', 'retirement103_sealed_gate')
    identity = read_json(RUN / 'server-identity.json', evidence)
    need(evidence[str(RUN / 'server-identity.json')]['sha256'] == IDENTITY_SHA and
         identity['source_packet_manifest_sha256'] == MANIFEST_SHA, 'server identity differs')
    plan_path = PACKET / 'resolution/candidate-plan.json'
    wrapped = read_json(plan_path, evidence)
    need(wrapped['plan_sha256'] == PLAN_SHA == hashlib.sha256(canonical(wrapped['plan'])).hexdigest(), 'source plan differs')
    docs = {name: read_json(RUN / name, evidence) for name in
            ('same-size-native-references.json', 'same-size-candidate-check.json', 'same-size-timed.json', 'resolution-campaign-result.json')}
    ref, candidate, timed = (RUN / name for name in
                            ('same-size-native-references.json', 'same-size-candidate-check.json', 'same-size-timed.json'))
    actual = gate._verify(ROOT, plan_path, ref, evidence[str(ref)]['sha256'], 'timed', candidate, evidence[str(candidate)]['sha256'])
    need(actual == docs['same-size-timed.json'], 'stored timed proof differs from unchanged full reconstruction')
    need(actual['status'] == 'timed_verified' and actual['four_tensor_exact_clips'] == 40 and
         actual['distinct_fixtures'] == 10 and actual['runtime_manifest_sha256'] == MANIFEST_SHA and
         actual['server_identity_sha256'] == IDENTITY_SHA, 'incomplete or different proof')
    campaign = docs['resolution-campaign-result.json']
    need(campaign['passed'] is True and len(campaign['requests']) == len(set(campaign['requests'])) == 87 and
         campaign['timed_receipt'] == str(timed), 'campaign incomplete')
    closeout = read_json(CLOSEOUT / 'summary.json', evidence)
    need(closeout['schema'] == 'ltx.resolution103.completed-qualification.v1' and
         closeout['run'] == str(RUN) and closeout['runtime_manifest_sha256'] == MANIFEST_SHA and
         closeout['fault_latched'] is False and
         (closeout['native_executions'], closeout['candidate_exact_clips'], closeout['timed_exact_clips']) == (20, 10, 40), 'closeout incomplete')
    for path in (ref, candidate, timed, RUN / 'resolution-campaign-result.json', RUN / 'server-identity.json'):
        need(closeout['files'][str(path)]['sha256'] == evidence[str(path)]['sha256'], 'closeout file binding differs')
    fault_free()
    for path, record in evidence.items():
        need(fp(path) == record, 'proof input changed')
    return wrapped['plan'], actual, identity, evidence


def archive(name):
    return ROOT / 'output/validation' / name / 'tensors.safetensors'


def select_pairs(plan, proof):
    rows = [r for r in plan['requests'] if r['phase'] == 'timed']
    need(len(rows) == 44 and [r['name'] for r in rows] == [PREFIX + f'timed-{i:02d}' for i in range(44)], 'timed namespace differs')
    executions = {r['name']: r for r in proof['executions']}
    need(len(executions) == 44, 'execution census differs')
    keepers = {r['expected_emitted_fixture']: r for r in rows[4:14]}
    need(list(keepers) == FIXTURES, 'retained initial fixture order differs')
    result = []
    for offset, row in enumerate(rows[14:]):
        fixture = row['expected_emitted_fixture']
        need(fixture == FIXTURES[offset % 10] and row['timing_scope'] == 'bounded-continuity', 'continuity fixture differs')
        keeper = keepers[fixture]
        a, b = executions[row['name']], executions[keeper['name']]
        need(a['fixture'] == b['fixture'] == fixture and a['tensors'] == b['tensors'] and
             a['parity_status'] == b['parity_status'] == 'four-tensors-exact' and
             a['prompt_id'] != b['prompt_id'], 'execution binding differs')
        candidate, retained = fp(archive(row['name'])), fp(archive(keeper['name']))
        need(all(proof['evidence_sha256'].get(r['path']) == r['sha256'] for r in (candidate, retained)),
             'raw archive differs from reconstructed proof')
        need(candidate['sha256'] == retained['sha256'] and candidate['st_size'] == retained['st_size'], 'whole archive differs; preserve it')
        need((candidate['st_dev'], candidate['st_ino']) != (retained['st_dev'], retained['st_ino']), 'aliased archives')
        result.append({'candidate': candidate, 'retained': retained, 'fixture': fixture,
                       'candidate_execution': a, 'retained_execution': b,
                       'restore': {'destination': candidate['path'], 'source': retained['path'],
                                   'sha256': retained['sha256'], 'bytes': retained['st_size']}})
    return result


def build_plan():
    source, proof, identity, evidence = reconstruct_proof()
    rows = select_pairs(source, proof)
    return {'schema': SCHEMA, 'helper_sha256': fp(Path(__file__).resolve())['sha256'],
            'runtime_manifest_sha256': MANIFEST_SHA, 'source_plan_sha256': PLAN_SHA,
            'identity': identity, 'evidence': evidence, 'retire': rows,
            'reclaim_logical_bytes': sum(r['candidate']['st_size'] for r in rows),
            'reclaim_allocated_bytes': sum(r['candidate']['st_blocks'] * 512 for r in rows),
            'proof_status': 'full unchanged sealed proof verified before retirement; absent paths require restoration before replay'}


def checked_plan(path, digest):
    plan = read_json(path)
    need(fp(path)['sha256'] == digest, 'explicit plan SHA mismatch')
    need(plan['schema'] == SCHEMA and plan['helper_sha256'] == fp(Path(__file__).resolve())['sha256'] and
         plan['runtime_manifest_sha256'] == MANIFEST_SHA and plan['source_plan_sha256'] == PLAN_SHA, 'plan identity differs')
    rows = plan['retire']
    need(len(rows) == 30, 'exactly thirty rows required')
    for i, row in enumerate(rows):
        a, b = row['candidate'], row['retained']
        need(a['path'] == str(archive(PREFIX + f'timed-{i+14:02d}')) and
             b['path'] == str(archive(PREFIX + f'timed-{i%10+4:02d}')) and
             row['fixture'] == FIXTURES[i % 10] and a['st_nlink'] == b['st_nlink'] == 1 and
             a['sha256'] == b['sha256'] and a['st_size'] == b['st_size'] and
             row['restore'] == {'destination': a['path'], 'source': b['path'], 'sha256': b['sha256'], 'bytes': b['st_size']}, 'restore mapping differs')
    return plan


def stopped(identity):
    """No signal/probe: conservative PID absence, pinned identity, recorded single stop."""
    evidence = {}
    need(fp(RUN / 'server-identity.json')['sha256'] == IDENTITY_SHA, 'current server identity differs')
    need(read_json(RUN / 'server-identity.json') == identity, 'recorded server differs')
    pid = identity.get('pid')
    need(type(pid) is int and pid > 1 and str(identity.get('proc_start_ticks', '')).isdigit(), 'invalid process identity')
    need(not Path('/proc', str(pid)).exists(), 'server PID still exists')
    intent = read_json(CLOSEOUT / 'controlled-reload-stop-intent.json', evidence)
    stop = read_json(CLOSEOUT / 'controlled-reload-stopped.json', evidence)
    need(intent['schema'] == 'ltx.controlled-application-reload.v1' and intent['identity'] == identity and
         intent['signal'] == 'SIGINT', 'stop intent identity differs')
    need(stop['schema'] == 'ltx.controlled-application-reload-stopped.v1' and stop['pid'] == pid and
         stop['gone'] is True and stop['hard_kill'] is False and stop['fault_latched'] is False, 'unclean stop')
    fault_free()
    return evidence


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive_json(path, value):
    path = safe(path, False)
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    fsync_dir(path.parent)


def parent_fd(path):
    path = safe(path, False)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def unlink_exact(record):
    path = Path(record['path'])
    need(fp(path) == record, 'candidate changed immediately before unlink')
    fd = parent_fd(path)
    try:
        now = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        need(stat.S_ISREG(now.st_mode) and all(getattr(now, k) == record[k] for k in STAT_KEYS), 'candidate replaced')
        os.unlink(path.name, dir_fd=fd); os.fsync(fd)
    finally:
        os.close(fd)


def restore_one(row):
    src, dst = Path(row['retained']['path']), Path(row['candidate']['path'])
    need(fp(src) == row['retained'], 'retained archive changed')
    directory = parent_fd(dst)
    try:
        fd = os.open(dst.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, 'wb') as out, src.open('rb') as inp:
            for block in iter(lambda: inp.read(1024**2), b''):
                out.write(block)
            out.flush(); os.fsync(out.fileno())
        os.fsync(directory)
    finally:
        os.close(directory)
    restored = fp(dst)
    need(fp(src) == row['retained'] and restored['sha256'] == row['restore']['sha256'] and
         restored['st_size'] == row['restore']['bytes'] and restored['st_nlink'] == 1, 'restored file differs; preserve partial evidence')
    return restored


def storage_admission(rows):
    module = load(REPO / 'scripts/check-storage-headroom.py', 'retirement103_headroom')
    planned = sum((r['candidate']['st_size'] + 4095) // 4096 * 4096 for r in rows) + 16 * 1024**2
    result = module.inspect_destination(ROOT / 'output/validation', FLOOR, planned)
    need(result['admitted'] is True, 'restore storage admission refused')
    return result


def operate(mode, plan_path, digest, receipt):
    need(mode in ('apply', 'restore'), 'unsupported operation')
    plan = checked_plan(plan_path, digest)
    # Reconstruct BEFORE any output/deletion; restore cannot replay absent proof.
    if mode == 'apply':
        need(build_plan() == plan, 'full proof or plan changed')
    stop_evidence = stopped(plan['identity'])
    rows = plan['retire']
    for row in rows:
        need(fp(row['retained']['path']) == row['retained'], 'retained source changed')
        if mode == 'restore':
            need(not safe(row['candidate']['path'], False).exists(), 'restore destination already exists; no overwrite or automatic resume')
    admission = storage_admission(rows) if mode == 'restore' else None
    receipt = safe(receipt, False)
    need(not receipt.is_relative_to(ROOT), 'control receipts must be outside experiment artifacts')
    intent = receipt.with_name(receipt.name + '.intent.json')
    events = receipt.with_name(receipt.name + '.events.jsonl')
    need(not any(p.exists() for p in (receipt, intent, events)), 'existing operation output; no retry')
    exclusive_json(intent, {'schema': SCHEMA, 'mode': mode, 'plan_sha256': digest, 'plan': plan,
                            'stopped_evidence': stop_evidence, 'storage_admission': admission,
                            'status': 'intent-before-any-file-change'})
    with events.open('xb') as stream:
        stream.flush(); os.fsync(stream.fileno())
    fsync_dir(events.parent)
    def event(value):
        with events.open('ab') as stream:
            stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    completed, error = [], None
    try:
        for row in rows:
            need(stopped(plan['identity']) == stop_evidence, 'shutdown evidence changed')
            need(fp(row['retained']['path']) == row['retained'], 'retained archive changed')
            event({'phase': 'file-intent', 'mode': mode, 'restore': row['restore'], 'candidate': row['candidate']})
            actual = restore_one(row) if mode == 'restore' else unlink_exact(row['candidate'])
            completed.append(row['candidate']['path'])
            event({'phase': 'file-completed', 'mode': mode, 'path': completed[-1], 'restored_stat': actual})
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        exclusive_json(receipt, {'schema': SCHEMA, 'mode': mode, 'plan_sha256': digest,
            'status': 'completed' if error is None else 'incomplete-no-automatic-retry',
            'completed': completed, 'error': error, 'intent_sha256': fp(intent)['sha256'],
            'events_sha256': fp(events)['sha256'],
            'proof_status': ('verified before retirement; raw paths absent and restorable' if mode == 'apply'
                             else 'ordinary copies restored; full sealed proof revalidation remains required')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('plan'); p.add_argument('--out', type=Path, required=True)
    for mode in ('apply', 'restore'):
        p = sub.add_parser(mode)
        p.add_argument('--plan', type=Path, required=True); p.add_argument('--sha256', required=True)
        p.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'plan':
        need(not args.out.is_relative_to(ROOT), 'plan must be outside experiment artifacts')
        exclusive_json(args.out, build_plan())
        print(fp(args.out)['sha256'])
    else:
        operate(args.mode, args.plan, args.sha256, args.receipt)


if __name__ == '__main__':
    main()

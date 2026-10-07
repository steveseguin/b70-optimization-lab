#!/usr/bin/env python3
"""Fixed40-file retirement for stopped105; never controls applications."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRIMITIVES = HERE.parent / '20261007-resolution103-retirement/retire103.py'
PRIMITIVES_SHA = '043912bdf375d36f0691cfa3d000a66a48408747d5837871b3d1af8da76150bb'
if PRIMITIVES.is_symlink() or hashlib.sha256(PRIMITIVES.read_bytes()).hexdigest() != PRIMITIVES_SHA:
    raise RuntimeError('Reviewed file-safety primitive source differs')
spec = importlib.util.spec_from_file_location('post105_file_safety', PRIMITIVES)
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
need, fp, read_json, canonical = H.need, H.fp, H.read_json, H.canonical
safe, load, exclusive_json, fsync_dir = H.safe, H.load, H.exclusive_json, H.fsync_dir
unlink_exact, restore_one = H.unlink_exact, H.restore_one
ROOT = H.ROOT
DATA = REPO / 'experiments/ltx25-b70/data/resume-20261007'
SCHEMA = 'ltx.post105.fixed-duplicate-retirement.v1'
FIXTURES = H.FIXTURES
RUNS = {
    '105': {'packet': 'prepared-client-reverse-105',
        'run': 'encoder-server-client-reverse-105-two-way-w2-b1-p1-dxpu2-s640x384',
        'manifest': '1ff7bd5ab281dad1a19f8d01aaf8899505168f0606689ba43ccb23cc05311fad',
        'identity': 'cb4ff31d62bdf6ad094adbec7325fb20e4eb02995f6a36d96dec63a8f5254d58',
        'plan': 'f12dfbfa8be44c9798a1ac9f0dacb1ae7576e3ca30317a5b57de847642faec4f',
        'candidate_gate_sha256': '60d533a2129694af562393e67e08466bcc8ead523f9c7119864300f14b0197b7',
        'final_control_receipt_sha256': 'bd19ab85de3ad5cf4ea7c84202a44356ea9649888f52309e8db2f903ff81c093',
        'pid': 3329528, 'start_ticks': '27505015', 'boot_id': '10192010-9700-4915-ac6c-980d6b74afa0',
        'prefix': 'resolution-client-reverse-20261007-', 'closeout': 'client105-closeout',
        'summary_schema': 'ltx.client105.completed-comparison.v1', 'requests': 71},
}


def archive(name):
    return ROOT / 'output/validation' / name / 'tensors.safetensors'


def protected_anchors():
    names = [f'resolution-full-20261007-timed-{i:02d}' for i in range(4, 14)]
    names += [f'resolution-client-20261007-timed-{i:02d}' for i in range(4, 14)]
    names += [prefix + 'native-p1-' + fixture for prefix in
              ('resolution-ref101c-20261007-', 'resolution-w2-20261007-') for fixture in FIXTURES[:3]]
    return [str(archive(name)) for name in names]


def selection():
    prefix = RUNS['105']['prefix']; result = []
    for phase in ('native-p2', 'candidate-check', 'timed-fast', 'timed'):
        for i, fixture in enumerate(FIXTURES):
            name = prefix + (phase + '-' + fixture if phase == 'native-p2' else f'{phase}-{i+4:02d}')
            result.append(('105', name, prefix + 'native-p1-' + fixture, fixture))
    candidates = {str(archive(r[1])) for r in result}
    need(len(result) == len(candidates) == 40 and
         not candidates.intersection(str(archive(r[2])) for r in result) and
         not candidates.intersection(protected_anchors()), 'fixed selection defect')
    return result


def process_exists(pid):
    # Read-only; a reused PID also conservatively refuses. Tests stub this function.
    return Path('/proc', str(pid)).exists()


def stopped_all(expected=None):
    cfg = RUNS['105']; run = ROOT / cfg['run']; closeout = DATA / cfg['closeout']; evidence = {}
    need(not any(p.exists() for p in (ROOT / 'FAULT.json', run / 'FAULT.json', run / 'resolution-halt.json')), 'fault/halt present')
    identity = read_json(run / 'server-identity.json', evidence)
    need(evidence[str(run / 'server-identity.json')]['sha256'] == cfg['identity'] and
         identity['source_packet_manifest_sha256'] == cfg['manifest'], 'exact server identity differs')
    if expected is not None:
        need(identity == expected['105'], 'plan server identity differs')
    need(type(identity['pid']) is int and identity['pid'] == cfg['pid'] and
         identity.get('proc_start_ticks') == cfg['start_ticks'] and identity.get('boot_id') == cfg['boot_id'],
         'exact105 PID/start/boot differs')
    need(not process_exists(identity['pid']), 'server PID still exists:105')
    intent = read_json(closeout / 'controlled-reload-stop-intent.json', evidence)
    stop = read_json(closeout / 'controlled-reload-stopped.json', evidence)
    need(intent['schema'] == 'ltx.controlled-application-reload.v1' and
         intent['identity'] == identity and intent['signal'] == 'SIGINT', 'stop intent differs')
    need(stop['schema'] == 'ltx.controlled-application-reload-stopped.v1' and stop['pid'] == cfg['pid'] and
         stop['gone'] is True and stop['hard_kill'] is False and stop['fault_latched'] is False, 'unclean controlled stop')
    return {'105': identity}, evidence


def reconstruct_lane(lane):
    """The final105 control verifier recursively verifies the earlier fast block."""
    need(lane == '105', 'unsupported run')
    cfg = RUNS[lane]; packet = ROOT / cfg['packet']; run = ROOT / cfg['run']; evidence = {}
    manifest = read_json(packet / 'manifest.json', evidence)
    need(evidence[str(packet / 'manifest.json')]['sha256'] == cfg['manifest'], 'sealed manifest differs')
    for name in ('reference_gate.py', 'candidate_gate.py'):
        path = packet / 'resolution/components' / name; evidence[str(path)] = fp(path)
        need(evidence[str(path)]['sha256'] == manifest['files']['resolution/components/' + name], 'sealed verifier source differs')
        if name == 'candidate_gate.py':
            need(evidence[str(path)]['sha256'] == cfg['candidate_gate_sha256'], 'exact105 gate source differs')
    gate = load(packet / 'resolution/components/candidate_gate.py', 'post105_sealed_gate')
    plan_path = packet / 'resolution/candidate-plan.json'; source = read_json(plan_path, evidence)
    need(source['plan_sha256'] == cfg['plan'] == hashlib.sha256(canonical(source['plan'])).hexdigest(), 'source plan differs')
    names = ['same-size-native-references.json', 'same-size-candidate-check.json',
             'same-size-timed-fast.json', 'same-size-timed.json']
    docs = {n: read_json(run / n, evidence) for n in names}
    ref, candidate, fast, control = (run / n for n in names)
    need(evidence[str(control)]['sha256'] == cfg['final_control_receipt_sha256'], 'known final control receipt differs')
    actual = gate._verify(ROOT, plan_path, ref, evidence[str(ref)]['sha256'], 'timed',
                          candidate, evidence[str(candidate)]['sha256'], fast, evidence[str(fast)]['sha256'])
    need(actual == docs[names[-1]], 'complete sealed proof reconstruction differs')
    native = docs[names[0]]
    need(native['status'] == 'reference_verified' and len(native['executions']) == 20 and
         native['four_tensor_repeat_pairs_exact'] == 10 and docs[names[1]]['four_tensor_exact_clips'] == 10 and
         docs[names[2]]['status'] == 'timed_fast_verified' and docs[names[2]]['four_tensor_exact_clips'] == 10 and
         actual['status'] == 'timed_verified' and actual['four_tensor_exact_clips'] == 10 and
         actual['runtime_manifest_sha256'] == cfg['manifest'] and actual['server_identity_sha256'] == cfg['identity'],
         'proof counts/identity differ')
    campaign_path = run / 'resolution-campaign-result.json'; campaign = read_json(campaign_path, evidence)
    need(campaign['passed'] is True and len(campaign['requests']) == len(set(campaign['requests'])) == 71 and
         campaign['timed_receipt'] == str(control) and campaign['fast_timed_receipt'] == str(fast), 'campaign incomplete')
    summary = read_json(DATA / cfg['closeout'] / 'summary.json', evidence)
    need(summary['schema'] == cfg['summary_schema'] and summary['fault_latched'] is False and
         summary['native_executions'] == 20 and summary['candidate_exact_clips'] == 10 and
         summary['runtime_manifest_sha256'] == cfg['manifest'] and summary['run'] == str(run) and
         summary['control_exact_clips'] == summary['fast_exact_clips'] == 10, 'closeout differs')
    for path in [*(run / n for n in names), campaign_path]:
        need(summary['files'][str(path)]['sha256'] == evidence[str(path)]['sha256'], 'closeout evidence binding differs')
    executions, raw_hashes = {}, {}
    for doc in docs.values():
        for row in doc['executions']:
            need(row['name'] not in executions, 'duplicate execution name')
            executions[row['name']] = row
        for path, digest in doc['evidence_sha256'].items():
            if path.endswith('/tensors.safetensors'):
                need(path not in raw_hashes or raw_hashes[path] == digest, 'contradictory raw proof hash')
                raw_hashes[path] = digest
    for path, record in evidence.items():
        need(fp(path) == record, 'proof input changed')
    return {'executions': executions, 'raw_hashes': raw_hashes, 'evidence': evidence}


def build_plan():
    identities, stop_evidence = stopped_all()
    proofs = {lane: reconstruct_lane(lane) for lane in RUNS}
    rows = []
    for lane, candidate_name, keeper_name, fixture in selection():
        proof = proofs[lane]; a = proof['executions'][candidate_name]; b = proof['executions'][keeper_name]
        need(a['fixture'] == b['fixture'] == fixture and a['tensors'] == b['tensors'] and
             a['prompt_id'] != b['prompt_id'], 'candidate/keeper execution differs')
        candidate, retained = fp(archive(candidate_name)), fp(archive(keeper_name))
        need(all(proof['raw_hashes'].get(r['path']) == r['sha256'] for r in (candidate, retained)), 'archive differs from full proof')
        need(candidate['sha256'] == retained['sha256'] and candidate['st_size'] == retained['st_size'] and
             (candidate['st_dev'], candidate['st_ino']) != (retained['st_dev'], retained['st_ino']), 'whole archive differs or aliases keeper')
        rows.append({'lane': lane, 'fixture': fixture, 'candidate': candidate, 'retained': retained,
                     'candidate_execution': a, 'retained_execution': b,
                     'restore': {'destination': candidate['path'], 'source': retained['path'],
                                 'sha256': retained['sha256'], 'bytes': retained['st_size']}})
    need(stopped_all(identities) == (identities, stop_evidence), 'stop evidence changed during proof')
    return {'schema': SCHEMA, 'helper_sha256': fp(Path(__file__).resolve())['sha256'], 'primitives_sha256': PRIMITIVES_SHA,
            'run_pins': RUNS, 'protected_previous_anchors': protected_anchors(), 'identities': identities, 'stop_evidence': stop_evidence,
            'proof_evidence': {lane: p['evidence'] for lane, p in proofs.items()}, 'retire': rows,
            'reclaim_logical_bytes': sum(r['candidate']['st_size'] for r in rows),
            'reclaim_allocated_bytes': sum(r['candidate']['st_blocks'] * 512 for r in rows),
            'proof_status': 'complete unchanged sealed105 final-control proof verified before retirement; restore absent paths for replay'}


def checked_plan(path, digest):
    plan = read_json(path)
    need(fp(path)['sha256'] == digest, 'explicit plan SHA mismatch')
    need(plan['schema'] == SCHEMA and plan['helper_sha256'] == fp(Path(__file__).resolve())['sha256'] and
         plan['primitives_sha256'] == PRIMITIVES_SHA and plan['run_pins'] == RUNS and plan['protected_previous_anchors'] == protected_anchors(), 'plan/source identity differs')
    need(len(plan['retire']) == 40, 'exact40 rows required')
    for row, (lane, candidate_name, keeper_name, fixture) in zip(plan['retire'], selection()):
        a, b = row['candidate'], row['retained']
        need(row['lane'] == lane and row['fixture'] == fixture and a['path'] == str(archive(candidate_name)) and
             b['path'] == str(archive(keeper_name)) and a['st_size'] == b['st_size'] and a['sha256'] == b['sha256'] and
             a['st_nlink'] == b['st_nlink'] == 1 and
             row['restore'] == {'destination': a['path'], 'source': b['path'], 'sha256': b['sha256'], 'bytes': b['st_size']},
             'fixed restoration mapping differs')
    return plan


def storage_admission(rows):
    module = load(REPO / 'scripts/check-storage-headroom.py', 'post105_headroom')
    planned = sum((r['candidate']['st_size'] + 4095) // 4096 * 4096 for r in rows) + 16 * 1024**2
    result = module.inspect_destination(ROOT / 'output/validation', 50 * 1024**3, planned)
    need(result['admitted'] is True, 'restore storage admission refused')
    return result


def operate(mode, path, digest, receipt):
    need(mode in ('apply', 'restore'), 'unknown operation')
    plan = checked_plan(path, digest)
    need(stopped_all(plan['identities']) == (plan['identities'], plan['stop_evidence']), 'stop evidence changed')
    if mode == 'apply':
        need(build_plan() == plan, 'full proof or exact plan changed')
    for row in plan['retire']:
        need(fp(row['retained']['path']) == row['retained'], 'retained archive changed')
        if mode == 'restore':
            need(not safe(row['candidate']['path'], False).exists(), 'restore destination exists; no overwrite/resume')
    admission = storage_admission(plan['retire']) if mode == 'restore' else None
    receipt = safe(receipt, False); need(not receipt.is_relative_to(ROOT), 'control output must be outside artifacts')
    intent = receipt.with_name(receipt.name + '.intent.json'); events = receipt.with_name(receipt.name + '.events.jsonl')
    need(not any(p.exists() for p in (receipt, intent, events)), 'operation output exists; no automatic retry')
    exclusive_json(intent, {'schema': SCHEMA, 'mode': mode, 'plan_sha256': digest, 'plan': plan,
                            'storage_admission': admission, 'status': 'intent-before-any-file-change'})
    with events.open('xb') as stream:
        stream.flush(); os.fsync(stream.fileno())
    fsync_dir(events.parent)
    def event(value):
        with events.open('ab') as stream:
            stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    completed, error = [], None
    try:
        for row in plan['retire']:
            need(stopped_all(plan['identities']) == (plan['identities'], plan['stop_evidence']), 'stop evidence changed')
            need(fp(row['retained']['path']) == row['retained'], 'retained source changed before operation')
            event({'phase': 'file-intent', 'mode': mode, 'candidate': row['candidate'], 'restore': row['restore']})
            actual = restore_one(row) if mode == 'restore' else unlink_exact(row['candidate'])
            completed.append(row['candidate']['path'])
            event({'phase': 'file-completed', 'mode': mode, 'path': completed[-1], 'restored_stat': actual})
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        exclusive_json(receipt, {'schema': SCHEMA, 'mode': mode, 'plan_sha256': digest,
            'status': 'completed' if error is None else 'incomplete-no-automatic-retry', 'error': error,
            'completed': completed, 'intent_sha256': fp(intent)['sha256'], 'events_sha256': fp(events)['sha256'],
            'proof_status': ('verified before retirement; selected raw paths absent and restorable' if mode == 'apply'
                             else 'ordinary copies restored; unchanged full proof revalidation still required')})


def main():
    p = argparse.ArgumentParser(description=__doc__); subs = p.add_subparsers(dest='mode', required=True)
    sub = subs.add_parser('plan'); sub.add_argument('--out', type=Path, required=True)
    for mode in ('apply', 'restore'):
        sub = subs.add_parser(mode); sub.add_argument('--plan', type=Path, required=True)
        sub.add_argument('--sha256', required=True); sub.add_argument('--receipt', type=Path, required=True)
    args = p.parse_args()
    if args.mode == 'plan':
        need(not args.out.is_relative_to(ROOT), 'control output must be outside artifacts')
        exclusive_json(args.out, build_plan()); print(fp(args.out)['sha256'])
    else:
        operate(args.mode, args.plan, args.sha256, args.receipt)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Fixed52-file retirement for stopped101c/102/104; never controls applications."""
import argparse
import hashlib
import importlib.util
import math
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
spec = importlib.util.spec_from_file_location('post104_file_safety', PRIMITIVES)
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
need, fp, read_json, canonical = H.need, H.fp, H.read_json, H.canonical
safe, load, exclusive_json, fsync_dir = H.safe, H.load, H.exclusive_json, H.fsync_dir
unlink_exact, restore_one = H.unlink_exact, H.restore_one
ROOT = H.ROOT
DATA = REPO / 'experiments/ltx25-b70/data/resume-20261007'
SCHEMA = 'ltx.post104.fixed-duplicate-retirement.v1'
FIXTURES = H.FIXTURES
RUNS = {
    '101c': {'packet': 'prepared-resolution-reference-101c',
        'run': 'encoder-server-resolution-reference-101c-two-way-w1-b1-p1-dxpu2-s640x384',
        'manifest': '236637003cf90e2146a8e5bd8fef6aca0a280a1d580c192f5666ae2476f0a966',
        'identity': 'b247e96cc485f8abe96928876167c1a92f2a0406be73c635ba68c5052110c703',
        'plan': '3281a1eb45d210ac75f2a07c415cf2f99b2b9308651456587aa483e2596d65e2',
        'prefix': 'resolution-ref101c-20261007-', 'closeout': 'resolution101c-closeout',
        'summary_schema': 'ltx.resolution101c.closeout.v1', 'requests': 32},
    '102': {'packet': 'prepared-resolution-w2-102',
        'run': 'encoder-server-resolution-w2-102-two-way-w2-b1-p1-dxpu2-s640x384',
        'manifest': '25761564f8e6790d25cbc4495662b2be19dfe2001401c5b8966e0a9c09264db4',
        'identity': '9d6948936f87d9b885c3592fa46e92ca2461631198288ee5b5775f54ffcbec5a',
        'plan': '5973dddeed7f1af0324c87aab04ad9b95c0e452181a7c92e81134fcd075479dd',
        'prefix': 'resolution-w2-20261007-', 'closeout': 'resolution102-closeout',
        'summary_schema': 'ltx.resolution102.completed-screen.v1', 'requests': 36},
    '104': {'packet': 'prepared-client-compare-104',
        'run': 'encoder-server-client-compare-104-two-way-w2-b1-p1-dxpu2-s640x384',
        'manifest': '49892a00ece1cf4a7d84ce5d03e6a9c2290ffc3af9b2822ba4866e72cfa2e93a',
        'identity': '658856183a2b854725cd21825ed83d2d0b63007384fa1065ee806330cb96067d',
        'plan': '1fc6e1f2f5874ab88915c93424f333402fa2bae1b73370391105fade270c841c',
        'prefix': 'resolution-client-20261007-', 'closeout': 'client104-closeout',
        'summary_schema': 'ltx.client104.completed-comparison.v1', 'requests': 71},
}


def archive(name):
    return ROOT / 'output/validation' / name / 'tensors.safetensors'


def selection():
    result = []
    for lane in ('101c', '102'):
        prefix = RUNS[lane]['prefix']; offset = 3 if lane == '101c' else 4
        for fixture in FIXTURES[:3]:
            result.append((lane, prefix + 'native-p2-' + fixture, prefix + 'native-p1-' + fixture, fixture))
        for phase, count in (('candidate-check', 3), ('timed', 10)):
            for i in range(count):
                fixture = FIXTURES[i % 3]
                result.append((lane, prefix + f'{phase}-{i+offset:02d}', prefix + 'native-p1-' + fixture, fixture))
    prefix = RUNS['104']['prefix']
    for phase in ('candidate-check', 'timed-fast'):
        for i, fixture in enumerate(FIXTURES):
            result.append(('104', prefix + f'{phase}-{i+4:02d}', prefix + f'timed-{i+4:02d}', fixture))
    need(len(result) == 52 and len({r[1] for r in result}) == 52 and
         not {r[1] for r in result}.intersection(r[2] for r in result), 'fixed selection defect')
    return result


def stopped_all(expected=None):
    identities, evidence = {}, {}
    need(not (ROOT / 'FAULT.json').exists(), 'global fault')
    for lane, cfg in RUNS.items():
        run = ROOT / cfg['run']; closeout = DATA / cfg['closeout']
        need(not any((run / n).exists() for n in ('FAULT.json', 'resolution-halt.json')), 'run fault/halt')
        identity = read_json(run / 'server-identity.json', evidence)
        need(evidence[str(run / 'server-identity.json')]['sha256'] == cfg['identity'] and
             identity['source_packet_manifest_sha256'] == cfg['manifest'], 'exact server identity differs')
        if expected is not None:
            need(identity == expected[lane], 'plan server identity differs')
        pid = identity['pid']
        need(type(pid) is int and pid > 1 and str(identity.get('proc_start_ticks', '')).isdigit(), 'invalid process identity')
        need(not Path('/proc', str(pid)).exists(), 'server PID still exists: ' + lane)
        old = lane == '101c'
        intent_name = 'resolution-stop-intent.json' if old else 'controlled-reload-stop-intent.json'
        stop_name = 'resolution-stopped.json' if old else 'controlled-reload-stopped.json'
        intent = read_json(closeout / intent_name, evidence); stop = read_json(closeout / stop_name, evidence)
        need(intent['schema'] == ('ltx.resolution-graceful-stop.v1' if old else 'ltx.controlled-application-reload.v1') and
             intent['identity'] == identity and intent['signal'] == 'SIGINT', 'stop intent differs')
        need(stop['pid'] == pid and stop['hard_kill'] is False, 'unclean or wrong stop')
        if old:
            times = [intent.get('time_unix'), stop.get('gone_unix')]
            need(all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in times) and times[1] >= times[0], '101c stop timestamps differ')
        else:
            need(stop['schema'] == 'ltx.controlled-application-reload-stopped.v1' and
                 stop['gone'] is True and stop['fault_latched'] is False, 'unclean controlled stop')
        identities[lane] = identity
    return identities, evidence


def reconstruct_lane(lane):
    """Run each actual sealed schema;104 fast verification includes control proof."""
    cfg = RUNS[lane]; packet = ROOT / cfg['packet']; run = ROOT / cfg['run']; evidence = {}
    manifest = read_json(packet / 'manifest.json', evidence)
    need(evidence[str(packet / 'manifest.json')]['sha256'] == cfg['manifest'], 'sealed manifest differs')
    for name in ('reference_gate.py', 'candidate_gate.py'):
        path = packet / 'resolution/components' / name; evidence[str(path)] = fp(path)
        need(evidence[str(path)]['sha256'] == manifest['files']['resolution/components/' + name], 'sealed verifier source differs')
    gate = load(packet / 'resolution/components/candidate_gate.py', 'post104_sealed_' + lane)
    plan_path = packet / 'resolution/candidate-plan.json'; source = read_json(plan_path, evidence)
    need(source['plan_sha256'] == cfg['plan'] == hashlib.sha256(canonical(source['plan'])).hexdigest(), 'source plan differs')
    names = ['same-size-native-references.json', 'same-size-candidate-check.json', 'same-size-timed.json']
    if lane == '104':
        names.append('same-size-timed-fast.json')
    docs = {n: read_json(run / n, evidence) for n in names}
    ref, candidate, timed = (run / n for n in names[:3])
    args = (ROOT, plan_path, ref, evidence[str(ref)]['sha256'], 'timed-fast' if lane == '104' else 'timed',
            candidate, evidence[str(candidate)]['sha256'])
    actual = gate._verify(*args, timed, evidence[str(timed)]['sha256']) if lane == '104' else gate._verify(*args)
    need(actual == docs[names[-1]], 'complete sealed proof reconstruction differs')
    native = docs[names[0]]; fixtures = 10 if lane == '104' else 3
    need(native['status'] == 'reference_verified' and len(native['executions']) == fixtures * 2 and
         native['four_tensor_repeat_pairs_exact'] == fixtures and
         docs[names[1]]['four_tensor_exact_clips'] == fixtures and
         actual['four_tensor_exact_clips'] == 10 and actual['runtime_manifest_sha256'] == cfg['manifest'] and
         actual['server_identity_sha256'] == cfg['identity'], 'proof counts/identity differ')
    campaign_path = run / 'resolution-campaign-result.json'; campaign = read_json(campaign_path, evidence)
    need(campaign['passed'] is True and len(campaign['requests']) == len(set(campaign['requests'])) == cfg['requests'] and
         campaign['timed_receipt'] == str(timed), 'campaign incomplete')
    if lane == '104':
        need(campaign['fast_timed_receipt'] == str(run / names[-1]), 'fast proof binding differs')
    summary = read_json(DATA / cfg['closeout'] / 'summary.json', evidence)
    need(summary['schema'] == cfg['summary_schema'] and summary['fault_latched'] is False and
         summary['native_executions'] == 2 * fixtures and summary['candidate_exact_clips'] == fixtures and
         summary['packet_manifest_sha256' if lane == '101c' else 'runtime_manifest_sha256'] == cfg['manifest'], 'closeout differs')
    if lane == '104':
        need(summary['run'] == str(run) and summary['control_exact_clips'] == summary['fast_exact_clips'] == 10, '104 closeout counts differ')
    else:
        need(summary['timed_exact_clips'] == 10, 'historical closeout counts differ')
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
            'run_pins': RUNS, 'identities': identities, 'stop_evidence': stop_evidence,
            'proof_evidence': {lane: p['evidence'] for lane, p in proofs.items()}, 'retire': rows,
            'reclaim_logical_bytes': sum(r['candidate']['st_size'] for r in rows),
            'reclaim_allocated_bytes': sum(r['candidate']['st_blocks'] * 512 for r in rows),
            'proof_status': 'three complete unchanged sealed proofs verified before retirement; restore absent paths for replay'}


def checked_plan(path, digest):
    plan = read_json(path)
    need(fp(path)['sha256'] == digest, 'explicit plan SHA mismatch')
    need(plan['schema'] == SCHEMA and plan['helper_sha256'] == fp(Path(__file__).resolve())['sha256'] and
         plan['primitives_sha256'] == PRIMITIVES_SHA and plan['run_pins'] == RUNS, 'plan/source identity differs')
    need(len(plan['retire']) == 52, 'exact52 rows required')
    for row, (lane, candidate_name, keeper_name, fixture) in zip(plan['retire'], selection()):
        a, b = row['candidate'], row['retained']
        need(row['lane'] == lane and row['fixture'] == fixture and a['path'] == str(archive(candidate_name)) and
             b['path'] == str(archive(keeper_name)) and a['st_size'] == b['st_size'] and a['sha256'] == b['sha256'] and
             a['st_nlink'] == b['st_nlink'] == 1 and
             row['restore'] == {'destination': a['path'], 'source': b['path'], 'sha256': b['sha256'], 'bytes': b['st_size']},
             'fixed restoration mapping differs')
    return plan


def storage_admission(rows):
    module = load(REPO / 'scripts/check-storage-headroom.py', 'post104_headroom')
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

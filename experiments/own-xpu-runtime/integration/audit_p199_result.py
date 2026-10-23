#!/usr/bin/env python3
"""Read-only audit of a completed p199 pilot; --write saves one new receipt.

No worker imports, native execution, service queries, HTTP calls or deletion.
Run with the pinned vllm-xpu Python on nice19/helper cores. The codec reads only
its pinned GGUF header. Missing/deferred result evidence is a refusal, not PASS.
"""
from __future__ import annotations
import argparse
import ast
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P = HERE.parent / 'stage2/packet199-chat-parking'
OUT = P / 'evidence/device-p199-chat-A-a'
STATE = P / 'evidence/runcheckpoints'
READY_SHA = '096e731f91f9831e88db693011d49c1d9d64b717e849c2f6a483bd53040b261b'
IDS = ['a-park', 'b-park', 'a-chat-append', 'a-chat-fresh', 'a-edited', 'final-b-no-park']
CORRECTNESS = ['A_parent_exact', 'B_parent_exact', 'append_restore_selected',
    'append_fresh_tokens_exact', 'append_fresh_state_exact', 'edited_prefill', 'final_B_repeat',
    'postreply_controls_exact', 'final_release_before_stopped', 'http_usage_exact', 'parking_budget_respected']
STOP_IDS = {248044, 248046}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Evidence:
    def __init__(self):
        self.files = {}

    def bytes(self, path, limit=16 * 1024**2):
        path = Path(path)
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'bounded regular evidence required: ' + str(path))
        raw = path.read_bytes()
        after = path.lstat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'evidence changed')
        self.files[str(path.relative_to(ROOT))] = dict(bytes=len(raw), sha256=digest(raw))
        return raw

    def json(self, path):
        return json.loads(self.bytes(path))


def check_terminal(worker):
    expected = dict(passed=True, device_executed=True, native_process_count=1, model_loads=1,
                    child_still_running=False, safe_to_exit=True, devices_drained=True,
                    submission_eligible=False, save_count=5, release_count=1)
    require(all(type(worker.get(k)) is type(v) and worker[k] == v for k, v in expected.items()), 'worker incomplete or failed')
    require(worker.get('stop_reasons') == [] and worker.get('incident_sigterm_count', 0) == 0, 'worker incident recorded')
    require(worker['completed_requests'] == IDS and all(worker['correctness'].get(k) is True for k in CORRECTNESS),
            'worker request/correctness proof missing')
    stopped = dict(event='stopped', reason='request-limit', safe_to_exit=True, completed_requests=6,
                   completed_controls=6, discarded_pending=False, pending_request_id='')
    require(all(type(worker['stopped'].get(k)) is type(v) and worker['stopped'][k] == v for k, v in stopped.items()),
            'final disposition/stopped disagreement')


def check_http(response, native_id, prompt, generated, maximum, codec, model):
    require(type(generated) is list and 0 < len(generated) <= maximum and
            all(type(t) is int and 0 <= t < codec.vocab for t in generated), 'invalid generated tokens')
    terminal = generated[-1] in STOP_IDS
    require(not any(t in STOP_IDS for t in generated[:-1]) and (terminal or len(generated) == maximum),
            'generation does not match native stop rule')
    require(response['id'] == 'chatcmpl-' + native_id and response['object'] == 'chat.completion' and
            response['model'] == model and type(response['created']) is int, 'HTTP identity mismatch')
    require(response['choices'] == [dict(index=0, message=dict(role='assistant', content=codec.decode(
                generated[:-1] if terminal else generated)), finish_reason='stop' if terminal else 'length')],
            'HTTP text/finish-reason mismatch')
    require(response['usage'] == dict(prompt_tokens=len(prompt), completion_tokens=len(generated),
            total_tokens=len(prompt) + len(generated)), 'HTTP usage mismatch')


def check_control(control, index, native_id):
    require(control['operation_id'] == 'parking-' + str(index + 1) and control['request_id'] == native_id,
            'control/request identity mismatch')
    require(control['event'] == ('request-released' if index == 5 else 'checkpoint-saved') and
            control['request_disposed'] is True and control['request_quiesced'] is True and
            control['final_request'] is (index == 5), 'control disposition mismatch')


def manifest_map(manifest):
    result = {'tokens.bin': manifest['token_state']['tokens_sha256']}
    sizes = {'tokens.bin': manifest['token_state']['length'] * 4}
    for blob in manifest['blobs']:
        name = blob['name'] + '.bin'
        require(Path(name).name == name and name not in result, 'invalid/duplicate blob name')
        result[name], sizes[name] = blob['sha256'], blob['bytes']
    return result, sizes


def hash_remaining(folder, manifest, expected):
    hashes, sizes = manifest_map(manifest)
    require(hashes == expected, 'captured blob map differs from manifest')
    require({f.name for f in folder.iterdir()} == set(hashes) | {'manifest.json', 'fields.tsv'}, 'remaining state file set differs')
    total = 0
    for name, wanted in hashes.items():
        path = folder / name
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_size == sizes[name], 'remaining blob extent/type mismatch')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = path.lstat()
        require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'remaining blob changed')
        require(actual == wanted, 'remaining raw blob hash mismatch: ' + name)
        total += before.st_size
    return dict(files=len(hashes), bytes=total)


def fault_patterns(path):
    patterns = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                    patterns[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
    require(set(patterns) == {'FAULT', 'DELETED'}, 'sealed fault rules unavailable')
    return patterns


def audit():
    e = Evidence()
    ready_raw = e.bytes(P / 'READY-FOR-DEVICE.json')
    require(digest(ready_raw) == READY_SHA, 'pilot readiness differs from reviewed seal')
    ready = json.loads(ready_raw)
    require(ready['passed'] is True and digest(e.bytes(P / 'evidence/device-cpu-gates.json')) == ready['gates_sha256'],
            'CPU gate binding mismatch')
    for path in [P / name for name in ('device_worker.py', 'plan.json', 'vectors.json')] + [
            HERE / name for name in ('chat_codec.py', 'checkpoint_bridge.py')]:
        require(digest(e.bytes(path)) == ready['files_sha256'][str(path.relative_to(ROOT))], 'audited source changed')
    plan, vectors = e.json(P / 'plan.json'), e.json(P / 'vectors.json')
    require(digest(e.bytes(P / 'vectors.json')) == plan['vector_sha256'], 'vector seal mismatch')
    for path, wanted in vectors['source_files_sha256'].items():
        require(digest(e.bytes(ROOT / path)) == wanted, 'retained parent fixture drift')
    worker = e.json(OUT / 'worker.json')
    check_terminal(worker)
    require(worker['plan']['ready_sha256'] == READY_SHA and worker['plan']['native_argv'] == ready['native_argv'], 'worker launch identity mismatch')
    require(worker['plan']['max_requests'] == 6 and worker['plan']['max_native_processes'] == 1, 'owner budget mismatch')
    require(worker['environment']['FilterBdfPath'] == '0000:23:00.0' and worker['environment']['OMP_NUM_THREADS'] == '2',
            'runtime placement mismatch')
    isolation = worker['isolation']
    require(set(isolation) == {str(worker['pid'])}, 'unexpected monitored model-owner PID')
    owner = isolation[str(worker['pid'])]
    require(owner['seen'] is True and owner['exited'] is True and owner['fds'] and
            all(fd['pci'] == '0000:23:00.0' and fd['driver'] == 'xe' for fd in owner['fds']), 'owner/card0 isolation proof missing')
    native = e.json(OUT / 'owner/receipt.json')
    require(native['passed'] is True and native['safe_to_exit'] is True and native['device_executed'] is True and not native['error'],
            'native terminal receipt failed')
    require(native['teardown'] and all(t['status'] == 'complete' and t['exit_code'] == 0 and t['safe_to_exit'] is True
            and t['in_flight'] == 0 and t['live_bytes'] == 0 and not t['error'] for t in native['teardown']), 'native teardown incomplete')
    from chat_codec import PinnedChatCodec
    from checkpoint_bridge import validate_snapshot
    codec = PinnedChatCodec()
    require(dict(codec.tokenizer_identity) == plan['identity']['tokenizer_identity'], 'codec/native identity mismatch')
    rows = e.json(OUT / 'http-requests.json')
    require(rows == worker['requests'] and [r['name'] for r in rows] == IDS, 'HTTP row inventory mismatch')
    operations = [json.loads(line) for line in e.bytes(OUT / 'guard-operations.jsonl').splitlines() if line.strip()]
    require(len(operations) % 2 == 0, 'unfinished guarded operation')
    completed = collections.Counter()
    deletes = set()
    for before, after in zip(operations[::2], operations[1::2]):
        require(before['phase'] == 'before' and after['phase'] == 'after' and before['operation'] == after['operation']
                and before.get('id') == after.get('id'), 'guard operation pairing differs')
        completed[before['operation']] += 1
        if before['operation'] == 'store.delete':
            deletes.add(before['id'])
    require(all(completed[k] == n for k, n in {'front.request':6, 'front.save':5, 'front.release':1, 'front.close':1}.items()),
            'guarded native operation count mismatch')
    captures, results, surviving, deleted = {}, [], {}, []
    for index, (row, vector) in enumerate(zip(rows, vectors['rows'])):
        rid = row['native_request_id']
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', rid) is not None, 'unsafe recorded native ID')
        prompt, generated = vector['prompt_tokens'], row['tokens']
        require(codec.encode(codec.render(vector['http']['body']['messages'])) == prompt, 'real-message token identity mismatch')
        folder = OUT / 'owner/requests' / rid
        result_raw = e.bytes(folder / 'result.json'); result = json.loads(result_raw)
        require(digest(result_raw) == row['native_result_sha256'] and result['passed'] is True and result['tokens'] == generated,
                'raw native tokens/receipt disagree')
        require(result['request_front_scope'] == 'experimental-postreply-owner-v2' and result['context'] == 4096,
                'native request identity differs')
        require([int(x) for x in e.bytes(folder / 'input.tokens').split()] == prompt, 'native input differs from HTTP vector')
        require(e.json(folder / 'reset.json')['cached_tokens'] == 0 and e.json(folder / 'lookup-request-complete.json')['passed'] is True,
                'native reset/quiescence proof missing')
        require(e.json(folder / 'receipt.json')['passed'] is True, 'native per-request receipt failed')
        response_raw = e.bytes(OUT / (row['name'] + '.http.json'))
        response = json.loads(response_raw)
        require(response == row['response'] and digest(response_raw) == row['http_response_sha256'], 'HTTP bytes/record differ')
        check_http(response, rid, prompt, generated, vector['http']['body']['max_tokens'], codec, vectors['model'])
        if vector['expected_output']['kind'] == 'exact-recorded-p198':
            reference = P.parent / 'packet198-postreply-checkpoint/evidence/device-p198-lifecycle-A-a/owner/requests'
            reference = e.json(reference / vector['expected_output']['source_request'] / 'result.json')
            require(generated == vector['expected_output']['tokens'] == reference['tokens'], 'A/B parent output mismatch')
        restored = vector['expected_policy_action'] == 'restore'
        require(row['decision']['action'] == vector['expected_policy_action'] and result['session_reuse'] is restored,
                'policy/native restore mismatch')
        cached = 342 if restored else 0
        require(row['cached_tokens'] == result['cached_tokens'] == cached and result['prompt_tokens'] == len(prompt), 'cached/input count mismatch')
        if restored:
            restore = result['checkpoint']['restore']
            require(restore['operation'] == 'append' and restore['saved_prefix_length'] == 342 and
                    restore['saved_history_length'] == 343 and restore['input_length'] == 370 and
                    restore['appended_length'] == 27 and restore['append_prefill_tokens'] == 28,
                    'native pending-token plus chat-delta accounting differs')
        check_control(row['control'], index, rid)
        require([v['session'] for v in row['policy_events'] if v['event'] == 'checkpoint evicted'] == vector['expected_evictions'],
                'eviction ordering mismatch')
        budget = row['parking']
        require(budget['budget'] == 512*1024**2 and budget['bytes'] == sum(v['bytes'] for v in budget['sessions'].values())
                + sum(budget['retained_bytes'].values()) and 0 <= budget['bytes'] <= budget['budget'], 'policy accounting mismatch')
        require(not budget['pending_delete'] and not budget['retained_bytes'] and row['no_parking']['bytes'] == 0,
                'unresolved deletion/accounting or no-parking residue')
        require(budget['bytes'] == [1,2,1,2,2,2][index] * 256*1024**2 and
                all(s['bytes'] == 256*1024**2 for s in budget['sessions'].values()) and
                row['no_parking']['budget'] == 0 and not row['no_parking']['sessions'], 'fixed reservation accounting differs')
        if index < 5:
            capture = OUT / 'checkpoint-captures' / row['name']
            proof = e.json(capture / 'state-proof.json'); manifest_raw = e.bytes(capture / 'manifest.json')
            manifest = json.loads(manifest_raw)
            require(proof == worker['checkpoint_captures'][row['name']], 'capture/worker proof differs')
            control = e.json(OUT / 'owner/operations' / ('parking-' + str(index+1)) / 'save.json')
            require(control == row['control'] and control['manifest_sha256'] == proof['manifest_sha256'] == digest(manifest_raw),
                    'SAVE event/manifest/capture mismatch')
            cid = control['checkpoint_id']
            view = validate_snapshot(e.bytes(capture / 'inspect.json'), inspect_returncode=0, manifest_bytes=manifest_raw,
                tokens_bytes=e.bytes(capture / 'tokens.bin'), next_token_bytes=e.bytes(capture / 'next_token.bin'),
                checkpoint_id=cid, expected_identity=plan['identity'], admitted_contract='v1.2+p198')
            require(list(view.saved_history) == prompt + generated, 'saved complete visible token history mismatch')
            hashes, sizes = manifest_map(manifest)
            require(hashes == proof['state_sha256'] and len(hashes) == 129 and
                    proof['storage_bytes'] <= 256*1024**2, 'captured full-state inventory/bound mismatch')
            captures[row['name']] = proof
            if (STATE / cid).exists():
                require(e.bytes(STATE / cid / 'manifest.json') == manifest_raw, 'surviving metadata changed')
                surviving[cid] = hash_remaining(STATE / cid, manifest, hashes)
            else:
                require(cid in deletes, 'checkpoint absent without recorded guarded policy deletion')
                deleted.append(cid)
        results.append(dict(name=row['name'], request_id=rid, prompt_tokens=len(prompt), output_tokens=len(generated),
                            finish_reason=response['choices'][0]['finish_reason'], cached_tokens=cached))
    require(rows[2]['tokens'] == rows[3]['tokens'] and captures['a-chat-append']['state_sha256'] ==
            captures['a-chat-fresh']['state_sha256'], 'append/fresh output or state mismatch')
    require(set(d.name for d in STATE.iterdir() if d.is_dir()) == set(surviving), 'unexpected surviving checkpoint directory')
    require(worker['controls'] == [r['control'] for r in rows] and worker['completed_controls'] ==
            ['parking-' + str(i) for i in range(1,7)], 'worker control summary differs')
    require(worker['total_output_tokens'] == sum(len(r['tokens']) for r in rows) <= 896, 'total output mismatch')
    driver = P.parent / 'packet181-session-swap-v3/one-card/lineage/window_driver.py'
    require(digest(e.bytes(driver)) == ready['files_sha256'][str(driver.relative_to(ROOT))], 'fault-rule source changed')
    patterns = fault_patterns(driver)
    kernel = e.bytes(OUT / 'kernel-window.jsonl').decode()
    require(not any(patterns['FAULT'].search(line) and not patterns['DELETED'].search(line) for line in kernel.splitlines()),
            'kernel window contains a new fault')
    require(not any(path.exists() for path in (OUT / 'STOP', OUT / 'http-incident.json')), 'incident marker present')
    return dict(schema='packet199.independent-device-result.v1', passed=True,
        audited_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), ready_sha256=READY_SHA,
        source_sha256={str(Path(__file__).relative_to(ROOT)): digest(Path(__file__).read_bytes())},
        artifact_sha256=e.files, model_owner_pid=worker['pid'], model_loads=1, card='0000:23:00.0',
        requests=results, generated_tokens=worker['total_output_tokens'], saves=5, releases=1,
        guarded_operations=dict(completed), captured_blob_maps=5, blobs_per_capture=129,
        surviving_raw_states_rehashed=surviving, policy_deleted_state_ids=deleted,
        append_fresh_tokens_exact=True, append_fresh_captured_state_digests_exact=True,
        stopped=worker['stopped'], worker_drain_passed=True,
        legacy_real_model_qualified=native.get('real_model_qualified'),
        limitations=['Deleted checkpoint tensors cannot be independently rehashed; their complete digest maps were captured by the sealed worker before policy deletion and checked against native manifest declarations.',
            'Remaining checkpoint tensors are independently rehashed; captured small token/manifest/inspect bytes are independently validated for all five saves.',
            'Protocol frames are retained as parsed worker fields and native SAVE operation receipts; no independent raw stdout transcript is claimed.',
            'Worker/native drain is audited here. Privileged controller postflight and endpoint restoration are separate receipts and are not asserted by this auditor.',
            'Edited prompt has no prerecorded output oracle; only its prefill selection, native consistency and HTTP mapping are checked.',
            'Functional six-request pilot only. No cold benchmark, throughput gain, general serving or changed native checkpoint qualification claim.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS,0) == 19 and
            set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'nice19/helper cores required')
    result = audit()
    if args.write:
        output = P / 'evidence/independent-device-result.json'
        with output.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
        print(json.dumps(dict(passed=True, receipt=str(output), generated_tokens=result['generated_tokens'])))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

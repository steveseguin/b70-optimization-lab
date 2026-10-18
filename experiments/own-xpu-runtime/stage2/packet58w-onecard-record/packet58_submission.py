#!/usr/bin/env python3
"""Offline packet58w evidence replay and one-card payload preparation.

Adapted from packet91's packet56_submission.py and packet58w's CPU validators.
No runtime imports, subprocesses, network, keys, or device access. Binary fixtures
are hashed incrementally; small original receipts are retained in a portable bundle.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

import suite_metrics as M

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STAGE = Path('experiments/own-xpu-runtime/stage2')
PACKET = STAGE / 'packet58w-onecard-record'
OUTPUT = STAGE / 'packet58w-onecard-record/submission'
CHAIN = PACKET / 'evidence/card0-58w-a'
AUTHORITY = STAGE / 'packet49-integrate/oracle'
ORACLE = Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results')
FROZEN = STAGE / 'suite-inputs-20261012-cap128/suite-manifest.json'
THRESHOLD = PACKET / 'record-threshold.json'
LIVE_THRESHOLD = Path('scripts/packet58_onecard_record_threshold.json')
POLICY = json.loads((HERE/'submission-policy.json').read_text())
ARITHMETIC = 'iq3-p49-split32-v1'
MODEL = 'Qwen3.8 Flash-Next 125B-A6B Unsloth UD-IQ3_XXS (GGUF)'
MODEL_REVISION = '766911a6b7369840a91dbcd95f9f997acaab6cd6'
SUITE_SHA = '0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812'
# Exact running 58g seal. No automatic reseal or wildcard lineage admission.
SEAL_SHA = json.loads((HERE/'submission-pins.json').read_text())['build_receipt_sha256'] if (HERE/'submission-pins.json').exists() else None
ORDER = ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128')
GATES = ('varied_task_quality_passed', 'exact_or_target_oracle_passed',
         'deterministic_repeats_passed', 'fresh_server_repeat_passed',
         'target_model_unchanged', 'no_quality_loss')
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)|job.*timed.out', re.I)
SCOPE = POLICY['scope']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inside(root, relative):
    relative = Path(relative)
    path = (root / relative).resolve()
    require(not relative.is_absolute() and '..' not in relative.parts
            and path.is_relative_to(root.resolve()), 'unsafe evidence path: ' + str(relative))
    return path


class Evidence:
    def __init__(self, members=None):
        self.members = {} if members is None else members

    def add(self, key, path, *, digest_only=False):
        if digest_only:
            member = dict(sha256=file_hash(path), bytes=path.stat().st_size, retention='sha256-only')
        else:
            raw = path.read_bytes()
            member = dict(sha256=sha(raw), raw_base64=base64.b64encode(raw).decode())
        member['source_path'] = str(path)
        require(key not in self.members or self.members[key] == member, 'evidence changed: ' + key)
        self.members[key] = member

    def verify(self, key, digest):
        member = self.members[key]
        require(member['sha256'] == digest, 'bound hash mismatch: ' + key)
        if member.get('retention') == 'sha256-only':
            require(type(member['bytes']) is int and member['bytes'] >= 0, 'invalid retained size')
        else:
            self.raw(key)

    def raw(self, key, digest=None):
        member = self.members[key]
        raw = base64.b64decode(member['raw_base64'], validate=True)
        require(sha(raw) == member['sha256'], 'member hash mismatch: ' + key)
        require(digest is None or sha(raw) == digest, 'bound hash mismatch: ' + key)
        return raw

    def read(self, key, digest=None):
        return json.loads(self.raw(key, digest))


def validate_threshold(row):
    require(row.get('schema') == 'lab.packet58.onecard-record-threshold.v1'
            and row.get('gpu_count') == 1 and row.get('model_revision') == MODEL_REVISION
            and row.get('quantization') == 'UD-IQ3_XXS (GGUF)', 'one-card threshold identity')
    records = row.get('records')
    require(isinstance(records, list), 'threshold history missing')
    previous, ids = 0., set()
    for record in records:
        value, sid = record.get('threshold_tok_s'), record.get('reference_submission')
        require(type(value) in (int, float) and math.isfinite(value) and value > previous,
                'threshold must increase; lowering refused')
        require(isinstance(sid, str) and re.fullmatch(r'[A-Za-z0-9_-]+', sid)
                and sid not in ids, 'invalid/duplicate submission ID')
        ref = record.get('result', {})
        require(isinstance(ref.get('path'), str) and not Path(ref['path']).is_absolute()
                and '..' not in Path(ref['path']).parts
                and re.fullmatch(r'[0-9a-f]{64}', str(ref.get('sha256'))), 'missing result pin')
        previous = value
        ids.add(sid)
    return records[-1] if records else dict(reference_submission=None, threshold_tok_s=None)


def collect(chain=ROOT / CHAIN, oracle=ORACLE, repo=ROOT):
    chain = Path(chain).resolve()
    require(chain == (repo / CHAIN).resolve(), 'only the registered card0-58w-a queue is admitted')
    e = Evidence()
    e.add('queue.json', chain / 'queue.json')
    queue = e.read('queue.json')
    require(queue.get('passed') is True and queue.get('completed') == list(ORDER)
            and queue.get('running') is None, 'queue incomplete; wait for finished WS128')
    e.add('record-threshold.json', repo / THRESHOLD)
    e.add('submission-policy.json', repo / PACKET / 'submission-policy.json')
    e.add('seal.json', repo / PACKET / 'build-receipt.json')
    seal = e.read('seal.json', SEAL_SHA)
    # Verify every sealed source, build gate and binary without importing runtime code.
    for group, root in (('sources', repo), ('artifacts', repo / PACKET), ('gates', repo / PACKET)):
        for leaf, digest in seal[group].items():
            key = group + '/' + leaf
            e.add(key, inside(root, leaf), digest_only=group == 'artifacts')
            e.verify(key, digest)
    e.add('oracle-binding.json', repo / PACKET / 'oracle-binding.json')
    for leaf, digest in e.read('oracle-binding.json')['files_sha256'].items():
        e.add('binding/' + leaf, inside(repo, leaf))
        e.verify('binding/' + leaf, digest)
    for leaf in ('build-receipt.json', 'arithmetic.json', 'suite_check.py'):
        e.add('oracle-source/' + leaf, repo / AUTHORITY / leaf)
    e.add('frozen-manifest.json', repo / FROZEN)
    # The in-repo oracle path is a symlink to exactly the requested external authority.
    # A different location is refused, not treated as an equivalent oracle by assertion.
    require(Path(oracle).resolve() == ORACLE.resolve()
            and (repo / AUTHORITY / 'results').resolve() == Path(oracle).resolve(),
            'oracle authority differs from registered packet49 results')
    for leaf in ('completion.json', 'suite-manifest.json', 'determinism.json', 'kd-capture.json', 'old-v-new.json'):
        e.add('oracle/' + leaf, Path(oracle) / leaf)
    for pid in (*M.PROMPT_CLASSES, 'incident-retrospective-repeat'):
        for leaf in ('receipt.json', 'result.json', 'validation.json', 'input.json'):
            e.add(f'oracle/{pid}/{leaf}', Path(oracle) / pid / leaf)
    for name in ORDER:
        directory = chain / name
        e.add(name + '/window.json', directory / 'window.json')
        w = e.read(name + '/window.json')
        require(w.get('passed') is True, 'failed window: ' + name)
        files = dict(w['native_files'])
        if name not in ('K1a', 'K1b'):
            files.update(w['postload_memory']['sources'])
            files['host-memory.jsonl'] = w['memory_samples_sha256']
        for leaf, digest in files.items():
            # Keep request/reset/layer records and journals. Large fixture bytes and
            # verbose native logs retain their on-disk SHA-256 and byte count.
            digest_only = leaf.endswith(('.bf16', '.bin', '.log'))
            e.add(name + '/' + leaf, inside(directory, leaf), digest_only=digest_only)
            e.verify(name + '/' + leaf, digest)
        if name not in ('K1a', 'K1b'):
            actual = {str(p.relative_to(directory)) for p in (directory / 'run').rglob('*') if p.is_file()}
            require(set(w['native_files']) == actual | {'summary.json', 'kernel-before.jsonl', 'kernel-window.jsonl'},
                    'native receipt closure incomplete: ' + name)
    # Detect mutations of finished queue/windows during collection.
    require(file_hash(chain / 'queue.json') == sha(e.raw('queue.json')), 'queue changed during collection')
    for name in ORDER:
        require(file_hash(chain / name / 'window.json') == sha(e.raw(name + '/window.json')), 'window changed during collection')
    return e


def oracle_check(e):
    completion = e.read('oracle/completion.json')
    require(completion['passed'] is True and completion['device_executed'] is False
            and completion['arithmetic'] == ARITHMETIC and completion['prompts'] == 12
            and completion['token_cap'] == 128, 'incomplete CPU oracle')
    for key, leaf in (('manifest_sha256', 'suite-manifest.json'), ('determinism_sha256', 'determinism.json'),
                      ('kd_capture_sha256', 'kd-capture.json'), ('old_v_new_sha256', 'old-v-new.json')):
        e.raw('oracle/' + leaf, completion[key])
    build = e.read('oracle-source/build-receipt.json', completion['build_receipt_sha256'])
    e.raw('oracle-source/arithmetic.json', completion['arithmetic_sha256'])
    frozen = e.read('frozen-manifest.json', completion['old_manifest_sha256'])
    require(build['passed'] is True and build['frozen_sources'][str(FROZEN)] == sha(e.raw('frozen-manifest.json')),
            'oracle frozen suite binding')
    binding = e.read('oracle-binding.json')
    require(binding['arithmetic'] == ARITHMETIC and binding['binary_sha256'] == build['binary_sha256'], 'oracle identity differs')
    for leaf, digest in binding['files_sha256'].items():
        e.raw('binding/' + leaf, digest)
    for leaf in ('build-receipt.json', 'arithmetic.json', 'suite_check.py'):
        e.raw('oracle-source/' + leaf, binding['files_sha256'][str(AUTHORITY / leaf)])
    manifest = e.read('oracle/suite-manifest.json')
    require(manifest['complete'] is True and manifest['arithmetic'] == ARITHMETIC
            and manifest['context'] == 4096 and manifest['token_cap'] == 128
            and manifest['suite_sha256'] == SUITE_SHA, 'oracle suite identity')
    require([r['prompt_id'] for r in manifest['prompts']] == list(M.PROMPT_CLASSES), 'partial/reordered oracle suite')
    expected, prompts, fixtures = {}, {}, {}
    for entry, original in zip(manifest['prompts'], frozen['prompts'], strict=True):
        pid = entry['prompt_id']
        require(all(entry[k] == original[k] for k in ('prompt_id', 'input_bundle', 'input_bundle_hashes', 'prompt_tokens')),
                'prompt differs from frozen suite')
        r = e.read(f'oracle/{pid}/receipt.json', entry['oracle_receipt_sha256'])
        require(r['verified'] is True and r['device_executed'] is False and r['arithmetic'] == ARITHMETIC
                and r['binary_sha256'] == build['binary_sha256'], 'oracle prompt unverified')
        result = e.read(f'oracle/{pid}/result.json', r['result_sha256'])
        validation = e.read(f'oracle/{pid}/validation.json', r['validation_sha256'])
        inp = e.read(f'oracle/{pid}/input.json', r['input_sha256'])
        e.raw(f'oracle/{pid}/input.json', entry['input_bundle_hashes']['input.json'])
        tokens = result['tokens']
        require(result['arithmetic'] == ARITHMETIC and result['device_executed'] is False
                and result['status'] in ('token-cap', 'eos') and not result.get('error')
                and len(tokens) == entry['generated_tokens'] == 128 and all(type(t) is int for t in tokens)
                and not any(t in M.EOS for t in tokens[:-1]) and validation['passed'] is True,
                'incomplete oracle output')
        require(len(inp['tokens']) == entry['prompt_tokens'] and inp['tokens'], 'oracle prompt length')
        expected[pid], prompts[pid], fixtures[pid] = tokens, inp['tokens'], validation['fixture_hashes']
    repeat = e.read('oracle/determinism.json')
    require(repeat['passed'] is True, 'CPU repeat failed')
    e.raw('oracle/incident-retrospective/receipt.json', repeat['first_receipt_sha256'])
    prefix = 'oracle/incident-retrospective-repeat/'
    rr = e.read(prefix + 'receipt.json', repeat['repeat_receipt_sha256'])
    rv = e.read(prefix + 'validation.json', rr['validation_sha256'])
    repeated = e.read(prefix + 'result.json', rr['result_sha256'])
    require(rr['verified'] is True and rr['binary_sha256'] == build['binary_sha256']
            and rr['arithmetic'] == repeated['arithmetic'] == ARITHMETIC
            and rr['device_executed'] is repeated['device_executed'] is False
            and rv['passed'] is True and repeated['tokens'] == expected['incident-retrospective']
            and rv['fixture_hashes'] == fixtures['incident-retrospective']
            and e.read(prefix + 'input.json', rr['input_sha256'])['tokens'] == prompts['incident-retrospective'],
            'CPU repeat differs')
    return manifest, expected, prompts, fixtures


def token_hash(tokens):
    return sha(json.dumps(tokens, separators=(',', ':')).encode())


def check_requests(e, name, manifest, expected, prompts, fixtures):
    cap = 8 if name in ('KD', 'W2m') else 128
    retain = '1-8' if name in ('KD', 'W2m', 'WS') else 'none'
    entries = manifest['prompts'][:1] if cap == 8 else manifest['prompts']
    native = e.read(name + '/run/run/receipt.json')
    require(native['passed'] is True and native['safe_to_exit'] is True and native['device_executed'] is True
            and native['owner_cards'] == 1 and native['arithmetic'] == ARITHMETIC
            and native.get('profiling') is False, 'native owner identity/teardown')
    seal = e.read('seal.json')
    require(native['selection_sha256'] == seal['sources'][str(PACKET / 'selection.json')], 'native selection differs')
    require(e.read(name + '/run/suite-manifest.snapshot.json') == manifest, 'native input suite differs')
    if name.startswith('W'):
        require(native['cpu_affinity'] == [0, 1, 2, 3, 16, 17, 18, 19]
                and native['observed_nice'] == native['native_nice'] == 0, 'native timing placement')
    teardown = native['teardown']
    require(len(teardown) == 1 and teardown[0]['safe_to_exit'] is True
            and teardown[0]['idle_marker_complete'] is True
            and all(type(teardown[0][k]) is int and teardown[0][k] == 0 for k in ('exit_code', 'live_bytes', 'in_flight')),
            'native owner did not drain')
    rows = []
    for entry in entries:
        pid = entry['prompt_id']
        prefix = name + '/run/run/' + pid + '/'
        r = e.read(prefix + 'result.json')
        require(r['passed'] is True and r['arithmetic'] == ARITHMETIC
                and r['tokens'] == expected[pid][:cap], 'inexact prompt: ' + name + '/' + pid)
        require(r['cached_tokens'] == 0 and r['gpu_count'] == 1 and r['decode_mode'] == 'plain'
                and r['context'] == 4096 and r['requested_max_new'] == cap
                and r['prompt_tokens'] == entry['prompt_tokens'], 'request scope/cache identity')
        reset = e.read(prefix + 'reset.json')
        require(reset['passed'] is True and reset['cached_tokens'] == 0
                and reset['allocation_ids_preserved'] is True, 'cold request reset missing')
        count = 0
        if retain != 'none':
            for step in range(1, 9):
                layers = [json.loads(line) for line in e.raw(prefix + f'step{step}/layers.jsonl').splitlines()]
                require([x['layer'] for x in layers] == list(range(48)), 'retained layer coverage')
                for layer in layers:
                    leaf = f"step{step}/layer-{layer['layer']:02}.bf16"
                    e.verify(prefix + leaf, fixtures[pid][leaf])
                    require(layer['sha256'] == fixtures[pid][leaf]
                            and e.members[prefix + leaf]['bytes'] == 20480, 'layer exactness mismatch')
                    count += 1
        stamps = [x['completed_monotonic'] for x in r['timing_rows']]
        start, end = r['request_start_monotonic'], r['request_end_monotonic']
        require(len(stamps) == cap
                and all(type(x) in (int, float) and math.isfinite(x) for x in [start, end, *stamps])
                and start <= stamps[0] < stamps[-1] <= end, 'invalid request endpoints')
        metrics = M.request_metrics(r, entry['prompt_tokens'], cap, retain, start=start, end=end, device=True)
        rows.append(dict(metrics, passed=True, prompt_id=pid, prompt_class=M.PROMPT_CLASSES[pid],
                         prompt_token_sha256=token_hash(prompts[pid]), tokens=r['tokens'], repeat=1,
                         exact_oracle=True, compared_layer_fixtures=count,
                         native_result_sha256=sha(e.raw(prefix + 'result.json'))))
    summary = e.read(name + '/run/summary.json')
    require(summary == e.read(name + '/summary.json'), 'window/driver summary mismatch')
    require(summary['requests'] == rows and all(summary[k] == v for k, v in M.aggregate(rows).items()),
            'summary metrics differ from raw receipts')
    require(summary['passed'] is True and summary['prompt_kv_response_reuse'] is False
            and summary['kv_dtype'] == 'BF16' and summary['gpu_count'] == 1
            and summary['decode_mode'] == 'plain' and summary['context'] == 4096
            and summary['oracle_completion_sha256'] == sha(e.raw('oracle/completion.json'))
            and summary['timing_claim_eligible'] is (name == 'WS128')
            and summary['lane_scope'] == 'whole-host' and summary.get('cache_maintenance') == 'overlap', 'suite scope identity')
    driver = e.read(name + '/run/receipt.json')
    command=driver['command']
    require(command.count('--cache-maintenance')==1 and command[command.index('--cache-maintenance')+1]=='overlap'
            and command.count('--miss-path')==1 and command[command.index('--miss-path')+1]=='zero-copy'
            and '--bracket-inputs' not in command,'native overlapped cache argv differs')
    require(summary['view']=='down-tile16' and summary['selection_sha256']==seal['sources'][str(PACKET/'selection.json')], 'tile16 summary differs')
    require(driver['passed'] is True and driver['safe_to_exit'] is True and driver['window'] == name
            and driver['summary_sha256'] == sha(e.raw(name + '/run/summary.json')), 'driver receipt mismatch')
    require(summary['native_receipt_sha256'] == sha(e.raw(name + '/run/run/receipt.json')), 'native receipt binding')
    return rows


def derive(e):
    queue = e.read('queue.json')
    require(queue['schema'] == 'own-runtime.packet58.queue.v1' and queue['passed'] is True
            and queue['completed'] == list(ORDER) and queue.get('running') is None
            and queue['card'] == 0 and not queue.get('error'), 'queue incomplete or failed')
    seal = e.read('seal.json', SEAL_SHA)
    e.raw('submission-policy.json', seal['sources'][str(PACKET/'submission-policy.json')])
    require(seal['passed'] is True and seal['device_executed'] is False
            and seal['arithmetic'] == ARITHMETIC and seal['gpu_count'] == 1
            and seal['decode_mode'] == 'plain', 'seal identity')
    for group in ('sources', 'artifacts', 'gates'):
        for leaf, digest in seal[group].items():
            e.verify(group + '/' + leaf, digest)
            if group == 'gates':
                gate = e.read(group + '/' + leaf)
                require(gate['passed'] is True and gate['device_executed'] is False, 'failed CPU gate')
    e.raw('oracle-binding.json', seal['sources'][str(PACKET / 'oracle-binding.json')])
    manifest, expected, prompts, fixtures = oracle_check(e)
    windows, owners, device_owners, checked, misses = {}, set(), set(), {}, []
    for index, name in enumerate(ORDER):
        w = e.read(name + '/window.json')
        mode = 'K1' if name.startswith('K1') else name
        require(w['schema'] == 'own-runtime.packet58.window.v1' and w['window'] == mode
                and w['passed'] is True and w['qualifying'] is (mode != 'K1')
                and w['device_executed'] is True and w['child_still_running'] is False
                and w['stop_reasons'] == [] and w['returncode'] == 0 and not w.get('error'), 'failed window: ' + name)
        require(w.get('cache_maintenance') == 'overlap' and w.get('view') == 'down-tile16', 'window overlap selection differs')
        require(w['gpu_count'] == 1 and w['card'] == 0 and w['context'] == 4096 and w['decode_mode'] == 'plain'
                and w['build_receipt_sha256'] == SEAL_SHA and w['artifacts_sha256'] == seal['artifacts'], 'window identity')
        owner = (w['boot_id'], w['pid'], w['process_start_ticks'])
        require(owner not in owners and type(w['pid']) is int and w['pid'] > 0
                and type(w['process_start_ticks']) is int and w['process_start_ticks'] > 0, 'fresh process required')
        owners.add(owner)
        require(type(w['started_utc_ns']) is int and type(w['finished_utc_ns']) is int
                and 0 < w['started_utc_ns'] < w['finished_utc_ns'], 'window timestamps')
        if index:
            previous = windows[ORDER[index - 1]]
            require(w['started_utc_ns'] > previous['finished_utc_ns'] and w['boot_id'] == previous['boot_id']
                    and w['environment'] == previous['environment'], 'window overlap or identity drift')
        proof = w['lane_admission']
        scope = 'whole-host'
        require(proof['passed'] is True and proof['devices_drained'] is True and proof['card'] == 0
                and proof['scope'] == scope and proof['timing_claim_eligible'] is (name == 'WS128')
                and proof['reservation']['scope'] == scope and proof['reservation']['boot_id'] == w['boot_id'],
                'whole-host/lane admission missing')
        for key in ('clients', 'clients_latest', 'clients_after_drain'):
            require(proof[key]['blocked'] == [] and (scope != 'whole-host' or proof[key]['other'] == []), 'foreign timing owners')
        seen = [(pid, record) for pid, record in proof['owners'].items() if record['seen']]
        require(seen, 'native card ownership unobserved')
        for pid, record in seen:
            identity = (w['boot_id'], pid, record['start_ticks'])
            require(identity not in device_owners, 'native device process reused')
            require(all(fd['driver'] == 'xe' and fd['pci'] == '0000:23:00.0' for fd in record['fds']),
                    'native owner touched another card')
            device_owners.add(identity)
        for leaf, digest in w['native_files'].items():
            e.verify(name + '/' + leaf, digest)
        bound = set(w['native_files']) | set(w.get('postload_memory', {}).get('sources', {}))
        if mode != 'K1':
            bound.add('host-memory.jsonl')
        require(all(key[len(name) + 1:] in bound for key in e.members
                    if key.startswith(name + '/') and key != name + '/window.json'), 'unbound window evidence')
        for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
            require(not FAULT.search(e.raw(name + '/' + leaf).decode()), 'kernel fault evidence')
        if mode == 'K1':
            k = e.read(name + '/run/k1.json')
            cpu = e.read('gates/k1-cpu.json')
            require(all(k.get(x) is True for x in ('passed', 'safe_to_exit', 'device_executed', 'zero_copy_supported',
                        'zero_copy_bytes_equal', 'mixed_bytes_equal', 'streamed_bytes_equal', 'cold_rotation'))
                    and k['exact_output_sha256'] == cpu['exact_output_sha256']
                    and k['working_set_bytes'] >= 128 * 1024**2, 'K1 exact bytes/cold rotation')
            require(all(type(k[x]) in (int, float) and math.isfinite(k[x]) and k[x] > 0
                        for x in ('bytes_per_iteration', 'host_ms', 'vram_ms', 'streamed_ms')), 'K1 timing')
            misses.append('zero-copy' if k['bytes_per_iteration'] / (k['host_ms'] * 1e6) >= 12.5 else 'streamed')
        else:
            expected_previous = ORDER[index - 1]
            for ref, key in [(w['previous'], expected_previous + '/window.json'),
                             *[(r, n + '/window.json') for r, n in zip(w['k1_refs'], ORDER[:2], strict=True)]]:
                e.raw(key, ref['sha256'])
                require(Path(ref['path']).parts[-3:] == (CHAIN.name, *Path(key).parts), 'foreign predecessor reference')
            for ref, n in zip(w['k1_refs'], ORDER[:2], strict=True):
                e.raw(n + '/run/k1.json', ref['native_k1_sha256'])
            require(w['miss_path'] == ('zero-copy' if misses == ['zero-copy', 'zero-copy'] else 'streamed'), 'unbound miss choice')
            memory = w['postload_memory']
            require(memory['complete_postload'] is True and memory['full_cache_bytes'] == 18_000_000_000
                    and memory['pinned_expert_bytes'] > 0, 'expert cache/host pin proof')
            for leaf, digest in memory['sources'].items():
                e.verify(name + '/' + leaf, digest)
            e.verify(name + '/host-memory.jsonl', w['memory_samples_sha256'])
            checked[name] = check_requests(e, name, manifest, expected, prompts, fixtures)
        windows[name] = w
    timed = checked['WS128']
    require(len(timed) == 12 and all(r['metric_window_eligible'] for r in timed), 'missing WS128 metric window')
    aggregate = M.aggregate(timed)
    classes = aggregate['class_balanced_tok_s_1_100_intervals_after_ttft']['class_medians']
    require(len(classes) == 6, 'six prompt classes required')
    speed = statistics.median(classes.values())
    policy = e.read('record-threshold.json')
    record = validate_threshold(policy)
    require(record['threshold_tok_s'] is None or speed > record['threshold_tok_s'], 'not above matching one-card threshold')
    policy=e.read('submission-policy.json')
    require(policy == POLICY, 'submission policy differs')
    require(sha(e.raw('record-threshold.json')) == policy['ledger_sha256'] and record == policy['supersedes'], 'pinned ledger changed')
    faults={'major':0,'minor':0,'tokens':0,'new_gpu_fault_lines':0}
    for prompt in M.PROMPT_CLASSES:
        records=[json.loads(line) for line in e.raw('WS128/run/run/'+prompt+'/timings.jsonl').splitlines()]
        require(len(records)==128,'per-token fault counters incomplete')
        for row in records:
            for short,key in [('major','process_major_faults'),('minor','process_minor_faults')]:
                value=row[key];require(type(value) is int and value>=0,'invalid fault counter');faults[short]+=value
            faults['tokens']+=1
    w = windows['WS128']
    return dict(schema='lab.packet58w.realistic-suite-result.v1', packet='packet58w-onecard-record',
                model=MODEL, gpu_count=1, decode_mode='plain', miss_path=w['miss_path'],
                label='qwen38-flash-next-unsloth-iq3xxs-ownrt-tp1-packet58w-realistic-20261018',
                promotionIdentity=dict(model_revision=MODEL_REVISION, runtime_revision=seal['runtime_revision'],
                    optimization_identity='packet58w-tile16-overlap-tp1-plain-lru18gb-c4096-' + w['miss_path'] + '-seal-' + SEAL_SHA,
                    arithmetic=ARITHMETIC, suite_sha256=SUITE_SHA),
                build_receipt_sha256=SEAL_SHA, artifacts_sha256=seal['artifacts'], boot_id=w['boot_id'],
                primary_metric=dict(name=M.PRIMARY, value_tok_s=speed, class_medians=classes,
                    accounting='99 / (t100 - t1)', aggregation='median-of-prompt-class-medians'),
                secondary={**{k: aggregate[k] for k in ('submission100_statistics', 'ttft_statistics', 'wall_rate_statistics')},
                           'class_median_statistics': M.stats(classes.values())},
                rows=timed, exactness=dict(prompts=12, tokens=1536, all_prompts_exact=True,
                    oracle_arithmetic=ARITHMETIC, authority=str(ORACLE),
                    oracle_completion_sha256=sha(e.raw('oracle/completion.json')),
                    fresh_process_windows=['WS', 'WS128x', 'WS128'], fresh_exactness_repeat_passed=True),
                fresh_timing_repeat_passed=False, submission_scope=SCOPE,
                realistic_final_gate=aggregate['realistic_final_gate'], comparison=record,
                public_record_check=policy['public_record_check'],fault_counters=faults,
                limitations=['Only WS128 is timed; WS128x is whole-host exactness only.',
                             'A second whole-host timing run is still required for a speed verdict.',
                             'Strict 512-token gate false; 512-token prefill and natural completion unmeasured.'])


def submission_notes(result):
    fault=result['fault_counters'];previous=result['comparison']
    text=(MODEL+'. Quantized compressed version, separate from FP8. Lab own Intel Xe runtime; one Arc Pro B70. '
          'Target-only greedy; no draft/MTP. Host-pinned experts; 18 GB device expert cache; zero-copy misses; '
          'tile16 down layout; overlapped cache maintenance. BF16 KV at context 4096. '
          '12 cold prompts / 1536 exact tokens against packet49 CPU oracle iq3-p49-split32-v1; '
          'fresh WS/WS128x/WS128 exactness repeats. cached_tokens=0; no prompt/KV/response reuse. '
          '128-token owner scope: realistic_final_gate.passed=false; no strict512 claim. '
          'WS128 only: median of six class medians; 99 intervals from events 1 to 100 after TTFT. '
          'tokSTotal is median output/(last token-request start). WS128x is exactness only. '
          'Second fresh whole-host timing run still needed for a speed verdict. Standard 512-token prefill '
          'and full natural completion unmeasured. '
          f"Per-token process faults over {fault['tokens']} tokens: major={fault['major']}, minor={fault['minor']}; new GPU fault lines={fault['new_gpu_fault_lines']}. "
          f"Supersedes pinned local one-card record {previous['reference_submission']} ({previous['threshold_tok_s']:.6f} tok/s). "
          +result['public_record_check']['disclosure'])
    require(len(text)<=2000,'submission notes exceed 2000 characters')
    return text


def payload_for(result, result_ref, att_ref):
    rows = result['rows']
    flags = dict(packet58Evidence=True, benchmarkJson=result_ref['path'], benchmarkJsonSha256=result_ref['sha256'],
                 promotionAttestation=att_ref['path'], promotionAttestationSha256=att_ref['sha256'],
                 promotionIdentity=result['promotionIdentity'], buildReceiptSha256=SEAL_SHA,
                 realisticSuiteScopeException=SCOPE, rawRealisticFinalGate=result['realistic_final_gate'],
                 realisticSuiteGatePassed=False, strict512TokenFinalGatePassed=False, requestedMaxNew=128,
                 realisticSuiteId='rapid-model-snapshots-b70-realistic-v1', realisticSuiteCachedTokensAllZero=True,
                 primaryMetricName=M.PRIMARY, primaryMetricAccounting='inter-token-intervals',
                 primaryMetricAggregation='median-of-prompt-class-medians', metricWindowGeneratedTokens=100, metricWindowIntervals=99,
                 realisticPromptTokenCounts=[r['prompt_tokens'] for r in rows], realisticOutputTokenCounts=[128] * 12,
                 promptSha256=[r['prompt_token_sha256'] for r in rows], outputSha256=[r['output_token_sha256'] for r in rows],
                 prefixCaching=False, responseReuse=False, contextCheckpoints=0, historyAccelerated=False,
                 kvCacheDtype='bf16', apiKvCacheDtype='auto', attentionBackend='own Xe split32 QSA', apiAttentionBackend='sdpa',
                 concurrency=1, tensorParallel=1, gpuLayers=48, temperature=0, specDecoding=False, mtpEnabled=False,
                 deviceCards=[0], immutableExpertWeightCacheBytes=18_000_000_000, hostPinnedExperts=True,
                 wholeHostTiming=True, freshTimingRepeatPassed=False, cacheMaintenance='overlap', downLayout='down-tile16',
                 processFaultCounters=result['fault_counters'], supersedesSubmissionId=result['comparison']['reference_submission'],
                 commandSnippet='python3 -B ' + str(PACKET / 'queue_runner.py') +
                    ' --authorized-device-window --card 0 --output-root ' + str(CHAIN) + ' --view down-tile16 --fault-review <fresh-capture.json>',
                 githubResultPacket='https://github.com/steveseguin/b70-optimization-lab/blob/main/' +
                    str(Path(result_ref['path']).parent / 'result-packet.md'))
    return dict(label=result['label'], payload=dict(hfId='unsloth/Qwen3.8-Flash-Next-GGUF', modelRevision=MODEL_REVISION,
                engineName='custom', engineVersion='own-xpu-runtime packet58w-onecard-record sealed base ' + result['promotionIdentity']['runtime_revision'],
                backend='xpu', quantization='UD-IQ3_XXS (GGUF)',
                hardware=dict(hwClass='DISCRETE_GPU', gpuName='Intel Arc Pro B70', gpuCount=1, vramGb=32,
                              cpu='AMD Ryzen Threadripper PRO 5955WX 16-Cores', ramGb=128, os='Ubuntu 24.04.4 LTS'),
                contextLength=4096, batchSize=1, promptTokens=int(statistics.median(r['prompt_tokens'] for r in rows)),
                outputTokens=128, tokSOut=result['primary_metric']['value_tok_s'],
                tokSTotal=result['secondary']['wall_rate_statistics']['median'],
                ttftMs=result['secondary']['ttft_statistics']['median'], notes=submission_notes(result), engineFlags=flags))


def bound_file(ref, repo):
    raw = inside(repo, ref['path']).read_bytes()
    require(sha(raw) == ref['sha256'], 'evidence digest mismatch: ' + ref['path'])
    return raw


def replay_result(result, repo=ROOT):
    bundle = json.loads(gzip.decompress(bound_file(result['evidence_bundle'], repo)))
    require(bundle['schema'] == 'lab.packet58w.evidence-bundle.v1', 'unknown evidence bundle')
    derived = derive(Evidence(bundle['members']))
    require(result == dict(derived, evidence_bundle=result['evidence_bundle']), 'computed result differs from original evidence')
    return derived


def attestation(result, ref):
    return dict(schema='neural.download.promotion-attestation.v1', identity=result['promotionIdentity'],
                performance_evidence=ref, quality_evidence=[dict(result['evidence_bundle'], supports=list(GATES))],
                gates={**dict.fromkeys(GATES, True), 'strict_512_token_final_gate_passed': False,
                       'fresh_timing_repeat_passed': False}, submission_scope=SCOPE)


def is_packet49(item):
    """Compatibility hook for shared CLI, scoped solely to this new local wrapper."""
    flags = item.get('payload', {}).get('engineFlags', {})
    return flags.get('packet58Evidence') is True or 'packet58' in str(item.get('label', ''))


def scope_problems(item, repo=ROOT):
    try:
        flags = item['payload']['engineFlags']
        result_ref = dict(path=flags['benchmarkJson'], sha256=flags['benchmarkJsonSha256'])
        att_ref = dict(path=flags['promotionAttestation'], sha256=flags['promotionAttestationSha256'])
        result = json.loads(bound_file(result_ref, repo))
        replay_result(result, repo)
        current = validate_threshold(json.loads((repo / LIVE_THRESHOLD).read_bytes()))
        require(current['threshold_tok_s'] is None or result['primary_metric']['value_tok_s'] > current['threshold_tok_s'],
                'result does not exceed current one-card threshold')
        require(json.loads(bound_file(att_ref, repo)) == attestation(result, result_ref), 'attestation differs')
        require(item == payload_for(result, result_ref, att_ref), 'payload differs from verified result')
    except (KeyError, TypeError, ValueError, OSError, OverflowError, EOFError) as error:
        return ['invalid packet58w evidence: ' + str(error)]
    return []


def write_prepared(e, output, repo=ROOT):
    result = derive(e)  # Refuse before creating any output.
    require((repo / THRESHOLD).read_bytes() == e.raw('record-threshold.json'), 'threshold changed during preparation')
    output = Path(output).resolve()
    require(output.is_relative_to((repo / OUTPUT).resolve()) and not output.exists(), 'fresh packet58w submission output required')
    # Check notes before writing the bundle too.
    submission_notes(result)
    output.mkdir(parents=True)

    def save(leaf, raw):
        (output / leaf).write_bytes(raw)
        return dict(path=str((output / leaf).relative_to(repo)), sha256=sha(raw))

    result['evidence_bundle'] = save('evidence.json.gz', gzip.compress(encoded(dict(schema='lab.packet58w.evidence-bundle.v1', members=e.members)), mtime=0))
    ref = save('result.json', encoded(result))
    att_ref = save('promotion-attestation.json', encoded(attestation(result, ref)))
    item = payload_for(result, ref, att_ref)
    require(not scope_problems(item, repo), 'prepared scope replay failed')
    save('result-packet.md', ('# Packet58w one-card scoped measurement\n\n' + submission_notes(result) +
         '\n\nMeasured WS128: ' + str(result['primary_metric']['value_tok_s']) + ' tok/s. See result.json for all prompt/class statistics.\n'
         '\nPreparation only; no submission performed. Strict final gate and fresh timing confirmation remain false.\n').encode())
    save('payload-queue.json', encoded([item]))  # Queue LAST; no partial eligible output.
    return result


def update_record(result_path, submission_id, repo=ROOT):
    path = Path(result_path).resolve()
    require(path.is_relative_to(repo.resolve()), 'record result outside repository')
    raw = path.read_bytes()
    result = json.loads(raw)
    replay_result(result, repo)
    ledger = repo / LIVE_THRESHOLD
    before = ledger.read_bytes()
    policy = json.loads(before)
    current = validate_threshold(policy)
    value = result['primary_metric']['value_tok_s']
    require(current['threshold_tok_s'] is None or value > current['threshold_tok_s'], 'record update must improve threshold')
    policy['records'].append(dict(reference_submission=submission_id, threshold_tok_s=value,
                                  result=dict(path=str(path.relative_to(repo)), sha256=sha(raw))))
    validate_threshold(policy)
    require(ledger.read_bytes() == before, 'threshold changed during update')
    ledger.write_bytes(encoded(policy))
    return policy['records'][-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chain', type=Path, default=ROOT / CHAIN)
    parser.add_argument('--oracle', type=Path, default=ORACLE)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--update-record', type=Path, metavar='RESULT_JSON')
    parser.add_argument('--submission-id')
    args = parser.parse_args(argv)
    if args.update_record:
        require(args.submission_id and not args.output, '--update-record requires --submission-id and no output')
        print(json.dumps(update_record(args.update_record, args.submission_id)))
    else:
        require(args.output and not args.submission_id, 'preparation requires --output')
        result = write_prepared(collect(args.chain, args.oracle), args.output)
        print(json.dumps(dict(prepared_only=True, submitted=False, tok_s=result['primary_metric']['value_tok_s'])))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, EOFError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)

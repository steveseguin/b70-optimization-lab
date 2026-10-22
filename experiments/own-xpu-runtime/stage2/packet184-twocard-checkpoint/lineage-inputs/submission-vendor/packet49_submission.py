#!/usr/bin/env python3
"""CPU-only packet49 lineage evidence builder and offline submission validator.

No runtime imports, subprocesses, model reads, device calls or network access.
Original evidence bytes are retained in a portable gzip/base64 bundle. The helper
replays the same checks from that bundle, rather than trusting a computed headline.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from string import Template

from receipt_qualification import require_qualifying

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('experiments/own-xpu-runtime/stage2')
DEFAULT_PACKET = 'packet49c-round2'
ARITHMETIC = 'iq3-p49-split32-v1'
MODEL_REVISION = '766911a6b7369840a91dbcd95f9f997acaab6cd6'
SUITE_SHA = '0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812'
RECORD_FLOOR = 39.422009  # Historical bundle fallback only; new preparation reads THRESHOLD_FILE.
REFERENCE_RECORD = 'cmv9wjmtj013gle01v8k1yg4v'
FROZEN_MANIFEST = STAGE / 'suite-inputs-20261012-cap128/suite-manifest.json'
PRIMARY = 'median_of_prompt_class_medians_tok_s_1_100_intervals_after_ttft'
# Read from each immutable build-receipt.json. parent_commit is a build base,
# NOT a claim that that Git revision alone contains this sealed source overlay.
LINEAGE = {
    'packet49-integrate': ('34c62b433', 'c95a6cdf423d4c059afda23a6b9a5a2372f16781d021b7f65749fad1fd7ce5bb'),
    'packet49b-gemv': ('34c62b433', '000960bb7690119fbb99723c00abc23961aab3efb6b94bfeb8734624e3e71221'),
    'packet49c-round2': ('192ee28f2', '2ebe64adc810d7560c23f2674117c424caf360a4e7c3b75217eb25aa0b900dd7'),
}
D_PACKET = 'packet49d-round3'
LINEAGE[D_PACKET] = None  # Filled only by a verified post-device fast reseal.
PINS_FILE = Path('scripts/packet49_submission_pins.json')
THRESHOLD_FILE = Path('scripts/packet49_record_threshold.json')
# Historical 49c scope stays replayable; 49d uses its explicit sealed pin.
OWNER_128_PACKET49 = {(LINEAGE[DEFAULT_PACKET]): DEFAULT_PACKET}
CLASSES = {
    'incident-retrospective': 'operations', 'code-review': 'code',
    'customer-email': 'prose', 'sql-debugging': 'code', 'release-plan': 'operations',
    'benchmark-analysis': 'analysis', 'architecture-tradeoff': 'analysis',
    'bug-report-synthesis': 'operations', 'technical-guide': 'documentation',
    'risk-register': 'structured-writing', 'performance-hypotheses': 'analysis',
    'decision-memo': 'prose',
}
WINDOWS = ('KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128')
SUITES = WINDOWS[2:]
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)|job.*timed.out', re.I)
EXTENSION = ('Coordinator decision 2026-10-17: packet49c WS128 may use the existing '
             'owner-authorized 128-token scope only if all 12 prompts are exact against '
             'the packet49 CPU oracle and the class-balanced rate exceeds 39.422009. '
             'split32 QSA changes arithmetic identity to iq3-p49-split32-v1; lossless '
             'against this line\'s own CPU reference, not an assertion of equality to SPEED6. '
             'Preparation does not submit; the coordinator performs real submission.')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def validate_threshold(row):
    require(isinstance(row, dict) and row.get('schema') == 'lab.packet49.record-threshold.v1', 'record threshold schema')
    records = row.get('records')
    require(isinstance(records, list) and records, 'record threshold history missing')
    require(records[0] == dict(reference_submission=REFERENCE_RECORD, threshold_tok_s=39.422009), 'record threshold historical anchor changed')
    previous = 0.
    ids = set()
    for record in records:
        require(isinstance(record, dict), 'record threshold row must be an object')
        value = record.get('threshold_tok_s')
        require(type(value) in (int, float) and math.isfinite(value) and value > previous,
                'record threshold must be finite and strictly increasing; lowering refused')
        submission = record.get('reference_submission')
        require(isinstance(submission, str) and re.fullmatch(r'[A-Za-z0-9_-]+', submission)
                and submission not in ids, 'invalid or duplicate reference submission')
        if previous:
            ref = record.get('result', {})
            require(isinstance(ref.get('path'), str) and not Path(ref['path']).is_absolute()
                    and '..' not in Path(ref['path']).parts
                    and re.fullmatch(r'[0-9a-f]{64}', str(ref.get('sha256', ''))), 'record result pin missing')
        ids.add(submission)
        previous = value
    return records[-1]


def threshold_policy(e):
    if 'record-threshold.json' not in e.members:
        return dict(reference_submission=REFERENCE_RECORD, threshold_tok_s=RECORD_FLOOR), None
    row = e.read('record-threshold.json')
    return validate_threshold(row), sha(e.raw('record-threshold.json'))


def lineage_pin(e, packet):
    require(packet in LINEAGE, 'unknown packet lineage')
    if packet != D_PACKET:
        revision, seal_hash = LINEAGE[packet]
        return revision, seal_hash
    pins = e.read('submission-pins.json')
    require(pins.get('schema') == 'lab.packet49.submission-pins.v1', 'submission pins schema')
    pin = pins.get('lineages', {}).get(packet)
    require(isinstance(pin, dict), 'packet49d selection has not been resealed')
    revision, seal_hash = pin.get('runtime_revision'), pin.get('build_receipt_sha256')
    require(isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{7,40}', revision)
            and re.fullmatch(r'[0-9a-f]{64}', str(seal_hash)), 'packet49d runtime/seal pin invalid')
    selection_hash = pin.get('selection_sha256')
    require(re.fullmatch(r'[0-9a-f]{64}', str(selection_hash)), 'packet49d selection pin invalid')
    e.raw('selection.json', selection_hash)
    seal = e.read('seal.json', seal_hash)
    require(seal.get('runtime_revision') == revision and seal.get('device_admission_ready') is True
            and seal.get('sources', {}).get(str(STAGE / packet / 'selection.json')) == selection_hash,
            'packet49d selection/runtime not bound by seal')
    require('record-threshold.json' in e.members, 'packet49d requires current pinned record threshold')
    return revision, seal_hash


def pin_resealed_packet49d(*, repo=ROOT):
    """Called AFTER p49d fast-reseal verifies and writes its final build receipt.

    CPU checks remain the caller's responsibility. This pins the exact final
    selection and runtime; it never builds, runs a device, or changes the floor.
    """
    packet = repo / STAGE / D_PACKET
    seal_raw = (packet / 'build-receipt.json').read_bytes()
    seal = json.loads(seal_raw)
    selection_raw = (packet / 'selection.json').read_bytes()
    selection_hash = sha(selection_raw)
    require(seal.get('passed') is True and seal.get('device_executed') is False
            and seal.get('arithmetic') == ARITHMETIC and seal.get('device_admission_ready') is True, 'incomplete packet49d final seal')
    revision = seal.get('runtime_revision')
    require(isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{7,40}', revision), 'missing packet49d runtime revision')
    require(seal.get('sources', {}).get(str(STAGE / D_PACKET / 'selection.json')) == selection_hash,
            'selection is not bound by final seal')
    pins = json.loads((repo / PINS_FILE).read_bytes())
    require(pins.get('schema') == 'lab.packet49.submission-pins.v1'
            and set(pins.get('lineages', {})) == {D_PACKET}, 'submission pins schema')
    pins['lineages'][D_PACKET] = dict(runtime_revision=revision, build_receipt_sha256=sha(seal_raw),
                                    selection_sha256=selection_hash)
    (repo / PINS_FILE).write_bytes(encoded(pins))
    return pins['lineages'][D_PACKET]


def pin_packet49d(repo=ROOT):
    return pin_resealed_packet49d(repo=repo)


def token_hash(tokens):
    return sha(json.dumps(tokens, separators=(',', ':')).encode())


def stats(values):
    values = sorted(values)
    require(values and all(type(v) in (int, float) and math.isfinite(v) for v in values), 'invalid numeric sample')
    at = (len(values) - 1) * .1
    lo = int(at)
    return dict(median=statistics.median(values), mean=statistics.mean(values),
                p10=values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (at - lo), count=len(values))


def close(actual, expected, message):
    require(type(actual) in (int, float) and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8), message)


class Evidence:
    """Logical names avoid opening source paths when validating a saved bundle."""
    def __init__(self, members=None):
        self.members = {} if members is None else members

    def add(self, key, path):
        raw = path.read_bytes()
        member = dict(source_path=str(path), sha256=sha(raw), raw_base64=base64.b64encode(raw).decode())
        require(key not in self.members or self.members[key] == member, 'evidence changed during collection: ' + key)
        self.members[key] = member
        return raw

    def raw(self, key, digest=None):
        member = self.members[key]
        raw = base64.b64decode(member['raw_base64'], validate=True)
        require(sha(raw) == member['sha256'], 'evidence member hash mismatch: ' + key)
        if digest is not None:
            require(sha(raw) == digest, 'bound receipt hash mismatch: ' + key)
        return raw

    def read(self, key, digest=None):
        value = json.loads(self.raw(key, digest))
        require_qualifying(value)
        return value

    def add_digest(self, key, path):
        # KD repeats large logit/state fixtures. Preserve their original on-disk
        # hashes and checker receipts without duplicating those binary payloads.
        from promotion_evidence import sha256_file
        self.members[key] = dict(source_path=str(path), sha256=sha256_file(path),
                                 bytes=path.stat().st_size, retention='sha256-only')

    def verify_digest(self, key, digest):
        member = self.members[key]
        if member.get('retention') == 'sha256-only':
            require(key.startswith('KD/owner') and key.endswith(('.bin', '.bf16'))
                    and member['bytes'] > 0 and member['sha256'] == digest,
                    'bound fixture hash mismatch: ' + key)
        else:
            self.raw(key, digest)


def inside(root, value):
    path = (root / value).resolve()
    require(path.is_relative_to(root.resolve()), 'path escapes evidence root: ' + str(value))
    return path


def collect(packet, chain, oracle, repo=ROOT):
    """Read finished artifacts only; no glob of model trees or binary payloads."""
    e = Evidence()
    e.add('record-threshold.json', repo / THRESHOLD_FILE)
    validate_threshold(e.read('record-threshold.json'))
    directory = repo / STAGE / packet
    if packet == D_PACKET:
        e.add('submission-pins.json', repo / PINS_FILE)
        e.add('selection.json', directory / 'selection.json')
    e.add('seal.json', directory / 'build-receipt.json')
    if packet != 'packet49-integrate':
        e.add('oracle-binding.json', directory / 'oracle-binding.json')
    authority = repo / STAGE / 'packet49-integrate/oracle'
    for name in ('build-receipt.json', 'arithmetic.json', 'suite_check.py'):
        e.add('oracle-source/' + name, authority / name)
    e.add('oracle-source/frozen-manifest.json', repo / FROZEN_MANIFEST)
    for name in ('completion.json', 'suite-manifest.json', 'determinism.json', 'kd-capture.json', 'old-v-new.json'):
        e.add('oracle/' + name, oracle / name)
    for entry in e.read('oracle/suite-manifest.json')['prompts']:
        pid = entry['prompt_id']
        require(pid in CLASSES, 'unknown prompt')
        for name in ('receipt.json', 'result.json', 'validation.json', 'input.json'):
            e.add(f'oracle/{pid}/{name}', oracle / pid / name)
    for name in ('receipt.json', 'result.json', 'validation.json', 'input.json'):
        e.add('oracle/incident-retrospective-repeat/' + name, oracle / 'incident-retrospective-repeat' / name)
    for name in WINDOWS:
        root = chain / name
        window = json.loads(e.add(name + '/window.json', root / 'window.json'))
        for leaf in ('kernel-preflight.txt', 'kernel-window.txt'):
            e.add(name + '/' + leaf, root / leaf)
        for relative in window['receipts']:
            if name == 'KD' and relative.endswith(('.bin', '.bf16')):
                e.add_digest(name + '/' + relative, inside(root, relative))
            else:
                e.add(name + '/' + relative, inside(root, relative))
        if name in SUITES:
            for leaf in ('summary.json', 'suite-manifest.snapshot.json', 'ranks/ownership.json'):
                e.add(name + '/run/' + leaf, root / 'run' / leaf)
        elif name == 'W2m':
            e.add(name + '/run/ownership.json', root / 'run/ownership.json')
    e.add('dispatch.json', chain / 'K2/run0/dispatch-measured.json')
    return e


def scope(packet=DEFAULT_PACKET):
    from submit_localmaxxing_results import OWNER_128_AUTHORIZATION, OWNER_128_RAW_GATE
    return dict(owner_authorization=OWNER_128_AUTHORIZATION,
                raw_realistic_final_gate=OWNER_128_RAW_GATE, strict_512_gate_passed=False,
                owner_exception_authorized=True, requested_max_new=128,
                prepared_only=True, real_submission_performed=False,
                authorization_extension=(EXTENSION if packet != D_PACKET else
                    'Coordinator packet49d scope: same packet49 CPU oracle, all 12 prompts exact, '
                    '128-token owner-authorized scope; unchanged iq3-p49-split32-v1 arithmetic; '
                    'class-balanced speed must exceed the pinned current submitted record. '
                    'Preparation does not submit; the coordinator performs real submission.'))


def derive(e, packet):
    """Recompute the entire result from hash-bound, original receipt bytes."""
    revision, seal_hash = lineage_pin(e, packet)
    threshold, threshold_hash = threshold_policy(e)
    floor = threshold['threshold_tok_s']
    seal = e.read('seal.json', seal_hash)
    require(seal['passed'] is True and seal['runtime_revision' if packet == D_PACKET else 'parent_commit'] == revision
            and seal['arithmetic'] == ARITHMETIC, 'sealed runtime identity mismatch')
    completion = e.read('oracle/completion.json')
    require(completion['passed'] is True and completion['device_executed'] is False
            and completion['arithmetic'] == ARITHMETIC and completion['prompts'] == 12
            and completion['token_cap'] == 128, 'incomplete CPU oracle')
    for key, name in (('manifest_sha256', 'suite-manifest.json'), ('determinism_sha256', 'determinism.json'),
                      ('kd_capture_sha256', 'kd-capture.json'), ('old_v_new_sha256', 'old-v-new.json')):
        e.raw('oracle/' + name, completion[key])
    oracle_build = e.read('oracle-source/build-receipt.json', completion['build_receipt_sha256'])
    e.raw('oracle-source/arithmetic.json', completion['arithmetic_sha256'])
    for name in ('build-receipt.json', 'arithmetic.json'):
        e.raw('oracle-source/' + name, seal['oracle_inputs_sha256'][name])
    frozen = e.read('oracle-source/frozen-manifest.json', oracle_build['frozen_sources'][str(FROZEN_MANIFEST)])
    e.raw('oracle-source/frozen-manifest.json', completion['old_manifest_sha256'])
    require(oracle_build['passed'] is True and oracle_build['binary_sha256'] == seal['oracle_binary_sha256'], 'oracle binary identity mismatch')
    require(sha(e.raw('oracle-source/suite_check.py')) == seal['sources'][str(STAGE / packet / 'oracle/suite_check.py')], 'oracle checker changed')
    if packet != 'packet49-integrate':
        binding = e.read('oracle-binding.json')
        require(binding == seal['shared_oracle'] and binding['arithmetic'] == ARITHMETIC
                and binding['binary_sha256'] == oracle_build['binary_sha256'], 'shared oracle static binding changed')
    manifest = e.read('oracle/suite-manifest.json')
    require(manifest['complete'] is True and manifest['arithmetic'] == ARITHMETIC
            and manifest['context'] == 4096 and manifest['token_cap'] == 128
            and manifest['suite_sha256'] == SUITE_SHA, 'suite identity mismatch')
    entries = manifest['prompts']
    require(len(entries) == 12 and [r['prompt_id'] for r in entries] == list(CLASSES), 'missing, duplicate or reordered prompt')
    expected, prompts = {}, {}
    for entry, original in zip(entries, frozen['prompts'], strict=True):
        pid = entry['prompt_id']
        require(all(entry[k] == original[k] for k in ('prompt_id', 'input_bundle', 'input_bundle_hashes', 'prompt_tokens')),
                'prompt differs from frozen suite')
        receipt = e.read(f'oracle/{pid}/receipt.json', entry['oracle_receipt_sha256'])
        require(receipt['verified'] is True and receipt['device_executed'] is False
                and receipt['arithmetic'] == ARITHMETIC and receipt['binary_sha256'] == oracle_build['binary_sha256'], 'oracle prompt not verified')
        result = e.read(f'oracle/{pid}/result.json', receipt['result_sha256'])
        validation = e.read(f'oracle/{pid}/validation.json', receipt['validation_sha256'])
        inp = e.read(f'oracle/{pid}/input.json', receipt['input_sha256'])
        require(sha(e.raw(f'oracle/{pid}/input.json')) == entry['input_bundle_hashes']['input.json'], 'prompt input hash mismatch')
        tokens = result['tokens']
        require(result['arithmetic'] == ARITHMETIC and result['device_executed'] is False
                and result['status'] in ('token-cap', 'eos') and not result.get('error')
                and len(tokens) == 128 and all(type(t) is int for t in tokens)
                and not any(t in (248044, 248046) for t in tokens[:-1])
                and validation['passed'] is True and entry['generated_tokens'] == 128,
                'incomplete oracle prompt')
        require(len(inp['tokens']) == entry['prompt_tokens'] and inp['tokens'], 'prompt length mismatch')
        expected[pid], prompts[pid] = tokens, inp['tokens']
    repeat = e.read('oracle/determinism.json')
    first = 'oracle/incident-retrospective/'
    second = 'oracle/incident-retrospective-repeat/'
    require(repeat['passed'] is True, 'CPU oracle repeat failed')
    e.raw(first + 'receipt.json', repeat['first_receipt_sha256'])
    rr = e.read(second + 'receipt.json', repeat['repeat_receipt_sha256'])
    require(rr['verified'] is True and rr['binary_sha256'] == oracle_build['binary_sha256'], 'CPU repeat not verified')
    repeated = e.read(second + 'result.json', rr['result_sha256'])
    rv = e.read(second + 'validation.json', rr['validation_sha256'])
    require(rr['arithmetic'] == repeated['arithmetic'] == ARITHMETIC
            and rr['device_executed'] is repeated['device_executed'] is False
            and repeated['status'] in ('token-cap', 'eos') and not repeated.get('error')
            and rv['passed'] is True
            and e.read(second + 'input.json', rr['input_sha256']) == e.read(first + 'input.json')
            and repeated['tokens'] == expected['incident-retrospective']
            and rv['fixture_hashes'] == e.read(first + 'validation.json')['fixture_hashes'], 'CPU repeat differs')
    windows = {name: e.read(name + '/window.json') for name in WINDOWS}
    headline = windows['WS128']
    artifacts = seal['artifacts_sha256']
    selected_hash = sha(e.raw('selection.json')) if packet == D_PACKET else None

    def observed_selection(row, location, *, mandatory=False):
        if selected_hash is not None and (mandatory or 'selection_sha256' in row):
            require(row.get('selection_sha256') == selected_hash,
                    'native selection identity mismatch: ' + location)

    seen_pids, checked = set(), {}
    initial_faults = {line for line in e.raw('KD/kernel-preflight.txt').decode().splitlines() if FAULT.search(line)}
    for name, w in windows.items():
        observed_selection(w, name + '/window.json', mandatory=True)
        require(w['schema'] == packet.split('-')[0] + '.window.v1' and w['window'] == name
                and w['passed'] is True and w['qualifying'] is True
                and w['device_executed'] is True and w['cpu_rehearsal'] is False
                and w['diagnostic_unsealed'] is False and not w.get('error'), 'failed/non-device window: ' + name)
        require(w['build_receipt_sha256'] == seal_hash and w['artifacts_sha256'] == artifacts
                and (w['card'], w['context'], w['draft_rank'], w['target_split']) == (0, 4096, 1, 23)
                and w['boot_id'] == headline['boot_id'] and w['dispatch_sha256'] == headline['dispatch_sha256'], 'window identity mismatch: ' + name)
        if packet != 'packet49-integrate':
            shared = w['shared_oracle']
            require(shared['arithmetic'] == ARITHMETIC
                    and shared['static_binding_sha256'] == sha(e.raw('oracle-binding.json'))
                    and shared['completion_sha256'] == sha(e.raw('oracle/completion.json'))
                    and all(shared[k] == completion[k] for k in ('manifest_sha256', 'determinism_sha256', 'kd_capture_sha256')),
                    'window oracle binding mismatch: ' + name)
        pids = w['launched_pids']
        require(len(pids) == 2 and len(set(pids)) == 2 and not seen_pids.intersection(pids)
                and w['retained_owner_pids'] == [], 'fresh processes/teardown missing: ' + name)
        seen_pids.update(pids)
        preflight_faults = {line for line in e.raw(name + '/kernel-preflight.txt').decode().splitlines() if FAULT.search(line)}
        # The preflight journal is a 200-line tail. Old entries may roll out;
        # a newly appearing fault between windows must still block preparation.
        require(preflight_faults <= initial_faults, 'new fault-line change between windows: ' + name)
        require(not FAULT.search(e.raw(name + '/kernel-window.txt').decode()), 'new fault-line change: ' + name)
        require(w['receipts'], 'missing receipts: ' + name)
        for relative, digest in w['receipts'].items():
            e.verify_digest(name + '/' + relative, digest)
            if relative.endswith('.json'):
                r = e.read(name + '/' + relative, digest)
                require(r.get('passed') is True, 'failed native receipt: ' + name + '/' + relative)
                observed_selection(r, name + '/' + relative)
        if name == 'KD':
            mandatory = {'host-reference-identity.json', 'host-reference.jsonl.gz'} | {
                f'owner{i}/{leaf}' for i in (0, 1) for leaf in ('receipt.json', 'fixture-comparison.json')}
            require(mandatory <= set(w['receipts']), 'KD mandatory receipts missing')
            host = e.read('KD/host-reference-identity.json')
            observed_selection(host, 'KD/host-reference-identity.json', mandatory=True)
            require(host['passed'] is True and host['device_executed'] is False
                    and host['binary_sha256'] == artifacts['gnu-host/own-rt-iq3']
                    and host['dispatch_sha256'] == headline['dispatch_sha256'] and host['fixtures']
                    and host['capture_table_sha256'] == e.read('oracle/kd-capture.json')['table_sha256'], 'KD host identity mismatch')
            for owner in (0, 1):
                native = e.read(f'KD/owner{owner}/receipt.json')
                observed_selection(native, f'KD/owner{owner}/receipt.json', mandatory=True)
                teardown = native['teardown']
                require(native['device_executed'] is True and len(teardown) == 1
                        and teardown[0]['safe_to_exit'] is True and teardown[0]['live_bytes'] == 0
                        and teardown[0]['in_flight'] == 0, 'unsafe KD teardown')
                comparison = e.read(f'KD/owner{owner}/fixture-comparison.json')
                require(comparison['passed'] is True and comparison['sha256'] == host['fixtures']
                        and comparison['files'] == len(host['fixtures']), 'KD fixture comparison mismatch')
                for leaf, digest in host['fixtures'].items():
                    require(w['receipts'][f'owner{owner}/' + leaf] == digest, 'KD fixture not bound by window')
                    e.verify_digest(f'KD/owner{owner}/' + leaf, digest)
            continue
        owner = 'run/ranks' if name in SUITES else 'run'
        ownership = e.read(name + '/' + owner + '/ownership.json')
        require(ownership['retained_pids'] == [] and ownership['returncodes'] == [0, 0], 'unfinished rank processes')
        for rank in (0, 1):
            key = f'{owner}/rank{rank}/receipt.json'
            native = e.read(name + '/' + key, w['receipts'][key])
            observed_selection(native, name + '/' + key, mandatory=True)
            teardown = native['teardown']
            require(native['rank'] == rank and len(teardown) == 1
                    and teardown[0]['safe_to_exit'] is True and teardown[0]['live_bytes'] == 0
                    and teardown[0]['in_flight'] == 0, 'unsafe rank teardown')
        if name == 'W2m':
            request = e.read(name + '/run/receipt.json', w['receipts']['run/receipt.json'])
            require(request['tokens'] == expected['incident-retrospective'][:64]
                    and w['token_matches'] == 64 and w['layer_matches'] == 8 * 48, 'W2m non-exact prompt')
            continue
        summary = e.read(name + '/run/summary.json')
        require(summary == w['summary'] == e.read(name + '/run/receipt.json', w['receipts']['run/receipt.json'])
                and summary['passed'] is True and summary['complete'] is True
                and summary['partial_suite'] is False, 'incomplete suite: ' + name)
        e.raw(name + '/run/suite-manifest.snapshot.json', completion['manifest_sha256'])
        require(summary['manifest_sha256'] == completion['manifest_sha256']
                and summary['draft'] == ('none' if name == 'WSs' else 'mtp')
                and summary['controller'] == w['controller'] == 'native'
                and summary['requested_max_new'] == w['max_new'] == 128 and w['repeat'] == 1
                and w['prompt_overlap'] == 'on', 'suite oracle/draft/controller identity mismatch')
        steps = [] if name == 'WS128' else list(range(1, 9)) + (list(range(97, 105)) if name == 'WS128x' else [])
        require(w['retained_steps'] == steps and w['diagnostic_for_speed'] is bool(steps), 'window retention scope differs')
        rows = summary['rows']
        require(len(rows) == 12 and [r['prompt_id'] for r in rows] == list(CLASSES), 'partial/repeated suite')
        warmkey = 'run/warmup/receipt.json'
        warm = e.read(name + '/' + warmkey, w['receipts'][warmkey])
        selection = warm['warmup_selection']
        require(warm['excluded_from_timing'] is True
                and all(selection[k] is True for k in ('distinct_from_every_suite_prompt',
                        'absent_from_every_contiguous_suite_input_span', 'complete_reset_before_measured_requests')), 'cold suite reset/warmup missing')
        warm_tokens = selection['token_ids']
        require(warm_tokens and all(warm_tokens != p[i:i + len(warm_tokens)]
                for p in prompts.values() for i in range(len(p))), 'measured prompt warmed')
        checked[name] = {}
        for row in rows:
            pid = row['prompt_id']
            key = 'run/' + row['receipt']
            r = e.read(name + '/' + key, w['receipts'][key])
            require(row['passed'] is True and row['repeat'] == r['repeat'] == 1
                    and r['prompt_id'] == pid and r['prompt_class'] == row['prompt_class'] == CLASSES[pid]
                    and r['device_executed'] is True and r['arithmetic'] == ARITHMETIC
                    and r['binary_sha256'] == artifacts['device/own-rt-iq3'] and r['target_split'] == 23,
                    'request identity mismatch')
            require(r['tokens'] == expected[pid], 'non-exact prompt: ' + name + '/' + pid)
            require(r['cached_tokens'] == row['cached_tokens'] == r['usage']['prompt_tokens_details']['cached_tokens'] == 0
                    and r['requested_max_new'] == row['requested_max_new'] == 128
                    and r['output_tokens'] == row['output_tokens'] == 128
                    and r['prompt_tokens'] == row['prompt_tokens'] == len(prompts[pid]), 'request scope/cache mismatch')
            require(r['prompt_token_sha256'] == row['prompt_token_sha256'] == token_hash(prompts[pid])
                    and r['output_token_sha256'] == row['output_token_sha256'] == token_hash(r['tokens']), 'token hash mismatch')
            check = r['oracle_check']
            fixtures = 0 if name == 'WS128' else (16 if name == 'WS128x' else 8) * 48
            require(check['passed'] is True and check['every_emitted_token'] is True
                    and check['tokens'] == 128 and check['fixture_files'] == fixtures
                    and check['checker_sha256'] == sha(e.raw('oracle-source/suite_check.py')), 'exact checker receipt missing')
            checked[name][pid] = r
    e.raw('dispatch.json', headline['dispatch_sha256'])
    companion = headline['exactness_companion']
    require(companion['window'] == 'WS128x' and companion['boot_id'] == headline['boot_id']
            and companion['sha256'] == sha(e.raw('WS128x/window.json')), 'WS128 exactness companion differs')
    rows = []
    for pid, r in checked['WS128'].items():
        require(r['retain_steps'] == 'none' and r['diagnostic'] is False and r['metric_window_eligible'] is True,
                'instrumented/diagnostic speed')
        stamps = r['token_timestamps']
        require(len(stamps) == 128 and all(type(t) in (int, float) and math.isfinite(t) for t in stamps)
                and all(b > a for a, b in zip(stamps, stamps[1:])), 'invalid token timestamps')
        start, end = r['request_start_monotonic'], r['request_end_monotonic']
        require(math.isfinite(start) and math.isfinite(end) and start <= stamps[0] < stamps[-1] <= end, 'invalid request timing')
        rate = 99 / (stamps[99] - stamps[0])
        ttft = 1000 * (stamps[0] - start)
        # suite_metrics.request_metrics overwrites the pipeline's wall field with
        # t_last - request_start. Preserve that SPEED6 metric; also retain end rate.
        wall = 128 / (stamps[-1] - start)
        for actual, expected_value, label in ((r['tok_s_1_100_intervals_after_ttft'], rate, 'rate'),
                (r['ttft_ms'], ttft, 'TTFT'), (r['wall_tok_s'], wall, 'wall rate')):
            close(actual, expected_value, 'stored ' + label + ' differs from timestamps')
        accounting = dict(rate=rate, event_count=100, interval_count=99, numerator=99,
                          first=stamps[0], last=stamps[99], complete=True)
        require(r['submission100'] == accounting, '99-interval accounting mismatch')
        rows.append(dict(prompt_id=pid, prompt_class=CLASSES[pid], prompt_tokens=len(prompts[pid]),
                         output_tokens=len(r['tokens']), requested_max_new=128, cached_tokens=0,
                         prompt_sha256=token_hash(prompts[pid]), output_sha256=token_hash(r['tokens']),
                         submission_tok_s=rate, ttft_ms=ttft, wall_tok_s=wall,
                         request_end_wall_tok_s=128 / (end - start), submission100=accounting,
                         token_timestamps=stamps,
                         full_natural_completion_tok_s=(127 / (stamps[-1] - stamps[0]) if r['tokens'][-1] in (248044, 248046) else None),
                         full_cap_limited_tok_s=(None if r['tokens'][-1] in (248044, 248046) else 127 / (stamps[-1] - stamps[0]))))
    classes = {c: statistics.median(r['submission_tok_s'] for r in rows if r['prompt_class'] == c)
               for c in sorted(set(CLASSES.values()))}
    headline_rate = statistics.median(classes.values())
    require(headline_rate > floor, f'speed at or below {floor}: {headline_rate}')
    identity = dict(model_revision=MODEL_REVISION, runtime_revision=revision,
                    optimization_identity=f'{packet}-{ARITHMETIC}-tp2-c4096-target23-25-draft-rank1-seal-{seal_hash}',
                    suite_sha256=SUITE_SHA, arithmetic=ARITHMETIC)
    return dict(schema='lab.packet49.realistic-suite-result.v1', packet=packet,
                label=f'qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-{packet}-realistic-20261017',
                promotionIdentity=identity, artifacts_sha256=artifacts, build_receipt_sha256=seal_hash,
                boot_id=headline['boot_id'], dispatch_sha256=headline['dispatch_sha256'],
                primary_metric=dict(name=PRIMARY, value_tok_s=headline_rate, class_medians=classes,
                                    accounting='99 / (t100 - t1)', aggregation='median-of-prompt-class-medians'),
                secondary=dict(submission100_all_prompt_statistics=stats([r['submission_tok_s'] for r in rows]),
                               ttft_statistics=stats([r['ttft_ms'] for r in rows]),
                               wall_rate_statistics=stats([r['wall_tok_s'] for r in rows]),
                               class_median_statistics=stats(list(classes.values()))),
                exactness=dict(prompts=12, tokens=sum(len(t) for t in expected.values()),
                               oracle_arithmetic=ARITHMETIC, all_prompts_exact=True,
                               repeated_windows=list(SUITES), unchanged_target_verifier=True,
                               authority='hash-bound CPU oracle and independent device checker receipts; no tolerance'),
                rows=rows, submission_scope=scope(packet), realistic_final_gate=scope(packet)['raw_realistic_final_gate'],
                comparison=dict(reference_submission=threshold['reference_submission'], threshold_tok_s=floor,
                                observed_increase_percent=(headline_rate / floor - 1) * 100,
                                **({'threshold_file_sha256': threshold_hash} if threshold_hash else {})),
                limitations=['512-token natural completion and 512-input-token prefill not measured',
                             'New split32 arithmetic; exact to its own CPU reference, not claimed identical to SPEED6',
                             'One preregistered timed WS128; independent quality windows are not pooled speed repeats',
                             'Wall rate uses last token minus request start, matching SPEED6 suite accounting'])


def payload_for(result, result_ref, attestation_ref, result_doc):
    """Construct measured fields only from the replayed result; no headline pin."""
    from submit_localmaxxing_results import OWNER_128_AUTHORIZATION
    rows, secondary = result['rows'], result['secondary']
    packet = result['packet']
    flags = dict(
        benchmarkJson=result_ref['path'], benchmarkJsonSha256=result_ref['sha256'],
        promotionAttestation=attestation_ref['path'], promotionAttestationSha256=attestation_ref['sha256'],
        promotionIdentity=result['promotionIdentity'], packet49Evidence=True,
        buildReceiptSha256=result['build_receipt_sha256'], bootId=result['boot_id'],
        dispatchSha256=result['dispatch_sha256'], targetSplit=[23, 25], draftRank=1, deviceCards=[0, 1],
        realisticSuiteScopeException=OWNER_128_AUTHORIZATION,
        scopeAuthorizationExtension=result['submission_scope']['authorization_extension'], rawRealisticFinalGate=result['realistic_final_gate'],
        realisticSuiteGatePassed=False, strict512TokenFinalGatePassed=False, requestedMaxNew=128,
        realisticSuiteId='rapid-model-snapshots-b70-realistic-v1', realisticSuiteCachedTokensAllZero=True,
        realisticPromptTokenCounts=[r['prompt_tokens'] for r in rows],
        realisticOutputTokenCounts=[r['output_tokens'] for r in rows],
        promptSha256=[r['prompt_sha256'] for r in rows], outputSha256=[r['output_sha256'] for r in rows],
        primaryMetricName=PRIMARY, primaryMetricAccounting='inter-token-intervals',
        primaryMetricAggregation='median-of-prompt-class-medians', metricWindowGeneratedTokens=100,
        metricWindowIntervals=99, prefixCaching=False, responseReuse=False, contextCheckpoints=0,
        historyAccelerated=False, targetModelVerifiedAcceptedTokens=True,
        kvCacheDtype='bf16', apiKvCacheDtype='auto', attentionBackend='own Xe split32 QSA',
        apiAttentionBackend='sdpa', concurrency=1, tensorParallel=2, temperature=0,
        specDecoding=True, mtpEnabled=True, specMethod='mtp', specNumTokens=1,
        githubResultPacket='https://github.com/steveseguin/b70-optimization-lab/blob/main/' + result_doc,
        commandSnippet=f'python3 -B {STAGE / packet}/window.py --authorized-device-window --window WS128 '
                       '--card 0 --context 4096 --target-split 23 --draft-rank 1 --controller native '
                       '--repeat 1 --retain-steps none --output <chain>/WS128 '
                       '--suite-manifest <packet49-oracle>/suite-manifest.json --exactness-window <chain>/WS128x/window.json '
                       '--k0 <K0> --k1a <K1a> --k1b <K1b> --k2 <K2> --w0p <W0p> --kd <KD> --dispatch <K2-dispatch>',
        commandSnippetFullInEvidence=str(STAGE / packet / 'WINDOW.md'),
    )
    notes = (f'{packet}, sealed build base {result["promotionIdentity"]["runtime_revision"]}. '
             'Quantized compressed Unsloth UD-IQ3_XXS model; separate from FP8. Two B70 cards 0+1, '
             '23/25 target split, one-token MTP on rank 1, full BF16 KV, capacity 4096. '
             f'Arithmetic changed from SPEED6 to {ARITHMETIC} (split32 QSA). '
             'Lossless against this line\'s own packet49 CPU reference; no claim of bit equality to SPEED6. '
             'All 12 prompts / 1536 tokens exact, repeated in fresh WS/WSs/WS128x/WS128 processes; '
             'accepted speculative tokens verified by unchanged target. Cold prompts, complete resets, '
             'zero cached tokens, no prompt/KV/response/history reuse. Preregistered WS128 alone supplies '
             'the headline: median of six class medians, 99 intervals between events 1 and 100. '
             'Owner-authorized 128-token scope extended by coordinator 2026-10-17. Strict 512-cap gate '
             'remains false. 512-token natural completion and standard prefill not measured. '
             'No new fault signatures in window journal tails; historical faults retained. '
             'Wall rate: output tokens / (last-token timestamp - request start), matching SPEED6.')
    return dict(label=result['label'], payload=dict(
        hfId='unsloth/Qwen3.8-Flash-Next-GGUF', modelRevision=MODEL_REVISION,
        engineName='custom', engineVersion=f'own-xpu-runtime {packet} sealed base {result["promotionIdentity"]["runtime_revision"]}; '
                                          f'device binary sha256 {result["artifacts_sha256"]["device/own-rt-iq3"]}',
        backend='xpu', quantization='UD-IQ3_XXS (GGUF)',
        hardware=dict(hwClass='DISCRETE_GPU', gpuName='Intel Arc Pro B70', gpuCount=2, vramGb=32,
                      cpu='AMD Ryzen Threadripper PRO 5955WX 16-Cores', ramGb=128, os='Ubuntu 24.04.4 LTS'),
        contextLength=4096, batchSize=1, promptTokens=int(statistics.median(r['prompt_tokens'] for r in rows)),
        outputTokens=128, tokSOut=result['primary_metric']['value_tok_s'],
        tokSTotal=secondary['wall_rate_statistics']['median'], ttftMs=secondary['ttft_statistics']['median'],
        notes=notes, engineFlags=flags))


def bound_file(ref, repo):
    path = inside(repo, ref['path'])
    raw = path.read_bytes()
    require(sha(raw) == ref['sha256'], 'evidence digest mismatch: ' + ref['path'])
    return raw


def replay_result(result, repo=ROOT):
    bundle = json.loads(gzip.decompress(bound_file(result['evidence_bundle'], repo)))
    require(bundle['schema'] == 'lab.packet49.evidence-bundle.v1', 'unknown bundle schema')
    derived = derive(Evidence(bundle['members']), result['packet'])
    require(result == dict(derived, evidence_bundle=result['evidence_bundle']), 'computed result differs from original evidence')
    return derived


def scope_problems(item, repo=ROOT):
    try:
        require_qualifying(item)
        flags = item['payload']['engineFlags']
        identity = flags['promotionIdentity']
        pair = (identity['runtime_revision'], flags['buildReceiptSha256'])
        authorized = dict(OWNER_128_PACKET49)
        if flags.get('packet49Evidence') is True and D_PACKET in identity.get('optimization_identity', ''):
            pins = json.loads((repo / PINS_FILE).read_bytes())
            require(pins.get('schema') == 'lab.packet49.submission-pins.v1', 'submission pins schema')
            pin = pins.get('lineages', {}).get(D_PACKET)
            require(isinstance(pin, dict), 'packet49d selection has not been resealed')
            authorized[(pin['runtime_revision'], pin['build_receipt_sha256'])] = D_PACKET
        require(pair in authorized, 'packet49 runtime/seal pair not owner-authorized')
        result_ref = dict(path=flags['benchmarkJson'], sha256=flags['benchmarkJsonSha256'])
        att_ref = dict(path=flags['promotionAttestation'], sha256=flags['promotionAttestationSha256'])
        result = json.loads(bound_file(result_ref, repo))
        att = json.loads(bound_file(att_ref, repo))
        require_qualifying(result)
        require_qualifying(att)
        require(result['packet'] == authorized[pair], 'packet pin mismatch')
        replay_result(result, repo)
        from promotion_evidence import REQUIRED_GATES, SCHEMA
        require(att['schema'] == SCHEMA and att['identity'] == result['promotionIdentity']
                and att['performance_evidence'] == result_ref and att['submission_scope'] == scope(result['packet'])
                and att['gates'] == {**dict.fromkeys(REQUIRED_GATES, True), 'strict_512_token_final_gate_passed': False}
                and att['quality_evidence'] == [dict(result['evidence_bundle'], supports=list(REQUIRED_GATES))],
                'attestation identity, evidence or gates mismatch')
        result_doc = str(Path(result_ref['path']).parent / 'result-packet.md')
        require(item == payload_for(result, result_ref, att_ref, result_doc), 'payload differs from bound computed result/scope')
    except (KeyError, TypeError, ValueError, OSError, OverflowError) as error:
        return ['invalid packet49 owner-authorized 128-token scope: ' + str(error)]
    return []


def is_packet49(item):
    flags = item.get('payload', {}).get('engineFlags', {})
    identity = flags.get('promotionIdentity') or {}
    return (flags.get('packet49Evidence') is True or 'packet49' in str(item.get('label', ''))
            or 'packet49' in str(identity.get('optimization_identity', ''))
            or identity.get('runtime_revision') == LINEAGE[DEFAULT_PACKET][0]
            or flags.get('buildReceiptSha256') in {v[1] for v in LINEAGE.values() if v is not None})


def write_prepared(e, packet, output, repo=ROOT):
    if 'record-threshold.json' in e.members:
        require((repo / THRESHOLD_FILE).read_bytes() == e.raw('record-threshold.json'),
                'record threshold changed during preparation; collect again')
    if packet == D_PACKET:
        require((repo / PINS_FILE).read_bytes() == e.raw('submission-pins.json'),
                'packet49d lineage pin changed during preparation')
    result = derive(e, packet)  # Refuse before writing any eligible output.
    output = output.absolute()
    require(output.resolve().is_relative_to(repo.resolve()), 'output must be inside repository')
    require(not output.exists(), 'new output directory required; never overwrite evidence')
    require(any(output.resolve().is_relative_to((repo / STAGE / p / 'submission').resolve()) for p in LINEAGE),
            'output must be beneath a lineage submission directory')
    output.mkdir(parents=True)

    def save(name, raw):
        path = output / name
        path.write_bytes(raw)
        return dict(path=str(path.relative_to(repo)), sha256=sha(raw))

    bundle = dict(schema='lab.packet49.evidence-bundle.v1', members=e.members)
    result['evidence_bundle'] = save('evidence.json.gz', gzip.compress(encoded(bundle), mtime=0))
    result_ref = save('result.json', encoded(result))
    from promotion_evidence import REQUIRED_GATES, SCHEMA
    att = dict(schema=SCHEMA, identity=result['promotionIdentity'], performance_evidence=result_ref,
               quality_evidence=[dict(result['evidence_bundle'], supports=list(REQUIRED_GATES))],
               gates={**dict.fromkeys(REQUIRED_GATES, True), 'strict_512_token_final_gate_passed': False},
               submission_scope=scope(packet))
    att_ref = save('promotion-attestation.json', encoded(att))
    values = dict(packet=packet, revision=result['promotionIdentity']['runtime_revision'],
                  seal=result['build_receipt_sha256'], arithmetic=ARITHMETIC,
                  binary=result['artifacts_sha256']['device/own-rt-iq3'],
                  headline=str(result['primary_metric']['value_tok_s']),
                  all_prompt=str(result['secondary']['submission100_all_prompt_statistics']['median']),
                  p10=str(result['secondary']['submission100_all_prompt_statistics']['p10']),
                  mean=str(result['secondary']['submission100_all_prompt_statistics']['mean']),
                  ttft=str(result['secondary']['ttft_statistics']['median']),
                  wall=str(result['secondary']['wall_rate_statistics']['median']),
                  increase=str(result['comparison']['observed_increase_percent']),
                  boot=result['boot_id'], reference=result['comparison']['reference_submission'], result_path=result_ref['path'])
    templates = ROOT / STAGE / DEFAULT_PACKET / 'submission'
    for name in ('result-packet', 'ledger-entry'):
        text = Template((templates / (name + '.md.in')).read_text()).substitute(values)
        text = text.replace('over 39.422009 threshold', 'over ' + str(result['comparison']['threshold_tok_s']) + ' threshold')
        if packet == D_PACKET:
            text = text.replace("This comes from the seal's `parent_commit`", "This comes from the seal's `runtime_revision`")
        save(name + '.md', text.encode())
    if packet in (DEFAULT_PACKET, D_PACKET):
        item = payload_for(result, result_ref, att_ref, str((output / 'result-packet.md').relative_to(repo)))
        problems = scope_problems(item, repo)
        require(not problems, '; '.join(problems))
        # Queue written LAST. An interrupted or failed build never leaves a queue.
        save('payload-queue.json', encoded([item]))
    return result


def update_record(result_path, submission_id, *, repo=ROOT):
    """Append only a verified, faster result after the coordinator submits it.

    The ID is the coordinator's receipt of real submission; this offline tool
    never contacts the service or asserts that it observed that transaction.
    """
    path = Path(result_path).resolve()
    require(path.is_relative_to(repo.resolve()), 'record result must be inside repository')
    raw = path.read_bytes()
    result = json.loads(raw)
    replay_result(result, repo)
    threshold_path = repo / THRESHOLD_FILE
    before = threshold_path.read_bytes()
    policy = json.loads(before)
    current = validate_threshold(policy)
    value = result['primary_metric']['value_tok_s']
    require(value > current['threshold_tok_s'], 'record update must improve the current threshold')
    policy['records'].append(dict(reference_submission=submission_id, threshold_tok_s=value,
                                 result=dict(path=str(path.relative_to(repo.resolve())), sha256=sha(raw))))
    validate_threshold(policy)
    require(threshold_path.read_bytes() == before, 'record threshold changed during update')
    threshold_path.write_bytes(encoded(policy))
    return policy['records'][-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', choices=LINEAGE, default=DEFAULT_PACKET)
    parser.add_argument('--update-record', type=Path, metavar='RESULT_JSON', help='Append a validated submitted result to the pinned record ledger')
    parser.add_argument('--submission-id', help='Real submission ID supplied by coordinator after successful submission')
    parser.add_argument('--chain', type=Path, help='Finished registered device-cards01-a chain (read only)')
    parser.add_argument('--oracle', type=Path, default=Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice -n 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32)), 'reserved CPU cores forbidden')
    if args.update_record:
        require(args.submission_id and not args.chain and not args.output, '--update-record requires --submission-id and no chain/output')
        print(json.dumps(update_record(args.update_record, args.submission_id)))
        return 0
    require(args.submission_id is None, '--submission-id requires --update-record')
    chain = args.chain or Path('/home/steve/own-xpu-runtime-results') / args.packet / 'build/device-cards01-a'
    # No cherry-picked repeat or card pair. Test fixtures exercise the pure API.
    require(chain.resolve() == (ROOT / STAGE / args.packet / 'build/device-cards01-a').resolve(), 'unregistered chain')
    require(args.oracle.resolve() == (ROOT / STAGE / 'packet49-integrate/oracle/results').resolve(), 'unregistered oracle')
    output = args.output or ROOT / STAGE / args.packet / 'submission/prepared'
    require(not output.exists(), 'new output directory required')
    evidence = collect(args.packet, chain, args.oracle)
    result = write_prepared(evidence, args.packet, output)
    print(json.dumps(dict(prepared_only=True, submitted=False, output=str(output),
                          class_balanced_tok_s=result['primary_metric']['value_tok_s'],
                          strict_512_gate_passed=False)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyError, TypeError, ValueError, OSError, OverflowError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(1)

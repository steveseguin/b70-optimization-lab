"""Synthetic completed-chain fixtures; never starts or imports a runtime/device."""
import base64
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
import packet49_submission as p
import promotion_evidence as promotion
import submit_localmaxxing_results as submit


def put(e, name, value):
    raw = value if isinstance(value, bytes) else p.encoded(value)
    e.members[name] = dict(source_path='/synthetic/' + name, sha256=p.sha(raw),
                           raw_base64=base64.b64encode(raw).decode())
    return p.sha(raw)


def fixture(packet=p.DEFAULT_PACKET, speed=45):
    e = p.Evidence()
    directory = p.ROOT / p.STAGE / packet
    for key, path in [('seal.json', directory / 'build-receipt.json')]:
        e.add(key, path)
    seal = e.read('seal.json')
    if packet != 'packet49-integrate':
        e.add('oracle-binding.json', directory / 'oracle-binding.json')
    authority = p.ROOT / p.STAGE / 'packet49-integrate/oracle'
    for name in ('build-receipt.json', 'arithmetic.json', 'suite_check.py'):
        e.add('oracle-source/' + name, authority / name)
    checker = p.sha(e.raw('oracle-source/suite_check.py'))
    e.add('oracle-source/frozen-manifest.json', p.ROOT / p.FROZEN_MANIFEST)
    originals = e.read('oracle-source/frozen-manifest.json')['prompts']
    entries = []
    for index, (pid, cls) in enumerate(p.CLASSES.items()):
        original = originals[index]
        raw_input = (p.ROOT / original['input_bundle'] / 'input.json').read_bytes()
        inp = json.loads(raw_input)
        ih = put(e, f'oracle/{pid}/input.json', raw_input)
        tokens = list(range(1000 + index, 1128 + index))
        rh = put(e, f'oracle/{pid}/result.json', dict(tokens=tokens, arithmetic=p.ARITHMETIC,
                     device_executed=False, status='token-cap', schema='iq3-runtime-cpu-oracle.v1'))
        vh = put(e, f'oracle/{pid}/validation.json', dict(passed=True, fixture_hashes={'step1/layer-00.bf16': 'a' * 64}))
        receipt = dict(verified=True, device_executed=False, arithmetic=p.ARITHMETIC,
                       binary_sha256=seal['oracle_binary_sha256'], result_sha256=rh,
                       validation_sha256=vh, input_sha256=ih)
        receipt_hash = put(e, f'oracle/{pid}/receipt.json', receipt)
        entries.append(dict(prompt_id=pid, input_bundle=original['input_bundle'], input_bundle_hashes=original['input_bundle_hashes'],
                            generated_tokens=128, prompt_tokens=len(inp['tokens']), oracle_receipt_sha256=receipt_hash))
    for name in ('input.json', 'result.json', 'receipt.json', 'validation.json'):
        put(e, 'oracle/incident-retrospective-repeat/' + name, e.raw('oracle/incident-retrospective/' + name))
    manifest = dict(complete=True, arithmetic=p.ARITHMETIC, context=4096, token_cap=128,
                    suite_sha256=p.SUITE_SHA, prompts=entries)
    mh = put(e, 'oracle/suite-manifest.json', manifest)
    dh = put(e, 'oracle/determinism.json', dict(passed=True,
             first_receipt_sha256=entries[0]['oracle_receipt_sha256'], repeat_receipt_sha256=entries[0]['oracle_receipt_sha256']))
    kh = put(e, 'oracle/kd-capture.json', dict(passed=True, table_sha256='c' * 64))
    oh = put(e, 'oracle/old-v-new.json', dict(informational_only=True))
    completion = dict(passed=True, device_executed=False, arithmetic=p.ARITHMETIC, prompts=12,
                      token_cap=128, manifest_sha256=mh, determinism_sha256=dh, kd_capture_sha256=kh,
                      old_manifest_sha256=p.sha(e.raw('oracle-source/frozen-manifest.json')), old_v_new_sha256=oh, build_receipt_sha256=p.sha(e.raw('oracle-source/build-receipt.json')),
                      arithmetic_sha256=p.sha(e.raw('oracle-source/arithmetic.json')))
    ch = put(e, 'oracle/completion.json', completion)
    dispatch = put(e, 'dispatch.json', {'synthetic': True})
    for n, name in enumerate(p.WINDOWS):
        w = dict(schema=packet.split('-')[0] + '.window.v1', window=name, passed=True,
                 qualifying=True, device_executed=True, diagnostic_unsealed=False, cpu_rehearsal=False,
                 build_receipt_sha256=p.sha(e.raw('seal.json')), artifacts_sha256=seal['artifacts_sha256'],
                 card=0, context=4096, draft_rank=1, target_split=23, boot_id='synthetic-boot',
                 controller='native', max_new=128, repeat=1, prompt_overlap='on',
                 retained_steps=[] if name == 'WS128' else list(range(1,9)) + (list(range(97,105)) if name == 'WS128x' else []),
                 diagnostic_for_speed=name != 'WS128', dispatch_sha256=dispatch, launched_pids=[n * 10 + 1, n * 10 + 2], retained_owner_pids=[], receipts={})
        if packet != 'packet49-integrate':
            w['shared_oracle'] = dict(arithmetic=p.ARITHMETIC, static_binding_sha256=p.sha(e.raw('oracle-binding.json')),
                                      completion_sha256=ch, manifest_sha256=mh, determinism_sha256=dh, kd_capture_sha256=kh)
        put(e, name + '/kernel-preflight.txt', b'historical Fault response\n')
        put(e, name + '/kernel-window.txt', b'No fresh device errors\n')

        def receipt(key, data):
            w['receipts'][key] = put(e, name + '/' + key, data)

        if name == 'KD':
            fixtures = {'row-1/sample.bf16': p.sha(b'\x00\x00')}
            receipt('host-reference-identity.json', dict(passed=True, device_executed=False,
                binary_sha256=seal['artifacts_sha256']['gnu-host/own-rt-iq3'], dispatch_sha256=dispatch, capture_table_sha256='c' * 64, fixtures=fixtures))
            for owner in (0, 1):
                receipt(f'owner{owner}/receipt.json', dict(passed=True, device_executed=True,
                    teardown=[dict(safe_to_exit=True, live_bytes=0, in_flight=0)]))
                receipt(f'owner{owner}/fixture-comparison.json', dict(passed=True, files=1, sha256=fixtures))
                receipt(f'owner{owner}/row-1/sample.bf16', b'\x00\x00')
            receipt('host-reference.jsonl.gz', gzip.compress(b'synthetic', mtime=0))
            put(e, name + '/window.json', w)
            continue
        owner = 'run/ranks' if name in p.SUITES else 'run'
        put(e, name + '/' + owner + '/ownership.json', dict(retained_pids=[], returncodes=[0, 0]))
        for rank in (0, 1):
            receipt(f'{owner}/rank{rank}/receipt.json', dict(passed=True, rank=rank,
                    teardown=[dict(safe_to_exit=True, live_bytes=0, in_flight=0)]))
        if name == 'W2m':
            receipt('run/receipt.json', dict(passed=True, tokens=e.read('oracle/incident-retrospective/result.json')['tokens'][:64]))
            w.update(token_matches=64, layer_matches=384)
        else:
            rows = []
            for i, (pid, cls) in enumerate(p.CLASSES.items()):
                # Uneven classes and different per-prompt rates catch wrong aggregation.
                rate = speed + i
                stamps = [100 + i * 100 + j / rate for j in range(128)]
                start = stamps[0] - 1
                rate = 99 / (stamps[99] - stamps[0])
                tokens = e.read(f'oracle/{pid}/result.json')['tokens']
                prompt = e.read(f'oracle/{pid}/input.json')['tokens']
                request = dict(passed=True, repeat=1, prompt_id=pid, prompt_class=cls, device_executed=True,
                    arithmetic=p.ARITHMETIC, binary_sha256=seal['artifacts_sha256']['device/own-rt-iq3'],
                    target_split=23, tokens=tokens, cached_tokens=0, usage={'prompt_tokens_details': {'cached_tokens': 0}},
                    requested_max_new=128, output_tokens=128, prompt_tokens=len(prompt),
                    output_token_sha256=p.token_hash(tokens), prompt_token_sha256=p.token_hash(prompt),
                    oracle_check=dict(passed=True, every_emitted_token=True, tokens=128,
                        fixture_files=0 if name == 'WS128' else (16 if name == 'WS128x' else 8) * 48,
                        checker_sha256=checker),
                    retain_steps='none' if name == 'WS128' else '1-8', diagnostic=name != 'WS128',
                    metric_window_eligible=name == 'WS128', token_timestamps=stamps,
                    request_start_monotonic=start, request_end_monotonic=stamps[-1] + .01,
                    tok_s_1_100_intervals_after_ttft=rate, ttft_ms=1000., wall_tok_s=128 / (stamps[-1] - start),
                    submission100=dict(rate=rate, event_count=100, interval_count=99, numerator=99,
                                       first=stamps[0], last=stamps[99], complete=True))
                key = f'repeat-1/{pid}/receipt.json'
                receipt('run/' + key, request)
                row = {key: request[key] for key in ('prompt_id', 'prompt_class', 'passed', 'repeat', 'cached_tokens',
                       'requested_max_new', 'output_tokens', 'prompt_tokens', 'prompt_token_sha256', 'output_token_sha256')}
                row['receipt'] = key
                rows.append(row)
            receipt('run/warmup/receipt.json', dict(passed=True, excluded_from_timing=True,
                warmup_selection=dict(token_ids=[98765, 98766], distinct_from_every_suite_prompt=True,
                absent_from_every_contiguous_suite_input_span=True, complete_reset_before_measured_requests=True)))
            summary = dict(passed=True, complete=True, partial_suite=False, rows=rows,
                           controller='native', requested_max_new=128, manifest_sha256=mh, draft='none' if name == 'WSs' else 'mtp')
            receipt('run/receipt.json', summary)
            put(e, name + '/run/summary.json', summary)
            put(e, name + '/run/suite-manifest.snapshot.json', manifest)
            w['summary'] = summary
        if name == 'WS128':
            w['exactness_companion'] = dict(window='WS128x', boot_id=w['boot_id'], sha256=p.sha(e.raw('WS128x/window.json')))
        put(e, name + '/window.json', w)
    return e


def change_request(e, window, key, value):
    name = f'{window}/run/repeat-1/incident-retrospective/receipt.json'
    r = e.read(name)
    r[key] = value
    digest = put(e, name, r)
    w = e.read(window + '/window.json')
    w['receipts'][name[len(window) + 1:]] = digest
    put(e, window + '/window.json', w)


def test_computes_class_balanced_and_secondary_metrics():
    r = p.derive(fixture(), p.DEFAULT_PACKET)
    assert r['primary_metric']['value_tok_s'] == pytest.approx(51.25)
    assert r['secondary']['submission100_all_prompt_statistics']['median'] == pytest.approx(50.5)
    assert r['secondary']['submission100_all_prompt_statistics']['p10'] == pytest.approx(46.1)
    assert r['secondary']['submission100_all_prompt_statistics']['mean'] == pytest.approx(50.5)
    assert r['secondary']['ttft_statistics']['median'] == pytest.approx(1000)
    assert r['exactness']['tokens'] == 1536
    assert r['realistic_final_gate']['passed'] is False


@pytest.mark.parametrize('packet', [name for name, pin in p.LINEAGE.items() if pin is not None])
def test_generic_lineage(packet):
    assert p.derive(fixture(packet), packet)['packet'] == packet


def test_nonexact_prompt_refused_even_when_passed_and_hash_rebound():
    e = fixture()
    change_request(e, 'WS128', 'tokens', [0] * 128)
    with pytest.raises(ValueError, match='non-exact prompt'):
        p.derive(e, p.DEFAULT_PACKET)


@pytest.mark.parametrize('speed', [20, 33])
def test_slower_result_refused(speed):
    with pytest.raises(ValueError, match='speed at or below'):
        p.derive(fixture(speed=speed), p.DEFAULT_PACKET)


@pytest.mark.parametrize('change,match', [
    ('missing', '.*'), ('fault', 'fault-line'), ('seal', 'bound receipt hash'),
    ('cpu', 'non-device'), ('reused_pid', 'fresh processes'), ('retained', 'teardown'),
    ('cache', 'cache'), ('timestamp', 'timestamps'), ('fixture', 'checker'),
    ('oracle', 'hash mismatch'), ('repeat', 'CPU repeat'), ('missing_manifest', '.*'),
])
def test_refusals(change, match):
    e = fixture()
    if change == 'missing':
        del e.members['WS/run/receipt.json']
    elif change == 'fault':
        put(e, 'WSs/kernel-window.txt', b'xe: timed-out job\n')
    elif change == 'seal':
        put(e, 'seal.json', dict(e.read('seal.json'), parent_commit='other'))
    elif change in ('cpu', 'reused_pid', 'retained'):
        w = e.read('WS/window.json')
        w.update({'cpu_rehearsal': True} if change == 'cpu' else
                 {'launched_pids': [1, 2]} if change == 'reused_pid' else {'retained_owner_pids': [21]})
        put(e, 'WS/window.json', w)
    elif change == 'cache':
        change_request(e, 'WS128', 'cached_tokens', 1)
    elif change == 'timestamp':
        change_request(e, 'WS128', 'token_timestamps', [1.] * 128)
    elif change == 'fixture':
        r = e.read('WS128x/run/repeat-1/incident-retrospective/receipt.json')['oracle_check']
        change_request(e, 'WS128x', 'oracle_check', dict(r, fixture_files=1))
    elif change == 'oracle':
        put(e, 'oracle/incident-retrospective/result.json', {'tokens': [1] * 128})
    elif change == 'repeat':
        r = e.read('oracle/incident-retrospective-repeat/result.json')
        h = put(e, 'oracle/incident-retrospective-repeat/result.json', dict(r, tokens=[1] * 128))
        r = e.read('oracle/incident-retrospective-repeat/receipt.json')
        h = put(e, 'oracle/incident-retrospective-repeat/receipt.json', dict(r, result_sha256=h))
        d = e.read('oracle/determinism.json')
        h = put(e, 'oracle/determinism.json', dict(d, repeat_receipt_sha256=h))
        c = e.read('oracle/completion.json')
        put(e, 'oracle/completion.json', dict(c, determinism_sha256=h))
    else:
        del e.members['WS128/run/suite-manifest.snapshot.json']
    with pytest.raises((ValueError, KeyError), match=match):
        p.derive(e, p.DEFAULT_PACKET)


def prepared(tmp_path):
    output = tmp_path / p.STAGE / p.DEFAULT_PACKET / 'submission/prepared'
    p.write_prepared(fixture(), p.DEFAULT_PACKET, output, tmp_path)
    return output, json.loads((output / 'payload-queue.json').read_text())[0]


def test_full_helper_and_attestation_accept_synthetic_bundle(tmp_path, monkeypatch):
    output, item = prepared(tmp_path)
    monkeypatch.setattr(submit, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(promotion, 'REPO_ROOT', tmp_path)
    assert submit.preflight_payload(item) == []
    promotion.validate_promotion_attestation(output / 'promotion-attestation.json', output / 'result.json')
    assert 'prepared, not submitted' in (output / 'result-packet.md').read_text()
    assert 'pending coordinator submission' in (output / 'ledger-entry.md').read_text()


@pytest.mark.parametrize('change', ['headline', 'revision', 'seal', 'gate', 'cap', 'identity', 'authorization', 'metrics', 'attestation'])
def test_helper_refuses_tampered_payload_or_bound_files(tmp_path, monkeypatch, change):
    output, item = prepared(tmp_path)
    monkeypatch.setattr(submit, 'REPO_ROOT', tmp_path)
    flags = item['payload']['engineFlags']
    if change == 'headline':
        item['payload']['tokSOut'] += 1
    elif change == 'revision':
        flags['promotionIdentity']['runtime_revision'] = 'other'
    elif change == 'seal':
        flags['buildReceiptSha256'] = '0' * 64
    elif change == 'gate':
        flags['strict512TokenFinalGatePassed'] = True
    elif change == 'cap':
        flags['requestedMaxNew'] = 512
    elif change == 'identity':
        flags['promotionIdentity']['arithmetic'] = 'old'
    elif change == 'authorization':
        del flags['realisticSuiteScopeException']
    elif change == 'metrics':
        path = output / 'result.json'
        r = json.loads(path.read_text())
        r['primary_metric']['value_tok_s'] += 1
        path.write_bytes(p.encoded(r))
        flags['benchmarkJsonSha256'] = p.sha(path.read_bytes())
    else:
        path = output / 'promotion-attestation.json'
        a = json.loads(path.read_text())
        a['gates']['no_quality_loss'] = False
        path.write_bytes(p.encoded(a))
        flags['promotionAttestationSha256'] = p.sha(path.read_bytes())
    assert submit.preflight_payload(item)


def test_failed_build_leaves_no_queue(tmp_path):
    out = tmp_path / p.STAGE / p.DEFAULT_PACKET / 'submission/prepared'
    with pytest.raises(ValueError, match='speed at or below'):
        p.write_prepared(fixture(speed=20), p.DEFAULT_PACKET, out, tmp_path)
    assert not out.exists()


def test_existing_output_refused(tmp_path):
    output, _ = prepared(tmp_path)
    with pytest.raises(ValueError, match='never overwrite'):
        p.write_prepared(fixture(), p.DEFAULT_PACKET, output, tmp_path)


def test_pin_matches_real_seal():
    seal = p.ROOT / p.STAGE / p.DEFAULT_PACKET / 'build-receipt.json'
    assert (json.loads(seal.read_bytes())['parent_commit'], p.sha(seal.read_bytes())) in p.OWNER_128_PACKET49
    assert set(submit.OWNER_128_RESULTS) == {'75d2c459d', '34c62b433'}


def test_exactly_equal_record_refused():
    evidence = fixture()
    measured = p.derive(evidence, p.DEFAULT_PACKET)['primary_metric']['value_tok_s']
    with patch.object(p, 'RECORD_FLOOR', measured):
        with pytest.raises(ValueError, match='speed at or below'):
            p.derive(evidence, p.DEFAULT_PACKET)


@pytest.mark.parametrize('change,match', [('prompt', 'frozen suite'), ('companion', 'companion'), ('kd', 'KD teardown')])
def test_rebound_evidence_cannot_bypass_independent_gates(change, match):
    e = fixture()
    if change == 'prompt':
        manifest = e.read('oracle/suite-manifest.json')
        manifest['prompts'][0]['input_bundle_hashes']['input.json'] = '0' * 64
        digest = put(e, 'oracle/suite-manifest.json', manifest)
        completion = e.read('oracle/completion.json')
        put(e, 'oracle/completion.json', dict(completion, manifest_sha256=digest))
    elif change == 'companion':
        w = e.read('WS128/window.json')
        w['exactness_companion']['sha256'] = '0' * 64
        put(e, 'WS128/window.json', w)
    else:
        r = e.read('KD/owner0/receipt.json')
        r['teardown'][0]['in_flight'] = 1
        digest = put(e, 'KD/owner0/receipt.json', r)
        w = e.read('KD/window.json')
        w['receipts']['owner0/receipt.json'] = digest
        put(e, 'KD/window.json', w)
    with pytest.raises(ValueError, match=match):
        p.derive(e, p.DEFAULT_PACKET)


@pytest.mark.parametrize('fail_at,expected', [(0, 3), (1, 1), (2, 2)])
def test_wrapper_only_builds_then_two_dry_runs_and_stops(tmp_path, fail_at, expected):
    # Stub the CPU launcher; no Python builder, network call, key read or device work.
    import os
    stub = tmp_path / 'nice'
    log = tmp_path / 'calls'
    stub.write_text('#!/usr/bin/env bash\n'
                    'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
                    'n=$(wc -l < "$CALL_LOG")\n'
                    'if [[ "$n" == "$FAIL_AT" ]]; then exit 7; fi\n')
    stub.chmod(0o755)
    script = p.ROOT / p.STAGE / p.DEFAULT_PACKET / 'submission/prepare_submission.sh'
    run = subprocess.run(['bash', str(script), str(tmp_path / 'unused')], capture_output=True, text=True,
                         env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH'],
                              'CALL_LOG': str(log), 'FAIL_AT': str(fail_at)})
    calls = log.read_text().splitlines()
    assert len(calls) == expected
    assert 'scripts/packet49_submission.py' in calls[0]
    if expected > 1:
        assert calls[1].endswith('--dry-run')
    if expected > 2:
        assert calls[2].endswith('--server-dry-run')
        assert 'No real submission performed' in run.stdout
    assert (run.returncode == 0) == (fail_at == 0)


def test_collect_reads_synthetic_chain_without_copying_kd_binary(tmp_path):
    original = fixture()
    chain, oracle = tmp_path / 'chain', tmp_path / 'oracle'
    for key in original.members:
        if key.startswith('oracle/'):
            path = oracle / key.removeprefix('oracle/')
        elif key.split('/')[0] in p.WINDOWS:
            path = chain / key
        elif key == 'dispatch.json':
            path = chain / 'K2/run0/dispatch-measured.json'
        else:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original.raw(key))
    collected = p.collect(p.DEFAULT_PACKET, chain, oracle)
    assert collected.members['KD/owner0/row-1/sample.bf16']['retention'] == 'sha256-only'
    assert 'raw_base64' not in collected.members['KD/owner0/row-1/sample.bf16']
    original.add('record-threshold.json', p.ROOT / p.THRESHOLD_FILE)
    assert p.derive(collected, p.DEFAULT_PACKET) == p.derive(original, p.DEFAULT_PACKET)
    collected.members['KD/owner0/row-1/sample.bf16']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='fixture hash mismatch'):
        p.derive(collected, p.DEFAULT_PACKET)


def test_fault_between_windows_refused():
    evidence = fixture()
    put(evidence, 'WS/kernel-preflight.txt', b'historical Fault response\nnew timestamp: xe engine reset\n')
    with pytest.raises(ValueError, match='fault-line change between windows'):
        p.derive(evidence, p.DEFAULT_PACKET)


def policy(e, records=None):
    value = json.loads((p.ROOT / p.THRESHOLD_FILE).read_bytes())
    if records is not None:
        value['records'] = records
    put(e, 'record-threshold.json', value)
    return value


def next_record(rate=50):
    return dict(reference_submission='submitted49c', threshold_tok_s=rate,
                result=dict(path='experiments/submitted-result.json', sha256='a' * 64))


def test_current_record_file_replaces_historical_floor():
    e = fixture()
    current = policy(e)
    current['records'].append(next_record(52))
    put(e, 'record-threshold.json', current)
    with pytest.raises(ValueError, match='speed at or below 52'):
        p.derive(e, p.DEFAULT_PACKET)
    current['records'][-1]['threshold_tok_s'] = 50
    digest = put(e, 'record-threshold.json', current)
    comparison = p.derive(e, p.DEFAULT_PACKET)['comparison']
    assert comparison['threshold_tok_s'] == 50
    assert comparison['reference_submission'] == 'submitted49c'
    assert comparison['threshold_file_sha256'] == digest


@pytest.mark.parametrize('rate', [float('nan'), float('inf'), -1, True, '50', 39, 39.422009])
def test_bad_or_lowered_threshold_refused(rate):
    value = json.loads((p.ROOT / p.THRESHOLD_FILE).read_bytes())
    value['records'].append(next_record(rate))
    with pytest.raises(ValueError, match='finite and strictly increasing'):
        p.validate_threshold(value)


@pytest.mark.parametrize('change', ['schema', 'empty', 'anchor', 'duplicate', 'missing_result'])
def test_threshold_history_structure_refused(change):
    value = json.loads((p.ROOT / p.THRESHOLD_FILE).read_bytes())
    value['records'].append(next_record())
    if change == 'schema':
        value['schema'] = 'wrong'
    elif change == 'empty':
        value['records'] = []
    elif change == 'anchor':
        value['records'][0]['threshold_tok_s'] -= 1
    elif change == 'duplicate':
        value['records'][-1]['reference_submission'] = p.REFERENCE_RECORD
    else:
        del value['records'][-1]['result']
    with pytest.raises(ValueError):
        p.validate_threshold(value)


def test_threshold_change_between_collect_and_prepare_refused(tmp_path):
    e = fixture()
    value = policy(e)
    path = tmp_path / p.THRESHOLD_FILE
    path.parent.mkdir(parents=True)
    value['records'].append(next_record())
    path.write_bytes(p.encoded(value))
    out = tmp_path / p.STAGE / p.DEFAULT_PACKET / 'submission/prepared'
    with pytest.raises(ValueError, match='changed during preparation'):
        p.write_prepared(e, p.DEFAULT_PACKET, out, tmp_path)
    assert not out.exists()


def d_fixture():
    e = fixture()
    old_seal = e.read('seal.json')
    selection = {'schema': 'packet49d.selection.v1', 'route': 'route-rank4',
                 'recurrence': 'rows4-shared', 'hc': 'mix-vector4'}
    selected = put(e, 'selection.json', selection)
    seal = copy.deepcopy(old_seal)
    seal['runtime_revision'] = '123456789abc'
    seal['device_admission_ready'] = True
    source = str(p.STAGE / p.DEFAULT_PACKET / 'oracle/suite_check.py')
    seal['sources'][str(p.STAGE / p.D_PACKET / 'oracle/suite_check.py')] = seal['sources'][source]
    seal['sources'][str(p.STAGE / p.D_PACKET / 'selection.json')] = selected
    seal_hash = put(e, 'seal.json', seal)
    pin = dict(runtime_revision=seal['runtime_revision'], build_receipt_sha256=seal_hash, selection_sha256=selected)
    put(e, 'submission-pins.json', dict(schema='lab.packet49.submission-pins.v1', lineages={p.D_PACKET: pin}))
    policy(e)
    for name in p.WINDOWS:
        w = e.read(name + '/window.json')
        w['schema'] = 'packet49d.window.v1'
        w['build_receipt_sha256'] = seal_hash
        w['selection_sha256'] = selected
        for leaf in list(w['receipts']):
            if leaf == 'host-reference-identity.json' or leaf in ('owner0/receipt.json', 'owner1/receipt.json') or leaf.endswith(('/rank0/receipt.json', '/rank1/receipt.json')):
                native = e.read(name + '/' + leaf)
                native['selection_sha256'] = selected
                w['receipts'][leaf] = put(e, name + '/' + leaf, native)
        if name == 'WS128':
            w['exactness_companion']['sha256'] = p.sha(e.raw('WS128x/window.json'))
        put(e, name + '/window.json', w)
    return e


def test_packet49d_own_lineage_selection_and_unchanged_oracle():
    e = d_fixture()
    result = p.derive(e, p.D_PACKET)
    assert result['packet'] == p.D_PACKET
    assert result['promotionIdentity']['runtime_revision'] == '123456789abc'
    assert result['exactness']['oracle_arithmetic'] == p.ARITHMETIC
    assert result['comparison']['threshold_file_sha256'] == p.sha(e.raw('record-threshold.json'))
    assert 'packet49d' in result['submission_scope']['authorization_extension']


@pytest.mark.parametrize('change', ['pending', 'selection', 'revision', 'seal', 'missing_threshold'])
def test_packet49d_pin_mutation_refused(change):
    e = d_fixture()
    if change == 'pending':
        pins = e.read('submission-pins.json')
        pins['lineages'][p.D_PACKET] = None
        put(e, 'submission-pins.json', pins)
    elif change == 'selection':
        put(e, 'selection.json', {'route': 'production'})
    elif change == 'missing_threshold':
        del e.members['record-threshold.json']
    else:
        pins = e.read('submission-pins.json')
        pins['lineages'][p.D_PACKET]['runtime_revision' if change == 'revision' else 'build_receipt_sha256'] = '0' * (12 if change == 'revision' else 64)
        put(e, 'submission-pins.json', pins)
    with pytest.raises(ValueError):
        p.derive(e, p.D_PACKET)


def test_fast_reseal_pin_api_binds_final_runtime_and_selection(tmp_path):
    e = d_fixture()
    packet = tmp_path / p.STAGE / p.D_PACKET
    packet.mkdir(parents=True)
    (packet / 'build-receipt.json').write_bytes(e.raw('seal.json'))
    (packet / 'selection.json').write_bytes(e.raw('selection.json'))
    pins = tmp_path / p.PINS_FILE
    pins.parent.mkdir(parents=True)
    pins.write_bytes((p.ROOT / p.PINS_FILE).read_bytes())
    result = p.pin_resealed_packet49d(repo=tmp_path)
    assert result == e.read('submission-pins.json')['lineages'][p.D_PACKET]
    (packet / 'selection.json').write_text('{}')
    with pytest.raises(ValueError, match='not bound'):
        p.pin_resealed_packet49d(repo=tmp_path)


def test_record_update_is_bound_monotonic_and_historical_replay_survives(tmp_path):
    output, _ = prepared(tmp_path)
    path = tmp_path / p.THRESHOLD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((p.ROOT / p.THRESHOLD_FILE).read_bytes())
    old = json.loads((output / 'result.json').read_bytes())
    updated = p.update_record(output / 'result.json', 'submitted49c', repo=tmp_path)
    assert updated['threshold_tok_s'] == pytest.approx(51.25)
    assert updated['result']['sha256'] == p.sha((output / 'result.json').read_bytes())
    p.replay_result(old, tmp_path)
    with pytest.raises(ValueError, match='must improve'):
        p.update_record(output / 'result.json', 'duplicate', repo=tmp_path)


def test_packet49d_prepared_queue_uses_trusted_pin_and_current_threshold(tmp_path):
    e = d_fixture()
    current = e.read('record-threshold.json')
    current['records'].append(next_record(50))
    put(e, 'record-threshold.json', current)
    for leaf, key in [(p.PINS_FILE, 'submission-pins.json'), (p.THRESHOLD_FILE, 'record-threshold.json')]:
        path = tmp_path / leaf
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(e.raw(key))
    out = tmp_path / p.STAGE / p.D_PACKET / 'submission/prepared'
    result = p.write_prepared(e, p.D_PACKET, out, tmp_path)
    item = json.loads((out / 'payload-queue.json').read_bytes())[0]
    assert p.scope_problems(item, tmp_path) == []
    text = (out / 'result-packet.md').read_text()
    assert 'over 50 threshold' in text and '`runtime_revision`' in text
    pins = json.loads((tmp_path / p.PINS_FILE).read_bytes())
    pins['lineages'][p.D_PACKET]['build_receipt_sha256'] = '0' * 64
    (tmp_path / p.PINS_FILE).write_bytes(p.encoded(pins))
    assert p.scope_problems(item, tmp_path)
    # Historical replay uses its original bound pin, not a newly resealed packet.
    assert p.replay_result(result, tmp_path)['packet'] == p.D_PACKET


@pytest.mark.parametrize('location', ['KD/window.json', 'KD/host-reference-identity.json',
                                    'KD/owner0/receipt.json', 'KD/owner1/receipt.json',
                                    'W2m/run/rank0/receipt.json', 'WS/run/ranks/rank1/receipt.json',
                                    'WS128/run/repeat-1/incident-retrospective/receipt.json'])
@pytest.mark.parametrize('missing', [False, True])
def test_packet49d_native_observed_selection_hash_cannot_drift(location, missing):
    e = d_fixture()
    # Per-request pipeline receipts need no duplicate stamp: resident rank
    # teardown receipts bind every request. Any present stamp must still agree.
    if missing and '/repeat-1/' in location:
        return
    native = e.read(location)
    if missing:
        del native['selection_sha256']
    else:
        native['selection_sha256'] = '0' * 64
    changed = put(e, location, native)
    window, relative = location.split('/', 1)
    if relative != 'window.json':
        row = e.read(window + '/window.json')
        row['receipts'][relative] = changed
        put(e, window + '/window.json', row)
    with pytest.raises(ValueError, match='native selection identity mismatch'):
        p.derive(e, p.D_PACKET)

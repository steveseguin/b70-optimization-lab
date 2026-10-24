#!/usr/bin/env python3
"""C62 diagnostic: C61 reviewer with source-assistant reasoning fields omitted.

The sole request change from C61 removes reasoning_content/reasoning fields from
assistant messages inside the quoted source_turns packet. No source message,
content, call, observation, opening, prior note or candidate is removed. This is
an explicitly lossy input projection, not a lossless history algorithm.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import urllib.request

import note_evidence_review_probe as base

EXPECTED_REVIEWER_SHA256 = 'be3e2012681bdde4aaa48bd43ba6d68812358ca70c6eb40918513f3b5724ada0'
SOURCE_MODE = 'assistant-source-reasoning-fields-omitted'
FIELDS = ('reasoning_content', 'reasoning')


def project_request(original):
    request = copy.deepcopy(original)
    packet = json.loads(request['messages'][1]['content'])
    removed = []
    for index, record in enumerate(packet['source_turns']):
        message = record['message']
        if message.get('role') != 'assistant':
            continue
        keys = list(message)
        for field in FIELDS:
            if field not in message:
                continue
            value = message.pop(field)
            removed.append({'source_turn_index': index, 'archive_n': record['archive_n'],
                'field': field, 'message_key_order': keys, 'value_type': type(value).__name__,
                'canonical_value_sha256': base.canonical_sha(value),
                'characters': len(value) if isinstance(value, str) else None,
                'utf8_bytes': len(value.encode()) if isinstance(value, str) else None,
                'text_sha256': hashlib.sha256(value.encode()).hexdigest() if isinstance(value, str) else None})
    request['messages'][1]['content'] = json.dumps(packet, ensure_ascii=False)
    return request, removed


def restore_request(projected, removed, fixture):
    """CPU proof only: recover exact request using fields from the frozen fixture.

Removed text never enters a projected reviewer request or its receipt. Receipts
locate the original field and bind its value and length; source fixtures retain it.
"""
    restored = copy.deepcopy(projected)
    packet = json.loads(restored['messages'][1]['content'])
    orders = {}
    for item in removed:
        index, field = item['source_turn_index'], item['field']
        record = fixture['records'][index]
        assert record['n'] == item['archive_n']
        assert record['message']['role'] == 'assistant' and field in FIELDS
        value = record['message'][field]
        assert base.canonical_sha(value) == item['canonical_value_sha256']
        assert item['characters'] == (len(value) if isinstance(value, str) else None)
        packet['source_turns'][index]['message'][field] = copy.deepcopy(value)
        orders[index] = item['message_key_order']
    for index, keys in orders.items():
        message = packet['source_turns'][index]['message']
        assert set(message) == set(keys)
        packet['source_turns'][index]['message'] = {key: message[key] for key in keys}
    restored['messages'][1]['content'] = json.dumps(packet, ensure_ascii=False)
    return restored


def cpu_checks(selected):
    checks = base.cpu_checks(selected)
    projections = []
    for fixture, candidate, reply in selected:
        original = base.make_request(fixture, candidate, reply, 'cpu-fixture', False)
        projected, removed = project_request(original)
        assert removed, 'registered fixture must exercise the projection'
        assert restore_request(projected, removed, fixture) == original
        expected = json.loads(original['messages'][1]['content'])
        for record in expected['source_turns']:
            if record['message'].get('role') == 'assistant':
                for field in FIELDS:
                    record['message'].pop(field, None)
        actual = json.loads(projected['messages'][1]['content'])
        assert actual == expected
        assert len(actual['source_turns']) == len(fixture['records']) + bool(fixture.get('synthetic_user_message'))
        on, on_removed = project_request(base.make_request(fixture, candidate, reply, 'cpu-fixture', True))
        on['chat_template_kwargs']['enable_thinking'] = False
        assert on == projected and on_removed == removed
        projections.append({'fixture': fixture['id'], 'candidate_thinking': candidate['notes_thinking'],
            'removed_fields': len(removed), 'removed_characters': sum(r['characters'] or 0 for r in removed),
            'original_request_sha256': base.canonical_sha(original),
            'projected_request_sha256': base.canonical_sha(projected), 'inverse_exact': True})
    # Exercise both removable fields, a null value, and identically named user
    # metadata. Only fields on an original source-assistant message may be removed.
    fixture = {'records': [
        {'n': 1, 'message': {'role': 'assistant', 'reasoning': 'private words',
                           'content': 'visible words', 'reasoning_content': None,
                           'tool_calls': [{'id': 'call', 'function': {'name': 'op', 'arguments': '{}'}}]}},
        {'n': 2, 'message': {'role': 'user', 'content': 'instruction', 'reasoning': 'retain this field'}}]}
    packet = {'opening_messages': [{'role': 'assistant', 'reasoning': 'retain opening'}],
              'source_turns': [{'archive_n': r['n'], 'message': r['message']} for r in fixture['records']],
              'prior_notes': 'reasoning: retain prior', 'candidate_delta': 'reasoning: retain candidate',
              'candidate_applied_notes': 'reasoning: retain applied'}
    original = {'messages': [{'role': 'system', 'content': 'review'},
                            {'role': 'user', 'content': json.dumps(packet, ensure_ascii=False)}]}
    projected, removed = project_request(original)
    assert len(removed) == 2 and restore_request(projected, removed, fixture) == original
    assert json.loads(projected['messages'][1]['content'])['source_turns'][1] == packet['source_turns'][1]
    checks['projection_checks'] = projections
    checks['checks'] += ['exact inverse from frozen fields and receipts',
        'projection removes only two named fields from source assistant messages',
        'all messages, IDs, content, tools, opening, prior notes and candidates preserved',
        'both fields/null values and same-named nonassistant metadata tested']
    return checks


def run(args):
    reviewer_path = Path(base.__file__).resolve()
    if base.sha(reviewer_path) != EXPECTED_REVIEWER_SHA256:
        raise ValueError('frozen C61 reviewer changed; refusing a different comparison')
    if args.json.exists():
        raise ValueError('refusing to overwrite an existing result')
    selected = base.load_inputs(args.fixtures, args.candidates)
    checks = cpu_checks(selected)
    model = 'cpu-fixture'
    if not args.cpu_check:
        with urllib.request.urlopen(args.base_url.rstrip('/') + '/models', timeout=15) as stream:
            models = json.load(stream)['data']
        if len(models) != 1:
            raise ValueError('expected exactly one served model')
        model = models[0]['id']
    result = {'schema': 'ctxkeeper.note-evidence-observable-probe.v1', 'complete': False,
              'source_mode': SOURCE_MODE, 'cpu_check': args.cpu_check, 'promotion': False, 'model': model,
              'quality_verdict': 'manual source-grounded review required',
              'scope': 'C61 request with an explicitly lossy source-assistant reasoning projection. No end-to-end, lossless-history or speed claim.',
              'fixtures_manifest_sha256': base.sha(args.fixtures / 'manifest.json'),
              'candidates_sha256': base.sha(args.candidates), 'script_sha256': base.sha(Path(__file__)),
              'reviewer_sha256': base.sha(reviewer_path),
              'notesdelta_sha256': base.sha(base.LAB / 'tools/ctxkeeper/notesdelta.py'),
              'review_system_sha256': hashlib.sha256(base.REVIEW_SYSTEM.encode()).hexdigest(),
              'cpu_checks': checks, 'runs': []}
    base.dump(args.json, result)
    for fixture, candidate, reply in selected:
        for thinking in (False, True):
            original = base.make_request(fixture, candidate, reply, model, thinking)
            request, removed = project_request(original)
            assert restore_request(request, removed, fixture) == original
            row = {'fixture': fixture['id'], 'fixture_kind': fixture['kind'], 'source_mode': SOURCE_MODE,
                   'candidate_repeat': 0, 'candidate_thinking': candidate['notes_thinking'],
                   'candidate_sha256': base.canonical_sha(candidate),
                   'candidate_call_count': len(candidate['calls']),
                   'candidate_finish_reasons': [c['response']['choices'][0].get('finish_reason') for c in candidate['calls']],
                   'reviewer_thinking': thinking, 'original_request_sha256': base.canonical_sha(original),
                   'projected_request_sha256': base.canonical_sha(request),
                   'removed_fields': removed, 'inverse_exact': True, 'request': request, 'response': None}
            started = time.monotonic()
            try:
                if args.cpu_check:
                    response = base.fake_response()
                else:
                    wire = urllib.request.Request(args.base_url.rstrip('/') + '/chat/completions',
                        data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(wire, timeout=180) as stream:
                        response = json.load(stream)
                row.update(response=response, result=base.assess_response(response, fixture['prior_notes']))
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
                row['seconds'] = round(time.monotonic() - started, 3)
                result['runs'].append(row)
                base.dump(args.json, result)
                raise
            row['seconds'] = round(time.monotonic() - started, 3)
            result['runs'].append(row)
            base.dump(args.json, result)
            print(f"{fixture['id']} candidate={candidate['notes_thinking']} reviewer={thinking} "
                  f"removed={len(removed)} valid_layout={row['result']['syntactically_valid']} "
                  f"issues={row['result']['issues']}", flush=True)
    result['complete'] = True  # all conditions attempted; NOT semantic quality success
    result['syntactically_valid_count'] = sum(r['result']['syntactically_valid'] for r in result['runs'])
    base.dump(args.json, result)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fixtures', type=Path, required=True)
    ap.add_argument('--candidates', type=Path, required=True)
    ap.add_argument('--base-url')
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--json', type=Path, required=True)
    ap.add_argument('--cpu-check', action='store_true')
    args = ap.parse_args()
    if args.rounds != 1:
        ap.error('the registered diagnostic has exactly one round (12 conditions)')
    if not args.cpu_check and not args.base_url:
        ap.error('--base-url is required for device calls')
    run(args)


if __name__ == '__main__':
    main()

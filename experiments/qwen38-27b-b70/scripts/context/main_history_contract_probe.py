#!/usr/bin/env python3
"""C65 bounded decisive-turn replay through production Keeper.complete.

The fixture reconstructs a prior call from recorded client input and a later
saved state whose memory cutoff did not change. It is not historical upstream
wire identity. Only archive recall executes; task tools never execute.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]
sys.path.insert(0, str(LAB / 'tools/ctxkeeper'))
import ctxkeeper as ck

BASE = Path('/mnt/fast-ai/bench-results/context-longrun-20261016')
SOURCE_STATE = BASE / 'proxy-state/c64-pi/4051fd73e25016a5'
SOURCE_REQUESTS = BASE / 'runs/c64/pi/jobs/AB-pi__repair-n40-s2x/trial/agent/requests.jsonl'
SPEC = Path('/mnt/fast-ai/bench-results/context-longrun-20261012/client-repair2/tasks/repair-n40-s2x/tests/spec.json')
SESSION = '4051fd73e25016a5'
CUTOFF = 585
REQUEST_INDEX = 289
EXPECTED_PROMPT_TOKENS = 6026
CONTRACT = """
- NOTES are selective memory, not an exhaustive event log. Absence from NOTES does not establish that an event never happened.
- Before producing an exhaustive historical list, use recall to inspect the original evidence for the requested range and verify coverage. Search snippets can omit matches or truncate messages; inspect original messages as needed.
- Historical evidence does not cancel later authorized corrections or changes of instruction."""


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def load(path):
    return json.loads(path.read_text())


def validate_cutoff(state, archive, notes, body):
    h = ck.head_length(ck.one_system_message(body['messages']))
    if h != 2 or state['cut'] + h != CUTOFF or len(body['messages']) != 601:
        raise ValueError('unexpected registered request/cutoff')
    if state['boundary'] != ck.fingerprint(body['messages'][h:CUTOFF]):
        raise ValueError('saved boundary does not match the recorded request')
    numbers = [row['n'] for row in archive]
    if numbers != sorted(set(numbers)) or numbers[-1] != CUTOFF or any(n > CUTOFF for n in numbers):
        raise ValueError('archive contains future, unordered or missing cutoff records')
    if any(row['upto'] > CUTOFF for row in notes) or notes[-1]['upto'] != CUTOFF:
        raise ValueError('notes include a later cutoff')
    if state['notes'] != notes[-1]['notes']:
        raise ValueError('saved state notes differ from last cutoff')
    if any(state.get(key) is not None for key in ('kept_user', 'kept_open', 'carry')):
        raise ValueError('fixture has additional retained/carry material requiring reconstruction')


def new_keeper(ask, root):
    config = dict(ck.RECIPES['qwen'])
    config.update(notes_thinking=True, recall_unit='message', log_calls=True)
    return ck.Keeper(ask, root, **config)


def audit_write(response):
    choices = response.get('choices') or []
    if len(choices) != 1:
        return {'supported': False, 'reason': 'not one completion'}
    if choices[0].get('finish_reason') != 'tool_calls':
        return {'supported': False, 'reason': 'completion did not finish with a complete tool action'}
    calls = (choices[0].get('message') or {}).get('tool_calls') or []
    if len(calls) != 1 or (calls[0].get('function') or {}).get('name') != 'write':
        return {'supported': False, 'reason': 'first external action is not one write call'}
    try:
        args = json.loads(calls[0]['function']['arguments'])
    except (TypeError, ValueError, KeyError):
        return {'supported': False, 'reason': 'invalid write arguments'}
    if args.get('path') != '/app/AUDIT.md' or not isinstance(args.get('content'), str):
        return {'supported': False, 'reason': 'write is not the requested audit artifact'}
    return {'supported': True, 'content': args['content'], 'lines': args['content'].splitlines(),
            'scope': 'proposed tool payload only; no file was written'}


def control_matches(row, original_content):
    first = row['calls'][0] if row.get('calls') else {}
    measured = (first.get('response') or {}).get('usage', {}).get('prompt_tokens')
    return (row.get('write', {}).get('supported') is True
            and row['write']['content'] == original_content
            and row.get('recalls_requested') == 0 and row.get('recalls_served') == 0
            and len(row.get('calls', [])) == 1 and measured == EXPECTED_PROMPT_TOKENS
            and len((first.get('request') or {}).get('messages', [])) == 19)


def run_arm(fixture, arm, ask, expected_first=None):
    body = load(fixture / 'request-body.json')
    manifest = load(fixture / 'manifest.json')
    calls, kinds = [], []
    with tempfile.TemporaryDirectory(prefix='ctx-main-contract-') as temp:
        root = Path(temp)
        session_dir = root / SESSION
        shutil.copytree(fixture / 'state', session_dir)
        initial = load(session_dir / 'state.json')
        archive_hash = sha(session_dir / 'archive.jsonl')
        notes_hash = sha(session_dir / 'notes-history.jsonl')
        old_note = ck.MEMORY_NOTE
        try:
            if arm == 'candidate':
                ck.MEMORY_NOTE = old_note + CONTRACT
            def capture(request):
                if len(calls) >= 34:
                    raise RuntimeError('registered production recall/empty-reply call bound exceeded')
                saved = {'request': copy.deepcopy(request), 'response': None}
                calls.append(saved)
                if len(calls) == 1 and expected_first is not None and request != expected_first:
                    raise RuntimeError('first production request differs from its frozen CPU capture')
                response = ask(request)
                saved['response'] = copy.deepcopy(response)
                return response
            keeper = new_keeper(capture, root)
            upstream = keeper.upstream
            def traced(request, session=None, kind='main'):
                kinds.append(kind)
                if kind != 'main':
                    raise RuntimeError('reconstruction unexpectedly requested new NOTES')
                return upstream(request, session, kind)
            keeper.upstream = traced
            response = keeper.complete(copy.deepcopy(body), manifest.get('session_header'))
            state = keeper.sessions[SESSION].state
            if state['cut'] != initial['cut'] or state['boundary'] != initial['boundary'] or state['notes'] != initial['notes']:
                raise RuntimeError('reconstruction changed the frozen memory cut')
            if state.get('restarts', 0) != initial.get('restarts', 0):
                raise RuntimeError('reconstruction restarted the conversation')
            if sha(session_dir / 'archive.jsonl') != archive_hash or sha(session_dir / 'notes-history.jsonl') != notes_hash:
                raise RuntimeError('reconstruction changed the frozen archive or notes')
            recalled = state['recalls'] - initial['recalls']
            events = [json.loads(line) for line in (session_dir / 'events.jsonl').read_text().splitlines()] if (session_dir / 'events.jsonl').exists() else []
        except BaseException as exc:
            exc.probe_calls = copy.deepcopy(calls)
            exc.probe_kinds = list(kinds)
            raise
        finally:
            ck.MEMORY_NOTE = old_note
    requested = sum((call.get('function') or {}).get('name') == 'recall'
        for row in calls for choice in (row['response'] or {}).get('choices', [])
        for call in (choice.get('message') or {}).get('tool_calls', []))
    write = audit_write(response)
    expected = manifest['expected_lines']
    exact = (write.get('supported') is True and len(write['lines']) == len(expected)
             and set(write['lines']) == set(expected))
    return {'arm': arm, 'calls': calls, 'call_kinds': kinds, 'response': response,
        'recalls_requested': requested, 'recalls_served': recalled, 'events': events,
        'write': write, 'proposed_audit_exact': exact,
        'correct_expected_lines': len(set(write.get('lines', [])) & set(expected)),
        'expected_line_count': len(expected), 'task_tools_executed': 0}


def fake_response():
    return {'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'capture only'}}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0}}


def prepare(out):
    if out.exists():
        raise ValueError('refusing an existing fixture directory')
    selected, following = None, None
    with SOURCE_REQUESTS.open() as stream:
        for line in stream:
            record = json.loads(line)
            if record.get('i') == REQUEST_INDEX:
                selected = record
            if record.get('i') == REQUEST_INDEX + 1:
                following = record
                break
    if selected is None or following is None:
        raise ValueError('registered original request/response not found')
    body = json.loads(selected['body'])
    following_body = json.loads(following['body'])
    if following_body['messages'][:len(body['messages'])] != body['messages']:
        raise ValueError('following request does not extend the selected request')
    observed = following_body['messages'][len(body['messages'])]
    original_response = {'choices': [{'finish_reason': 'tool_calls', 'message': observed}]}
    original_write = audit_write(original_response)
    if original_write.get('lines') != ['6 | time_limited', '7 | numeric_range', '8 | classify_unique']:
        raise ValueError('historical three-line control differs')
    state = load(SOURCE_STATE / 'state.json')
    archive = [json.loads(line) for line in (SOURCE_STATE / 'archive.jsonl').read_text().splitlines()]
    notes = [json.loads(line) for line in (SOURCE_STATE / 'notes-history.jsonl').read_text().splitlines()]
    validate_cutoff(state, archive, notes, body)
    spec = load(SPEC)
    expected = [f"{bug['ticket']} | {bug['func']}" for bug in spec['bugs'] if bug['ticket'] in spec['audit']]
    out.mkdir(parents=True)
    (out / 'request-body.json').write_bytes(selected['body'].encode())
    (out / 'state').mkdir()
    for name in ('state.json', 'archive.jsonl', 'notes-history.jsonl'):
        shutil.copyfile(SOURCE_STATE / name, out / 'state' / name)
    dump(out / 'observed-terminal-message.json', observed)
    dump(out / 'manifest.json', {'schema': 'ctxkeeper.main-history-contract-fixture.v1',
        'scope': 'Reconstructed state capture, not historical upstream HTTP byte identity.',
        'source_request_index': REQUEST_INDEX, 'source_request_path': str(SOURCE_REQUESTS),
        'source_request_file_sha256': sha(SOURCE_REQUESTS), 'source_body_sha256': sha(out / 'request-body.json'),
        'session_header': selected.get('session_header'), 'cutoff': CUTOFF,
        'expected_first_upstream_messages': 19, 'expected_first_prompt_tokens': EXPECTED_PROMPT_TOKENS,
        'expected_lines': expected, 'original_control_content': original_write['content'],
        'score_scope': 'proposed write payload only; full-task quality remains untested',
        'spec_path': str(SPEC), 'spec_sha256': sha(SPEC), 'keeper_sha256': sha(Path(ck.__file__)),
        'source_pins': {str(path): sha(path) for path in
            (SOURCE_REQUESTS, SPEC, SOURCE_STATE / 'state.json', SOURCE_STATE / 'archive.jsonl',
             SOURCE_STATE / 'notes-history.jsonl')},
        'notesdelta_sha256': sha(LAB / 'tools/ctxkeeper/notesdelta.py'), 'contract': CONTRACT,
        'original_memory_note_sha256': hashlib.sha256(ck.MEMORY_NOTE.encode()).hexdigest(),
        'configuration': {'recipe': 'qwen', 'notes_thinking': 'on', 'max_recalls': 16,
                          'recall_unit': 'message', 'transport': 'original production stream=False conversion'},
        'pins': {str(path.relative_to(out)): sha(path) for path in out.rglob('*') if path.is_file()}})
    capture = {}
    for arm in ('control', 'candidate'):
        row = run_arm(out, arm, lambda request: fake_response())
        if len(row['calls']) != 1 or row['call_kinds'] != ['main'] or row['recalls_requested']:
            raise RuntimeError('CPU capture did not take exactly one unchanged main path')
        capture[arm] = row['calls'][0]['request']
    if len(capture['control']['messages']) != 19:
        raise RuntimeError('reconstructed control has a different message count')
    expected_candidate = copy.deepcopy(capture['control'])
    expected_candidate['messages'][0]['content'] += CONTRACT
    if capture['candidate'] != expected_candidate:
        raise RuntimeError('candidate request changes more than the memory contract suffix')
    dump(out / 'cpu-capture.json', capture)
    manifest = load(out / 'manifest.json')
    manifest['pins']['cpu-capture.json'] = sha(out / 'cpu-capture.json')
    manifest['cpu_capture_checks'] = {'main_only': True, 'messages': 19, 'no_cut_restart_recall': True, 'suffix_only_delta': True}
    dump(out / 'manifest.json', manifest)
    print('Prepared exact client body, frozen pre-question memory, and suffix-only production captures.')


def verify_fixture(folder):
    manifest = load(folder / 'manifest.json')
    for name, expected in manifest['source_pins'].items():
        if sha(Path(name)) != expected:
            raise ValueError(f'original source changed: {name}')
    for name, expected in manifest['pins'].items():
        if sha(folder / name) != expected:
            raise ValueError(f'fixture file changed: {name}')
    if manifest['keeper_sha256'] != sha(Path(ck.__file__)) or manifest['notesdelta_sha256'] != sha(LAB / 'tools/ctxkeeper/notesdelta.py'):
        raise ValueError('production keeper changed after capture')
    if manifest['contract'] != CONTRACT or manifest['original_memory_note_sha256'] != hashlib.sha256(ck.MEMORY_NOTE.encode()).hexdigest():
        raise ValueError('memory instructions changed after capture')
    validate_cutoff(load(folder / 'state/state.json'),
        [json.loads(line) for line in (folder / 'state/archive.jsonl').read_text().splitlines()],
        [json.loads(line) for line in (folder / 'state/notes-history.jsonl').read_text().splitlines()],
        load(folder / 'request-body.json'))
    return manifest


def cpu_check(folder, output):
    if output.exists():
        raise ValueError('refusing an existing CPU check result')
    manifest = verify_fixture(folder)
    captured = load(folder / 'cpu-capture.json')
    arms = [run_arm(folder, arm, lambda request: fake_response(), captured[arm])
            for arm in ('control', 'candidate')]
    expected = copy.deepcopy(captured['control'])
    expected['messages'][0]['content'] += CONTRACT
    if captured['candidate'] != expected or any(len(row['calls']) != 1 or row['call_kinds'] != ['main'] for row in arms):
        raise RuntimeError('CPU capture paths or candidate delta differ')
    dump(output, {'complete': True, 'cpu_check': True, 'promotion': False,
        'fixture_manifest_sha256': sha(folder / 'manifest.json'),
        'checks': {'source_hashes': True, 'suffix_only': True, 'one_main_call_each': True,
                   'no_cut_restart_recall': True, 'messages': 19},
        'scope': manifest['scope']})


def run(args):
    if args.json.exists():
        raise ValueError('refusing an existing result')
    manifest = verify_fixture(args.fixture)
    captured = load(args.fixture / 'cpu-capture.json')
    result = {'schema': 'ctxkeeper.main-history-contract-probe.v1', 'complete': False, 'cpu_check': False, 'promotion': False,
        'fixture_manifest_sha256': sha(args.fixture / 'manifest.json'), 'script_sha256': sha(Path(__file__)),
        'scope': manifest['scope'], 'quality_verdict': 'manual source review; proposed payloads, not executed task results',
        'arms': []}
    dump(args.json, result)
    def ask(request):
        wire = urllib.request.Request(args.base_url.rstrip('/') + '/chat/completions',
            data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(wire, timeout=600) as stream:
            return json.load(stream)
    for arm in ('control', 'candidate'):
        started = time.monotonic()
        try:
            row = run_arm(args.fixture, arm, ask, captured[arm])
        except BaseException as exc:
            result.update(error=f'{type(exc).__name__}: {exc}', failed_arm=arm,
                          failed_arm_calls=getattr(exc, 'probe_calls', []), failed_arm_kinds=getattr(exc, 'probe_kinds', []))
            dump(args.json, result)
            raise
        row['seconds'] = round(time.monotonic() - started, 3)
        result['arms'].append(row)
        if arm == 'control':
            result['control_matched'] = control_matches(row, manifest['original_control_content'])
            if not result['control_matched']:
                result.update(complete=True, candidate_skipped=True,
                              decision='inconclusive: reconstructed control did not reproduce original behavior')
                dump(args.json, result)
                return
        else:
            result['candidate_proposal_screen_pass'] = row['proposed_audit_exact'] and row['recalls_served'] > 0
            result['source_evidence_pass'] = None
            result['source_evidence_review'] = 'Manual audit must verify original retrieved receipts cover all requested entries; any recall alone is insufficient.'
        dump(args.json, result)
        print(f"{arm}: proposed_correct={row['correct_expected_lines']}/7 recalls={row['recalls_served']}", flush=True)
    result['complete'] = True
    result['decision'] = 'source coverage audit required before full-task test' if result['candidate_proposal_screen_pass'] else 'candidate did not pass the bounded screen'
    dump(args.json, result)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare', type=Path)
    ap.add_argument('--fixture', type=Path)
    ap.add_argument('--base-url')
    ap.add_argument('--rounds', type=int, default=1)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--cpu-check', action='store_true')
    args = ap.parse_args()
    if args.prepare:
        prepare(args.prepare)
    elif args.cpu_check and args.fixture and args.json and args.rounds == 1:
        cpu_check(args.fixture, args.json)
    elif args.fixture and args.base_url and args.json and args.rounds == 1:
        run(args)
    else:
        ap.error('choose --prepare DIR or --fixture DIR --base-url URL --rounds 1 --json FILE')


if __name__ == '__main__':
    main()

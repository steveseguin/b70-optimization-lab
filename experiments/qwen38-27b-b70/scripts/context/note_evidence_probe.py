#!/usr/bin/env python3
"""Small source-evidence diagnostic from campaign 20's pi failure; no tools execute.

--extract DIR freezes two recorded cuts and one explicitly synthetic cancellation.
--check DIR checks fixture provenance/observations without contacting a model.
--fixtures DIR --base-url URL --json FILE runs current notes code with thinking
off/on. Completion is not a quality verdict; outputs need source-grounded review.
These reconstructed notes requests are not the original recorded HTTP requests.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[3]
RAW = Path('/mnt/fast-ai/bench-results/context-longrun-20261012/c20b')
SESSION = RAW / 'proxy-state/AB-pi__repair-n40-s2x/4051fd73e25016a5'
REQUESTS = RAW / 'runs/jobs/AB-pi__repair-n40-s2x/trial/agent/requests.jsonl'


def rows(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def extract(out):
    if out.exists():
        raise ValueError(f'refusing existing fixture directory {out}')
    # Only the first HTTP record is needed: the original system/task and tools.
    # Full conversation records are streamed from the much smaller archive.
    first = next(rows(REQUESTS))
    body = json.loads(first['body'])
    versions = list(rows(SESSION / 'notes-history.jsonl'))
    archive = list(rows(SESSION / 'archive.jsonl'))
    assert len(versions) == 9 and versions[-1]['upto'] == 502
    fixtures = []
    for number, label in [(8, 'pi-preceding-cut'), (9, 'pi-observed-audit')]:
        prev, current = versions[number - 2], versions[number - 1]
        selected = [r for r in archive if prev['upto'] < r['n'] <= current['upto']]
        assert [r['n'] for r in selected] == list(range(prev['upto'] + 1, current['upto'] + 1))
        fixtures.append({'id': label, 'kind': 'recorded-cut', 'version': number,
            'prior_upto': prev['upto'], 'upto': current['upto'], 'prior_notes': prev['notes'],
            'historical_notes': current['notes'], 'opening': body['messages'],
            'tools': body['tools'], 'records': selected,
            'scope': 'Recorded source messages and prior NOTES; current 1.3.0 request reconstruction, not original wire replay.'})
    cancelled = copy.deepcopy(fixtures[-1])
    cancelled.update(id='pi-explicit-cancellation', kind='synthetic-counterfactual',
        synthetic_user_message='The audit ticket is withdrawn. Remove /app/AUDIT.md. Keep the completed library fixes and the other required records.',
        scope='Counterfactual: append one explicit user instruction to the recorded cut. Tests legitimate supersession; not a historical result.')
    fixtures.append(cancelled)
    out.mkdir(parents=True)
    for fixture in fixtures:
        dump(out / (fixture['id'] + '.json'), fixture)
    paths = [SESSION / name for name in ('archive.jsonl', 'notes-history.jsonl', 'events.jsonl')]
    dump(out / 'manifest.json', {'schema': 'ctxkeeper.note-evidence-fixtures.v1',
        'fixtures': [{'file': f['id'] + '.json', 'sha256': sha(out / (f['id'] + '.json'))} for f in fixtures],
        'sources': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in paths],
        'opening_source': {'path': str(REQUESTS), 'record': first['i'],
                           'body_sha256': hashlib.sha256(first['body'].encode()).hexdigest()},
        'review_rubric': [
            'Recorded failure: ticket 43 and ticket 44 were delivered; AUDIT.md was requested and written.',
            'Do not turn the assistant\'s later contrary speculation into an observed fact.',
            'No invented cleanup instruction; distinguish an executed tool operation from a proposal.',
            'Counterfactual: honor explicit user withdrawal; do not invent a blanket ban on deleting audit files.',
            'Preceding cut: retain its source-supported task state and standing rules.',
            'Review every new STATE and OPEN claim against source, not just the named audit failure.',
        ]})
    check(out)


def load(out):
    manifest = json.loads((out / 'manifest.json').read_text())
    fixtures = []
    for row in manifest['fixtures']:
        path = out / row['file']
        if sha(path) != row['sha256']:
            raise ValueError(f'fixture hash mismatch: {path}')
        fixtures.append(json.loads(path.read_text()))
    if len(fixtures) != 3:
        raise ValueError('expected exactly three registered fixtures')
    return fixtures


def check(out):
    fixtures = load(out)
    for fixture in fixtures:
        pending = set()
        for record in fixture['records']:
            message = record['message']
            pending.update(call['id'] for call in message.get('tool_calls', []))
            if message['role'] == 'tool':
                assert message['tool_call_id'] in pending, (fixture['id'], record['n'])
                pending.remove(message['tool_call_id'])
        assert not pending, (fixture['id'], pending)
    observed = next(f for f in fixtures if f['id'] == 'pi-observed-audit')
    tools = '\n'.join(r['text'] for r in observed['records'] if r['role'] == 'tool')
    assert 'TICKET 43/44 (BUG)' in tools and 'TICKET 44/44 (AUDIT)' in tools
    assert 'Successfully wrote to /app/AUDIT.md' in tools
    assert 'consider removing' in observed['historical_notes']
    assert 'no AUDIT ticket' in observed['historical_notes']
    counterfactual = next(f for f in fixtures if f['kind'] == 'synthetic-counterfactual')
    assert counterfactual['records'] == observed['records']
    assert counterfactual['prior_notes'] == observed['prior_notes']
    assert counterfactual['synthetic_user_message'].startswith('The audit ticket is withdrawn.')
    print('PASS: source observations, historical contradiction, distinct cancellation control, fixture hashes')


def run(args):
    sys.path.insert(0, str(LAB / 'tools/ctxkeeper'))
    import ctxkeeper as ck
    fixtures = load(args.fixtures)
    target = args.base_url.rstrip('/') + '/chat/completions'
    model = 'cpu-fixture'
    if not args.cpu_check:
        with urllib.request.urlopen(args.base_url.rstrip('/') + '/models', timeout=15) as stream:
            served = json.load(stream)['data']
        if len(served) != 1:
            raise RuntimeError('expected exactly one served model')
        model = served[0]['id']
    result = {'schema': 'ctxkeeper.note-evidence-probe.v1', 'quality_verdict': 'manual review required',
              'promotion': False, 'scope': 'Reconstructed recorded cuts, one synthetic control; no end-to-end or speed claim.',
              'model': model,
              'fixtures_manifest_sha256': sha(args.fixtures / 'manifest.json'),
              'keeper_sha256': sha(LAB / 'tools/ctxkeeper/ctxkeeper.py'), 'runs': []}
    dump(args.json, result)
    for repeat in range(args.rounds):
        # Alternate order; cached calls are diagnostic only, never a speed result.
        modes = [False, True] if repeat % 2 == 0 else [True, False]
        for fixture in fixtures:
            for thinking in modes:
                calls = []
                def ask(body):
                    if args.cpu_check:
                        response = {'choices': [{'message': {'content': 'NEW RULES\n(none)\nCHANGES\n(none)\nOPEN\n'}}],
                                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
                    else:
                        req = urllib.request.Request(target, data=json.dumps(body).encode(),
                            headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=180) as stream:
                            response = json.load(stream)
                    calls.append({'request': body, 'response': response})
                    return response
                with tempfile.TemporaryDirectory(prefix='ctx-note-evidence-') as temp:
                    keeper = ck.Keeper(ask, Path(temp), notes_mode='inplace', notes_thinking=thinking,
                        notes_checks='off', effort='medium', notes_cap=2048, notes_max_tokens=8192)
                    session = ck.Session(Path(temp), 'probe')
                    opening = ck.one_system_message(copy.deepcopy(fixture['opening']))
                    opening = ck.with_memory_note(opening)
                    h = ck.head_length(opening)
                    session.state.update(cut=fixture['prior_upto'] - h, notes=fixture['prior_notes'])
                    noted = [r['message'] for r in fixture['records']]
                    if fixture.get('synthetic_user_message'):
                        noted = noted + [{'role': 'user', 'content': fixture['synthetic_user_message']}]
                    client = {'tools': fixture['tools']}
                    req, tools = keeper.inplace_request(session, opening, h, noted, client)
                    started = time.monotonic()
                    computed = keeper.inplace_compute(session, model, req, tools, client, noted, fixture['prior_notes'])
                row = {'fixture': fixture['id'], 'repeat': repeat, 'notes_thinking': thinking,
                       'seconds': round(time.monotonic() - started, 3), 'result': computed, 'calls': calls}
                result['runs'].append(row)
                dump(args.json, result)
                print(f"{fixture['id']} repeat={repeat} thinking={thinking} calls={len(calls)} why={computed['why']!r}", flush=True)
                if not calls or computed['why']:
                    raise RuntimeError('notes call failed; stop instead of hiding a failed diagnostic')
    result['complete'] = True
    result['cpu_check'] = args.cpu_check
    dump(args.json, result)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extract', type=Path)
    ap.add_argument('--check', type=Path)
    ap.add_argument('--fixtures', type=Path)
    ap.add_argument('--base-url')
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--cpu-check', action='store_true')
    args = ap.parse_args()
    if args.extract:
        extract(args.extract)
    elif args.check:
        check(args.check)
    elif args.fixtures and args.json and (args.base_url or args.cpu_check):
        args.base_url = args.base_url or 'http://unused.invalid/v1'
        run(args)
    else:
        ap.error('choose --extract DIR, --check DIR, or --fixtures DIR --base-url URL --json FILE')


if __name__ == '__main__':
    main()

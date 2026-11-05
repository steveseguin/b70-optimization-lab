#!/usr/bin/env python3
"""Bounded ctxkeeper policy test over an existing plain endpoint; --run opts into inference.

Uses synthetic tool logs only. This qualifies notes/cut/recall behavior, not native
checkpointing, streaming, broad coding quality, or lossless full-history recall.
"""
import argparse
import copy
import importlib.util
import json
import re
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[1]
REPO = RUNTIME.parents[1]
MODEL = 'sc117-qwen3.8-flash-next-iq3s-ownrt'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


class Halt(BaseException):
    """Cannot be swallowed by ctxkeeper's recoverable notes-error handling."""


class Upstream:
    def __init__(self, url, output, max_calls=12, timeout=300, run_seconds=1800,
                 opener=urllib.request.urlopen, clock=time.monotonic):
        self.url, self.output = url.rstrip('/') + '/v1/chat/completions', Path(output)
        self.max_calls, self.timeout, self.clock = max_calls, timeout, clock
        self.deadline, self.opener = clock() + run_seconds, opener
        self.rows, self.failed = [], None

    def __call__(self, body):
        if self.failed:
            raise Halt(self.failed)
        remaining = self.deadline - self.clock()
        if len(self.rows) >= self.max_calls or remaining <= 0:
            self.failed = 'qualification call/time budget exhausted'
            raise Halt(self.failed)
        start = self.clock()
        request = copy.deepcopy(body)
        request['model'], request['stream'] = MODEL, False
        request.pop('stream_options', None)
        row = dict(call=len(self.rows) + 1, request=request)
        self.rows.append(row)
        try:
            wire = urllib.request.Request(self.url, data=json.dumps(request).encode(),
                                          headers={'Content-Type': 'application/json'})
            with self.opener(wire, timeout=min(self.timeout, remaining)) as response:
                result = json.loads(response.read())
            if not isinstance(result, dict) or result.get('error') or not result.get('choices'):
                raise ValueError('upstream response has no usable completion: ' + str(result)[:300])
            row.update(response=result, usage=result.get('usage', {}), ownrt=result.get('ownrt', {}))
            return result
        except BaseException as error:
            self.failed = f'first upstream failure: {type(error).__name__}: {error}'
            row['error'] = self.failed
            raise Halt(self.failed) from error
        finally:
            row['wall_s'] = self.clock() - start
            with (self.output / 'upstream.jsonl').open('a') as f:
                f.write(json.dumps(row) + '\n')


def message(response):
    return response['choices'][0]['message']


def checksum_ok(response, checksum):
    return bool(re.search(r'(?<!\d)' + re.escape(checksum) + r'(?!\d)', message(response).get('content') or ''))


def secondary_fact(archive, notes):
    """Select a routine archived fact absent from current notes; never seed the answer in the question."""
    for row in archive:
        for line in row.get('text', '').splitlines():
            found = re.fullmatch(r'(\S+) host=(\S+) job=(\S+) status=ok duration=\S+ checksum=(\d+)', line)
            if found and found[4] not in notes and found[3] != 'kappa-17':
                return dict(timestamp=found[1], host=found[2], job=found[3], checksum=found[4],
                            archived_message=row['n'], record=line)
    return None


def report_checks(turns, state, archive, primary, secondary):
    leaked = any(any((c.get('function') or {}).get('name') == 'recall'
                     for c in message(t['response']).get('tool_calls') or []) for t in turns)
    return dict(cut_happened=state.get('cuts', 0) > 0,
                archive_has_primary=any('48151623' in r.get('text', '') for r in archive),
                primary_checksum_retained=primary.get('correct', False),
                secondary_archived_fact_available=secondary.get('fact') is not None,
                instructed_recall_used=secondary.get('recall_delta', 0) > 0,
                secondary_checksum_recalled=secondary.get('correct', False),
                no_internal_recall_leak=not leaked,
                valid_finish_reasons=all(t['response']['choices'][0].get('finish_reason') in
                                        ('stop', 'length', 'tool_calls') for t in turns))


def qualify(args, output):
    ck = load(REPO / 'tools/ctxkeeper/ctxkeeper.py', 'keeper_policy_library')
    fixture = load(RUNTIME / 'gsq-rco-iq3s/serving/lan/keeper_device_test.py', 'keeper_policy_fixture')
    upstream = Upstream(args.url, output, args.max_calls, args.timeout, args.run_seconds)
    policy = dict(budget=args.budget, reply_reserve=1024, headroom=1024, target_ratio=0.6,
                  notes_mode='inplace', inplace_tokens=8192, inplace_fit=True,
                  notes_max_tokens=2048, notes_thinking=False, effort='medium',
                  max_recalls=2, empty_retry=False, notes_async=None, log_calls=True)
    keeper = ck.Keeper(upstream, output / 'state', **policy)
    session_id = 'keeper-policy-smoke'
    messages = [dict(role='system', content='Review deployment logs. Track failed jobs and their reasons. '
                     'The logs below were obtained by read_log. Give a brief status after each part; '
                     'do not call read_log yourself. Use the archive when old facts are needed.'),
                dict(role='user', content=fixture.TASK)]
    turns, primary, secondary = [], {}, {}
    summary = dict(schema='ownrt.keeper-policy-smoke.v1', policy=policy, endpoint=args.url,
                   scope='policy over plain HTTP; no native keeper/checkpoint/streaming qualification',
                   client_turns=turns, passed=False)

    def ask(kind, max_tokens=256, tool_choice='none'):
        body = dict(model=MODEL, messages=copy.deepcopy(messages), tools=fixture.TOOLS,
                    tool_choice=tool_choice, max_tokens=max_tokens,
                    chat_template_kwargs={'enable_thinking': False, 'reasoning_effort': 'medium'})
        start = time.monotonic()
        result = keeper.complete(body, session_id)
        session = keeper.sessions[session_id]
        turns.append(dict(kind=kind, response=result, wall_s=time.monotonic() - start,
                          state=copy.deepcopy(session.state), upstream_calls=len(upstream.rows)))
        write(output / 'turns.json', turns)
        messages.append(message(result))
        return result, session

    try:
        for part in range(1, args.parts + 1):
            call = f'fixture-log-{part}'
            messages.extend([dict(role='assistant', content=None, tool_calls=[dict(id=call, type='function',
                function=dict(name='read_log', arguments=json.dumps({'part': part})))]),
                dict(role='tool', tool_call_id=call, content=fixture.log_part(part))])
            _, session = ask(f'log-{part}')
        before = session.state.get('recalls', 0)
        messages.append(dict(role='user', content=f'What checksum did job {fixture.FACT_JOB} print in log part 1? '
                             'Reply with the checksum digits only.'))
        result, session = ask('primary-retention', 512, 'auto')
        primary = dict(correct=checksum_ok(result, fixture.FACT_SUM),
                       natural_recall_delta=session.state.get('recalls', 0) - before,
                       checksum_in_notes=fixture.FACT_SUM in session.state.get('notes', ''))
        archive = [json.loads(line) for line in session.archive.path.read_text().splitlines()] if session.archive.path.exists() else []
        fact = secondary_fact(archive, session.state.get('notes', ''))
        secondary = dict(fact=fact)
        if fact is not None:
            before = session.state.get('recalls', 0)
            messages.append(dict(role='user', content=f'Search the archive with recall for the exact record at '
                f'{fact["timestamp"]}, host={fact["host"]}, job={fact["job"]}. What checksum did it print? '
                'The record is archived and its checksum is absent from the current notes. Reply with digits only.'))
            result, session = ask('instructed-archive-recall', 512, 'auto')
            secondary.update(correct=checksum_ok(result, fact['checksum']),
                             recall_delta=session.state.get('recalls', 0) - before)
        checks = report_checks(turns, session.state, archive, primary, secondary)
        summary.update(checks=checks, passed=all(checks.values()), state=copy.deepcopy(session.state))
    except BaseException as error:
        summary['error'] = f'{type(error).__name__}: {error}'
    finally:
        summary.update(primary=primary, secondary=secondary, upstream_calls=len(upstream.rows),
                       upstream_failure=upstream.failed, retries=0,
                       usage=[r.get('usage', {}) for r in upstream.rows],
                       budget_observations=[dict(call=r['call'], prompt_tokens=r.get('usage', {}).get('prompt_tokens'),
                           requested_tokens=r['request'].get('max_tokens'),
                           exceeds_nominal_budget=(r.get('usage', {}).get('prompt_tokens', 0) +
                               r['request'].get('max_tokens', 0) > args.budget)) for r in upstream.rows],
                       notes_quality_warning='Small checksum test only; historical Pi keeper runs lost answers in summaries.')
        write(output / 'summary.json', summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true', help='explicitly permit bounded inference requests')
    p.add_argument('--url', default='http://127.0.0.1:18160')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--budget', type=int, default=16384)
    p.add_argument('--parts', type=int, default=5)
    p.add_argument('--max-calls', type=int, default=12)
    p.add_argument('--timeout', type=float, default=300)
    p.add_argument('--run-seconds', type=float, default=1800)
    a = p.parse_args()
    if not 8192 <= a.budget <= 32768 or not 3 <= a.parts <= 8 or not 1 <= a.max_calls <= 20:
        p.error('budget 8192..32768, parts 3..8, max-calls 1..20 required')
    if not 0 < a.timeout <= 600 or not 0 < a.run_seconds <= 3600:
        p.error('bounded positive timeout <=600 and run-seconds <=3600 required')
    out = a.output.absolute()
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        p.error('fresh output under an existing persistent parent required')
    if any(out.is_relative_to(x) for x in (Path('/dev/shm'), Path('/tmp'), Path('/run'))):
        p.error('use persistent output storage')
    if not a.run:
        print(json.dumps(dict(run=False, requests=0, output=str(out), budget=a.budget,
                              max_calls=a.max_calls, parts=a.parts), indent=2))
        return
    out.mkdir(mode=0o700)
    write(out / 'intent.json', {**vars(a), 'output': str(out)})
    result = qualify(a, out)
    print(json.dumps({k: result.get(k) for k in ('passed', 'checks', 'upstream_calls', 'error')}, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()

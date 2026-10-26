#!/usr/bin/env python3
"""Client-side device test of the keeper model (SC117_KEEPER=1) against the running LAN service. HTTP only.

An agent-style conversation through `<MODEL_ID>-keeper`: the client offers one tool, read_log(part), answers each call
with a long synthetic deployment log (about 3.7K tokens), and keeps going until the conversation has gone through at
least one cut (default: 9 parts, about 33K tokens of tool output; about 10-15 minutes at ~100 prompt tokens/s). Part 1 holds one unremarkable line, a checksum for
job kappa-17. Then it asks for that checksum: it is in the archive only, so the keeper must answer it with an internal
`recall` round. Every response is checked for leaks of the internal tool; half of the requests stream.

Checks (all must hold):
  cut_happened              the keeper cut the view at least once (ownrt.keeper.state.cuts)
  head_parked_and_pinned    a split read parked the head checkpoint (event parked), later calls found it (pinned)
  cut_restores_head         the first main call after each cut restored the head and read only the rest
                            (cached_tokens == head tokens, session.restored.position == head tokens)
  notes_continue_live_state every post-reply notes call continued the live state (cached_tokens > 0, no restore)
  turns_continue            between cuts, each request continued the previous one (cached_tokens > 0)
  recall_answer_correct     the answer holds the part-1 checksum, and the keeper made at least one recall round
  no_internal_recall        no response (JSON or SSE) carries a `recall` call or <tool_call> text
  finish_reasons_valid      every finish_reason is stop, length or tool_calls
Per request it prints the final call's cached_tokens and, for each internal call, cached / read tokens and the prompt
read seconds (prompt_wall_ms), so the cost of a cut and a restore is visible.

  python3 -B keeper_device_test.py [--url http://127.0.0.1:18160] [--parts 9] [--exactness]

--exactness also sends the final question once more with sc117_reuse=false (every call reads its prompt fresh, about
3 minutes per call at 20K tokens) and requires the same answer. No GPU access from this script; it reads the API key
file only to send it.
"""
import argparse, http.client, json, random, sys, time, urllib.parse, uuid
from pathlib import Path

MODEL_ID = 'sc117-qwen3.8-flash-next-iq3s-ownrt-keeper'
SYSTEM = ('You are an operations assistant. You review deployment logs for the release of build 7.4 and keep a record '
          'of every job that FAILED, with its host and the reason. Read the logs with the read_log tool, one part per '
          'call, in order, starting at part 1. After each part, write one short line on what failed in it (or "no '
          'failures"), then call read_log for the next part. Do not read a part twice.')
TASK = 'Review the deployment logs of build 7.4, part by part, and keep track of the failures.'
TOOLS = [{'type': 'function', 'function': {
    'name': 'read_log', 'description': 'Read one part of the build 7.4 deployment log.',
    'parameters': {'type': 'object', 'properties': {'part': {'type': 'integer', 'description': 'part number, from 1'}},
                   'required': ['part']}}}]
FACT_JOB, FACT_SUM = 'kappa-17', '48151623'
QUESTION = (f'Question, separate from the review: what checksum did job {FACT_JOB} print in log part 1? It is no longer '
            'in view; search the archive for it. Reply with the checksum digits only.')
JOBS = ['alpha', 'bravo', 'delta', 'gamma', 'omega', 'sigma', 'theta', 'zeta', 'lambda', 'rho']


def log_part(k, lines=70, seed=7):
    """A deterministic synthetic log part: routine ok jobs, one FAILED job; part 1 also holds the kappa-17 line."""
    rng = random.Random(seed * 1000 + k)
    out = [f'=== build 7.4 deployment log, part {k} ===']
    fail_at, fact_at = rng.randrange(lines), rng.randrange(lines)
    for i in range(lines):
        t = f'2026-10-26T{4 + k:02d}:{i // 2:02d}:{(i * 37) % 60:02d}Z'
        if k == 1 and i == fact_at:
            out.append(f'{t} host=web-{rng.randrange(40)} job={FACT_JOB} status=ok duration=8.1s checksum={FACT_SUM}')
        elif i == fail_at:
            out.append(f'{t} host=db-{rng.randrange(9)} job=migrate-{k}{rng.randrange(10)} status=FAILED '
                       f'reason="{rng.choice(["lock timeout", "disk full", "schema mismatch", "connection reset"])}"')
        else:
            out.append(f'{t} host=web-{rng.randrange(40)} job={rng.choice(JOBS)}-{rng.randrange(100)} status=ok '
                       f'duration={rng.randrange(10, 600) / 10}s checksum={rng.randrange(10**7, 10**8)}')
    return '\n'.join(out)


class Client:
    def __init__(self, url, key, session):
        self.url, self.key, self.session = urllib.parse.urlparse(url), key, session

    def post(self, body, stream):
        c = http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=7200)
        headers = {'Content-Type': 'application/json', 'x-session-affinity': self.session}
        if self.key:
            headers['Authorization'] = 'Bearer ' + self.key
        t0 = time.monotonic()
        c.request('POST', '/v1/chat/completions', json.dumps(dict(body, stream=stream)), headers)
        r = c.getresponse()
        raw = r.read().decode()
        wall = time.monotonic() - t0
        if r.status != 200:
            raise SystemExit(f'HTTP {r.status}: {raw[:600]}')
        if not stream:
            return json.loads(raw), raw, wall, 0
        # Rebuild the completion from the SSE events; keep the raw text for the leak check.
        msg, finish, usage, keeper, rid = {'role': 'assistant', 'content': None}, None, None, None, None
        for line in raw.splitlines():
            if not line.startswith('data: {'):
                continue
            ev = json.loads(line[6:])
            if 'error' in ev:
                raise SystemExit('stream error: ' + json.dumps(ev['error']))
            rid = ev.get('id', rid)
            usage = ev.get('usage') or usage
            keeper = ev.get('ownrt') or keeper
            for ch in ev.get('choices') or []:
                d = ch.get('delta') or {}
                for f in ('content', 'reasoning_content'):
                    if d.get(f):
                        msg[f] = (msg.get(f) or '') + d[f]
                if d.get('tool_calls'):
                    msg['tool_calls'] = [{k: v for k, v in c.items() if k != 'index'} for c in d['tool_calls']]
                finish = ch.get('finish_reason') or finish
        resp = {'id': rid, 'choices': [{'message': msg, 'finish_reason': finish}], 'usage': usage, 'ownrt': {'keeper': keeper}}
        return resp, raw, wall, raw.count(': keeper\n')

    def get(self, path):
        c = http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=60)
        c.request('GET', path, headers={'Authorization': 'Bearer ' + self.key} if self.key else {})
        r = c.getresponse()
        return r.status, json.loads(r.read() or b'{}')


def leaks(resp, raw):
    msg = resp['choices'][0]['message']
    names = [((c.get('function') or {}).get('name')) for c in msg.get('tool_calls') or []]
    text = (msg.get('content') or '') + (msg.get('reasoning_content') or '')
    return 'recall' in names or '<tool_call>' in text or '"name": "recall"' in raw or '<function=recall>' in raw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default='http://127.0.0.1:18160')
    ap.add_argument('--key-file', default='/home/steve/.config/sc117-lan/api_key')
    ap.add_argument('--parts', type=int, default=9, help='log parts to read (about 3.7K tokens each)')
    ap.add_argument('--max-tokens', type=int, default=1024)
    ap.add_argument('--exactness', action='store_true', help='repeat the question with sc117_reuse=false and compare')
    ap.add_argument('--out', help='write the full report as JSON here')
    a = ap.parse_args()
    key_path = Path(a.key_file)
    client = Client(a.url, key_path.read_text().strip() if key_path.exists() else None, 'keeper-device-' + uuid.uuid4().hex[:12])
    status, models = client.get('/v1/models')
    if MODEL_ID not in [m['id'] for m in models.get('data', [])]:
        raise SystemExit(f'{MODEL_ID} is not served (start the unit with SC117_KEEPER=1): {models}')
    report = dict(session=client.session, health_before=client.get('/health')[1], requests=[])
    msgs = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': TASK}]
    sent, n, recalls_before_question = 0, 0, None

    def ask(kind, max_tokens, **extra):
        nonlocal n
        n += 1
        stream = n % 2 == 0                                   # every other request streams (keepalives, SSE shape)
        body = dict({'model': MODEL_ID, 'messages': msgs, 'tools': TOOLS, 'max_completion_tokens': max_tokens,
                     'stream_options': {'include_usage': True}}, **extra)
        resp, raw, wall, keepalives = client.post(body, stream)
        k = (resp.get('ownrt') or {}).get('keeper') or {}
        row = dict(n=n, kind=kind, stream=stream, wall_s=round(wall, 2), keepalives=keepalives,
                   finish=resp['choices'][0]['finish_reason'], prompt_tokens=(resp.get('usage') or {}).get('prompt_tokens'),
                   cached_tokens=((resp.get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens'),
                   leak=leaks(resp, raw), state=k.get('state'), head=k.get('head'),
                   calls=k.get('calls') or [], previous_post_reply=k.get('previous_post_reply') or [])
        report['requests'].append(row)
        calls = ' '.join(f"{c['kind']}:{c['cached_tokens']}+{c['read_tokens']}r/{(c.get('prompt_wall_ms') or 0) / 1000:.1f}s"
                         + ('[restored]' if (c.get('session') or {}).get('restored') else '')
                         + (f"[head {c['head']['event']}]" if c.get('head') else '') for c in row['calls'])
        post = ' '.join(f"notes:{c['cached_tokens']}+{c['read_tokens']}r/{(c.get('prompt_wall_ms') or 0) / 1000:.1f}s"
                        for c in row['previous_post_reply'])
        print(f"{n:3d} {kind:8s} {'sse' if stream else 'json'} {wall:7.1f}s prompt={row['prompt_tokens']} "
              f"cached={row['cached_tokens']} cuts={(row['state'] or {}).get('cuts')} | {calls}" + (f' | before: {post}' if post else ''),
              flush=True)
        return resp

    resp = ask('start', a.max_tokens)
    while sent < a.parts:
        msg = resp['choices'][0]['message']
        msgs.append(msg)
        calls = [c for c in msg.get('tool_calls') or [] if (c.get('function') or {}).get('name') == 'read_log']
        sent += 1
        if calls:   # answer the model's read_log call with the next unread part (pi-style tool result)
            msgs.append({'role': 'tool', 'tool_call_id': calls[0].get('id'), 'content': log_part(sent)})
            kind = 'tool'
        else:       # the model replied in text: send the next part as a user message
            msgs.append({'role': 'user', 'content': f'Here is log part {sent}:\n' + log_part(sent)})
            kind = 'user'
        resp = ask(kind, a.max_tokens)
    msgs.append(resp['choices'][0]['message'])
    recalls_before_question = (report['requests'][-1]['state'] or {}).get('recalls') or 0
    msgs.append({'role': 'user', 'content': QUESTION})
    final = ask('question', 512)
    answer = final['choices'][0]['message'].get('content') or ''
    report['answer'] = answer
    rows = report['requests']
    if a.exactness:
        again, raw, wall, _ = client.post({'model': MODEL_ID, 'messages': msgs, 'tools': TOOLS, 'max_completion_tokens': 512,
                                           'sc117_reuse': False}, False)
        report['exactness'] = dict(answer=again['choices'][0]['message'].get('content'), wall_s=round(wall, 1))
        print(f'fresh-read answer: {report["exactness"]["answer"]!r} ({wall:.0f} s)')

    # ---- checks
    checks = {}
    cuts = [(r['state'] or {}).get('cuts') or 0 for r in rows]
    checks['cut_happened'] = cuts[-1] >= 1
    heads = [c['head'] for r in rows for c in r['calls'] if c.get('head')]
    head_tokens = next((h['tokens'] for h in heads if h['event'] == 'parked'), None)
    checks['head_parked_and_pinned'] = head_tokens is not None and any(h['event'] == 'pinned' for h in heads)
    after_cut = [r for prev, r in zip(rows, rows[1:]) if ((r['state'] or {}).get('cuts') or 0) > ((prev['state'] or {}).get('cuts') or 0)]
    firsts = [next((c for c in r['calls'] if c['kind'] in ('main', 'notes')), None) for r in after_cut]
    checks['cut_restores_head'] = bool(firsts) and all(
        c is not None and c['cached_tokens'] == head_tokens and ((c.get('session') or {}).get('restored') or {}).get('position') == head_tokens
        for c in firsts)
    notes = [c for r in rows for c in r['previous_post_reply'] if c['kind'] == 'notes']
    checks['notes_continue_live_state'] = bool(notes) and all(c['cached_tokens'] > 0 and not (c.get('session') or {}).get('restored')
                                                              for c in notes)
    steady = [r for prev, r in zip(rows, rows[1:]) if r not in after_cut and r['kind'] != 'question']
    checks['turns_continue'] = all((r['cached_tokens'] or 0) > 0 for r in steady)
    recalls_after = (rows[-1]['state'] or {}).get('recalls') or 0
    checks['recall_answer_correct'] = FACT_SUM in answer and recalls_after > recalls_before_question
    checks['no_internal_recall'] = not any(r['leak'] for r in rows)
    checks['finish_reasons_valid'] = all(r['finish'] in ('stop', 'length', 'tool_calls') for r in rows)
    if a.exactness:
        checks['fresh_read_same_answer'] = report['exactness']['answer'] == answer
    report['checks'] = checks
    report['passed'] = all(checks.values())
    report['totals'] = dict(
        requests=len(rows), wall_s=round(sum(r['wall_s'] for r in rows), 1),
        prompt_read_s=round(sum((c.get('prompt_wall_ms') or 0) for r in rows for c in r['calls'] + r['previous_post_reply']) / 1000, 1),
        tokens_read=sum(c['read_tokens'] for r in rows for c in r['calls'] + r['previous_post_reply']),
        tokens_cached=sum(c['cached_tokens'] for r in rows for c in r['calls'] + r['previous_post_reply']))
    report['health_after'] = client.get('/health')[1]
    report['keeper_status'] = client.get('/keeper/status')[1].get(client.session)
    print(json.dumps(dict(answer=answer, checks=checks, totals=report['totals'], keeper_status=report['keeper_status']), indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1) + '\n')
    print('PASSED' if report['passed'] else 'FAILED')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())

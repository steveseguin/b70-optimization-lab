#!/usr/bin/env python3
"""Client-side device test of session parking against the running LAN service (SC117_SESSIONS=1).

  1. conversation A (long prompt, natural stop)        -> live state H = prompt_A + reply_A[:-1]
  2. conversation B (short, different)                 -> evicts A: the service parks H before its RESET
  3. A's next turn (prompt_A + reply_A + new user turn) -> restored from the parked session, continues at N = |H|
  4. the same prompt with sc117_reuse=false             -> a fresh full read (no continuation, no parked session)
Passes only if 2 parked exactly H, 3 reports cached_tokens == N > 0 and restored position N, and 3's output token ids
equal 4's token for token (4 reports cached_tokens == 0). Also checks the parked manifest on disk. No GPU access: HTTP
only, plus the CPU tokenizer to pre-check that the next turn extends H (template round trip).

  SC117_CONTEXT=32768 python3 -B session_device_test.py [--url http://127.0.0.1:18160]
"""
import argparse, hashlib, http.client, importlib.util, json, struct, sys, time, urllib.parse
from pathlib import Path

P = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PASSAGE = ' '.join(
    f'Station {i} of the coastal survey recorded a tide of {(i * 37) % 91 + 10} centimetres, a water temperature of '
    f'{(i * 13) % 17 + 8} degrees, and noted that the {["north", "east", "south", "west"][i % 4]} breakwater was '
    f'{["intact", "slightly worn", "under repair", "recently rebuilt"][i % 4]}.' for i in range(1, 25))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', default='http://127.0.0.1:18160')
    ap.add_argument('--key-file', default='/home/steve/.config/sc117-lan/api_key')
    ap.add_argument('--session-dir', default='/dev/shm/sc117-sessions')
    ap.add_argument('--run-json', default='/home/steve/own-xpu-runtime-results/sc117-lan/current/run.json')
    a = ap.parse_args()
    chat_mod = load(P / 'chat.py', 'sc117_device_test_chat')
    chat = chat_mod.Chat()
    key_path = Path(a.key_file)
    key = key_path.read_text().strip() if key_path.exists() else None
    url = urllib.parse.urlparse(a.url)

    def post(body):
        c = http.client.HTTPConnection(url.hostname, url.port, timeout=3600)
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Authorization'] = 'Bearer ' + key
        t0 = time.monotonic()
        c.request('POST', '/v1/chat/completions', json.dumps(body), headers)
        r = c.getresponse()
        raw = r.read()
        if r.status != 200:
            raise SystemExit(f'HTTP {r.status}: {raw[:500]!r}')
        out = json.loads(raw)
        out['_wall_s'] = time.monotonic() - t0
        return out

    def ids(body):
        return chat_mod.parse(body, chat)['prompt_ids']

    def sid(tokens):
        return hashlib.sha256(struct.pack(f'<{len(tokens)}i', *tokens)).hexdigest()[:32]

    report, checks = {}, {}
    run = Path(a.run_json)
    if run.exists():
        status = json.loads(run.read_text())
        report['service'] = {k: status.get(k) for k in ('sessions', 'continuation', 'prefill_rows', 'activations')}
        checks['service_sessions_on'] = bool(status.get('sessions'))
        checks['service_continuation_gate'] = status.get('continuation') is True

    system = {'role': 'system', 'content': 'You are a careful, concise assistant.'}
    a_msgs = [system, {'role': 'user', 'content': PASSAGE + '\n\nIn one sentence: which breakwaters need attention?'}]
    body_a = {'messages': a_msgs, 'max_tokens': 256}
    ra = post(body_a)
    out_a = ra['ownrt']['output_token_ids']
    prompt_a = ids(body_a)
    H = prompt_a + out_a[:-1]
    report['A'] = dict(prompt_tokens=len(prompt_a), output_tokens=len(out_a), finish=ra['choices'][0]['finish_reason'], wall_s=ra['_wall_s'])
    checks['A_prompt_tokens_match'] = ra['usage']['prompt_tokens'] == len(prompt_a)
    checks['A_natural_stop'] = ra['choices'][0]['finish_reason'] == 'stop'
    checks['A_long_enough'] = len(H) >= 256

    next_msgs = a_msgs + [{'role': 'assistant', 'content': ra['choices'][0]['message']['content']},
                          {'role': 'user', 'content': 'Name the three warmest stations and their temperatures.'}]
    body_c = {'messages': next_msgs, 'max_tokens': 128}
    prompt_c = ids(body_c)
    checks['next_turn_extends_H'] = prompt_c[:len(H)] == H and len(prompt_c) >= len(H) + 2 and prompt_c[len(H)] == out_a[-1]

    rb = post({'messages': [{'role': 'user', 'content': 'What is the capital of France? One word.'}], 'max_tokens': 16})
    sess_b = rb['ownrt'].get('session') or {}
    report['B'] = dict(session=sess_b, wall_s=rb['_wall_s'])
    checks['B_parked_exactly_H'] = sess_b.get('parked') == sid(H)
    manifest = Path(a.session_dir) / sid(H) / 'manifest.json'
    if manifest.exists():
        m = json.loads(manifest.read_text())
        checks['manifest_binds_H'] = m['tokens'] == H and m['position'] == len(H) and m['pending_token'] == out_a[-1]
        report['manifest'] = dict(id=m['id'], position=m['position'], bytes=m['bytes'], draft_position=m.get('draft_position'),
                                  stage_wall_ms=m.get('stage_wall_ms'), ranks={r: m['ranks'][r]['saved_bytes'] for r in m['ranks']})
    else:
        checks['manifest_binds_H'] = False

    rr = post(body_c)                                     # restored from the parked session
    rf = post(dict(body_c, sc117_reuse=False))            # fresh full read of the same prompt
    sess_r = rr['ownrt'].get('session') or {}
    restored = sess_r.get('restored') or {}
    cached_r = rr['usage']['prompt_tokens_details']['cached_tokens']
    cached_f = rf['usage']['prompt_tokens_details']['cached_tokens']
    out_r, out_f = rr['ownrt']['output_token_ids'], rf['ownrt']['output_token_ids']
    report['restored'] = dict(cached_tokens=cached_r, session=sess_r, prompt_wall_ms=rr['ownrt'].get('prompt_wall_ms'),
                              decode_tok_s=rr['ownrt'].get('decode_tok_s'), wall_s=rr['_wall_s'], output_tokens=len(out_r))
    report['fresh'] = dict(cached_tokens=cached_f, prompt_wall_ms=rf['ownrt'].get('prompt_wall_ms'), decode_tok_s=rf['ownrt'].get('decode_tok_s'),
                           wall_s=rf['_wall_s'], output_tokens=len(out_f))
    checks['restored_cached_tokens_is_N'] = cached_r == len(H) > 0
    checks['restored_position_is_N'] = restored.get('position') == len(H) and rr['ownrt'].get('continued_from') == len(H)
    checks['fresh_read_has_no_cache'] = cached_f == 0
    checks['restored_equals_fresh_token_for_token'] = out_r == out_f
    if out_r != out_f:
        report['first_difference'] = next((i for i, (x, y) in enumerate(zip(out_r, out_f)) if x != y), min(len(out_r), len(out_f)))
    report['checks'] = checks
    report['passed'] = all(checks.values())
    print(json.dumps(report, indent=1))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())

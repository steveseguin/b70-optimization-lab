#!/usr/bin/env python3
"""Many request endings in agent-like conversations, to reproduce the 2026-10-17 06:23 hang (notes/2026-10-17-hang-repro.md).

The 06:23 hang was in the last step issued for a request that had just finished (async scheduling issues one step
ahead). Agent traffic ends about 400 requests an hour; this client ends several times as many, with the agent's
pattern: conversations whose history grows by each answer plus a new chunk (so every request but the first of a
conversation is a prefix-cache hit with a short new tail), greedy answers of mixed length (8-300 tokens, some stopped
by a stop string), conversations restarted once past --max-context tokens, and a few idle pauses.

Stops at the first failed request (HTTP error, timeout) and says so; one JSON line per request in --log.
Synthetic text only (seeded word lists), no task data.
"""
import argparse
import json
import random
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--base-url', required=True)
ap.add_argument('--minutes', type=float, default=60)
ap.add_argument('--seed', type=int, default=20261017)
ap.add_argument('--conversations', type=int, default=6)
ap.add_argument('--max-context', type=int, default=30000, help='approximate tokens before a conversation restarts')
ap.add_argument('--pause-share', type=float, default=0.03, help='share of requests followed by an idle pause')
ap.add_argument('--log', required=True)
ap.add_argument('--timeout', type=float, default=180)
ap.add_argument('--answers', default='8,16,32,64,128,200,300', help='max_tokens values drawn per request (comma list)')
ap.add_argument('--tail-words', default='20,400', help='new words added before each request: min,max')
ap.add_argument('--gap', default='0,0', help='idle seconds before each request, drawn uniformly: min,max (agent traffic: 0.1-0.3)')
a = ap.parse_args()
rng = random.Random(a.seed)
ANSWERS = tuple(int(x) for x in a.answers.split(','))
TAIL = tuple(int(x) for x in a.tail_words.split(','))
GAP = tuple(float(x) for x in a.gap.split(','))
WORDS = ('time person year way day thing man world life hand part child eye woman place work week case point number '
         'group problem fact file test value error line code check build run state cache block step token answer '
         'record table field index list queue server client model layer write read call open close start stop '
         'again small three such away old few them will only think use just find through well little does each '
         'like did good words air must said many big if as get this between come water still large over new').split()


def chunk(n_words):
    out = []
    for i in range(n_words):
        if i % 14 == 0:
            out.append('\nRecord %06d: code %s-%05d.' % (rng.randrange(10 ** 6), ''.join(rng.choice('ABCDEFGHJKLMNPQRSTVWXYZ')
                                                                                        for _ in range(3)), rng.randrange(10 ** 5)))
        out.append(rng.choice(WORDS))
    return ' '.join(out)


def model_name():
    with urllib.request.urlopen(a.base_url + '/v1/models', timeout=30) as r:
        return json.load(r)['data'][0]['id']


def complete(model, prompt, max_tokens, stop):
    body = {'model': model, 'prompt': prompt, 'max_tokens': max_tokens, 'temperature': 0}
    if stop:
        body['stop'] = stop
    req = urllib.request.Request(a.base_url + '/v1/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=a.timeout) as r:
        return json.load(r)


model = model_name()
convs = [{'text': chunk(rng.randrange(300, 2500)), 'turn': 0} for _ in range(a.conversations)]
end = time.time() + a.minutes * 60
n = fails = 0
with open(a.log, 'a') as log:
    while time.time() < end:
        c = rng.choice(convs)
        if c['turn'] and len(c['text']) / 4.2 > a.max_context:
            c['text'], c['turn'] = chunk(rng.randrange(300, 2500)), 0
        c['text'] += '\n' + chunk(rng.randrange(*TAIL)) + '\nQuestion: list the next records.\nAnswer:'
        max_tokens = rng.choice(ANSWERS)
        stop = ['\nRecord 0'] if rng.random() < 0.3 else None
        if GAP[1] > 0:
            time.sleep(rng.uniform(*GAP))
        t0 = time.time()
        try:
            out = complete(model, c['text'], max_tokens, stop)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            fails += 1
            log.write(json.dumps({'n': n, 't': round(t0, 3), 'error': repr(e)[:300]}) + '\n')
            log.flush()
            print('REQUEST FAILED at request %d after %.1f s: %r' % (n, time.time() - t0, e), flush=True)
            break
        choice = out['choices'][0]
        usage = out.get('usage') or {}
        c['text'] += choice['text']
        c['turn'] += 1
        n += 1
        log.write(json.dumps({'n': n, 't': round(t0, 3), 's': round(time.time() - t0, 3), 'prompt': usage.get('prompt_tokens'),
                              'cached': (usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
                              'out': usage.get('completion_tokens'), 'max': max_tokens, 'finish': choice.get('finish_reason')}) + '\n')
        log.flush()
        if n % 100 == 0:
            print('STRESS %d requests, %.0f min left' % (n, (end - time.time()) / 60), flush=True)
        if rng.random() < a.pause_share:
            time.sleep(rng.uniform(5, 45))
print('STRESS DONE %d requests, %d failed' % (n, fails), flush=True)
raise SystemExit(1 if fails else 0)

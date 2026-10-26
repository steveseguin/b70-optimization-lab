#!/usr/bin/env python3
"""Device test: a session parked by one engine build, present only in the RAID archive, restored by the next build.

  before  (old build serving): conversation A, then an unrelated request parks A; waits for A's archive copy; deletes
          A's RAM copy (only the archive holds it now); writes state.json.
  after   (new build serving, after its session compat gate): A's next turn must be restored (cached_tokens == the
          parked length) and equal the same prompt read fresh (sc117_reuse false) token for token.
HTTP only, plus file checks under the session directories."""
import json, sys, time, urllib.request
from pathlib import Path
URL = 'http://127.0.0.1:18160/v1/chat/completions'
HERE = Path(__file__).resolve().parent
STATE = HERE / 'state.json'
RAM, ARCHIVE = Path('/dev/shm/sc117-sessions'), Path('/mnt/raid-models/sc117-session-archive')
PASSAGE = ' '.join(f'Ledger entry {i}: warehouse {chr(65 + i % 7)} shipped {(i * 41) % 97 + 3} crates of part '
                   f'{(i * 7919) % 10000:04d} to depot {(i * 13) % 29}, signed by clerk {["Ada", "Bo", "Cy", "Di"][i % 4]}.'
                   for i in range(1, 70))
M1 = [{'role': 'user', 'content': 'Here is a shipping ledger.\n\n' + PASSAGE + '\n\nWhich warehouse shipped part 7919? Answer briefly.'}]


def post(messages, max_tokens=48, reuse=True):
    body = json.dumps({'messages': messages, 'max_tokens': max_tokens, 'sc117_reuse': reuse}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'}), timeout=3600) as r:
        return json.load(r)


def before():
    t0 = time.time()
    r1 = post(M1)
    post([{'role': 'user', 'content': 'Say OK.'}], 4)  # evicts A: the service parks it
    new = lambda: [d for d in RAM.iterdir() if d.is_dir() and not d.name.startswith('.') and d.stat().st_mtime >= t0 - 1]
    parked = new()
    assert len(parked) == 1, parked
    sid = parked[0].name
    m = json.loads((parked[0] / 'manifest.json').read_text())
    for _ in range(600):  # the archive copies while the engine is idle (about 32 MB/s)
        done = [d for d in ARCHIVE.iterdir() if d.name.startswith(sid + '.') and (d / 'COMPLETE').exists()]
        if done:
            break
        time.sleep(2)
    assert done, 'no archive copy'
    for p in (RAM / sid, RAM / f'{sid}.lock'):
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    STATE.write_text(json.dumps(dict(sid=sid, archive=done[0].name, parked_tokens=m['position'], build_binary=m['identity']['binary_sha256'],
                                     reply=r1['choices'][0]['message']['content'], utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), indent=1))
    print(STATE.read_text())


def after():
    st = json.loads(STATE.read_text())
    m2 = M1 + [{'role': 'assistant', 'content': st['reply']}, {'role': 'user', 'content': 'Who signed that entry? Answer briefly.'}]
    r = post(m2)
    fresh = post(m2, reuse=False)
    o, f = r['ownrt'], fresh['ownrt']
    out = dict(cached_tokens=r['usage']['prompt_tokens_details']['cached_tokens'], parked_tokens=st['parked_tokens'],
               session=o.get('session'), fresh_cached=fresh['usage']['prompt_tokens_details']['cached_tokens'],
               restored_equals_fresh=o.get('output_token_ids') == f.get('output_token_ids'),
               text=r['choices'][0]['message']['content'][:200])
    out['passed'] = out['cached_tokens'] == st['parked_tokens'] and out['fresh_cached'] == 0 and out['restored_equals_fresh']
    (HERE / 'result.json').write_text(json.dumps(dict(state=st, result=out), indent=1))
    print(json.dumps(out, indent=1))


{'before': before, 'after': after}[sys.argv[1]]()

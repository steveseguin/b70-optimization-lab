#!/usr/bin/env python3
"""Drive one SC117 rank-0 engine process alone (rank0-lab, 2026-10-26).

Rank 0 holds the embedding/PLE lookups, the first `--target-split` layers and the MTP draft. In the service, rank 1
and the native controller (native_controller.hpp) feed it. Here this driver stands in for both, over the rank's
socket protocol (rank.hpp ops), with deterministic synthetic inputs where rank 1 would supply data:

  * token ids: a 32-bit LCG over the vocabulary (prompt and "confirmed" decode tokens alike);
  * rank 1's final hidden row of position q (the draft's reverse input): seeded F32 rows in [-1, 1), written to the
    shared reverse slot with reverse_ready = q+1, exactly where the native controller copies rank 1's rows;
  * no speculation: every HALF is confirmed (speculative=0) and the draft runs synchronously (speculative=0).

Sequence, as the native controller's bulk path (non-speculative form):
  prefill:  PREFILL chunks of --rows rows (token ids in the prefill header), each followed by the draft replay of its
            rows (DRAFT position q+1, token q+1, reverse row q, head off) for q+1 < prompt;
  decode:   for p in [prompt, prompt+steps): HALF(p, token p) + ACCEPT, then DRAFT(p, token p, reverse row p-1,
            head on) and its published guess for p+1 (the draft consumes confirmed positions strictly in order);
  end:      RESET (op 11) with --reset-dump all: the target state (state-2147483647, as the rank-1 driver's DUMP)
            and the draft's mutable state (draft-final-state/all-state.json, every draft allocation hashed), then FINISH.

  tp_rank0_driver.py run --launch RANK0-LAUNCH.json --out DIR [--steps N] [--prompt N] [--rows R] [--cache DIR]
  tp_rank0_driver.py compare DIR_A DIR_B      (target buffers bitwise, draft allocations, draft guesses)

2026-10-29 additions (copied from research/rank0-gdn-c43/tp_rank0_driver.py for the exact-TP lab):
  --tp            run the rank on two cards (--cards 2 --tp-replicate, ZE_AFFINITY_MASK=0,3 = 23:00.0 + 47:00.0);
                  OWNRT_TP_* come from the caller's environment and are recorded in summary.json (tp_env).
  --pattern P     decode step kinds, repeated over the steps: n = non-speculative half (default), h = speculative half
                  with the right token (accepted), m = speculative half with a wrong token (runs to the end, then
                  ROLLBACK with redo and the confirmed half), c = the same with the miss published before the half
                  (cancelled at its first card-0 launch), x = the same with the miss published by a timer thread
                  1-8 ms after the half starts (cancelled wherever the half then is, or completed). --cancel-launch
                  is refused by device builds. A cancelled or wrong half is always rolled back and redone.
  --prompt 0      no prefill and no --prefill-rows arguments.
"""
import argparse, json, mmap, os, socket, struct, subprocess, sys, time
from pathlib import Path

REQ = struct.Struct('<8i')            # op, token, position, fixture, speculative, sequence, reserved[2]
REP = struct.Struct('<8i4d')          # status, token, error, bytes, sequence, rank, reserved[2]; four doubles
SLOT = 65536
REVERSE = 2 * SLOT + 4096             # rank.hpp reverse_offset
SHARED = 2 * SLOT + 4096 + 2 * SLOT + 64
PUBLICATION = 2 * SLOT                # draft publication {valid, position, token, error, elapsed_ns, sequence, reserved, gpu_ms}
VERIFICATION = 2 * SLOT + 128         # {position_plus_one, token}: left zero (no confirmation check)
REVERSE_READY = 2 * SLOT + 192        # {position_plus_one}
HALF, ACCEPT, ROLLBACK, FINISH, DRAFT, RESET, PREFILL = 1, 2, 3, 5, 9, 11, 15
PREFILL_MAGIC, PREFILL_VERSION, PREFILL_HEADER = 0x31465050, 1, 4096
STREAM_FLOATS = 4 * 2560
STREAM = STREAM_FLOATS * 4
VOCAB = 248320


def recv_exact(sock, n, deadline):
    data = b''
    while len(data) < n:
        sock.settimeout(max(1.0, deadline - time.monotonic()))
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise RuntimeError('rank closed the channel')
        data += chunk
    return data


def call(sock, op, seq, position=0, token=0, fixture=0, speculative=0, timeout=1800):
    sock.sendall(REQ.pack(op, token, position, fixture, speculative, seq, 0, 0))
    rep = REP.unpack(recv_exact(sock, REP.size, time.monotonic() + timeout))
    if rep[0] != 0 or rep[2] != 0:
        raise RuntimeError(f'rank reply status={rep[0]} error={rep[2]} for op {op} position {position}')
    return rep


def token_at(q):
    x = (q * 2654435761 + 977) & 0xffffffff
    x = (x * 1664525 + 1013904223) & 0xffffffff
    return x % VOCAB


_BASE = None


def reverse_row(q):
    # Deterministic stand-in for rank 1's final F32 hidden row of position q (four streams of 2560): a window of one
    # seeded LCG sequence of floats in [-1, 1), starting at element q (distinct for every position).
    global _BASE
    if _BASE is None:
        x, vals = 3266489917, []
        for _ in range(65536 + STREAM_FLOATS):
            x = (x * 1664525 + 1013904223) & 0xffffffff
            vals.append((x / 2**31) - 1.0)
        _BASE = struct.pack(f'<{len(vals)}f', *vals)
    o = 4 * (q % 65536)
    return _BASE[o:o + STREAM]


def run(a):
    launch = json.loads(Path(a.launch).read_text())
    argv, env = list(launch['argv']), dict(launch['environment'])
    out = Path(a.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    shared = out / 'shared.bin'
    shared.write_bytes(bytes(SHARED))
    parent, child = socket.socketpair()
    stop_r, stop_w = os.pipe()

    def replace(flag, value):
        argv[argv.index(flag) + 1] = value
    require_rank = argv[argv.index('--rank') + 1]
    if require_rank != '0' or '--draft-mtp' not in argv:
        raise SystemExit('rank-0 launch with --draft-mtp required')
    replace('--channel', str(child.fileno()))
    replace('--stop-fd', str(stop_r))
    replace('--shared', str(shared))
    replace('--output', str(out / 'rank0'))
    replace('--reset-dump', 'all')
    for flag in ('--prefill-rows', '--prefill-shared', '--cancel-launch'):
        if flag in argv:
            i = argv.index(flag)
            del argv[i:i + 2]
    prefill_file = out / 'prefill.bin'
    with open(prefill_file, 'wb') as f:
        f.write(struct.pack('<4I', PREFILL_MAGIC, PREFILL_VERSION, a.rows, STREAM).ljust(PREFILL_HEADER, b'\0'))
        f.write(bytes(4 * a.rows * STREAM))
    if a.prompt:
        argv += ['--prefill-rows', str(a.rows), '--prefill-shared', str(prefill_file)]
    if a.cancel_launch >= 0:
        argv += ['--cancel-launch', str(a.cancel_launch)]
    if a.tp:
        replace('--cards', '2')
        argv.append('--tp-replicate')
        env['ZE_AFFINITY_MASK'] = '0,3'
        env.pop('FilterBdfPath', None)
        env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:*'
        if a.split:
            env['OWNRT_TP_SPLIT'] = a.split
    cache_root = Path(a.cache).absolute() if a.cache else out / 'cache'
    for key in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'):
        env[key] = str(cache_root / key.lower())
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    full_env = dict(os.environ)
    full_env.update(env)
    log = open(out / 'rank0.log', 'w')
    proc = subprocess.Popen(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: os.nice(19 - os.nice(0)))
    child.close()
    os.close(stop_r)
    t0 = time.monotonic()
    try:
        recv_exact(parent, REP.size, time.monotonic() + 3600)  # ready
        load_s = time.monotonic() - t0
        seq = 0
        f = open(shared, 'r+b')
        m = mmap.mmap(f.fileno(), SHARED)
        pf = open(prefill_file, 'r+b')
        pm = mmap.mmap(pf.fileno(), PREFILL_HEADER + 4 * a.rows * STREAM)

        def verify(position, token):  # what the native controller publishes when rank 1 confirms `position`
            struct.pack_into('<Ii', m, VERIFICATION, position, token)

        def draft(position, head):
            nonlocal seq
            if a.pattern != 'n':
                verify(position, token_at(position))
            q = position - 1
            m[REVERSE:REVERSE + STREAM] = reverse_row(q)
            m[REVERSE_READY:REVERSE_READY + 4] = struct.pack('<I', position)
            seq += 1
            s = time.monotonic()
            rep = call(parent, DRAFT, seq, position=position, token=token_at(position), fixture=int(head))
            ms = (time.monotonic() - s) * 1000
            valid, pos, tok, err = struct.unpack_from('<4i', m, PUBLICATION)
            # Head-off replay rows publish no guess (valid 0); a head-on step must publish a valid guess.
            if pos != position + 1 or err != 0 or (head and valid != 1):
                raise RuntimeError(f'draft publication at {position}: valid={valid} position={pos} error={err}')
            return (tok if valid == 1 else -1), ms, rep[9]

        prefill_ms = replay_ms = 0.0
        prefill_tokens = []
        for chunk, first in enumerate(range(0, a.prompt, a.rows)):
            n = min(a.rows, a.prompt - first)
            struct.pack_into(f'<{n}i', pm, 16, *[token_at(first + r) for r in range(n)])
            seq += 1
            s = time.monotonic()
            call(parent, PREFILL, seq, position=first, token=n, fixture=chunk % 2)
            prefill_ms += (time.monotonic() - s) * 1000
            for r in range(n):
                q = first + r
                if q + 1 < a.prompt:
                    tok, ms, _ = draft(q + 1, False)
                    prefill_tokens.append(tok)
                    replay_ms += ms
        prompt_ms = prefill_ms + replay_ms  # device-side calls only (host row generation excluded)
        half_ms, draft_ms, draft_tokens, draft_gpu = [], [], [], []
        events = dict(hits=0, misses=0, cancelled=0, redos=0)
        for step, p in enumerate(range(a.prompt, a.prompt + a.steps)):
            kind = a.pattern[step % len(a.pattern)]
            true = token_at(p)
            if kind == 'n':
                seq += 1
                s = time.monotonic()
                call(parent, HALF, seq, position=p, token=true, fixture=1)
                half_ms.append((time.monotonic() - s) * 1000)
            else:
                guess = true if kind == 'h' else (true + 1) % VOCAB
                if kind == 'c':
                    verify(p, true)
                timer = None
                if kind == 'x':
                    import threading
                    timer = threading.Timer((1.0 + (step * 1.7) % 7.0) / 1000.0, verify, args=(p, true))
                seq += 1
                s = time.monotonic()
                if timer:
                    timer.start()
                rep = call(parent, HALF, seq, position=p, token=guess, fixture=1, speculative=1)
                if timer:
                    timer.join()
                if kind == 'h' and not rep[6]:
                    half_ms.append((time.monotonic() - s) * 1000)
                    events['hits'] += 1
                else:
                    events['cancelled' if rep[6] else 'misses'] += 1
                    verify(p, true)
                    seq += 1
                    call(parent, ROLLBACK, seq, position=p, token=true, fixture=1, speculative=1)
                    seq += 1
                    s = time.monotonic()
                    call(parent, HALF, seq, position=p, token=true, fixture=1)
                    half_ms.append((time.monotonic() - s) * 1000)
                    events['redos'] += 1
            seq += 1
            call(parent, ACCEPT, seq, position=p, token=true, fixture=1)
            if p == 0:  # --prompt 0: the draft starts at position 1 (it needs rank 1's row of the previous position)
                continue
            tok, ms, gpu = draft(p, True)  # the draft consumes confirmed positions in order: p (reverse row p-1, token p)
            draft_tokens.append(tok)
            draft_ms.append(ms)
            draft_gpu.append(gpu)
        pm.close(); pf.close()
        m.close(); f.close()
        seq += 1
        (out / 'rank0' / f'reset-{seq}.txt').write_text(f"{out / 'rank0-after-reset'}\n\n")
        call(parent, RESET, seq)
        seq += 1
        parent.sendall(REQ.pack(FINISH, 0, 0, 0, 0, seq, 0, 0))  # the rank exits on finish without a reply
        proc.wait(timeout=600)
        summary = dict(binary=next((x for x in argv if x.endswith('engine')), None),
                       tp=a.tp, split=a.split, pattern=a.pattern, cancel_launch=a.cancel_launch, events=events,
                       tp_env={k: v for k, v in sorted(full_env.items()) if k.startswith('OWNRT_TP_') or k in ('NEOReadDebugKeys', 'EnableDeferBacking')},
                       prompt=a.prompt, rows=a.rows, steps=a.steps, load_s=load_s, prompt_ms=prompt_ms, prefill_ms=prefill_ms, draft_replay_ms=replay_ms,
                       half_ms=half_ms, draft_ms=draft_ms, draft_gpu_ms=draft_gpu, draft_tokens=draft_tokens,
                       prefill_draft_tokens=prefill_tokens, rc=proc.returncode)
        (out / 'summary.json').write_text(json.dumps(summary, indent=1))
        med = lambda v: sorted(v)[len(v) // 2]
        print(json.dumps({k: summary[k] for k in ('steps', 'load_s', 'prompt_ms', 'draft_replay_ms', 'rc')}),
              'median half ms %.3f draft ms %.3f' % (med(half_ms), med(draft_ms)))
    except Exception:
        try:
            os.write(stop_w, b'x')
        except OSError:
            pass
        proc.wait(timeout=600)
        raise


def compare(a):
    def state(root):
        return json.loads((Path(root) / 'rank0' / 'state-2147483647' / 'state.json').read_text())

    def draft_state(root):
        return json.loads((Path(root) / 'rank0' / 'draft-final-state' / 'all-state.json').read_text())
    sa, sb = state(a.a), state(a.b)
    ba, bb = sa['buffers'], sb['buffers']
    ignore = [x for x in (a.ignore or '').split(',') if x]
    skipped = sorted(k for k in ba.keys() | bb.keys() if any(k.endswith(x) for x in ignore))
    keys = sorted((ba.keys() & bb.keys()) - set(skipped))
    diff = [k for k in keys if ba[k] != bb[k]]
    only = sorted((ba.keys() ^ bb.keys()) - set(skipped))
    other = {k: (sa[k], sb[k]) for k in sa if k != 'buffers' and sa.get(k) != sb.get(k)}
    da, db = draft_state(a.a), draft_state(a.b)
    ma, mb = da['mutable_sha256'], db['mutable_sha256']
    draft_diff = sorted(k for k in ma.keys() & mb.keys() if ma[k] != mb[k])
    draft_only = sorted(ma.keys() ^ mb.keys())
    ta = json.loads((Path(a.a) / 'summary.json').read_text())
    tb = json.loads((Path(a.b) / 'summary.json').read_text())
    tokens_equal = ta['draft_tokens'] == tb['draft_tokens'] and ta['prefill_draft_tokens'] == tb['prefill_draft_tokens']
    print(json.dumps(dict(compared=len(keys), ignored=len(skipped), differ=diff[:40], differ_count=len(diff), only_one_side=only[:20],
                          other_fields_differ=other, draft_compared=len(ma.keys() & mb.keys()), draft_differ=draft_diff[:20],
                          draft_differ_count=len(draft_diff), draft_only_one_side=draft_only[:20], draft_tokens_equal=tokens_equal)))
    return 1 if diff or only or other or draft_diff or draft_only or not tokens_equal else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--launch', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--steps', type=int, default=48)
    r.add_argument('--prompt', type=int, default=4096)
    r.add_argument('--rows', type=int, default=256)
    r.add_argument('--cache')
    r.add_argument('--tp', action='store_true')
    r.add_argument('--split', help='OWNRT_TP_SPLIT (with --tp)')
    r.add_argument('--pattern', default='n', help='decode step kinds n/h/m/c, repeated')
    r.add_argument('--cancel-launch', type=int, default=-1)
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    c.add_argument('--ignore')
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == 'run' else compare(a))

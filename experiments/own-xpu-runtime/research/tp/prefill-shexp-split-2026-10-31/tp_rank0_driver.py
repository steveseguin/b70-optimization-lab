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

Lab copy for research/tp/service-ready-2026-10-29 (from research/tp/direct-exchange-2026-10-28): --pair picks the two
cards of --tp (PCI-order indices, default 0,3). --token-prompt reads the prompt rows token by token instead of in
PREFILL chunks: HALF(q, fixture 0) + ACCEPT per row, each followed by the same draft call the batched path makes after
that row (DRAFT q+1, head off, for q+1 < prompt). The draft calls are the batched path's, in the same order.

Lab copy for research/tp/prefill-speed-2026-10-29: --draft-chunk replaces the per-row draft replay after each PREFILL chunk
by one DRAFT_CHUNK command (op 29, prefill_wire.hpp draft_chunk_op; OWNRT_DRAFT_CHUNK_REPLAY=1 in the caller's environment):
the same rows (reverse rows q written to the chunk's reverse buffer of prefill.bin, confirmed tokens q+1 to the header's
draft_tokens at byte 2048), the same order, and the shared reverse slot/reverse_ready of the last row, as the per-row
calls leave them. Everything else is unchanged.

Lab copy for research/tp/rank0-trims-2026-10-29: the same command sequence; summary.json also records, per decode step,
the step kind and the wall time of every speculative HALF (spec_ms), ROLLBACK (rollback_ms) and redo HALF (redo_ms).
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
DRAFT_CHUNK, DRAFT_TOKENS = 29, 2048  # prefill_wire.hpp draft_chunk_op, draft_tokens_offset
PREFETCH_HINT, PREFETCH_MAGIC, NEXT_TOKENS = 1536, 0x32485050, 3072  # prefill_wire.hpp prefetch_hint_offset, prefetch_magic, next_tokens_offset (OWNRT_PREFILL_LOOKUP_PREFETCH)
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
        env['ZE_AFFINITY_MASK'] = a.pair
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

        off = dict(token=0, row=0)  # --second-prompt: request B reads other token ids and reverse rows

        def tk(q):
            return token_at(q + off['token'])

        def rv(q):
            return reverse_row(q + off['row'])

        def verify(position, token):  # what the native controller publishes when rank 1 confirms `position`
            struct.pack_into('<Ii', m, VERIFICATION, position, token)

        def draft(position, head):
            nonlocal seq
            if a.pattern != 'n':
                verify(position, tk(position))
            q = position - 1
            m[REVERSE:REVERSE + STREAM] = rv(q)
            m[REVERSE_READY:REVERSE_READY + 4] = struct.pack('<I', position)
            seq += 1
            s = time.monotonic()
            rep = call(parent, DRAFT, seq, position=position, token=tk(position), fixture=int(head))
            ms = (time.monotonic() - s) * 1000
            valid, pos, tok, err = struct.unpack_from('<4i', m, PUBLICATION)
            # Head-off replay rows publish no guess (valid 0); a head-on step must publish a valid guess.
            if pos != position + 1 or err != 0 or (head and valid != 1):
                raise RuntimeError(f'draft publication at {position}: valid={valid} position={pos} error={err}')
            return (tok if valid == 1 else -1), ms, rep[9]

        def request(prompt_n):  # one request: prompt (batched or token by token) with its draft replay, then the decode steps
            nonlocal seq
            prefill_ms = replay_ms = 0.0
            prefill_tokens = []
            for q in (range(prompt_n) if a.token_prompt else ()):
                seq += 1
                s = time.monotonic()
                call(parent, HALF, seq, position=q, token=tk(q), fixture=0)
                seq += 1
                call(parent, ACCEPT, seq, position=q, token=tk(q), fixture=0)
                prefill_ms += (time.monotonic() - s) * 1000
                if q + 1 < prompt_n:
                    tok, ms, _ = draft(q + 1, False)
                    prefill_tokens.append(tok)
                    replay_ms += ms
            for chunk, first in enumerate(range(0, 0 if a.token_prompt else prompt_n, a.rows)):
                n = min(a.rows, prompt_n - first)
                struct.pack_into(f'<{n}i', pm, 16, *[tk(first + r) for r in range(n)])
                nxt = first + a.rows
                if os.environ.get('OWNRT_PREFILL_LOOKUP_PREFETCH') == '1' and nxt < prompt_n:
                    # prefill-balance-2026-10-31: announce the next chunk with this one (its tokens at next_tokens_offset,
                    # then the hint, magic last), as the service controller does (prefill_wire.hpp)
                    n2 = min(a.rows, prompt_n - nxt)
                    struct.pack_into(f'<{n2}i', pm, NEXT_TOKENS, *[tk(nxt + r) for r in range(n2)])
                    struct.pack_into('<iii', pm, PREFETCH_HINT + 4, nxt, n2, 0)
                    struct.pack_into('<I', pm, PREFETCH_HINT, PREFETCH_MAGIC)
                seq += 1
                s = time.monotonic()
                call(parent, PREFILL, seq, position=first, token=n, fixture=chunk % 2)
                prefill_ms += (time.monotonic() - s) * 1000
                if a.draft_chunk:
                    k = sum(1 for r in range(n) if first + r + 1 < prompt_n)
                    if k:
                        slot = chunk % 2
                        rev = PREFILL_HEADER + (2 + slot) * a.rows * STREAM
                        for r in range(k):
                            pm[rev + r * STREAM:rev + (r + 1) * STREAM] = rv(first + r)
                        struct.pack_into(f'<{k}i', pm, DRAFT_TOKENS, *[tk(first + r + 1) for r in range(k)])
                        m[REVERSE:REVERSE + STREAM] = rv(first + k - 1)
                        m[REVERSE_READY:REVERSE_READY + 4] = struct.pack('<I', first + k)
                        seq += 1
                        s = time.monotonic()
                        call(parent, DRAFT_CHUNK, seq, position=first, token=k, fixture=slot)
                        replay_ms += (time.monotonic() - s) * 1000
                        valid, pos, tok, err = struct.unpack_from('<4i', m, PUBLICATION)
                        if valid != 0 or pos != first + k + 1 or err != 0:
                            raise RuntimeError(f'draft chunk publication at {first}: valid={valid} position={pos} error={err}')
                        prefill_tokens += [-1] * k
                    continue
                for r in range(n):
                    q = first + r
                    if q + 1 < prompt_n:
                        tok, ms, _ = draft(q + 1, False)
                        prefill_tokens.append(tok)
                        replay_ms += ms
            prompt_ms = prefill_ms + replay_ms  # device-side calls only (host row generation excluded)
            half_ms, draft_ms, draft_tokens, draft_gpu = [], [], [], []
            events = dict(hits=0, misses=0, cancelled=0, redos=0)
            kinds, spec_ms, rollback_ms, redo_ms = [], [], [], []
            for step, p in enumerate(range(prompt_n, prompt_n + a.steps)):
                kind = a.pattern[step % len(a.pattern)]
                kinds.append(kind)
                true = tk(p)
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
                    spec_ms.append((time.monotonic() - s) * 1000)
                    if timer:
                        timer.join()
                    if kind == 'h' and not rep[6]:
                        half_ms.append((time.monotonic() - s) * 1000)
                        events['hits'] += 1
                    else:
                        events['cancelled' if rep[6] else 'misses'] += 1
                        verify(p, true)
                        seq += 1
                        s = time.monotonic()
                        call(parent, ROLLBACK, seq, position=p, token=true, fixture=1, speculative=1)
                        rollback_ms.append((time.monotonic() - s) * 1000)
                        seq += 1
                        s = time.monotonic()
                        call(parent, HALF, seq, position=p, token=true, fixture=1)
                        half_ms.append((time.monotonic() - s) * 1000)
                        redo_ms.append(half_ms[-1])
                        events['redos'] += 1
                seq += 1
                call(parent, ACCEPT, seq, position=p, token=true, fixture=1)
                if p == 0:  # --prompt 0: the draft starts at position 1 (it needs rank 1's row of the previous position)
                    continue
                tok, ms, gpu = draft(p, True)  # the draft consumes confirmed positions in order: p (reverse row p-1, token p)
                draft_tokens.append(tok)
                draft_ms.append(ms)
                draft_gpu.append(gpu)
            return dict(prompt=prompt_n, prompt_ms=prompt_ms, prefill_ms=prefill_ms, draft_replay_ms=replay_ms, half_ms=half_ms, kinds=kinds,
                        spec_ms=spec_ms, rollback_ms=rollback_ms, redo_ms=redo_ms, draft_ms=draft_ms, draft_gpu_ms=draft_gpu,
                        draft_tokens=draft_tokens, prefill_draft_tokens=prefill_tokens, events=events)
        first_request = request(a.prompt)
        second_request = None
        if a.second_prompt:
            # Request boundary as the service: RESET (op 11; --reset-dump all dumps request A's state into rank0/ first),
            # then the shared region zeroed as the lab adapter does at a reset, then request B from position 0.
            seq += 1
            (out / 'rank0' / f'reset-{seq}.txt').write_text(f"{out / 'rank0-b'}\n\n")
            call(parent, RESET, seq)
            m[:SHARED] = bytes(SHARED)
            off.update(token=500000, row=31337)
            second_request = request(a.second_prompt)
        pm.close(); pf.close()
        m.close(); f.close()
        r = first_request
        prompt_ms, prefill_ms, replay_ms, half_ms, kinds = r['prompt_ms'], r['prefill_ms'], r['draft_replay_ms'], r['half_ms'], r['kinds']
        spec_ms, rollback_ms, redo_ms, draft_ms, draft_gpu = r['spec_ms'], r['rollback_ms'], r['redo_ms'], r['draft_ms'], r['draft_gpu_ms']
        draft_tokens, prefill_tokens, events = r['draft_tokens'], r['prefill_draft_tokens'], r['events']
        seq += 1
        (out / 'rank0' / f'reset-{seq}.txt').write_text(f"{out / ('rank0-b-after-reset' if a.second_prompt else 'rank0-after-reset')}\n\n")
        call(parent, RESET, seq)
        seq += 1
        parent.sendall(REQ.pack(FINISH, 0, 0, 0, 0, seq, 0, 0))  # the rank exits on finish without a reply
        proc.wait(timeout=600)
        summary = dict(binary=next((x for x in argv if x.endswith('engine')), None),
                       tp=a.tp, pair=a.pair if a.tp else None, split=a.split, pattern=a.pattern, cancel_launch=a.cancel_launch, events=events,
                       tp_env={k: v for k, v in sorted(full_env.items()) if k.startswith('OWNRT_TP_') or k in ('NEOReadDebugKeys', 'EnableDeferBacking', 'OWNRT_DRAFT_HEAD_SPLIT', 'OWNRT_SNAPSHOT_NOWAIT', 'OWNRT_DRAFT_GEMV_SPLIT', 'OWNRT_ROLLBACK_NOWAIT')},
 env_flags={k: v for k, v in sorted(full_env.items()) if k.startswith('OWNRT_')},  # prefill-host-2026-10-30: every OWNRT_ key the rank saw
                       prompt=a.prompt, token_prompt=a.token_prompt, draft_chunk=a.draft_chunk, rows=a.rows, steps=a.steps, load_s=load_s, prompt_ms=prompt_ms, prefill_ms=prefill_ms, draft_replay_ms=replay_ms,
                       half_ms=half_ms, kinds=kinds, spec_ms=spec_ms, rollback_ms=rollback_ms, redo_ms=redo_ms,
                       draft_ms=draft_ms, draft_gpu_ms=draft_gpu, draft_tokens=draft_tokens,
                       prefill_draft_tokens=prefill_tokens, second_prompt=a.second_prompt, second_request=second_request, rc=proc.returncode)
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
    def state(root, sub='rank0'):
        return json.loads((Path(root) / sub / 'state-2147483647' / 'state.json').read_text())

    def draft_state(root, sub='rank0'):
        return json.loads((Path(root) / sub / 'draft-final-state' / 'all-state.json').read_text())
    # --second-prompt runs (prefill-speed-2026-10-29): request B's dumps in rank0-b, its tokens in summary second_request,
    # the reset-time allocation inventories of both requests, and the ones invariant (inventory_check.py).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import inventory_check as IC
    second = [(Path(x) / 'rank0-b' / 'state-2147483647' / 'state.json').exists() for x in (a.a, a.b)]
    extra = {}
    if any(second):
        if not all(second):
            print(json.dumps(dict(second_request_on_one_side_only=second))); return 1
        sa2, sb2 = state(a.a, 'rank0-b'), state(a.b, 'rank0-b')
        ka = sorted(sa2['buffers'].keys() & sb2['buffers'].keys())
        d2 = [k for k in ka if sa2['buffers'][k] != sb2['buffers'][k]]
        o2 = sorted(sa2['buffers'].keys() ^ sb2['buffers'].keys())
        f2 = {k: (sa2[k], sb2[k]) for k in sa2 if k != 'buffers' and sa2.get(k) != sb2.get(k)}
        ma2, mb2 = draft_state(a.a, 'rank0-b')['mutable_sha256'], draft_state(a.b, 'rank0-b')['mutable_sha256']
        dd2 = sorted(k for k in ma2.keys() & mb2.keys() if ma2[k] != mb2[k]); do2 = sorted(ma2.keys() ^ mb2.keys())
        ra = json.loads((Path(a.a) / 'summary.json').read_text())['second_request']; rb = json.loads((Path(a.b) / 'summary.json').read_text())['second_request']
        t2 = ra['draft_tokens'] == rb['draft_tokens'] and ra['prefill_draft_tokens'] == rb['prefill_draft_tokens']
        inv = {sub: IC.inventory(a.a, a.b, sub) for sub in ('rank0', 'rank0-b')}
        extra = dict(second=dict(compared=len(ka), differ=d2[:40], differ_count=len(d2), only_one_side=o2[:20], other_fields_differ=f2,
                                 draft_compared=len(ma2.keys() & mb2.keys()), draft_differ=dd2[:20], draft_differ_count=len(dd2), draft_only_one_side=do2,
                                 draft_tokens_equal=t2), inventory=inv)
        extra['second_ok'] = not (d2 or o2 or f2 or dd2 or do2 or not t2) and all(v.get('compared', 0) and not v['differ_count'] for v in inv.values() if not v.get('missing'))
    ones = IC.ones(a.a) + IC.ones(a.b)
    extra['ones'] = ones
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
                          draft_differ_count=len(draft_diff), draft_only_one_side=draft_only[:20], draft_tokens_equal=tokens_equal, **extra)))
    bad = diff or only or other or draft_diff or draft_only or not tokens_equal or not all(x['ok'] for x in ones)
    return 1 if bad or ('second_ok' in extra and not extra['second_ok']) else 0


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
    r.add_argument('--pair', default='0,3', help='ZE_AFFINITY_MASK of --tp (PCI-order indices: 0=23 1=27 2=43 3=47)')
    r.add_argument('--token-prompt', action='store_true', help='read the prompt token by token (HALF fixture 0) instead of PREFILL chunks')
    r.add_argument('--draft-chunk', action='store_true', help='one DRAFT_CHUNK command per PREFILL chunk instead of per-row DRAFT calls')
    r.add_argument('--second-prompt', type=int, default=0, help='after the decode steps: RESET, then a second request of N prompt rows (other tokens and rows) and the same decode steps')
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    c.add_argument('--ignore')
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == 'run' else compare(a))

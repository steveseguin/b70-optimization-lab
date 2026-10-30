#!/usr/bin/env python3
"""Per-site decode census driver: one SC117 rank process alone on one card, real tokens (2026-10-30).

Lab copy of the rank harnesses in research/tp/prefill-speed-2026-10-29 (tp_rank0_driver.py / tp_rank1_driver.py): the same
socket protocol, shared-map offsets and PREFILL / HALF / ACCEPT / DRAFT / RESET / DUMP / FINISH commands, imported from
those drivers. What differs is the command sequence, built for measuring per-site device time at M = 1..4 rows:

  * real tokens: --tokens SEQ.json holds one suite prompt followed by the model's own greedy output (oracle tokens);
  * one request per mode, RESET between requests (no reset dumps), each request:
      prefix: positions [0, K) read with PREFILL chunks of at most --rows rows;
      window: positions [K, K+W) read in the mode's way:
        d   decode: HALF(p, token p) + ACCEPT per position (rank 0 then also DRAFT(p) with the head on: its guess for p+1);
        1..4 PREFILL chunks of exactly M rows (the batched multi-row kernels);
    rank 0 replays the draft per row after every chunk (DRAFT q+1, head off) as the native controller's bulk path does;
  * rank 0 records every output row (layer-22 stream: the forward rows of PREFILL, the handoff slot of HALF) and rank 1
    every final row (the reverse rows) and next token, per mode, so rank 1 can be fed rank 0's real rows (--rows-in) and
    rank 0's draft rank 1's real final rows (--reverse-in); without --reverse-in the draft gets the harness's seeded rows;
  * --trace: --timing launch (profiling queue) and OWNRT_SITE_TRACE=1 (the engine writes rank<r>/site-trace.jsonl);
    without it the launch's --timing token (unprofiled) runs;
  * --route-dump: OWNRT_PREFILL_ROUTE_DUMP=<out>/routes.bin (the engine's existing diagnostic: every routed prefill site's
    M x 10 routes, after a drain);
  * --cycle: OWNRT_PREFILL_REUSE2_CYCLE=1 and OWNRT_PREFILL_EXPERTS_CYCLE=1 (existing diagnostics: PREFILL call i uses tile
    configuration i % (count+1) of each family, count = the family's existing one-row kernel);
  * --dump: DUMP (op 4, position 2147483647) of the full target state before the final RESET.

  census_driver.py run --rank R --launch LAUNCH.json --binary ENGINE --out DIR --tokens SEQ.json --prefix K --window W
                       [--modes d,1,2,3,4] [--rows-in FILE] [--reverse-in FILE] [--trace] [--route-dump] [--dump] [--cache DIR]
  census_driver.py compare DIR_A DIR_B     (state dump buffers, captured rows of every mode, tokens/guesses)
"""
import argparse, hashlib, json, mmap, os, socket, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'research/tp/prefill-speed-2026-10-29'))
import tp_rank0_driver as R0  # noqa: E402  (protocol constants, recv_exact, seeded reverse rows)

REQ, REP, SLOT, SHARED = R0.REQ, R0.REP, R0.SLOT, R0.SHARED
REVERSE, PUBLICATION, REVERSE_READY = R0.REVERSE, R0.PUBLICATION, R0.REVERSE_READY
HALF, ACCEPT, FINISH, DRAFT, RESET, PREFILL, DUMP = 1, 2, 5, 9, 11, 15, 4
PREFILL_MAGIC, PREFILL_VERSION, PREFILL_HEADER = R0.PREFILL_MAGIC, R0.PREFILL_VERSION, R0.PREFILL_HEADER
STREAM = R0.STREAM
CALLS = []


def call(sock, op, seq, position=0, token=0, fixture=0, speculative=0, timeout=1800):
    t0 = time.monotonic_ns()
    sock.sendall(REQ.pack(op, token, position, fixture, speculative, seq, 0, 0))
    rep = REP.unpack(R0.recv_exact(sock, REP.size, time.monotonic() + timeout))
    CALLS.append([op, position, token if op == PREFILL else 1, t0, time.monotonic_ns()])
    if rep[0] != 0 or rep[2] != 0:
        raise RuntimeError(f'rank reply status={rep[0]} error={rep[2]} for op {op} position {position}')
    return rep


def run(a):
    launch = json.loads(Path(a.launch).read_text())
    argv, env = list(launch['argv']), dict(launch['environment'])
    seq_tokens = json.loads(Path(a.tokens).read_text())['tokens']
    K, W, rank = a.prefix, a.window, a.rank
    total = K + W
    if total + 1 > len(seq_tokens):
        raise SystemExit('token sequence too short')
    modes = a.modes.split(',')
    out = Path(a.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    shared = out / 'shared.bin'
    shared.write_bytes(bytes(SHARED))
    parent, child = socket.socketpair()
    stop_r, stop_w = os.pipe()

    def replace(flag, value):
        argv[argv.index(flag) + 1] = value
    if argv[argv.index('--rank') + 1] != str(rank):
        raise SystemExit(f'launch is not rank {rank}')
    if rank == 0 and '--draft-mtp' not in argv:
        raise SystemExit('rank-0 launch with --draft-mtp required')
    replace('--channel', str(child.fileno()))
    replace('--stop-fd', str(stop_r))
    replace('--shared', str(shared))
    replace('--output', str(out / f'rank{rank}'))
    replace('--reset-dump', 'none')
    for flag in ('--prefill-rows', '--prefill-shared', '--cancel-launch'):
        if flag in argv:
            i = argv.index(flag)
            del argv[i:i + 2]
    engine = next(i for i, x in enumerate(argv) if x.endswith('sc117-engine'))
    argv[engine] = a.binary
    if a.trace:
        replace('--timing', 'launch')
        env['OWNRT_SITE_TRACE'] = '1'
    if a.route_dump:
        env['OWNRT_PREFILL_ROUTE_DUMP'] = str(out / 'routes.bin')
    if a.cycle:  # existing diagnostics: every exact multi-row tile configuration of the dense (reuse2) and expert (xgroup)
        # prefill kernels plus the existing one-row kernel, chosen per chunk by the engine's chunk counter (chunk % (count+1))
        env['OWNRT_PREFILL_REUSE2_CYCLE'] = '1'
        env['OWNRT_PREFILL_EXPERTS_CYCLE'] = '1'
    R = a.rows
    prefill_file = out / 'prefill.bin'
    with open(prefill_file, 'wb') as f:
        f.write(struct.pack('<4I', PREFILL_MAGIC, PREFILL_VERSION, R, STREAM).ljust(PREFILL_HEADER, b'\0'))
        f.write(bytes(4 * R * STREAM))
    argv += ['--prefill-rows', str(R), '--prefill-shared', str(prefill_file)]
    cache_root = Path(a.cache).absolute() if a.cache else out / 'cache'
    for key in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'):
        env[key] = str(cache_root / key.lower())
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    rows_in = Path(a.rows_in).read_bytes() if a.rows_in else None
    reverse_in = Path(a.reverse_in).read_bytes() if a.reverse_in else None
    if rank == 1 and (rows_in is None or len(rows_in) < total * STREAM):
        raise SystemExit('rank 1 needs --rows-in with rows for every position')
    if reverse_in is not None and len(reverse_in) < (total - 1) * STREAM:
        raise SystemExit('--reverse-in too short')
    full_env = dict(os.environ)
    full_env.update(env)
    full_env.pop('LD_PRELOAD', None)
    (out / 'launch-used.json').write_text(json.dumps(dict(argv=argv, environment=env), indent=1))
    log = open(out / f'rank{rank}.log', 'w')
    proc = subprocess.Popen(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: os.nice(19 - os.nice(0)))
    child.close()
    os.close(stop_r)
    t0 = time.monotonic()
    try:
        R0.recv_exact(parent, REP.size, time.monotonic() + 3600)  # ready
        load_s = time.monotonic() - t0
        seq = 0
        f = open(shared, 'r+b')
        m = mmap.mmap(f.fileno(), SHARED)
        pf = open(prefill_file, 'r+b')
        pm = mmap.mmap(pf.fileno(), PREFILL_HEADER + 4 * R * STREAM)

        def fwd(slot):
            return PREFILL_HEADER + slot * R * STREAM

        def rev(slot):
            return PREFILL_HEADER + (2 + slot) * R * STREAM

        def reverse_row(q):
            return reverse_in[q * STREAM:(q + 1) * STREAM] if reverse_in is not None else R0.reverse_row(q)

        def draft(position, head):
            nonlocal seq
            q = position - 1
            m[REVERSE:REVERSE + STREAM] = reverse_row(q)
            m[REVERSE_READY:REVERSE_READY + 4] = struct.pack('<I', position)
            seq += 1
            rep = call(parent, DRAFT, seq, position=position, token=seq_tokens[position], fixture=int(head))
            valid, pos, tok, err = struct.unpack_from('<4i', m, R0.PUBLICATION)
            if pos != position + 1 or err != 0 or (head and valid != 1):
                raise RuntimeError(f'draft publication at {position}: valid={valid} position={pos} error={err}')
            return tok if valid == 1 else -1

        def request(mode):
            nonlocal seq
            rows = bytearray(total * STREAM)     # rank 0: output rows; rank 1: final (reverse) rows
            tokens, guesses, chunks = {}, {}, []
            draft_until = K if mode == 'd' else total   # the draft replays rows q+1 < draft_until after chunks

            def chunk(first, n, index):
                nonlocal seq
                slot = index % 2
                if rank == 0:
                    struct.pack_into(f'<{n}i', pm, 16, *seq_tokens[first:first + n])
                else:
                    pm[fwd(slot):fwd(slot) + n * STREAM] = rows_in[first * STREAM:(first + n) * STREAM]
                seq += 1
                s = time.monotonic()
                call(parent, PREFILL, seq, position=first, token=n, fixture=slot)
                chunks.append([first, n, (time.monotonic() - s) * 1000])
                src = fwd(slot) if rank == 0 else rev(slot)
                rows[first * STREAM:(first + n) * STREAM] = pm[src:src + n * STREAM]
                if rank == 0:
                    for q in range(first, first + n):
                        if q + 1 < draft_until:
                            draft(q + 1, False)
            index = 0
            for first in range(0, K, R):
                chunk(first, min(R, K - first), index); index += 1
            if mode == 'd':
                for p in range(K, total):
                    if rank == 1:
                        m[SLOT:SLOT + STREAM] = rows_in[p * STREAM:(p + 1) * STREAM]
                    seq += 1
                    s = time.monotonic()
                    rep = call(parent, HALF, seq, position=p, token=seq_tokens[p], fixture=1)
                    chunks.append([p, 0, (time.monotonic() - s) * 1000])
                    if rank == 0:
                        if rep[3] != STREAM:
                            raise RuntimeError(f'rank 0 half {p} exported {rep[3]} bytes')
                        rows[p * STREAM:(p + 1) * STREAM] = m[0:STREAM]
                    else:
                        if struct.unpack_from('<I', m, REVERSE_READY)[0] != p + 1:
                            raise RuntimeError(f'rank 1 half {p}: reverse rows not published')
                        rows[p * STREAM:(p + 1) * STREAM] = m[REVERSE:REVERSE + STREAM]
                        tokens[p] = rep[1]
                    seq += 1
                    call(parent, ACCEPT, seq, position=p, token=seq_tokens[p], fixture=1)
                    if rank == 0:
                        guesses[p + 1] = draft(p, True)
            else:
                M = int(mode)
                for first in range(K, total, M):
                    chunk(first, min(M, total - first), index); index += 1
            (out / f'rows-{mode}.bin').write_bytes(bytes(rows))
            hit = sum(1 for p, g in guesses.items() if g == seq_tokens[p])
            match = sum(1 for p, t in tokens.items() if t == seq_tokens[p + 1])
            return dict(mode=mode, chunks=chunks, tokens=tokens, guesses=guesses, guess_hits=hit, guess_count=len(guesses),
                        token_oracle_matches=match, token_count=len(tokens),
                        rows_sha256=[hashlib.sha256(rows[q * STREAM:(q + 1) * STREAM]).hexdigest() for q in range(total)])
        def reset():  # request_reset.hpp reads OUTPUT/reset-<sequence>.txt: an absolute output path and an (empty) oracle line
            nonlocal seq
            seq += 1
            (out / f'rank{rank}' / f'reset-{seq}.txt').write_text(f"{out / f'rank{rank}-after-reset-{seq}'}\n\n")
            call(parent, RESET, seq)
        results = []
        for i, mode in enumerate(modes):
            if i:
                reset()
                m[:SHARED] = bytes(SHARED)
            results.append(request(mode))
        if a.dump:
            seq += 1
            call(parent, DUMP, seq, position=2147483647)
        reset()
        seq += 1
        parent.sendall(REQ.pack(FINISH, 0, 0, 0, 0, seq, 0, 0))  # the rank exits on finish without a reply
        proc.wait(timeout=600)
        pm.close(); pf.close(); m.close(); f.close()
        ref = results[0]['rows_sha256']
        rows_equal = {r['mode']: r['rows_sha256'] == ref for r in results}
        summary = dict(rank=rank, binary=a.binary, launch=a.launch, trace=a.trace, route_dump=a.route_dump, cycle=a.cycle, tokens_file=a.tokens,
                       prefix=K, window=W, rows=R, modes=modes, load_s=load_s, rc=proc.returncode, rows_equal_to_first_mode=rows_equal,
                       requests=results, calls=CALLS,
                       env={k: v for k, v in sorted(env.items()) if k.startswith('OWNRT_') or k in ('NEOReadDebugKeys', 'EnableDeferBacking', 'ZE_AFFINITY_MASK', 'FilterBdfPath')})
        (out / 'summary.json').write_text(json.dumps(summary, indent=1))
        brief = {r['mode']: dict(guess_hits=r['guess_hits'], guesses=r['guess_count'], oracle=r['token_oracle_matches'], tokens=r['token_count'])
                 for r in results}
        print(json.dumps(dict(rank=rank, load_s=round(load_s, 1), rc=proc.returncode, rows_equal=rows_equal, per_mode=brief)))
        return 0 if proc.returncode == 0 and all(rows_equal.values()) else 1
    except Exception:
        try:
            os.write(stop_w, b'x')
        except OSError:
            pass
        proc.wait(timeout=600)
        raise


def compare(a):
    def state(root):
        d = next(Path(root).glob('rank*/state-2147483647'))  # the dump lands in the output directory of the request it ends
        return json.loads((d / 'state.json').read_text())
    sa, sb = state(a.a), state(a.b)
    ba, bb = sa['buffers'], sb['buffers']
    keys = sorted(ba.keys() & bb.keys())
    diff = [k for k in keys if ba[k] != bb[k]]
    only = sorted(ba.keys() ^ bb.keys())
    other = {k: (sa[k], sb[k]) for k in sa if k != 'buffers' and sa.get(k) != sb.get(k)}
    ta = json.loads((Path(a.a) / 'summary.json').read_text())
    tb = json.loads((Path(a.b) / 'summary.json').read_text())
    per_mode = {}
    for ra, rb in zip(ta['requests'], tb['requests']):
        per_mode[ra['mode']] = dict(rows_equal=ra['rows_sha256'] == rb['rows_sha256'], tokens_equal=ra['tokens'] == rb['tokens'],
                                    guesses_equal=ra['guesses'] == rb['guesses'])
    ok = not (diff or only or other) and all(all(v.values()) for v in per_mode.values()) and len(ta['requests']) == len(tb['requests'])
    print(json.dumps(dict(passed=ok, compared=len(keys), differ=diff[:40], differ_count=len(diff), only_one_side=only[:20],
                          other_fields_differ=other, per_mode=per_mode)))
    return 0 if ok else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--rank', type=int, required=True, choices=(0, 1))
    r.add_argument('--launch', required=True)
    r.add_argument('--binary', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--tokens', required=True)
    r.add_argument('--prefix', type=int, default=128)
    r.add_argument('--window', type=int, default=144)
    r.add_argument('--rows', type=int, default=256)
    r.add_argument('--modes', default='d,1,2,3,4')
    r.add_argument('--rows-in')
    r.add_argument('--reverse-in')
    r.add_argument('--trace', action='store_true')
    r.add_argument('--route-dump', action='store_true')
    r.add_argument('--cycle', action='store_true', help='OWNRT_PREFILL_REUSE2_CYCLE=1 and OWNRT_PREFILL_EXPERTS_CYCLE=1')
    r.add_argument('--dump', action='store_true')
    r.add_argument('--cache')
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == 'run' else compare(a))

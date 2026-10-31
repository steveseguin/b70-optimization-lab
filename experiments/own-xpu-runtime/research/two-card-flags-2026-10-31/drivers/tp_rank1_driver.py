#!/usr/bin/env python3
"""Drive one SC117 rank-1 engine process alone (TP development, 2026-10-25).

Launches the rank-1 command line recorded by the LAN service (ranks/rank1-launch.json), with its own socket, stop pipe
and shared file, feeds N decode halves with deterministic input streams (seeded F32 in [-1, 1)), commits each, then
dumps the full state. Two runs with different card setups are compared with --compare A B (bitwise, per buffer file).

  tp_rank1_driver.py run --launch RANK1-LAUNCH.json --out DIR [--binary PATH] [--tp] [--steps N]
  tp_rank1_driver.py compare DIR_A DIR_B

OWNRT_TP_EXPERTS / OWNRT_TP_EXCHANGE / OWNRT_TP_THREADS are taken from the caller's environment and recorded in
summary.json (tp_env) with the binary path.

--tp runs the process on two cards (ZE_AFFINITY_MASK=0,3 in PCI order: 23:00.0 and 47:00.0) with --cards 2
--tp-replicate. It needs the service stopped (the cards are the service's).

Lab copy for research/tp/fault-ladder-2026-10-29 (from service-ready-2026-10-29): records every call's CLOCK_MONOTONIC send
and reply times (summary.json "calls": [op, position, send_ns, reply_ns]); with ALLOC_TRACE_SO in the caller's environment the
engine process alone (not this driver) gets LD_PRELOAD=ALLOC_TRACE_SO and ALLOC_TRACE_OUT=OUT/alloc-trace (host-only tracer).
Lab copy for research/tp/prefill-speed-2026-10-29: --second-prompt N (RESET between two requests, each dumped at its RESET;
the compare also checks request B, the allocation inventories and the moe-ones invariant). Earlier:
Lab copy for research/tp/service-ready-2026-10-29 (from engine/tools/tp_rank1_driver.py). Changes: prefill arguments
(--prefill-rows/--prefill-shared) are passed only with --batched or --prefill-alloc (a TP rank refused them before
batched prefill under TP existed); --pair picks the two cards of --tp (PCI-order indices, default 0,3).
"""
import argparse, hashlib, json, os, socket, struct, subprocess, sys, time
# Lab copy for research/hc-kernels-2026-10-30 (of research/tp/prefill-speed-2026-10-29/tp_rank1_driver.py): also records
# rank 1's exported draft-input rows (the engine's layer-47 streams export into the shared reverse region after every
# half, and each batched prefill chunk's final rows in the prefill file's reverse buffer) as SHA-256 per row in
# summary.json `exports` (second request: second_request.exports), and `compare` checks them. Any fusion that moves a
# site's write must keep these rows equal (the 2026-10-30 cnorm end-gate halt: final.norm pairing changed them).
REVERSE = 2 * 65536 + 4096
REVERSE_READY = 2 * 65536 + 192
from pathlib import Path

REQ = struct.Struct('<8i')            # op, token, position, fixture, speculative, sequence, reserved[2]
REP = struct.Struct('<8i4d')          # status, token, error, bytes, sequence, rank, reserved[2]; four doubles
SLOT = 65536
SHARED = 2 * SLOT + 4096 + 2 * SLOT + 64
HALF, ACCEPT, DUMP, FINISH, PREFILL, RESET = 1, 2, 4, 5, 15, 11
PREFILL_MAGIC, PREFILL_VERSION, PREFILL_HEADER = 0x31465050, 1, 4096
STREAM_FLOATS = 4 * 2560


def recv_exact(sock, n, deadline):
    data = b''
    while len(data) < n:
        sock.settimeout(max(1.0, deadline - time.monotonic()))
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise RuntimeError('rank closed the channel')
        data += chunk
    return data


CALLS = []


def call(sock, op, seq, position=0, token=0, fixture=0, timeout=1800):
    t0 = time.monotonic_ns()
    sock.sendall(REQ.pack(op, token, position, fixture, 0, seq, 0, 0))
    rep = REP.unpack(recv_exact(sock, REP.size, time.monotonic() + timeout))
    CALLS.append([op, position, t0, time.monotonic_ns()])
    if rep[0] != 0 or rep[2] != 0:
        raise RuntimeError(f'rank reply status={rep[0]} error={rep[2]} for op {op}')
    return rep


def streams(step):
    # Deterministic, no numpy dependency: a 32-bit LCG mapped to [-1, 1).
    x = (step * 2654435761 + 12345) & 0xffffffff
    out = []
    for _ in range(STREAM_FLOATS):
        x = (x * 1664525 + 1013904223) & 0xffffffff
        out.append((x / 2**31) - 1.0)
    return struct.pack(f'<{STREAM_FLOATS}f', *out)


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
        i = argv.index(flag)
        argv[i + 1] = value
    replace('--channel', str(child.fileno()))
    replace('--stop-fd', str(stop_r))
    replace('--shared', str(shared))
    replace('--output', str(out / 'rank1'))
    if a.second_prompt:
        replace('--reset-dump', 'all')  # each RESET dumps the request's state and allocation inventory before zeroing
    for flag in ('--prefill-rows', '--prefill-shared'):
        if flag in argv:
            i = argv.index(flag)
            del argv[i:i + 2]
    prefill_file = None
    if a.prompt and (a.batched or a.prefill_alloc):
        # Prompt rows: --batched reads them in chunks of --rows through the prefill command (op 15); otherwise one
        # half per row with fixture 0 (the token-by-token reading the prefill gate compares against).
        stream = STREAM_FLOATS * 4
        prefill_file = out / 'prefill.bin'
        with open(prefill_file, 'wb') as f:
            f.write(struct.pack('<4I', PREFILL_MAGIC, PREFILL_VERSION, a.rows, stream).ljust(PREFILL_HEADER, b'\0'))
            f.write(bytes(4 * a.rows * stream))
        argv += ['--prefill-rows', str(a.rows), '--prefill-shared', str(prefill_file)]
    if a.binary:
        argv[argv.index(next(x for x in argv if x.endswith('own-engine')))] = a.binary
    if a.tp:
        replace('--cards', '2')
        argv.append('--tp-replicate')
        env['ZE_AFFINITY_MASK'] = a.pair
        env.pop('FilterBdfPath', None)
        env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:*'
        if a.split:
            env['OWNRT_TP_SPLIT'] = a.split
    cache_root = Path(a.cache).absolute() if a.cache else out / 'cache'  # --cache: shared, warm JIT caches across runs
    for key in ('SYCL_CACHE_DIR', 'NEO_CACHE_DIR', 'XDG_CACHE_HOME'):
        env[key] = str(cache_root / key.lower())
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    full_env = dict(os.environ)
    full_env.update(env)
    full_env.pop('LD_PRELOAD', None)
    if os.environ.get('ALLOC_TRACE_SO'):
        full_env['LD_PRELOAD'] = os.environ['ALLOC_TRACE_SO']
        full_env['ALLOC_TRACE_OUT'] = str(out / 'alloc-trace')
    log = open(out / 'rank1.log', 'w')
    proc = subprocess.Popen(argv, env=full_env, pass_fds=(child.fileno(), stop_r), stdout=log, stderr=subprocess.STDOUT,
                            preexec_fn=lambda: os.nice(19 - os.nice(0)))
    child.close()
    os.close(stop_r)
    t0 = time.monotonic()
    try:
        recv_exact(parent, REP.size, time.monotonic() + 1800)  # ready
        load_s = time.monotonic() - t0
        seq = 0
        with open(shared, 'r+b') as f:
            import mmap
            m = mmap.mmap(f.fileno(), SHARED)
            def request(prompt_n, soff, tok):  # one request: prompt rows (batched or token by token), then the decode steps
                nonlocal seq
                times_r, tokens_r, exports_r = [], [], []
                prompt_ms = 0.0
                def export(position):  # the shared reverse region after a half: ready position and the row's SHA-256
                    ready = struct.unpack_from('<I', m, REVERSE_READY)[0]
                    exports_r.append([position, ready, hashlib.sha256(m[REVERSE:REVERSE + STREAM_FLOATS * 4]).hexdigest()])
                if prompt_n:
                    stream = STREAM_FLOATS * 4
                    s0 = time.monotonic()
                    if a.batched:
                        pf = open(prefill_file, 'r+b')
                        pm = mmap.mmap(pf.fileno(), PREFILL_HEADER + 4 * a.rows * stream)
                        chunk = 0
                        for first in range(0, prompt_n, a.rows):
                            n = min(a.rows, prompt_n - first)
                            base = PREFILL_HEADER + (chunk % 2) * a.rows * stream
                            for r in range(n):
                                pm[base + r * stream: base + (r + 1) * stream] = streams(soff + 100000 + first + r)
                            seq += 1
                            call(parent, PREFILL, seq, position=first, token=n, fixture=chunk % 2)
                            rb = PREFILL_HEADER + (2 + chunk % 2) * a.rows * stream  # prefill_wire.hpp reverse(base, fixture)
                            for r in range(n):
                                exports_r.append([first + r, 'batched', hashlib.sha256(pm[rb + r * stream: rb + (r + 1) * stream]).hexdigest()])
                            chunk += 1
                        pm.close(); pf.close()
                    else:
                        for r in range(prompt_n):
                            m[SLOT:SLOT + stream] = streams(soff + 100000 + r)
                            seq += 1
                            call(parent, HALF, seq, position=r, token=tok + 2000 + r, fixture=0)
                            export(r)
                            seq += 1
                            call(parent, ACCEPT, seq, position=r, token=tok + 2000 + r, fixture=0)
                    prompt_ms = (time.monotonic() - s0) * 1000
                for step in range(prompt_n, prompt_n + a.steps):
                    m[SLOT:SLOT + STREAM_FLOATS * 4] = streams(soff + step)
                    seq += 1
                    s = time.monotonic()
                    rep = call(parent, HALF, seq, position=step, token=tok + 1000 + step, fixture=1)
                    times_r.append((time.monotonic() - s) * 1000)
                    tokens_r.append(rep[1])
                    export(step)
                    seq += 1
                    call(parent, ACCEPT, seq, position=step, token=tok + 1000 + step, fixture=1)
                return prompt_ms, times_r, tokens_r, exports_r
            prompt_ms, times, tokens, exports = request(a.prompt, 0, 0)
            second = None
            if a.second_prompt:
                # Request boundary as the service: RESET (op 11; with --reset-dump all it dumps request A's state and the
                # allocation inventory into rank1/ first), the shared region zeroed as the lab adapter does, then request B
                # (other streams and tokens) from position 0; a final RESET dumps request B into rank1-b.
                seq += 1
                (out / 'rank1' / f'reset-{seq}.txt').write_text(f"{out / 'rank1-b'}\n\n")
                call(parent, RESET, seq)
                m[:SHARED] = bytes(SHARED)
                pms, tms, tks, exb = request(a.second_prompt, 300000, 50000)
                second = dict(prompt=a.second_prompt, prompt_ms=pms, half_ms=tms, tokens=tks, exports=exb)
                seq += 1
                (out / 'rank1' / f'reset-{seq}.txt').write_text(f"{out / 'rank1-b-after-reset'}\n\n")
                call(parent, RESET, seq)
            else:
                seq += 1
                call(parent, DUMP, seq, position=2147483647)
            seq += 1
            parent.sendall(REQ.pack(FINISH, 0, 0, 0, 0, seq, 0, 0))  # the rank exits on finish without a reply
        proc.wait(timeout=600)
        summary = dict(binary=next((x for x in argv if x.endswith('engine')), None),
                       tp_env={k: v for k, v in sorted(full_env.items()) if k.startswith('OWNRT_TP_')},
                       tp=a.tp, pair=a.pair if a.tp else None, split=a.split, prompt=a.prompt, batched=a.batched, rows=a.rows, prompt_ms=prompt_ms, second_prompt=a.second_prompt, second_request=second, steps=a.steps, load_s=load_s, half_ms=times, tokens=tokens, exports=exports, rc=proc.returncode,
                       alloc_trace=full_env.get('LD_PRELOAD'), calls=CALLS)
        (out / 'summary.json').write_text(json.dumps(summary, indent=1))
        print(json.dumps({k: summary[k] for k in ('tp', 'steps', 'load_s', 'tokens', 'rc')}),
              'median half ms %.2f' % sorted(times)[len(times) // 2])
    except Exception:
        try:
            os.write(stop_w, b'x')
        except OSError:
            pass
        proc.wait(timeout=600)
        raise


def compare(a):
    """Per-buffer comparison of two dumps (state.json hashes). --ignore lists buffer-name suffixes that are allowed to
    differ (e.g. per-slot expert intermediates that hold NaN for the slots another card computes)."""
    def state(root, sub='rank1'):
        return json.loads((Path(root) / sub / 'state-2147483647' / 'state.json').read_text())
    # --second-prompt runs (prefill-speed-2026-10-29): request B's dump in rank1-b and its tokens, the reset-time allocation
    # inventories of both requests, and the ones invariant (inventory_check.py).
    sys.path.insert(0, '/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/prefill-speed-2026-10-29')
    import inventory_check as IC
    second = [(Path(x) / 'rank1-b' / 'state-2147483647' / 'state.json').exists() for x in (a.a, a.b)]
    extra = {}
    if any(second):
        if not all(second):
            print(json.dumps(dict(second_request_on_one_side_only=second))); return 1
        sa2, sb2 = state(a.a, 'rank1-b'), state(a.b, 'rank1-b')
        ka = sorted(sa2['buffers'].keys() & sb2['buffers'].keys())
        d2 = [k for k in ka if sa2['buffers'][k] != sb2['buffers'][k]]
        o2 = sorted(sa2['buffers'].keys() ^ sb2['buffers'].keys())
        f2 = {k: (sa2[k], sb2[k]) for k in sa2 if k != 'buffers' and sa2.get(k) != sb2.get(k)}
        ra = json.loads((Path(a.a) / 'summary.json').read_text())['second_request']; rb = json.loads((Path(a.b) / 'summary.json').read_text())['second_request']
        t1 = json.loads((Path(a.a) / 'summary.json').read_text())['tokens'] == json.loads((Path(a.b) / 'summary.json').read_text())['tokens']
        inv = {sub: IC.inventory(a.a, a.b, sub) for sub in ('rank1', 'rank1-b')}
        extra = dict(tokens_equal=t1, second=dict(compared=len(ka), differ=d2[:40], differ_count=len(d2), only_one_side=o2[:20], other_fields_differ=f2,
                                                  tokens_equal=ra['tokens'] == rb['tokens']), inventory=inv)
        extra['second_ok'] = t1 and not (d2 or o2 or f2) and ra['tokens'] == rb['tokens'] and all(v.get('compared', 0) and not v['differ_count'] for v in inv.values() if not v.get('missing'))
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
    print(json.dumps(dict(compared=len(keys), ignored=len(skipped), differ=diff[:40], differ_count=len(diff),
                          only_one_side=only[:20], other_fields_differ=other, **extra)))
    ea = json.loads((Path(a.a) / 'summary.json').read_text()); eb = json.loads((Path(a.b) / 'summary.json').read_text())
    exa = [ea.get('exports'), (ea.get('second_request') or {}).get('exports')]; exb = [eb.get('exports'), (eb.get('second_request') or {}).get('exports')]
    exports_equal = exa == exb and exa[0] is not None
    print(json.dumps(dict(exports_equal=exports_equal, exports_rows=[len(x or []) for x in exa],
                          first_export_difference=next((i for i, (x, y) in enumerate(zip(exa[0] or [], exb[0] or [])) if x != y), None))))
    bad = diff or only or other or not all(x['ok'] for x in ones) or not exports_equal
    return 1 if bad or ('second_ok' in extra and not extra['second_ok']) else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--launch', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--binary')
    r.add_argument('--tp', action='store_true')
    r.add_argument('--steps', type=int, default=8)
    r.add_argument('--cache', help='shared SYCL/NEO cache directory (warm kernels for timing)')
    r.add_argument('--prompt', type=int, default=0, help='prompt rows read before the decode steps')
    r.add_argument('--batched', action='store_true', help='read the prompt rows through the batched prefill command')
    r.add_argument('--rows', type=int, default=32, help='prefill chunk rows (--batched)')
    r.add_argument('--split', help='OWNRT_TP_SPLIT label suffixes, e.g. .attention,.gdn.qkv (with --tp)')
    r.add_argument('--prefill-alloc', action='store_true', help='pass the prefill arguments for a token-by-token prompt too')
    r.add_argument('--second-prompt', type=int, default=0, help='after the decode steps: RESET, then a second request of N prompt rows (other streams) and the same decode steps')
    r.add_argument('--pair', default='0,3', help='ZE_AFFINITY_MASK of --tp (PCI-order indices: 0=23 1=27 2=43 3=47)')
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    c.add_argument('--ignore', help='comma-separated buffer-name suffixes allowed to differ')
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == 'run' else compare(a))

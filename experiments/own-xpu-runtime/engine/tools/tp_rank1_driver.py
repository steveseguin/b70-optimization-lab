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
"""
import argparse, json, os, socket, struct, subprocess, sys, time
from pathlib import Path

REQ = struct.Struct('<8i')            # op, token, position, fixture, speculative, sequence, reserved[2]
REP = struct.Struct('<8i4d')          # status, token, error, bytes, sequence, rank, reserved[2]; four doubles
SLOT = 65536
SHARED = 2 * SLOT + 4096 + 2 * SLOT + 64
HALF, ACCEPT, DUMP, FINISH, PREFILL = 1, 2, 4, 5, 15
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


def call(sock, op, seq, position=0, token=0, fixture=0, timeout=1800):
    sock.sendall(REQ.pack(op, token, position, fixture, 0, seq, 0, 0))
    rep = REP.unpack(recv_exact(sock, REP.size, time.monotonic() + timeout))
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
    for flag in ('--prefill-rows', '--prefill-shared'):
        if flag in argv:
            i = argv.index(flag)
            del argv[i:i + 2]
    prefill_file = None
    if a.prompt:
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
        env['ZE_AFFINITY_MASK'] = '0,3'
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
        times = []
        tokens = []
        with open(shared, 'r+b') as f:
            import mmap
            m = mmap.mmap(f.fileno(), SHARED)
            prompt_ms = 0.0
            if a.prompt:
                stream = STREAM_FLOATS * 4
                s0 = time.monotonic()
                if a.batched:
                    pf = open(prefill_file, 'r+b')
                    pm = mmap.mmap(pf.fileno(), PREFILL_HEADER + 4 * a.rows * stream)
                    chunk = 0
                    for first in range(0, a.prompt, a.rows):
                        n = min(a.rows, a.prompt - first)
                        base = PREFILL_HEADER + (chunk % 2) * a.rows * stream
                        for r in range(n):
                            pm[base + r * stream: base + (r + 1) * stream] = streams(100000 + first + r)
                        seq += 1
                        call(parent, PREFILL, seq, position=first, token=n, fixture=chunk % 2)
                        chunk += 1
                    pm.close(); pf.close()
                else:
                    for r in range(a.prompt):
                        m[SLOT:SLOT + stream] = streams(100000 + r)
                        seq += 1
                        call(parent, HALF, seq, position=r, token=2000 + r, fixture=0)
                        seq += 1
                        call(parent, ACCEPT, seq, position=r, token=2000 + r, fixture=0)
                prompt_ms = (time.monotonic() - s0) * 1000
            for step in range(a.prompt, a.prompt + a.steps):
                m[SLOT:SLOT + STREAM_FLOATS * 4] = streams(step)
                seq += 1
                s = time.monotonic()
                rep = call(parent, HALF, seq, position=step, token=1000 + step, fixture=1)
                times.append((time.monotonic() - s) * 1000)
                tokens.append(rep[1])
                seq += 1
                call(parent, ACCEPT, seq, position=step, token=1000 + step, fixture=1)
            seq += 1
            call(parent, DUMP, seq, position=2147483647)
            seq += 1
            parent.sendall(REQ.pack(FINISH, 0, 0, 0, 0, seq, 0, 0))  # the rank exits on finish without a reply
        proc.wait(timeout=600)
        summary = dict(binary=next((x for x in argv if x.endswith('engine')), None),
                       tp_env={k: v for k, v in sorted(full_env.items()) if k.startswith('OWNRT_TP_')},
                       tp=a.tp, split=a.split, prompt=a.prompt, batched=a.batched, rows=a.rows, prompt_ms=prompt_ms, steps=a.steps, load_s=load_s, half_ms=times, tokens=tokens, rc=proc.returncode)
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
    def state(root):
        return json.loads((Path(root) / 'rank1' / 'state-2147483647' / 'state.json').read_text())
    sa, sb = state(a.a), state(a.b)
    ba, bb = sa['buffers'], sb['buffers']
    ignore = [x for x in (a.ignore or '').split(',') if x]
    skipped = sorted(k for k in ba.keys() | bb.keys() if any(k.endswith(x) for x in ignore))
    keys = sorted((ba.keys() & bb.keys()) - set(skipped))
    diff = [k for k in keys if ba[k] != bb[k]]
    only = sorted((ba.keys() ^ bb.keys()) - set(skipped))
    other = {k: (sa[k], sb[k]) for k in sa if k != 'buffers' and sa.get(k) != sb.get(k)}
    print(json.dumps(dict(compared=len(keys), ignored=len(skipped), differ=diff[:40], differ_count=len(diff),
                          only_one_side=only[:20], other_fields_differ=other)))
    return 1 if diff or only or other else 0


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
    c = sub.add_parser('compare')
    c.add_argument('a')
    c.add_argument('b')
    c.add_argument('--ignore', help='comma-separated buffer-name suffixes allowed to differ')
    a = ap.parse_args()
    sys.exit(run(a) if a.cmd == 'run' else compare(a))

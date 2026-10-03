#!/usr/bin/env python3
"""Physical-address-aware memory test (run as root; CPU only, never touches a GPU).

Locks a large anonymous buffer, reads its own /proc/self/pagemap to learn the
physical address of every page, writes a sequence of patterns and reads them
back, and logs every mismatching 64-bit word with its PHYSICAL address as one
JSON line (fsynced, so a crash keeps what was found).

Default mode tests the last --tail-mib of every 1 GiB block plus an equal
control set from the middle of each block: fast (about a minute per round on
100 GiB) and it shows at once whether failures are tied to particular
physical regions. --all tests every locked page (about ten minutes per round
per 100 GiB). See docs/host-stability-and-fault-diagnosis.md for the case
this was written for and how to fence off what it finds.

    sudo python3 tools/physmap_memtest.py --gib 100 --rounds 3 --out run.jsonl
    sudo python3 tools/physmap_memtest.py --gib 100 --rounds 2 --all --out all.jsonl

Needs numpy. Leave 15-20 GiB unlocked for the rest of the system.
"""
import argparse, ctypes, json, mmap, os, sys, time
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--gib', type=int, required=True, help='buffer size to lock')
ap.add_argument('--tail-mib', type=int, default=4)
ap.add_argument('--rounds', type=int, default=3)
ap.add_argument('--out', required=True)
ap.add_argument('--all', action='store_true', help='test every locked page, not just tails and controls')
args = ap.parse_args()

PAGE = 4096
size = args.gib << 30
npages = size // PAGE
buf = mmap.mmap(-1, size, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS | getattr(mmap, 'MAP_POPULATE', 0))
addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
libc = ctypes.CDLL(None, use_errno=True)
if libc.mlock(ctypes.c_void_p(addr), ctypes.c_size_t(size)) != 0:
    raise OSError(ctypes.get_errno(), 'mlock failed')
words = np.frombuffer(buf, dtype=np.uint64).reshape(npages, PAGE // 8)

with open('/proc/self/pagemap', 'rb') as pm:
    pm.seek((addr // PAGE) * 8)
    ent = np.frombuffer(pm.read(npages * 8), dtype=np.uint64)
present = (ent >> np.uint64(63)) == 1
phys = (ent & np.uint64((1 << 55) - 1)) << np.uint64(12)
if not present.all() or (phys == 0).any():
    raise RuntimeError('pagemap lacks PFNs (need root) or pages absent')
off = phys & np.uint64((1 << 30) - 1)
tail = args.tail_mib << 20
is_tail = off >= np.uint64((1 << 30) - tail)
is_ctrl = (off >= np.uint64(1 << 29)) & (off < np.uint64((1 << 29) + tail))
idx = np.flatnonzero(is_tail | is_ctrl)
if args.all:
    idx = np.arange(npages)
kind = np.where(is_tail[idx], 0, 1)  # 0 = tail, 1 = control (with --all: 1 = everything else)
p = phys[idx]
blocks_tail = np.unique(p[kind == 0] >> np.uint64(30))
print(f'locked {args.gib} GiB; {len(idx)} pages under test '
      f'({int((kind == 0).sum())} tail in {len(blocks_tail)} GiB blocks, {int((kind == 1).sum())} control)', flush=True)

patterns = [np.uint64(int.from_bytes(bytes([j]) * 8, 'little')) for j in range(0, 64)]
patterns += [np.uint64(0x5555555555555555), np.uint64(0xAAAAAAAAAAAAAAAA)] * 8
patterns += [np.uint64(0), np.uint64(0xFFFFFFFFFFFFFFFF)] * 8
if args.all:
    patterns = patterns[:8] + patterns[64:68] + patterns[80:84]
log = open(args.out, 'a')
log.write(json.dumps({'event': 'start', 'time': time.time(), 'gib': args.gib, 'tail_mib': args.tail_mib,
                      'pages': int(len(idx)), 'tail_blocks': [int(b) for b in blocks_tail]}) + '\n')
log.flush(); os.fsync(log.fileno())
total = 0
CH = 16384
for rnd in range(args.rounds):
    t0 = time.time(); bad_round = 0
    for pat in patterns:
        for s in range(0, len(idx), CH):
            if args.all: words[s:s + CH] = pat
            else: words[idx[s:s + CH]] = pat
        for s in range(0, len(idx), CH):
            got = words[s:s + CH] if args.all else words[idx[s:s + CH]]
            bad = np.argwhere(got != pat)
            for r, w in bad[:4096]:
                rec = {'event': 'mismatch', 'round': rnd, 'phys': hex(int(p[s + r]) + int(w) * 8),
                       'kind': 'tail' if kind[s + r] == 0 else 'control',
                       'expected': hex(int(pat)), 'got': hex(int(got[r, w]))}
                log.write(json.dumps(rec) + '\n')
            if len(bad):
                bad_round += len(bad); log.flush(); os.fsync(log.fileno())
    total += bad_round
    print(f'round {rnd}: {bad_round} mismatching words in {time.time() - t0:.0f} s', flush=True)
log.write(json.dumps({'event': 'end', 'time': time.time(), 'mismatches': total}) + '\n')
log.flush(); os.fsync(log.fileno())
print('total mismatching words:', total)

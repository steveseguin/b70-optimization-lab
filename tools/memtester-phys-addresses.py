#!/usr/bin/env python3
"""Map memtester FAILURE offsets to physical addresses (run as root while memtester is still running).

memtester reports "FAILURE: 0xGOOD != 0xBAD at offset 0x..." as an offset into
each half of its buffer. While the process is alive and its pages are locked
(run memtester under sudo so mlock works), /proc/<pid>/pagemap gives the
physical page behind each offset. The first value printed by memtester is the
first half (bufa), the second is the second half (bufb); whichever differs
from the pattern being written is the bad copy.

    sudo memtester 13G 1 > worker-1.log &        # one log per worker
    sudo python3 tools/memtester-phys-addresses.py

Each worker's stdout must be redirected to its own log file.
"""
import os, re, struct

PAT = re.compile(rb'FAILURE: 0x([0-9a-f]+) != 0x([0-9a-f]+) at offset 0x([0-9a-f]+)')
for pid in [int(p) for p in os.listdir('/proc') if p.isdigit()]:
    try:
        if open(f'/proc/{pid}/comm').read().strip() != 'memtester':
            continue
        log = os.readlink(f'/proc/{pid}/fd/1')
        raw = open(log, 'rb').read().replace(b'\x08', b'')
    except OSError:
        continue
    offsets = sorted({int(o, 16) for _, _, o in PAT.findall(raw)})
    if not offsets:
        continue
    start, end = max(((int(a, 16), int(b, 16)) for a, b in
                      (l.split()[0].split('-') for l in open(f'/proc/{pid}/maps'))),
                     key=lambda r: r[1] - r[0])
    base = (start + 16 + 4095) // 4096 * 4096          # memtester page-aligns its malloc
    want = re.search(rb'got\s+(\d+)MB', raw) or re.search(rb'want (\d+)MB', raw)
    if not want:
        continue
    half = (int(want.group(1)) << 20) // 2              # each test compares the two halves
    print(f'{os.path.basename(log)} pid {pid}: {len(offsets)} failing words')
    with open(f'/proc/{pid}/pagemap', 'rb') as pm:
        for name, shift in (('first half (bufa)', 0), ('second half (bufb)', half)):
            pages = []
            for page in sorted({o // 4096 for o in offsets}):
                pm.seek(((base + shift) // 4096 + page) * 8)
                entry = struct.unpack('<Q', pm.read(8))[0]
                pages.append(hex((entry & ((1 << 55) - 1)) * 4096) if entry >> 63 else 'absent')
            print(f'  {name}: {pages}')

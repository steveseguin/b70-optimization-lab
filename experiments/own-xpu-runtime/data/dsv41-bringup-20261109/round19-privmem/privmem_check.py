#!/usr/bin/env python3
# privmem_check.py BINARY: per-kernel private memory in an engine binary's device code (zeinfo per_thread_memory_buffers).
# The driver keeps one private buffer per kernel (taken at its first launch, kept for the run) of
# size per lane x SIMD x 2048 hardware threads (B70: 32 Xe cores x 8 x 8): prints every kernel at 8 MiB or more, the
# index kernels by name, and the total over all kernels if every one were launched. privmem-1 (tp118p) should leave
# no TopKSel*M / IndexerScore* / index lambda kernel at ~1.1 KiB per lane.
import re, subprocess, sys, tempfile, os

THREADS = 2048
binary = sys.argv[1]
with tempfile.TemporaryDirectory() as td:
    bundle = os.path.join(td, 'bundle.bin')
    subprocess.run(['objcopy', '-O', 'binary', '--only-section=__CLANG_OFFLOAD_BUNDLE__sycl-spir64_gen', binary, bundle],
                   check=True)
    d = open(bundle, 'rb').read()
rows = []
pos = 0
while True:
    k = d.find(b'\nkernels:', pos)
    if k < 0:
        break
    end = d.find(b'\x00', k)
    txt = d[k:end].decode('latin1')
    pos = end
    for blk in re.split(r'\n  - name:\s*', txt)[1:]:
        name = blk.split('\n', 1)[0].strip()
        m = re.search(r'per_thread_memory_buffers:(.*?)(\n    [a-z_]+:|\Z)', blk, re.S)
        simd = re.search(r'simd_size:\s*(\d+)', blk)
        simd = int(simd.group(1)) if simd else 0
        if not m:
            continue
        for e in re.finditer(r'type:\s*(\w+)\s*\n\s*usage:\s*(\w+)\s*\n\s*size:\s*(\d+)(\s*\n\s*is_simt_thread:\s*(\w+))?',
                             m.group(1)):
            if e.group(2) != 'private_space':
                continue
            per_thread = int(e.group(3)) * (simd if e.group(5) == 'true' else 1)
            rows.append((per_thread * THREADS / 2**20, int(e.group(3)), simd, name))
idx = re.compile(r'TopKSelM|TopKSelMB|TopKSelMC|IndexerScoreB|idx_score_r|tpm_index|ixm_score|ixm_check|idx_cand_check_m|LensPut|CidxFillM')
big = [r for r in rows if r[0] >= 30]
print(f"privmem_check {os.path.basename(binary)}: {len(rows)} kernels with private memory, "
      f"{sum(r[0] for r in rows):.0f} MiB per card if all launched; {len(big)} at 30 MiB or more")
for mib, lane, simd, name in sorted(rows, reverse=True):
    if mib >= 30 or idx.search(name):
        short = re.search(r'ops41sycl(\d+)([A-Za-z0-9_]+)', name)
        short = short.group(2)[:int(short.group(1))] if short else name[:110]
        print(f"  {mib:6.1f} MiB  {lane} B/lane simd{simd}  {short}")

import re, sys
# categories of a OWN_GPROF=2 per-type table: ms per cycle
def cat(name):
    if name.startswith('Xchg'): return 'exchange'
    if name.startswith('Routed'): return 'routed'
    if re.search(r'Gemv(Q8P|Q6KP|Q5KP)<(40u|5u)', name) and 'HcDots' not in name: return 'q_b'
    if re.search(r'Gemv(Q8P|Q6KP)<(128u|16u)', name) and 'HcDots' not in name: return 'o_a'
    if 'NormRows<5120' in name and 'HcDots' not in name: return 'norm5120'
    if re.search(r'Score|Softmax|OutM|Indexer|TopKSel|WindowAppend|CompressPool|RingCommit|Rope|PubAppend|StatePack|Cidx', name): return 'attention'
    if 'Gemv' in name: return 'dense other'
    if 'Norm' in name: return 'norm other'
    return 'other'
for f in sys.argv[1:]:
    tot = {}; ktot = None
    for ln in open(f):
        m = re.match(r'\s+([0-9.]+)\s+[0-9.]+%\s+([0-9.]+)\s+([0-9.]+) us\s+(.*)$', ln)
        if m:
            c = cat(m.group(4)); tot[c] = tot.get(c, 0) + float(m.group(1))
        m = re.match(r'\s+kernels ([0-9.]+) ms', ln)
        if m: ktot = float(m.group(1))
    s = sum(tot.values())
    print(f.split('/')[-1], f'kernels {ktot} (sum {s:.3f}); outside exchange {s - tot.get("exchange",0):.3f}')
    for k, v in sorted(tot.items(), key=lambda x: -x[1]):
        print(f'   {k:12s} {v:7.3f} ms  {100*v/s:5.1f} %')

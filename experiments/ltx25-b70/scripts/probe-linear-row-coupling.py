#!/usr/bin/env python3
"""Does an fp32 linear layer on this XPU stack give a row the same bits whatever the OTHER rows hold?

The encoder localiser showed o_proj changing real-token rows whose inputs were bit-identical, when only
other (pad) rows differed. This isolates that: same rows, different neighbours, different row counts.
    ZE_AFFINITY_MASK=<card> python probe-linear-row-coupling.py
"""
import json, sys, torch
import torch.nn.functional as F
torch.use_deterministic_algorithms(True, warn_only=True)
dev = torch.device('xpu')
g = torch.Generator().manual_seed(1234)
out = []
for fin, fout in ((4096, 3840), (3840, 4096), (3840, 15360), (15360, 3840), (2048, 3840)):
    w = torch.randn(fout, fin, generator=g).to(torch.bfloat16).to(dev)
    keep = torch.randn(1, 56, fin, generator=g)
    for m in (1024, 512, 256, 128, 64):
        res = {}
        for label, scale in (('zeros', 0.0), ('small', 1.0), ('large', 50.0), ('huge', 5000.0)):
            x = torch.randn(1, m, fin, generator=g) * scale
            x[:, -56:] = keep
            y = F.linear(x.to(dev), w.float())
            res[label] = y[:, -56:].cpu()
        base = res['small']
        row = {'in': fin, 'out': fout, 'rows': m}
        for label in ('zeros', 'large', 'huge'):
            row['vs_' + label] = 'exact' if torch.equal(base, res[label]) else 'diff %.2e' % float((base.double() - res[label].double()).abs().max())
        out.append((row, base))
        print(row, flush=True)
# same rows, different row counts
for fin, fout in ((4096, 3840), (3840, 4096), (3840, 15360), (15360, 3840), (2048, 3840)):
    refs = [(r['rows'], b) for r, b in out if r['in'] == fin and r['out'] == fout]
    print(fin, fout, 'row-count invariance vs 1024:', {m: ('exact' if torch.equal(refs[0][1], b) else 'diff %.2e' % float((refs[0][1].double() - b.double()).abs().max())) for m, b in refs[1:]}, flush=True)

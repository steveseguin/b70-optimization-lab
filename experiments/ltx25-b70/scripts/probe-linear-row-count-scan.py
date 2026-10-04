#!/usr/bin/env python3
"""For each encoder linear shape: at which row counts M does a row get the same bits as in a 1024-row call?
    ZE_AFFINITY_MASK=<card> python probe-linear-row-count-scan.py [out.json]
"""
import json, sys, torch
import torch.nn.functional as F
torch.use_deterministic_algorithms(True, warn_only=True)
dev = torch.device('xpu')
g = torch.Generator().manual_seed(4321)
KEEP = 56
out = {}
for fin, fout in ((3840, 4096), (3840, 2048), (4096, 3840), (3840, 15360), (15360, 3840), (2048, 3840)):
    w = torch.randn(fout, fin, generator=g).to(torch.bfloat16).float().to(dev)
    keep = torch.randn(1, KEEP, fin, generator=g)
    def run(m, lead=None):
        x = torch.randn(1, m, fin, generator=g)
        x[:, -KEEP:] = keep
        if lead is not None:           # rows first instead of last
            x = torch.cat((keep, x[:, :-KEEP]), dim=1)
            return F.linear(x.to(dev), w)[:, :KEEP].cpu()
        return F.linear(x.to(dev), w)[:, -KEEP:].cpu()
    ref = run(1024)
    same = [m for m in range(64, 1025, 32) if torch.equal(ref, run(m))]
    extra = {m: bool(torch.equal(ref, run(m))) for m in (1023, 1025, 1040, 1088, 1152, 1536, 2048)}
    twod = bool(torch.equal(ref, F.linear(torch.cat((torch.randn(1024 - KEEP, fin, generator=g), keep[0])).to(dev), w)[-KEEP:].cpu().unsqueeze(0)))
    front = bool(torch.equal(ref, run(1024, lead=True)))
    out[f'{fin}->{fout}'] = {'exact_row_counts_64_to_1024_step_32': same, 'others': extra, '2d_input_same': twod, 'rows_first_same': front}
    print(f'{fin}->{fout}', 'exact at M =', same, '| other M:', extra, '| 2D input same:', twod, '| rows first same:', front, flush=True)
if len(sys.argv) > 1:
    json.dump(out, open(sys.argv[1], 'w'), indent=1)

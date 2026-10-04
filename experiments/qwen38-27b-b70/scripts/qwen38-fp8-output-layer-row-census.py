"""Row-invariance census of the REAL output-layer kernel of the FP8 lane: FP16 F.linear, per-rank shape 124160 x 5120.

For each row count M, every row of F.linear(x[:M], W) is compared bit for bit with the same row computed alone
(F.linear(x[r:r+1], W)), on several random weights/inputs and with rows in shuffled positions. Reports, for each M,
whether all rows equal their one-row result, and the row classes that follow. One card, no model, about a minute.
"""
import json, sys, torch
dev = 'xpu'
N, K = 124160, 5120
lin = torch.nn.functional.linear
bits = lambda t: t.view(torch.int16)
report = {'shape': [N, K], 'dtype': 'float16', 'trials': []}
MS = list(range(1, 41)) + [48, 56, 64, 96, 128, 129, 160, 256, 320, 321, 512]
for seed, wscale, xscale in ((1, 0.02, 1.0), (2, 0.05, 0.5), (3, 0.01, 3.0)):
    g = torch.Generator().manual_seed(seed)
    W = (torch.randn(N, K, generator=g) * wscale).to(torch.float16).to(dev)
    x = (torch.randn(512, K, generator=g) * xscale).to(torch.float16).to(dev)
    solo = torch.cat([lin(x[r:r + 1], W) for r in range(64)], dim=0)        # each of the first 64 rows alone
    again = torch.cat([lin(x[r:r + 1], W) for r in range(8)], dim=0)
    deterministic = bool(torch.equal(bits(again), bits(solo[:8])))
    equal_to_solo = {}
    for m in MS:
        out = lin(x[:m], W)
        k = min(m, 64)
        equal_to_solo[m] = bool(torch.equal(bits(out[:k]), bits(solo[:k])))
    # shuffled positions inside a 32-row call, and the production path for 64 rows (two 32-row pieces)
    perm = torch.randperm(32, generator=g)
    shuffled = bool(torch.equal(bits(lin(x[:32][perm.to(dev)], W)), bits(solo[:32][perm.to(dev)])))
    pieces64 = torch.cat([lin(x[i:i + 32], W) for i in (0, 32)], dim=0)
    pieces_ok = bool(torch.equal(bits(pieces64), bits(solo)))
    largest = max(m for m in MS if all(equal_to_solo[j] for j in MS if j <= m))
    trial = {'seed': seed, 'deterministic': deterministic, 'largest_M_with_every_row_equal_to_solo': largest,
             'first_M_not_equal': next((m for m in MS if not equal_to_solo[m]), None),
             'equal_to_solo_by_M': {str(m): equal_to_solo[m] for m in MS},
             'shuffled_positions_in_32_rows_equal': shuffled, 'two_32_row_pieces_equal_solo_for_64_rows': pieces_ok}
    report['trials'].append(trial)
    print(f"CENSUS seed {seed}: deterministic={deterministic} every row equals solo up to M={largest}, first failing M={trial['first_M_not_equal']}, "
          f"shuffled 32 ok={shuffled}, 64 rows as two 32-row pieces equal solo={pieces_ok}", flush=True)
    del W, x, solo
json.dump(report, open(sys.argv[1], 'w'), indent=1)

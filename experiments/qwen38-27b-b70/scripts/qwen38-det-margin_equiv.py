import json, torch
import torch.nn.functional as F
DEV="xpu:0"
torch.manual_seed(20260903)
K, N = 5120, 124160
MARGIN = 0.25
bad = 0
for trial in range(40):
    m = 1 + trial % 6
    x = torch.randn(m, K, dtype=torch.float16, device=DEV)
    w = torch.randn(N, K, dtype=torch.float16, device=DEV)
    true_logits = (x.float() @ w.float().t())
    # simulate int4 head output: true + bounded noise
    eps = 0.08
    logits = (true_logits + (torch.rand_like(true_logits)*2-1)*eps).to(torch.float16)
    # force some near-ties: shrink top gaps on ~20% of rows
    if trial % 5 == 0:
        r = 0
        top2 = torch.topk(logits[r].float(), 2)
        logits[r, top2.indices[1]] = top2.values[0] - 0.05  # near-tie
    # ORIGINAL semantics
    lo = logits.clone()
    top2o = torch.topk(lo.float(), k=2, dim=-1).values
    low = (top2o[:, 0] - top2o[:, 1]) < MARGIN
    if bool(low.any()):
        exact = F.linear(x.reshape(-1, K)[low].to(torch.float16), w, None)
        lo[low] = exact.to(lo.dtype)
    # PATCHED semantics
    lp = logits.clone()
    lf = lp.float()
    top1v, top1i = lf.max(dim=-1)
    top2v = lf.scatter(1, top1i.unsqueeze(1), float("-inf")).max(dim=-1).values
    lowp = (top1v - top2v) < MARGIN
    assert torch.equal(low, lowp), "mask mismatch"
    if bool(lowp.any()):
        rows = lowp.nonzero(as_tuple=True)[0]
        for r in rows.tolist():
            cand = (top1v[r] - lf[r]) < MARGIN
            cand[top1i[r]] = True
            cols = cand.nonzero(as_tuple=True)[0]
            exact = x[r].to(torch.float16) @ w[cols].t()
            lp[r, cols] = exact.to(lp.dtype)
    # acceptance-relevant comparison: argmax equality per row
    if not torch.equal(lo.argmax(-1), lp.argmax(-1)):
        bad += 1
        print(json.dumps({"trial": trial, "argmax_mismatch": True}), flush=True)
    del w; torch.xpu.empty_cache()
print(json.dumps({"trials": 40, "argmax_mismatches": bad}))
json.dump({"trials": 40, "argmax_mismatches": bad}, open("/tmp/margin_equiv.json","w"))

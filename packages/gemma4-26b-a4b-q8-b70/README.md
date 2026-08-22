# Gemma 4 26B A4B Q8 — one-B70 reconstruction package

This is the user-facing front door for our one-card Gemma 4 Q8 research lane.
The lab moved this model from an early roughly `15.55 tok/s` one-card Q8
starting point to a valid `124.977 tok/s` high through our llama.cpp/SYCL,
MoE, and target-verified MTP work. Those historical endpoints are not a
like-for-like percentage comparison; use the linked result evidence for exact
identities.

> **Status: source-verified reconstruction candidate, not a beginner install.**
> The exact aggregate source stack now applies cleanly from its pinned base.
> The original record binary hash and historical local Q4_0 draft hash were not
> retained, and this audit host does not have the record's oneAPI 2026.0
> toolchain or a B70 replay slot. A rebuilt package must pass the full canary and
> cold-suite gates before anyone calls it reproduced.

Start with the [125 tok/s reproduction guide](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md).
Every required project artifact is linked inside our repository:

- [canonical aggregate patch](../../patches/gemma4-26b-a4b-q8-b70/README.md);
- [source restore/build helper](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh);
- [pinned model manifest](../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/model-manifest.json);
- [record evidence](../../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json);
- [full result packet](../../results/gemma4-26b-a4b-q8-b70/README.md).

The next promotion step is a clean one-B70 rebuild with oneAPI 2026.0, a newly
recorded Q4_0 draft digest, `512/512` canary pass, 12/12 cache-zero cold suite,
and retained source/model/binary receipts.

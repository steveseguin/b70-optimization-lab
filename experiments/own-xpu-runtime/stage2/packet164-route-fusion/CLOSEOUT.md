# Packet164 CPU route-fusion closeout

<!-- campaign-closeout -->

## Question and identity

October 19,2026: can packet141's bundle8 route cost expose≥0.4 ms/half of
latency for exact router-epilogue fusion? Unchanged quantized compressed
Flash-Next UD-IQ3_XXS, `iq3-p49-split32-v1`. No new device execution. Existing
24-layer rank0 diagnostic; one-card 58aj and two-card 136 rates anchor
counterfactual pricing only.

## Outcome

Inconclusive latency split; no device build selected. Route is already 24
single-kernel calls/half,0.792448 ms. The visible preceding gaps are 0.003073 ms.
Top-k, normalization, publication, activation and internal waits cannot be
timed separately from these clocks. At 20% transfer, even deleting route and
all fused-router work yields only+1.729% one-card. Raw full deletion exceeds 2%,
so a conditional one-card build brief is retained, with no READY or queue write.

## What worked

Complete raw-event replay reproduces the route/router costs, preserves all
per-site and sample rows, and exposes the original 31 plan-count mismatches.
Exact record reaggregation prices B, B+C and A+B+C independently. Both host
compilers pass two fresh route epilogue byte runs, ties and invalid-input
refusals. Ten corruption/real-evidence parser tests pass.

## What failed or remains uncertain

No clocks identify 0.4 ms removable latency; CPU arithmetic does not prove
last-group synchronization, full model exactness or speed. Packet141 remains
diagnostic after its analyzer refusal. Initial parser checks correctly refused
the stale declared counts; the final parser uses the retained actual plan
and explicitly keeps the original failure status. An initial compiler include
path mixed p141/p97 type trees; final builds use one p97 closure with byte-checked
identical route arithmetic and p141's unchanged p109 host header. No runtime
source was edited to resolve that build-only problem.

## Evidence and patches

[Analysis](ANALYSIS.md), [design/specification](DESIGN.md),
[CPU receipts](evidence/cpu.json), [prior audit](PRIOR.md),
[retention and replay](RETENTION.md), [conditional build brief](briefs/onecard.md).
Existing raw receipts are compressed byte-for-byte with original hashes.
New sources are CPU-only; all frozen existing packet/screen/ops trees remain
unchanged. No model weights, device or services were accessed.

## When to revisit

A distinct exact producer-completion mechanism with supported net≥0.612738
ms/token on the 48-layer 58aj line, or matched new evidence of≥0.4 ms/half
removable latency that can cover its synchronization cost. Preserve the
20% caveat, both compiler gates, real-arm/reset/consumer proof, whole-host
freeze,25 GB device disk floor and READY-last contract. No reopened 112 sorting
campaign or borrowed 80% transfer assumption.

# Packet 96 CPU model plan

Recorded before threshold results, 2026-10-18 UTC. Time budget starts at
02:24:55 UTC; finish by 03:04:55 UTC. No runtime implementation or device work.

Use packet31 `mtp_fp8_iq3` only: 256 unique positions, four prompts of 64.
Do not count the other draft variants or repeat receipts as independent samples.
Fit on incident-retrospective and code-review; test once on customer-email and
benchmark-analysis. Also report leave-one-prompt-out and first-32/latter-32
checks. No threshold or cost selection based on held-out outcomes.

Search fixed margin thresholds 0 through 16 in steps of 0.125, plus 32 and 64;
flag when logit1-logit2 < theta. Also search top-four-normalized probability
thresholds 0.25 through 1.00 in steps of 0.01, plus 1.01. That probability is
only a surrogate/upper bound: full-vocabulary normalization is unavailable.
Include never/always flags. Optimize mean cycle milliseconds on training
transitions; tie-break toward fewer flags, then margin, then smaller threshold.

Use packet85's composition, with current verification at i and next
speculation at i+1. Score only adjacent positions within each prompt/block;
no wraparound or cross-prompt edges. Report all position counts separately.
One interval produces one token, including a rescue. Retain raw model rates
and additive-millisecond and multiplicative transfers to the supplied 55.69
record anchor. These are forecasts across different identities, not results.

Cost scenarios: favorable sharing bound; partial sharing with a byte-reference
residual; conservative repeated arithmetic and one full extra state capture;
and serial M1 fallback. Keep new top-two extraction and selection costs explicit.
No fitted device latency coefficients. Current per-class costs are sampled
estimates; byte traffic does not prove runtime cost. Sweep cost sensitivity.

Decide seal-ready only for at least +1.5% under conservative costs on held-out
data, with supported memory and arithmetic. Otherwise close this lever, retain
all evidence and add a packet-local DO-NOT-REPEAT entry. All writes, including
the requested dated note under `notes/`, stay within this new folder because
the brief freezes existing trees. No CURRENT.md or shared index edits.

Opening `git pull --rebase` refused pre-existing unstaged work. Fetch found
HEAD == origin/main at 95b3f43a5. No stash, branch or worktree was used.

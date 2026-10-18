# Packet 118 — bundle 7, fixed draft prefix

Started 09:53 UTC on the four-card host. CPU-only preparation, 75-minute box.
The requested pull refused unrelated dirty files; fetch confirmed HEAD and
origin/main at `9c34b183ca822843c99eff83a1bc522d342efd40`. Foreign changes remain
untouched. Root had about 37 GB free; preparation stops below 25 GB.

This is a frozen copy of packet111 after packet111r `9b49c03e7`. Exactly two
compositions are prepared: bundle 6's combined fusion and repaired target-head
split, and that same bundle with packet114's preregistered 80,128-row draft
prefix. The previous prefix is 91,392 rows. The per-row arithmetic, lower-ID
argmax tie rule, full target head, BF16 KV and target verifier remain unchanged.
The draft shares the existing head allocation. KD recomputes only the selected
draft reference against the original target captures.

The prefix was chosen on non-benchmark text before packet114's device runs.
Its size is fixed: never retune N from benchmark prompts, outputs, acceptance
or timing. The two prefix sizes may have different draft acceptance. Exact
output remains `iq3-p49-split32-v1`; each selection must remain deterministic.

The smoke proposal is first: bundle 6 + prefix, twelve cold prompts, 64 tokens,
every token checked, including the known suffix-token regression. It is planned
on a temporary queue and handed to the coordinator; this task launches nothing.

The composites compare packet103's sealed selection (bundle 5, the record
line) against bundle 6 + prefix80128, independently on lanes A and B. Readiness
requires smoke success and at least 1.0% above **both** controls on **each** lane,
all prompts exact, matching control repeat acceptance and matching candidate
acceptance across fresh lanes. Identical selections cannot establish a gain.
The chain has a fresh packet118 output folder and finalized submission tooling
with the prefix preregistration disclosed in its notes.

All CPU work uses nice19, CPUs 8–15/24–31, Python `-B`, closed stdin, at most
8 GiB and packet94's serial compiler turn. Resource caps belong only to CPU
entry processes. Actual rank launch boundaries must retain unlimited address
space and unchanged inherited limits. Build budget: 250 MB. No GPU, service,
sudo, live queue, power, host memory, swap, page-cache or reboot action.

Preparation evidence and final status are recorded below as gates complete.

## Smoke milestone

Both GNU and Intel pass two fresh runs of the head, fusion and reset gates,
and two fresh runs for each prefix. Both real-shape ranks pass allocation
admission for each composition. Rank0 uses 28,144,182,388 bytes and rank1
31,425,985,242 bytes in both views; arena headroom is 4,068,072,332 and
786,269,478 bytes. No new head allocation is present.

All 22 startup/host-reference windows pass (eleven per composition), including
the actual CPU canary handshake and both KD argument paths. The run took
103.25 seconds, maximum child RSS 1,250,476 KiB. The first shape fixture tried
to call a private accessor; it was corrected to use emitted prefix metadata.
Its compile refusal is retained. No runtime arithmetic changed for this fix.

Exactly two views are sealed. `proposed-p118-smoke-B.txt` passes the real
planner on a private temporary queue. It ships before the remaining CPU
orchestration tests. Build size is about 208 MB, below 250 MB; root free is
about 38.8 GB. Device output, smoke result and speed remain unmeasured here.

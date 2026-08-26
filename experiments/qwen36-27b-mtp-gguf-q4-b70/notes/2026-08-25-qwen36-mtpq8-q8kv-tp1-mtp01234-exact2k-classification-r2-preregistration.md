# Qwen3.6 embedded-Q8/q8KV exact-2K classification R2

State: **preregistered, not launched**.

The failed R1 full curve produced a fresh, clean Q8-KV MTP0 control that did
not match the older F16-parent output at 2K. More importantly, the fresh Q8-KV
routes separated into three output hashes at that depth: one for MTP0, one for
MTP1, and one shared by MTP2/3/4. R1 therefore authorizes no curve or site
cells, but it leaves a bounded question: are those route-specific outputs
repeat-stable, or were they single-run noise?

R2 changes only the workload and campaign identity. It keeps the R1 model,
runtime, q8_0 target and draft KV, graph-off environment, fixture, sampler,
and route argv identities. A fresh MTP0 control both opens and closes the
campaign, bracketing the four speculative arms in six total server lifetimes.
Each arm receives exactly three uncached 128-token completions at exact active
context 2,048. The validator compares full token IDs within each arm, checks
the two MTP0 controls for temporal drift, and only then compares candidates
against the controls and records the first cross-arm divergence. It requires
conserved draft counters for every speculative request, and requires cache
zero and clean shutdown throughout.

The interpretation is frozen before launch. A three-repeat exact route earns
bounded grade B evidence, not grade A. Stable route-specific divergence earns
grade C negative evidence. Within-arm noise or any invalid mechanism/lifecycle
gate earns grade D. Grade A is unavailable because this packet has neither a
seven-depth curve nor the complete quality battery.

The R1 MTP0 hash `e11b5a...620d` is retained as a prior observation, not an
acceptance oracle; R2 is allowed to reproduce or change it. If the opening and
closing controls disagree, the frozen classification is temporal drift rather
than route divergence.

This packet fills zero site cells and cannot authorize curve expansion,
publication, a speed claim, protected replacement, graph evidence, or a record
submission. Its only purpose is to classify the R1 2K observation without
post-hoc promotion.

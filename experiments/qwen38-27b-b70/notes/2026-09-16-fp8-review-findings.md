# FP8 27B review, 2026-09-16: one-card package re-checked, two-card depth reclaim

Independent review of the September 15-16 one-card FP8 work, followed by one unattended campaign
([preregistration](2026-09-16-fp8-review-campaign-prereg.md),
[runner](../scripts/run-20260916-fp8-review-campaign.py), raw root `/mnt/fast-ai/bench-results/fp8-review-20260916/`,
receipts under [data/2026-09-16-fp8-review](../data/2026-09-16-fp8-review/)).

## What the review found before any GPU work

1. **A missing gate.** The one-card depth-5 package was qualified on the 12-prompt strict suite, a 2K-12K context
   screen, a chat quality suite and a 21-request no-MTP replay. It was never run through the 64-prompt sequential oracle
   that caught the two-card depth-2 "phantom first token" on September 3 (a scheduler bookkeeping defect that appears
   only after dozens of back-to-back requests). The package runs vLLM's async scheduling, the same mode that defect
   needed: vLLM 0.29 counts `qwen3_next_mtp` as an Eagle-type method and enables async scheduling for it by default.
2. **A launcher that only starts on this host's Docker.** Both package launchers compared `docker image inspect
   --format {{.Id}}` with the registry manifest digest. That equality holds only under Docker's containerd image store
   (this host). Under the classic image store, still the default on hosts upgraded from older Docker, `.Id` is the
   config digest (`845f559e…` for R310) and the launcher refuses to start with "Pull the pinned runtime first".
   Fixed in the one-card `serve.py` (`local_image_id()`: accept `.Id` equal to the pin or the pin listed under
   `RepoDigests`; the resolved local ID is recorded in `state.json` and used for container ownership checks). The
   two-card launcher (`serve.py` and the shared `run-server.sh`) has the same defect; those files are pinned by frozen
   evidence and are fixed with the two-card update below.
3. **Stale wording.** The package summary (and therefore the public model page) still said 13,824 tokens of context
   after the default moved to 16,384 on September 16. Fixed in `package.json`; pages regenerated.
4. **The draft shortlist is honest but worth stating plainly.** The 67,248-row draft shortlist was built from token
   frequencies over the lab's own text, system documentation and the image's Python sources (99.5% coverage of the
   suite output). It only limits what the draft may propose; the target still scores every token with its full head,
   so it cannot change an answer. It can flatter the benchmark's acceptance rate a little relative to unrelated text.
5. **The reference chain is sound.** Every one-card comparison in the package evidence used the R309+head-group no-MTP
   run (`fp8-tp1-35`) as its reference; the R310 no-MTP run (`fp8-tp1-54`) matches it 12/12, so the comparisons are
   effectively same-image.

## One-card package, re-tested through the shipped launcher

Server: `packages/qwen38-27b-fp8-tp1-b70/scripts/serve.py start --profile recommended` (R310, 16,384 context, MTP
depth 5, INT4 draft shortlist), one B70. Reference: a fresh R310 no-MTP server in the same run (`tp1-mtp0`).

| Check | Result |
| --- | --- |
| 64 prompts one at a time, vs no-MTP one at a time | **64/64** identical |
| Two more passes of the same 64 prompts, queued all at once | 64/64 and 64/64, cache zero |
| Strict 12-prompt suite vs the R310 no-MTP strict run | **12/12**, 53.31 tok/s (published pair 53.58 / 53.45) |
| 2K/4K/8K/12K prompts, three content types, two repeats, vs no-MTP | passed, every continuation identical |
| Chat quality suite (7 exact cases, repeat, 8K needle) vs no-MTP baseline | matched |
| 21-request replay at depth 5 with logprobs | zero token and zero logprob differences |
| `status`, then `serve.py stop` | clean, container removed |

Prefill and writing speed after 2K-12K prompts matched the published points (2,024 tok/s prefill at 2K, 56.5 tok/s
writing). **The recommended one-card profile holds up.** The `no-quantization` profile was not re-run in this
campaign (my runner reused a port too soon and its server never started); its existing strict 12/12 evidence stands
and the sequential oracle for it is queued with the context-length work.

## Two-card depth reclaim

Two B70s, R310 image, 33,024-token context, one user. Reference: a fresh R310 no-MTP server in the same run
(`tp2-mtp0`), which matched the frozen R304 two-card control 12/12 on the strict suite at 33.04 tok/s, so the new
image's arithmetic is the qualified one. Every candidate below passed **all four gates**: strict 12/12 identical to
no-MTP, 64/64 on the sequential oracle and 64/64 on each of two queued 64-prompt passes (cache zero), the 2K/8K/16K
context screen with every continuation identical to no-MTP, and the chat quality suite matching the no-MTP baseline.

| Server | Strict writing speed | Prompt reading 2K / 8K / 16K | Writing after 2K / 8K / 16K input |
| --- | ---: | --- | --- |
| No MTP | 33.04 | 3,763 / 3,535 / 3,384 | 32.7 / 31.8 / 31.0 |
| Depth 1, full-vocabulary draft head (the September 14 recipe) | 54.90 | 3,648 / 3,435 / 3,288 | 54.5 / 55.6 / 53.0 |
| Depth 1 + INT4 draft shortlist | 55.25 | 3,657 / 3,437 / 3,289 | 54.8 / 56.1 / 53.3 |
| Depth 3 + shortlist | 80.44 | 3,652 / 3,443 / 3,286 | 79.0 / 92.5 / 83.0 |
| Depth 4 + shortlist | 83.97 | 3,650 / 3,437 / 3,283 | 80.3 / 109.1 / 89.8 |
| **Depth 5 + shortlist** | **88.32** | 3,642 / 3,436 / 3,282 | 88.0 / 114.0 / 96.3 |

All speeds are tokens/s; strict is the class-balanced median of tokens 1-100 over the fixed 12-prompt suite. The
depth-1 control shows the runtime change itself costs nothing (54.90 here against 54.80 on the R304 service the same
morning). Depth 5 is +61% over the published recipe and above the September 4 depth-5 record (86.18) that was
withdrawn for the phantom first token; that phantom did not appear in 192 depth-5 answers here, nor at depths 3 and 4.

**Decision.** The two-card package moves to MTP depth 5 with the draft shortlist on R310 (`serve.py` rewritten in the
one-card style, `depth-1` kept as a profile, image-identity check fixed for both Docker image stores, compose
regenerated from the launcher's own `docker run` argv). The pair rule is satisfied by the acceptance replay of the
package launcher from an anonymous public-source download (`run-fp8-tp2-acceptance-session.py`, frozen by
`collect-fp8-tp2-acceptance-evidence.py`), which is the second fresh depth-5 server.

Receipts: [data/2026-09-16-fp8-review](../data/2026-09-16-fp8-review/) (`results.json` has every gate per stage).

## Follow-up campaign (September 17, 01:36-02:35 UTC)

[Runner](../scripts/run-20260917-fp8-followup-campaign.py), raw root `/mnt/fast-ai/bench-results/fp8-followup-20260917/`.

| Stage | Result |
| --- | --- |
| One-card `no-quantization` profile through the shipped launcher | 64/64 sequential oracle + 64/64 queued vs no-MTP; strict 12/12 at 51.77 tok/s; clean stop |
| One-card depth 5 at 24,576 context, 4,096-token prefill chunk | refused: 2.59 GiB of KV needed, 2.49 available |
| One-card depth 5 at 24,576 context, **2,048-token chunk** | starts (2.9 GiB KV, 27,136 tokens); strict 12/12 at 53.43 tok/s; 64/64 oracle + queued pass; 2K/8K/16K prompts exact vs no-MTP; prefill 2,023 / 2,014 / 1,933, writing 56.4 / 72.1 / 61.9 |
| One-card depth 5 at 32,768 context, 2,048-token chunk | refused: 3.13 GiB needed, 2.85 available (engine estimate: 28,288 maximum) |
| Two-card depth 6 + shortlist | every gate exact; 89.78 tok/s on the first 100 tokens, 73.4 tok/s over whole answers (depth 5: 88.32 / 75.0) |
| Two-card package acceptance replay (anonymous download at `5b494649f`) | model verify, image pull, start, strict 12/12 vs no-MTP at **88.49 tok/s**, practical 6/6 with exact repeats, clean stop, health before and after; [packet](../data/2026-09-17-fp8-two-card-depth5/) |

The smaller prefill chunk costs nothing measurable (prompt reading within 0.5% of the 16K profile at every length,
writing speed unchanged), so the one-card package moves to 24,576 tokens of context with a 2,048-token chunk; the
shipped launcher is verified at that setting in a third campaign. One receipt correction: the session runner wrote the
`git_worktree` field inverted; the receipt records the correction and the re-check (no `.git` directory).

## One-card 24K campaign (September 17, 02:38-03:11 UTC)

[Runner](../scripts/run-20260917-fp8-onecard-24k-campaign.py), receipts in [data/2026-09-17-fp8-onecard-24k](../data/2026-09-17-fp8-onecard-24k/).

| Stage | Result |
| --- | --- |
| Shipped one-card launcher, `recommended` at 24,576 context (2,048-token chunk) | 27,136 KV tokens; strict 12/12 at 53.43 tok/s; 64/64 sequential + 2x64 queued; 2K/8K/16K exact (prefill 2,026 / 2,017 / 1,934, writing 56.6 / 72.2 / 62.0); chat quality matched; logprob replay zero differences; clean stop |
| `no-quantization` (FP16 draft shortlist) at 20,480 context, 2,048 chunk, research launcher | starts (21,432 KV tokens); strict 12/12 at 51.77 tok/s; 64/64 sequential + queued. One server, not through the package launcher, so the shipped profile stays at 12,544 and this is a documented option |
| Two-card service start afterwards | **GPU fault** on `xe 0000:03:00.0` (copy-engine page faults, CAT error, coredump) 67 s into weight load; halted, no retry; the second identical fault in 24 hours, both two-card starts after long one-card sessions; `/mnt/fast-ai/bench-results/gpu-fault-20260917T0310/` |

The one-card package now ships 24,576 tokens of context (pair 53.43 / 53.43 tok/s).

## Night of September 17 (after the second fault; user chose to try the GPUs without a reset)

- **Fault pattern:** arm A, a two-card depth-5 start from idle, came up clean (88.35 tok/s, 12/12, clean stop); arm B,
  a two-card start right after 65 minutes of one-card and two-card research servers, also came up clean (88.09 tok/s,
  12/12) and is the running service. So the boot has now seen four clean two-card starts and two faults, and "after
  one-card work" alone does not reproduce the fault. The two faults followed much longer sessions (four to six hours
  of servers on the same boot); a stale devcoredump and a possible thermal or firmware component remain open. Fewer
  stop/start cycles per evening is still the practical rule.
- **Where one-card memory goes (from the vLLM source):** attention KV is exactly 64 KB per token (16 full-attention
  layers, 4 KV heads x 256); the hybrid page padding is 3%; the large item is speculative decoding itself, which keeps
  1+K copies of every GDN layer's recurrent state per request (48 layers x 3.25 MiB per copy): 0.9 GiB at depth 5
  against 0.15 GiB with no draft. vLLM avoids this for KDA models with a single checkpoint (RecoverSSM); a GDN
  equivalent would be the lossless way to 32K and beyond on one card.
- **Memory-utilization ceiling:** 0.985 is refused (29.84 GiB target vs 29.81 GiB free at startup); 0.983 is the most
  the card accepts, +0.24 GiB over the shipped 0.975, still about 40 MB short of 32K at depth 5. Probes: 30,720 at
  depth 5 and 32,768 at depth 4 (second night campaign).
- **Context ceiling probes (second night campaign):** 30,720 tokens at depth 5 with 0.983 memory passes every gate
  (strict 12/12 at 53.41 tok/s, 64/64 + queued, 2K/8K/16K exact, prefill 2,019 / 2,006 / 1,927). The 32K depth-4 probe
  and the graph-capture probe were lost to a false alarm: the driver's `Xe device coredump has been deleted` line (the
  23:10 dump expiring) matched the research launcher's fault pattern, which stopped a healthy server mid-suite. The
  pattern now matches only `coredump has been created`; the probes rerun in the third campaign.
- **Third night campaign, one card (through the shipped launcher unless noted):** `max-context` (30,720 tokens,
  0.983 memory) 53.51 tok/s, and `no-quantization` at 20,480 tokens 51.78 tok/s, each 12/12, 64/64 + queued,
  2K/8K/16K exact; both are package profiles now, with the earlier research servers as their pair (53.41 / 51.77).
  A research probe at 32,768 tokens with MTP depth 4 (0.983) also passed every gate at 50.97 tok/s: 32K on one card
  costs about 5% of writing speed; documented in the recipe, not shipped as a profile until replayed through the
  launcher. Graph capture with prompt embeddings was disqualified (9/12 outputs changed, 49.57 tok/s).
- **Broad-text draft shortlist (v3):** built from WikiText-103 (91.9M tokens) plus the CPython standard library
  (1.2M tokens), no lab text. Only 22,845 distinct tokens appear in that corpus, so every v3 list is really the whole
  corpus vocabulary; v3-top65536 covers 95.3% of the strict suite's output tokens against 99.8% for the shipped
  list (Jaccard 0.39). The shipped list is broader, not narrower, than general English plus Python; the two-card
  speed comparison in the third campaign puts a number on the difference: **85.19 tok/s with v3 against 88.36 with the
  shipped list in the same session** (both 12/12, 64/64, context exact). The shipped list is worth 3.6% on this suite;
  the package guide now says so.
- **LocalMaxxing:** the two-card record is submitted and approved as `cmu4zwfht07nzlq01tyj03f17` (88.407 tok/s pair
  median), bound by `data/2026-09-17-fp8-tp2-mtp5-r310-promotion-attestation.json`.
- **Tooling:** `fp8-gate-suite.py` runs the whole gate set against a live endpoint and freezes the evidence as one
  tarball packet; `2026-09-17-clean-host-replay-plan.md` lays out the four-B70 replay that would move the packages
  from candidate to published.

## One-card decode profile (September 17, 02:08 UTC)

In-worker torch/XPU trace of 60 decode steps at the shipped one-card settings
([overlay](../overlays/b70-step-profiler/b70_step_profiler.py), [summary](../data/2026-09-17-fp8-night3/tp1-decode-profile-summary.json)):

| Quantity | Value |
| --- | ---: |
| Wall per decode step | 78 ms (60 steps in 4.7 s; unprofiled the step is 75-90 ms) |
| Device busy | 74% of wall; idle 26% |
| oneDNN `gemm_kernel` (W8A16) | 92% of device time: 318 launches per step, 168 µs each, 53 ms per step |
| Effective weight streaming | 25.2 GiB per step in 53 ms, about 507 GB/s, roughly 83% of the card's bandwidth |
| Everything else on the device | GDN spec kernels 1.3 ms, attention 0.2 ms, fused norm/act kernels about 1.5 ms per step |
| Launches | about 1,330 device launches and 12,000 host operations per step |

So the GEMMs are near their memory-bandwidth ceiling and the only remaining lever on one card is the 26% of gaps:
fewer launches (fused epilogues; the 87 small memcpys per step, of which the host-embedding gather is a handful) or
graph replay. Graph replay is out for this recipe as long as the input embedding lives in host memory: the drafter
looks up its own sampled tokens inside the step, which a replayed graph cannot do (measured: 9/12 changed). A one-card
"speed" profile with the embedding back on the card and graphs on would trade 2.4 GiB of context for that 26%, and
on this platform the earlier capture probes were slower anyway. The two-card lane, with half the GEMM work per step
and the same overhead, has more of its step in gaps; its trace is next.

**Two-card decode profile (03:06 UTC, 30 steps, rank 0;
[summary](../data/2026-09-17-fp8-night3/tp2-decode-profile-summary.json)):** the profiled step is inflated to about
108 ms (two profiled processes), so only shares are read from it. Device busy 59%, idle 41%. The oneCCL PCIe ring
allreduce is **47% of device time** (134 calls per step at 223 µs, about 30 ms per step) against 28 ms per step for
all GEMMs (312 launches at 90 µs). Attention, GDN and the fused kernels are under 3 ms per step together. The lever on
two cards is therefore the collective, not the GEMMs: the recipe pins `CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4 GiB`
(since the first FP8 TP2 recipe on August 16, no recorded reason), which forces the ring "simple" kernel for every
message size and bypasses oneCCL's small-message and low-latency kernels. A same-session A/B with the default
thresholds and the low-latency path, each gated for exactness against its own no-MTP reference, is the next campaign.

**Collective A/B (07:11-07:18 UTC): stopped by a fault attributable to the experiment.** The same-session control
(pinned environment) ran cleanly at 88.50 tok/s. The first server with the oneCCL simple thresholds lifted (default
small-message kernels) faulted *both* cards at once about two minutes in: compute-engine page faults, CAT errors, a
scheduler timeout and two coredumps (`gpu-fault-20260917T0717`). The non-simple oneCCL paths use peer memory access
over PCIe, the class of the September 14 peer-IPC fault, so the pinned 4 GiB threshold is a guard and the collective
cannot be sped up by oneCCL algorithm selection on this host. Remaining levers for the two-card allreduce are fewer
calls per step (the model does two per layer) or a device-side collective that does not rely on peer access; both are
kernel projects. The service stays down until the user decides on a reset; this is the third fault on this boot.

The HTTP profiler endpoints do not deliver the engine worker's trace on this build (the API server drops the stop
connection before forwarding it); the overlay above profiles from inside the worker instead.

## Two-card collectives, campaign 2 (September 17, 13:26-14:04 UTC): allgather + fixed-order add

The two-rank allreduce (134 per decode step, 47% of device time in the two-card profile) replaced by one
`all_gather_into_tensor` plus `gathered[0] + gathered[1]` on each rank ([overlay](../overlays/b70-allgather-allreduce/b70_allgather_allreduce.py),
[runner](../scripts/run-20260917-fp8-comm2-campaign.py), results `/mnt/fast-ai/bench-results/fp8-comm2-20260917`).
The oneCCL environment is untouched (the pinned ring thresholds stay; no peer-access kernels, so not a retry of
campaign 1). A two-operand floating-point add is commutative, so the sum is the ring kernel's sum bit for bit, and
the strict gate confirms it:

| Server (two cards, R310) | Strict vs R310 no-MTP | tok/s | Ladder | 2K/8K/16K | Chat quality |
| --- | --- | ---: | --- | --- | --- |
| no MTP, overlay | 12/12 (same outputs as the ring allreduce) | 33.86 (was 33.04) | 64/64 + queued exact | exact | exact |
| depth 5 + INT4 shortlist + verifier rows, overlay | 12/12, 12/12 | 90.37, 90.28 (control 88.3-88.5) | exact | exact | exact |
| shipped service restored (no overlay) | 12/12 | 88.44 | | | |

So the exchange is lossless and worth +2.3%, not the ~25% the per-call latency suggested: the ring allreduce's
223 us per call is mostly the synchronisation both ranks pay for any collective, and the allgather pays it too.
The remaining two-card cost is the number of collectives per step, which the replicated drafter (no collectives in
the draft passes) addresses next. Shipping the overlay in the two-card package would take it to about 90.4 tok/s.

## Single-checkpoint GDN state, campaigns 1-2 (September 17, 14:16-15:20 UTC)

R311 kernel + `b70-gdn-checkpoint` overlay on one card at the shipped settings (`/mnt/fast-ai/bench-results/fp8-ckpt1b-20260917`, `fp8-ckpt2-20260917`):

| Server (one card, 24,576 context, depth 5) | Strict vs no-MTP | tok/s | Note |
| --- | --- | ---: | --- |
| R311 + checkpoint overlay (first kernel version) | 10/12 vs the 832-block reference, 10/12 vs an 896-block reference; the same two prompts diverge at the same tokens (341, 127) in both runs | 52.9, 52.8 | deterministic; both divergent outputs are coherent text, i.e. a rounding-level difference at one step |
| R310 no MTP, `--block-size 896` | 12/12 vs the 832-block reference | 19.4 | the attention block size does not change the no-MTP outputs |
| R310 depth 5, `--block-size 896` | 12/12 vs 832 and vs 896 references | 53.6 | the block size is innocent for the speculative path too |

The overlay's page grows by the stash (0.24 MiB), so vLLM raises the attention block from 832 to 896 tokens; the two
rows above rule that out as the cause. What remains is the kernel: the first version factored the per-token
arithmetic into a helper called from two places (replay loop, window loop). With icpx's default fast floating-point
model the two call sites need not compile to the same instruction sequence, so a replayed token can differ from the
same token computed as a window token by an ulp, and the committed state drifts from what the per-slot kernel stored.
The first campaign also found a Python-side error: the page-size alignment resolves the model class through the
registry (`Qwen3_5ForConditionalGeneration`), so the state-shape hooks have to be wrapped on every class that defines
them, not on `Qwen3NextForCausalLM` alone.

r311b (campaign 3, running): one loop over replayed rows then window tokens, with the per-slot kernel's statements
verbatim in the single loop body, so both are computed by the same code; the ckpt-3 runner also checks the
rewritten kernel without the overlay against the R310 reference.

## Single-checkpoint GDN state, campaign 3 (September 17, 15:20-15:56 UTC): r311b is lossless and reaches 32K

R311b (one loop body for replayed rows and window tokens) on one card, shipped settings unless noted
(`/mnt/fast-ai/bench-results/fp8-ckpt3-20260917`, receipts in [data/2026-09-17-fp8-ckpt3](../data/2026-09-17-fp8-ckpt3/)):

| Server (one card, depth 5, INT4 shortlist, host embedding, verifier rows) | Strict | tok/s | Ladder | 2K/8K/16K | Chat quality | KV budget |
| --- | --- | ---: | --- | --- | --- | --- |
| R311b, per-slot protocol (no overlay), 24,576 | 12/12 vs the R310 832-block reference | 53.49 | | | | 26,178 tokens (as R310) |
| R311b + checkpoint overlay, 24,576 | 12/12, 12/12 vs the 896-block no-MTP reference | 54.28, 53.96 | 64/64 + two queued passes exact | exact | exact, baseline match | **38,845 tokens** |
| R311b + checkpoint overlay, **32,768** at 0.975 | 12/12 | 54.36 | | exact | | 40,140 tokens (1.23 requests of 32K) |

So the single-checkpoint state is lossless at every gate, costs nothing in speed (slightly faster: one state write per
step instead of six), and turns the one-card KV budget from 26K into 40K tokens at the same 2.9 GiB. 32K context at
depth 5 on one card is now a plain 0.975 setting (the R310 package needed 0.983 for 30,720). The 30,720-token probe
did not run: the corpus tool refused to build a 30,720-token prompt without repeating its source
(`/tokenize did not return enough valid numeric tokens`); the night-2 campaign's 30,720 probe used the same corpus,
so this needs a look at the tool, not the server. Left for the one-card package acceptance.

## Two-card campaign 3 (September 17, 20:05-21:15 UTC): replicated drafter, single-checkpoint state on two cards

All servers carry the shipped allgather-allreduce overlay (`/mnt/fast-ai/bench-results/fp8-comm3-20260917`):

| Server (two cards, depth 5, INT4 shortlist, verifier rows) | Strict | tok/s | Ladder | 2K/8K/16K | Chat quality |
| --- | --- | ---: | --- | --- | --- |
| no MTP, `--block-size 896` (references for the checkpoint page) | 12/12 vs the 832 reference | 33.89 | recorded | recorded | recorded |
| replicated drafter, all parts ([overlay](../overlays/b70-replicated-drafter/b70_replicated_drafter.py)) | 12/12, 12/12 | 86.72, 85.93 | exact | exact | exact |
| single-checkpoint state (R311b + [overlay](../overlays/b70-gdn-checkpoint/b70_gdn_checkpoint.py)) | 12/12, 12/12 vs 896 refs | 90.40, 90.15 | exact | exact | exact |
| both | 12/12, 12/12 | 86.71, 86.35 | exact | exact | exact |

The replicated drafter works as designed (drafts identical on both ranks, outputs identical) but loses 4%: replicating
the drafter's MLP doubles that GEMM per card (about 1 ms per draft pass, five passes per step), more than the three
collectives it removes (about 0.2 ms each). Campaign 4 tries the lighter selections (embedding, fc and head only;
embedding and fc; head only). The single-checkpoint state is exact on two cards and speed-neutral (90.4 vs the
90.3-90.6 control): each card writes one state block per step instead of six, but the two-card step is bound by the
collectives, not by those writes, and memory was never the two-card constraint (268K-token KV budget). It stays a
research result; the two-card package keeps R310.

## Two-card campaign 4 (September 17, 21:09-21:30 UTC): which drafter parts to replicate

All exact (12/12, 12/12 vs the comm-2 no-MTP reference); speeds are the two strict runs (`/mnt/fast-ai/bench-results/fp8-comm4-20260917`):

| Replicated drafter parts | tok/s | Against the allgather control (90.3-90.6) |
| --- | ---: | --- |
| embedding, fc, MLP, head (comm-3) | 86.72, 85.93 | -4% (the MLP GEMM doubles per card) |
| embedding, fc, head | 89.25, 88.96 | -1.5% |
| embedding, fc | 89.72, 89.45 | -1% |
| head | 90.15, 89.59 | -0.4% |

Removing the drafter's collectives does not pay: the exchanges it removes are short (a few hundred microseconds each,
five passes per step) and every replicated part costs at least as much in extra per-card compute or in the larger
unsharded lookups. Closed; the drafter stays sharded. The overlay remains for reference.

## One-card long-prompt probes (September 17, 21:30-22:15 UTC): exact to 36,864 tokens

With the long unrepeated corpus ([data/2026-09-17-long-corpus](../data/2026-09-17-long-corpus/), 62K+ tokens per
class, built by [build-long-corpus.py](../scripts/build-long-corpus.py)), the no-MTP server at 40,960 context
(R311b, 0.983) recorded continuations at 2,048 / 8,192 / 16,384 / 24,576 / 30,720 / 36,864 tokens (three classes,
two repeats); both package profiles reproduced them token for token
([probe-1](../data/2026-09-17-fp8-probe1/), [probe-2](../data/2026-09-17-fp8-probe2/); the recommended profile
used the [five-length subset](../scripts/subset-prefill-baseline.py) of the same reference since it serves 32,768):

| Prompt tokens | 2,048 | 8,192 | 16,384 | 24,576 | 30,720 | 36,864 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No MTP: reading tok/s / writing tok/s | 2,215 / 19.3 | 2,125 / 18.9 | 2,025 / 18.5 | 1,941 / 18.2 | 1,884 / 17.9 | 1,829 / 17.7 |
| `recommended` (32,768): reading / writing | 2,032 / 59.2 | 2,020 / 76.8 | 1,935 / 65.7 | 1,857 / 39.7 | 1,804 / 37.5 | |
| `max-context` (40,960): reading / writing | 2,026 / 59.2 | 2,011 / 76.9 | 1,930 / 65.8 | 1,853 / 39.8 | 1,799 / 37.5 | 1,748 / 38.4 |

So the 32K claim now rests on 30,720-token prompts, and the 40,960 profile on 36,864-token ones. The writing speed
after a prompt drops from 65 tok/s at 16K to 40 at 24K while the no-MTP rate barely moves (18.5 to 18.2): the cost is
in the speculative verify pass (six query rows against a 24K+ KV cache per step), the next one-card lever.

## Where the writing speed goes after long prompts (September 17, 23:20 UTC): the verifier's per-row attention

Per-step device time from the per-prefill profiler ([overlay](../overlays/b70-step-profiler/b70_step_profiler.py),
`B70_PROFILE_BY_PREFILL=1`) on the one-card 32K recipe, 30 decode steps after one prose prompt of each length
(`/mnt/fast-ai/bench-results/fp8-lc1-20260917/prof-*-summary.json`):

| Context | Device busy per step | FA2 attention (cutlass) per step | Calls per step | Per call | GEMMs per step | GDN spec kernel |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 16,384 | 76.1 ms | 14.8 ms | 106 | 140 us | 53.8 ms | 1.5 ms |
| 24,576 | 82.6 ms | 21.2 ms | 106 | 201 us | 53.8 ms | 1.3 ms |
| 32,768 | 89.1 ms | 27.6 ms | 106 | 261 us | 53.8 ms | 1.2 ms |

Two things are true at once:

- **Content dominates the headline.** The per-class after-prompt writing speeds vary far more with the text than
  with the length (prose: 34.6 tok/s after 8K, 69.1 after 16K; docs: 44.2 after 2K, 76.9 after 8K), because the draft
  acceptance depends on how predictable the continuation is. Only the code class declines smoothly with length
  (85.9, 77.1, 65.7, 60.7, 54.5, 38.4 tok/s from 2K to 36K), and that is the context cost.
- **The context cost is the verifier's attention.** The [verifier-rows overlay](../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_verify_rows.py)
  keeps depth-5 verification bit-identical to decode by issuing one single-query attention call per draft row above
  1,536 keys: six calls per attention layer, 106 per step, each rereading the whole cache (at 32K, 16 layers x 6 rows
  x 128 MB = 12 GB per step, 24 ms at 500 GB/s). It grows linearly: +6.4 ms per 8K of context on a 76 ms step, i.e.
  about 8% per 8K. The GEMMs (54 ms) and the GDN kernels do not move with context.

The lever is a multi-row attention kernel that reads each cache tile once for all six rows while computing every
row with the single-row arithmetic (the census found the stock multi-row path differs from single-row above ~1,980
keys). If its output equals the six single-row calls bit for bit, the verifier cost falls from 6 reads to 1: about
-12 ms per step at 16K and -22 ms at 32K (+16% and +25% writing speed at those lengths), nothing below 1,536 keys.
That is a kernel project in the FA2 XPU (cutlass/sycl-tla) source, of the same size as the GDN checkpoint work.

## lc-2 and the r312c build sessions (September 18, 01:40-02:30 UTC): the candidate never started

Campaign lc-2 ([runner](../scripts/run-20260918-fp8-lc2-campaign.py), receipts in
[data/2026-09-18-fp8-lc2](../data/2026-09-18-fp8-lc2/), raw `/mnt/fast-ai/bench-results/fp8-lc2-20260918`) was meant to
be the first end-to-end run of the one-pass verifier attention: a no-MTP arm on the new image to build R312 references,
then the depth-5 candidate with the `b70-fa-multiq` overlay against them. Only the first arm ran.

**The reference arm (`tp1-r312-mtp0`, r312b image `sha256:627aade4…`, no MTP, 32,768 at 0.983, one card).** Ready in two
minutes, every self-referenced gate passed, and it reproduced the R311b *speeds* almost exactly -- but not the R311b
*outputs*:

| Gate | Result |
| --- | --- |
| Strict vs the R311b 896 no-MTP reference (`fp8-ckpt2-20260917/tp1-mtp0-b896-strict`) | **9/12**, 19.36 tok/s against the reference's 19.43 |
| 64-prompt ladder, two passes | 64/64 and 64/64 (self), 19.30 and 19.29 tok/s aggregate |
| Long screen 2K/8K/16K/24K/30K, three classes, two repeats | 30/30 rows, reading 2,217 tok/s at 2K down to 1,887 at 30,720, writing 19.25 down to 17.9 |
| Chat quality, two repeats | pass (no baseline compare) |

The three prompts that moved are `architecture-tradeoff` (token 341), `customer-email` (token 124, and the answer ends
8 tokens shorter) and `risk-register` (token 127) -- so this is exactly the r312a/b defect already written up in
[DO-NOT-REPEAT](../DO-NOT-REPEAT.md): an image whose upstream flash-attention library was rebuilt from source computes
slightly different numbers, and every reference built on it is worthless to everything else. The speeds above say the
rebuild costs nothing; the 9/12 says it may not ship.

**The candidate (`tp1-r312-multiq`) never reached readiness.** The overlay looks the op up as
`torch.ops._xpu_C.paged_decode_multiq`, and the r312b image had built it into `_vllm_fa2_C` instead, so the server
exited on its own guard before loading weights:

```
RuntimeError: b70_fa_multiq: the kernel library has no paged_decode_multiq (needs the r312 build)
```

There is therefore **no candidate number of any kind** from lc-2 -- no strict pair, no ladder, no writing speed after a
long prompt. The runner did the right thing (one attempt, no retry) and went straight to the service restore.

**The service came back clean.** Unit `fp8-service-20260918-lc2`, state `fp8-lc2-20260918/service`, strict **12/12**
against the comm-2 no-MTP reference at **90.52 tok/s** (that reference itself runs at 33.86 tok/s without MTP). The
two-card package is unaffected by any of this.

### The r312c rebuild: three sessions, two cmake bugs and a port race

r312c is the correction: the new op goes into `_xpu_C` with its own device library and the upstream attention library
stays the upstream binary. Getting it to compile took three unattended sessions, each of which stops the service,
builds, and restores it (`/mnt/fast-ai/bench-results/r312-session4*.sh`, logs `r312-session4*.log` and
`fp8-r312-session4*/build.log`).

- **Session 4 (02:23-02:24 UTC) -- wrong kernel set, then a missing include.** The builder did not pass a config, so the
  top-level `VLLM_PAGED_DECODE_CONFIG` default resolved to the full **118-translation-unit** kernel set, and the first
  two of them failed at once: `fatal error: './collective/chunk_prefill_mainloop.hpp' file not found`. The multiq
  library simply never had the upstream attention directory on its include path. Two fixes: the builder now passes
  `-DVLLM_MULTIQ_DECODE_CONFIG` explicitly (commit `6e1a2f615`, `scripts/build-vllm-xpu-kernels-xpu-c-only.sh`), and the
  dev tree adds `target_include_directories(... csrc/xpu/attn/xe_2)` (dev commit `825959e`).
- **Session 4b (02:27 UTC) -- the config name did not resolve.** cmake stopped before compiling anything:
  `Paged decode kernel config not found: paged_decode_qwen38.conf / Available presets: paged_decode_full.conf,
  paged_decode_default.conf`. The multiq configure only accepted a path, while the top-level `CMakeLists.txt` also
  resolves a bare preset name inside `kernel_configs`. Fixed in dev commit `3b1e5c5`, re-exported into the lab patch as
  `c6cb8b9a5`.
- **Session 4b also lost the service.** Its restore ran immediately after the graceful stop and the listener was still
  holding the port: `ERROR: [Errno 98] Address already in use`, unit `fp8-service-20260918-r312c2` dead one second after
  it started. The service stayed down until session 4c picked it up three minutes later. Every session script now polls
  `ss -ltn` until 18124 is free before starting the service -- the same lesson as the September 16 acceptance run, in a
  new place (new [DO-NOT-REPEAT](../DO-NOT-REPEAT.md) row).
- **Session 4c (from 02:30 UTC) is the live one.** `RESUME=1`, `JOBS=2`, **32 build objects** where session 4 had 144, then the image
  `neural-download/vllm-openai-xpu:qwen38-fp8-v0290-r312c-multiq`, then the census at v-tile 64 and 256 against the
  upstream lone-row path, then the service back as unit `fp8-service-20260918-r312c3`
  (state `fp8-r312-session4c-20260918/service`). Queued behind it: lc-3
  ([runner](../scripts/run-20260918-fp8-lc3-campaign.py)) **only if every census case is bit-exact**, then the
  MiniMax-H3 first-light session.

## Left open

- **The r312c census (running now).** Session 4c builds the 32-object `_xpu_C` multiq library, then runs the census at
  v-tile 64 and 256 against the upstream lone-row path. Every case must be bit-exact (`all_equal`, `max_abs == 0.0`,
  and the repeat check) or nothing downstream runs: that is the gate the chain script reads.
- **lc-3 (queued, gated on that census).** The same three stages as lc-2 on the r312c image
  ([runner](../scripts/run-20260918-fp8-lc3-campaign.py), receipts `/mnt/fast-ai/bench-results/fp8-lc3-20260918`):
  fresh R312 references from a no-MTP arm that must be **12/12** against the R311b reference this time, then the
  depth-5 candidate with `b70-fa-multiq` -- strict twice, ladder, the long screen, quality and the logprob replay.
  The number to look for is the writing speed after a long prompt against R311b's 66 tok/s at 16K and 40 at 24K.
- **Then packaging, only if it is both exact and faster.** A one-pass verifier that is bit-identical but not faster is
  a closed experiment, not a package revision; the one-card package keeps R311b until lc-3 shows both.
- Why `0000:03:00.0` faults on a two-card start after hours of one-card work (twice today); the health probe passed
  both times minutes earlier. Until the user decides on a reset, no GPU work.
- One-card context above 40,960 tokens: the single-checkpoint state (r311b) settled 32K lossless at 0.975 and 40,960
  at 0.983 (KV budget 45,139 tokens). The engine refuses 46,080 at depth 5 and 0.983 (3.20 GiB needed, 3.09 free; its
  estimate of the ceiling is 44,800), so 40,960 is the shipped maximum and about 44K the hard one; beyond that the
  attention KV itself (64 KB per token) is the limit, and an FP8 cache is off the table (not lossless).
- A 30,720-token-plus prompt probe needs a longer unrepeated corpus for bench-prefill-followup (the AMD-transfer
  corpus tokenizes shorter than 30,720); the 2K/8K/16K screen is what every 32K gate ran.
- Two-card: the replicated drafter (campaigns 3-4) is exact but never faster; the collective count per step is set by
  the 64 target layers, so the next two-card lever would be fusing the per-layer allreduce pairs (out_proj + MLP down)
  or overlapping them with compute, both deeper changes than an overlay.
- The R311b image must be pushed to ghcr by the user (`publish-r311b-image-ghcr.sh`); the one-card package pins its
  digest already, and the one-card LocalMaxxing payload is held until then.

# Laguna S 2.1 lane pause closeout

Date: 2026-08-08 America/Toronto

Status: **paused at the user's request; no active service or authorized
experiment.**

Laguna work is stopping here so the four B70s and the workspace can be used
for other models. This is a pause, not deletion: the promoted result,
diagnostic work, rejected candidates, source commits, patch bundles, and raw
artifacts remain preserved.

## Final disposition

- The promoted Laguna result remains **125.4619731637751 tok/s** under
  conventional 99-interval accounting, with 13/13 exact and cache-zero rows.
  Its LocalMaxxing receipt is `cms9wuuf300cqpm01t5i285tq`.
- The August no-drafter graph fix remains diagnostic. It measured
  `63.532897 tok/s` at 32,640 tokens, but its full runner did not pass the
  corrected harness and its output was not exact against the required
  authority. It is not a promoted baseline.
- The estimated ~7,600-token speculation crossover remains an interpolation
  from separate services, not a measured shipping threshold.
- The single-service M12-to-M1 cutoff candidate at vLLM `00c8bbbb5` is
  rejected. Its corrected transition request diverged from the pinned Q1
  oracle at output index 96, with 32/128 positions different. Its timing is
  invalid and no 8,192 policy run follows from it.
- The 24,576-token engine failure remains reproduced and unexplained. It is a
  bookmark for a future investigation, not pending work in this pause.
- No new LocalMaxxing submission was made from the August long-context work.

The exact dynamic-cutoff evidence is in
[`2026-08-08-dynamic-dflash-context-cutoff-preregistration.md`](2026-08-08-dynamic-dflash-context-cutoff-preregistration.md).
The corrected source bundle, patch checksums, and raw artifact checksums are in
[`2026-08-08-dynamic-cutoff-manifest.md`](../../../patches/laguna-s-2.1-xpu-b70/2026-08-08-dynamic-cutoff-manifest.md).
Its prerequisite `561698049` is preserved by the verified bundle in the
[`August 4--7 diagnostics manifest`](../../../patches/laguna-s-2.1-xpu-b70/2026-08-07-diagnostics-manifest.md).

## Preserved restart point

- main notebook: branch `experiment/laguna-kernel-loop-20260728`, closure
  parent `b2bd1fe93`;
- dynamic-cutoff vLLM worktree:
  `/home/steve/src/laguna-vllm-shared-elementwise-m12-20260731`, branch
  `experiment/laguna-shared-elementwise-m12-20260731`, commit `00c8bbbb5`;
- matching XPU-kernel worktree:
  `/home/steve/src/laguna-xpu-kernels-shared-elementwise-m12-20260731`, commit
  `99886d7`;
- promoted record reconstruction:
  [`repro/laguna-s-2.1-int4-b70-125tps-20260731/`](../../../repro/laguna-s-2.1-int4-b70-125tps-20260731/);
- lane resume and complete record identity:
  [`RESUME.md`](../RESUME.md).

The main notebook branch is local work ahead of its remote, and the source
candidate is not contained by a configured remote branch. The source is still
recoverable from the verified Git bundles recorded in the manifest. Do not
reset, clean, rebase, or repurpose these worktrees when bringing up another
model.

## Runtime handoff

At closure, no Laguna/vLLM/Ray/benchmark process or experiment listener was
running. All four GPUs were at their ordinary idle allocation of approximately
42.9 MiB. No reset, reload, reboot, temporary swap, or privileged cleanup is
pending. Recheck processes, listeners, Git status, and device health before
the next model launch because this observation is only a closure-time fact.

## If Laguna is reopened

Treat it as a newly authorized experiment. Start from the promoted static
record or a fresh identity-matched control, not from a failed dynamic timing.
For long-context work, the first obligations are correctness and stability:

1. reproduce the no-drafter graph arm under the corrected complete harness and
   pinned oracle;
2. localize the 24,576-token engine failure independently;
3. explain the dynamic transition's output-index-96 divergence and prove
   audited M1 replay before measuring a cutoff policy; and
4. measure matched crossover points before assigning a production threshold.

None of these is an active action while the lane is paused.

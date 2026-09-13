# R308 qualified for one active request on one B70

The functional R308 image
`sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba`
passed the registered 4B and 9B boundary and strict identity gates. The
[frozen qualification packet](../data/2026-09-13-r308-single-request-qualification/summary.json)
limits this result to TP1, fixed MTP depth 3, one active request,
`MAX_NUM_SEQS=1`, the declared W4A16 checkpoints, V1 runner, class padding off,
and prompt caching off. Boundary tests use context capacity 256; strict suites
use capacity 1024 and batched-token budget 1024. This is not qualification for
32K, concurrent speculative serving, TP2, dynamic depth, or forced preemption.

| Gate | 4B | 9B |
| --- | ---: | ---: |
| Same-image MTP0 boundary capture and repeats | 60/60 | 60/60 |
| Fresh MTP3 boundary server A | 52/52 | 52/52 |
| Fresh MTP3 boundary server B | 52/52 | 52/52 |
| Strict MTP0 A versus B | 12/12 | 12/12 |
| Strict MTP3 A versus B | 12/12 | 12/12 |
| Strict MTP3 A versus MTP0 A | 12/12 | 12/12 |
| Strict MTP3 B versus MTP0 A | 12/12 | 12/12 |

Each boundary compare covers L8–27 and six exact token-ID tails of L14 at
offsets 236–241, twice. The strict comparisons use complete numeric arrays,
not rendered strings: 6,144 IDs per 4B arm and 5,902 per 9B arm. The 9B
customer-email response naturally stops at 270 tokens on all four servers;
the other responses reach the 512-token cap. All cache metadata is zero,
canaries pass, and runtime image/model/launch identities agree with the declared
scope. Both models have four independent strict server starts. Captured image
contracts pass; completed postflights show two normal devices, successful
compute and both allreduce ranks, and no new kernel-fault signatures. The
qualification host has two cards; the measured serving profile uses card 0 only.

The final independent audit recalculated all 4B numeric comparisons and all
24 comparison artifact pins, supplementing the same checks for 9B. All 164
copied-source hashes in the
[source manifest](../data/2026-09-13-r308-single-request-qualification/source-manifest.json)
match the archived files. The collector reports `passed=true`; its legacy schema
name contains `r307`, while its explicit candidate and image identify R308.

## Repair mechanism and retained negative evidence

R307 alone failed ten 9B single-request rows. Lifecycle instrumentation showed
accepted count 2 surviving non-resumed removal, then becoming 1 at re-add and
reaching the final one-token runner as 1. R308 retains the count by request ID
across that pause, synchronizes the accepted-count copy before eviction, and
restores the request's current runner row after async corrections. Finished and
resumed IDs invalidate saved counts. The
[lifecycle evidence](../data/2026-09-13-r308-lifecycle-negative/summary.json)
and [negative campaign](../data/2026-09-13-r307-r308-negative-qualification/summary.json)
remain frozen; instrumented diagnostics were not themselves functional fixes.

The [repair cross-check](../data/2026-09-13-r308-repair-cross-check/summary.json)
verifies all ten old failures are exact under R308, with identical numeric
inputs across 26 cases and unchanged same-image MTP0 outputs across all 20
base prompts. This separates the repair from oracle drift. Earlier c4 failures
remain negative evidence; nothing here promotes concurrency.

## Recorded throughput, not a new headline

Conventional 99-interval class-balanced medians from these strict receipts:

| Model | MTP0 A / B (tok/s) | MTP3 A / B (tok/s) |
| --- | ---: | ---: |
| 4B | 102.567 / 102.368 | 191.579 / 191.169 |
| 9B | 64.417 / 64.347 | 123.816 / 123.696 |

These are supporting measurements from the qualification campaign, not a speed
gate or a new promoted record. R304 defaults and historical runtime/metric
attribution remain unchanged.

## Source reconstruction and publication boundary

The [rebuild helper](../../qwen38-27b-b70/docker/rebase-v0290/rebuild-r308-overlay.sh)
reconstructs public R304 through R307 to R308. Dependencies are the
[R307 Dockerfile](../../qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r307-gdn-state-handoff),
[R306 staging overlay](../../qwen38-27b-b70/docker/rebase-v0290/r306-gdn-active-width-contiguous-staging.py),
[R307 handoff overlay](../../qwen38-27b-b70/docker/rebase-v0290/r307-gdn-state-handoff.py),
[R308 Dockerfile](../../qwen38-27b-b70/docker/rebase-v0290/Dockerfile.r308-gdn-state-resume),
and [R308 resume overlay](../../qwen38-27b-b70/docker/rebase-v0290/r308-gdn-state-resume.py).
All 17 rebuilt runtime digests match the
[committed contract inventory](../../qwen38-27b-b70/docker/rebase-v0290/r308-contract-digests.sha256)
(hash `a45dddb714460c1131e22f5da0e9cafe5954ecb54ba823a4bfbed0446f698446`).
The [seven lifecycle tests](../tests/test-r308-state-resume.py) pass.

At this note's capture, public image publication and remote verification remain
pending. Local qualification and source reconstruction are not public download
verification or clean-host certification. This note grants no publication or
performance promotion by itself.

## Replay the registered qualification

These host-specific lab commands require the measured image, pinned model paths,
and an idle host. Run sequentially with new output roots. They are the full
qualification, not the optional end-user serving commands. The first runner
owns both models' boundary checks and the four-server 9B strict suite; the second
adds the four-server 4B strict suite. The collector retains the historical c4
failure and rebuild evidence as separate inputs.

```bash
python3 experiments/qwen35-4b-b70/scripts/run-20260913-r307-qualification.py \
  --candidate r308 \
  --image sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba \
  --inventory experiments/qwen38-27b-b70/docker/rebase-v0290/r308-contract-digests.sha256 \
  --concurrency 1 --max-num-seqs 1 \
  --out /mnt/fast-ai/bench-results/r308-single-request-replay
RUN_ROOT=/mnt/fast-ai/bench-results/r308-4b-strict-replay \
  bash experiments/qwen35-4b-b70/scripts/run-20260913-r308-4b-strict.sh
python3 experiments/qwen35-4b-b70/scripts/summarize-r307-qualification.py \
  --candidate r308 \
  --image sha256:b9bbb5190f6dd47973501e61aa129706c92345b310eeec4537a20256eba424ba \
  --inventory experiments/qwen38-27b-b70/docker/rebase-v0290/r308-contract-digests.sha256 \
  --single-root /mnt/fast-ai/bench-results/r308-single-request-replay \
  --four-b-strict-root /mnt/fast-ai/bench-results/r308-4b-strict-replay \
  --failed-root /mnt/fast-ai/bench-results/r307-qualification-20260913 \
  --rebuild-root /mnt/fast-ai/bench-results/r308-rebuild-20260913 \
  --out /mnt/fast-ai/bench-results/r308-replay-summary
```

# Scoped coding trial: closed without a patch

The single authorized Qwen3.8-27B-FP8 attempt completed 12 model requests in
114.54 seconds, exhausted its step budget and made no edits. The exported patch
is empty; no acceptance submission occurred. This is **0/1 completed repairs**,
not a passing coding result. No retry, hint, budget increase or server restart
was used. Five of the original eight coding cases remain unused.

All replies completed naturally with explicit zero cached tokens and matching
input/output token accounting. Outputs ranged from 25 to 73 tokens, below the
512-token cap. Neither that cap nor the 120-second request deadline caused this
failure. Independent review found one XML-format response followed by eleven read-only
commands. The relevant function was visible by request 3, yet inspection continued;
six tool outputs were truncated. No further tuning campaign is queued on this task.

The narrowed workflow itself worked: 12 pinned files totaling 202,639 bytes
were admitted while preserving the 50 GiB disk reserve. Real isolated CPU
containers rejected the historical bug and accepted the historical fix; the
selected collector/stream regressions passed in both. All 135 shared-worker
CPU tests passed, together with five lifecycle and three request-guard controls.
The actual model attempt preserved the source repository and baseline unchanged.
Scope selection and smaller budgets make this a separate evidence class from
the earlier full-repository failures; no controlled improvement is claimed.

The frozen eight boundary checks and one representative bash-format canary
passed on this load. The supervisor started one historical R276 model container,
sent one graceful SIGINT after the task, and exited successfully. All four B70s
passed the final health check; no new kernel fault or OOM occurred. Full model
and launch identities are retained in [the frozen plan](runtime-plan.json) and
`results/server/`. This does not qualify the newer R314 serving package.

## Decision

Park local-worker autonomy and model-memory integration. Preserve this negative
result without rerunning it. The useful delivered tools are the exact-source
[lab navigator](../../lab-navigator-20261007/README.md), the explicit scoped
snapshot workflow, and verified source preparation for
[LFM2.5](../../../repro/lfm25-26b-q8-b70/README.md). Use the navigator with source
review: it covered all required passages for only 4/6 questions in each frozen
split. Summaries do not replace exact archives, and the other host's incomplete
memory confirmation remains incomplete.

LFM's public source preparation now replays from a clean committed archive and
verifies all 3,452 extracted files. The complete strict-result toolchain identity,
public runtime rebuild and clean-host certification remain open. Older local
binaries are not silently substituted for the qualified build. Package checks
now replay frozen FP8 evidence with explicit, narrowly proved source-drift
records; acceptance of changed runtime inputs remains pending.

LTX and Flash-Next remain parked and preserved. No power, RAM exclusion, swap,
page-cache or driver settings changed. All 80 temporary RAM files were rehashed and released after shutdown; the verified
cold copy is retained and EX400U is unmounted.

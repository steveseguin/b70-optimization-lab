# Laguna persistent KV-cache views preregistration

Date: 2026-07-25 America/Toronto

Status: Gate 1 complete; Gate 2 tooling frozen before any XPU diagnostic.
No Gate 2 model load, prompt, generation, endpoint campaign, payload, or
submission has started.

## Pre-implementation lifecycle addendum

An independent source audit after preregistration, but before candidate code,
found that vLLM binds a temporary minimal KV cache during profiling, clears it,
and later binds the final runtime cache. A cache seeded from the profiling
allocation cannot legally survive that existing lifecycle transition.

The candidate may therefore expose one explicit invalidation method which is
called only by the existing profiling-cache cleanup/final-cache binding
lifecycle. Invalidation must discard the entire cached-view state; partial
state is never retained. The next eligible use after that explicit lifecycle
event may initialize one new complete state from the newly bound cache.

This is not a per-use rebuild or fallback allowance. Outside that audited
lifecycle call, any initialized source or view drift still raises immediately.
Gate 1 must additionally prove that:

- stable use cannot rebuild;
- source drift cannot trigger an implicit reset;
- explicit lifecycle invalidation clears the complete state; and
- exactly one subsequent initialization is allowed before strict validation
  resumes.

## Hypothesis

Each of Laguna's 48 piecewise eager attention boundaries currently recreates
the same KV-cache aliases in `FlashAttentionImpl.forward`:

```text
kv_cache.transpose(1, 2).split(head_size, dim=-1)
```

It then runs singleton-stride canonicalization on both aliases. The preceding
KV-cache update recreates the raw aliases again. These are host-side view
operations over a fixed-address cache; they do not read or change KV data.

The candidate stores the raw key/value aliases and their canonicalized
forward aliases once per `FlashAttentionImpl`, then returns those same aliases
only while a full source-and-view identity contract remains unchanged.
Attention kernels, KV writes, cache contents, BF16 arithmetic, query/key/value
inputs, metadata, graph segments, and every model operation remain identical.

## Measured ceiling

A CPU-only microbenchmark on this host used a representative BF16 cache shape
`[256,2,16,256]` and 31 repeated measurements:

- 48 uncached transpose/split/canonicalize preparations:
  `0.190186 ms` median;
- 48 cached tuple accesses: `0.004592 ms` median; and
- raw forward-only saving ceiling: `0.185595 ms`.

The update path repeats transpose/split, so the generous raw ceiling is about
`0.37 ms` per 48-layer target cycle. A deliberately conservative full
source-plus-view signature check measured about `0.272467 ms` for 96 helper
calls, leaving an expected net opportunity near `0.10 ms`. These CPU
measurements authorize implementation only; they are not XPU, endpoint, or
record evidence.

The latest exact replay diagnostic measured about `21.137799 ms` whole replay.
The absolute hard ceiling is therefore below 1.8%, while a realistic endpoint
effect is expected to be roughly 0-0.5% after host/device overlap.

## Frozen identity

Implementation starts from:

- main repository:
  `60e4a0a38`;
- vLLM:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- record XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- installed record grouped-GEMM SHA-256:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`; and
- matched DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`.

The approved record remains `94.92003934159611 tok/s`,
LocalMaxxing `cmrzrd4tf001ipa013xpx4kid`.

Before any XPU diagnostic, use a clean kernel source worktree at the exact
record commit. The closed N32 source commit and candidate binary are not part
of this experiment.

All model, source, binary, cache, temporary, log, run, and evidence paths must
stay on internal NVMe/ext4. The external USB is backup-only.

## Sole treatment

Control:

```text
VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=0
```

Candidate:

```text
VLLM_XPU_LAGUNA_M8_PERSISTENT_KV_CACHE_VIEWS=1
```

The flag is default off. When enabled it is valid only for the frozen Laguna
exact graph contract: XPU decoder attention, BF16 cache tensor, head size 128,
two local KV heads, one fixed cache layout, exact speculative attention, and
the audited M=8 Breakable graph stack. Any contract mismatch must raise before
the candidate can silently fall back.

No kernel build, op schema, tensor allocation, model arithmetic, attention
argument, graph topology, DFlash policy, collective, or benchmark setting may
change.

## Fail-closed cache contract

The first eligible cache use may build:

- raw key and value aliases from the incumbent transpose/split expression;
- canonicalized key and value aliases using the incumbent helper; and
- immutable source, raw-view, canonical-view, and object-identity signatures.

Every later use must validate:

- source data pointer, storage offset, shape, stride, dtype, and device;
- configured head size and split width;
- cached raw/canonical view object identities;
- every cached view's data pointer, storage offset, shape, stride, dtype, and
  device; and
- exact expected alias offsets between key and value.

Any source pointer/layout change, cached view replacement, in-place view
metadata change, wrong dtype/device/head geometry, or partial cache state must
raise. It may not rebuild or fall back after initialization. Flag-off behavior
must remain byte-for-byte on the incumbent preparation path.

The update path must receive the raw aliases; the attention forward path must
receive the canonical aliases. Quantized KV reinterpretation remains after
the helper exactly where it is today and is outside the frozen BF16 candidate
contract.

## Gate 1: CPU/static

Before any XPU use:

- default-off and strict flag parsing tests pass;
- stable repeated calls return the identical cached alias objects;
- candidate aliases have the same raw bits, shapes, strides, offsets, dtype,
  device, and storage as independently computed incumbent aliases;
- source pointer/storage/shape/stride/dtype/device drift is rejected;
- raw and canonical cached-view object or metadata drift is rejected;
- partial cache state is rejected;
- wrong head geometry, KV heads, attention type, dtype, device, and ineligible
  selector combinations are rejected;
- update selects raw aliases and forward selects canonical aliases; and
- flag-off calls the original view construction with no cache state.

Focused pytest, Ruff, formatting, whitespace, and an independent code review
must pass.

## Gate 2: exact diagnostic

Only Gate 1 authorizes a fresh, no-promotion diagnostic on all four physical
B70s. It must compare the current record control against the candidate and
require:

- one fresh q1 teacher, eager DFlash control, graph DFlash control, and graph
  DFlash candidate request, each in its own fresh process;
- complete bitwise token identity across q1/eager/graph;
- `cached_tokens=0`;
- unchanged DFlash depth and bounded acceptance;
- q2 through q8 attention output parity;
- unchanged 146-graph/145-break topology with exactly 48 attention and 97
  collective boundaries on every rank;
- exact source, binary, model, environment, and flag identity; and
- 31 replay-profile samples per rank.

Profile both KV-view preparation and whole replay. Promotion requires a
positive median whole-replay saving on the maximum rank, a positive fresh
generation-wall effect, no p90 instability, and no transfer of the apparent
host saving into post-replay synchronization. Host-only improvement is not
enough.

The fourth arm clarifies the earlier three-arm wording before any Gate 2 tool
or device run. It adds a same-session record-graph control rather than relying
on historical timing. Every arm still performs exactly one cold generation;
there is no warm-up, retry, cache reuse, or result-conditioned selection.
Both graph arms must independently retain 31 samples per rank. A separate
non-timing packet must compare q2 through q8 attention outputs bytewise with
the selector off and on for every physical card.

## Gate 3: endpoint boundary

Only a clean diagnostic win may authorize a separately constructed, audited,
and committed graph-vs-graph A1-B1-B2-A2 endpoint protocol. It must retain the
existing 13 unique cold prompts, canonical-q1 exactness, cache-zero, long-next,
rollover, no-retry, no-warmup, single-generation, acceptance-drift, cleanup,
and adjacent-pair causal gates.

Only the lower candidate start may be promoted, and only if it is strictly
above `94.92003934159611 tok/s`. No diagnostic result is submit-worthy.

## Gate 1 result

Gate 1 passed before any XPU diagnostic or generation:

- candidate vLLM commit:
  `4d3124f1a`;
- strict default-off `0`/`1` parsing and invalid-value rejection passed;
- 37 focused environment, cache-view, lifecycle, and runner-contract tests
  passed;
- an additional focused persistent-view run passed 18 tests;
- Ruff check, Ruff format, whitespace, typos, SPDX, environment-default,
  attention-documentation, forbidden-import, and other applicable pre-commit
  hooks passed;
- the full pre-commit run reached one pre-existing mypy error at
  `gpu_model_runner.py`'s Laguna collective-state assignment, outside this
  candidate's changed hunks; and
- independent review approved Gate 1 after requiring and verifying direct
  raw-update/canonical-forward routing, actual record-shape reuse, same-object
  source/view drift rejection, explicit lifecycle invalidation, strict flag
  parsing, and KV-transfer rejection.

The measured representative hot-path result after all validation was:

- control median: `0.366909 ms` per 48 forward+update preparations;
- candidate median: `0.318848 ms`;
- median saving: `0.048061 ms`;
- control p90: `0.371708 ms`; and
- candidate p90: `0.324279 ms`.

This is only about 0.23% of the latest `21.137799 ms` whole replay and remains
well inside endpoint noise. It authorizes Gate 2 only. It is not performance,
promotion, record, payload, or submission evidence.

## Gate 2 telemetry and parity addendum

The independent pre-run audit rejected the first Gate 2 harness draft before
any XPU or model use. It required three corrections:

- selector parity must instantiate the real `FlashAttentionImpl` flag-off and
  flag-on paths rather than construct the private cache manager directly;
- each parity process must have its own process group, survivor cleanup,
  post-process worker proof, and strict post-idle proof; and
- the replay profile must measure the two actual KV-view preparation helpers
  directly instead of treating aggregate attention-boundary host time as that
  measurement.

Those corrections are frozen in telemetry-only vLLM commit
`5da4a8ccdde0abe77d2dd2abda7b6a12bc74c01a`, a descendant of Gate 1 candidate
`4d3124f1a2a8f4f08ded49d148022ee660f68ff1`. Replay-profile schema v2 brackets
the existing forward and update helper bodies with `perf_counter_ns`, and
requires exactly 48 forward plus 48 update calls per replay. The graph control
must report 96 incumbent calls. The candidate must report 96 persistent hits
and zero builds after capture. The direct timer adds equal diagnostic overhead
to both graph arms, so its values are mechanism evidence only; the existing
whole-replay and post-sync fields remain the promotion gates for end-to-end
effect.

The parity packet now sets the exact graph contract first, constructs real
selector-off/on attention implementations for both full and sliding attention,
proves absent/present persistent state and repeated candidate object identity,
and compares q2 through q8 FA2 outputs bitwise on each physical card. It remains
non-timing and performs no model generation.

After these fixes, focused checks passed:

- 68 vLLM attention, lifecycle, runner, and Breakable-profile tests;
- 11 analyzer/controller contract tests;
- Ruff check and format;
- shell syntax and whitespace checks; and
- an independent final working-tree audit.

The independent audit approved the corrected diagnostic conditional on
committing the exact inspected source and tool trees before launch.
The inspected Gate 2 tools are committed at
`f2c9db671d0a80ebfac3da7d05fc82b2b187c54c`; no XPU or model command ran before
that commit.

## Gate 2 attempt 1: parity import failure

The first sealed Gate 2 root was:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-persistent-kv-views-a1f4a4e60-5da4a8ccd-20260725T040536Z
```

It failed closed on physical card 0 before any model load, prompt, or
generation. The standalone parity process tried to import
`flash_attn_varlen_func` from the vLLM FlashAttention backend module, where
that name is only conditionally re-exported. The import raised before a tensor
or attention call. Post-process worker and strict idle proofs passed, and no
worker survived.

This is a harness import defect, not candidate, exactness, timing, or device
evidence. The root is sealed and will not be reused. A corrected attempt may
import the frozen kernel package's public
`vllm_xpu_kernels.flash_attn_interface.flash_attn_varlen_func`, which is the
same direct interface used by the existing Laguna attention gates. It may not
change tensors, seeds, selector construction, FA arguments, output checks,
process isolation, or any model arm.

The minimal import-only correction and its static provenance test are committed
at `a15303cc00d9f1fcc05ce0dd924518a0cf650ac7`. An independent read-only audit
approved it: the direct public function is exactly the function used by
vLLM's XPU wrapper, accepts the frozen keyword call, and leaves selector and
parity semantics unchanged. This approval occurred before any second XPU or
model attempt.

## Gate 2 attempt 2: incomplete runtime bundle

The second sealed Gate 2 root was:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-persistent-kv-views-dc79f12c2-5da4a8ccd-20260725T041008Z
```

It again failed closed on physical card 0 before model load, prompt,
generation, tensor allocation, or attention. The direct import correction
worked, but vLLM's XPU platform plugin could not load `_xpu_C.abi3.so` because
the new clean record worktree contained only four top-level binaries and
omitted its frozen shared-library dependencies. Platform detection therefore
returned `UnspecifiedPlatform`; the real selector-on constructor correctly
rejected `not_xpu=True`. Post-process worker and strict idle proofs passed.

A separate non-model import probe reproduced the exact loader failure:

```text
ImportError: libgrouped_gemm_xe_default.so: cannot open shared object file
```

This is a second harness/runtime-bundle defect, not candidate or performance
evidence. The root is sealed and will not be reused. Before another attempt,
the clean record worktree must contain and the harness must hash the complete
approved runtime closure:

- `_C.abi3.so`;
- `_xpu_C.abi3.so`;
- `_moe_C.abi3.so`;
- `_vllm_fa2_C.abi3.so`;
- `libattn_kernels_xe_2.so`;
- `libgdn_attn_kernels_xe_2.so`;
- `libgrouped_gemm_xe_2.so`;
- `libgrouped_gemm_xe_default.so`;
- `libmhc_kernels_xe_2.so`; and
- `libmqa_logits_kernels_xe_2.so`.

The six omitted files must be copied mechanically from the installed
record-matched package only after matching their previously recorded SHA-256
values. Parity must also fail unless the compiled FA2 extension is available
from that exact package; fallback attention is forbidden.

## Gate 2 attempt 3 runtime freeze

Before any third campaign, the six missing libraries were copied mechanically
into the clean record worktree and verified against their durable recorded
hashes. The controller, arm driver, parity packet, and analyzer now freeze the
same ten-file closure. Parity additionally requires:

- `current_platform.is_xpu()` is true;
- exactly one post-affinity XPU is visible;
- compiled FA2 is available;
- `_vllm_fa2_C.abi3.so` resolves from the exact record package;
- the direct FA2 fallback is replaced with a fatal handler; and
- successful JSON explicitly records XPU platform, compiled FA2, fallback
  prohibition, and extension origin.

A terminal-only, non-model import check observed one visible XPU, XPU platform
selection, compiled FA2 availability, and the exact record-package extension
path. It is operational information, not durable evidence; the next sealed
parity packet must independently record all four facts.

The complete-closure tool update is committed at
`880d638b377f97e10372f9a56617bf0d844b1ddd`. Twelve focused analyzer,
controller, selector, process-cleanup, and closure tests pass, along with Ruff,
shell syntax, and whitespace checks. An independent read-only audit verified
all ten actual hashes against durable Laguna evidence and conditionally
approved one new sealed root after this exact tool commit. No third campaign,
model load, prompt, or generation occurred before this freeze.

## Gate 2 attempt 3: exact timing stop

The third sealed Gate 2 root was:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-persistent-kv-views-9e65e991b-5da4a8ccd-20260725T041943Z
```

All four physical-card q2-through-q8 compiled-FA2 parity packets passed. The
q1, eager, graph-control, and graph-candidate arms each ran once in a fresh
process, reported zero cached tokens, and produced the same 272-token greedy
output bitwise. Every pre/post idle check passed and no worker survived an arm.

The controller nevertheless failed closed at its first analyzer comparison.
The analyzer had validated each graph arm's distinct replay-profile destination
and then compared the raw environment maps after removing only the treatment
selector. The necessarily different `graph-control/replay-profile` and
`graph-candidate/replay-profile` paths therefore tripped the sole-treatment
guard. An independent artifact audit confirmed that this path was the only
remaining environment difference; it is telemetry provenance, not a runtime
treatment.

The next fail-closed check exposed a second preregistration error. The addendum
above expected 48 forward plus 48 update Python view preparations per replay.
Source audit proved that `unified_kv_cache_update` is captured inside graph
segments, so its Python `do_kv_cache_update` body runs at capture time rather
than on each replay. Only the 48 eager attention boundaries re-enter Python and
prepare forward views. Every one of the 31 samples on all four ranks in both
graph arms independently reports exactly:

- 48 forward preparations;
- zero update preparations; and
- 48 total preparations.

The candidate reports 48 persistent hits and zero builds; the control reports
48 incumbent calls. This is complete hot-replay coverage, not missing
instrumentation. The analyzer correction therefore:

- normalizes only the already-validated arm-local profile destination;
- requires the source-correct 48/0/48 replay preparation contract; and
- permits mode-0500/mode-0400 sealed roots as read-only inputs only when the
  analysis output stays outside the sealed root.

The sealed root was never modified or reopened. A corrected analyzer read it
in place and wrote only to a private temporary directory. It classified the
candidate as `exact_timing_stop`:

| Gate or metric | Control | Candidate | Candidate saving | Result |
|---|---:|---:|---:|---|
| KV-view preparation median | 0.897617 ms | 0.583971 ms | 0.313646 ms | pass |
| attention-host median | 4.484839 ms | 4.219462 ms | 0.265377 ms | pass |
| whole-replay median | 21.097835 ms | 21.012204 ms | 0.085631 ms | pass |
| whole-replay p90 | 21.420231 ms | 21.264729 ms | 0.155502 ms | pass |
| post-replay sync median | 9.332333 ms | 9.477547 ms | -0.145214 ms | fail |
| fresh 272-token generation | 21.700585 s | 21.839529 s | -0.138944 s | fail |

This is exact mechanism evidence and a useful measured negative: persistent
views remove their intended Python overhead, but the saving is mostly absorbed
elsewhere and does not improve the fresh end-to-end generation. No
uninstrumented endpoint campaign is authorized, and nothing from this attempt
is benchmark, record, payload, or LocalMaxxing submission evidence.

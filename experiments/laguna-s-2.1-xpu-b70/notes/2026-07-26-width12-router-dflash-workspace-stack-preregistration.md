# Laguna width-12 router plus DFlash workspace stack preregistration

Date: 2026-07-26 America/Toronto

Status: **host and four-card component gates passed; cold endpoint crossover
authorized but not yet run.** No model service or generation has occurred for
this combined treatment.

## Question

Can two independent, arithmetic-preserving reductions in per-cycle overhead
move the exact width-12/depth-11 path from `100.5248896052723` to more than
`102 tok/s`?

The frozen best leg is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/phase5-w12-b0dabaa3-20260726T144510Z
```

It is 13/13 bitwise exact against the q=1 teacher, has zero cached prompt
tokens, and records audited `146/145` graph topology on every rank. At its
measured `3.9552` emitted tokens per cycle, reaching 102 at unchanged
acceptance requires approximately `0.57 ms` less cycle time.

The first component is measured at width 12. Kernel
`906190641d708b8028018c5dde653e265c835348` preserved exact FP32 weights,
int32 expert IDs, and source indices across a 192-case adversarial corpus and
won 31/31 paired blocks on physical card zero. It saved `0.498946 ms` per
47-call target cycle. That missed its standalone `0.60 ms` gate, so cards one
through three and its endpoint correctly did not run.

The second component was frozen earlier as vLLM
`4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0`. Its DFlash context-KV workspace
passed exact component checks on all four physical B70s and two separate TP4
selector-off/on runtime exactness campaigns at width 8/depth 7. It removes
repeated allocation and layout-buffer creation but preserves the literal
RMSNorm, BMM, BF16 bias, layout copy, K normalization, RoPE, and cache-write
order. It has no throughput result. Widths 9 through 12 and depth 11 were not
covered by that evidence.

The router leaves roughly `0.07 ms` of the estimated gap. The workspace need
not remove its entire measured `0.480 ms` context-KV interval to be useful,
but additivity is only a hypothesis. The endpoint, not this arithmetic, decides
whether the stack clears 102.

## Frozen treatment

The candidate enables exactly:

```text
VLLM_XPU_LAGUNA_MWIDE_BF16_ROUTER_TOPK=1
VLLM_XPU_LAGUNA_DFLASH_CONTEXT_KV_WORKSPACE=1
```

Both arms use the same candidate vLLM source and native binaries. The control
sets both selectors to zero. All other model, draft, graph, MoE, attention,
benchmark, process, cache, and topology fields remain identical.

The router selector may dispatch the existing direct-BF16 native operation
only for exact `[12,256]` target-verifier logits when:

- `VLLM_XPU_LAGUNA_EXACT_MAX_M=12`;
- `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`;
- `VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1`;
- the Laguna top-10, 256-expert, normalized, unbiased-weight sigmoid contract
  holds; and
- the current PIECEWISE Breakable-graph identity is exact.

Every other shape uses the incumbent FP32 router path. M=8 behavior is
unchanged unless its old selector is independently used under its old
contract.

The workspace selector may persist exactly the four existing intermediate
buffers for context widths 1 through 12 only when the current model is the
six-layer Laguna DFlash drafter, target layer IDs are
`[1,10,19,29,38,47]`, hidden size is 3072, speculative depth is 11, target
verifier width is 12, scheduling is synchronous at one sequence, model dtype
is BF16, and TP/PP/DP are 4/1/1. It must also require the complete combined
router selector stack above. Any selector or contract drift is a startup error.

The workspace retains the already-proven operation order and all pointer,
shape, stride, dtype, device, non-aliasing, weight-identity, projected-K
handoff, and capture guards. The only semantic extension is allocating the
same row-generic buffers for context widths 9 through 12.

## Validation before an endpoint

Host tests must answer:

1. selector-off is byte-identical to the incumbent path;
2. widths 1, 3, 8, 9, and 12 produce raw-bit-equal K, V, and normalized K for
   changing BF16 inputs, with and without bias;
3. every eligible width reuses stable objects and pointers;
4. widths 0 and 13 retain the incumbent allocation path;
5. input, weight, pointer, projected-K, shape, and capture drift fail closed;
6. every field of the exact width-12/depth-11 platform contract is enforced;
7. the router dispatches only `[12,256]`, while M=1, M=8 without its old
   contract, other dtypes, and other shapes retain exact FP32 fallback; and
8. lint, formatting, focused tests, whitespace checks, source identity, and
   clean-worktree checks pass.

Then run sequential one-visible-card component legs on physical cards 0
through 3:

- the width-12 router must be raw-bit exact on the frozen 192-case corpus;
- the workspace must be raw-bit exact for changing real-shape BF16 widths 9
  through 12, including reuse and cache-boundary checks; and
- no component mismatch, crash, device error, or process leak is allowed.

The old router's standalone `0.60 ms` floor does not apply to this combined
treatment. Its measured `0.498946 ms` remains evidence, not a reclassified
pass. The combined experiment is authorized by independent exactness and is
decided only by the endpoint.

## Endpoint gate

After the host and four-card component gates pass, run one cold control then
one cold candidate through the unchanged 13-prompt, 512-token realistic suite.
No warmup request, retry, favorable arm selection, prompt removal, continuation,
prefix caching, capture relocation, or metric substitution is allowed.

Each arm must independently satisfy:

- exactly one invocation of every prompt and one active generation;
- `cached_tokens=0` on all 13 prompts;
- 13/13 token and text equality to the canonical q=1 teacher;
- audited target graph capture/replay topology `146/145` on every rank;
- real depth-11 speculation and normal acceptance accounting;
- clean startup, shutdown, XCCL teardown, and verified idle intervals; and
- actual vLLM, kernel-source, native-binary, launcher, suite, teacher, and
  selector identities recorded from disk and the service environment.

Promotion requires the candidate's frozen scored median for tokens 1 through
100 after TTFT to exceed `102 tok/s`. If it does, run a second independent
cold candidate confirmation under the same gates. A single crossing, a
full-window score, or a result obtained by moving work outside the scored
window is not sufficient.

## Source and component result

The default-off combined implementation is vLLM
`9090947f229ef4110f4b71a79cba7114efbbac5a`. Focused host validation returned
`71 passed`; Ruff, Python compilation, and whitespace checks passed. The
worktree was clean before every component leg.

The width-12 router uses kernel
`906190641d708b8028018c5dde653e265c835348` and `_moe_C.abi3.so` SHA256
`154eebd95beb83089b6628a21085e079b730c4474408d8fd2b484c385a0ce5d5`.
All four physical cards passed pre/post exactness over the frozen 192-case
corpus and won 31/31 paired blocks:

| physical card | paired median saving per 47 calls |
| ---: | ---: |
| 0 | `0.498946 ms` |
| 1 | `0.535074 ms` |
| 2 | `0.500916 ms` |
| 3 | `0.510949 ms` |

The retained root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/mwide-bf16-router-component-9061906-41dd691d-20260726
```

These legs remain `formal_component_pass=false` under the old standalone
`0.60 ms` floor. They are used here only as exactness and measured component
evidence; their status was not relabelled.

The width-12 workspace gate is main
`5eecb368d` with vLLM `9090947f2`. Every physical card returned
`exact_component_pass` for changing real-shape BF16 widths 9, 10, 11, and 12
in both actual no-bias and synthetic-bias branches. Each branch repeated every
width and preserved raw bits at normalized context, BMM output, projected K,
projected V, normalized K, RoPE K, and all six cache writes. Workspace
pointers were stable, weights and inputs stayed unchanged, and capture
rejection did not allocate or mutate state.

The retained root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/mwide-dflash-context-kv-9090947-5eecb368d-20260726
```

Two earlier card-zero attempts are harness failures, not candidate results:

1. main `b60ec7960` reached cache writes but the old fixture omitted the
   current backend's `_xpu_persistent_kv_cache_views=None` initialization;
2. the next attempt completed both arithmetic branches and then tried to hash
   nonexistent `libgrouped_gemm_bmg_xe2.so` instead of the installed
   `libgrouped_gemm_xe_2.so`.

Neither wrote a result, started a service, generated a token, or produced a
performance sample. Both faults were corrected in committed source before the
successful four-card campaign.

## Accumulated-branch endpoint invalidation and clean rebase

The first selector-off endpoint control on the accumulated source identity
`9090947f229ef4110f4b71a79cba7114efbbac5a` is invalid as a baseline:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-stack-control-211d26eab-9090947f2-20260726T161100Z
```

It was cache-zero and preserved the audited `146/145` topology, but measured
only `91.03238 tok/s` and matched the frozen teacher on `12/13` prompts. The
`shell-safety-review` prompt first diverged at generated token index 1
(`4603` expected, `23950` actual). No candidate leg was authorized.

That result exposed source-identity contamination rather than evidence about
either treatment. The accumulated vLLM branch was 2,096 inserted lines beyond
the last proven `13/13` source identity and carried unrelated tree, local
argmax, and attention-capture experiments that had never been jointly
re-proven. The clean correction ports only the two audited treatments onto:

- vLLM base `6ae34833dda19b4d4315d2a2a236180b7fe44612`, clean candidate
  `c6994754f7e41139772847b31af4363d2e742aaa`;
- XPU-kernel base `a5f99d8ed98c02eef87e29be44a8cd63b1ec9155`, clean candidate
  `6f9dd3c3a7b1b677a992ca4f431a968408f9c816`; and
- clean `_moe_C.abi3.so` SHA256
  `00fd81608f057039d31e1b316fecbecec60b3b03151e66b95d0f844185119715`.

The clean source ports passed the same 71 focused vLLM tests and two kernel
static tests, plus Ruff, Python compilation, clang-format, and whitespace
checks. Physical-card component gates and the selector-off endpoint control
must be rerun under these identities before a selector-on measurement is
allowed.

All four clean-identity component reruns then passed their arithmetic gates.
The router matched every raw BF16/FP32 output before and after timing, won
`31/31` paired blocks on every card, and saved `0.499690`, `0.545085`,
`0.500676`, and `0.554635 ms` per 47-call cycle on cards 0 through 3. As
before, its old standalone `0.60 ms` timing floor remains formally false; this
does not relabel that preregistered result. The retained root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
mwide-bf16-router-clean-6f9dd3c-6eb01c9a9-20260726
```

The clean workspace gate returned `exact_component_pass` on every card for
widths 9, 10, 11, and 12, in both no-bias and synthetic-bias branches, with
stable workspaces and capture rejection. Its retained root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
mwide-dflash-context-kv-clean-c699475-6eb01c9a9-20260726
```

The clean selector-off endpoint control is valid:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-stack-clean-control-40985722f-c6994754f-20260726T204225Z
```

It returned `13/13` bitwise exact, `cached_tokens=0` throughout, and audited
`146/145` on all four ranks. Its cold scored median was
`98.95528531492559 tok/s`; this is below the earlier `100.524890` leg but no
favorable retry or baseline substitution was performed.

The first clean selector-on integration attempt produced no performance
sample. Its first benchmark request returned HTTP 500 because a second
full-model cast-skip guard still required router logits shape `(8, 256)`, even
though dispatch and the native op already admitted width 12:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-stack-clean-candidate-40985722f-c6994754f-20260726T205059Z
```

The narrow correction is vLLM
`13e211c3bb6d23ad50598980acb914a05bd1e8ba`: it admits only `(8, 256)` and
`(12, 256)` BF16 logits in that cast-skip guard and keeps all other widths
fail-closed. The focused suite now returns `74 passed`, including direct
coverage of both admitted widths and rejection of width 11. The failed run is
an integration/harness result, not a correctness or throughput result.

The corrected selector-on candidate is valid but below the promotion floor:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-width12-stack-clean-candidate2-1e9887a92-13e211c3b-20260726T205829Z
```

It returned `13/13` bitwise exact, `cached_tokens=0` throughout, audited
`146/145` on all four ranks, normal decaying acceptance, and clean teardown.
Its cold scored median was `99.72015184765868 tok/s`, versus
`98.95528531492559 tok/s` for the valid selector-off control: a real
`+0.7729%` paired treatment gain, but not `102 tok/s`.

The suite-level speculative counters were materially matched
(`1607/4749` control drafts/accepted tokens versus `1608/4748` candidate), so
the gain is execution-time reduction rather than an acceptance change. No
repeat was authorized: the candidate missed the preregistered promotion floor,
and retrying for a favorable cold start would be invalid.

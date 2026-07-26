# Laguna width-12 router plus DFlash workspace stack preregistration

Date: 2026-07-26 America/Toronto

Status at registration: design only. The width-12 router's first-card
component result and the older width-8 DFlash workspace evidence already
exist, but this combined treatment has not changed vLLM source, run a new XPU
call, started a service, or generated a token.

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


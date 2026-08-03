# Laguna real-use latency and upstream-sync checkpoint

Date: 2026-08-03 America/Toronto

Status: **offline successor assembled and host-tested; no new device, model,
endpoint, or performance run**.

## Product objective

Optimize the latency users feel, while retaining the exact decode record:

- client time to first token (TTFT);
- full request wall time and delivered output tok/s end to end;
- prompt processing by prompt-length bucket;
- long-context decode and retrieval behavior; and
- conventional decode at or above the protected
  `125.4619731637751 tok/s` record when a candidate is promoted.

The long-context harness now reports client TTFT, client request wall time,
end-to-end delivered output tok/s, and prompt-tokens/TTFT lower bound, both in
aggregate and by exact prompt-token count. These fields supplement rather than
replace Prometheus prefill time and the conventional 99-interval decode
metric. Six CPU-only contract tests and Ruff formatting/lint pass.

## Existing measured E2E win

The first priority is not speculative: exact pure-prefill chunking already
measured a large client-visible improvement under
`VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS=1` at vLLM `4ddb91528`:

| metric | selector off | selector on | ratio |
| --- | ---: | ---: | ---: |
| 256-token Prometheus prefill | 19.875 tok/s | 184.598 tok/s | 9.288x |
| 256-token client TTFT | 12.883 s | 1.399 s | 0.109x |
| 32K conventional decode | 39.589 tok/s | 39.754 tok/s | 1.004x |

The short rows were q1 exact. The treatment is especially relevant because 12
of the 13 protected short-suite prompts are 89--229 tokens and the protected
suite's median TTFT is about 5.954 seconds. It does not claim a new decode
record.

The treatment has now been combined, without modifying either parent branch,
with the INT4 tile-record integration in the clean successor worktree:

```text
/home/steve/src/laguna-vllm-e2e-latency-integration-20260803
experiment/laguna-e2e-latency-integration-20260803
f9e167ad0 xpu: batch exact Laguna pure-prefill rows
```

The combined host suite passes 36 tests: 21 tile-record host/static/post-load
cases plus 15 exact-prefill model/runner contract cases. Ruff lint passes. No
native module was imported and no XPU work was performed.

The offline successor now also attests the exact-prefill selector in each
worker before model loading at vLLM `d9e7e2f1a`. A separate default-off
production readiness canary can pay and validate the known 10.478-second
first-live graph/JIT capture before a frontdoor advertises readiness. It is
strictly excluded from cold runners and does not change or improve any cold
benchmark result. See
[`2026-08-03-production-readiness-canary-offline.md`](2026-08-03-production-readiness-canary-offline.md).
The comprehensive successor host run now passes 77 tests, including the
original tile/prefill coverage and the v2 worker-attestation contract.

## Upstream policy

Community upstream `vllm-project/vllm:main` and contributor fork
`steveseguin/vllm:main` are synchronized at `68ca6fd02`. The focused public
community packer branch is rebased on that tip and is one commit ahead at
`3ab3e1927`.

The measured Laguna branches are approximately 763 upstream commits behind
and contain 130--219 local commits. They are exact experiment and record
identities, not ordinary feature branches. Rebasing or merging them in place
would destroy useful provenance and create a high-risk semantic migration.
Keep them pinned. Maintain current-upstream community/development branches and
forward-port only focused, independently testable pieces. The dirty protected
Qwen worktree at `/home/steve/src/vllm` must not be reset or reused for this
work.

## Next work and gates

1. Promote exact pure-prefill chunking through a fresh real-use A/B when the
   device quarantine is separately lifted.
2. The authenticated M12/M8/scalar decomposition for the incumbent
   scheduler's 10/20/30-row tails is now implemented offline at vLLM
   `015fee586`; run its raw and endpoint exactness gates only after separate
   authorization.
3. Complete the accepted-position diagnostic before implementing a
   long-context depth-7 drafter with the unchanged width-12 target verifier.
   The next artifact now has a fail-closed offline analyzer; see
   [`2026-08-03-mixed-depth-analyzer-offline.md`](2026-08-03-mixed-depth-analyzer-offline.md).
4. Re-screen exact paired-row attention only for long full-attention layers
   if the 8K--32K component crossover reverses its short-context loss. The
   offline gate now has a `long-full` profile for exact 8K/16K/24K/32K
   contexts; see
   [`2026-08-03-long-full-attention-screen-offline.md`](2026-08-03-long-full-attention-screen-offline.md).
5. Adapt wide-prefill Q/K normalization plus RoPE to the incumbent 8,182/8,094
   partitions instead of reviving the inexact 8,202/8,192 scheduler identity.
6. For production only, put the loopback backend behind the readiness canary
   and expose the frontdoor only after its atomic ready marker exists.

A real-use promotion must preserve short-suite q1 exactness, cache-zero cold
identity, accepted/drafted counters for a prefill-only change, 146/145 target
and 14/13 draft topology, clean teardown, and adjacent-control conventional
decode. The preferred screen requires at least 50% median TTFT reduction and
20% median wall-latency reduction, candidate decode at least 0.99x control,
and no matched decode row below 0.95x. A new record claim still requires a
confirmed result at or above `125.4619731637751 tok/s`.

The NVMe/device quarantine remains controlling. This checkpoint does not
authorize a service start, model load, XPU probe, component run, swap change,
reset, reboot, or recovery action.

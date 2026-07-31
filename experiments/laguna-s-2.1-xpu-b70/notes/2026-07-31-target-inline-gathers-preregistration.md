# Laguna width-12 target inline-gather preregistration

Date: 2026-07-31 America/Toronto

## Objective

Test whether recording only the target verifier's 96 deterministic TP4
`all_gather_into_tensor` operations inside the surrounding XPU graph segments
can reduce decode-cycle latency without changing any arithmetic, model output,
acceptance, benchmark accounting, or quality.

The verified incumbent remains:

- historical-window decode: `121.03724088473012 tok/s`;
- conventional 99-interval decode: `119.82686847588282 tok/s`;
- exactness: 13/13 against the frozen q=1 teacher, including text hashes;
- target graph topology: 146 graphs / 145 eager breaks on all four ranks;
- draft graph topology: 14 graphs / 13 eager breaks on all four ranks; and
- run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-dflash-inline-attention-scored-20260731T035401Z`.

Reaching 130 tok/s requires +7.405% on the historical metric, or about
2.5 ms from the approximately 32.9 ms median decode cycle at unchanged
acceptance. Small drafter cleanups are not sufficient; the target's 145 eager
boundaries remain the largest unretired structural overhead.

## Narrow prior evidence

The 2026-07-24 direct-XCCL runtime graph probe is retained as a terminal
negative for recording *all* target collectives. Its boundary-by-boundary
changing-input evidence is narrower and more useful than that headline:

- sample 1 and sample 2 passed all 97 raw gathered tensors on all four ranks;
- both samples passed all 97 literal fixed-rank BF16 sums on all four ranks;
- sample 1 passed the final ordinary XCCL all-reduce; and
- sample 2 first diverged at that final ordinary all-reduce.

The live target has exactly 96 model gathers (48 attention output projections,
one layer-0 dense MLP down projection, and 47 MoE final combines) plus one
embedding ordinary all-reduce. The candidate therefore excludes the only
primitive that failed the changing-input probe.

This is not a rerun of the rejected all-collective graph treatment. It records
the 96 previously exact gathers and their unchanged literal rank-ordered BF16
sums, while the embedding ordinary all-reduce remains an eager boundary.

## Candidate contract

Add one default-off selector,
`VLLM_XPU_LAGUNA_M8_INLINE_GATHERS=1`, with these fail-closed requirements:

- Poolside Laguna S2.1 INT4 target and official DFlash draft;
- BF16 KV cache;
- TP4, EP4, PP1, DP1, max-num-seqs 1;
- exact width 12 / speculative depth 11;
- exact attention, width-12 router/workspace, FP8 DFlash, and segmented DFlash
  graph stack unchanged from the incumbent;
- target attention capture and target inline attention both disabled;
- runner-owned, preallocated, fixed-address gather outputs unchanged;
- the rank-ordered BF16 reduction implementation and order unchanged;
- the embedding ordinary all-reduce remains eager; and
- the selector is recorded in identity and verified in the service
  environment.

The selector may alter scheduling only. It must not alter tensor shape, dtype,
contents, reduction order, logits, sampled tokens, acceptance, cache state,
prompt set, request length, measurement window, or scoring.

## Audited topology

The incumbent's 145 target eager breaks are:

- 96 model gathers;
- one embedding ordinary all-reduce; and
- 48 attention calls.

Inlining only the 96 gathers therefore requires exactly:

- target: 50 graphs / 49 eager breaks on every rank; and
- draft: 14 graphs / 13 eager breaks on every rank, unchanged.

Any other count is a hard failure. The embedding all-reduce must still appear
as an eager collective. On initial capture, all 96 Python gather calls execute;
on replay, they do not re-enter Python and only the embedding eager callback
does. The collective audit must distinguish these two valid counter states
without weakening the fixed gather-count, order, shape, address, or topology
checks.

## Validation ladder and stop rules

1. Work only in a new vLLM experiment worktree based on incumbent commit
   `34b43849fc7c8ff8633f223469cc2a0d525c256e`.
2. Add unit tests proving selector-off behavior is unchanged, selector-on
   gathers execute within capture, the ordinary all-reduce remains an eager
   callback, capture/replay counter states are exact, and invalid
   configurations fail before model load.
3. Run focused tests, formatting/lint checks, shell syntax checks, and inspect
   the actual diffs and files rather than trusting edit output.
4. Preserve the source patch, harness patch, exact identities, and test output.
5. With a clean idle host, run exactly one non-scored two-request, 400-token
   smoke. It must match both frozen q=1 prefixes byte-for-byte, use real
   width-12 speculation with a decaying acceptance curve, show target 50/49
   and draft 14/13 capture and replay on 4/4 ranks, and tear down cleanly.
6. Only a passed smoke authorizes one cold scored 13-prompt leg.
7. The scored leg must pass the existing 13/13 token/text exactness, cached
   token zero, request uniqueness, 50/49 and 14/13 topology, idle interval,
   provenance, runtime-lock, and clean teardown gates before any rate is
   reported.

Stop after the first graph, collective, device, topology, or exactness failure.
Do not retry, reset, unbind, reload, FLR, clear shared memory, or reboot. No
failed or diagnostic run may be quoted as throughput. If the smoke passes but
the scored leg is not faster, retain the exact negative result and leave the
selector default-off.

## Promotion criterion

The candidate is a win only if it is 13/13 exact, satisfies every identity and
topology gate, and improves the incumbent under the same cold scored protocol.
It becomes a new record only after a second confirmation if the first result is
inside the established noise band. A matching LocalMaxxing submission is made
only for a verified real record.

# Laguna incumbent wide-prefill Q/K RMSNorm plus NeoX RoPE

Date: 2026-08-03 America/Toronto

Status: **default-off source successor and fail-closed component gate are
host-tested; no XPU component, model, endpoint, correctness, latency, or
throughput run was performed**.

## Outcome

The closed 8,202/8,192 scheduler-alignment experiment is not being revived.
This successor instead targets the incumbent q12 scheduler exactly:

```text
max_num_batched_tokens = 8192
max_num_scheduled_tokens = 8182
32640 prompt = 8182 + 8182 + 8182 + 8094
```

The isolated source commits are:

- vLLM `505b59cb9` on
  `experiment/laguna-e2e-wide-prefill-incumbent-20260803` in
  `/home/steve/src/laguna-vllm-e2e-wide-prefill-incumbent-20260803`;
- XPU kernels `13cd7e0` on
  `experiment/laguna-int4-wide-prefill-incumbent-20260803` in
  `/home/steve/src/laguna-xpu-kernels-int4-wide-prefill-incumbent-20260803`.

Focused source deltas are frozen independently of those worktrees at:

- `patches/laguna-s-2.1-xpu-b70/incumbent-wide-prefill-20260803/0001-xpu-adapt-wide-Laguna-prefill-to-incumbent-chunks.patch.gz`;
- `patches/laguna-s-2.1-xpu-b70/incumbent-wide-prefill-20260803/0001-xpu-adapt-wide-QKNorm-RoPE-to-incumbent-chunks.patch.gz`.

Both branches preserve the earlier aligned experiment in their parent commit,
then adapt it rather than rewriting its failed evidence. The selector remains
strict, default off, and unpromoted.

## Source contract

The new native symbol is
`laguna_incumbent_wide_prefill_qk_norm_rope_out`. Giving the successor a new
symbol is intentional: an old aligned-scheduler DSO exports the prior wide-op
symbol but rejects 8,094/8,182 rows. A mere `hasattr` check on the old symbol
could therefore pass startup and fail on the first real long request. The new
symbol makes that stale-binary mismatch a startup failure.

The exact registered row set is now `{1024, 4096, 8094, 8182}`. Rows 8,064 and
8,192 fall back and are explicitly tested as closed scheduler surface. The
8,094/8,182 shapes use two heads per workgroup. Under TP4, full-attention has
14 physical Q+K heads and sliding-attention has 20; two divides both totals and
creates one 32-lane subgroup containing two independent 16-lane reductions.
The source also statically restricts the accepted head geometries and requires
whole 32-lane subgroups. Raw device equality remains mandatory because this
host proof does not establish BF16 execution identity.

Worker selector evidence is versioned to v3 and includes
`VLLM_XPU_LAGUNA_WIDE_PREFILL_QKNORM_ROPE=1`. The production readiness wrapper
can require that contract with
`LAGUNA_PRODUCTION_REQUIRE_WIDE_PREFILL=1`; its default remains zero. This does
not enable or authorize the candidate.

## Component and endpoint gates

The component tools share one pure scheduler contract. The gate now uses the
incumbent native symbol, row set, actual position starts `0`, `8182`, `16364`,
and `24546`, and a 32,640-token cache bound. The aggregator requires all four
rows on all four ranks and rejects:

- the old native symbol or any unexpected row identity;
- missing or duplicate rank/row results;
- wrong position starts or chunk multiplicity;
- any raw-BF16, input-immutability, output-guard, or timing failure; and
- less than 25 ms projected saving per rank for
  `3 x 8182 + 1 x 8094` across the 48 attention layers.

The 1,024/4,096 rows carry zero multiplicity in the 32K projection but remain
required component coverage for the registered shorter-prefill paths.

If a separate device window is later authorized, the order is:

1. run the 16 changing-input component rows and aggregate them;
2. stop on any non-exact value, stale symbol, guard failure, or sub-threshold
   projection;
3. only after a component pass, preregister one endpoint A/B under the unchanged
   8,192/8,182 scheduler;
4. require exact responses, cache-zero evidence, v3 worker/DSO attestation,
   protected short decode at or above the existing 125 tok/s lane within the
   frozen acceptance rule, and direct TTFT/wall/output-rate comparison at 1K,
   4K, 8K, 16K, 24K, and 32,640 prompts.

This candidate targets prefill launch and memory traffic. It is not expected to
fix the low 32K speculative acceptance rate by itself; the mixed-depth analyzer
and long full-attention gate remain separate 32K-decode decisions.

## Offline validation

- vLLM: 104 focused tests passed; 181 unrelated cases were deselected. The
  suite covers strict environment parsing, exact-prefill coexistence, all four
  registered rows, rejection of 8,064/8,192, the real 32K final chunk, stale
  old-symbol rejection, model dispatch, and v3 worker evidence.
- XPU kernels: 5 CPU/static source-contract tests passed, including exact
  native switch/predicate row sets and the two-head geometry invariants.
- Main repository: 31 tests plus 48 subtests passed for the component contract,
  aggregator drift cases, worker evidence, and readiness wrapper. Ruff, Bash
  syntax, and whitespace checks passed.

The earlier measured exact-prefill treatment remains the only performance
result: 256-token prefill `19.875 -> 184.598 tok/s`, TTFT
`12.883 -> 1.399 s`, and 32K decode `39.589 -> 39.754 tok/s`. No performance
number is attributed to this wide-prefill successor. The protected short
decode result remains `125.4619731637751 tok/s`.

## Safety boundary

The Laguna NVMe/device quarantine remains controlling. This work grants no
authorization to load a model, contact an endpoint, run an XPU component or
probe, alter swap, reset, reboot, or perform recovery. The candidate is source
ready and unrun.

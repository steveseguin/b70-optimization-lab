# Laguna exact M12 pure-prefill chunks

## Result

The default-off `VLLM_XPU_LAGUNA_EXACT_PREFILL_CHUNKS=1` source candidate is
a real preprocessing win and leaves the decode lane effectively unchanged.
For a single pure target prefill of 13 through 512 tokens, it replaces the
intentional row-by-row exact path with authenticated width-12 batches. Full
width chunks use the already proved BF16 router/top-k path; the final partial
chunk remains sequential M=1 in MoE. Decode and verifier contexts retain their
existing paths.

The focused vLLM commit is
`4ddb915284d4442885f72bed48311fd04640977c`, based on the protected
`1a7f61feffbc61b21b73f812d231c7426386ccdc` tree. The restorable bundle is
`patches/laguna-s-2.1-xpu-b70/vllm-exact-prefill-chunks-4ddb91528-20260802.bundle`
with SHA-256
`2c96ceacbee8e4554254bb5f2a6b01436964d3ea86be3f0a78373526bc01cc61`.

## Exact 256-token A/B gate

The three gate prompts reproduce the post-32K sentinels byte-for-byte; their
prompt-token hashes match the sealed target-only q=1 oracle. Both selector-on
and selector-off runs passed all three rows exactly against q=1, including
returned prompt IDs, output token IDs, text hashes, and retrieval JSON.

The first row in each fresh service was affected by JIT warmup, so performance
uses the remaining two rows:

| metric | selector off | selector on | ratio |
| --- | ---: | ---: | ---: |
| Prometheus prefill | 19.875 tok/s | 184.598 tok/s | 9.288x |
| client TTFT | 12.883 s | 1.399 s | 0.109x |
| conventional 99-interval decode | 162.911 tok/s | 161.160 tok/s | 0.989x |

The per-row decode movement was mixed (-4.7% and +2.0%), while the two-row
median was -1.1%. Acceptance counts and every emitted token were identical
between arms. Target and draft graph topology remained 146/145 and 14/13.

## 32K validation

The final run used the same 1,024-token warmup as the sealed long-context
baseline, followed by all three 32,640-token cases and their sentinels. All
retrieval checks passed. Long-context medians were:

| metric | prior baseline | source candidate | ratio |
| --- | ---: | ---: | ---: |
| Prometheus prefill | 7,345.070 tok/s | 7,351.147 tok/s | 1.001x |
| client TTFT | 4.478 s | 4.477 s | 1.000x |
| conventional 99-interval decode | 39.589 tok/s | 39.754 tok/s | 1.004x |

Thus the short-prefill optimization did not cost the sustained 32K decode
rate. The low long-context decode rate still tracks speculative acceptance:
median acceptance was only 0.558%. Improving long-context DFlash acceptance is
a separate experiment; changing the exact-prefill selector cannot address it.

The three post-32K sentinels were q=1 exact and measured median 197.870 prefill
tok/s, 1.299 s TTFT, and 165.089 decode tok/s. Relative to the original
post-32K sentinel baseline, prefill moved from about 19.6 to 197.9 tok/s and
TTFT from about 13.06 to 1.30 s.

## Long-output caveat retained

The first 32,640-token case did not match the earlier speculative candidate
oracle, even after the standard 1K warmup. The next two cases matched. All
three new 32K outputs repeated exactly across two independent selector-on
services, and all retrieval JSON passed. The selector cannot activate on the
actual 8,182/8,182/8,182/8,094 pure-prefill schedule because every step exceeds
its 512-token ceiling. The earlier 8,192/8,192/8,192/8,064 description missed
vLLM's ten-slot DFlash reservation and is corrected here. This does not change
the selector or result interpretation. The behavior remains an existing
order-dependent long-path arithmetic caveat, not hidden or promoted as
full-response exactness. The target-only q=1 comparison already classified all
4K+ speculative outputs as non-exact, so the long gate remains a retrieval and
performance gate.

## Verification and disposition

- Ruff checks passed on all six changed source/test files.
- New focused tests passed: 2 model chunk tests and 13 runner contract tests.
- The broader Laguna custom-op subset passed 14 tests.
- `tests/test_envs.py` passed 60 tests.
- A broader pre-existing test subset had one environment-order-dependent
  fixture failure when run as a group; that test passed alone. The shared
  elementwise suite had one missing-symbol failure when run without the sealed
  kernel tree on `PYTHONPATH`; this was an environment mismatch, not this diff.
- All four level-1 XPU diagnostics passed before and after the GPU gates.
- All services shut down ordinarily and no memory guard fired.
- The non-persistent `/swap-laguna-longctx.img` 16 GiB validation swap was
  disabled and removed afterward; only the ordinary 8 GiB `/swap.img` remains.

Keep the selector default-off until this branch is deliberately promoted.
This is not a new LocalMaxxing submission: the protected short decode record
was not rerun or changed, and the win is in request preprocessing/TTFT.

# TP2 historical autotune-winner overlay result

Date: 2026-08-23. This closes the two-arm program frozen in the
[preregistration](2026-08-23-qwen38-tp2-autotune-winner-overlay-prereg.md).
It keeps the newest upstream runtime and does not lower or relabel the pinned
TP2 frontier.

## Outcome

The historical Triton-winner overlay recovered essentially all of the TP2
regression on the newest `a3561ef8` runtime, with full quality and cache
integrity, but it missed the frozen strict promotion gate by `0.010299 tok/s`
(`0.0210%`). The correct classification is **quality-qualified partial
performance recovery; not promoted**.

| Arm | Overlay tok/s | Newest default control | Historical gate | Frozen result |
|---|---:|---:|---:|---|
| seeded fresh, ignore EOS | **49.058940** | 48.647592 | 48.830100 | pass; +0.846% vs current and +0.469% vs historical floor |
| exact-cache, natural EOS + quality | **49.009352** | 48.490490 | 49.019651 | quality pass; speed fail by 0.010299 tok/s |

The second arm is 1.070% faster than the like-for-like current-runtime strict
control. That supports autotune-winner drift as the mechanism for most of the
regression. It does not satisfy the preregistered definition of full recovery,
so neither the historical frontier nor the current default profile is
overwritten.

The fresh result is also 0.222% above the old 48.950459 diagnostic best and
was faster on 23/25 paired prompts, so it is preserved as a valid diagnostic
high for this experimental overlay identity. In the strict old/new comparison,
the overlay was faster on 11/25 prompts; the first 100 tokens matched on 25/25
and complete outputs matched on 19/25.

## Newest code stayed underneath the optimization

Both arms resolved the floating nightly to repository digest
`sha256:d3f5daa1552a231471a5ec5097475d282e07788db336819ed9e932f9193b0e35`
and source `a3561ef8e49d3545c4078df43444beb4c98ae124`. The fresh arm seeded only
78 historical `.best_config` decisions, then compiled and saved a new AOT
model under the current runtime namespace. It rejected direct loading of an
old AOT model.

No historical generated Python, compiled model, Triton binary, cache object,
`.kernel_perf`, or outer cache artifact was copied. This is the maintained
update model: newest upstream code and binaries remain the base; compatible,
identity-gated optimization decisions are applied on top.

The 78-file seed manifest had SHA-256
`65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`
before compile, after compile, and after the complete workload. No extra
`.best_config` appeared.

## Correctness and immutability

The strict replay passed the whole existing TP2 contract:

- 25/25 eligible benchmark rows with cached tokens zero;
- exact code-14 canary;
- 7/7 objective cases;
- 8/8 same-server repeats with one output hash;
- requested 8K needle, with the 7,617-token constructed prompt and 7,629 API
  prompt tokens, passed;
- 24/24 nonempty baseline comparisons;
- cached tokens zero on all 16 quality requests.

The sealed current-runtime cache manifest contains 1,061 regular-file entries.
Its manifest-file SHA-256 was
`75215310993cb84cfece6643086be025b97f4f419ba0f72f7e9007396399c74b`
before replay, after benchmark/quality, and at the final post-workload check.

The raw status files have two different scopes: the inner runner's
`final.status=pass` means identity, benchmark, quality, and cache gates passed;
the outer `overlay-strict-speed-gate.status=fail` controls experiment promotion
and is the final disposition. Accordingly, the fresh wrapper exited 0 and the
strict wrapper exited 5 solely for the frozen speed near-miss; exit 5 does not
mean the strict arm was quality-red.

Across the fresh ignore-EOS and strict natural-EOS boots of the same cache,
complete outputs matched on 20/25 prompts, common prefixes on 21/25, and the
first 100 tokens on 24/25. The EOS policies differ, so this is not a clean
determinism A/B; the existing cross-boot nondeterminism disclosure remains.

## Frozen disposition

- Preserve both measured rates and the overlay packet.
- Keep `49.019651` as the strict pinned frontier; do not round the new result
  up or relax the gate after seeing it.
- Do not call `49.009352` a promoted record. It is a quality-qualified current
  runtime candidate and a strong causal result.
- The capped TP2 program is closed; no third arm is authorized by its
  preregistration.
- TP1 and TP4 have clean one-to-one winner mappings, but require separate
  preregistrations and fresh candidates. Before either run, resolve the
  floating nightly again and remap rather than using this image if it moved.

Structured details and evidence hashes are in
[`2026-08-23-qwen38-tp2-autotune-winner-overlay-result.json`](../data/2026-08-23-qwen38-tp2-autotune-winner-overlay-result.json).

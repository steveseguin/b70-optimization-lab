# Qwen3.8 Q4_K_M TP2 exact-depth HTTP R1 preregistration

Status: **preregistered; not run**.

## Question

What decode rate and TTFT does the already-promoted two-B70 Q4_K_M TP2
package deliver at exact active HTTP prompt lengths 2K, 4K, 8K, 16K, 24K,
and 32K?

This fills a package-coverage gap. It does not reopen the accepted short
decode result and must not inherit the one-B70 depth curve.

## Frozen identity and procedure

The machine-readable contract is
[`2026-08-25-qwen38-q4km-tp2-http-depth-r1-prereg.json`](../data/2026-08-25-qwen38-q4km-tp2-http-depth-r1-prereg.json).
The runner is
[`run-qwen38-q4km-tp2-http-depth-r1.sh`](../scripts/run-qwen38-q4km-tp2-http-depth-r1.sh).

It uses the accepted protected source at commit `a4349bcee`, its exact
oneAPI-2026.1.1 AOT binary, the manifest-matching Q4_K_M weights, equal TP2,
F16 KV, target-only generation, one HTTP slot, cache disabled, and a 33,024
token capacity. The source's intentional three-file dirty patch state is
recorded but never modified.

Every point must return exactly 128 token IDs, report the requested actual
prompt count, remain cache-zero, and avoid truncation/context shift. The
fixture is evidence grade C: it fixes context shape with registered repeated
tokens and is not natural prose. No zero-context point, interpolation, or
extrapolation is permitted.

## Terminal outcomes

- Six passing receipts: publish the additive TP2 decode and TTFT profiles.
- Model, binary, source, fixture, token-count, cache, or context mismatch:
  fail closed and retain the attempt as invalid evidence.
- Fit/OOM/unsupported at a depth: publish that exact tested limitation; do
  not substitute a smaller requested context or a TP1 result.

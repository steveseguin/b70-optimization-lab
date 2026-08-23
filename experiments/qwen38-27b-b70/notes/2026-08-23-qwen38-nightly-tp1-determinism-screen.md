# TP1 nightly determinism screen: cache replay seals execution; fresh compiles still diverge

Date: 2026-08-23. Structured evidence:
[`2026-08-23-qwen38-nightly-tp1-determinism-screen.json`](../data/2026-08-23-qwen38-nightly-tp1-determinism-screen.json).

This was an isolated candidate program. It did not change the historical
driver, overwrite any raw result, or alter the recorded `30.2178 / 30.2569`
TP1 graph pair.

## Frozen screen

The identity was TP1, MTP off, F16 KV, 32K max length, one sequence, XPU
Graph on, GPU0, memory utilization `0.90`, and `PYTHONHASHSEED=0`. The speed
floor was `29.31 tok/s` conventional, three percent below the historical
`30.22` headline. Two prompts known to flip were used at 128 tokens before
any full-suite expansion.

With the nightly's autotune defaults, fresh cache A measured `30.8418`, exact
replay A measured `30.7249`, and fresh cache B measured `30.8025 tok/s`.
Fresh A and replay A matched 2/2 complete token streams, and replay left the
1,097-file cache manifest byte-identical. Fresh B differed from A at token 18
of `selection--technical-guide`. This localizes the observed variability to
fresh compile generation rather than request execution within a sealed cache.

## No-autotune candidate

The preregistered next door explicitly set all three controls to zero:

- `VLLM_ENABLE_INDUCTOR_MAX_AUTOTUNE`;
- `VLLM_ENABLE_INDUCTOR_COORDINATE_DESCENT_TUNING`;
- `TRITON_CACHE_AUTOTUNING`.

Two independent fresh caches matched 2/2 at 128 tokens and measured `30.8400`
and `30.8705 tok/s`, so the candidate qualified for the full 25 prompts. The
full sealed-cache replays then measured `30.2312 / 30.2565 tok/s`
conventional. Every row had 512 returned token IDs, every cached-token count
was zero, and both cache manifests remained unchanged.

The full outputs matched only 19/25. First divergences appeared at token
indices 118, 135, 166, 307, 338, and 386 across six prompts. The candidate
therefore preserves the 30.2-class speed but does **not** seal independent
fresh compiles. It is rejected for promotion.

## Frozen interpretation

- Do not lower or rewrite the historical speed evidence; this candidate
  reproduced it within `0.13%`.
- An exact sealed cache is sufficient for repeat execution of one compiled
  identity on the screened prompts.
- `PYTHONHASHSEED=0` plus disabled autotuning is insufficient for cross-compile
  token determinism across the full suite.
- Keep the cross-boot disclosure on TP1/TP2/TP4 graph results. A natural-EOS
  submission gate cannot by itself remove it.
- Stop this candidate lane. Advance an independent matrix cell rather than
  adding post-hoc determinism flags.


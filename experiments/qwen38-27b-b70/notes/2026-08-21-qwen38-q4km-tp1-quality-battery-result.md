# Qwen3.8 Q4_K_M TP1: quality battery pass and final-binary capture

Date: 2026-08-21

Status: **all quality gates pass; the lane's official capture on the final
binary is `27.813629` / `27.824790 tok/s`, 24/24 hashes exact against the
registered oracle.**

## Quality battery

`scripts/qwen38-text-quality-suite.py` against a fresh TP1 server on GPU 0
(final lane binary, quality run at ctx 16384 — quality gates only, no
timing quoted from it): **`pass_all=true`** —

- seven exact canaries: arithmetic, code-execution, copy-phrase, factual,
  JSON-schema, logic, exact-ok — all true;
- repeat stability: 8/8 identical;
- long-context needle: pass;
- `baseline_match_all=true`.

Evidence:
[`../data/2026-08-21-q4km-tp1-gpu0-quality-battery.json`](../data/2026-08-21-q4km-tp1-gpu0-quality-battery.json).

## Final-binary official capture

Two fresh-server cold 12-prompt suites at the registered lane identity
(ctx 8192, GPU 0, cache-zero on all requests, gates passed):

- I: `27.813629 tok/s` conventional median, 12/12 output hashes identical
  to the registered TP1 oracle;
- J: `27.824790 tok/s`, 12/12.

The shipping binary (with the rejected Q8OUT door off and the q8-memo
hardening) reproduces the oracle byte-for-byte; the lane's quotable state is
**27.81-27.86 tok/s** across the final four captures (G/H/I/J), `+6.8-7.0%`
over the day-open baseline, with the full battery green. Evidence:
[`../data/2026-08-21-q4km-tp1-gpu0-final-i.json`](../data/2026-08-21-q4km-tp1-gpu0-final-i.json),
[`../data/2026-08-21-q4km-tp1-gpu0-final-j.json`](../data/2026-08-21-q4km-tp1-gpu0-final-j.json).

## Promotion posture

The lane now satisfies exactness, cold/cache-zero, semantic, repeat, and
needle requirements on its own oracle. Before any LocalMaxxing submission:
confirm the 1-GPU category standing for this model class, and record the
promotion provenance snapshot (source tree HEAD + patch artifacts already in
`patches/qwen38-27b-q4km-tp1-b70s/`). Submission remains a separate
downstream action per `MANAGER.md`.

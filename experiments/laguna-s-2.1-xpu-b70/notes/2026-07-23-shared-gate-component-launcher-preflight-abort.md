# Shared-gate component launcher preflight abort

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Classification

- Outcome: pre-device tooling abort; no component result.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T022000Z.json`
- Authorization commit: `bc67028c4d423ea73531d07843f6aadadbce60d3`
- Tools commit: `01a3c20df6edb961f16360a18ba9c721127ae7b3`
- Launcher exit: `2`
- Diagnostic:
  `component launcher rejected: launcher invocation differs from frozen argv`
- Campaign root: absent.
- Canonical preflight-failure sibling: absent.
- XPU discovery, component kernels, model generation, counters, endpoint work,
  network access, reboot, and submission: not started.

This authorization is retired and must not be rerun.

## Root cause

The launcher reconstructed the exact canonical coordinator argv correctly, but
compared it with an unquoted right-hand operand inside Bash `[[ ... == ... ]]`.
The JSON begins with `[` and was therefore interpreted as a pattern instead of
as a literal string. Independent `jq` output showed that the actual and frozen
JSON arrays were byte-identical.

## Correction

Materialize the frozen argv JSON once as `EXPECTED_ARGV` and quote both operands
of the Bash comparison. Add a regression assertion for the literal comparison,
run the full CPU-only component and Stage 0 suites, then seal a new tools commit
and a fresh packet-only child with a new NVMe campaign root. The failed packet
and its nonexistent root are never reused.

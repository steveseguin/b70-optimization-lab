# MiniMax Website Quality Metrics V2 Addendum

Date: 2026-05-22

## Purpose

The simple 4K website task is now the practical quality gate for the fast
MiniMax M2.7 AutoRound path. The task is intentionally narrow but useful:
generate a complete static HTML status page. A candidate only counts if it
passes strict validation; malformed graph-corrupted candidates are rejected and
retried.

## Current Promoted Result

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Path:
  `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T082745Z-skeleton-graph-prefill-prefixcache-instruct-metricsv2-repeat30/result.json`
- Command shape:
  `--mode graph --prompt-format chat --assistant-prefill skeleton_open --task skeleton_status_html --repeat 30 --retry-until-pass 5 --max-tokens 96 --max-model-len 4096 --max-num-batched-tokens 512 --enable-prefix-caching`
- Result: 30/30 accepted, 32 total candidate attempts, 2 rejected candidates.
- First-attempt pass rate: `93.3%`.
- Cold-inclusive effective accepted output: `85.46` tok/s.
- Post-first steady-state effective accepted output: `88.46` tok/s.
- Accepted-output mean decode: `93.40` tok/s.
- Post-first accepted-output mean decode: `95.14` tok/s.

This is still not proof that the forced XPU graph path is generally
quality-safe. It is a validated/retry-bounded simple-site workflow. The
remaining performance work is to remove the two rejected graph-corrupted
candidates without falling back to the slow no-graph path.

## Negative Screens

- Bad-words filtering on known corruption fragments was worse: repeat-30 stayed
  30/30 accepted after retry, but needed 33 candidate attempts and fell to
  `81.98` effective accepted tok/s.
- Lowering `max_tokens` from 96 to 64 preserved delivered quality, but stayed at
  two rejected candidates and fell slightly to `84.77` effective accepted tok/s.

## Harness Patch

Patch record:
`patches/minimax-website-harness-post-first-metrics-20260522.patch`

The harness now reports both cold-inclusive and post-first steady-state metrics
so future result summaries can be honest about first-request overhead while
still showing the warmed decode path separately.

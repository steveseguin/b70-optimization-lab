# Codex handoff: publish the deterministic Flash-Next line on the family page

Date: 2026-09-03. Owner of the family/package schemas: Codex. The lab
record is in `results/qwen38-flash-next-fp8-b70/README.md` (section
"Deterministic full-decode-graph line") and the notes/data linked there.

What to add to `families/qwen-flash-next.json` (validate with
`tools/build-family-pages.py`; the coverage contract's `graph_mode` axis
currently lists only `off` and `PIECEWISE`, so `FULL_DECODE_ONLY` needs an
axis value and a rule):

- `run_measurements`: two `lab-measured` entries on
  `runtime` "vLLM XPU 2169dbfe (overlay on 1372c62d) + staged kernels 2f829747",
  `config` tp 4 / ep 4 / mtp 0 / graph_mode FULL_DECODE_ONLY / kv auto /
  configured_max_context_tokens 4352:
  - short (`active_context_tokens` 0): decode_tok_s samples
    22.966002 (A73 median of 22.966002/23.898996/22.256402) and
    22.355390 (A78 median of 22.355390/23.350884/22.321053); evidence
    `experiments/qwen38-flash-next-fp8-b70/data/20260903-tp4-mtp0-a73-exact-4k-deterministic-summary.json`
    and `...a78-fresh-repeat-deterministic-summary.json`;
  - exact 4K (`active_context_tokens` 4096): conventional 99-interval rows
    12.728316 / 12.825225 (A73) and 13.498466 / 12.241721 (A78), TTFT
    98.68 / 89.51 / 102.52 / 96.36 s, median 12.776770;
  - exact 2K (`active_context_tokens` 2048): 13.514374 / 14.909545 (A73),
    13.443310 / 14.471953 (A78), median 13.993164.
- `quality_scope`: 6/7 semantic (sole miss `code_execution=30`), 16/16
  repeat, exact cache-zero 2K needle; outputs identical across five servers;
  logit-exact probes at depths 8-4096.
- `featured_results`: make the exact-4K row the hero (12.78 tok/s, no
  speculation, deterministic) and keep the MTP3 eager 15.50 screen listed
  as the native-line, non-deterministic screen.
- The 2304-token triple (A70-A72; short center 23.028483, exact-2K rows
  13.18-14.62) can be a second entry at configured_max_context_tokens 2304.

Nothing in the native-line entries changes.

# MiniMax Website Quality Follow-up

Date: 2026-05-22

## Summary

The previous strict MiniMax AutoRound TP4 speed gates were too narrow for
practical code/website generation. Raw fixed-token, semantic, arithmetic, and
sixpack probes did not catch corrupt HTML/CSS/JS generation under the current
fast XPU graph path.

The high-speed graph recipe can still be useful, but only for a narrower
validated-output workflow right now:

- Compact static HTML task: 8/10 raw attempts passed strict validation.
- Raw speed: `94.99` output tok/s average.
- Effective accepted-output rate, counting rejected attempts: `73.52` tok/s.
- This exceeds the 60 tok/s practical-task floor, but it is not equivalent to
  saying the graph path is quality-safe for richer CSS or JavaScript.

## What Failed

The richer static page with inline CSS is not quality-safe on the fast graph
path:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T042244Z-static-graph-repeat3`
- Result after tightened validation: 0/3 pass.
- Failure modes: malformed CSS, empty CSS properties, stray non-Latin text, and
  recurring corruption fragments such as `kelompok`.
- Speed remained high at about `98.10` tok/s, so this is a correctness problem,
  not a throughput problem.

The same static CSS task with graph replay disabled was much cleaner but slow:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T045312Z-static-cudagraph-none-strict-repeat3`
- Result: 2/3 pass.
- Mean speed: `41.73` tok/s.
- The only failed output contained a single NUL token in `letter-spacing: 0px`.

Replay-safety knobs did not fix the graph corruption:

- `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`: still failed, `98.02` tok/s.
- `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1`: still failed and slowed to `66.20` tok/s.
- strong output plus sync: still failed and slowed to `66.19` tok/s.
- forced recapture after replay: crashed because vLLM rejects graph capture
  during active inference.
- `FULL_DECODE_ONLY` graph mode is blocked by the SYCL graph
  `work_group_scratch_memory` limitation.

## What Works Now

The compact static HTML task is a usable narrow path:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T050735Z-compact-graph-repeat10`
- Task: valid compact single-file HTML status page, no CSS, no JavaScript.
- Passes: 8/10 after strict validation.
- Mean raw speed: `94.99` output tok/s.
- Effective accepted-output rate: `73.52` tok/s.

Adding vLLM `bad_words` for the observed corruption fragments did not help:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T051159Z-compact-graph-badwords-repeat10`
- Passes: 8/10.
- Mean raw speed: `94.31` output tok/s.
- Effective accepted-output rate: `71.74` tok/s.
- Decision: do not rely on bad-words filtering as a correctness fix.

The harness now supports `--retry-until-pass N`, so a production-style compact
HTML task can reject malformed outputs and retry without accepting corrupted
content. The first retry run wedged during XCCL startup after a previous
graph/no-graph crash, so it is not counted as evidence yet.

## Follow-Up Runs

After adding malformed-angle checks and exact compact-task list/table counts,
one previously accepted compact retry output was reclassified as invalid because
it contained malformed markup (`<td>1 </</td>`). The earlier `79.57` effective
accepted tok/s number should not be claimed as clean.

Clean stricter compact result:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T054332Z-compact-graph-retry5-repeat10-stricter/result.json`
- Task: `compact_status_html`
- Result: 10/10 accepted, 14 total attempts, 4 rejected attempts.
- Effective accepted output rate: `71.07` tok/s.
- Accepted-output mean decode rate: `94.99` tok/s.

Broader original micro semantic task:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T054706Z-micro-graph-retry5-repeat10-stricter/result.json`
- Task: original `micro_status_html`.
- Result: 10/10 accepted after retry, 19 total attempts, 9 rejected attempts.
- Effective accepted output rate: `52.57` tok/s.
- Accepted-output mean decode rate: `99.81` tok/s.
- Interpretation: quality-clean after retry, but below the 60 tok/s effective
  target because too many first attempts were corrupted.

Compact semantic prompt optimization:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T055146Z-microcompact-graph-retry5-repeat10/result.json`
- Task: tightened `micro_status_html` prompt with compact semantic HTML.
- Result: 10/10 accepted, 12 total attempts, 2 rejected attempts.
- Effective accepted output rate: `74.10` tok/s.
- Accepted-output mean decode rate: `95.88` tok/s.
- Validator required complete HTML, ASCII-only content, no control characters,
  no known corruption fragments, no malformed raw angle fragments outside
  script/style, `main`, `section`, `ul`, `table`, exactly three list items, and
  exactly four table rows including the header.

This establishes a practical, repeatable, quality-gated static semantic HTML
envelope above 60 tok/s. It does not clear rich CSS/JS generation.

## Interpretation

The fast graph path appears to have a real correctness hazard for longer or more
structured code-like outputs. The repeated corruption signatures are not normal
model mistakes:

- repeated fragments including `kelompok`, `luas`, `alkyl`, `foremost`, and
  occasional CJK text;
- malformed closing tags such as `</alkyl ...>`;
- CSS declarations with missing or empty property names.

Shorter compact HTML reduces exposure enough that validation/retry can keep the
delivered output quality acceptable while sustaining an effective rate above
60 tok/s. The best current practical result is the compact semantic HTML prompt
at `74.10` effective accepted tok/s. This does not clear the graph path for CSS,
JavaScript, or richer website generation.

## Next Steps

1. Add a stronger source-level graph correctness probe that compares token
   hashes for identical compact prompts across graph and graph-disabled modes.
2. Keep debugging the XPU graph communication boundary, especially
   `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1` and compiled allreduce interactions.
3. Test whether the compact semantic prompt remains clean over a longer repeat
   count, for example 30 accepted outputs with retry capped at 5.
4. Do not submit these website task results to LocalMaxxing as model throughput
   benchmarks; they are quality-gate diagnostics, not standard leaderboard
   runs.

## Data

- Structured follow-up:
  `data/minimax-m27-website-quality-followup-20260522.json`
- Replay safety matrix:
  `data/minimax-m27-website-replay-safety-matrix-20260522.json`

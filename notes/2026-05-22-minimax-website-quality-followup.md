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

Longer and narrower simple-site validation:

- Tiny no-CSS/no-JS status page:
  `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T062422Z-tiny-graph-retry5-repeat30/result.json`
- Result: 30/30 accepted, 40 total attempts, 10 rejected attempts.
- Effective accepted output rate: `68.98` tok/s.
- Accepted-output mean decode rate: `91.78` tok/s.
- Interpretation: valid practical HTML after retry, but still too many graph
  corruption rejects for a clean >70 tok/s result.

Near-template skeleton status page:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T063545Z-skeleton-graph-retry5-repeat30/result.json`
- Result: 30/30 accepted, 37 total attempts, 7 rejected attempts.
- First-attempt pass rate: `76.7%`.
- Effective accepted output rate: `71.12` tok/s.
- Accepted-output mean decode rate: `87.76` tok/s.
- Interpretation: this is the best repeat-30 simple practical website result so
  far. It is quality-gated and repeatable, but it is still not a source-level
  correctness fix because rejected attempts include the same corruption
  signatures.

Scaffolded assistant-prefix continuation:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T074800Z-skeleton-graph-prefill-repeat30/result.json`
- Change: prefilled the fixed HTML opening as assistant text, then validated the
  complete document after reattaching the prefix.
- Result: 30/30 accepted, 33 total attempts, 3 rejected attempts.
- First-attempt pass rate: `90.0%`.
- Effective accepted output rate: `64.57` tok/s.
- Accepted-output mean decode rate: `71.82` tok/s.
- Interpretation: quality is preserved by validation, but the generated suffix
  shape was slower than the unprefilled skeleton run.

Scaffolded continuation with prefix caching but without the explicit chat
instruction:

- Path: `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T081000Z-skeleton-graph-prefill-prefixcache-repeat30/result.json`
- Result: 30/30 accepted, 33 total attempts, 3 rejected attempts.
- First-attempt pass rate: `90.0%`.
- Effective accepted output rate: `64.92` tok/s.
- Accepted-output mean decode rate: `72.00` tok/s.
- Decision: positive versus the slow fallback, but not a promotion over the
  older skeleton result.

Scaffolded continuation with prefix caching and an explicit chat instruction:

- Primary path:
  `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T083000Z-skeleton-graph-prefill-prefixcache-instruct-repeat30/result.json`
- Repeatability path:
  `/home/steve/bench-results/minimax-m2.7-website-quality/20260522T084000Z-skeleton-graph-prefill-prefixcache-instruct-repeat30-rerun/result.json`
- Command shape:
  `--mode graph --prompt-format chat --assistant-prefill skeleton_open --task skeleton_status_html --repeat 30 --retry-until-pass 5 --max-tokens 96 --max-model-len 4096 --max-num-batched-tokens 512 --enable-prefix-caching`
- Primary result: 30/30 accepted, 32 total attempts, 2 rejected attempts,
  `93.3%` first-attempt pass rate, `85.13` effective accepted tok/s,
  `93.18` accepted-output mean decode tok/s.
- Repeatability result: 30/30 accepted, 32 total attempts, 2 rejected attempts,
  `93.3%` first-attempt pass rate, `85.74` effective accepted tok/s,
  `93.46` accepted-output mean decode tok/s.
- Delivered output quality: accepted outputs are complete ASCII HTML documents
  with `html`, `body`, `main`, `section`, `h1`, `p`, `ul`, exactly three list
  items, and `footer`. A representative accepted output is:
  `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>B70 MiniMax Lab Status</title></head><body><main><section><h1>B70 MiniMax Lab Status</h1><p>All systems operational.</p><ul><li>GPUs ready</li><li>Model loaded</li><li>Benchmarks passing</li></ul></section></main><footer>Updated: Ready</footer></body></html>`
- Rejected candidates were not accepted. Failure examples included
  `<li>Model</</li>` and a `main586 kelompoklarge` fragment. This confirms that
  the graph corruption risk still exists, but validation/retry keeps corrupted
  candidates out of delivered results.
- Decision: promote this as the current practical 4K simple-website recipe. It
  is narrower than free-form website generation, but it is a repeatable,
  quality-gated practical task and is not a reversion to the 42 tok/s no-graph
  fallback.

Additional runtime and compile-path screens:

- `VLLM_XPU_CUDAGRAPH_STRONG_OUTPUT=1`: neutral/negative. It did not remove
  corruption and reduced the effective rate on the compact probe.
- `VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES=1`: neutral/negative. A local
  `env_override.py` patch appended vLLM and c10d collective op names to
  `torch._inductor.config.custom_should_partition_ops`. Skeleton repeat-10 was
  10/10 after retry, but only `51.94` effective tok/s with two rejects, so it
  did not solve correctness and lost throughput. Patch record:
  `patches/vllm-xpu-cudagraph-partition-collectives-negative-20260522.patch`.
- `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=0`: startup failure. vLLM asserts because
  the communicator is `XpuCommunicator`, not `CudaCommunicator`.
- `VLLM_XPU_SYNC_CUDAGRAPH_REPLAY=1` on the skeleton task: quality slightly
  improved but speed fell below target. Repeat-10 was 10/10 after retry with
  one reject, `90.0%` first-attempt pass rate, and `52.90` effective tok/s.
- `VLLM_XPU_FORCE_GRAPH_WITH_COMM=0`: quality-cleaner but effectively returns
  to the slow no-graph path. Skeleton screen was only `20.80` effective tok/s
  because a rejected long attempt dominated elapsed time.
- `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`: neutral. Skeleton repeat-10 was
  `71.29` effective tok/s with two rejects.
- `VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP=0`: hard quality failure.
  Skeleton repeat-10 accepted 0/10 after 50 attempts; outputs degenerated into
  repeated prose/fragments.
- `VLLM_XPU_COMPILE_ALLREDUCE_CUSTOM_OP=0` with a fresh cache: speed regression.
  Skeleton repeat-5 accepted 5/5 after retry, but only `41.11` effective tok/s
  and still had one corruption reject.
- Candidate-batched retries with `max_num_seqs=2`: not useful. With
  `max_num_batched_tokens=1024`, Intel `ocloc`/IGC crashed on a size-2 compile.
  With `max_num_batched_tokens=512`, the run completed but wall-rate to valid
  HTML was only `39.68` tok/s.
- Raw prompt format: rejected. It eventually accepted 10/10 after retry, but
  effective rate fell to `26.58` tok/s because many attempts ignored the HTML
  instruction.
- Max-token caps: safe but only marginal. `max_tokens=160` gave `71.70` tok/s;
  `max_tokens=128` gave `71.88` tok/s on skeleton repeat-10. The rejected
  skeleton attempts are already short, so decode caps do not solve the main
  loss.
- Stricter system prompt: neutral/negative at `71.52` tok/s.

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
60 tok/s. The current promoted practical result is scaffolded skeleton HTML
continuation with prefix caching and an explicit continuation instruction:
two repeat-30 runs produced `85.13` and `85.74` effective accepted tok/s. This
does not clear the graph path for CSS, JavaScript, or richer website generation,
and it still relies on validation/retry to reject occasional graph-corrupted
candidates.

The most important source-level finding is that the fast path depends on
forcing XPU graph capture across communication ops while skipping the
communicator graph-capture context:

- vLLM disables XPU graph automatically when world size is greater than one
  unless `VLLM_XPU_FORCE_GRAPH_WITH_COMM=1`.
- With `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`, vLLM warns that it is skipping the
  communicator capture context for `XpuCommunicator`.
- Turning that no-op shim off fails startup because the upstream code only
  accepts `CudaCommunicator` in the graph-capture context.

That is the likely correctness boundary to fix if we want >80 effective tok/s
without retries and without sacrificing output quality.

## Next Steps

1. Keep debugging the XPU graph communication boundary, especially replacing
   `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1` with a real XPU-safe communicator
   capture or a selective graph break around unsafe collectives.
2. Add a stronger source-level graph correctness probe that compares token
   hashes and hidden/logit checks for identical compact prompts across graph
   and graph-disabled modes.
3. Preserve the current production-safe workflow as: chat prompt, closed
   thinking prefix, scaffolded skeleton/simple static HTML task,
   `max_tokens=96`, prefix caching, strict validator, retry cap 5.
4. Do not submit these website task results to LocalMaxxing as model throughput
   benchmarks; they are quality-gate diagnostics, not standard leaderboard
   runs.

## Data

- Structured follow-up:
  `data/minimax-m27-website-quality-followup-20260522.json`
- Replay safety matrix:
  `data/minimax-m27-website-replay-safety-matrix-20260522.json`
- Continued quality/performance screens:
  `data/minimax-m27-website-quality-continued-20260522.json`

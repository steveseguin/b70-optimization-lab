# Model Effort Index

This page is the cross-model work queue and archive. It is meant to help the
next agent switch models without rereading every historical note.

## How To Add A Model Effort

Create or update the smallest set of files that makes the lane understandable:

1. `results/<model>-<hardware>/README.md` for promoted or closed-out outcomes.
2. `results/<model>-<hardware>/validity-gates.md` for what counts as a record.
3. `results/<model>-<hardware>/reproduce.md` for the best known commands.
4. `results/<model>-<hardware>/bugs-failed-paths.md` for invalid fast lanes and
   failure signatures.
5. `notes/YYYY-MM-DD-<model>-...md` for chronological experiment notes.
6. `patches/<model>-...patch` for source or config deltas worth preserving.
7. `data/<model>-...json` for compact structured result evidence.

Do not move old files just to make the tree look tidy. Add indexes and links
unless a file is clearly misplaced and no one is likely to reference the old
path.

## Active / Recent Efforts

| Effort | Main Entry | Current Decision |
| --- | --- | --- |
| Gemma 4 26B A4B Q8 / INT8 on B70 | [results/gemma4-26b-a4b-q8-b70](../results/gemma4-26b-a4b-q8-b70/README.md); strict plan: [research-plan](../results/gemma4-26b-a4b-q8-b70/research-plan.md); latest negative: [adaptive MTP depth cap](../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1841-realistic-adaptive-mtp-dpnmax.md) | Active but at a diminishing-returns frontier unless doing a larger router/speculation/verifier design. Current policy-compliant one-B70 Q8-target record is llama.cpp `c926ad098`, UD-Q8_K_XL target/verifier with Q4_0 MTP draft verified by the target, fixed realistic cold prompt suite, `cached_tokens=0` every request, no cache/history reuse: `87.61145306230438 tok/s` median generated-token throughput for tokens 1-100 after TTFT, p10 `77.54715049816033`, mean `86.63390357338118`, LocalMaxxing `cmqwnl2ag03lgqr01ch5bxknq`. The older `104+` and `176+ tok/s` filled-long rows are diagnostic/pre-final-gate only, and the draftless `ngram-mod` `245-280 tok/s` rows are warmed/history artifacts. Recent adaptive MTP depth-cap work, including an MTP `dp.n_max` generation-stop fix, passed the strict gate but topped out at `83.342 tok/s`; do not submit it. Next high-ROI Gemma work should reduce target/verifier MoE or LM-head cost, improve fresh-valid speculation, or build a structural verifier shortcut; avoid more LocalMaxxing submissions unless the realistic cold-suite gate beats `87.611`. MiniMax TP4 is optional side repair, not the primary lane while Gemma remains the user priority. |
| Gemma 4 12B IT INT4 AutoRound | [experiments/gemma4-12b-int4-autoround-vllm](../experiments/gemma4-12b-int4-autoround-vllm/README.md) | Current model-slot production profile is c8. c10 is research-only; c12+ hit boundary failures. |
| MiniMax M2.7 INT4 AutoRound | [repro/minimax-m27-b70-110tps-ubuntu24-20260523](../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md) | Best next optimization lane after Gemma Q8 micro-sweeps flattened. Strict speed lane is `89.314195` output tok/s / `119.085594` total at p512/n1536; deployable 32K endpoint baseline is about `83-84` output tok/s. Future speed work should target hidden-state collective and graph-boundary fusion, especially MoE-output allreduce plus epilogue or attention `o_proj` allreduce plus residual/RMSNorm, not more env flag sweeps. |
| Qwen3.6 35B A3B Quark W8A8 INT8 | [results/qwen36-35b-quark-int8-b70](../results/qwen36-35b-quark-int8-b70/README.md) | Closed for now. No valid `>150 tok/s` path found; best strict 4x baseline is `93.55 tok/s`. |
| Qwen3.6 27B Q4_0 / FP8 historical lanes | [results/fp8-vllm-xpu-qwen36-2026-05-04.md](../results/fp8-vllm-xpu-qwen36-2026-05-04.md) and older notes | Useful reference for SYCL/llama.cpp and FP8 vLLM patterns. Reopen only with a clear record target. |
| DeepSeek V4 Flash AutoRound | [experiments/deepseek-v4-flash-autoround-vllm](../experiments/deepseek-v4-flash-autoround-vllm/README.md) | Candidate future lane. Needs fresh validity gates before promotion. |

## Cross-Model Lessons

- Lock benchmark identity before interpreting speed. Missing graph mode or a
  changed launcher can create false regressions or false wins.
- Treat fast speculative paths as invalid until canaries pass at scale. The
  Qwen36 lane had multiple 75-199 tok/s "wins" that failed quality or were
  synthetic.
- Preserve negative patches and logs. MiniMax improved because dead ends were
  visible; Qwen36 became hard when failed branches were not summarized quickly.
- Prefer model-specific result packets over giant branch merges. Curated
  packets are easier to merge and reuse than mixed experiment branches.
- Keep LocalMaxxing payloads and responses in `data/`, but keep API keys outside
  Git as documented in [localmaxxing.md](localmaxxing.md).
- For one-replica-per-GPU work, prefer four independent servers and four
  disjoint experiments before trying tensor parallelism. This is especially
  relevant to Gemma 4 26B A4B, where the goal is to avoid PCIe collectives.
- LocalMaxxing headline submissions must come from the fixed realistic
  cold-response suite. Synthetic filled-long, repeated, warmed, cached,
  n-gram/history, or continuation-learned scores can guide optimization but
  must remain diagnostic unless revalidated by that gate.

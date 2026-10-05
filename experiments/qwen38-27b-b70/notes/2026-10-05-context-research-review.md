# Context research review: self-editing context, exact long context, one-step decisions (2026-10-05)

Research only: no GPU work, no servers, nothing committed. Companion to `2026-10-05-context-window-prereg.md`.

## The short answer (plain words)

- **The paper is real and the code is real.** "Context Language Models" (Shao et al., arXiv 2609.37725,
  https://arxiv.org/abs/2609.37725) lets the model rewrite its own conversation as a text file. Code:
  https://github.com/facebookresearch/context-language-models (exists, matches the article; one gap: the benchmark,
  ContextBench, is not released yet).
- **What we can use as-is:** the harness. It talks to any OpenAI-compatible server, so it can talk to our vLLM. The
  model choosing what to keep is an *informational* edit (allowed by the owner); the arithmetic stays exact.
- **What we must not use:** the paper's serving speed-up, "Suffix Cache Reuse". It reuses cached numbers that were
  computed for the old, pre-edit text. The authors say themselves it "approximates re-prefilling". Same for
  CacheBlend, attention-sink / sliding-window methods, KV quantization and CacheGen.
- **Biggest practical point for this lab:** we already have a 268K-token exact window on two cards. The paper's
  headline results are at 32K, and its own 128K run scored *higher* than its 32K runs. So: open the exact window first,
  and add self-editing on top for tasks that run longer than any window.
- **Disk does not make the window bigger.** Text on disk (notes the model can grep) is unlimited and exact. KV cache on
  disk only saves re-reading time; the model can only attend to what is loaded on the GPU.
- **One-step decisions are exact** when done as constrained greedy choice and the choices start with different
  tokens: one forward pass gives exactly the answer that constrained greedy decoding would give. Reading the answer
  from hidden states with a probe is *not* equivalent.
- **Today's blocker for edit-heavy work:** our published lanes run with prefix caching off. Every turn re-reads the
  whole prompt (about 16 s at 32K at roughly 2,000 tok/s measured prefill). Exact prefix reuse needs a fix first (E0
  below): our own probe found cache-hit outputs can differ from cold prefill on tie-sensitive prompts.

Claims I could not check against a primary source are marked **[unverified]**. Paper numbers are author-reported and
have not been independently reproduced.

---

## (a) The paper in about fifteen lines

1. A normal LM only appends: next context = old context + new output. A "CLM" may produce the next context any way it
   likes: c(t+1) = f(c(t)).
2. Implementation: the harness writes the live conversation (everything after the pinned system prompt and task) to
   `/tmp/.live_ctx/LIVE_CTX_MAIN.txt`, one `[[CTX_TURN i role=...]]` block per message, refreshed before every command.
3. The model has one tool, `bash`. To compact, it edits that file with `sed`, `python3`, `cat >`, etc. If the file
   changed, the harness parses it back into messages and sends the new message list on the next call; otherwise
   output is appended as usual.
4. The harness adds budget nudges (at 25/50/75% of budget, and an urgent one near the limit), rolls back the newest
   turns and asks for compaction when over the limit, and an "edit gate" (`fit` or `shrink`) rejects edits that grow
   the context too much.
5. Cost metric: "prefix-reuse FLOPs" = FLOPs to re-prefill everything after the first changed token, plus decode.
   An edit early in the context is expensive because everything after it is re-read.
6. Zero-shot, Qwen3.6-27B at a 32K budget: BrowseComp-Plus 59.4%, 11.4% (relative) above Codex-style summarisation,
   with 21.5% fewer prefix-reuse FLOPs; matches summarisation on TerminalBench 2.1 at 70% of its FLOPs; TBLite 73.7%
   vs 67.0%.
7. Long runs: 12-hour EdgeBench-10 (Qwen3.6-27B) 44.6 vs 42.3 for summarisation at 179 vs 437 PFLOPs per trial; a
   24-hour six-agent "Software World" swarm with GPT-5.6-Sol gets 65% more downstream speedup at equal spend.
8. ContextBench: four synthetic tasks (keep needles verbatim, edit a Sudoku board in place, store/recall key-values,
   triage logs) that isolate context management; every baseline fails somewhere as input grows up to 24x the window.
9. Steering: one sentence in the prompt changes when and how the model compacts.
10. Prompt evolution (GEPA-style) of a "skill" document raises held-out KV Store accuracy from 38.3% to 74.2%.
11. RL: Qwen3.5-9B with stepwise GRPO plus a "success-gated efficiency" bonus goes from 28.8% to 42.5% on
    BrowseComp-Plus, matching a trained summariser (42.1%) at 1.34 vs 2.19 PFLOPs per question.
12. Multi-agent: several context files coexist; sub-agents are started and stopped by creating and deleting files.
13. Suffix Cache Reuse (SCR): after an edit, reuse cached keys/values of text that survived the edit, re-rotating
    positions; 65% of standard SGLang's compute at the same accuracy (60.2% both) on BrowseComp-Plus. Approximate.
14. Emergent behaviours: scoreboards edited in place 163 times, a new "notes" role, reusable compaction functions.
15. Safety: editable context is a channel for persistent prompt injection and self-generated instructions; defences
    are left to future work.

---

## Paper details the owner asked for (verified from the full text and appendices)

Sources: HTML full text https://arxiv.org/html/2609.37725v1 and PDF https://arxiv.org/pdf/2609.37725 (v1, 29 Sep
2026, CC BY 4.0). Secondary write-up: https://mer.vin/news/context-language-models-let-the-model-edit-its-own-context-as-a-file/
(consistent with the paper; adds no new facts; it correctly flags "no independent replication", "prefix-reuse FLOPs
are not latency or GPU-hours", "best of three seeds on EdgeBench", and "no trained weights released").

### Mechanism

- **Mirror:** path given in the system prompt; system prompt and task stay pinned and are not in the editable file.
  The released system prompt (`clm/clm_harness/clm_agent/prompts.yaml`) tells the model: edit the file to replace
  stale regions; locate text with code, never retype it; keep `[[CTX_TURN ...]]` headers; do not `cat` the file;
  "an edit forces everything *after* it to be re-read, so cost grows with how much text FOLLOWS the edit"; batch
  compactions; an editing turn that prints nothing and exits 0 is free (does not count as a task step).
- **Sync:** read-back parses the file into a valid message list; the edit gate accepts or rejects; the model gets a
  one-line receipt.
- **Triggers:** none are mandatory. Nudges at 25/50/75%, a persistent nudge near the limit (adaptive, roughly 90%),
  a reminder 2,048 tokens before the budget (Appendix E), rollback-and-retry when over the limit (6 retries on BCP, 50
  default). Appendix G: models estimate their own context length poorly at long lengths, so token-count hints are
  shown after every tool result.

### Baselines (what each one is)

| Baseline | What it does | Source |
|---|---|---|
| Mini-SWE-Agent ("Base") | bash-only agent, history only grows, no context management; run ends when over budget | https://github.com/SWE-agent/mini-swe-agent |
| Codex-style Summary | harness compacts at 75% of budget with Codex CLI summarisation prompts; everything except system prompt and task becomes one summary message | https://github.com/openai/codex |
| Context Folding | model branches into a sub-trajectory and folds it into a summary on return | arXiv 2510.11967 |
| RLM (Recursive LMs) | long input lives as a REPL variable; the model reads it with code and recursive sub-calls; live context is still append-only | https://arxiv.org/abs/2512.24601 |
| Self-Compact | model decides when to compact; asked every two turns once context exceeds 37% of budget, with a self-check rubric | arXiv 2606.23525 [unverified beyond the paper's citation] |
| ACM | model-triggered `manage_context` (summarise everything since last call) plus offload/retrieve via `query_memory` | arXiv 2607.23809 [unverified beyond the paper's citation] |
| MEM1 | rewrites one consolidated internal state every turn (authors' re-implementation) | ICLR 2026 (per paper) |

### ContextBench (Section 3, Appendix D)

- Input arrives as a stream of operations, each a new user message, so no harness can intercept it. The agent says
  `echo READY_FOR_NEXT_OP` to receive the next one.
- Budget: 32,768 tokens with 2,048 reserved for output, so 30,720 usable; one operation fits in a fifth, everything
  that must be retained fits in half (10% margins). Tokens counted with o200k. Context pressure = total input / 32,768,
  up to 24x.
- Tasks and scoring (all graded from the agent's *context*; answers only held in files get no credit):
  Needle Retention (~4K-token chunks with 2-8 needle lines and 140 filler lines; needles must be verbatim in the final
  context); Sudoku Sketchpad (16x16 board, one move per turn, every board version must be reproduced exactly); KV Store
  (batches of 100 SETs with random 24-word values, 24 GET queries, exact-value accuracy); Log Triage (batches of 14-54
  log lines, 24 lookup/count queries, exact-answer accuracy).
- Model: GPT-5.4 via API; 4 seeds per level (8 for some). Per-method numbers exist only as a plot (Figure 2); I could
  not read exact values from text.
- **Not released.** Repo README lists "Coming soon: ContextBench"; open issue #2 "Release ContextBench on Hugging
  Face". Appendix D is detailed enough to re-implement the generators and graders.

### Qwen3.6-27B zero-shot at 32K (Section 5.1, Appendix E)

- BrowseComp-Plus (830 questions): CLM 59.4%; strongest baseline Codex-style Summary (11.4% relative lower, so about
  53.3% by arithmetic; the exact baseline value is only in the plot). CLM uses 21.5% fewer prefix-reuse FLOPs than
  Summary and 28.9% fewer than MEM1. Settings: vLLM, thinking on, temperature 0.7, top-p 0.95, 4,096 output tokens per
  call, 23,560-token budget, 100 turns, editing turns not counted. Judge: Qwen3.5-27B at temperature 0.
- TerminalBench 2.1 (89 tasks): matches Summary at 70% of its FLOPs. 32,000-token budget, 64-turn cap, 4,096 output
  tokens per call. Qwen3.6-27B edits 2.6 times per task, median peak context 17.6K (Qwen3.5-9B: 1.4 edits, 30.2K).
- TBLite: 73.7% vs 67.0% at 91% of Summary's FLOPs; 2,048 output tokens per call.
- **Inconsistencies to note:** Figure 5 caption says "100-turn cap" for all three benchmarks, but Appendix E says 64
  turns for TerminalBench/TBLite. BCP budget is 23,560 in Appendix E but the released `configs/bcp.yaml` uses 28,672
  and `max_steps: 500` ("100, 500 and 2000 were all used"). EdgeBench subagents: "up to five" in Section 5.1.2, "up to
  six" in Appendix E. Plot header says BCP "avg. context 97K", i.e. far more total text than fits the 32K window.
- FLOP accounting (Appendix C): per token C_token = 48.70 GFLOPs for Qwen3.6-27B (MLP 34.23, full-attention
  projections 3.36, Gated DeltaNet projections 11.12), C_attn = 3.93e5 FLOPs per query-key pair, 16 of 64 layers are
  full attention. The GDN recurrent update, embeddings and LM head are omitted, so it is a theoretical count, not
  time. Worked example, 20,000-token prompt + 500 output: append-only turn 1.41e14 FLOPs, mid-context edit 5.74e14,
  edit at start 10.81e14 (7.7x).
- EdgeBench-10 at 128K (Appendix F): CLM+subagents 50.2, Summary 47.8, CLM 47.3 (219/222/142 PFLOPs); at 32K CLM was
  44.6. Best of three seeds, temperature 0.7.

### RL training (Section 4.2, Appendix E/F, `clm/clm_rl`)

Stepwise GRPO: each model call in a trajectory gets the trajectory's outcome advantage. Efficiency bonus
A_eff = clip((mean_cost_successes - cost_i)/mean_cost_successes, -1, 1) for successful trajectories only, zero when a
group has fewer than two successes; weight 0.25, applied only to tokens of context-editing turns. Qwen3.5-9B, 3,040
OpenResearcher prompts, 8 prompts x 32 rollouts per step, 70 steps, lr 1e-6, KL 0.01, clip [0.2, 0.28], SGLang
rollouts at temperature 0.7, 28K budget, judge GPT-5.4-nano with DeepSearchQA rubric, 16 H200 for the policy and 48
for rollouts. Result table: Summary 34.7 -> 42.1 (4.01 -> 2.19 PFLOPs/Q); CLM 28.8 -> 42.5 (1.52 -> 1.34). The
abstract's "47.6%" is relative (28.8 -> 42.5). Training code is not in the repo: it uses NVIDIA ProRL-Agent-Server +
Slime, and the repo ships two patches. No trained weights are released.

### Prompt evolution (Section 4.2, Appendix E/F, `clm/clm_icl`)

A "skill" text is appended to the system prompt and rewritten by a proposer model (Claude Fable 5.1 for "assisted",
Opus 5 for "self" evolution). Candidate run on 6 training instances, then 12 more, then a development split of 102
instances per task; held-out test 102 x 3 seeds, run once. Four proposers in parallel; stop after five non-improving
proposals. Development accuracy before -> after (Qwen3.6-27B, 32K): Needle 97.6 -> 100, Sudoku 45.3 -> 65.8, KV Store
22.3 -> 83.8, Log Triage 0.0 -> 100. Held-out KV Store 38.3 -> 74.2 (the "35.9 points").

### Multi-agent

Each agent is a context file; a swarm starts with several files; sub-agents are created/terminated by creating or
deleting files. Math problems: up to five sub-agents of 40 turns. Software World: six agents (requests, urllib3 and
four downstream packages) for over 24 hours in the Pi harness, GPT-5.6-Sol, 272K context, cost in USD, score =
geometric-mean instruction-count speedup on 17 held-out benchmarks.

### Suffix Cache Reuse: what exactly is reused, why it is not exact, measured effect

- **Reused:** for context [A B C] edited to [A B' C], the K/V of surviving span C (up to K = 6 largest surviving spans
  per edit) are copied from a session-private side buffer, their RoPE keys are re-rotated to the new positions, and
  spliced in after B'. Only B', the last 16 tokens of each span (`KVREUSE_V6_MIN_EXTEND`) and new tokens are prefilled.
  SGLang 0.5.16 monkeypatch, one GPU (`--tp-size 1`), Qwen3.6-27B only. Side buffer at defaults: 12 sessions x 30,000
  tokens = 21.97 GiB (64 KiB/token).
- **Why not exact (full-attention layers):** C's keys and values were computed while attending to A and B, not A and
  B'. Re-rotation fixes positions only. The paper: SCR "approximates re-prefilling".
- **Why not exact (Gated DeltaNet layers, 48 of 64):** there are no per-token entries to move. The paper text says it
  continues from a recurrent-state snapshot "before the edit"; the released code's docstring says `fork` mode
  "restore[s] the state saved at the end of the previous prompt", i.e. a state that has already consumed B (the
  deleted text) and the old C. Either way the recurrence never sees B', and in `fork` mode the linear layers keep
  "remembering" text the model deleted. (Discrepancy between paper text and code comment; I read the code comment in
  `suffix_cache_reuse/overlay.py`, not the full control flow.) A `strict` mode exists but is not the default.
- **Measured (Figure 11 HTML / Figure 9 PDF, BCP, Qwen3.6-27B, 830 questions):** accuracy 60.2% vs 60.2%; prefix-reuse
  PFLOPs per question 10.98 -> 7.14 (65.0%). All turns: standard = 72.9% prefix hits / 27.1% prefilled; SCR = 73.9%
  prefix hits / 7.8% relocated / 18.3% prefilled. Edited turns: 24.2/75.8 vs 29.9/28.2/41.8. Of the 7.8% relocated,
  5.3 points come from the chat template stripping old reasoning blocks and only 2.5 from model edits. K sweep on 64
  questions: no accuracy change observed, gains saturate by K = 6. Equal accuracy at temperature 0.7 on one benchmark
  is a statistical claim, not numerical equivalence.
- **Authors' own note:** much remaining waste is unchanged *prefix* that SGLang fails to reuse because hybrid-model
  recurrent states are only checkpointed at request boundaries. Finer checkpoints (e.g. message boundaries) would help
  exact prefix caching too. This part is directly relevant and exact.

### Repository (checked via GitHub API and a shallow clone, HEAD 18dc111, 30 Sep 2026)

- Exists, public, Python, ~500 stars. Layout: `clm/clm_harness` (Harbor agent `clm-minimal`, context env, edit gate,
  budget/nudges, FLOPs metrics, configs `bcp.yaml`/`edgebench.yaml`), `clm/clm_icl` (skill evolution),
  `clm/clm_rl` (README + two patches only), `suffix_cache_reuse` (SGLang patch, tests, analysis script).
- Install: Python 3.12-3.13, `pip install -e .` pulls `harbor==0.16.1`, `litellm`, `tiktoken`, `pyyaml`
  (`transformers` optional for exact tokenizer counts). Tasks run in Harbor environments (Docker by default;
  Singularity option).
- Pointing at our server: `clm-harbor run -p <task> -a clm-minimal -m openai/<served-name> --agent-kwarg
  api_base=http://localhost:<port>/v1`. Needs tool calling on the server; the README's vLLM example uses
  `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`, and the server window must hold
  `context_budget_tokens + max_tokens`. **Default `max_tokens` is 16,384 with a 32,000 budget = 48,384 tokens; our
  33,024-token window will reject that,** so set `max_tokens=4096` (as the paper did) or open the window. FLOPs
  accounting uses Qwen3.6-27B constants (`flops_model_key 27b`); whether Qwen3.8-27B has the same shape is
  [unverified].
- ContextBench is **not** in the repo. Other open issues: an OpenCode port, a Pi plugin (`@lolipopshock/pi-clm`),
  "auditable context management", a fix for SCR diff helpers.
- **Licence:** code is **CC BY-NC 4.0** (non-commercial), while the paper is CC BY 4.0. NOTICE credits mini-swe-agent
  (MIT) and Harbor (MIT, used as a dependency). If the lab's published packets are ever commercial, do not vendor this
  code; re-implementing the idea from the paper is the safer route.

---

## (b) What applies here, question by question

Facts used below: 262,144 trained positions; two-card 16-bit KV pool about 268K tokens; one card about 44K; host 15 GiB
RAM, 8 cores; measured prefill on our lanes about 2,000 input tok/s at 2K-12K prompts (lab notes 2026-09-1x;
long-prompt speed not yet measured); published lanes run with prefix caching **off**. If Qwen3.8-27B keeps Qwen3.6-27B's
attention shape (16 full-attention layers, 4 KV heads, head dim 256) [unverified for 3.8], 16-bit KV is 64 KiB/token:
32K = 2 GiB, 262K = 16 GiB per sequence. The Gated DeltaNet state is a fixed size per sequence (tens to a few hundred
MB depending on dtype) [unverified exact size].

**Q1. Can the 27B get effectively unlimited context by editing its own context (continuously, or past ~75%)?**
Unlimited *task length*, yes in principle: the paper runs 12- and 24-hour jobs inside 32K. Unlimited *memory*, no:
whatever the model deletes is gone unless it first wrote it to a file. With offload-to-files (grep it back later) the
store is unlimited and exact; recall then depends on the model remembering to look. The paper's Qwen3.6-27B, zero-shot,
was a competent editor (2.6 edits per TerminalBench task, median peak 17.6K of 32K). Triggering: the paper's CLM edits
whenever it chooses, with nudges at 25/50/75%; its Summary baseline compacts at a fixed 75%. Both are easy to run here.

**Q2. Is ~32K enough?**
For the paper's tasks it was enough to beat the baselines, but the paper's own 128K EdgeBench runs scored higher (47-50
vs 44.6), and nobody in the paper compared "32K + self-editing" with "just a 262K window, no editing" on the same task.
We can: our exact window is 268K. Expected sensible setting [my analysis]: a large exact working window (64K-128K) plus
self-editing at about 75%, so edits are rare and each one is cheap relative to the work done.

**Q3. One GPU runs the model and the other prunes, or both work and pause to prune?**
In CLM the editor *is* the model; an edit is just another turn. Our 27B lane uses both cards together (TP2), so the
natural design is "both cards work, the model pauses to edit". Splitting into two one-card servers (one worker, one
pruner) cuts each to a ~44K window and the slower one-card lane, and the pruner would be a second 27B with no more
knowledge than the first. A separate pruner only makes sense as a much smaller model, which would not need a B70.
[my analysis; not tested]

**Q4. Can context live on disk instead of VRAM?**
Two different things:
- *Text on disk* (notes, offloaded tool outputs, the full transcript): yes, unlimited, exact; the model greps it back.
  This is what CLM, ACM, RLM and MemGPT/Letta do.
- *KV cache on disk or host RAM* (LMCache, vLLM offloading connector, llama.cpp slot save/restore): byte-exact storage,
  but it does **not** enlarge the attention window. Attention reads keys from GPU memory; storage only saves the time
  to re-read a prompt when a session comes back. Host RAM (15 GiB) fits about seven 32K snapshots or less than one
  262K snapshot. Disk fits many.

**Q5. Can the CPU help?**
- Safe, information-preserving hygiene before text enters the context: drop exact duplicate tool outputs (replace with
  "same as turn 7"), strip ANSI colour codes and progress bars, collapse repeated identical log lines with a count,
  minify JSON, keep only the changed lines when a file is re-shown (a diff). All are cheap on 8 cores. These change
  the tokens (so the model's output changes), but no information is lost and the original is kept on disk.
- A small CPU-only classifier/model that deletes "known-wasteful" spans: possible and deterministic if CPU threads
  are pinned, but it is an informational *lossy* edit: it decides what the 27B never sees. Treat it like the paper's
  baselines: measure task accuracy, not just tokens saved.
- 32K -> ~100K effective (3x) from lossless hygiene alone is plausible only for very repetitive logs; for typical text
  I would not expect it [unverified; measure on our own transcripts, E3 below]. The CPU cannot help with the 27B's
  own prefill or attention at useful speed.

**Q6. Other strategies that are not quantization and not numerically lossy:** see the table in (c). The main ones:
exact prefix caching made bitwise-safe; edit-at-the-tail layouts; not stripping old reasoning (or stripping only at
compaction time); KV/state snapshots to disk for resume; text offload + retrieval; token-efficient encodings.

**Q7. Early stop for decisions/choices/enums:**
Yes, exactly, under one definition: "the answer constrained greedy decoding over the allowed choices would produce".
If all choices start with different tokens, the argmax over those first tokens (from the prompt's last-position
logits) *is* that answer; the remaining tokens are forced. If choices share a first token, walk a token trie: one
extra decode step per shared level. In vLLM this is `structured_outputs: {"choice": [...]}` (older: `guided_choice`;
https://docs.vllm.ai/features/structured_outputs.html) or, for the one-step version, `max_tokens=1` with
`allowed_token_ids` restricted to the first tokens of the choices (present in vLLM's sampling parameters; our fork's
API exposure [unverified]). Caveats: (1) with thinking enabled the model would reason first; a first-token decision
equals the *non-thinking* constrained answer, not the thinking answer. (2) Tokenisation: " Yes" and "Yes" are
different tokens; derive first tokens from the exact chat-template text. (3) Ties: our lanes have known FP16 ties;
the tie-break must be the same as the sampler's. "Before the first token" (reading a probe on hidden states during
prefill) is a learned approximation, not equivalent to decoding.

**Recurrent layers (applies to every editing idea):** 48 of 64 layers carry a running Gated DeltaNet state, not
per-token entries. That state cannot "unsee" deleted text. The only exact way to apply an edit at position p is to
restart the recurrence from a saved state at or before p and recompute every token after p. vLLM stores hybrid states
only on a block grid (`--mamba-cache-mode align`: "a prefix-cache hit can resume only at a block boundary",
https://docs.vllm.ai/en/v0.30.0/features/automatic_prefix_caching/; our probe saw 576-token blocks), so an exact edit
costs re-reading from the last block boundary before p to the end. Cost is driven by how much text sits *after* the
edit, which is exactly what the paper's system prompt tells the model.

---

## (c) Strategy table

"Exact" = the arithmetic is bitwise what our reference path computes. "Informational" = arithmetic exact, but some
content is chosen away (allowed for this research, reported as a judgement).

| Strategy | Exact / lossless? | Cost | Possible gain here | How to test on this hardware |
|---|---|---|---|---|
| Open the exact window to 262K (TP2) | Exact | Prefill time grows with length (16 full-attn layers are quadratic); 64 KiB/token KV [shape unverified] | 8x today's window for one user | Already pre-registered: `2026-10-05-context-window-prereg.md` (longctx probe) |
| Exact prefix caching (block-aligned prefill so a cache hit equals a cold run bit for bit) | Exact only after proof; today cache-on can differ from cache-off on tie-sensitive prompts (2026-09-12 probe) | Engineering; GPU memory for cached blocks and state checkpoints | Turn cost drops from "whole prompt" to "new text"; makes every other idea affordable | E0 below |
| Edit-at-the-tail layouts (pinned head, append-only log, compaction rewrites only the tail / rewinds to a checkpoint and appends a summary) | Exact arithmetic; informational for the summary | Some extra tokens kept | Edits cost only the text after the edit point | E2 below |
| Keep old reasoning in the history (no template stripping), or strip only at compaction | Exact | More tokens per turn | Paper: template stripping caused 5.3 of 7.8 points of re-prefill that SCR recovered; an exact layout avoids the miss instead | E2 arm |
| KV + recurrent state snapshot to disk / host RAM between turns or sessions (LMCache `naive` serde, vLLM offloading connector, llama.cpp-style slot save) | Byte-exact restore; equals a cold run only if E0 holds. LMCache docs say for hybrids "Generation is not bit-exact between a cached and a fresh run" (https://docs.lmcache.ai/mp/hybrid_models.html) | ~2 GiB per 32K; 15 GiB host RAM; disk bandwidth; XPU support of these tools [unverified] | Resume a 32K session in ~1 s instead of ~16 s of re-prefill [estimate] | E5 below |
| Text offload + grep/retrieval (CLM file notes, ACM, RLM, MemGPT/Letta archival memory) | Retrieved text is exact; what gets retrieved is the model's choice | Tool turns | Unlimited store on disk | Part of E1 (KV Store / Log Triage style tasks) |
| Model self-editing (CLM harness) | Informational | Editing turns; re-prefill after each edit | Unlimited task length inside a fixed window | E1 below |
| Harness summary at 75% (Codex-style) | Informational, lossier than CLM per the paper | One summarisation call per compaction | Baseline | E1 arm |
| CPU lossless hygiene (dedupe, ANSI strip, repeated-line counts, JSON minify, show diffs) | Information-preserving (tokens change; originals kept on disk) | Negligible CPU | Workload-dependent, maybe 10-40% on logs [unverified] | E3 below |
| Token-efficient encodings of structured data (CSV/TSV instead of verbose JSON, short stable keys) | Information-preserving | Prompt design | Workload-dependent | E3 arm |
| Small CPU model/classifier deletes "wasteful" spans | Informational, lossy | CPU time; another model to validate | Possibly large, unproven | Optional E6 |
| One-step decision via constrained first token | Exact vs constrained greedy (distinct first tokens) | None | Skip all decode steps after the first for enum answers | E4 below |
| Hidden-state probe for the decision | **Not exact** (learned approximation) | Training a probe | Answer before any decode step | Not recommended under the rules |
| Suffix Cache Reuse (paper), CacheBlend (https://arxiv.org/abs/2405.16444), EPIC, PIE, Prompt Cache | **Not exact** (stale K/V for the new surrounding text; CacheBlend recomputes only selected tokens) | | 35% less server compute in the paper | Excluded by the owner's rules |
| Sliding window / attention sinks (StreamingLLM, https://arxiv.org/abs/2309.17453), KV eviction (H2O, SnapKV) | **Not exact** (tokens silently dropped from attention) | | | Excluded |
| KV quantization / CacheGen (https://arxiv.org/abs/2310.07240, quantizes KV) | **Lossy** | | | Excluded |
| LLMLingua / LongLLMLingua / LLMLingua-2 (https://arxiv.org/abs/2310.05736, https://arxiv.org/abs/2403.12968) | **Lossy** text compression (drops tokens by a small model's scoring) | | | Excluded, or at most an informational baseline clearly labelled lossy |
| Split cards: one-card worker + one-card pruner | Exact per card | Halves window (44K) and speed per card | Little, per Q3 | Not proposed |

---

## (d) Experiment proposals, in priority order

All runs: greedy decoding, our usual deterministic settings, no server left running, results in the lab's normal
notes/evidence layout. Each needs its own pre-registration note before GPU time.

### E0. Make exact prefix reuse bitwise-safe (prerequisite for E2, E5 and cheap editing)

- **What:** our 2026-09-12 probe showed cache-hit outputs can differ from cache-off on tie-sensitive prompts because
  the prefix resumes from a block-boundary state instead of one-pass prefill. Define the reference prefill as
  "chunks aligned to the cache block grid" (576 tokens here, or a multiple), so that a cold run and a cache-hit run do
  exactly the same chunk computations.
- **Measure:** token-for-token and logprob-for-logprob equality, cache-on vs aligned cache-off, on the existing
  `apc-mtp-probe.py` fixture plus long prompts (8K-120K), single and 8-way concurrent; prefill time saved.
- **Pass:** 100% bitwise identical output ids and logprobs on all cases including the known tie-sensitive prompts.
  **Fail:** any difference; then find which kernel depends on chunk history (attention split, GDN chunk boundary).

### E1. Self-editing at 32K vs a bigger exact window

- **What:** re-implement ContextBench from Appendix D (seeded generators, deterministic graders; four tasks, pressure
  levels 0.5x-24x) since it is not released. Optionally add a small real task set (local deep-research corpus or a few
  Harbor/Terminal-Bench tasks) if host RAM allows Docker beside the server. Arms on the same TP2 server:
  (A) no management, 262K window; (B) Codex-style summary at 75% of 32K; (C) CLM harness at 32K (`max_tokens 4096`,
  edit gate `shrink`); (D) CLM at 128K; (E) plain 32K, no management (lower bound).
- **Measure:** task accuracy per pressure level; wall-clock seconds and prefilled tokens per task; number of edits;
  peak context; for (A) whether the answer stays correct as context grows past what the model handles well.
- **Pass (CLM worth adopting):** (C) or (D) at least matches (A) within the confidence interval at pressures where
  (A) fits, beats (A) where (A) overflows, and costs less wall time than (A). **Fail:** (A) wins on both accuracy and
  time wherever it fits; then self-editing is only for tasks longer than 262K.
- **Caveat:** the paper sampled at temperature 0.7 with best-of-3 on some tasks; greedy single runs here will differ.

### E2. Edit-friendly layouts with exact prefix reuse (after E0 passes)

- **What:** same CLM tasks, three layouts: (1) paper default (model edits anywhere); (2) "tail-only": pinned head,
  compaction may only rewrite the last N turns or rewind to a checkpoint and append a summary; (3) "notes at the end":
  a running notes block that is always the last message, so rewriting it never invalidates earlier text. Arms with and
  without old-reasoning stripping.
- **Measure:** prefix-hit fraction, re-prefilled tokens per turn, wall time, accuracy; check outputs equal the
  cache-off aligned reference for a sample of turns.
- **Pass:** >= 50% fewer re-prefilled tokens than layout (1) at equal accuracy (within CI), and bitwise equality with
  the reference on every sampled turn.

### E3. CPU-side lossless hygiene

- **What:** collect real transcripts from our own agent/tool sessions (no GPU needed to measure). Apply each rule
  separately: exact-duplicate replacement, ANSI/progress-bar strip, repeated-line counting, JSON minify, show-diff on
  re-read files, CSV instead of JSON for tables. Every rule must be reversible or keep the original on disk.
- **Measure:** tokens saved per rule with the real Qwen tokenizer; CPU ms per 32K tokens; then a small GPU A/B on
  E1 tasks with and without hygiene.
- **Pass:** >= 15% token reduction on real transcripts, < 50 ms per 32K tokens on one core, no accuracy loss on E1.
  Report 32K -> X effective honestly; do not claim 100K unless measured.

### E4. One-step decisions

- **What:** a few hundred decision prompts (yes/no, A-D, small enums) with thinking off. Arm 1: full constrained
  generation (`structured_outputs.choice`). Arm 2: one step, `max_tokens=1` with `allowed_token_ids` = first tokens of
  the choices (trie walk if they share a first token). Arm 3 (informational only): thinking on, free generation,
  parsed answer.
- **Measure:** agreement Arm 1 vs Arm 2; latency; agreement Arm 2 vs Arm 3 (how often skipping reasoning changes the
  answer).
- **Pass:** Arm 1 == Arm 2 on 100% of prompts, including tie-sensitive ones. Any mismatch is a bug (tokenisation or
  tie-break). Arm 3 disagreement is reported, not a fail.

### E5. KV + recurrent state snapshot and restore (after E0)

- **What:** save a 32K session's KV and GDN state to host RAM and to disk (LMCache `naive` serde or vLLM's offloading
  connector if they run on XPU; otherwise a minimal save/restore in our fork), restore, continue.
- **Measure:** restore time vs re-prefill time; bitwise equality of the continuation with an uninterrupted run; host
  RAM peak (stay well below the 15 GiB that already caused oomd kills).
- **Pass:** bitwise-equal continuation and restore at least 5x faster than re-prefill.

### E6 (optional, lowest). Small CPU pruner

Only if E3 leaves a gap. A small model on CPU labels spans keep/drop; compare E1 accuracy with and without it; report
as an informational lossy method.

---

## (e) Risks

- **Prompt-injection persistence.** Text from tool outputs or web pages can be copied by the model into its own notes
  and then survives every compaction. OpenAI reported a model writing jailbreak-like instructions into its own
  compaction summaries (27 summaries; one made it give a 23-word refusal on a medical task); the cause correlated with
  failure to end summaries and a termination bug was fixed
  (https://alignment.openai.com/misalignment-reports/self-generated-prompt-injections-in-compaction-summaries/).
  Mitigations: keep system prompt and task pinned (the harness already does); log every edit as a diff; keep tool
  output in a region the model may delete but not rewrite into "instructions"; run a check that flags imperative
  instructions appearing in notes.
- **Error accumulation.** Each compaction can drop or distort a fact; later compactions build on the distorted
  version. The paper's ContextBench shows summary methods losing or hallucinating needles and Sudoku cells. Keep raw
  originals on disk so a fact can be re-checked, and grade exact recall, not fluency.
- **Evaluation pitfalls.** Prefix-reuse FLOPs are a theoretical count, not time on our cards; measure wall time. Paper
  results use temperature 0.7, best-of-3 on EdgeBench, LLM judges, and budgets that differ between paper and config;
  do not compare our greedy numbers to theirs directly. ContextBench grades only what is in the context, so
  offloading to files without bringing the answer back scores zero by design. Small sample sizes (64 questions for the
  K sweep) cannot show the absence of an effect.
- **Exactness pitfalls specific to us.** Prefix caching is not yet bitwise-safe here (E0). Old-reasoning stripping in
  the chat template silently changes the prompt mid-way. Any stale-cache trick (SCR, CacheBlend) breaks the rule even
  when accuracy "matches".
- **Host limits.** 15 GiB RAM: Docker task containers, LMCache host buffers and the server compete; past incidents
  (oomd killed the user session on 2026-09-17) argue for disk, not RAM, as the snapshot tier.
- **Licence.** CLM code is CC BY-NC 4.0.

## Sources (all read 2026-10-05)

- Paper: https://arxiv.org/abs/2609.37725, https://arxiv.org/html/2609.37725v1, https://arxiv.org/pdf/2609.37725
- Article: https://mer.vin/news/context-language-models-let-the-model-edit-its-own-context-as-a-file/
- Code: https://github.com/facebookresearch/context-language-models (README, `clm/clm_harness/README.md`,
  `clm_agent/prompts.yaml`, `context_env/edit_gate.py`, `configs/bcp.yaml`, `clm/clm_icl/README.md`,
  `clm/clm_rl/README.md`, `suffix_cache_reuse/README.md`, `suffix_cache_reuse/overlay.py` header and SSM section,
  `LICENSE`, `NOTICE`, open issues)
- RLM: https://arxiv.org/abs/2512.24601. MemGPT: https://arxiv.org/abs/2310.08560 (Letta is its successor project,
  https://docs.letta.com [not re-read today]). Memento: https://arxiv.org/abs/2604.09852.
- vLLM: structured outputs https://docs.vllm.ai/features/structured_outputs.html; prefix caching for hybrids
  https://docs.vllm.ai/en/v0.30.0/features/automatic_prefix_caching/ (v0.30 docs; our fork is based on v0.29, so flags
  such as `--enable-mamba-fine-grained-prefix-cache` may not exist in it [unverified]); KV offloading flags
  (`--kv-offloading-size`, `--kv-offloading-backend native|lmcache`) via
  https://docs.nvidia.com/dynamo/dev/backends/v-llm/native-kv-offloading.md [secondary source].
- LMCache: https://docs.lmcache.ai/api_reference/configurations.html (`remote_serde` `naive` default, `cachegen`
  optional), https://docs.lmcache.ai/mp/hybrid_models.html (hybrid support, not bit-exact).
- llama.cpp slot save/restore (`--slot-save-path`, `POST /slots/{id}?action=save|restore`):
  https://github.com/ggml-org/llama.cpp/tree/master/tools/server [read via secondary summaries, not the README itself].
- CacheGen https://arxiv.org/abs/2310.07240 (abstract only); CacheBlend https://arxiv.org/abs/2405.16444, StreamingLLM
  https://arxiv.org/abs/2309.17453, LLMLingua https://arxiv.org/abs/2310.05736, LLMLingua-2
  https://arxiv.org/abs/2403.12968: cited from known IDs, not re-read today [unverified details].
- Lab notes used: `2026-10-05-context-window-prereg.md`, `2026-09-12-rebase-onto-vllm-v0290.md` (prefix-caching probe),
  prefill speed tables in the 2026-09 notes.

# Unlimited context: what else is out there, and what to test next (survey, 2026-10-05)

Research only: web reading plus our own notes. No GPU, no server, nothing committed. Builds on
`2026-10-05-context-research-results.md` (today's measurements), `2026-10-05-context-research-review.md`
(the "Context Language Models" paper, arXiv 2609.37725) and `2026-10-05-context-followup-ideas.md`.

## The short version (plain words)

1. Nearly every serious long-running agent today does the same three things: keep the raw record somewhere safe
   (files, a database), keep a small working page in view, and look things up again instead of trusting memory.
   Our "files plus search" winner is that pattern; it is not a fluke of our test.
2. Plain summarising loses detail a little at a time, and the losses pile up ("context collapse"). The better
   designs never throw the original away: a summary carries pointers back to the exact text, and the model can
   open the pointer when a detail matters. That is the most likely way to beat summarising on memory.
3. Our worst errors today are not reading errors, they are bookkeeping: arithmetic slips, a counter dropped from
   the table, a command run twice. The fix the literature points to: the model only *reports what it read*
   (with a quote), and plain code does the sums and keeps the books, so a slip can be caught and replayed.
4. That split also makes it fast: reading separate pieces does not need to be done one after another. Our
   server already gives identical answers with many users at once (630 tok/s at 64 users), so the reading can
   run in parallel and the total time can drop several-fold.
5. Long runs go wrong in known ways: the agent repeats itself, forgets a rule given early, gets confused by its
   own earlier mistakes, or wanders off-task. The cheap guards are: restate the goal and rules at the end of
   every prompt, let code check the rules, and remove failed attempts from view once they are resolved.
6. Splitting a big job into side-jobs that each start with a clean page and hand back only a short result
   ("branch and return") beats summarising in two recent papers; we can try it without any training.
7. Saving the model's working memory (the cache) to the fast drive and loading it back is exact if done
   carefully, and would let one card switch between long jobs in seconds; it is engine work, so it comes later.
8. Many famous ideas are off-limits or useless here: trained memory models (we cannot train a 27B), cache
   tricks that reuse stale numbers (not exact), and chat-memory products built for remembering user
   preferences.
9. Top experiments, in order: checked reading with code-kept books (about 4 GPU hours), summaries with pointers
   versus plain summaries on a test that asks about old details (about 5 hours), focus guards on a long run
   with rule changes (about 4 hours), parallel side-jobs (about 3 hours), exact save-and-restore (about 2 hours
   after the engine work).
10. Most likely to beat summarising on retention: summaries-with-pointers (lossless by reference), the
    quoted-event log replayed by code, and keeping notes as separate itemised entries edited one at a time
    rather than rewriting one big summary.

---

## How to read the assessments

- **Exact** means our arithmetic is untouched (no change to weights, cache precision or kernels). Every
  harness-level idea below is exact in that sense. What can still be lost is *information* (text the model or a
  rule chooses to drop). So each entry says where information can be lost.
- **Cost of a first test** is server time on the two-card TP2 server, assuming the existing CLM-derived harness
  (`scripts/context/clm_improved.py`), the stream generators (`make_sparse_prose_tasks.py`,
  `make_kvstream_tasks.py`, `make_ledger_tasks.py`) and the replay checker (`replay_state_check.py`).
- **Work needed:** harness-only / engine overlay / kernel work / training.
- "Paper numbers" are author-reported, usually on other models, often with LLM judges or sampling. None has been
  reproduced here.

---

## A. Compaction that keeps more than a summary does

### A1. Summaries with pointers to the untouched original ("lossless by reference", LCM)

- **What:** Every message, tool output and thought is kept verbatim in a database; older spans are replaced in
  the live context by summaries that carry IDs, and summaries are themselves rolled up into a tree (a DAG).
  The model has `grep` and `expand(id)` tools to reopen any span exactly.
- **Evidence:** "LCM: Lossless Context Management" (Ehrlich and Blackman, arXiv 2605.04050; listed as
  14 Feb 2026 on the aggregator, the ID suggests May 2026) — https://www.emergentmind.com/papers/2605.04050 .
  Their coding agent "Volt" (https://github.com/evahteev/volt, plugins: https://github.com/stephenschoettler/hermes-lcm)
  scored 74.8 vs 70.3 for Claude Code on OOLONG trec_coarse with Opus 4.6, ahead at every length from 32K to 1M
  (contaminated items excluded). OOLONG itself: https://arxiv.org/abs/2511.02817 (aggregation over every chunk;
  all models degrade with length). ReadAgent (ICML 2024, https://arxiv.org/abs/2402.09727) is the earlier form:
  "gist" summaries per page plus a "look up the page" action, 3.5-20x effective context on QuALITY,
  NarrativeQA, QMSum. Sculptor (https://arxiv.org/abs/2508.04664, ICLR 2026) gives the model
  fragment/fold/restore/search tools, untrained, and reports gains on interference-heavy tasks.
- **Exact?** Arithmetic exact. Information is never deleted, only moved out of view; the residual loss is the
  model not *thinking* to expand a pointer. That is a measurable miss rate, unlike a summary's silent loss.
- **On our stack:** harness-only. SQLite (stdlib) with FTS5 gives BM25 search on CPU for free; no embedding model
  needed (host has ~1 GiB spare RAM while a server runs). Summaries appended at the tail keep the exact prefix
  cache warm.
- **First test:** ~5 GPU hours (see experiment 2). **Verdict: try now.** It is the most direct answer to "better
  than summarising blindly".

### A2. Itemised notes edited one entry at a time, never rewritten whole (ACE "playbook")

- **What:** Memory is a list of numbered bullet entries; each step proposes small *delta* edits (add, update,
  delete entry N) that code applies, instead of the model rewriting one summary. Avoids "brevity bias" and
  "context collapse", where each rewrite quietly shortens and erodes detail.
- **Evidence:** Agentic Context Engineering, arXiv 2510.04618 (Oct 2025, ICLR 2026),
  https://arxiv.org/abs/2510.04618 : +10.6 points on AppWorld agents, +8.6 on finance tasks, with a documented
  collapse case (AppWorld, Figure 2) where one monolithic rewrite shrank an 18,282-token context to 122 tokens
  and accuracy fell from 66.7 % to 57.1 %, below the 63.7 % no-adaptation baseline. Memory-R1 (https://arxiv.org/abs/2508.19828) and Mem0 (https://arxiv.org/abs/2504.19413)
  use the same ADD/UPDATE/DELETE/NOOP shape.
- **Exact?** Arithmetic exact; information loss only where the model chooses to delete an entry, and each delete
  is a logged, reversible diff.
- **On our stack:** harness-only; our `clm_improved.py` pinned state block is already close (a table). The change
  is to make all state edits go through an edit tool with entry IDs and a log, and forbid whole-block rewrites.
- **First test:** folded into experiment 2 as an arm (~1 extra hour). **Verdict: try now (as an arm).**

### A3. Observation masking (drop old tool outputs, keep the actions)

- **What:** Replace old tool outputs with a placeholder such as "[output omitted, N lines, file X]" and keep the
  model's own actions and reasoning. No LLM call for compaction.
- **Evidence:** "The Complexity Trap" (JetBrains/TUM, arXiv 2508.21433, NeurIPS 2025 DL4C workshop)
  https://arxiv.org/abs/2508.21433 : on SWE-bench Verified with SWE-agent across five model configurations,
  masking halved cost versus the raw agent and matched or slightly beat LLM summarisation; a hybrid was 7-11 %
  cheaper again. SWE-agent's default history processor already does this for all but the last five
  observations (https://arxiv.org/abs/2410.03859 describes the setting). Anthropic calls tool-result clearing
  "one of the safest, lightest-touch forms of compaction"
  (https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents , 29 Sep 2025).
- **Exact?** Arithmetic exact; information kept on disk if we archive the output (then it is A1-lite).
- **On our stack:** harness-only; one CPU rule. Note: our hygiene census found "large tool outputs to disk with a
  pointer" frees 7.5 % on our sessions; on read-heavy streams the gain is far larger because the stream text
  *is* the tool output.
- **Verdict: try now, as the cheap baseline that replaces "summarise at 75 %"** in every future comparison. It is
  the bar a fancy method must beat.

### A4. Recursive / hierarchical summarisation, with or without verification

- **What:** Summarise chunks, then summarise the summaries (MemWalker, RAPTOR, Codex's handoff summary, OpenHands
  `LLMSummarizingCondenser`); "verified" variants check the summary against the source.
- **Evidence:** OpenHands condenser blog (up to 2x per-turn cost cut at equal SWE-bench score)
  https://openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents ; ReSum
  (Tongyi, arXiv 2509.13313) https://arxiv.org/abs/2509.13313 : +4.5 points over ReAct untrained, +8.2 with
  RL and a trained 30B summary model; InftyThink (arXiv 2503.06692) applies the same to long reasoning, with
  training. Codex CLI compaction (local path is a plain LLM handoff summary; OpenAI-hosted path is an
  encrypted server-side blob): https://codex.danielvaughan.com/2026/03/31/codex-cli-context-compaction-architecture/
  (secondary source). Against it: ACE's collapse result (A2), our own run (summarise 41 min vs 26 for keep-all,
  because each summary breaks the cache), and Context-Folding/AgentFold both beating summary baselines.
- **Exact?** Informational loss at every level, compounding.
- **Verdict: skip as a new direction;** keep only as the comparison arm. A verification pass is better spent on
  structured state (B1) than on prose summaries.

### A5. Trained folding / constant-memory agents (MEM1, MemAgent, AgentFold, FoldGRPO, ReSum-GRPO)

- **What:** Models trained (RL or SFT) to overwrite a fixed-size memory each step, or to fold sub-trajectories.
- **Evidence:** MEM1 (https://arxiv.org/abs/2506.15841, ICLR 2026): 3.5x better and 3.7x less memory than
  Qwen2.5-14B on a 16-objective QA. MemAgent (https://arxiv.org/abs/2507.02259, ICLR 2026 oral): trained at 8K
  memory/32K text, <10 % loss up to 3.5M-token QA. AgentFold (https://arxiv.org/abs/2510.24699): SFT'd
  30B-A3B, 36.2 % BrowseComp, context ~7K after 100 turns. Context-Folding / FoldGRPO
  (https://arxiv.org/abs/2510.11967): branch/return with RL, 10x smaller active context, beats summary baselines.
- **Exact?** Arithmetic of *our* model is exact if we only borrow the prompts; the trained behaviour is not
  available to us.
- **On our stack:** training a 27B is impossible here. The *prompt protocols* transfer (MemAgent's "read a chunk,
  overwrite the memory" is exactly our read-mode agent; AgentFold's two fold modes and Context-Folding's
  branch/return are prompt-level).
- **Verdict: skip the training; borrow branch/return (C1) and the two-granularity fold** (fold one step finely
  vs consolidate a finished sub-task coarsely) as prompt rules.

### A6. Chat-memory systems (Mem0, A-MEM, MemoryBank, HippoRAG 2, Letta archival)

- **What:** Extract facts from a conversation into a store (vector, graph or linked notes), retrieve a few per
  query. HippoRAG 2 adds a knowledge graph with personalised PageRank.
- **Evidence:** Mem0 (https://arxiv.org/abs/2504.19413): LoCoMo LLM-judge 26 % relative over OpenAI memory,
  ~90 % fewer tokens than full context. A-MEM (https://arxiv.org/abs/2502.12110, NeurIPS 2025): Zettelkasten-style
  linked notes, gains on multi-hop LoCoMo. HippoRAG 2 (https://arxiv.org/abs/2502.14802, ICML 2025): +7 points
  on associative memory over a strong embedding retriever. Counterpoint: Letta's own test put plain files with
  grep on LoCoMo at 74.0 % with gpt-4o-mini versus 68.5 % reported for Mem0
  (https://www.letta.com/blog/benchmarking-ai-agent-memory). LongMemEval (https://arxiv.org/abs/2410.10813):
  30 %+ drops for long-context models on knowledge updates and temporal questions; its fixes (fact-augmented
  keys, time-aware query expansion) are retrieval-index tricks.
- **Exact?** Extraction is lossy by design (the store keeps what the extractor thought mattered); originals are
  usually dropped.
- **On our stack:** harness plus extra LLM calls per write; graph building costs many calls. Embedding models
  compete with the server for host RAM.
- **Verdict: skip for now.** Built for remembering a user across chats, scored with LLM judges; the files result
  says the plain tool is as good. Revisit HippoRAG-style linking only if a task needs multi-hop recall over a
  large archive that BM25 misses.

### A7. Tiered memory with a background consolidator (MemGPT/Letta core/recall/archival, "sleep-time compute")

- **What:** A small always-visible "core" block the agent edits, a searchable log of the conversation, an
  archival store; a second agent consolidates memory while the main one is idle.
- **Evidence:** MemGPT https://arxiv.org/abs/2310.08560 ; Letta docs https://docs.letta.com/concepts/memory-management ;
  sleep-time compute https://arxiv.org/abs/2504.13171 (moves consolidation off the critical path; reported
  test-time compute savings on reasoning benchmarks) [details not re-read today].
- **Exact?** As A1 if the recall log is verbatim.
- **On our stack:** harness-only. Our pinned state = core, the archive = recall. The new piece is *background*
  consolidation: with the multi-user lossless server, a consolidator request can run concurrently with the main
  agent at little latency cost.
- **Verdict: try later,** after A1; it is A1 plus a scheduler.

---

## B. Getting the bookkeeping right (state you can verify)

### B1. Quoted event log + code-kept state, replayable ("event sourcing")

- **What:** The model never edits the table. For each piece of text it emits typed events (counter, operation,
  amount, *verbatim quote*, source position) under a JSON schema; code validates each quote is really in the
  source, applies the events, keeps a hash of the state, and can replay everything from the log.
- **Evidence:** ESAA, event sourcing for LLM agents (arXiv 2602.23193) https://arxiv.org/abs/2602.23193 : agents
  emit only validated JSON intentions; an orchestrator appends to a log and verifies by replay with hashing
  (case-study evidence, no large benchmark). Provenance survey https://arxiv.org/abs/2606.04990 . Our own data
  is the strongest evidence: of the four wrong answers in the 120K read-mode run, one was a misread and three
  were the agent loop (an arithmetic slip 369-65=309, a command re-run after its batch was gone, a script that
  misread "removed"). Code-applied events make all three impossible; a quote check makes "invented update"
  detectable.
- **Exact?** Arithmetic exact; information exact by reference (each state change points to its quote). The only
  residual error is a wrong or missed extraction from the text, i.e. pure reading error.
- **On our stack:** harness-only. vLLM structured outputs (`{"structured_outputs": {"json": schema}}`,
  https://docs.vllm.ai/en/latest/features/structured_outputs/) remove format slips (the three 3-per-batch
  calibration errors coincided with off-format replies). Constrained decoding is not a numeric change, but it can
  change the token chosen when the free answer would break the schema; label it. XPU support for the
  xgrammar bitmask path is **unverified**; we already use `allowed_token_ids` successfully, and a regex or
  JSON grammar needs a one-request smoke check.
- **Verdict: try now (top pick).**

### B2. Redundant reading with disagreement-triggered re-reads (verification without sampling)

- **What:** Read each piece twice in different ways (e.g. plain prompt and a "list every sentence that changes a
  number" prompt, or the batch split at a different boundary); where the two event lists disagree, re-read that
  passage with thinking on. Greedy decoding makes each reader deterministic, so diversity must come from the
  prompt, not from sampling.
- **Evidence:** Self-consistency and verifier-style checks are standard (https://arxiv.org/abs/2203.11171); "The
  Illusion of Diminishing Returns" (https://arxiv.org/abs/2509.09677, ICLR 2026) shows small per-step accuracy
  gains compound into much longer error-free runs and that thinking fixes per-step execution errors. Our
  calibration: per-change error 1.7 % (3 changes per batch) to 5.7 % (12 per batch) without thinking; thinking on
  dense batches ran into the output cap, so thinking must be targeted at small disagreements, not whole batches.
- **Exact?** Arithmetic exact; reduces the information loss of reading.
- **On our stack:** harness-only; doubles read calls, but they are short, thinking-off and parallel (B3).
- **Verdict: try now, as an arm of experiment 1.**

### B3. Parallel map, deterministic reduce (reading in parallel)

- **What:** When each piece can be read without knowing the running state (event extraction can be), send many
  pieces at once and fold the results in code. LCM calls this operator-level recursion (`llm_map`); RLM
  (https://arxiv.org/abs/2512.24601) and Chain-of-Agents are related.
- **Evidence:** LCM (A1). Our measured multi-user server: lossless through 64 concurrent users, about 630 tok/s
  aggregate against ~90 for one user (memory note `qwen38-fp8-multiuser-lossless-three-overlays`); the
  batch-invariant overlays mean a piece read in a batch of 16 gives the same tokens as read alone (this must be
  re-checked on the exact server configuration used, with the prefix cache on).
- **Exact?** Exact, provided the batch-invariance holds for that build; otherwise answers can differ by batch
  composition (still not "lossy", but not reproducible run to run). Make the reproducibility check part of the
  gate.
- **On our stack:** harness-only plus a launch with `--max-num-seqs` > 1 and the multi-user overlays (the
  context lane so far ran `--max-num-seqs 1`).
- **Speed estimate:** a 480K narrative stream is 240 short thinking-off reads; at ~16-way concurrency the wall
  time should fall from 26 min toward a few minutes. Estimate, to be measured.
- **Verdict: try now (inside experiment 1).** This is the biggest speed lever found in this survey.

### B4. Typed state checks and invariants (checksums, counts, "handled lines" checks)

- **What:** Code checks invariants on every state change: the number of events equals the number of quoted
  sentences; a deleted key cannot be updated without a re-add; the answer file contains exactly the asked keys;
  a state hash is shown to the model so it can see whether its edit landed.
- **Evidence:** Our own guards (repeat refusal, "no state change without a batch in view", the fold self-test)
  each fixed a real failure today. MAST (https://arxiv.org/abs/2503.13657): "no or incomplete verification" and
  "step repetition" are among the most common multi-agent failure modes, and the authors find most failures are
  system design, not model limits.
- **Verdict: keep doing; it is part of B1.**

---

## C. Staying on task over hours

### C1. Branch and return (side-jobs with a clean page)

- **What:** The main thread opens a branch for a sub-task; the branch works with its own context (shared pinned
  prefix, so the cache still hits) and returns a short result plus an archive pointer; the branch's working
  text is folded away.
- **Evidence:** Context-Folding (https://arxiv.org/abs/2510.11967, Oct 2025): matches or beats ReAct with a 10x
  smaller active context and beats summary-based management on deep research and SWE tasks (trained with
  FoldGRPO; zero-shot not separately reported) [abstract-level]. Anthropic's sub-agent pattern returns
  1-2K-token summaries from tens of thousands of tokens of work (link in A3). Git Context Controller
  (https://arxiv.org/abs/2508.00031): COMMIT/BRANCH/MERGE/CONTEXT on a file-system memory, reported >80 % on
  SWE-bench Verified with a frontier model.
- **Exact?** Arithmetic exact; branch details are archived (A1), so nothing is lost by design.
- **On our stack:** harness-only; branches can run concurrently on the multi-user server (B3).
- **Verdict: try now (experiment 4)** on a multi-part task; a stream task does not exercise it.

### C2. Goal and rule recitation at the end of every prompt

- **What:** The harness re-renders a short "task card" (goal, rules, what is done, what is next) as the last
  thing before the model writes, every call; the model updates a todo list.
- **Evidence:** Manus (https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus): a
  `todo.md` rewritten each step "recites" the goal into recent attention over ~50-call tasks; also: keep the
  prefix stable for cache hits (the input-to-output token ratio of their agent is ~100:1). Goal drift
  (https://arxiv.org/abs/2505.02709, AIES 2025): every model drifts eventually; drift correlates with pattern
  matching on the growing context; the best scaffolded agent held for >100K tokens. "LLMs Get Lost in Multi-Turn
  Conversation" (https://arxiv.org/abs/2505.06120): 39 % average drop when instructions arrive in pieces; giving
  everything again at once (CONCAT) recovers ~95 %; recap helps partly. Anthropic's long-running harness
  (https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents): a feature list with
  pass flags, a progress file and git commits re-read at the start of each session.
- **Exact?** Exact; costs a few hundred tokens per call but sits after the cached prefix, so it is re-read, not
  re-prefilled from the start.
- **On our stack:** harness-only; `clm_improved.py` already shows the state block last. Add the rules and the
  current instruction set to it.
- **Verdict: try now (experiment 3).**

### C3. Remove resolved mistakes from view (self-conditioning) — or keep them (Manus)?

- **What:** Once a failed command has been fixed, collapse the failure to one line ("attempt 3 failed: X; fixed
  by Y") so the model is not primed by its own errors.
- **Evidence:** For: "The Illusion of Diminishing Returns" shows models make more mistakes when their own earlier
  mistakes are in context ("self-conditioning"), not fixed by scale; thinking reduces it. Vending-Bench
  (https://arxiv.org/abs/2502.15840): runs derail when one misread status (an order "arrived" early) spirals
  into loops that rarely recover. Against: Manus keeps failed actions in context so the model does not repeat
  them. Our own 150-repeat loop on the 478K ledger fits the self-conditioning picture.
- **Exact?** Exact if the full failure goes to the archive.
- **Verdict: try now, as an arm of experiment 3;** the two published views disagree, so it needs a measurement.

### C4. Show the window and refuse what will not fit (budget awareness)

- Already found and fixed today (the corrected guard reserves the largest turn plus a margin). Codex and Claude
  Code both expose context usage to the agent (secondary source:
  https://codex.danielvaughan.com/2026/05/14/codex-cli-context-health-monitoring-compaction-telemetry-long-session-quality/).
  **Verdict: keep; not a new experiment.**

### C5. Long-run failure checklist (what to log in every long run)

From Vending-Bench, MAST, goal-drift and our runs: (1) repeated identical actions, (2) state claimed without
evidence (e.g. "order arrived"), (3) rules from early instructions violated late, (4) writing answers before the
question exists, (5) output-cap hits while thinking, (6) context near the window edge. Each has a cheap detector
in the harness log; experiment 3 reports all six per run. Chroma's "Context Rot" report
(https://research.trychroma.com/context-rot, July 2025, 18 models incl. Qwen3) is the general evidence that
reliability falls with input length even on trivial tasks; it agrees with our needle result (exact to ~60K,
look-alike confusions beyond).

---

## D. Speed

### D1. Parallel reading (B3) — the largest lever; try now.

### D2. Thinking only where it changes the answer

- Already measured: thinking off on routine steps, on for errors and the final answer, gave 24/24 four times
  faster. The new piece from B2 is *targeted* thinking: think only on passages where two cheap readings
  disagree. **Verdict: inside experiment 1.**

### D3. Speculative actions (predict the next tool call and run it early)

- **What:** A fast predictor guesses the agent's next action; it is executed in parallel and committed only if
  the real next action matches. Lossless by construction.
- **Evidence:** https://arxiv.org/abs/2510.04371 (ICLR 2026 oral): up to 55 % next-action accuracy, up to 20 %
  latency cut in games, shopping and search.
- **On our stack:** our tool calls take seconds in total (all file commands of a run under 3 s); time is in
  decoding. The only useful form would be pre-reading the next batch into the cache while the model writes,
  which the exact prefix cache cannot do for a prompt whose earlier part is still being generated.
- **Verdict: skip.** Nothing to hide here.

### D4. Exact park-and-restore of the cache on the NVMe drive

- **What:** Save a long session's attention cache plus recurrent-layer states to disk and load it back instead of
  re-reading the text; lets one card hold several long jobs and swap between them.
- **Evidence:** LMCache Qwen3.5 recipe (https://docs.lmcache.ai/recipes/qwen3_5.html): needs
  `--mamba-cache-mode align` and says "Generation is **not bit-exact** between a cached and a fresh run: GDN
  backends do not support vLLM's batch-invariant mode"; no XPU mention. TensorRT-LLM's KV connector example
  asserts identical outputs after restore
  (https://nvidia.github.io/TensorRT-LLM/latest/features/kv-cache-connector.html). A Sept 2026 case study of
  LMCache shared between two 27B vLLM replicas found a real correctness bug (a missing stream dependency in a
  raw-pointer path) that byte tests only caught under injected delays: https://arxiv.org/abs/2609.15021 . Our
  exact prefix cache already keeps reading-only states at fixed 832-token pieces, which is exactly what a
  byte-exact save needs.
- **Exact?** A byte copy of states our exact cache produced is exact; any tool that re-chunks, compresses
  (CacheGen) or stitches states from different prefixes (LinearKV, https://arxiv.org/abs/2608.11231 , explicitly
  approximate) is not.
- **Cost:** engine overlay (save/load of kept states); ~64 KiB per token, so 200K is ~12 GiB, 1 s at 12.7 GB/s
  read, against 152 s cold read. Host RAM (15 GiB) means stream straight from disk to device, no host staging
  of the whole thing.
- **Verdict: try later** (experiment 5); it speeds up resuming and switching, not a single run.

### D5. Position-independent / stale cache reuse (CacheBlend, Suffix Cache Reuse, LinearKV, EPIC)

- **Verdict: skip.** Not exact (already rejected in the review; LinearKV is new and also approximate).

---

## E. Ideas that fail the rules or do not fit

| Idea | Why not |
| --- | --- |
| KV quantization, CacheGen, KV eviction (H2O, SnapKV), sliding window / attention sinks | numeric loss or silent token drops; owner's rule |
| LLMLingua-style token dropping | lossy text compression by a small model's scores |
| Trained memory agents (MEM1, MemAgent, AgentFold, ReSum-GRPO, Memory-R1) | need RL/SFT on a 27B; borrow prompts only |
| Small CPU pruner model | measured: under 2 % to win losslessly on our sessions |
| One card works, the other prunes | rejected today: halves window and speed for little gain |
| Encrypted server-side compaction (OpenAI) | not available for local models; its value is tamper-resistance, which our harness gets by logging every edit |

---

## Ranked top five experiments

All on the two-card TP2 server with the exact prefix cache, greedy, drafting on, one preregistered unattended
runner per experiment, server stopped at the end, no resident server. "Right of N" graded against the hidden
reference; per-change error from `replay_state_check.py`. Two seeds minimum; one seed is a look, not a result.

### 1. Quoted events, code-kept books, parallel and cross-checked reading (~4 GPU hours)

**Task:** sparse-prose stream (`make_sparse_prose_tasks.py`) at 120K with 3, 6 and 12 real changes per 2K
batch (numbers as words plus pronouns and corrections, i.e. the "all together" setting where error was highest),
and the 480K stream at 3 per batch; 2 seeds each. **Arms:** (A) the current guarded read-mode agent (baseline:
23/24 and 24/24 at 3 per batch); (B) event extraction: each batch read once, thinking off, JSON-schema output
`{counter, op, amount, quote}`, quotes checked against the batch text, events applied by code, 16 requests in
flight; (C) B plus a second reading with a different prompt and different batch boundaries, disagreements
re-read with thinking on (cap 4K tokens). Server with the multi-user lossless overlays; first gate: 20 batches
read alone and in a batch of 16 must give identical event lists. **Pass:** (C) is right on at least as many
final values as (A) on every seed and density, its per-change error at 12 per batch is at most 1 % (A's
reading error there is ~5.7 %), every state change traces to a quote that exists in the source, and its wall
time is at most half of (A)'s. (B) alone is reported as the speed point. **Fail:** (C) loses any final value
that (A) gets, or the batch-invariance gate fails (then run B/C at one request in flight and report speed
separately).

### 2. Summaries with pointers vs plain summaries vs masking, on a test that asks about old details (~5 GPU hours)

**Task:** a new generator (CPU, no GPU) built on the sparse-prose stream: besides the 24 final counter values it
asks 24 *historical* questions whose answers sit only in old raw text and are not part of any running state
("what reason did the clerk give in the week the east granary was emptied?", "what was counter K before its
second correction?"), at 240K and 480K tokens, 32K budget, files forbidden except the harness archive. **Arms:**
(A) summarise at 75 % (Codex-style handoff); (B) observation masking with the raw text archived but no search
tool (the cheap baseline); (C) itemised delta notes (ACE-style, edits by entry ID, no whole rewrites);
(D) summaries with pointers: archive in SQLite with FTS5, summaries at the tail cite span IDs, tools
`search(query)` and `expand(id)`, summary roll-up when the summary block passes 4K. **Pass:** (D) beats (A) on
historical questions by at least 6 of 48 (two seeds pooled) with no loss on the 48 final values, and each wrong
historical answer is classified (never searched / searched but missed / found but misread). (C) is reported
against (A) as the "no rewrite" effect. **Fail:** (D) within 3 of (A); then retention is limited by deciding to
look, not by storage, and the next step is a harness rule that forces a search before any historical answer.

### 3. Focus guards on a long run with changing rules (~4 GPU hours)

**Task:** the 480K stream with three rule changes delivered inside the stream (e.g. "from now on ignore any
counter whose name starts with Q", "amounts from the north office are in dozens", "report deleted counters as
REMOVED"), five planted fake instructions inside the narrative (injection-style text that must not be obeyed),
and tool errors injected on 5 % of fetches. **Arms:** (A) current guarded read-mode agent; (B) A plus a task card
re-rendered last every call (goal, active rules with the batch they arrived in, progress); (C) B plus a
code-checked rule list (the harness validates answers and state edits against the active rules and returns
violations); (D) C plus collapsing resolved errors to one line (full text to the archive). **Pass:** report the
six failure counters of C5 per run; (C) or (D) has zero rule violations in the final answers and zero obeyed
planted instructions on both seeds, and at least 22 of 24 right; (D) versus (C) decides the self-conditioning
question (pre-stated: a difference of 2 or more right answers or a halving of repeated actions counts).
**Fail:** violations persist under (C); then the rules must move fully into code (the model proposes, code
disposes).

### 4. Branch and return with parallel side-jobs (~3 GPU hours)

**Task:** a multi-part job that does not fold into one table: eight independent sub-questions, each needing a
search through its own 60K-token document set (generated, hidden references), then one final question that
combines the eight answers; total input ~500K. **Arms:** (A) single thread with summaries with pointers (the
experiment 2 winner); (B) branch/return run one branch at a time (each branch starts from the pinned prefix,
returns at most 300 tokens plus an archive ID); (C) as B with all eight branches in flight at once. **Pass:**
(B) at least as accurate as (A) on the eight parts and the final combination (two seeds), main-thread peak
context at most a third of (A)'s, and (C) at least 3x faster than (B) wall-clock with identical branch outputs
to (B). **Fail:** branch results lose details the final question needs; then return the archive ID and let
the main thread `expand` it.

### 5. Exact save and restore of the cache on the NVMe drive (~2 GPU hours, after the engine overlay)

**Task:** follow-up idea 4 made concrete: save the exact cache's kept states for a 30K, 120K and 200K session to
disk, stop the server, start a fresh one, restore, continue for 512 tokens; also swap between two 120K sessions
on one server. **Arms:** (A) cold re-read; (B) exact prefix cache still warm (same server); (C) restore from
disk. **Pass:** (C) gives the same token ids as (A) and (B) on all cases (two fresh servers), restore of 200K
takes at most 15 s (vs 152 s cold), host RAM peak stays under 2 GiB above the server's baseline. **Fail:** any
token difference; then compare saved bytes against the warm states to find which state was not captured
(most likely a recurrent-layer state at the last partial piece).

**Total:** about 18 GPU hours, plus CPU-only work: the historical-question generator (exp. 2), the rule-change
generator (exp. 3), the multi-part document generator (exp. 4), and the save/restore overlay (exp. 5).

## Notes on what I could and could not verify

- Read at abstract or official-page level today: Complexity Trap, Context-Folding, AgentFold, ACE, ACON, MEM1,
  MemAgent, ReSum, InftyThink, Sculptor, ReadAgent, A-MEM, Mem0, HippoRAG 2, LongMemEval, OOLONG, Vending-Bench,
  goal drift, Lost-in-conversation, Illusion of Diminishing Returns, MAST, Speculative Actions, ESAA, LinearKV,
  the LMCache Qwen3.5 recipe, the shared-KV case study, Anthropic's two engineering posts, the Manus post, the
  Letta filesystem post. Numbers above come from those pages; full texts were not read.
- From secondary sources only: LCM paper details (aggregator page), Codex CLI compaction internals (third-party
  blog), sleep-time compute specifics.
- Not checked: whether vLLM's JSON-schema structured output path runs on our XPU build; whether the multi-user
  lossless overlays and the exact prefix cache have been tested together (the results note says several users
  at once is not yet tested with the cache). Both are first gates in experiments 1 and 4.
- ACON (https://arxiv.org/abs/2510.00615) is worth one line: it improves compression *guidelines* from paired
  failures (full context succeeded, compressed failed), 26-54 % fewer peak tokens; it is a way to tune the
  summary prompt for arm A of experiment 2 if that arm is to be a strong baseline, not a new direction.
- AgentDiet (https://arxiv.org/abs/2509.23586): a separate reflection call removes useless, redundant and expired
  text, 40-60 % fewer input tokens at equal SWE-bench score; on our streams the same effect comes from masking
  (A3) at no model cost.

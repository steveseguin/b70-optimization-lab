# Long-horizon context: the problem, every idea so far, and how we will test solutions

Status: program charter, 2026-10-10. Owner's framing (2026-10-05, 10-08, 10-10): an agent on one or two B70s should be able
to work on one task for weeks or months, with a history far beyond anything that fits in VRAM, and stay fast, accurate,
and on-goal. We are not interested in what is fastest below ~25K tokens (keep it all in VRAM; done). We are interested in
what happens when the history is 1M to 10M+ tokens and the live window is capped at 200K (or 32K-48K on a shared card),
after many rounds of context management.

Companion material: `experiments/qwen38-27b-b70/scripts/context/README.md` (harness),
`experiments/qwen38-27b-b70/notes/2026-10-05-context-*.md` and `2026-10-08-long-running-task-prereg.md` (prior work),
https://skindeep.ai/context.html (public page, stale as of 10-08: landing page lacks everything after the first ledger run).

---

## 1. The problem in one paragraph

A transformer agent's working memory is its KV cache. It is exact, fast to read, and bounded by VRAM. Once the history
outgrows it, something has to give: drop text (lossy), summarise text (lossy and compounding), move text out of the window
into files or stores and fetch it back on demand (exact text, but the model must know to look), or change how the cache is
built so that old material can be parked and restored exactly (engine work). Every production system today uses
threshold summarisation plus truncation, and the evidence is that quality decays with each round: constraint violations
rise from 0% to 30% after compaction (arXiv 2606.22528), summaries keep ~3% of tokens at 96K input (2605.23296), recent
actions lose influence (TRACE, 2608.06503), summaries-of-summaries drift (CliffCompaction, 2609.26779). Our own 10-08 run
shows the same shape: a lossy window at 48K answered 9/9 probes about the last 4 batches and 1/10 about anything more than
25 batches back. The goal is a system where accuracy by distance-back is flat, the live window stays under the cap, the
agent's wall time per 100K of history does not grow, and nothing numeric in the model's serving is lossy.

## 2. The use case and the rules

- Model served losslessly (16-bit KV, no quantised cache, no approximate kernels). How the *history* is managed may be
  lossy, but it is measured as such and the fastest-and-most-lossless option wins.
- One continuing task (research, a code base, agentic support), history 1M-10M+ tokens, live context cap 200K on a
  dedicated card, 32K-48K when the card is shared. Two cards available; the second may do background work.
- Studies must decide within hours: pilot, run arms concurrently against one server, stop when the gap is clear.
- Results go to skindeep.ai (lay -> example -> detail -> raw), recipes stay in this repo.

## 3. What the engine actually allows (facts that constrain every idea)

- **Qwen3.8-27B is a hybrid**: Gated DeltaNet recurrent layers plus attention layers. Recurrent state cannot be shifted
  or spliced. The only exact operations on it are *rollback to a saved checkpoint* and *re-prefill from that point*.
  llama.cpp's `--ctx-checkpoints` is exactly that mechanism; vLLM has no equivalent yet.
- **Gemma 4 26B** uses sliding-window attention on local layers: the same restriction (window contents change when
  you delete inside them), plus a huge 262K-row output head.
- **Deleting a middle block of a plain RoPE KV cache** (llama.cpp `seq_rm` + `seq_add` shift, Leyline 2606.01065,
  Kamera 2606.23581) is *approximate*: later keys are re-rotated to new positions, but their values were computed
  while attending to the deleted text. KL ~0.02 on GQA models. Exact only if everything after the edit is re-prefilled.
- **Appending is exact and cheap** (prefix cache). **Checkpoint + rollback is exact.** **Parking KV on host RAM or NVMe
  and restoring it is exact** (64 KiB/token on the 27B: 12.2 GiB at 200K; measured prefix-cache hit 0.8 s vs 11.4 s
  cold re-read at 121K).
- Therefore an exact custom engine should be designed around a **checkpoint tree** (branch, work, return, roll back),
  **exact prefix/suffix reuse**, and **background re-prefill on the idle card**, not around middle-splicing. Middle
  splicing can be offered as a labelled approximate mode with a measured seam-recompute (CacheBlend/EPIC/HYPIC style)
  and a measured KL, never as the default.
- "Update the context without feeding it back through the prompt": the exact ways are (a) append the update at the
  end (cheap, exact), (b) keep it outside the window and fetch on demand (files, archive, graph), (c) roll back to a
  checkpoint before the stale span and re-prefill the edited tail on the idle card, then swap at a turn boundary. (d)
  In-place KV surgery is the approximate fourth way and must carry a KL budget.

## 4. Every idea, with status

### 4a. Tried in this lab (2026-10-05 to 10-09; numbers from the notes, re-verified on the fixed checker)

| idea | arm | result | verdict |
| --- | --- | --- | --- |
| Whole 262K window, no management | A | 24/24 on 121K ledger, but 0/24 on seed 1 (window overflow) and decode falls 127->26 tok/s | not robust at the edge |
| Summarise at 75% of a 32K budget (Codex style) | C32 | 24/24, 41 min; retention 36/36 in 26 min; LongMemEval 19/23 at 58K tokens, 960 s | correct but slow and expensive |
| Paper's CLM self-editing agent (model edits its context file) | B32 | 19/24, 64 min; losses were harness rollback | harness bug, fixed |
| Improved CLM agent, thinking only where needed | B32in | 24/24 in 5.7-6.6 min; 24/24 on a 478K stream | best in-window editor |
| Files allowed (model writes state to disk, searches) | D32/E32 | 24/24 in 1.9 min | fastest when allowed |
| Read mode: model reads prose, keeps `name value` lines | B32ir | 23/24 at 119K; 10/10 at 480K; 23/24 at 1M in 62 min | reads past the window by understanding |
| Quoted events, code does arithmetic | B32iq | 24/24 at 1M in 48 min (~23% faster than B32ir) | exact for bookkeeping only |
| Archive-on-drop + `recall` search | B32ira | retention 36/36 in 6.1 min vs C32 26 min; LongMemEval 42/56 at 10.5K tokens vs full-history 46/56 | recommended memory method; weak on abstention (1/8) |
| Free-form notes <= 6,144 tokens + archive | B32ira-free | LongMemEval 42/56, 341 s | same as above |
| Drop old thinking from every call | At/*t | no gain unless state lives elsewhere | minor |
| CPU cleaner removing wasteful spans | - | frees < 2% | dead |
| Stop early on enum/decision answers | - | 6.5x faster for label decisions | keep as a lever |
| Lossy sliding window at 48K | W48 | **33/43**; probes 9/9 at 1-4 batches back, 13/14 at 5-24, 1/6 at 25-99, 0/4 at 100-399, "who" 4/11 | the decay curve we must beat |
| Compaction: stub old tool output, strip thinking, 48K | D48 | **30/43**; 9/9, 9/14, 2/6, 0/4, "who" 1/11 | worse than plain window drop |
| Summary at 48K | C48 | cancelled at the 4 h limit after 17 summaries | too slow to even finish |
| CLM variants at 48K / 200K | B48*, B200* | never ran (4 h limit, then a two-card GPU fault on 10-09 02:11) | **open** |

W48/D48 are from `/mnt/fast-ai/bench-results/context-longrun-20261008/campaign/` (not written up until now).

### 4b. Proposed here, not yet run

- Per-batch commit proof with atomic staging; file I/O cost vs decode cost; **exact KV park-and-restore on NVMe**;
  prompt layouts that pay back the prefix cache (`2026-10-05-context-followup-ideas.md`).
- Summaries with pointers ("lossless by reference"); itemised playbook notes (ACE); observation masking; recursive
  summarisation; parallel map / deterministic reduce reading with 16 requests in flight; redundant re-read on
  disagreement; branch-and-return side jobs; goal and rule recitation; removing resolved mistakes from view;
  speculative actions; tiered memory with a sleep-time consolidator; Mem0 / A-MEM / HippoRAG 2
  (`2026-10-05-context-approaches-survey.md`).
- ContextBench's other tasks (needle retention, sudoku, log triage) not built.
- Previously excluded as lossy at the engine: suffix cache reuse, CacheBlend, EPIC, PIE, H2O, SnapKV, StreamingLLM,
  CacheGen, KV quantisation, LLMLingua, trained memory agents. With our own engine these can be **re-admitted as
  labelled approximate modes** if the KL/exactness is measured and reported, never as the default.

### 4c. Outside work worth taking (survey 2026-10-10; arXiv ids)

Prompt / system level, no engine support needed:
- **Structured eviction without an LLM call** (CWL, "Beyond Compaction", 2606.11213): trajectory tagged as typed,
  dependency-linked episodes; over budget, drop *action* episodes whose effects already live in the environment; keep
  user turns, constraints and live reasoning verbatim. 89 tasks over 80M tokens with no measured loss. Zero compute.
- **Pinned head + tail, tool-result clearing, memory file** (Anthropic context-engineering primitives; Governance Decay
  shows head_tail is the only compaction that kept constraints at 0% violations).
- **Context folding** (branch/return with KV rollback to the branch point, 2510.11967): main thread ~8K while
  processing >100K; needs exactly the checkpoint rollback we have.
- **CLM** (2609.37725): model edits its own context; +11.4% at -21.5% FLOPs zero-shot on BrowseComp-Plus; its serving
  patch (suffix cache reuse) is approximate, so for us it becomes "roll back + re-prefill on the idle card".
- **CliffCompaction**: never summarise a summary; keep verbatim excerpts.
- **Temporal facts with validity windows** (Zep/Graphiti 2501.13956): the right fix for stale facts; **Mem0**-style
  add/update/delete ops; **HippoRAG** graph + PageRank for multi-hop recall; **A-MEM** linked notes; **ReadAgent** gist
  pages with re-read on demand; **RAPTOR** summary tree; **Voyager** skill library (executable, tested memory);
  **Reflexion/ExpeL** lessons; **Letta sleep-time** consolidation (5x less test-time compute at equal accuracy).
- **Parallel context compaction** (2605.23296): compact block by block in parallel instead of one blocking pass.

Engine level (needs our engine):
- Exact: prefix cache + host/NVMe KV tier (LMCache, Mooncake, llama.cpp `--cache-ram`, `--slot-save-path`,
  `--ctx-checkpoints`), checkpoint tree, prefill/decode disaggregation across the two cards (Splitwise, DistServe),
  background re-prefill of the post-edit prompt on the idle card and swap at a turn boundary.
- Approximate (labelled, measured): middle-span delete + RoPE re-anchor (Leyline, Kamera), non-prefix KV reuse with
  seam recompute (CacheBlend, EPIC, APE, HYPIC for hybrids), retrieval-head-only full KV (DuoAttention, RazorAttention),
  learned gist/compression tokens (ICAE, xRAG; falls apart beyond ~4-10x on exact recall).
- Model level (new weights, out of scope for Qwen/Gemma): RMT, Titans, Infini-attention, TTT-E2E, MemoryLLM.

### 4d. Answers to the specific questions

- *Graph-RAG of context looked up in RAM?* Yes as the archive tier: verbatim text on disk plus an index in RAM (BM25 +
  embeddings + an entity/temporal graph with validity windows). It is exact text. What it does not solve is *knowing to
  look*; that is why pinned state, recitation and probes matter, and why our archive arm failed abstention.
- *Update context without feeding it back into the prompt?* Appending is free. Replacing something in the middle is
  either a checkpoint rollback + re-prefill of the tail (exact; do it on the idle card) or an approximate KV edit.
  Keeping the editable material near the *end* of the prompt (layout) makes the exact path cheap.
- *Surgical compaction of only some blocks without reprocessing all?* Exactly: only if the blocks are a suffix, or the
  layout puts them at the end, or you accept the seam-recompute approximation with a measured KL. Our engine should
  expose both and report which one ran.
- *Compaction when the GPU is idle?* Yes: sleep-time consolidation (archive indexing, note rewriting, summary trees,
  re-prefill of the next layout) runs between turns or on card 2. The swap-in must happen at a turn boundary.
- *Two GPUs taking turns?* Card A decodes, card B prepares the next context (re-prefill, consolidation); hand over the
  ready KV at a boundary (Splitwise-style transfer, or just swap which card serves the next turn). Requires TP1 per card,
  which is our one-card lane.

## 5. What "better" means: the benchmark

Every benchmark we found measures recall from a *static* history. Almost none measures an agent after N rounds of its own
compaction. Ours must.

**Scenario.** One continuing task whose history grows to many times the live cap, with probes interleaved at controlled
distances back. Two scales: dedicated card (cap 200K, history 1M-2M) and shared card (cap 32K-48K, history 480K). Seeds
>= 2. Same server for all arms, arms run concurrently (host RAM is the limit; measure it).

**Axes measured (each probe family at distances 1-4, 5-24, 25-99, 100-399, 400+ batches back):**
1. Current value of overwritten state (ledger / kv-stream): tests the live working set.
2. Retention of incidental detail ("who did X at Y"): tests the archive and the model's willingness to look.
3. Knowledge updates and abstention (LongMemEval-style; "not mentioned" must be answerable).
4. Constraint and goal adherence after k compactions (a rule stated at the start must still hold at the end;
   Governance-Decay style; this is the cheapest and most damning test).
5. Procedure reuse: a tool or trick learned early must be reused late (Voyager-style skill memory).
6. Task progress on a real artefact: a growing code base or document whose later steps depend on early decisions
   (counts features delivered, regressions, and re-work).
7. No-collapse: coherence over the full run (Vending-Bench failure mode is collapse, not slow decay).

**Costs recorded for every arm:** wall time per 100K of history; tokens generated for management (edits, notes,
summaries); peak and mean live context; number of compaction events; prefix-cache hit rate and re-prefill tokens; host
RAM and VRAM; and for any approximate engine mode, the KL / token-divergence against the exact path.

**Decision rule:** accuracy-by-distance curve first (flat beats high-near-low-far), then wall time per 100K, then
management tokens. Lossy arms stay in the comparison as the floor.

**Existing assets to reuse now:** sparse prose stream with `--probes-every/--probes-k` (480K, 9 probes + final set,
43 questions), ledger and kv-stream generators, LongMemEval_S, `second-comparison.sh` arm matrix, `probe_analysis.py`,
the W48/D48 curves above as the first baseline, the fixed checkers (PR #73, #74).

**Missing and to build:** axis 4 (constraint probes), axis 5 (procedure reuse), axis 6 (artefact task), a
compaction-count dimension (force k compactions and plot accuracy vs k), and a "management overhead" ledger per arm.

## 6. Plan

- **P0, baselines (first):** W48/D48 finished across seeds; C48 and the 200K-cap variants; add axes 4-5. Produces the
  decay curves every contender must beat. Hours, not days.
- **P1, prompt/system contenders on the current engines:** archive + recall (B32ira) with abstention evidence; CLM
  self-edit (B32i*) at 48K and 200K; CWL structured eviction; pinned head/tail + memory file; Zep-style temporal fact
  store; folding (branch/return on checkpoints); hybrids. Same harness, same probes.
- **P2, engine levers in our own engine (coordinate with the other host's runtime work):** checkpoint tree with exact
  rollback; KV park/restore to host RAM and NVMe; background re-prefill on card 2 with turn-boundary swap; exact suffix
  reuse; approximate seam-recompute mode with KL reporting. Measure wall-time per 100K and cache hit rate.
- **P3, the combined system:** best P1 policy on the P2 engine, run to 10M tokens of history with probes, published on
  skindeep.ai with reproduction.

Owner decisions needed: whether approximate engine modes may appear in the comparison at all (as labelled arms), and
which card budget (one shared card at 48K vs a dedicated card at 200K) is the primary target for P1.

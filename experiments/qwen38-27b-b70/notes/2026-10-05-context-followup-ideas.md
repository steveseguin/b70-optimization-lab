# Context follow-ups: five proposed experiments

These are proposals, not new measurements or instructions to launch a campaign. Evidence reviewed through `83a71180e3abf4eec7f57181fc1433cedc3cdd26`. First consume the improved-agent 120K two-seed run and the queued 480K runs, including files-allowed arms. The work below adds questions those runs do not settle. Start with existing transcripts and CPU-only checks.

## 1. Prove every delivered update becomes committed state

The [first comparison](2026-10-05-self-editing-first-comparison.md) traces five wrong answers to discarded deliveries. Protecting a delivery is necessary, but seeing it once is not proof it was applied exactly once. In [the summarizer](../scripts/context/summarize_results.py), `items_lost` checks missing headers; `seen_whole` checks the header and final line. Neither checks every intervening update. [STATE validation](../scripts/context/clm_improved.py) checks size and optional line format, not state correctness.

**CPU-first experiment:** replay the saved ledger after every batch with a deterministic reference reducer. Compare the agent's state with that reference at each committed batch ID, covering all counters, including deleted ones. Keep the reference hidden from the agent. Classify errors as delivery, parsing, duplicate application, arithmetic, state replacement or answer lookup.

**Next mechanism to test:** stage a candidate state with its last committed batch ID and source hash; validate, then atomically commit it before discarding the raw delivery. Retrying an acknowledged batch must not apply ADD twice. Account for pending raw input in the memory-only budget; this must not create a hidden archive. Inject failure before/after commit and between state replacement and raw-turn deletion using a stub.

**Pass:** zero missing or duplicate updates, exact state at every batch, correct final answers, and restart/retry recovery without hidden retained data. A format-valid but wrong state must fail the grader.

## 2. Separate a compact running ledger from arbitrary historical recall

The [ledger task](2026-10-05-self-editing-first-comparison.md) has about 160 counters and deliberately irrelevant memos. A small sufficient state can retain everything needed for its final questions. That does not establish that summaries preserve an arbitrary document or conversation.

After the queued ledger results, preregister two extensions: a growing number of live counters, and surprise questions about old overwritten values or memo text. For the latter, keep queries hidden until the stream ends and spread them across the stream. Compare an exact indexed archive, agent-managed files with retrieval, and budget-matched self-editing/summary arms. Use the existing key-value generator where possible instead of inventing another benchmark.

**Measure:** exact answers, confident wrong answers versus admitted misses, bytes archived, retrieval calls, retrieved tokens, peak active context and completion time. Grade file integrity separately from retrieval and copying.

**Pass for an archival claim:** every requested value exact across the preregistered seeds and lengths, including input beyond the native window. Report the tested extent; finite tests cannot establish literally unlimited capacity. A ledger-only pass supports continued work with bounded sufficient state, not universal recall.

## 3. Measure file costs separately from the faster overall workflow

The [121K ledger result](2026-10-05-context-research-results.md) took about 1.9 minutes with files versus 26 minutes for the large-context arm. The runs also generated very different amounts of text and used different active contexts. This is not a disk-write overhead or decode-speed comparison.

First reconstruct time spent generating, reading prompts, executing tools and waiting from existing records. If streamed token timestamps are absent, leave decode rate unmeasured. Then replay identical file operations without a model, comparing an in-memory store and ordinary files: serialization, write, read, retrieval and peak RAM. Distinguish buffered writes from explicitly durable writes; identify page-cache effects without changing host cache settings.

A later paired model check should send identical prompts and produce identical continuations, changing only the storage operation between calls. Separately measure the real files-based workflow with its smaller prompts.

**Pass:** exact stored/retrieved bytes and equal task correctness; separately reported I/O time, TTFT, inter-token decode rate and full-task time. Any “no meaningful decode penalty” claim needs a preregistered tolerance and fresh-server repeats, not a nonsignificant difference from one pair.

## 4. Build an exact park-and-restore test before active disk offload

The [snapshot proposal](2026-10-05-context-research-review.md) is unbuilt. Begin with a source inventory: target KV pages, recurrent/convolution state, draft state, positions, token history, block mappings and scheduler metadata. Establish a supported XPU export/restore path and bounded staging buffers before GPU work.

Compare uninterrupted resident continuation, saved/restored continuation, and cold rereading under the same model, arithmetic and scheduling configuration. Start at a small prompt; scale only after equality. Record bytes, save time, restore-to-first-token latency, RAM/VRAM peaks and post-restore decode rate. Check tensor hashes and continuation tokens; copied bytes alone do not establish equivalent execution. Include fresh-process restore and scores where safely available.

**Pass:** exact continuation throughout the declared suite and measured restart benefit, with no state omitted. A saved session must fit active working memory again before ordinary resident decoding.

The target attention KV calculation is **64 KiB per token across both cards**: 200,000 tokens alone require about **12.2 GiB**, excluding recurrent checkpoints, drafting, padding and workspace ([layout](2026-10-05-prefix-cache-reuse-rules.md)). This is not a few-KB working set. Active per-step CPU/disk offload is a separate implementation requiring transfer/stall measurements; no disk decode rate has been established.

## 5. Find when exact prefix reuse repays its cold-read cost

Use saved trajectories to compare token prefixes for front-updated versus tail-updated state, then predict reusable boundaries from the [reuse rules](2026-10-05-prefix-cache-reuse-rules.md). Confirm with a small matched campaign only after the queued work.

Measure cold TTFT, each later turn, total task time, cache hits and checkpoint memory for both layouts and sparse checkpoint intervals. Require exact cache-on/off continuations within each fixed layout; different layouts need task-quality comparison because their prompts differ. Include conversations with generated answers and edits around checkpoint boundaries.

**Pass:** equal correctness and a repeatable end-to-end gain after including the slower cold read. The [88.5–89.7 tok/s gate](2026-10-05-prefix-cache-exactness-prereg.md) supports unchanged decode in that small test, not a speed boost. Prefer these layout improvements over another general cleaner: the [census](2026-10-05-context-hygiene-census.md) found only 1.83% removed by its information-preserving rules, and removing old thinking requires working state elsewhere.

# Context hygiene census (2026-10-05)

## In plain words

- The question was whether a CPU-side cleaner could tidy a 27B agent's context so a fixed window holds much more ("32K into 100K") with nothing lost. On real agent sessions it can't. A strictly no-loss cleaner (drop duplicate outputs, re-printed lines, superseded file reads, whitespace and terminal noise) frees about **1-2%**: a 32K window holds about 33K tokens' worth (**1.01x**) and a 128K window about 133K (**1.02x**).
- Also dropping earlier thinking takes it to about **1.02x**. On these transcripts most of the thinking text was not saved, so they undercount it. For our own model it matters more: on a typical call, earlier thinking that gets re-sent is **about 10%** of what is sent, and up to **56%** on the worst call.
- Also moving big tool outputs (over 2,000 tokens) to disk, keeping only their first and last 400 tokens in view, gets to about **1.08-1.09x**. That step does not delete anything, but in about **one case in three** the agent later used a line from the hidden middle, so it would have needed to read the file back.
- Why the gain is small: most of the context is new material. The agent's own tool calls (mostly scripts it writes inline) are 48% and fresh tool output is 43%. There is very little exact repetition to squeeze out.
- So to really multiply the window you have to change what goes in (summaries, self-editing, retrieval). Those methods can lose information, so they need to be measured on tasks. Tidying cannot do it. The one cheap win for our model is not re-sending old thinking.

## Data

- Set 1: the three largest Claude Code session transcripts on this host (31, 24 and 16 MB of JSONL). Together they hold 4.99M Qwen tokens of context content across 18,100 segments. Compaction summary records (9) and harness attachment records were skipped. 33 image blocks in tool results were skipped.
- Set 2: the 27B's own runs from the self-editing harness tonight (`/mnt/fast-ai/bench-results/context-clm-first-20261005/client/{kv32k,kvbig}/jobs/*/*/agent/context_snapshots`). That is 12 trials and 277 calls, using the per-call message snapshots.
- Tokenizer: `/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json` (HF `tokenizers`, no special tokens).

## Tables (set 1: three real sessions, pooled)

### What the context is made of

| kind | tokens | % |
|---|---:|---:|
| tool calls (inputs; ~75% of this is inline heredoc scripts) | 2,380,555 | 47.7 |
| tool outputs | 2,131,830 | 42.7 |
| user text | 202,459 | 4.1 |
| assistant text | 157,298 | 3.2 |
| harness-injected user text (meta) | 74,064 | 1.5 |
| assistant thinking (visible text only; 650 of 3,879 blocks kept text) | 40,899 | 0.8 |

Tool output size in tokens, per session:

| session | n | p50 | p90 | p99 | max |
|---|---:|---:|---:|---:|---:|
| A | 2,731 | 155 | 911 | 2,753 | 7,333 |
| B | 1,185 | 181 | 1,151 | 4,082 | 7,752 |
| C | 1,246 | 232 | 1,194 | 3,550 | 11,322 |

### Saving per rule (each alone, % of all context tokens)

| rule | tokens removed | % | per session |
|---|---:|---:|---|
| R1 exact duplicate tool output -> pointer | 1,910 | 0.04 | 0.02 / 0.04 / 0.08 |
| R2 superseded file read (containment) -> pointer | 63 | 0.00 | 1 read superseded in all three |
| R3 repeated lines (>= 40 chars) in tool outputs | 91,259 | 1.83 | 1.49 / 2.14 / 2.22 |
| R4 earlier-turn thinking (visible text only) | 40,594 | 0.81 | 0.97 / 0.57 / 0.74 |
| R5 whitespace / ANSI / CR / separator noise | 2,175 | 0.04 | 0.03-0.14% of tool-output tokens |
| R6 big outputs: head 400 + tail 400 + pointer (**moved to disk, not deleted**) | 374,120 | 7.50 | 4.75 / 10.74 / 9.84 |
| extra: any output fully contained in a later one | 2,601 | 0.05 | |
| extra: R3 applied to tool-call inputs | 1,996 | 0.04 | |

### Combined, without double counting

| set of rules | tokens removed | % |
|---|---:|---:|
| R1+R2+R3+R5 (strictly no loss) | 91,021 | 1.83 |
| + R4 | 131,615 | 2.64 |
| + R4 + R6 | 488,757 | 9.80 |

### Effective window multiplier (sliding window, averaged over ~1,600-2,200 points per session)

| window | R1+R2+R3+R5 | + R4 | + R4 + R6 |
|---|---|---|---|
| 32,768 | ~33,070 raw tokens held: **1.009x** (1.007 / 1.008 / 1.012) | **1.015x** | ~35,400: **1.081x** (1.055 / 1.078 / 1.109) |
| 131,072 | ~133,100: **1.016x** (1.012 / 1.016 / 1.019) | **1.023x** | ~143,100: **1.091x** (1.068 / 1.086 / 1.120) |

### R6: how often a hidden middle was needed later

- Outputs over 2,000 tokens: 152 across the three sessions.
- For 54 of them (**36%**), a later tool call quoted a distinctive line (>= 30 chars, not in the kept head or tail, and not in an earlier output) from the hidden middle. No assistant prose quoted one.
- For 15 of them (10%), the quote came within the next 6 segments, which is effectively the next step.
- This is a rough upper-bound proxy, because the same line could also have reached the agent another way. It means that roughly every third truncation would cost one extra read-back call.

## Set 2: earlier thinking re-sent by our 27B (share of each call's tokens)

The served chat template keeps thinking from all earlier assistant messages (`preserve_thinking` is undefined, which counts as true, at chat_template.jinja line 116). In a single-task agent loop every assistant message comes after the last user message anyway, so all of it is re-sent on every call.

| trial set | calls | median % | max % | final call % |
|---|---:|---:|---:|---:|
| kv32k clm p1 / p2 / p4 | 20 / 20 / 15 | 6.7 / 5.9 / 16.4 | 49.8 / 10.1 / 18.1 | 2.6 / 10.1 / 18.1 |
| kv32k summary p1 / p2 / p4 | 14 / 19 / 48 | 3.8 / 5.8 / 14.6 | 9.9 / 10.2 / 55.8 | 9.9 / 10.2 / 39.4 |
| kv32k plain p1 / p2 / p4 | 14 / 19 / 35 | 3.8 / 5.8 / 14.6 | 9.9 / 10.2 / 23.8 | 9.9 / 10.2 / 23.8 |
| kvbig plain p1 / p2 / p4 | 14 / 19 / 40 | 3.8 / 5.8 / 14.9 | 9.9 / 10.2 / 34.6 | 9.9 / 10.2 / 34.2 |
| **all 277 calls** | | **9.9** | **55.8** | |

Several trials produced identical trajectories (same p1 and p2 numbers in the plain, summary and kvbig runs), so there are only about 8 distinct runs here. The share grows with run length (p4 tasks: 15-40%). If the previous message's thinking is dropped at each step (a rolling drop), only the cache from that message onward is invalidated. That is the last tool call and its output, so the re-read costs about one step's worth of tokens per call (see caveat 5).

## Method

Script: `experiments/qwen38-27b-b70/scripts/context/hygiene_census.py`
(`claude FILE...` for set 1, `snapshots DIR...` for set 2). It prints only aggregate JSON. Peak RSS was 140 MB, and a run takes 11 s for the three sessions and 3 s for set 2.

- The script streams each JSONL file line by line and skips repeated record uuids, compaction summaries, and non-message records. Each content block becomes one segment: user text, harness-injected (isMeta) text, assistant text, thinking, tool call (`name + JSON input`), or tool output (text parts of the result). Each segment is counted with the Qwen tokenizer.
- The session is treated as one continuous stream; compaction resets are ignored. Dedup referents (R1, R3) must lie within the previous 131,072 raw tokens. In the window multiplier, a pointer whose referent has slid out of the window is undone, with an iterated fixed point. R2 counts only from the moment the superseding output exists.
- R1 matches byte-identical tool output and replaces it with a 12-token pointer, applied only if the output is over 12 tokens. R2 covers file reads (Read tool, or Bash `cat/head/tail/nl/sed -n` of a path with no pipe or redirect). Such a read is replaced by a 12-token pointer once a later tool output contains every one of its non-empty lines. R3 drops lines of 40 or more characters that are present verbatim in an earlier kept output, at a cost of 6 tokens per run. R4 drops thinking from every human turn except the latest one. R5 strips ANSI, keeps the final state of CR-overwritten lines, strips trailing spaces, collapses 3+ blank lines, and shortens separator runs of 10+ characters to 4. R6 replaces an output over 2,000 tokens with its first 400 and last 400 tokens plus a 20-token pointer.
- Combined order per output: R5, then R1 (on the normalised text). If R1 does not apply, an output that contains an earlier pending read keeps itself in full and turns that read into a pointer. Otherwise R3 runs against lines kept verbatim elsewhere. R6 is applied last. A copy is never removed in favour of a copy that was itself removed.
- R6 reference proxy: distinctive middle lines are indexed by their first 30 characters. Every later assistant text and tool-call input is scanned for a full-line substring match.
- Set 2 counts every message as content + `reasoning_content` + tool-call JSON + 4 tokens. Earlier thinking is the `reasoning_content` of every assistant message except the most recent one.

## Caveats

1. Set 1 comes from a different agent harness (Claude Code), not our 27B's. That harness already strips terminal noise and caps or persists very large outputs to files (max output seen: 11K tokens), so R5 and R6 are measured on outputs that were already cleaned upstream. A raw harness with no such caps would gain more from R5 and R6, but that is the same gain as fixing the harness's output handling.
2. These sessions write scripts inline as heredocs, so tool calls are 48% of the context, and no cleaning rule touches them. An agent that writes files with an edit tool and reads them back would show more R1, R2 and R3 repetition. R2 found almost nothing here because this agent seldom `cat`s whole files and mostly reads ranges and grep results.
3. Most of the thinking in set 1 was not stored (only 17% of blocks have text), so R4 there is a floor. Set 2 is the real measure for our model.
4. The cleaner changes the text the model sees. Even with no information lost, the model's next output can differ, so lossless here means the information is kept, not that the outputs are bit-identical.
5. Prefix cache: every rule changes the cached prefix from the edit point onward. Applying a rule when the text is appended, before the model has read it, costs nothing (R1, R3, R5, R6 can all work that way). Applying it later, as with R2 (which only becomes possible once the later read arrives) or R4 (which drops thinking from an earlier turn), forces the server to re-read everything after the edit point. For R4 on our model the cheap form is a rolling drop: remove the previous assistant message's thinking when the next call is built, so only the last step is re-read. The served template does not do this by itself, because `preserve_thinking` defaults to keeping the thinking.
6. R6's 36% "needed later" figure is a proxy. A quoted line may have come from somewhere else, and an agent may have needed a hidden line without quoting it.

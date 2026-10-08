# LongMemEval retention study: preregistration (2026-10-07, CPU preparation only)

**In one sentence:** the next context test should use someone else's benchmark, not ours. LongMemEval gives
each question about 110K tokens of real-looking chat history written by its authors, plus a reference answer.
We feed that history to the model one session at a time and ask the question at the end. Then we compare four
ways of managing context on the same 56 questions. Nothing has run on the GPU yet.

The owner's goal (2026-10-05) is "unlimited context with better speed and better long-term retention and task
focus; a single B70 (or two) should be able to work on a task indefinitely with better results than
summarisation or blind splicing of old context". The Oct 5-7 results used assistant-authored streams
([results](2026-10-05-context-research-results.md), "The short answer").
[Priorities](2026-10-07-context-research-priorities.md) asks for "independently sourced relevant history".
This study supplies that.

## Benchmark choice

| Benchmark | Source of history | Size per question | Ground truth | Licence | Fit |
| --- | --- | --- | --- | --- | --- |
| **LongMemEval_S** (cleaned) | Benchmark authors' pipeline. Simulated user sessions plus ShareGPT/UltraChat filler, timestamped | 102.6K-111.9K Qwen tokens (measured), 38-62 sessions | 500 human-curated Q/A, 6 types + 30 abstention | MIT | **Best.** Fits the 262K window, so a keep-everything arm and a one-call control are possible. Questions are asked after all sessions and the history is session-ordered. The official judge prompts are public |
| LoCoMo | LLM-agent conversations, human-edited | about 9K-26K tokens (10 conversations) | QA + event summaries | CC BY-NC 4.0 | Too short: it fits under the 32K budget, so it does not exercise context management. Licence is non-commercial |
| MemoryAgentBench (ai-hyz) | Repackages existing sets (incl. LongMemEval_S*, RULER, InfBench, FactConsolidation) as incremental chunks | varies | yes | MIT | Good later cross-check. Its Conflict_Resolution split is synthetic counterfactual edits, and it mostly reuses LongMemEval for chat memory |
| LongMemEval_M | same as S | about 500 sessions, about 1.5M tokens | same | MIT | The beyond-window follow-up (5.7 times the window). It is 2.7 GB, so it is not downloaded yet |
| LongMemEval-V2 (2026/05) | agentic memory | n/a | n/a | n/a | Not reviewed. Noted for later |

LongMemEval is independent: the history and the answers were written by the benchmark authors, not by this
lab or its assistant. The history itself is partly LLM-generated (simulated users), so it is "independently
authored", not "human-written". Say that wherever results are quoted.

Data facts (checked on this host, 2026-10-07):

- Downloaded to `/mnt/fast-ai/datasets/longmemeval/`: `longmemeval_s_cleaned.json` (277 MB, sha256
  d6f21ea9…c3a442) and `longmemeval_oracle.json` (15 MB, sha256 821a2034…38620c). Both hashes match the HF LFS
  oids. There are 500 instances: 133 multi-session, 133 temporal-reasoning, 78 knowledge-update, 70
  single-session-user, 56 single-session-assistant, 30 single-session-preference. 30 of the 500 are
  abstention (`_abs`). Answers: 468 strings, 32 integers.
- The upstream README now points to the **cleaned** release (2025-09, noisy sessions removed). That is the
  release we use.
- **Two quirks in the data:**
  - 211 of 500 histories are *not* in date order, although the README says they are. The task maker sorts
    sessions by date. Use `--order given` to keep the file's order.
  - In 76 instances (60 temporal-reasoning, 16 knowledge-update), some sessions are dated after the question
    date. 75 of those late sessions are evidence sessions.

  In our 56-question sample, 19 histories were reordered and 4 have late sessions (2 of them late evidence).
  Those 4 are flagged in `task.toml` metadata and are reported both with and without.
- Evidence session ids start with `answer_`. The ids and the `has_answer` labels are never served to the
  model.

## Grading

Official scoring uses a GPT-4o judge (`gpt-4o-2024-08-06`, temperature 0, `'yes' in reply`) with one prompt
per type. The prompts are copied verbatim into `make_longmemeval_tasks.py` (`JUDGE_PROMPTS`) from
`src/evaluation/evaluate_qa.py`:

- basic: single-session-user, single-session-assistant and multi-session.
- temporal-reasoning: off-by-one day counts are not penalised.
- knowledge-update: old information alongside the updated answer is still correct.
- preference: graded against a rubric.
- abstention: correct if the model identifies the question as unanswerable.

The headline is the per-type mean and the overall accuracy, plus task-averaged and abstention accuracy.

No judge is available offline. Each trial's verifier therefore does two things:

1. **Deterministic grade (not the headline).**
   - Abstention is correct when the answer reads as a refusal. That is the official rule, applied here with a
     regex. The regex matches all 30 abstention references and 2 of 470 other references.
   - Otherwise `exact` or `contains` (normalised) counts as correct.
   - Everything else is `unmatched`. Long or paraphrased references need the judge.
   - Preference answers are always `judge_only`.
2. **Judge pair.** It writes `/logs/verifier/judge_pair.json` with the question, the reference, the hypothesis
   and the fully formatted official prompt. `make_longmemeval_tasks.py collect JOBS... --out hyp.jsonl` writes
   the official hypothesis file for `evaluate_qa.py`.

**The headline must be the judged score.** Judge choices, which are the owner's call:

- (a) The official GPT-4o judge through an API key. This is comparable to published numbers, if
  `gpt-4o-2024-08-06` is still served.
- (b) The 27B as judge. It is free and offline, but it judges its own answers. Report it only as secondary,
  with its agreement against (a) on a subset.

In both cases, hand-check every case where the judged and deterministic grades disagree.

Oracle check (CPU, 2026-10-07): the reference answers written back through the grader score 40 exact, 8
correct refusals and 8 judge-only (preference) out of 56, in both modes. The storage audit raised no
violations.

## Hypothesis

At a 32K working budget, archive-and-recall (B32ira) answers LongMemEval_S questions at least as accurately as
summarising at 75 % (C32), in clearly less time. It also comes close to keeping the whole history in the 262K
window (Ar). Retention questions, meaning facts the agent had moved out of view, are where summarising should
lose: the agent does not know the question in advance, so a summary has to guess what matters, while an
archive keeps everything verbatim.

## Arms (identical tasks, identical instruction, server unchanged: 16-bit KV cache, no quantized KV)

| Arm | What it is | Budget | Storage | Trimming reported as |
| --- | --- | --- | --- | --- |
| **B32ira** | Improved agent. Reads each session, keeps its own notes in STATE.txt, drops the session into a read-only verbatim archive, and searches it with `recall` | 32,768 | memory (+ archive) | archive (lossless by reference) |
| **C32** | Summary agent, summarises at 75 % of the budget | 32,768 | memory | summarisation (lossy) |
| **Ar** | Plain agent, keeps everything, window shown | 262,144 window | memory | none |
| **E32r** | Plain agent, files allowed | 32,768 | notes | files (agent's own) |
| F (control, recommended) | One call: the official full-history reader prompt (`History Chats ... Current Date ... Question`), all sessions plus the question | 262,144 window | n/a | none |

F is the inexpensive baseline that [priorities](2026-10-07-context-research-priorities.md) asks for. It sees
the question together with the history, so it shows what the model can do with everything in view. It is not
a test of retention. It needs a small new driver (one chat call per question), not the stream harness.

**Resolved (same day): arm `B32ira-free` replaces B32ira for this study.** It is
`scripts/context/clm_freenotes.py:ClmFreeNotesAgent`, a subclass of the improved agent:

- STATE.txt holds free-form notes capped at 6,144 tokens (`STATE_MAX_TOKENS`).
- STATE.txt may change only while a new item is in view. The counter-line "never vanishes" guard is off.
- `ctxfold --drop` always runs forced, through a shim in front of the unchanged `ctxfold.py`.
- The protocol text is about notes on the user, and before answering it tells the agent to search the archive.
- Archive and `recall` are unchanged.

It is selected by `longmemeval-run.sh`, which appends `-a clm_freenotes:ClmFreeNotesAgent` to the harbor
arguments of `run-context-job.sh`. Harbor's `--agent` is single-valued and the last one given wins (checked
in harbor/cli/jobs.py and with typer 0.27.2). No existing file was edited.

Historical note, the original blocker: the read-mode protocol in `clm_improved.py` is worded for counters, and the
code enforces counter lines:

- `PROTOCOL_READ`, and `state_line_regex` defaulting to `^[a-z]+\d\d\s+(-?\d+|removed)$`.
- `ctxfold --drop` refuses when the text names `\b[a-z]+\d\d\b` tokens that have no STATE line. Chat text
  contains such tokens (`covid19`, `rtx30`).

A LongMemEval variant needs, in a **new** file (the live run uses the existing harness):

- a free-text STATE protocol, such as "facts about the user, with session date", with a size cap;
- `state_line_regex` set to something permissive (it can be passed with `EXTRA_KWARGS`);
- drop without the name check (`ctxfold --drop --force`);
- archive and `recall` unchanged.

`second-comparison.sh` cannot drive these tasks either: it builds its own task names. A small new driver should
call `run-context-job.sh` per task, with the same environment as its `run_one`. C32, Ar and E32r need no agent
change. Run the existing `STUB=1` wiring check against two LongMemEval tasks first.

## Sample and budgets

- `make_longmemeval_tasks.py build OUT --subset 8 --seed 0 --mode memory|notes --exact-tokens`
  - 8 questions in each of 7 strata (the 6 question types without abstention, plus abstention): 56 questions.
  - This replaces the "10 per type = 60" example so that abstention gets 8 questions instead of about 3.
  - The task lists are already built in `/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0/lme-{memory,notes}`,
    with ids in `selection.json`.
- The stream is 102.6K-111.9K tokens (mean 109.4K, total 6.13M) in 42-63 items, one session per item.
  - The largest item is 6.3K tokens, so the 8K split cap never fired.
  - The final item is the question, with the current date.
- B32ira, C32 and E32r use the 32,768 budget (memory mode; E32r uses notes mode). Ar uses the 262,144 window.
  The stream is 3.3 to 3.4 times the 32K budget and about 0.42 of the window.
- Server and settings: temperature 0, thinking as each arm's existing default, `MAX_TOKENS` 16384, the same
  served build for every arm. Record the build and the overlay set in the run folder.

## What is measured

- **Primary:** judged accuracy per type and overall (task-averaged and overall), and abstention accuracy, per
  arm. Use paired comparisons on the same 56 questions.
- **Secondary:**
  - deterministic grade;
  - elapsed wall time per question;
  - tokens written (and the thinking share);
  - peak context;
  - model calls;
  - for B32ira, `recall` calls and recall output tokens;
  - for C32, the number of summaries;
  - void, cap and timeout flags from `summarize_results.py --check`.
- **Per-question context:** stream tokens, evidence item positions (`tests/reference.json`), and whether the
  evidence had been dropped before the question. That last item separates retention from reading.

## What counts as "better than summarising"

On the judged score, B32ira beats C32 if both of these hold:

1. **Accuracy:**
   - B32ira is correct on at least as many of the 56 questions as C32 (non-inferior: at most 2 fewer, with
     discordant pairs listed); and
   - B32ira is not worse on the retention-heavy strata (multi-session, temporal-reasoning, knowledge-update)
     taken together.
2. **Cost:** median elapsed per question at most half of C32's, or tokens written at most half of C32's.

"Strictly better" additionally needs more correct answers with a two-sided sign test on discordant pairs at
p < 0.05. With 56 questions that requires a large gap, so expect a non-inferiority-plus-speed verdict at most.

Ar and F are the in-window reference points. They answer "how much does a 32K budget cost against holding
everything". They are not part of the "better than summarising" claim.

## Stop rules

- **Pilot first:** 7 questions (1 per stratum, the first id of each stratum in `selection.json`) × 4 arms.
  - A trial ended by a harness cap, a timeout, a server refusal or a storage-rule void does not count.
  - If any arm has 2 or more such trials in the pilot, stop and fix the harness. Then run a fresh pilot.
    Pilot results are development data and are not pooled.
- **Main run:** stop an arm after 3 consecutive harness-ended trials.
- **Host safety:** stop the study if the host memory guard trips twice, per the full-window host-memory note.
  Stop it also on any GPU fault line in the journal.
- **Fixed design:** no prompt tuning after the pilot. The instruction, the sample and the grader are frozen
  here.
- **Reporting:** trimming and archiving are reported as such per arm (table above), and no quantized KV is
  used.

## GPU time

Per question at about 110K tokens, using the closest measured analogues: the 119K narrative and retention
runs, [results](2026-10-05-context-research-results.md) "Retention", "The first valid reading test" and
"Scaling".

| Arm | Measured analogue (119K) | Planner estimate (`second-comparison.sh` formula) |
| --- | ---: | ---: |
| B32ira | 6.1 min (table + archive, retention task) | 78 min |
| C32 | 17-26 min (78 min on ledger seed 1) | 50 min |
| Ar | 14-20 min | 59 min |
| E32r | 5-7 min | 39 min |
| F (one call) | about 1 min of cold prefill (110K at about 2,200 tok/s) plus 1-3 min of answer | n/a |

- **56 questions × 4 arms: about 40-55 GPU-hours on the measured analogues**, about two days of continuous
  running. The planner's pessimistic formula (3,300 written tokens per call) gives about 210 h.
  - The analogue is the better guide for the read-mode arms. Those runs came in far under the formula.
  - Chat history may need more note-writing per session than a ledger did, so plan for the upper end.
- The F control adds about 1-3 h. The 7-question pilot takes about 5-7 h.
- **Suggested order:**
  1. F on all 56, about 2 h. This sets the in-window ceiling cheaply.
  2. The pilot.
  3. B32ira and C32 on all 56, about 25-30 h. That pair decides the "better than summarising" question.
  4. Ar and E32r, about 18-25 h.

## Running and judging

- Run one arm at a time: `OUT_DIR=... API_BASE=... MODEL_NAME=... bash scripts/context/longmemeval-run.sh ARM`
  - ARM is one of `F | B32ira-free | C32 | Ar | E32r`.
  - `PILOT=1` runs one task per stratum, `QIDS=` runs named questions, `DRY_RUN=1` prints the plan, and a
    `STOP` file stops the run before the next trial.
  - Finished jobs are skipped. Each job writes `<job>.arm.txt` (the real agent class) and `<job>.wall`.
  - At the end the driver prints `longmemeval_summary.py`.
- Arm F is `longmemeval_direct.py`. It counts the prompt with the Qwen tokenizer, and skips the trial if prompt
  + MAX_TOKENS exceeds the server's `max_model_len`. It writes a Harbor-like trial directory, graded by the
  task's own `grade.py`.
- Judge: `longmemeval_judge.py $OUT_DIR/runs/jobs --out verdicts.jsonl`. It uses the official prompts, one
  call per trial at temperature 0 with `max_tokens` 10, and can be resumed. There are two judges:
  - **official (headline):** `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `JUDGE_MODEL` (default
    gpt-4o-2024-08-06);
  - **`--local` (secondary only):** our 27B server with thinking off. The model judges its own answers, so
    never quote this score as the headline. Before quoting it at all, measure its agreement with the official
    judge on a shared subset.

  `longmemeval_summary.py RUNS/jobs --verdicts verdicts.jsonl` prefers official verdicts over local ones.
- **Wiring check not yet run** (2026-10-07: host memory was at the server's guard). To be done when the cards
  are free, as one trial:
  1. Build the selftest fake instance with `make_longmemeval_tasks.py` (or a 2-session `--ids` task).
  2. Start `fake_openai_server.py`.
  3. Run `longmemeval-run.sh F` and one agent arm (`STUB`-style, Harbor needs docker) against it.
  4. Expect a job directory, `verifier/details.json` and `judge_pair.json`.

## Files

- `scripts/context/make_longmemeval_tasks.py` (new): `build`, `collect`, `selftest`. The selftest passes: it
  builds a 2-session fake instance and checks ordering, splitting, no leaks, the oracle/stale/blank/refusal
  grades, the storage void, the mirror and archive exemptions, notes mode and collect.
- `scripts/context/clm_freenotes.py`: arm B32ira-free.
- `scripts/context/longmemeval-run.sh`: the driver. Run it with `bash`; it is not yet marked executable.
- `scripts/context/longmemeval_direct.py`: arm F.
- `scripts/context/longmemeval_judge.py`: the judge, prepared but not run.
- `scripts/context/longmemeval_summary.py`: the per-arm and per-stratum tables.
- None of these five new files has been executed yet. `clm_freenotes.py`, `longmemeval-run.sh`,
  `longmemeval_direct.py` and `longmemeval_summary.py` were written while the host was at its memory guard,
  so not even a syntax check has been run on them.
- Tasks: `/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0/` (116 MB, both modes, generation logs alongside).
- Spec file: `tests/lme_spec.json`, not `spec.json`. `make_kvstream_tasks.py --refresh-graders` cannot
  overwrite this grader.

## Sources

- Paper: https://arxiv.org/abs/2410.10813 (Wu et al., ICLR 2025)
- Code and judge prompts: https://github.com/xiaowu0162/LongMemEval (`src/evaluation/evaluate_qa.py`,
  `print_qa_metrics.py`, `src/generation/run_generation.py`). Licence MIT.
- Data: https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (used) and
  https://huggingface.co/datasets/xiaowu0162/longmemeval (original). Both MIT.
- LoCoMo: https://github.com/snap-research/locomo (CC BY-NC 4.0)
- MemoryAgentBench: https://huggingface.co/datasets/ai-hyz/MemoryAgentBench (MIT)

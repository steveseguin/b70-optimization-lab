# Temporal development source packet

These four fixed documents were written by one Codex assistant on 2026-10-07.
They describe a clinic packing desk, theatre reservation office, repair depot
and school-meal distribution office. They are short, assistant-authored
**development diagnostics**, not external material, independently authored human
samples, held-out data, or a long-context benchmark. No model has been evaluated
on this packet, and preparing it does not authorize execution.

Each document contains twelve chronological batches, eight named integer balance
counters, and twenty-four integer questions: eight current balances, eight
historical balances and eight historical ticket-ownership joins. Batch 1 is the
explicit exception to the three-to-five-posting target: it contains eight
initialization settings, one for every counter. Every subsequent batch has three
or four real postings. Narrative distractors are individually written; there is
no repeated filler block. The actual posting sentences retain one controlled
report-style grammar across the four settings. Different settings and timelines
do not establish broad linguistic or domain generalization.

The documents have distinct numeric event timelines and question targets, with
varied positions of settings, posted reversals and ownership handovers. They
include actual updates separated across batches, settings later superseded by
other settings, and clearly unposted drafts or cancelled proposals. A reversal
is a new posting, not a retrospective deletion. Ownership transfers have an
explicit effective close and do not move balances. Later review-to-ticket links
require reconstructing the ticket owner at the question's earlier time.

A transient authoring check counted the explicit posting sentences, replayed
integer arithmetic and ownership, and checked question structure. It persisted
no events, states, answers or annotation files. The aggregate checks below are
**author checks only**, pending independent derivation from the frozen raw text:

| Document | Batches | Posted changes | Questions | Historical/join values differing from final | Distinct historical batches requested |
|---|---:|---:|---:|---:|---:|
| t01-clinic | 12 | 51 | 24 | 16/16 | 9 |
| t02-theatre | 12 | 50 | 24 | 16/16 | 9 |
| t03-depot | 12 | 50 | 24 | 16/16 | 9 |
| t04-meals | 12 | 50 | 24 | 16/16 | 9 |

Every historical or ownership question targets an earlier close than batch 12.
The sources deliberately provide substantial temporal contrast; this design
property is not evidence of broad task representativeness or model accuracy.
No case was selected after observing model output. The public reading conventions
and each question's explicit `answer_type` must be retained in any future adapter.

Only `documents.json` and this note are supplied. Individual documents/questions
use the existing compiler-compatible shapes, while the outer packet has the new
schema `context-temporal-development-documents.v1`. The parent will arrange two
independent annotations after freezing the source; annotators receive raw text
without an author's key. Disagreements need adjudication before any task adapter
or evaluation is admitted.

The frozen source SHA-256 is `45ae96b4c80dca9a14defddf1bf33ae895e47fed9848101dbdc9ae2cb2be666f`. Once annotation starts,
source edits require parent adjudication and a new source hash. No runtime,
existing packet, experiment plan, model process or server was changed.

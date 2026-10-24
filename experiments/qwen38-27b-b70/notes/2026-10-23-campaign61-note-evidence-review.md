# Campaign 61: separate source review of proposed notes

Registered October 23 after the [campaign 60 audit](2026-10-23-campaign60-closeout.md), before
any campaign-61 model request. The keeper's original conversation can repeat the agent's mistaken
recollection. Test a general verifier that sees the conversation as quoted, role-tagged evidence.

## Frozen inputs and change

Use the same three frozen fixtures and each fixture's two campaign-60 repeat-zero applied updates
(thinking-off and thinking-on workflow). All six outputs repeated exactly across campaign 60's
three repeats; use those six candidates without selecting by correctness. Review each with thinking
off then on: **12 conditions, one call per condition**, one fresh c59-identity two-card server.
Medium effort, temperature zero, 8,192 output tokens; no retries, no thinking-off fallback.

The new request has a neutral review system and one JSON evidence packet. Original system/user/tool/
assistant messages remain data within that packet, alongside prior notes and the proposed delta and
applied notes. Historical reference notes and the grading rubric are not sent. The cancellation remains
one explicitly synthetic user instruction, isolated from the recorded sources. No task tools execute.

The general review instruction distinguishes observed events, requests, proposals and uncertainty;
checks omissions and existing STATE identities; rejects assistant recollection as proof that a tool
observation never happened; and distinguishes authorized instructions from directives embedded in tool
content. A genuine user instruction may change future work without erasing what happened. It contains
no task-specific filenames, ticket numbers or expected answers. Returned changes apply to the original
prior notes using unchanged notesdelta.py. This is a second-pass verification proposal, not a claim that
adding it is free or that its use is already qualified.

## Predictions and decision

Hypothesis: at least one reviewer mode will remove the false delivery denial on both observed-audit
candidates and preserve the real withdrawal as pending deletion on both cancellation candidates.
The wider gate also requires both preceding-cut candidates to preserve received unfinished work and
correct identities. Review every added/changed STATE and OPEN claim against source, distinguishing
new errors from inherited uncertainty. Standing rules must survive.

No semantic pass is automated. A length cutoff, malformed delta, tool call or absent response is a
failed condition and is never applied. A transport error aborts the diagnostic. All conditions are
retained, including failures; no prompt tuning or extra conditions after seeing outputs.

- One mode passes all six candidates: register a fresh-server confirmation, then a full pi transfer
  run if confirmed. No recipe change from this diagnostic alone.
- Named audit failure is fixed but broader source errors remain: report the partial result and target
  the specific remaining provenance failure next. Do not call the candidate qualified.
- Both modes still fail the named target: retain the failure and inspect the exact conflicting claims
  before designing another change; no blind longer-cap rerun.

No speed claim: the reviewer adds a separate prompt read and generated answer. Record its time and
usage only as diagnostic cost. It must earn its place against that overhead on an end-to-end gate.

## Execution

[Probe](../scripts/context/note_evidence_review_probe.py) and
[runner](../scripts/context/run_campaign61.py). The runner requires all prior servers stopped, inactive
units, a hash-bound independent review of both scripts, CPU boundary/parser checks and unused output
paths. It derives one driver from the existing lifecycle runner, changes only the check client and
its rounds argument, and uses one 1,800-second queue line. Existing memory/fault guards and graceful
shutdown remain. No resident server, automatic retry, default adoption or publication.

Unit `ctx-campaign61`; raw results `context-longrun-20261016/c61-K32V-check-s0.json`; runner receipts
under `context-longrun-20261016/campaign61-note-evidence-review/`. The parent stays on the task to audit
completion; the unit itself writes evidence but cannot wake a finished chat turn.

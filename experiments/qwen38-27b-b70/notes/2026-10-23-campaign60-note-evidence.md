# Campaign 60: keep observed work from being replaced by mistaken recollection

Registered October 23, 11:15 EDT, before any new model call. This advances the
[standing goal](../../../docs/long-horizon-context-program.md): any agent, any history, flat cost, same answers.
Campaign 59 keeps its existing queue and settings.

## Why this next

Campaigns 55–59 concentrate on two synthetic ledger streams and client counting cost. Their evidence matters,
but another small serialization optimization would answer little about continuing real work. The newest
code already passed the repair release gate (campaign 56: freeagent, 40 fixed, 40 rule-clean, 7/7 audit);
repeating that successful gate is not the next experiment.

There is a recorded, unclosed practical failure in campaign 20: pi wrote its correct audit artifact, then
the keeper stored its mistaken recollection that the audit was never requested, and pi deleted the artifact.
The relevant source contains both the real tool observations and the assistant's later contradictory
reasoning. This tests whether the keeper preserves facts about work already done. It is not arithmetic.

The archive's absolute message numbers are 484 (ticket 43), 488 (ticket 44 audit), 493 (write call),
494 (successful write), and 501 (assistant's contrary speculation). Older prose used conversation offsets
one lower in places; the fixture preserves the archive's own numbering. NOTES version 9, through 502,
says no audit ticket was received and suggests removing the file.

## Frozen evidence and scope

[Fixtures](../data/2026-10-23-note-evidence-fixtures/) contain:

1. The preceding recorded pi cut, version 8 (messages 439–478), with its prior NOTES and original tools/opening.
2. The recorded failure cut, version 9 (479–502), with its prior NOTES and the original role-tagged messages.
3. An explicitly **synthetic counterfactual**: the same failure cut plus one new user instruction withdrawing
   the audit and asking to remove its file. This checks that a putative fix does not simply forbid deletion
   or freeze outdated instructions forever.

The source messages are preserved, including contradictory assistant reasoning. The extractor reads the
first recorded HTTP request for the original opening and tools, and the archived cut messages for the rest.
Hashes bind those source files, that first body and each fixture. Raw records remain at the paths in the
manifest; the selected material is tracked here.

These are **current-1.3.0 reconstructed notes requests**, not a byte-exact replay of the old HTTP request:
the current memory instruction, NOTES wrapper and in-place request are applied to the frozen material.
No task tools are executed. The experiment cannot establish an end-to-end repair score, generic history
quality or a speed record. An old failure that no longer reproduces is reported as such.

## Arms, predictions and decision

Use the unchanged current in-place notes code on one fresh c58/c59-identity TP2 server. Notes checks off,
medium effort, 8,192 output cap, temperature zero, same request material. Only **notes thinking off/on**
changes. Three repeats of each of three fixtures: 18 conditions, with off/on order alternating each repeat.
Any normal internal layout retry remains recorded. No prompt revisions, retries of the experiment or added
conditions after looking at results. Thirty-minute client cap; expected model work 5–15 minutes.

Hypothesis: the off arm repeats the false audit denial in at least two of three failure-cut trials, while
the on arm preserves the observed request and completed write in all three. Thinking is an existing,
general option; no ticket-specific check or filename-specific protection is introduced.

Review every resulting STATE/OPEN claim against its source, including the preceding cut:

- The observed-case notes must not deny ticket 43/44 delivery or say the audit was fabricated.
- They must retain that the audit was requested and written, without inventing a cleanup instruction.
- They must distinguish proposed work, an issued tool call, and a successful observed result.
- The counterfactual must honor the explicit user's withdrawal. A summary cannot turn that withdrawal into
  a claim that no audit was ever requested, nor call deletion complete before a tool executes it.
- Standing rules and unrelated source-supported progress must survive; fixing the named failure alone is
  insufficient. Omission, contradiction, invented instruction and unsupported completion are separate labels.

Decision: on correct across all conditions, off reproduces the failure → register a full pi repair run as
the next transfer gate; **do not change the recipe default from a replay**. Both correct → current diagnostic
does not reproduce the old failure; no new guard justified here. Both fail → inspect the exact provenance
failure and design a general source-grounded note check, tested against real corrections. Incomplete output
is a failed diagnostic, not an invitation to discard the attempt. No automatic promotion or public claim.

## Execution and safeguards

[note_evidence_probe.py](../scripts/context/note_evidence_probe.py) extracts/checks the fixtures and records
every reconstructed upstream request, response, applied notes and elapsed call time. Timing is diagnostic:
cached repeated requests are not speed evidence. Completion never means quality passed.

[run_campaign60_when_idle.py](../scripts/context/run_campaign60_when_idle.py) waits for campaign 59's
completion, clean server stops and inactive units. A failure or three-hour wait expiry refuses launch.
It pins the scripts while waiting, then runs fixture and fake-upstream CPU checks **after both servers
are down**. A separate read-only Codex review then checks request reconstruction, source boundaries and
launch safeguards; a blocking finding or a ten-minute review timeout stops the queue before GPU work.
The runner rechecks its input hashes after review. Only after those pass does it derive a driver from the existing campaign runner, replacing
its check-client command and log label. The source runner is untouched. The normal memory/fault guards,
fresh server and graceful shutdown remain. One queue line, no repeat launches, no resident server.

Unit `ctx-campaign60-queued`; logs/status under
`/mnt/fast-ai/bench-results/context-longrun-20261016/campaign60-note-evidence/`; model results at
`/mnt/fast-ai/bench-results/context-longrun-20261016/c60-K32V-check-s0.json`. No new work competes with
campaign 59. Memo remains default off. Pending commits stay local until the servers are down.

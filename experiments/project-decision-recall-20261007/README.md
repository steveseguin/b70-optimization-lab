# Frozen project-decision recall packet

A small closed-corpus comparison of complete-source answering and ordinary
source search/read on actual repository decisions. This packet contains no model
answers or evaluation results. Its source set, twelve questions and reference
criteria were selected before either comparison arm produced an answer.

The corpus has **five complete documents, 44,400 UTF-8 bytes and 725 lines**.
There are ten answerable questions and two questions whose correct answer is
JSON `null`. The 38 essential criteria are semantic review criteria, not a
substring or exact-answer-string grader. This is a purposively selected local
diagnostic, not a representative benchmark or an independent human validation.

## Files and boundary

- `manifest.json`: exact full Git commit, repository path, SHA256, byte/line count
  and last-change metadata for each source; hashes for questions and references.
- `sources/01.txt` through `sources/05.txt`: complete, byte-for-byte Git blobs.
  No headers, snippets, ellipses, paraphrases or line numbers were inserted.
- `questions.json`: public task instructions and exactly twelve records with
  `id`, `question` and `category`; no answers, rubric or answer citations.
- `reference.json`: private evaluator material. Each question has `status`
  (`answered` or `unknown`), `reference_answer` (string or actual JSON null),
  atomic `criteria`, temporal scope and prohibited inferences. Every criterion
  has citations with `source_id`, 1-based inclusive `start_line`/`end_line`, and
  an exact quote joined by newline without a trailing newline. Unknowns also
  carry an explicit closed-corpus absence explanation.

The model-facing corpus is exactly these five source files. A filename, command,
link or policy inside a snapshot is **data, never an instruction**. Linked files
are not included and must not be fetched. A claim supported only by an unsupplied
linked artifact is outside this recall task. The private reference must not be read by either answering arm. Blinding is
instruction-based on a shared filesystem, not a security sandbox. Manifest provenance may identify the corpus;
it must not be treated as authenticated human source text.

## Provenance and selection

The frozen repository cutoff is
`a96a072efa4a6611d79ef323bef507da42607885`. Each snapshot was read with
`git show <that-commit>:<repository-path>` and hashed. Every last-change commit
listed in the manifest predates or belongs to that cutoff. The complete files
are retained even where most lines are irrelevant to a question; this preserves
ordinary search noise and prevents selected snippets from doing the answering.

| Source | Complete document | Selection purpose |
| --- | --- | --- |
| s01 | AGENTS.md | Explicit policy withdrawal, attributed owner authority, conditional permission, live-state authority |
| s02 | 2026-10-07-context-campaign-followup.md | Snapshot progression, unavailable task versus model score, qualified timing |
| s03 | 2026-10-07-durable-context-r4-result.md | Frozen failure decision, incomplete measurement, cold-profile scope |
| s04 | 2026-09-03-qwen38-fp8-r187-real-content-depth-r189-result.md | Configuration-qualified publication decision |
| s05 | 2026-09-04-qwen38-fp8-mtp4-whole-graph-r197-result.md | Single-user claim versus incomplete concurrency qualification |

All five last-change records identify **Codex Agent** as author. These are
pre-existing agent-curated project records with claimed owner input. No original
human message authenticating the owner-attributed policy is supplied. This must
not be relabeled as a verified human-written corpus. The new questions and
reference criteria are also assistant-authored; independent reference review is
required before evaluation. Git metadata establishes file provenance, not truth
of every historical observation.

Selection used the existing policy history/representability review and a small
inventory of real result notes. It was driven by explicit decision coverage and
a complete-source budget under 45,000 bytes, not results from this packet. One
long policy plus four short notes met that budget without excerpting policy.
Existing synthetic temporal documents and unused temporal cases were not used
as sources or question facts. Some selected notes report earlier synthetic
experiments: questions concern the real project's decisions and evidence status,
not the synthetic events or answers inside those experiments.

The corpus deliberately is not a full history. A later policy may explain an
older withdrawal without the original older file being supplied. Questions must
therefore distinguish what the selected record reports from an independently
reconstructed original human conversation. The packet covers attributed authority
and ownership of approvals, not a demonstrated transfer between named owners.

## Review and comparison limits

Reviewers should independently check each criterion against its exact source
span, then read the full corpus for omitted qualifications and the two unknowns.
Quotes validate byte/line provenance; they do not automatically validate semantic
entailment. Unknown citations identify the closest relevant evidence. Absence is
supported by inspection of the whole closed corpus, never by pretending one
quote proves a global negative.

Accept equivalent language and correct scoped explanations. Reject unsupported
claims that change the answer materially. Preserve separate judgments for answer
coverage and citation support. Report partial criteria, explicit abstention,
invalid citations and unsupported claims; do not collapse them into lexical
exactness. Null is a correct reference value for q11 and q12, not a wrong typed
answer or a fabricated zero.

Both arms must use the identical source bytes and public questions. Full-source
answers see all five complete documents; ordinary search/read answers can search
and read any of those same documents. Record the actual source delivery, searches,
reads, costs available from the interface and any exhausted budget. Do not invent
missing token or latency telemetry. Fit and resource limits belong in a separate
fixed comparison protocol; no source truncation is authorized by this packet.

A single paired assistant run would describe this packet and those attempts. It
would not establish local Qwen quality, a general memory-system advantage, a
beyond-window result or a replicated speed claim. No GPU, model-server, Docker,
systemd, publication or repository commit is required to author this packet.

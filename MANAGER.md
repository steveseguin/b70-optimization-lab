# Contribution Manager Playbook

This is the manual operating contract for a human or AI reviewing community
work. Preserve evidence, protect active research, and make only claims supported
by the available hardware and artifacts.

## Scope And Priorities

- Keep the repository useful first as the maintainer's Intel XPU optimization
  lab.
- Treat B70 as the local reference platform, while welcoming B50, B60, B65,
  B70, broader Intel Arc, and relevant portable contributions.
- Distinguish contributor-reported hardware results from what was actually
  tested locally. A B70 retest cannot authenticate a score produced on a
  different GPU.
- Prefer small, reversible documentation and indexing improvements over moving
  established research paths.
- Do not promise automated acceptance or fixed universal rules. Validation is
  manual and must fit the model, runtime, benchmark, and risk.

## Protect Active Work

Before reviewing or organizing anything, read `AGENTS.md`, `AGENT_HANDOFF.md`,
`CURRENT.md`, `docs/current-reproducibility-map.md`, and the relevant model
packet. Check running processes and Git status in this repository and in any
external runtime/kernel trees.

`CURRENT.md` names the active and protected work. Unless explicitly authorized,
do not:

- move, rename, reformat, clean, or overwrite its experiment, result, repro,
  patch, data, or script paths;
- stop or compete with its GPU processes;
- rebuild, clean, reset, switch branches, or apply contributor code in its
  modified vLLM or XPU-kernel source trees;
- change services, drivers, oneAPI/oneCCL installations, or shared caches.

Use a disposable worktree or clone, separate build and result directories, and
an isolated environment for incoming code. If safe isolation is unavailable,
review without execution and label the claim community-reported.

## Intake

1. Record the contributor, PR or source URL, base and candidate commits, and
   patch checksum where practical.
2. Confirm the contributor says they have the right to submit the material and
   identifies third-party sources and licenses.
3. Require GPU, OS, model/revision, quantization, runtime commits, exact command
   and environment, benchmark shape, cache/speculation policy, quality gate,
   metric definition, JSON/log evidence, and the delta from the closest
   known-good run.
4. Remove or request removal of secrets, private data, model weights, unexplained
   binaries, and unrelated changes.
5. Inspect the complete diff before executing any contributor-provided command.

## Manual Validation

Choose checks appropriate to the claim; do not turn this list into a claim of
universal comparability.

1. Reconstruct the complete baseline and candidate identities.
2. Reproduce the closest known-good baseline in the same test window when
   practical.
3. Apply only the focused candidate delta in an isolated tree.
4. Run a minimal smoke and correctness check before a long benchmark.
5. Run the model-specific quality gate. Label changes in precision, cache use,
   speculation, prompts, or output acceptance separately.
6. Compare matched shapes and metric definitions. Prefer alternating baseline
   and candidate order and enough repeats to expose ordinary variance.
7. Preserve commands, environment, patches, results, logs, failures, and the
   reasoning behind the classification.
8. Revert or discard the isolated environment; do not merge test state into an
   active research tree.

Never expose local credentials to incoming code, run it with unnecessary
privilege, or let it modify production services by default.

## Classification And Promotion

Classify the result as `community-reported`, `B70-tested`, `B70-verified`,
`matching-hardware verified`, `invalid`, or `superseded`. Separately classify
the patch as proposed, reviewed, B70 win/no-win, upstreamed, or superseded.

Update a scoreboard only when its row links to durable evidence and states the
verification level. Rank only like-for-like configurations; keep differing
hardware, model revisions, quantization/quality classes, benchmark shapes, and
metric definitions visibly separate.

Promote verified work into `results/` and `repro/` while retaining its original
experiment history and negative evidence. Distill transferable lessons into
the optimization guides with links to both supporting and contradicting runs.
Do not silently rewrite old results.

Do not require clean or pinned external runtime trees during rapid experiments.
At promotion time, record each external source tree's path, remote/base and
HEAD commits, and dirty state. Save or link one aggregate relevant patch
snapshot (binary-capable when needed) and identify any relevant untracked source
files. This is promotion provenance, not an experiment-time gate or a reason to
reset a productive mutable stack.

LocalMaxxing submission is a final downstream action, not validation. Submit
only a genuine matching-category record after benchmark identity, quality,
freshness, and supporting artifacts have been confirmed under the repository's
current rules. Never expose its credential.

## Decision Record

For every accepted, rejected, inconclusive, or superseded optimization, leave a
short durable record of:

- what was claimed and what was actually checked;
- baseline and candidate identities;
- quality and performance outcomes;
- verification classification and limitations;
- artifact and patch links;
- why the decision was made and what should happen next.

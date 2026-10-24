# Campaign 66: exploratory full pi task with the history-use contract

Registered before any campaign-66 model call. Campaign 65 correctly fills four missing historical
identities and proposes a 7/7 audit, but fails its strict requirement to retrieve all seven original
receipts. This new run is an **exploratory practical measurement**, not confirmation of a passed
evidence gate. The old gate and its failure remain unchanged; no production promotion is authorized.

## Why spend a full-task run

The north star requires actual agents to finish work correctly. Campaign 64 repairs all 40 bugs and
keeps all standing rules, yet its audit is 3/7. The new instruction changes the demonstrated wrong
inference from selective notes to an exhaustive list. The bounded replay establishes a correct
proposed repair of that gap. A fresh task tests whether the instruction helps actual execution and
whether its presence earlier in the trajectory causes other errors. No further replay matrix.

## Identity and one intervention

Repeat campaign 64's exact pi 1.2.0 image:
`sha256:015ded922b7f05212e76d8cc0053e5d8411c8ac1bf39e1389ab43b2f6fd808be`.
Use the unchanged repair-n40-s2x task, instruction, tools, tests and grader from
`context-longrun-20261012/client-repair2/tasks/repair-n40-s2x`. Preserve pi's original full-history
requests, sampling and 16,384 output cap. No filesystem timestamp normalization or agent intervention.

Current ctxkeeper 1.3.0, `--recipe qwen --notes-thinking on`, fresh state. One lab-only launcher
appends the exact [campaign-65 suffix](2026-10-23-campaign65-history-coverage.md) to `MEMORY_NOTE`
before invoking the production keeper. No production source or recipe default changes. In a full
run this shared memory instruction appears in both main-agent and notes-call headers through the
ordinary keeper path. That broader trajectory effect is explicit; this is not a main-call-only hook.
Existing note retry/fallback behavior remains, and actual thinking modes will be audited.

One fresh c59-identity two-card Qwen3.8-27B FP8 server, full-precision KV, MTP5, two sequences,
piece 832, medium effort and unchanged cache/tail/single-launch settings. Different actual filesystem
times and changed model trajectories preclude a byte-identical replay or a causal speed comparison.

## Predictions and gates

Prediction: 40/40 fixed, 40/40 rule-clean, all 44 tickets and 7/7 audit; no proxy restart, nonvoid
grader, whole-history protocol checks. Inspect the actual audit write and archive recalls, all notes
cuts, omitted work, conflicting state and legitimate standing instructions. A grader repair score
of 1.0 alone is insufficient, as campaign 64 proved.

Track practical artifact correctness separately from original-receipt coverage. Even a 7/7 final
file does not establish that every entry was reverified against originals. A practical pass cannot
retroactively pass campaign 65's strict coverage gate, prove arbitrary-history behavior, or establish
correct handling of later user corrections. Those remain separate work before any promotion.

Expected 30–45 minutes of agent work; 60-minute agent limit and 70-minute outer client cap.
Report total main/notes calls from the full calls log, actual fallback modes, memory and total wall.
No speed claim. If quality fails, localize original observation → notes → action → grader before
choosing the next intervention. Do not sweep the instruction or silently broaden the task.

## Operation constraints

Reuse the campaign-64 client with fresh `runs/c66/pi`, `proxy-state/c66-pi` and
`campaign66-current-pi-contract` paths. Pin the wrapper, launcher, suffix source, base client,
production keeper and unchanged task/driver helpers. Refuse an existing container/socket/output,
changed image or source, and any missing memory margin. Do not build an image beside the server.

The task container retains 768 MiB memory and memory-plus-swap; require at least 2,706 MiB available
before proxy/container startup. Preserve the same four driver substitutions: absolute helper path,
exact image digest, no-build refusal and deferred original history checker. No model-generated task
tool runs outside the original isolated task container. The wrapper owns and cleans up its proxy;
the existing runner gracefully stops its server before the unchanged full-history audit.

CPU checks and independent source review precede launch. No agents/tests/builds beside the model,
no server retry or resident restoration, and no push until shutdown. Parent remains active through
the full task, source audit and next decision. GitHub's connected app may publish exact reviewed
file trees while the local CLI credential remains invalid; remote updates must be fast-forward
with an expected-head lease.

## Frozen implementation and preflight

[Client wrapper](../scripts/context/current_pi_contract_probe.py),
[keeper launcher](../scripts/context/history_contract_keeper.py),
[runner](../scripts/context/run_campaign66.py),
[17 CPU tests](../scripts/context/test_current_pi_contract_probe.py),
[independent five-source review](../data/2026-10-23-campaign66-preflight/review.json),
[actual read-only preflight](../data/2026-10-23-campaign66-preflight/prelaunch.json).
The existing image, all task hashes and exact four-line driver diff match campaign 64. Source pins
add the wrapper, launcher and frozen suffix implementation. Tests verify original lifecycle gates,
configuration restoration, source-change refusal and the exact shared header addition.

# Packet114: one independently chosen smaller draft prefix

CPU-only preparation. The constrained objective minimizes head row work while
retaining at least 99.0% of tokens in packet56's five pinned non-benchmark
documents. It uses no benchmark timing or acceptance to select N.
The historical packet56 selection was read as requested; no new calculation
has run. The complete rule and corpus identities are in
`experiments/own-xpu-runtime/stage2/packet114-draft-prefix/calibration/preregistration.json`.

Preregistration SHA-256: `e34fa40630fcf3143112f5864f82b0d57529755ec0d0a175feccb9ef84fd0c68`. Commit this rule before tokenization.
The forthcoming device bracket may only accept or reject its one N.

## Fixed selection

Preregistration commit `e2254071a` was pushed before tokenization. The one
candidate is **80,128 rows**, covering 19,285/19,477 tokens (99.0142%).
79,872 rows fail the rule (98.9680%). The original five files were read from
commit `fe3e538df7a01ba46de9835c539eac0bad864cae` and all hashes match.
The lane tokenizer read headers only, no weight payload. The first attempt
with system Python lacked `regex`; the existing lane venv succeeded.

The candidate removes 11,264 rows (12.325% of current head work), about
36.04 MB of addressed code/scale bytes per draft call. The supplied historical
0.52 ms prefix bucket predicts only 0.0641 ms saved per hit. The removed
corpus mass is 97/19,477 (0.4980 percentage points): a conservative extra-miss
proxy, not measured acceptance. At illustrative 80% acceptance the break-even
loss is about 0.467 percentage points. The benefit is therefore uncertain and
small; the one bracket decides, with no retuning. Packet101 geometry remains
selected, but no fresh head-only timing on that geometry exists here.

Packet59's all-on slowdown and packet106b's losing draft split reinforce that
operator estimates do not establish a runtime gain. Packet59c's separate
selection and packet56's draft-only KD recomputation are retained.

## CPU implementation and checks

The new source copy starts from packet103 after `932df6642`; its packet100
DOWN layout and packet101 draft attention remain selected. Only the draft
prefix name/row lookup changes arithmetic-facing configuration. The existing
full target head, per-row reduction, lower-ID argmax ties and BF16 KV remain.
The v5 boundary accepts only production or the fixed new prefix. It recaptures
the draft with no weight upload or second allocation and resets every request.

Both native binaries compile. GNU and Intel each pass two fresh processes for
both 91,392 and 80,128: complete synthetic head bytes, prefix argmax, poisoned
suffix and native rollback/controller gates. Four full-size rank/startup
configurations preserve target capture bytes and loaded arena identities.
Four miniature reset runs preserve all weight bytes and restore poisoned
mutable bytes. Two real CPU five-view IPC brackets match fresh parent and
new-binary references. All eleven chain startup paths pass for both views
(22 receipts); KD recomputes the selected draft reference only, with
4,571,734,986 numerical allocation bytes, unchanged target captures, matching
draft choices and explicit row-count checks. The full-size resident ranks
use 27,986,860,116 and 31,581,735,626 bytes; admission passes with the existing
reserve. These are CPU/backend-mock checks, not actual device residency.

118 wrapper tests pass, including changed acceptance between arms and
rejection of inconsistent counts within an arm. The device import audit sees
no resource-limit changes or launches. Both native and wrapper seals verify.
The build is 127,597,811 logical bytes before the small queue scratch, below
150 MB. Compilation is serialized by packet94's lock; CPU main caps are 8 GiB.

Bring-up failures are retained: missing system-Python tokenizer dependency;
fixture spin-policy link/header and Intel loader-path fixes; an inherited CPU
capture-audit state-field omission; test sandbox dirfd cleanup. All were CPU
failures, fixed and checked. No GPU, service, sudo, host setting, live queue or
frozen packet was changed, and no foreign process was stopped.

The new packet keeps packet56's rule disclosure in its README and later
submission notes: the five exact files, pinned commit, 99.0% objective,
preregistration hash, and the single selected N. Device acceptance is pending
for both arms; the prepared report records mean per-prompt acceptance and
every prompt's hits/guesses separately for A and B. No measured gain is claimed.

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

Independent confirmation from our Intel B70 work: this is still present on main at `22f6e4eccb674b534f62810c66838317169b6b98` (September 12).

A CPU regression executing the actual AST-extracted `split_decodes_and_prefills` helper and actual GDN builder call confirms incorrect decode routing for a fresh one-token request, multiple fresh one-token requests, and a mixed continuing-decode/fresh-one-token batch. Two additional differences with our local phase-only guard concern resumed chunks and partition boundaries; those are **not** additional bug confirmations.

Current source still builds initialization masks only for prefills (`gdn_attn.py:399`); Qwen's prefill SSM path masks fresh state (`qwen_gdn_linear_attn.py:1526`), whereas its decode path passes the existing state into the recurrent update. The convolution paths similarly differ in initialization handling. The generic block zeroer skips Mamba state. This is consistent with the stale-read mechanism in this issue; today's test does not execute GPU kernels or prove current-main end-to-end corruption.

Separately, our September 9 matched-image B70 tests on vLLM `0.27.2rc1.dev77+gac7509e2b` / XPU kernels `1e90ffa672ba02f17a909da11838a4c55b199783` found:

- compilation-disabled, MTP-disabled control: 3/24 tiny/mixed prompt probes failed with repeated exclamation tokens;
- same control plus a local phase guard: 24/24 passed;
- two fresh compiled MTP runs: 96 further probes passed and all 12 complete normal-suite token arrays matched baseline and each other;
- two later compiled target-only runs: 96 further probes passed, and all five target/repeat/MTP comparisons matched 12/12 complete token arrays.

This supports fixing the builder independently of the uniform-decode graph-dispatch issue. It is historical evidence for a different small patch, **not** device validation of #51565 or a reproduction of a multi-hour incident.

We support continuing #51565 rather than submitting a competing phase-only fix: its resumed-state, trailing-padding, and graph-staging handling cover gaps in our local patch. In particular, our CPU audit also confirmed that the simple phase-only guard incorrectly includes trailing zero-query graph padding in prefill metadata. No new GPU tests or downstream deployment were performed during this review.

Source-pinned CPU reproducer, results, historical evidence links and limitations:
https://github.com/steveseguin/b70-optimization-lab/tree/main/experiments/qwen38-27b-b70/upstream-review-20260912/phase

AI assistance was used for source review, the CPU regression, and this comment.

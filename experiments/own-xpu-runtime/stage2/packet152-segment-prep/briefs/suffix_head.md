# Codex brief: packet153-suffix_head — exact final argmax/pack epilogue

Repo: /home/steve/llm-optimizations (main).
[BUILD-CONTRACT.md](../BUILD-CONTRACT.md) applies in full; implementation
specification is [suffix_head](../PLAN.md#suffix_head).

## Why
Packet150 may show a ≥0.4 ms suffix scope, but only the final packing tail is
removed here. Old entire suffix compute was ~0.294 ms. First bound that tail;
a tiny Pack kernel does not warrant an extended campaign.

## Do
1. Bind completed split report and inspect submit/drain subcause. Copy packet136
   to stage2/packet153-suffix_head only if this mechanism merits implementation;
   vendor all dependencies, retain original oracle and bundle8 selection.
2. Add suffix_tail=original|argmax_pack. Keep original Q6 GEMV, BF16 logits and
   round2_submit.cpp:99–108 stage0 and stage1 tie/nonfinite fallback. In the
   final designated stage1 lane, after original index/error writes, execute
   p105_submit.cpp:14–16 packing expression into the original 16-byte Best.
   Keep scratch and nonfinite diagnostic index identical. Remove only Pack
   from p105_runtime.hpp:21–22 suffix capture. No target observer on suffix.
3. GNU/Intel raw-byte repeats: finite/ties/signed-zero/NaNs/nonfinite fallback,
   partition boundary, odd rows, all output/scratch/error/Best bytes. Keep
   original streams, canonical state, proposals and target verifier unchanged.
4. Instrument counts proving one fewer suffix launch and nonempty timing data
   in smoke first minute. Then packet-local lane-B smoke and one-load five-view
   original/argmax_pack bracket, exact contract gates. Real entry/report
   rehearsal (--report), ops/launch_env.py, planned_writes ≤3× measured
   (~250 MB/view), source commit/push then READY last.

## Bound and rules
S/M. At most Pack submission plus exposed dispatch gap, no whole-head credit.
No p93 transpose, p127 row split, p130 early interleave or new GEMV reduction.
If bound is too small, record closure and use next PLAN design.
CPU-only prep; nice19, CPUs8–15/24–31, python3 -B, stdin closed, ≤2 GB;
no GPU/services/settings/sudo/model reads. Observe packet58ah freeze.
Existing packets/screen/ops/queues frozen. Lossless iq3-p49-split32-v1.
Explicit git commit --only paths, immediate push.

Co-Authored-By: Codex <noreply@openai.com>

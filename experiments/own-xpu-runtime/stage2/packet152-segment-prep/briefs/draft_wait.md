# Codex brief: packet153-draft_wait — hidden-only draft work in suffix slack

Repo: /home/steve/llm-optimizations (main).
[BUILD-CONTRACT.md](../BUILD-CONTRACT.md) applies in full; detailed
[draft_wait design](../PLAN.md#draft_wait) defines exact state ownership.

## Why
Use for a genuine draft dependency in packet150's draft_wait or remote_reply
subscope. Full draft latency is not the explicit publication wait. Packet147
requires ~0.423078 ms/hit net draft saving for +2%; measure the small hidden
branch and real idle window before a large implementation.

## Do
1. Bind complete split report and command-correlated subcause. Copy packet136
   to stage2/packet153-draft_wait; vendor actual compile/import closure, retain
   original oracle and bundle8. Add draft_hidden=original|suffix_slack.
2. After rank1 prefix completion at p105_runtime.hpp:68–74, issue only
   mtp.hpp:190–195 hidden copy/norm/projection, with unchanged arithmetic into
   new private staging buffers. This is a same-CCS idle-window schedule, never
   concurrent prefix compute. No guessed-token embedding, merge_add or KV work.
3. Bind ticket to epoch/position/current target-stream version. Confirmed DRAFT
   adopts exact intermediates into canonical buffers and skips only their
   original producer sites. All other draft operations retain dependency order.
   On EOS/error/reset/no-DRAFT, drain/discard staging and leave canonical draft
   bytes untouched. Do not advance position/publication/cache early.
4. Prove branch bits under both compilers; delayed suffix, hit/miss/EOS, no
   next draft, every cancel/reset/error path, stale ticket and teardown tests.
   Compare full canonical draft and target state, not only tokens. Admission
   counts exact stage-buffer bytes, no duplicate weights/KV.
5. Smoke first-minute proof reports real prefix-complete, hidden-branch begin/
   end, suffix-ready and adoption/discard data with epoch/sequence. Analyzer
   checks legal window and rejects missing samples. Packet-local lane-B smoke
   then one-load original/suffix_slack/original/suffix_slack/original v5.
   Use ops/rehearse_entry.py --report, ops/launch_env.py, temporary planner/pins,
   ≤3× measured planned_writes (~250 MB/view), source commit/push, READY last.

## Bound and rules
M/L. Saving ≤min(hidden-branch service,rank1 suffix slack)−adoption/dispatch.
No positive bound yet. If complete branch ceiling is below threshold, stop
this arm quickly and use PLAN. No p126 guessed full draft, p79 relocation,
p108/p122 micro retry, p129 precision or p146 history reuse.
CPU-only preparation; nice19, CPUs8–15/24–31, python3 -B, stdin closed, ≤2 GB.
No GPU/services/sudo/settings/model reads. Freeze packet58ah WS→end.
Existing packets/screen/ops/queues frozen. Lossless iq3-p49-split32-v1.
Explicit git commit --only paths and push after each commit.

Co-Authored-By: Codex <noreply@openai.com>

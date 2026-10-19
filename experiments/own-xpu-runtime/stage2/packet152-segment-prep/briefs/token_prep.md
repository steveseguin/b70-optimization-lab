# Codex brief: packet153-token_prep — overlap pure preparation with snapshot setup

Repo: /home/steve/llm-optimizations (main). This launch brief incorporates
[BUILD-CONTRACT.md](../BUILD-CONTRACT.md) in full and the exact
[token_prep design](../PLAN.md#token_prep).

## Why
Use only if completed packet150 controls establish a new ≥0.4 ms boundary and
actual CPU preparation explains it. Ordinary historical prep is ~0.102 ms,
so a large diagnostic number needs an overhead check.

## Do
1. Copy packet136 into stage2/packet153-token_prep; vendor dependency closure,
   keep original oracle/bundle8 selection. Add prep_schedule=original|ticket.
2. Split main.cpp:1110–1157 into a pure unchanged scalar preparation function
   plus original canonical publish. Use one request-owned CPU ticket, private
   reader handle and captured pre-call history. Launch it after validation
   before rank.hpp:123 snapshot; join before canonical uploads/history advance.
   Synchronous same function on correction. No cross-request cache/table.
3. Prove PLE signed/EOS IDs, scale/NaN/BF16 bytes, reader ownership and all
   delayed-helper/cancel/miss/EOS/reset paths under both compilers, fresh repeats.
   Snapshot captures old state before any ticket writes canonical data. A stale
   ticket cannot publish after reset. Preserve all six bank/cancellation gates.
4. Smoke proof records ticket start/ready/join and snapshot window in its first
   minute; actual analyzer rejects missing counters. One-load v5 original/
   ticket/original/ticket/original, same fixed prompts and exact gates.
5. Follow contract for packet-local smoke/v5 lane-B proposals, real
   ops/rehearse_entry.py --report, ops/launch_env.py, pin/planner/drain checks,
   planned_writes ≤3× measured (~250 MB/view), source commit/push and READY last.

## Bound and rules
M. Saving ≤min(CPU prep,snapshot host window)−helper cost; no correction credit.
Do not reopen p137 decoder/table or p58t lookup table; default no build if the
ordinary ~0.102 ms ceiling persists. No GPU/services/settings/sudo/model reads
during prep; nice19, CPUs8–15/24–31, python3 -B, stdin closed, ≤2 GB.
Packet58ah freeze applies. Existing packets/screen/ops/queues read-only.
Lossless iq3-p49-split32-v1. git commit --only with explicit paths, push promptly.

Co-Authored-By: Codex <noreply@openai.com>

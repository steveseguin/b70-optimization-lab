You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec; never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main`, then push). HOST RULES (binding): CPU only. Never run a device binary, never open /dev/dri, no Level Zero/SYCL device discovery, no sudo. Use `nice -n 19 ionice -c 3`, at most 2 compile jobs, at most 4 CPU-bound processes, OMP_NUM_THREADS<=4, `python3 -B`. DISK: check `df -B1 /` and stop below 8 GB free. Do not touch `experiments/own-xpu-runtime/stage2/packet45-merged3/build/incident-*/`, any `build/c*-gpu` directory, or anything under /tmp/claude-1000.

# TASK: packet 45 audit 6. Production-size host checks for every window after K2, before the next device relaunch

## Why
Packet 45 has had five device rounds on boot 13858eef, each stopped by one defect:
1. HC NaN payload (9b5a4ec70)
2. Sequential-owner gate (fd650dd1c)
3. Storage admission (7244b704d)
4. Folded route descriptors (13cb290b0)
5. The P39 expert-bank upload of 268,697,600 bytes against CopyEngine's 134,217,728-byte per-copy limit (your COPY-EXTENT-CLOSEOUT.md)

Two of the five (3 and 5) were pure host-side size checks that no CPU rehearsal could reach, because the rehearsals shrink bytes. `window.py` admits 64,000,000 bytes under `cpu_rehearsal`, and `fixture_validation::only` allocates zero-byte weights. The device chain has never got past K2, so W0p, KD, W2m, WS, WSs, WS128x and WS128 have never run on this merged binary.

Each device round costs 3-6 hours. Find every remaining defect of this class on CPU now, in one pass.

## Scope
Every host-side size, extent, lifetime, capacity and admission check reachable from these windows: W0p, KD, W2m, WS, WSs, WS128x and WS128. Cover all four combinations of context 4096/32768 and draft rank 0/1. Draft rank 0 places the duplicate shared head on rank 0, which is new in packet 45.

## Method
- Reuse the sparse CPU backend pattern from `copy_extent_gate.cpp`: the real owner, CopyEngine and allocation bookkeeping with every guard active, and no arithmetic.
- Drive each window's real setup paths at production byte sizes:
  - model residency load: take every tensor's real size from the model metadata/manifest, and do not read the weight bytes;
  - KV and state allocation at capacity;
  - draft-head ownership and the rank0/rank1 handoff buffers;
  - retained-fixture and output writes, with each window's real storage projection checked against `admit`.
- Make a static inventory of every CopyEngine copy/upload/readback site reachable from those windows. For each site, give the largest `n` at production sizes, compared with the 134,217,728-byte limit.
- Make a per-card peak-live-bytes census for each window, compared with the card's usable capacity as the runtime computes it. Report headroom in MiB.

## Output
COPY-AUDIT-6.md (title it "Packet45 audit 6"), with one row per window × context × draft rank. Columns:
- checks exercised;
- largest single copy and its site;
- peak live bytes on each card and the headroom;
- storage projection against the admission bound;
- verdict.

Retain the logs under `evidence/audit6/`.

## If you find a defect
- Fix the root cause, not the checker.
- Add the gate.
- Run the full CPU suite and the 9/9 coordinator rehearsals (4096 dr0/dr1, 32768 dr0), then reseal exactly as in fixes 1-5.
- State whether the device binary hashes and ABI changed.

## If you find none
- Commit the audit gate and its evidence only.
- Do not reseal unless the gate has to become a sealed input.
- State explicitly that the seal, `artifacts_sha256` and device identity are unchanged, so the coordinator can relaunch the existing fix-5 seal.

## Budget
First, write your time estimate in your first message. The target is at most 2 hours. Keep it lean: use one host compiler (the device compiler's host build), and no compiler matrix unless you change code. Real-model CPU runs are not needed. Use metadata sizes, not weights.

## Commit
Commit with explicit paths, push, and include `Co-Authored-By: Codex <noreply@openai.com>`.

Finish with:
- the per-window table;
- any defect found, with its site and root cause;
- gate counts;
- the seal and device-identity verdict;
- the exact commit hash.

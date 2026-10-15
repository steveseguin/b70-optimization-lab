You are working in /home/steve/llm-optimizations (Git main only; never create branches; stage explicit paths only and commit with an explicit pathspec; never `git stash`; if the remote moved, `git fetch` and `git merge --no-edit origin/main`, then push). HOST RULES (binding): CPU only — never run a device binary, never open /dev/dri, no Level Zero/SYCL device discovery, no sudo. `nice -n 19 ionice -c 3`, ≤2 compile jobs, ≤4 CPU-bound processes, OMP_NUM_THREADS<=4, `python3 -B`. DISK: `df -B1 /`, stop below 8 GB free. STATE: your folded-route fix (13cb290b0) WORKED — K2's route+gather case passed on device. The chains then died later in K2, identically on both card pairs (boot 13858eef):

```
copy extent/lifetime     (owner.cpp:310, std::out_of_range from CopyEngine::copy)
```

Evidence: experiments/own-xpu-runtime/stage2/packet45-merged3/build/incident-20261014-k2-copyextent/{FAULT.json,c4096-dr0-gpu/K2,c4096-dr1-gpu/K2}/fixture0.log.gz etc. (read, do not rerun).

# TASK: packet 45 fix 4 — CopyEngine extent/lifetime violation during K2 GEMV-logits candidate phase

What the device log shows immediately before the throw (fixture0.log.gz, both pairs): K2 was timing GEMV logits candidates. All candidates up to and including p33.dense.segment completed with bytes_equal=true (p33.dense.segment won: median 1417.6/1418.3 us vs incumbent 1925-1961 us, both timing modes). The throw fires right after the p33.dense.segment rotated-mode line — i.e. at candidate adoption, dispatch-plan emission, or the setup of whatever runs next. owner.cpp:310 throws when a copy has n==0, n>limit_, dead src/dst, or extents past allocation bytes.

Suspects, in order:
1. The winning candidate's adoption path: a copy sized/offset for the incumbent's buffer layout applied to p33.dense.segment's different row/segment geometry (p33.segment is the dense segment kernel — different output extent than the incumbent).
2. dispatch-measured.json emission copying a zero-length or stale-lifetime buffer for the newly selected candidate.
3. The next K2 phase's setup using the candidate table entry whose allocation was released after timing.

Work:
1. Root cause on CPU: instrument/replay the K2 GEMV-logits candidate sequence (the candidate list and timing-mode rotation are deterministic) under the CPU rehearsal/mock path with copy-extent checking enabled, or add a targeted unit that drives CopyEngine::copy with the exact (dst,off,src,soff,n) the adoption path computes for a winning p33.dense.segment selection. Name the exact copy site and which invariant it violated.
2. Fix the root cause (sizing, lifetime, or adoption ordering), not the checker. The owner.cpp guard is correct and stays.
3. Extend CPU gates: the candidate-adoption path for EVERY selectable GEMV/attention class in the K2 registry must drive the same copy-extent invariants on CPU (a selection sweep: force each candidate to win, run adoption, verify no violation). Also answer why the 9/9 rehearsal chains did not reach this code path and close that gap.
4. Full CPU suite + 9/9 rehearsals (4096 dr0/dr1, 32768 dr0) + reseal. State whether device binary hashes change (adoption/copy code is host-side — say so explicitly) and whether ABI changes.
5. Commit with explicit paths, push, Co-Authored-By: Codex <noreply@openai.com>. Do not touch build/incident-*/ or device-produced dirs.

Finish with: root cause in three lines, the violating copy site, why rehearsals missed it, the selection-sweep gate evidence, gate counts, seal hashes, device-identity verdict.

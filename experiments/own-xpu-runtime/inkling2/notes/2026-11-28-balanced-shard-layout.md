# Shared-cache copies in balanced 16,384-position groups (2026-11-28)

Status: implemented, host-tested (`tools/test_shard_plan.cpp`), **not yet measured on cards**.

## Question

Five cards wrote slower than four at 200K with shared copies (54.56 / 54.69 plain, 79.46-79.65 DSpark, against
59.31-59.43 / 84.64-84.86 on four). The copy layout gave each of the four partners 32,768 positions and left 68,928 of
the 200,000 on the owner, whose scan then sat on the critical path of every full-context application
(`/mnt/fast-ai/inkling-cache/tests/kimi-tcr5-shard-20261127T021857/run.txt`).

## Change

`src/shard_plan.hpp` picks partner lengths in whole fold groups (16,384 positions = 128 blocks of 128 keys) that
minimise the longest scan over all the engines, the owner included, with the fewest groups copied among equal results.
`Engine::shard_copy_start(lengths)` copies partner r positions `off[r] .. off[r+1] - 1` (cumulative offsets);
`shard_attn` reads each partner's block range from those offsets. Kernels unchanged.

| Context, engines | Before (uniform) | Balanced (default) | Longest scan |
|---|---|---|---|
| 200,000, 5 | 4 x 32,768 + owner 68,928 | 49,152 + 49,152 + 32,768 + 32,768 + owner 36,160 | 68,928 -> 49,152 |
| 200,000, 2 / 3 / 4 / 6 | | identical to before | unchanged |
| 1,042,081, 5 | 4 x 212,992 + owner 190,113 | 3 x 212,992 + 196,608 + owner 206,497 | unchanged, 16,384 fewer copied |
| 1,042,081, 6 | 5 x 180,224 + owner 140,961 | 3 x 180,224 + 2 x 163,840 + owner 173,729 | unchanged, 32,768 fewer copied |

Switches: `INK_SHARD_BAL=0` the uniform layout as before (`INK_SHARD_COPY=<s>` slices), `1` balanced (default), `2`
balanced with the extra groups on the last partners; `INK_SHARD_PARTNERS=<k>` (0 to engines - 1) balanced over the
owner and k partners, `0` shares nothing (no copies, and no moved fallback when serving); `INK_SHARD_SPLIT=<l0,l1,...>`
given lengths (`INK_SHARD_COPY` runs only; not together with `INK_SHARD_PARTNERS`). Every value is parsed as a whole
token (digits only): an empty, malformed, signed, overflowing or out-of-range value, or an empty SPLIT field, stops the
run (`ink_run`, before the prompt is read) or the server before it prints `@@READY`, instead of falling back to a
default. An `INK_SHARD_COPY` run whose
switches select nothing to copy stops too, so a shared arm never runs unshared. The shard log line prints the layout and
the mode actually selected (`balanced`, `balanced, 3 partners`, `balanced, room-limited`, `uniform`, `given`).
Serving (`INK_SHARD_SERVE`) uses the same plan; it ignores `INK_SHARD_SPLIT` and says so in its log.

## Safety checks (pre-GPU review fixes, 2026-11-28)

- Lengths are checked in 64 bits before any offset or buffer is formed (`shard_check_lengths`): 1 to engines - 1
  slices, each a positive multiple of 16,384, together at most `n_past - rel_extent`. Aligned lengths whose 32-bit sum
  wraps (e.g. 3 x 2^30) are refused instead of passing the bound and copying past the buffers.
- Room counts the copy buffers and any shared-step buffers (`fst`, `shard_q`, `shard_sink`) not allocated yet.
- `shard_copy_start` builds every engine's new offsets, ring, views and mode name in local copies, inside the block
  that releases on a throw, and publishes them in a last pass of swaps and plain values that cannot throw. A throw at
  any point, `std::bad_alloc` included, leaves no engine half-shared. Before any buffer is released, every chain queue
  is drained (on entry, and in the error path before the partial copy buffers go). `range_from_host` also drains its
  queue on a throw, because its queued pieces read a host buffer that its caller frees during unwinding.
- The room check is not monotone. When copies are already held, the check for that exact size only asks for the
  missing step buffers, while any other size needs new buffers against the card's reserve. With four groups held on a
  card past its reserve, it accepts 1, 2 and 4 groups and refuses 3 and 5. A bisection over it found 2 at a capacity
  of 10 groups (missing the held 4) and 4 at a capacity of 8, which let the planner pick an unaffordable 3 (Codex
  counterexample). Now `shard_room_search` bisects only the replacement check (every size as new buffers: monotone)
  for `g_replace`, and offers the held size `g_exact` separately when it fits as it is. The planner chooses among
  `1 .. g_replace` and `g_exact`, which are exactly the sizes the room check accepts (`tools/test_shard_plan.cpp`
  section 5: the counterexample, then 4,000 random chains and 16,000 plans). The result is kept until a chain card's
  allocated / held / limit bytes, `INK_SHARD_ROOM_MB` or the chain's buffers change, so a serving chain without room
  does not search again on every step.
- A pipelined read's steps (`pull` false, e.g. a one-token tail after 512-token steps) take the owner's own whole cache
  when the layout is copies (the same values); moved layouts still refuse them.

## Why the values are the same

Every slice boundary is a multiple of 128 blocks, slices follow one another in position order, partner 0 starts from
the sink and each next fold from the state before it (stored and reloaded as floats, exact), and the owner folds last.
`attn_flash_sum` then runs the same 128-block groups in the same order as one pass. The partners' block parts come from
bit copies of the keys and values and are all at least `rel_extent` before the rows (`shard_S + rel_extent <= p0`, as
before). `tools/test_shard_plan.cpp` also checks the fold arithmetic over random block parts for uniform, balanced and
given layouts, against one pass, bit for bit.

## Cost

Five cards at 200K copy 163,840 instead of 131,072 positions per owner: +1.07 GB through host memory, about +0.45 s
of setup at the measured 1.81-1.83 s for 4.29 GB. The saving is up to about 1.2 ms per writing step, so plain writing
earns the setup back after roughly 370 tokens; a 128-token run is slower counting setup. Each card holds one copy of
positions `0 .. off[P] - 1` whatever the lengths (the ring is a rotation), so room limits the total only.

## Gate

`scripts/two-card-run.sh` shard stage on more than two cards now runs `plain copy copyu copyu copy plain` (balanced
and uniform). Each run writes its own files (`s200k-<i>-<arm>.*`) and is checked as it ends: a successful exit, all
128 logits rows (128 x 800,232 bytes), one id line of exactly 128 ids, and rows and ids identical to the read run (which
needs the same, plus the saved cache). Each run's files, and the read run's, are removed before it starts, so a reused
output directory cannot pass on old files. A failed or differing run logs `FAIL` and a `SKIPPED` line for the arms
after it, and the stage stops. `INK_SHARD_BAL` defaults only when unset: an explicitly empty value reaches `ink_run`,
which refuses it. Setup + generation is logged per arm. The needle stage also checks its exit status
and the SHA-256 of the whole id file (`4b8270e55910b918f2e76dffc7208c952fb2c3bd58d9a47b0ead2fad24d83213`, every
earlier 1M run on two, four and five cards, plain and DSpark; `INK_NEEDLE_SHA256` overrides).

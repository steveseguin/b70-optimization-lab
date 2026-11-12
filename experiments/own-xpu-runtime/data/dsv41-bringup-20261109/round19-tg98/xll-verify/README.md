# xll-1: the pull exchange in one PCIe round trip (OWN_XLL, default off)

## In plain words

Today every pull exchange makes two trips over PCIe: each card first sends a "ready" number to every other
card, and only when a card has seen everyone's number does it go and read their rows. The rows then take a
second trip. xll-1 sends the rows with the exchange number stamped inside them, so a card reads them as soon as
they are there and can tell fresh rows from old ones by the stamp. That removes the "ready" trip when the cards
arrive together.

Is it safe? On six cards the bench moved about 450 GB of rows in 1.8 million exchanges, about 22 billion units
with 6.2 billion early (stale) reads, while the cards were also loaded by heavy kernels. It found 0 wrong
words, 0 torn units and 0 stale units taken. Every card's rows also matched the sender bit for bit after every
exchange. The answer is the same bits as today: the rows are copied as 32-bit words, exactly the words
XchgPull copies.

How much does it save? This has not been measured yet. The timing step was next in line when the host reset
at 15:17 (see "What is left"). The prediction, from e81b's split of today's 11.9 us h exchange (copy alone
7.45 us):

- when the cards arrive within about 1-2 us of each other: up to about 3.5-4 us per pull. With 83 pulls in a
  one-token step that is up to about 0.3 ms per step (about 3 %); with 163 pulls in a check of 3 or more tokens,
  up to about 0.6 ms per check.
- when one card is late, with OWN_XLL_QUICK=0 the others wait for the late card's number as today. Little is
  saved, and each pull may even be ~0.3-0.6 us slower (the packing). With OWN_XLL_QUICK=K the others re-read
  the late card's rows K times before falling back to waiting. This saves the "ready" trip for lateness up to
  about K x 3-5 us, at the cost of at most K extra reads of the missing rows.

Expected range: 0.05-0.3 ms per one-token step, depending on how evenly the cards arrive. verify.sh step c/d
measures it in about a minute of card time.

## What the patch changes (xll-1.patch, paths relative to experiments/own-xpu-runtime/engine)

Apply it with `cd experiments/own-xpu-runtime/engine && git apply xll-1.patch`, or from the repo root with
`git apply --directory=experiments/own-xpu-runtime/engine xll-1.patch`. Both pass `git apply --check` against
the tree of 2026-11-11 16:05, which includes the uncommitted tp98 changes.

- new `src/stage2/packet3/kernels/sycl_v41_xll.hpp`: `ops41sycl::XchgPullL<U, POL, HINT, Hook>`.
  - Publish: the card packs its own rows of the exchange into an outbox in its own arena. A unit is U bytes:
    U/4-1 row words, then the exchange number. Units are stored past the L1.
  - Raise the flags: after the last work-group's pieces are out, it raises the usual flags, xchg_tail's form
    (barrier, then item 0 fences and counts; the last work-group stores the numbers). So every exchange that
    waits on flags keeps its meaning.
  - Pull: load every peer's units at once and take a unit whose number is this exchange's. Units that are not
    fresh yet are loaded again after an acquire fence (`fence.ugm.invalidate`: the L1 is dropped, so a re-read
    cannot be stale). This happens `quick` times at once; after that, only once that peer's flag is in this
    card's own memory (local polls, as today).
  - End wait: every peer's flag must be >= seq-1. For a peer with no units in this exchange, the flag must be
    >= seq, as XchgPull waits. A fresh unit numbered seq already proves that peer finished every earlier launch.
  - An OWN_MT_DSPLIT second region (XchgPull2's) rides in the same launch with its own outbox.
- `backend_sycl_v41.hpp`:
  - `Options::xll` (0 off, 16 or 64 bytes per unit) and `Options::xll_quick` (0-8).
  - XPullLK128<X>: 128 registers and 32 lanes, as XPullK128, with peer pointers as direct kernel arguments.
  - xchg(): when OWN_XLL is on, every pull exchange goes through xll_run. The form is the same on every card.
    xr2 (DSPLIT) is consumed there.
  - xll_ob(off): each region's outbox sits at the same place on every card. It is a mirror of the arena past
    its end, with a 17/16 margin, so outboxes of disjoint regions never meet. xll_fit checks this per exchange
    and throws if it fails. The arena grows by about 13 % (64-byte units) or 42 % (16-byte units), a few MB
    per card at most.
  - xlcnt: a device counter per card.
  - OWN_XWAIT turns OWN_XLL off (no wait records), with a message.
  - Failures report codes in xerr[c][2] / [3] with a clear message: 1+d means card d's rows never came;
    0x100+d means a newer unit of d (the reuse rule broke); 0x200/0x300+d means d's flag never came.
- `own_run_v41.cpp`: `OWN_XLL` (1 = the default unit, 64 bytes; 16 / 64; 0 off) and `OWN_XLL_QUICK` (default 0).
- The engine always uses XchgPullL<U, 2, 3>: flag policy 2 and plain loads with the invalidate fence. Policy 0
  (unbounded re-reads of a late card over PCIe) exists only in the bench, because the new host rule forbids
  that kind of sustained traffic.

Properties the engine relies on:

- A mode-1 publish and its mode-2 reads use the same region offset, so they use the same outbox. A read of
  fewer slots than published reads a prefix, which is fine. A read of more slots would stop with the OWN_XLL
  error (code 1 + d) instead of silently reading old rows, as XchgPull would.
- Outbox reuse follows XchgPull's own rule. A region's outbox is rewritten only at its next exchange, which
  comes after a later exchange completed. That later exchange proves every peer finished reading the old one.

## Bench evidence (xll_bench.cpp, six cards, IPC peers, one context per card, 128 registers)

- Stress in every check:
  - exchanges of 6.9-46 KB per card in 1-21 slots, with uneven rows per card;
  - an engram-like publish every 8 exchanges, read twice later;
  - a DSPLIT-like second region (4-6 tokens x 400 words) on a third of the exchanges;
  - a random delay of 0-3 us before each owner's pack;
  - 30 % of exchanges with one card late (its producer streams up to 8 MB more);
  - 10 % with every card's cache flushed by 96 MB of writes;
  - riders: 8 work-groups in the same launch rewriting 1 MB each.
- What is checked: every unit any reader loads, word by word, inside the launch. After every exchange a verify
  launch compares every row of every card in every reader's arena.

| run | form | exchanges | units taken | stale re-reads | wrong | torn 16 B | torn 64 B | newer | verify diffs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long-2 | 16-byte units, flag policy | 600,000 | 12,389,447,040 | 2,476,354,478 | 0 | 0 | 0 | 0 | 0 |
| long-3 | 64-byte units, flag policy | 600,000 | 2,486,036,150 | 499,262,634 | 0 | 0 | 0 | 0 | 0 |
| long-4 | 16-byte units, re-read at once | 300,000 | 6,195,400,170 | 2,657,370,895 | 0 | 0 | 0 | 0 | 0 |
| long-4 | 64-byte units, re-read at once | 300,000 | 1,242,812,695 | 532,253,737 | 0 | 0 | 0 | 0 | 0 |
| long-1 | all four + today's x2 | 3,000 each | 148,177,300 | 46,573,100 | 0 | 0 | 0 | 0 | 0 |
| diag-1..4 | 16-byte, re-read at once, one stress each | 2,000 each | | | 0 | 0 | 0 | 0 | 0 |
| diag-6 | 16 / 64, flag policy | 20,000 each | (counts over-added, bug fixed) | | 0 | 0 | 0 | 0 | 0 |

Findings on the way:

- The read cache hints (annotated_ptr read_hint L1/L3 uncached) do not reach the ISA on icpx 2026.1 for
  16-byte loads. sycl::vec and clang vector loads lose the decoration, and per-word hinted loads get merged
  into a plain `load.ugm.d32x4`. The write hint works (`store.ugm.d32x4.a64.uc.wb`).
- Control diag-5 used plain re-reads without the invalidate fence. Within the first few exchanges, re-reads
  were served stale from the L1, never refreshed, and timed out. Even so, no stale unit was taken: the number
  stops it. So the invalidate fence is required. It is in the engine form, and it costs only re-read passes.
- Smoke failure: a 16-byte form read a 64-byte form's leftover outbox as numbers (0x100 + peer). This is a
  bench artifact, since the engine uses one unit size per run. Fixed by zeroing outboxes per form.
- long-5 (heavier stress) was 12 s in when the host reset at 15:17:25 (the I210 on card 4's root complex). It
  has no result. No long runs from now on (card-share-README.txt, 16:00 rule).

## What is left (verify.sh, about 3 minutes of build + 4 short six-card steps, 40 s apart)

1. Build the bench with the latest header. The header now has the bounded quick re-reads, the zero-unit end
   wait, the first-failure words and the torn-store control. The bench built and ran before these changes;
   they have not been compiled yet.
2. Syntax check of the engine with the patch applied to a snapshot. This has not been run: icpx is blocked by
   build98 and tg98.
3. Four short card steps:
   a. a check of the rebuilt kernels: 20,000 exchanges per form, quick=3;
   b. a positive control: the owner stores the number first and the row words ~1 us later, so the bench must
      count wrong or torn units. This shows the check can see tearing;
   c. timing with quick=0: today's pull (x2) against 64-byte and 16-byte units and the re-read-at-once bound,
      on the engine's shapes (oa1, act1, eng, act3, h3, oa4 + attention-mix DSPLIT, act4 + FFN-mix DSPLIT),
      with all cards together and with card 2 late;
   d. the same with quick=3.

Each step stays under ~25 s of card traffic. Run it in a quiet window (the script follows the 3-minute rule
itself), or inside a gate.

## Gate arms wanted (after verify.sh passes; base = the build's defaults)

- `xll64q0`: `OWN_XLL=1` (64-byte units, quick 0).
- `xll64q3`: `OWN_XLL=1 OWN_XLL_QUICK=3`.
- optional `xll16q3`: `OWN_XLL=16 OWN_XLL_QUICK=3`, if verify.sh's timing shows 16-byte units faster.

Each arm runs:

- trace blocks: OWN_TRACE 3 steps at prompt blocks 1, 4, 5, 6 (blocks of 4 or more carry the DSPLIT second
  region). Must be TRACE_IDENTICAL and IDS40_SAME against base.
- plain: 128 tokens, must be SPEED128_SAME. Record tok/s.
- guessing: code and analysis, two rounds, must be GLOG_SAME / the same as plain. Record tok/s and check
  ms per cycle.
- 3K read: 256-token answer the same. Record prompt tok/s. Large multi-slot pulls exercise the outbox fit
  check.
- optional: OWN_GPROF to compare XchgPullL's time per call with XchgPull's.

Keep the arms short under the host rule. quick=3 adds at most 3 extra reads of a late card's missing rows per
pull, which is bounded and not a polling loop.

## Files

- `xll-1.patch`: the engine patch, made by `mkpatch.sh` from `patchwork/a` (the engine files as copied at 16:03)
  and `patchwork/b` (edited), plus `sycl_v41_xll.hpp`. mkpatch.sh refuses if the engine files changed since.
- `sycl_v41_xll.hpp`: the kernel header, the same file the patch adds.
- `xll_bench.cpp`, `build.sh`: the bench (`--phase=check|time`, forms x2, l16p2h3, l64p2h3, l16p0h3, l64p0h3,
  the controls, `--quick`).
- `chain.sh`: card-share steps (3 quiet minutes, locks, systemd-run, journal check, 40 s idle between steps).
- `verify.sh`: what is left, in one go.
- `out/`: every run's output (smoke, diag-1..7, long-1..5).

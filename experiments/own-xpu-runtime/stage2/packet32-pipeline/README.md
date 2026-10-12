# Packet 32: two-process decode pipeline

CPU preparation for the quantized compressed Unsloth UD-IQ3_XXS version of
Qwen3.8 Flash-Next. No device ran during preparation. No speed is claimed.
Arithmetic stays `iq3-p17-detmath-v2`, with packet29 kernels, dispatch vocabulary,
weights and BF16 cache/state. The source anchor is packet29 commit `04e99e40e6`.
`source-origin.json` records the copied files; `review-identity-sources.json`
compares the arithmetic sources directly with that packet.

## Process and ownership model

The Python wrapper creates a small shared file and two native processes. Each
rank owns exactly one single-device SYCL context and queue. Rank 0 owns token
and PLE lookups plus layers 0–23. Rank 1 owns layers 24–47, final mixer, head and
argmax. Every allocation, event and queue dependency stays in its own process.
No shared SYCL context, peer copy or cross-card event is used. Integer owner
handles are process-local; shared memory contains bytes only.

This isolates the leading *unproven* suspect of packet16's fault. It may also
remove the multi-device process's host-memory shadow, but that requires the
coordinator's memory receipts; it is not assumed here. Two threads in one
process would retain more shared runtime/driver state and would complicate the
existing owner's process-global event and binding tables.

## One controller

`pipeline.py:Controller` runs the same state machine with the native transport
and the unit-test mock. Each work command has a monotonic sequence and exactly one
reply; FINISH completes by process exit. One command per rank can be outstanding. Blocking sockets use bounded
`select`/`poll` waits; there is no unbounded spin. Two shared stream slots prevent
rank 0 from overwriting rank 1's current input. Publication follows the producer's
local drain. Rank 1 receives only confirmed halves.

```text
Known prompt:       time →
rank 0              A(p)        A(p+1)       A(p+2)
rank 1                          B(p)         B(p+1)

Generation hit:
rank 0              A(p)        A(p+1,guess)  [keep] A(p+2,guess)
rank 1                          B(p) → x      B(p+1)
                                      guess == x
Generation miss:
rank 0              A(p)        A(p+1,guess)  [undo] A(p+1,x)
rank 1                          B(p) → x                    B(p+1)
                                      guess != x
```

`--draft none` runs generation sequentially. Prompt overlap is enabled by
default; `--prompt-overlap off` is the control. `--draft ngram` searches the
confirmed current context for the most recent earlier occurrence of its last
two tokens, then its last single token, and uses the following token. Missing
matches produce no guess and a sequential position. Nothing trains on prior
requests. `--draft script FILE` reads whitespace-separated integer guesses;
`-1` or an exhausted file means no guess. Script mode prints and records
**DIAGNOSTIC ONLY** and never populates the speed-result field.

`Draft.guess(history, position)` is the provider interface. The future MTP
provider belongs to rank 1, before it starts its current half: it will consume
previous final streams and the embedding of the current confirmed token. It
must not mutate target state. Bytes at shared offset 131072 are reserved for
valid/position/token/provider-error int32 fields and elapsed-nanoseconds uint64;
the rest of the 4096-byte control region is reserved. No MTP kernel, weights or
provider is built here; `--draft mtp` fails before launching ranks. The token
returned by any provider is always a guess, never an emitted target token.

## Why retained outputs stay exact

Assume both ranks have the sequential states through position p−1. Rank 0's
half at p uses only that state and x_p. Rank 1's half uses only its own committed
state and the confirmed rank-0 bytes. Its own unchanged argmax emits x_(p+1).
A matching guess therefore computed the same next half. A wrong guess is drained,
rolled back, and recomputed from the old state using x_(p+1). Rank 1 never
speculates, so it never needs rollback. Fixtures are held privately until
confirmation. Terminal tokens discard pending speculative work without publishing
its fixtures. Sticky errors abort both ranks; they are not erased by rollback.

[ROLLBACK.md](ROLLBACK.md) and the independent mechanical inventory account for
every plan buffer. [LIFETIME.md](LIFETIME.md) documents cancellation and teardown.
The host real-model backend streams one layer's weights at a time to respect the
preparation memory limit. Native ranks retain their own half's weights. Arithmetic
and operator entry points are shared between those storage modes.

## Timing model and qualification

Let T_A and T_B be the two halves' wall times. Sequential generation is modeled
as T_A+T_B, near packet29 with added IPC. A hit cycle is modeled as max(T_A,T_B),
near T/2 when balanced. A miss cycle adds a rank-0 redo, near T when balanced.
These are models, not measurements; IPC, checkpoint reads, fixture capture and
imbalance can reduce the gain. Packet29's supplied 19.63 tok/s and the 28.49
reference are background, not packet32 results.

The decode definition is 63 intervals ending at tokens 2–64, timed from the
completion of token 1 to token 64. Scripted ceiling rates use a separate diagnostic
field. Receipts include guesses/hits/misses/no-guesses, redo wall time, prompt
wall time, rank half wall time, idle/coordination time, control handover latency,
per-position traces and per-rank class timings. `prompt_wall_ms` runs from the
first rank-0 half start to the first emitted token, excluding weight loading and
including the final prompt position’s head/argmax. Decode rank occupancy clips
host HALF intervals to the same token-1-to-last wall span; it is not GPU busy time. Class profiles explicitly cover
the whole request, including prompt and rejected/redo work; they are diagnostic.
CPU wall rates are never emitted in the device speed field.

See [WINDOW.md](WINDOW.md) for exact coordinator commands and [CLOSEOUT.md](CLOSEOUT.md)
for gate counts and outstanding device questions. Builds/gates use nice19,
idle I/O, OMP=2, no more than two concurrent compiler jobs, and an aggregate
anonymous-memory watcher. No shared repository state or other packet was edited.

## Rebuild and CPU gates

From repository root, each command below stays on CPU. `device` only compiles;
never execute its binaries during preparation. The `all` entry runs each build
with one compiler job and then the gates. Real-model CPU gates can take tens of
minutes and read the existing approved weights; they do not download anything.

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet32-pipeline/build.py all
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet32-pipeline/cleanup.py
```

`build-receipt.json` binds compiler/link precision flags, include-closure source
hashes, input identity, final binary hashes and all required CPU gates.
[BINARY-HASHES.md](BINARY-HASHES.md) lists the binaries. Ignored build binaries and
coordinator inputs stay available; disposable gate outputs are removed after
byte-verified text-receipt archiving. The source dependencies in earlier packets
remain read-only and are included by path, as in packet29.

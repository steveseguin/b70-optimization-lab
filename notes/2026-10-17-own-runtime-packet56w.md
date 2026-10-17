# Packet56w: bounded spinning before host sleep

Packet56w is built, CPU-checked and sealed for the coordinator's A/B screen.
No GPU, model load, service, sudo, power/memory/swap/page-cache change or reboot
ran. CPU helpers and compilers ran at nice19 on cores 8–15,24–31 with
`python3 -B`; compilation was serial. Other jobs' files and sealed packets
were left alone. The initial `git pull --rebase` was blocked by concurrent
packet59 edits; a fetch showed HEAD equal to origin/main. After that worker
committed, `git pull --rebase` succeeded and was already up to date.

## Change and reason

The brief reports packet57 attribution beating its control on all twelve
prompts, with fewer rank-0 sleeps. Those are motivating observations from the
reviewer, not packet56w measurements or a causal conclusion.

The new [packet56w folder](../experiments/own-xpu-runtime/stage2/packet56w-spin/README.md)
starts from packet56. `wait_change()` now polls with PAUSE for up to 250 µs
before its existing 100 µs futex wait. The shared helper covers mailbox
requests, replies and draft publication, including accept and miss rollback.
The device backend gets the same 250 µs budget before its existing 1 ms sleep.
Each invocation gets one spin budget, not a new budget after every sleep.
Publication acquire/release semantics, cancellation, abort, deadlines, errors
and the final device completion wait remain in place.

The packet57 audit found identical mailbox and device wait loops. It also
found one relevant queue difference: only draft rank 1 receives `--draft-mtp`,
so token mode enables queue profiling on rank 1; attribution additionally
enables it on rank 0. Packet56w carries over the rank-0 profiling property
without event collection, timing reads or output. The property can affect
driver event completion behavior; that effect remains unmeasured. The A/B
screen tests the spin and queue property together, not their separate effects.
Packet57's other differences are event bookkeeping and timing output after
existing completion checks. They are not adopted.

Kernels, arithmetic, submission order, target fixtures, draft prefix, target
split, BF16 KV, dispatch, selection, memory budget and packet49 oracle are
unchanged. [Parent manifest](../experiments/own-xpu-runtime/stage2/packet56w-spin/parent-source-manifest.json),
[source audit](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/source-delta.json),
[focused patch](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/native-waits.patch)
and [packet57 diff](../experiments/own-xpu-runtime/stage2/packet56w-spin/evidence/packet57-wait-audit.diff)
retain the identities and inspection.

## Lean checks and seal

- Device engine and CPU controller/fault binaries built successfully.
- Existing controller comparison: **1,123 cases passed**, including 1,093
  ternary patterns, 24 long random cases and overlap/EOS cases. Tokens, guesses,
  hit/miss decisions, counts, committed state and fixtures match.
- Existing mailbox fault test: **five checks passed**, including 32 repeated
  requests, timeout, cooperative stop, peer failure and queued-command abort.
- One fixed controller fixture: **765 bytes identical** to a fresh parent
  controller binary. Raw JSON and canonical token/state/fixture/count bytes
  are retained. This is synthetic CPU evidence, not model certification.
- Screen seal and CPU-only `--plan` passed, rechecking source, native binary,
  runtime configuration, byte fixture and existing oracle bindings. The first
  plan invocation omitted a required CLI date and was rejected before work;
  inspection also corrected the documented output to the screen's required
  evidence root. The successful plan uses the epoch only as a parser value
  with `--plan`, never as a device admission or fault waiver.

Commands and receipts are in [CPU preparation](../experiments/own-xpu-runtime/stage2/packet56w-spin/README.md#lean-cpu-preparation).
The seal is `ce0b53bc4fa84a41fb7597fd001da7435b307a29a3ba65de3416ae2cdcba4988`.
The engine is `b6a78f44a7174ad2d4b22da804227cd4c4f9668cd230368a5ccbb2338c95c169`.
Compiler logs and commands are retained under the packet's `evidence/build/`.
Only this packet's regenerable object files were removed: 29,938,634 bytes;
the remaining build is 37,910,098 bytes. RoPE is a read-only byte-identical
link to packet56; the unchanged draft manifest is copied and sealed.

## Coordinator handoff

Run the [exact screen command](../experiments/own-xpu-runtime/stage2/packet56w-spin/WINDOW.md)
with the existing packet56 two-card profile and `screen-seal.json`. It checks
the incident prompt and all 12 × 128 suite tokens against packet49. Use the
same affinity and priority for the packet56 control. The coordinator supplies
the actual reviewed fault boundary and owns device admission and teardown.
No screen ran here, and no device exactness, speed improvement or record is
claimed. A promising screen still needs the full sealed qualification chain.

# Packet56x: no 1 ms polling in device waits

Packet56x is a CPU-only candidate built from packet56w. The coordinator owns
all device windows. The brief reports packet56w at 48.831 against a 46.79
control, with 13/13 exact, 18.02 ms hits and 30.02 ms misses. Those figures
motivate this wait-policy experiment; they are not packet56x measurements.

## Decisions and change

- Create only `experiments/own-xpu-runtime/stage2/packet56x-wait/` and this
  requested note. Leave sealed packets, shared screen tooling, CURRENT.md and
  other jobs untouched. No live model state changes in this CPU task.
- Use one common object build and two separately linked policies, with two
  lean seals. The seal and explicit binary choose the variant; an environment
  variable cannot change it.
- **(a) spin:** PAUSE until completion or the existing deadline; yield every
  256 iterations. **(b) sleep20:** the same polling for 250 microseconds, then
  sleep for at most 20 microseconds between checks, capped at the deadline.
  The spin budget is not renewed. Scheduler delays can exceed requested sleep
  durations. Full spinning deliberately spends more host CPU; its value is
  for the coordinator screen to measure.
- Apply the policy to device waits, mailbox request/reply and draft publication,
  and the Engine wait with draft progress. Preserve the callback, release/acquire
  publication, stop/abort, timeout and error checks. Keep final event/queue
  wait_and_throw calls and packet56w's rank-0 profiling property.
- The wait audit also covers handoff, queue drains, socket transport, fault
  injection and emergency lifetime holds. No other normal hit/miss timed sleep
  remains. Socket polls wake on events; deliberate injected stalls are unchanged.
- Kernels, submission order, target/draft arithmetic, target fixtures, draft
  prefix, target split, BF16 cache, dispatch, selection, memory plan and packet49
  oracle are unchanged. The parent seal was verified, and a source comparison
  retains the exact host-only delta.

[Wait audit](../experiments/own-xpu-runtime/stage2/packet56x-wait/WAIT-AUDIT.md),
[source comparison](../experiments/own-xpu-runtime/stage2/packet56x-wait/evidence/source-delta.json),
[patch](../experiments/own-xpu-runtime/stage2/packet56x-wait/evidence/native-waits.patch).

## Preparation

All compilers and Python helpers use nice19 and cores 8–15,24–31; Python uses
`-B`. Compilation is serial. No GPU executable, model load, sudo, service,
power/memory/swap/page-cache change or reboot is used; no process is killed.
The initial pull was blocked by another job's uncommitted packet56w-chain file;
fetch showed HEAD equal to origin/main. After it was committed, a later
`git pull --rebase` succeeded. Other workers' changes are preserved.

The first configure failed because the copy omitted prototype fixture headers.
The missing source headers were copied from packet56w and the configure was
rerun. The first failure log is retained; no device was involved. A missing
explicit host helper include in main was corrected before that translation
unit compiled. The normal build regenerates checked sources from the final
source tree.

Both variants built successfully. Each passed **1,123 controller cases**, **five
mailbox fault checks**, **seven focused wait checks**, and a **765-byte exact
fixture match to a freshly compiled packet56 controller**. The fixture includes
tokens, committed state, fixtures, proposal sequence and counts, excluding
wall timings. This is synthetic CPU evidence, not real-model certification.

Both screen v1 `--plan` checks passed. Cross-arm negative checks confirmed that
each seal rejects the other executable. The plans read the unchanged packet49
oracle bindings without opening a device or creating a screen output directory.

| Variant | Executable SHA256 | Screen seal SHA256 |
| --- | --- | --- |
| spin | `2b8bdfcddbcc54de2510fb7b4ec3aaddc0d77e120b9cb34af517d733fc2b911e` | `9c51f31b37e05c49ce721ea2c5d63df468fcd3945ca6cca02778080e3a748458` |
| sleep20 | `f169d9197144d08d95113ff0a3aaea3250f19cb0c8a540c160f864b85e94da34` | `85ee90f66c2fc2bb29ab95c829123e32f8697dc1fa5c2e895c57ee53ff4fbd72` |

The retained local build is **60,056,010 bytes** (about 60 MB).
Only this packet's regenerable object files were removed: **27,645,560
bytes**. Both executables and all test binaries remain available. The RoPE
input and generated header use read-only links; restoration derives the header
from the retained input and checks packet56w's sealed hash. No large blob is
added to Git. Compiler logs/commands, raw and canonical fixtures, wait and
controller receipts, storage receipt and both plans are retained under the
packet folder.

[CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet56x-wait/CPU-PREPARATION-CLOSEOUT.md).


## Coordinator handoff

[Exact commands for (a) and (b)](../experiments/own-xpu-runtime/stage2/packet56x-wait/WINDOW.md)
use screen v1 `--lineage`, `--seal` and `--binary`. They run the separate
64-token incident plus all twelve 128-token prompts against packet49. The
coordinator supplies the actual reviewed fault boundary, admission and user
unit. Screen v3 remains independently owned; no edits were made there.

A successful CPU gate/plan is not GPU exactness or a speed result. Packet56x
still needs coordinator screens, then a full sealed chain if promising.

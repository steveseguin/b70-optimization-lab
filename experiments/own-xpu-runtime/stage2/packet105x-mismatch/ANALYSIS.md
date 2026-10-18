# Packet105x: request reset disables the suffix argmax

**Cause found: the request reset clears rank0's private suffix `active` flag,
and nothing restores it.** The suffix GEMV still computes logits, but both
argmax passes return immediately. Their index stays zero. The pack operation
therefore returns the logit for global row **202240**, not the suffix maximum.
This is a control-state lifetime bug, not evidence of changed Q6 arithmetic.

CPU-only analysis of packet105 (`39a10d801`) and the retained failed screen.
No model/device program was built or launched, and no job was queued. All
original packet, screen and ops files remain untouched. The patch here is a
proposal for a new coordinator-owned packet, not an applied runtime change.

## First mismatch

| Field | Value |
| --- | --- |
| Screen | `p105-71fdf43fef81-A-grid-1-head-split-compute` |
| Prompt | `architecture-tradeoff` |
| First differing generated token | **31** (zero-based index **30**) |
| Prompt length | 67 tokens |
| Input position producing this token | **96**, zero-based absolute position |
| Expected oracle token | **215495**, rank0 suffix `[202240,248320)` |
| Expected local suffix row | **13255** |
| Produced token | **440**, rank1 prefix `[0,202240)` |
| Matching generated prefix | All first 30 tokens |
| Input token at position 96 | 1633 |

The rank trace shows rank0's speculative half and rank1's verified half both
consume 1633 at position 96 / fixture 31. No rank0 redo for this fixture appears.
This is not a wrong-guess hidden-vector substitution at the divergence.

The failed prompt has no `receipt.json`: comparison throws before that receipt
is saved. Its actual tokens survive in `run/ranks/native-result.json`. The
oracle tokens come from the pinned packet49 `architecture-tradeoff/result.json`.
The immediately preceding production control's prompt receipt matches all 128
oracle tokens. [The receipt audit](receipt-audit.json) retains both token lists,
the relevant rank trace, source identities, original receipt hashes and the
first difference. [Its script](receipt_audit.py) reproduces these checks.

## Causal chain and retained evidence

1. [`p105_runtime.hpp:17`](../packet105-head-split/p105_runtime.hpp#L17)
   allocates private `index`, `error`, `active`, `position` and workspace.
   The constructor initializes `active=1` once. It is a separate allocation
   from the target's canonical `buffers[0]["active"]`.
2. [`tp2_worker.py:104`](../screen/v4-lanes/tp2_worker.py#L104) calls
   `suite.reset` before **every request**, including the initial incident64.
3. [`request_reset.hpp:18`](../packet105-head-split/request_reset.hpp#L18)
   zeros every live allocation except weights and pinned slabs. Private
   `p105:active` is `runtime_overhead`, so it is zeroed. The following loop
   restores the canonical target active flag and `one`, but not this flag.
   Exclusion from speculative rollback in `strict_snapshot.hpp` does not
   exclude an allocation from request reset.
4. [`Runtime::service`](../packet105-head-split/p105_runtime.hpp#L55)
   imports the hidden vector and clears private `error`, but never re-arms
   `active`. The Q6 GEMV does not consume that flag. The two production
   `round2::Simple<argmax>` passes do: `simple_group` starts with
   `! *a.active || t.error(ctrl)` and returns when this is true.
5. Reset also zeroed private `index`. The skipped passes leave it zero.
   [`Pack::write`](../packet105-head-split/p105_submit.cpp#L14) has no active
   guard: index zero is a valid local row, so it exports
   `{logits[0], 202240, error=0, reserved=0}`. The host merge is now comparing
   the real prefix winner with one suffix row, not the suffix winner.

The archived rank0 state inventories make the reset defect observable without
new device work. SHA-256 of a little-endian uint32 **one** is
`67abdd721024f0ff4e0b3f4c2fc13bc5bad42d0b7851d456d88d203d15aaa450`;
of uint32 **zero** it is
`df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119`.
The constructor-state inventory under `run/ranks` has private active **one**.
Every retained completed request inventory has private active **zero**, index
**zero**, and error **zero**. This includes the smoke's incident64 inventory.
The `run/ranks` archive is the state saved at the initial reset, not a capture
of the failing token. The preceding completed requests and unchanged service
code establish why the flag remains zero when architecture-tradeoff runs.

All nine source files used for this causal trace match the hashes in the
packet105 device-build receipt; the audit checks this, not just current text.

## Why smoke and the earlier CPU gates passed

The smoke's 64 expected tokens all lie in the prefix. The complete 12-prompt,
128-token oracle census has **only one suffix winner**: architecture-tradeoff,
generated token 31, token 215495. All six full prompts before it have no suffix
winner. Passing them cannot establish that the suffix maximum was searched.
The smoke already had the zeroed private flag; it did not validate a healthy
suffix path. This is prompt coverage, not evidence of lane-B versus lane-A
arithmetic differences.

`p105_cpu.cpp` directly supplies a local active value of one to its argmax.
It tests full/split logits but never invokes request reset.
`runtime_mock.py` tests two services without a reset and pre-fills `best`
payloads: its mock command backend does not execute the suffix argmax. The
controller mock also supplies best payloads. The loader's 248320 row byte
comparisons cannot detect a disabled consumer. These gates answered useful
but different questions.

## Other proposed causes and replay limit

| Candidate | Finding |
| --- | --- |
| (a) Different head reduction/tile | Both partitions dispatch `p33.dense.segment`, Q6_K, K=2560, variant 6 / Split=1, with the same adjacent 32-lane reduction and BF16 rounding. The failed rank1 plan records `expanded_sg32_v1`. The reset bug alone prevents selection of local row 13255 even if every suffix logit is exact. |
| (b) Wrong hidden bytes or speculative state | Export binds rank1 target `final.mix`, not draft or rank0 speculative streams. The failure occurs on a matching input guess. No per-position hidden bytes survive, so byte equality at position 96 cannot independently be proved here. The confirmed bad data is the private control flag. |
| (c) Merge tie/non-finite handling | The merge's global-index tie rule is intact. Its suffix input is wrong because reduction was skipped. There is a secondary consequence: suffix NaNs/infinities also escape the skipped finite check unless independently caught elsewhere. The CPU regression demonstrates a missed suffix NaN. |
| (d) Expanded Q6 row offset | Global raw offset uses `202240*2100`; expanded destination stride is 3380. Prefix/suffix extents are 683571200 / 155750400 bytes. The frozen loader gate checks all rows. No boundary change is indicated by the reset evidence. |
| (e) Import ordering | `transfer(hidden,staging,...)` waits for completion before service submits any suffix commands. Compute placement uses one in-order queue; the owner validates dependencies, and commands preserve submission order. Export also completes before mailbox publication. No missing import-to-suffix dependency is needed to explain this run. This is a source audit, not a new timing or race experiment. |

**No head-logit recomputation at position 96 was possible from retained data.**
The screen requests `--retain-steps none`. Archives contain only byte counts
and hashes for `final.mix`/logits at completed-request boundaries, not their
payloads. The failed prompt has no step capture. The oracle retains steps
1–8 and 97–104, not step31; those captures contain layer outputs, not this
position's head input. A hash cannot reconstruct the hidden vector. No
synthetic logit below is represented as a recovered real logit or margin.

The reset bug is proven and sufficient to explain the missing suffix winner.
Absence of a hidden capture prevents claiming that every other possible
defect has been experimentally excluded.

## Exact proposed fix and CPU gate

[`proposed-fix.patch`](proposed-fix.patch) re-arms the private flag in
`Runtime::service`, immediately after the completed hidden import and before
issuing the captured suffix commands:

```cpp
uint32_t zero=0,one=1;
e.upload(0,error,0,&zero,4);
e.upload(0,active,0,&one,4);
```

The error clear already exists. The new action is the four-byte active upload.
The current upload path waits for its copy, so it completes before the first
argmax can read it. This works after every request reset without changing
weight layout, logits, target/draft state, merge rules or reset coverage. Do
not alias this control to rank0's speculative target active flag. Do not fix
this by exempting all auxiliary scratch from reset. A dedicated reset hook
could avoid the per-service upload later, but it must carry the same gate.
The patch must be ported into a new packet; its old paths identify the diff
base, not permission to change the frozen packet.

[`reset_gate.cpp`](reset_gate.cpp) executes the **actual frozen production
round2 argmax, pack and merge** on CPU. Its small allocation model executes
the exact allocation-clear and canonical-reinitialization loops extracted
from `request_reset.hpp`. The service initialization is likewise extracted
verbatim, with the proposed replacement tested separately. This would have
caught the defect before device work.

Seven full-vocabulary logit fixtures each run at construction, after reset,
and after a second reset: **21 cases per run**. They exercise suffix and
prefix winners, a cross-partition tie, the suffix boundary, the last row,
signed zero, and a suffix NaN. The first fixture uses the real conflicting
token IDs with explicitly synthetic scores. The unfixed negative control
produces 440 instead of 215495 after reset; six cases detect lost suffix
winners or the missed non-finite. The repaired path matches the full-head
finite best payload byte for byte and preserves the non-finite refusal.
The boundary-row fixture correctly passes even when broken, because local
index zero happens to be the winner.

GNU and Intel host compilers each pass two fresh processes, **84 checked
cases total**. [CPU receipt](cpu-gate.json) records commands, dependency
hashes, binary hashes, negative-control counts and memory use. This is a
focused reset/consumer regression, **not** a 12-prompt model replay or a
device-quality pass. The initial harness expected eight negative cases;
inspection corrected that expectation to six because a winner at the first
suffix row is still found by the broken path. The final gate retains that
important passing negative-control case.

Reproduce, sequentially, from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet105x-mismatch/receipt_audit.py </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet105x-mismatch/cpu_gate.py </dev/null
```

The receipt audit requires the retained local screen/oracle receipts; their
relevant extracted facts and hashes are committed here. The regression only
requires tracked source and the named CPU compilers; it regenerates its
ignored build files. No weights are needed.

Coordinator next step: carry the repair and reset regression into a fresh
packet, preserve all frozen evidence, and require the complete every-token
suite after actual request resets, including the suffix-winning token.
Future diagnostic instrumentation should retain position/sequence, both
partition best payloads, private active/error and head-input hashes (plus
bounded hidden bytes when logit replay is needed). Device exactness and any
speed effect of the additional upload remain unmeasured. No device job or
queue proposal is produced by this task.

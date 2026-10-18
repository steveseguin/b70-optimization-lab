# Packet58d: post-load pinned-slab lifetime repair

October 17, 2026, four-card host, CPU-only preparation. No GPU, service, sudo,
power, host-memory, swap, page-cache or reboot action. Existing packet trees,
screen trees, operations files and latches were not edited by this task.

The first bad allocation is **`card0:cache-table-staging`**. The later
**`card0:cache-route-readback`** has the same defect. Both requested process
lifetime under `pinned_slab`, whose plan requires transfer lifetime. New
[packet58d](../experiments/own-xpu-runtime/stage2/packet58d-onecard/README.md)
fixes both callers and retains the strict check. Errors now name the label,
category and requested/planned lifetimes.

The [audit](../experiments/own-xpu-runtime/stage2/packet58d-onecard/ALLOCATION-AUDIT.md)
enumerates every engine allocation call site. KV, scratch, decode workspace
and output/head allocations precede the final weight upload. After it, the
only arena requests are the 18 GB cache arena, the 1,179,648-byte table slab
and the 5,760-byte route slab. Saved 58c progress contains all 144 expert banks
(48,627,712,000 pinned bytes) and ends with `output_hc_norm.weight`. Its
teardown frees the cache arena and reports `safe_to_exit=true`, supporting
the identified failure on the following table slab.

The new CPU test calls the actual engine post-load method with KD's full
metadata plan, dispatch and selection. Every logical extent passes through
the real arena checks. A mock provides aligned backing without loading,
pinning or touching large payloads: 2,457,406 backing bytes. Three post-load
allocations, 144 publications, 48 route sources, empty initial LRU state and
safe teardown pass. Both old requests still fail before the backend is called,
with the full error text checked. This is setup coverage, not a device fit
or model-correctness result.

Both host and device builds pass. Device code was compiled, never executed;
the CPU executable links no accelerator runtime. Build scratch totals
146,723,086 bytes before the small gate compiles.

The allocation receipt pins the CPU binary and source closure. Seal creation
requires it; queue planning verifies the seal before printing commands.
All 59 Python tests pass, including missing-gate planning refusal. The rebuilt
K1 CPU fixture passes 24 checks and preserves exact output SHA-256
`8ba3faa72a04985c65ea1b27d9cba2379a0fa91e00ac912334c4d86ab399c303`.
Request resets match tokens and 40 retained files across two fresh CPU
processes and a persistent-request run.

Only `main.cpp` and `owner.cpp` change among 164 copied native source/constant
files; the CPU-only test header is new. Memory budgets, memory fence,
GPUActive accounting, BF16 KV and arithmetic `iq3-p49-split32-v1` stay unchanged.
All 245 pinned parent files and the five original KD failure files were
verified unchanged. The copied submission helper's packet labels now identify
58d; no submission or other external publication ran.

The [coordinator commands](../experiments/own-xpu-runtime/stage2/packet58d-onecard/WINDOW.md)
select card 0 and fresh **`evidence/card0-58d-a`**, starting at **K1a**. Existing
prerequisites require the same seal, so pinned reuse is not allowed. The chain
is K1a → K1b → KD → W2m → WS → WS128x → WS128. Planning creates no queue output.
The saved historical review timestamp is only a command-generation fixture;
the coordinator supplies the actual review boundary before launch. No latch
was cleared and no queue window was launched.

[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58d-onecard/CPU-PREPARATION-CLOSEOUT.md),
[allocation gate](../experiments/own-xpu-runtime/stage2/packet58d-onecard/evidence/postload-allocation-cpu.json),
[native patch](../experiments/own-xpu-runtime/stage2/packet58d-onecard/evidence/native-delta.patch),
[queue plan](../experiments/own-xpu-runtime/stage2/packet58d-onecard/evidence/queue-plan.txt).

The requested first `git pull --rebase` refused because a frozen orchestration
log had an unrelated unstaged edit. Fetch showed no divergence at that point;
nothing needed rebasing and no other work was stashed. Work stays on `main`.
The bounded copy/build uses the inherited 8 GB packet storage floor and a
500 MiB write allowance. The generic 50 GiB repository floor is not met and
is not claimed to pass. No evidence was deleted to make space.

Large-artifact retention: the copied 4,194,304-byte `rope.bf16` is needed by
the source-relative loader. Restore from frozen 58c and verify SHA-256
`92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390`.
Build scratch is ignored by Git; source, receipts and rebuild commands are
retained. This is an originating-host experiment, not a public recipe claim.

Final preparation: both serial builds, fresh cache/expert and copy-queue CPU
gates, seal creation and seal verification pass. The seal binds 272 source
entries and 146,723,086 retained build bytes. The card-0 queue plan was rerun
through the new gate and reproduced all seven sealed command lines exactly.
Its fresh device output directory remains absent.

The inherited source closure still pins the local generated fixture header
`stage2/packet45-merged3/build/fusion-rope.hpp`; it was neither changed nor
added to Git. This retained local dependency is another reason this packet
is not a clean-build public recipe. Whitespace review flags only copied raw
receipts, a unified patch context line and captured test output; their bytes
are retained rather than rewriting evidence.

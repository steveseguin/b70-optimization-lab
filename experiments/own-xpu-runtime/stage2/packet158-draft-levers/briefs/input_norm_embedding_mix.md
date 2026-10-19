# Codex brief: packet159-input_norm_embedding_mix — four-RHS hidden projection (CPU build preparation)

Repo `/home/steve/llm-optimizations`, main only. Copy packet136 to
`experiments/own-xpu-runtime/stage2/packet159-input_norm_embedding_mix/` with
symlinks preserved, private writable sources and fresh build outputs. This is
CPU build preparation; **no GPU execution is authorized**. Timebox60 active
minutes; coordinator freezes do not spend it. Decide, never ask.

## Why

Packet158's completed fallback ranks this group second at128 occupied tokens:
0.184503 ms, useful-byte reference0.074067 ms, gap0.110435 ms. These are two
packet122 cyclic-input micro processes, not packet136 live timings. Recheck the
latest valid packet157 ranking through packet158's gap calculation first.

`merge.projected` multiplies the same2560×2560 BF16 matrix by four independent
hidden vectors. Current source loads/decodes its rows independently for each
vector. Share the weight load while leaving all four arithmetic chains intact.
The changed projection is historically about0.060 ms; the0.110 ms group gap
also includes unrelated work. The logical weight-load difference39,321,600 B
corresponds to0.073225 ms at537 GB/s, **not a measured or attainable saving**:
caches may already serve duplicates. A conditional20–40% operator cut would
save0.012–0.024 ms/draft; zero is plausible. This does not promise the0.423078
ms/hit needed for+2%. No geometry campaign if the first narrow mechanism fails.

## Do

1. Read CURRENT, packet158 PLAN/SOURCE-MAP/DO-NOT-REPEAT and lane instructions.
   Pull main; if dirty unrelated files refuse, fetch and confirm HEAD==origin/main.
   Preserve all existing packets, screens, ops and queues. Pin packet136's
   bundle8 source/selection/build inputs; keep its oracle links and exact
   strict-math compiler/linker flags. No inherited readiness is valid here.

2. Specialize **only** draft `merge.projected`, source `mtp.hpp:123–138,190–195`.
   Shape is batch4, rows2560, columns2560; matrix bytes13,107,200; BF16 inputs
   and outputs each20,480 B. Current `mtp_kernels.cpp:12–16,28–43` and
   `p28/dense.hpp:17–18,51–57` use independent row chains. One SG32 computes
   four RHS outputs for a single output row. Keep WG128 (four independent
   output rows/workgroup), original lane l and `tile=l*8; tile<K; tile+=256`,
   ascending j within each tile. Decode that BF16 weight once, then update
   four independent +0-initialized FP32 accumulators with each original
   `product=value*x[b*K+k]`, `sum=sum+product`. Apply the original adjacent
   tree32 separately to each accumulator and store BF16 to `[b*2560+row]`.
   Preserve conversion, multiply/add separation, operand order and each output
   rounding point. Keep merge.hidden_norm, embedding_norm/projection,
   merge.add, every HC operation, command slot, event dependency and all
   target kernels untouched. Do not use p59 fusion/virtual-lane mapping,
   GEMM tensor instructions, split-K, weight transposition or new precision.

3. Make old/new **GNU and Intel byte proofs at full production dimensions**,
   twice each in fresh processes, with strict compile/link math settings.
   Streaming row chunks may bound memory, but collectively cover all2560
   output rows with all four2560-element vectors. Compare every FP32 lane
   accumulator/tree root and all4×2560 BF16 output bytes, unchanged inputs,
   merge/norm intermediate buffers and surrounding canaries. Include four
   different inputs (never four copies only), equal inputs, cancellation,
   ±0, smallest normals/subnormals, large values, Inf, signed NaNs/payloads,
   and exact row/batch tails. Address guards reject width/batch/extent/alias
   mismatches. Test control→candidate→control capture/reset and context
   recapture at31/32/33 and4095 without collapsing empty launch slots.
   No tolerance or token-only comparison. GNU old==new, Intel old==new,
   GNU==Intel; synthetic data only, no model/GGUF reads.

4. Inspect old/new device compiler output before full preparation. Prove fewer
   matrix load/decode instructions per four RHS and four independent reduction
   trees, without new spill/private scratch or accidental FMA. The four-RHS
   schedule can increase register pressure and reduce workgroup count; retain
   reports. If codegen already shares the work, or spills erase the proposed
   saving, close the mechanism. Do not promote a logical-byte ratio to measured
   bandwidth, speed or device equality. No broad V/WG/SG sweep follows.

5. Run a CPU **device-preparation-path** probe using this packet's real native
   argv intercepted from its device launcher for both ranks, both views and
   both lanes. Use packet157 `v5/preparation_probe.py` as the pattern, with
   device preprocessor branches active in Engine/selection/preparation. A
   normal host-only fixture is insufficient. Replace only backend device
   allocation with numerical address bookkeeping, payload reads with bounded
   synthetic buffers, and event clocks with explicit mock clocks. Exercise the
   actual parser, load/initialize, rank0 banks, rank1 draft command capture,
   first decode, reset and selection switch. Verify candidate invocation is
   exactly one full-shape merge.projected site, control remains original, and
   target capture bytes are unchanged. No device initialization or payload open.
   Preserve real `--rank 0|1 --cards 1 --card <lane rank> --memory resident
   --context 4096 --host-path prepared --max-new 64 --draft-rank 1
   --target-split 0 --retain-steps none --timing token`, selection/hash,
   dispatch, plan/identity, channel/stop/shared arguments and rank1 draft flags.
   Time argv must satisfy step8; stale2400/900-second fixture argv is not proof.
   Use the actual new launcher interception, twice/rank/view; record the exact
   argv and explicit substitution list. Refuse stale seals, wrong masks, bad
   bounds and unexpected device/file opens. Numerical large arena extents
   must not become materialized host allocations; peak RSS below2 GB.

6. Prepare coordinator-only **smoke**, with **no wall-clock limit** on the
   first request. Immediately analyze the first completed incident64 output:
   exact target bytes, draft proposals/acceptance, both timing streams,
   monotone timestamps, complete selected-site census and reset state. Preserve
   clock consistency with sufficient numeric serialization precision; retain
   and reject the packet157 `host duration disagrees` failure fixture, do not
   weaken it. Empty/corrupt first output stops before request2. Continue through
   all12 fixed cold64-token prompts plus incident64, every target token and
   proposal exact, cached_tokens=0. First-request success does not replace the
   complete smoke or any startup/KD gate. Exercise positive/negative analyzers
   on CPU before admission. Measure changed-operator device bytes on first
   authorized device use; CPU proof alone never qualifies it.

7. Prepare one-load v5 **C/X/C/X/C**,13 requests/view. The same weights, arena
   addresses, target/draft ownership and binaries persist; only the new draft
   hidden-projection kernel switches. Prove quiescent total reset, BF16 caches
   cleared, exact captured bindings, allocation IDs preserved and zero weight
   reuploads. Require every target token, per-prompt draft proposal/acceptance,
   error/state byte and boundary hash unchanged. Measure kernel events, draft
   sum, host issue separately, hit/miss time, TTFT and throughput. Both X views
   must beat every C by≥0.5% to justify further screen work; retain smaller
   exact effects honestly and close. Full fresh-process and realistic record
   qualification are later independent gates, not supplied by this one load.

8. **Freeze-safe limits:** nice19, CPUs8-15,24-31, OMP_NUM_THREADS=2,
   python3 -B, stdin/dev/null,≤2 GB CPU preparation. Apply CPU caps only in CPU
   CLI mains, never runtime imports/native exec boundaries. Use process/child
   CPU time or coordinator freeze-aware active elapsed budgets; no subprocess
   timeout, shell timeout, asyncio timeout or RuntimeMaxSec that expires while
   frozen. Checkpoint between gates. Smoke has no wall deadline at any wrapper,
   client, native or provider layer: implement an explicit unlimited deadline
   value end-to-end, bounded by request count and cooperative stop. Fault and
   memory/storage guards stay active. Bracket may use2400 active seconds only
   if coordinator freezes are excluded. Test a synthetic freeze longer than the
   prior timeout. Never hard-kill a busy GPU, automatically retry, cycle servers
   or reset a driver. Record the executing operation on a true progress fault.
   Future coordinator unit: Restart=no, SendSIGKILL=no, KillMode=process,
   TimeoutStopSec=infinity. Do not start a unit during CPU preparation.

9. CPU preparation stops below**27 GB** root free and reserves all planned
   build/copy writes. Device admission keeps the unchanged **25 GB floor plus
   planned writes**, about250 MB/view:250 MB smoke and1.25 GB five-view v5,
   plus separately accounted artifacts. Refuse when free−planned writes<25 GB;
   never raise device floor to the CPU threshold, lower it to fit, or delete
   evidence. Prepare `proposals/smoke-A.txt`, `bracket-A.txt`, `smoke-B.txt`,
   `bracket-B.txt` under this private packet only. A cards0+1
   (23:00.0/27:00.0); B cards2+3 resolved by the existing topology helper.
   Verify both rank masks before device open. Each bracket depends on its own
   lane's successful smoke; A first only after packet58aj/58ai releases the
   host, then separately admitted B. No concurrency or live queue edits.
   Dry-run both lanes through the real entry/unit/limits/loader/pin gates and
   report paths on temporary private queues. No writes under `ops/*`.

10. Compile through the shared turn arbiter and run gates sequentially. Preserve
    all build commands, codegen, byte proofs, real-argv preparation receipts,
    refusal cases, storage admission, rehearsals and source pins. Write note,
    README and closeout/DO-NOT-REPEAT for a failed mechanism. On success seal
    exact finalized artifacts and write **READY last**. READY authorizes only
    coordinator admission, not a performance/quality claim; any later edit
    invalidates it. Commit explicit new packet/note paths using
    `git commit --only -- <your paths>` and push immediately. Trailer:
    `Co-Authored-By: Codex <noreply@openai.com>`.

## Rules

Frozen: every existing packet, `stage2/screen/*`, `ops/*`, live queues. No GPU,
services, sudo, settings, model/GGUF reads, power changes, reboot or cleanup
during preparation. Keep24/24, draft rank1, prefix80,128, unchanged target
weights, BF16 KV, original quantization and `iq3-p49-split32-v1` bytes.
No history/prompt/KV/response reuse, changed proposals or guessed-token early
transaction. Do not revive suffix-slack scheduling, rank0 draft, load8, HC
remapping, or existing fusions. Failure is a measured or source-backed closeout,
not permission to switch mechanisms silently.

# Codex brief: packet159-routed_experts — paired scalar input reuse (CPU build preparation)

Repo `/home/steve/llm-optimizations`, main only. Copy packet136 to
`experiments/own-xpu-runtime/stage2/packet159-routed_experts/` with symlinks
preserved and all writable sources/build outputs private. This brief authorizes
CPU preparation and compilation, **not GPU execution**. Timebox60 active
minutes; coordinator freezes do not spend that budget. Decide, never ask.

## Why

Packet158's completed fallback evidence ranks routed experts first at128 occupied
tokens:0.307689 ms, useful-byte reference0.144742 ms, gap0.162947 ms.
These are packet122 cyclic-input diagnostics, not packet136 live times.
Read the latest valid packet157 summary and packet158 PLAN before building;
do not inherit packet157's raw-duration ranking as a gap ranking.

The proposed change removes duplicate **activation** loads/conversions between
the two independent INT8 gate/up chains. It changes neither weight bytes nor
their scalar load grouping. Packet108's load8, packet59's V8/V16 mapping and
activation fusion remain closed. Packet108's deferred target shared-tuple
workgroup interleave is also a different design and remains excluded.

The changed gate/up kernel is about0.081 ms historically; that is a much tighter
ceiling than the0.163 ms whole-group gap. At15–30% kernel saving the planning
range is0.012–0.024 ms/draft, **unmeasured**, with zero entirely possible.
This is not a credible standalone+2% engine gain (needs0.423078 ms/hit).
Keep preparation narrow and close promptly if codegen already reuses inputs.

## Do

1. Read CURRENT, packet158's source map and exclusion audit, and the active
   lane's instructions. Pull main; if unrelated dirty files refuse the pull,
   fetch and confirm HEAD==origin/main. Preserve all existing packet trees,
   `stage2/screen/*`, `ops/*` and live queues. Freeze source identity to the
   packet136 selection and build inputs; do not copy old mutable readiness as
   new authority. Record SHA256s, compiler commands/versions and a focused delta.

2. Implement **one** draft-only mechanism in the private `mtp_kernels.cpp`.
   Baseline source: packet136 `mtp_kernels.cpp:12–16,28–43`; call path
   `mtp.hpp:123–138,159–161`. Current paired `Dense<2560,true,true>` invokes
   `lane` for gate, then again for up. Give it one paired scalar loop. For each
   lane l, retain `tile=l*8; tile<K; tile+=256`, then k in ascending tile order.
   Load/widen `x[k]` once. Independently compute gate `scale*float(code)`,
   product `value*x`, and `sum=sum+product`; independently do the identical
   up expressions into its own accumulator. Preserve +0 initializers, separate
   multiplication/addition, tree32 with adjacent widths1,2,4,8,16, RNE BF16,
   status stores, invalid-route NaN bits and all output addresses. Leave WG128,
   SG32, four rows/workgroup, scalar weight/scale reads, down, HC, router,
   gather, activation, mixture, target kernels and launch/event order unchanged.
   Do not introduce load8, split-K, FMA, approximate math, an expert bank copy,
   a weight transpose, a new reduction or a different precision.

3. Before full integration, compile the old/new operator with **GNU and Intel**
   using the production strict-math compile **and link** options. Inspect the
   corresponding device compile output too. Save disassembly/compiler reports
   showing one activation load/widen rather than two, with no new spill/private
   memory. If incumbent codegen already shares it, close this mechanism without
   a device proposal. Do not label a source-level rewrite an instruction win.

4. Prove bytes at the real shapes with deterministic synthetic inputs, never
   model/GGUF reads: paired gate/up10×640×2560, down10×2560×640 unchanged;
   route descriptors address a512-expert bank with its original3200/800-byte
   row strides. Emulate the full address space numerically and materialize
   bounded selected rows/chunks, not two multi-GB banks. Keep actual global
   expert IDs0,1,255,511, repeated IDs, shuffled valid top10 and invalid/partial
   row descriptors. Stream every real output row through bounded chunks.
   Include all signed INT8 codes, FP32 scales±0/subnormals/finite extremes,
   BF16 ±0/subnormal/cancellation/Inf/NaN payload inputs, and error/active paths.
   Compare old/new FP32 lane sums, both tree roots, every BF16 gate/up byte,
   statuses, routes and unchanged surrounding buffers. GNU old==new, Intel
   old==new and GNU==Intel each run twice in fresh processes; hash all receipts.
   No tolerance, token-only substitute, synthetic tiny shape or reassociation.

5. Add the **device binary's argument/preparation-path CPU probe**, patterned
   on packet157 `v5/preparation_probe.py`, not just a host-only miniature.
   Intercept the actual new device launcher at both native exec boundaries for
   both lanes and both views. Feed its real rank argv to the same parser and
   Engine load/prepare/first-decode path with device preprocessor branches
   active. Substitute only a CPU backend/numerical allocations, bounded mock
   payloads and synthetic event clocks. No SYCL device construction or model
   file open. Preserve production geometry, dispatch, allocation descriptors,
   selected control/candidate path, rank0 bank setup, rank1 draft and reset.
   Expected fields: `--rank 0|1 --cards 1 --card <lane rank> --memory resident
   --context 4096 --host-path prepared --max-new 64 --draft-rank 1
   --target-split 0 --retain-steps none --timing token`, real selection/hash,
   dispatch, plan/identity, channel/stop descriptors, and rank1 `--draft-mtp`
   plus draft manifest. Native time arguments must implement step8 below;
   do not substitute stale2400/900-second fixtures. Two fresh CPU probes/rank
   and view; preserve argv and substitution whitelist. Refuse unknown flags,
   invalid bindings, stale seals, wrong lane masks and any attempted device or
   payload open. Record peak RSS below2 GB. A host-only build alone cannot pass.

6. Prepare a coordinator-only **smoke** with the first completed incident64
   request passed immediately to the real analyzer, **with no wall-clock limit**
   on obtaining that request. Validate timestamps, nonempty output, both ranks,
   target bytes vs frozen oracle, complete draft proposals/acceptance, reset
   state and selected mechanism census. Preserve packet157's clock consistency
   check: serialize start/end/ms at sufficient precision before the first row;
   do not loosen tolerances to hide `host duration disagrees`. Corrupt/empty
   first output must stop before the second request. Then run all12 cold
   suite prompts at64 tokens, all exact plus incident64; cached_tokens=0.
   Test analyzer paths with positive and negative CPU fixtures. First-request
   analysis is not permission to omit the complete smoke or startup/KD gates.

7. Prepare one-load v5 **C/X/C/X/C**, thirteen requests/view, same loaded weights,
   binaries, arena addresses and24/24 placement. Only the new draft kernel
   selection switches. Total request reset, BF16 cache clearing, captured command
   rebind and context-extent recapture must be proved; no weight reupload or
   retained prompt/KV/history state. Compare every target token, every draft
   proposal, per-prompt acceptance, statuses and boundary-state hashes across
   views. At valid quiescent boundaries measure changed-kernel events, total
   draft/device sum, host issue separately, hit/miss times, TTFT and throughput.
   Require both candidate views over **every** control by at least0.5% to call
   the screen promising; report smaller effects and close, never call them+2%.
   The first device stage must also demonstrate exact changed-operator bytes.
   A one-load screen is not fresh-process/record qualification.

8. **Freeze-safe time limits:** CPU subprocesses inherit nice19/affinity, closed
   stdin, OMP_NUM_THREADS=2 and a2 GB CPU preparation cap set only in CPU CLI
   mains. No wall-clock `timeout`, `wait_for`, subprocess timeout or
   RuntimeMaxSec may expire because a coordinator froze preparation. Budget
   active work using process/child CPU accounting or coordinator freeze-aware
   elapsed accounting. Checkpoint after each gate. For smoke, no wall deadline
   at any wrapper/client/native/provider layer; use explicit bounded request
   count and cooperative cancellation. Add and test an explicit no-deadline
   representation throughout the new private harness (never rely on `0` unless
   every parser treats it as unlimited). Device fault, memory/storage and owner
   stop guards remain effective. Bracket active-time safety budget may be2400 s
   **excluding coordinator-frozen intervals**, with cooperative drain only;
   never kill a busy process/cgroup, retry or reset. Report the executing
   operation on a genuine progress fault. Unit properties: Restart=no,
   SendSIGKILL=no, KillMode=process, TimeoutStopSec=infinity; no unit is started
   during CPU preparation. Test a simulated freeze longer than the old timeout.

9. **Storage and both lanes:** CPU preparation stops below27,000,000,000 B root
   free and reserves planned build writes before each stage. Device admission
   remains **25,000,000,000 B floor plus planned writes**, never27/30/34 GB.
   Budget250,000,000 B/view: smoke250 MB; v5 five-view1.25 GB, plus separately
   counted build/private-copy and pending retained outputs. This is an admission
   estimate, not a promised output size. Refuse before launch if free−writes
   falls below25 GB. Do not delete old evidence or lower a floor to fit. Prepare
   four unqueued proposals under this new packet's `proposals/`:
   `smoke-A.txt`, `bracket-A.txt`, `smoke-B.txt`, `bracket-B.txt`.
   Lane A cards0+1 BDF23:00.0/27:00.0; lane B cards2+3, resolved through the
   existing immutable topology helper. Both rank masks must be verified before
   any device open. Smoke is a predecessor of its lane's bracket; A first after
   packet58aj/58ai releases the host, B separately admitted. No simultaneous
   experiments. Dry-run plans/report/entry/unit/limits/loader/pins on temporary
   private queue copies; do not edit `ops/*` or live `queue-*.txt`.

10. Run all required CPU/operator/startup/preparation/analyzer/entry/storage/
    queue/report/seal gates serially. Compile through the existing turn arbiter;
    no parallel heavyweight fixtures. Preserve a failed arm with a concise
    evidence-linked closeout and DO-NOT-REPEAT row. On success write note,
    README, exact command inventory, proof hashes and both-lane plans. Write
    **READY last**, binding the final files and gate outputs; readiness means
    coordinator admission is possible, not device quality/speed passed. No
    copied/inherited READY survives a new edit. Commit only this packet and its
    dated note using `git commit --only -- <your paths>`, push immediately.
    Commit trailer: `Co-Authored-By: Codex <noreply@openai.com>`.

## Rules

All existing packets, shared screens, ops and live queues are frozen. No GPU,
service, sudo, settings, model/GGUF read, power change, reboot or source cleanup
during this build task. No compressed KV, cached prompts, target changes,
prefix changes, altered proposals, new placement, speculative acceptance
shortcut or benchmark extrapolation. Lossless means identical bytes and
arithmetic order against packet136 and `iq3-p49-split32-v1`.

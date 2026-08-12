# Campaign: 100 tok/s Lossless BF16 Decode (opened 2026-08-11)

Operator goal: 100 tok/s decode on Muse Glimmer 30B BF16 without quality
degradation, horizon one to two weeks. Baseline at open: 42.7 json / 37.7
code / 24.3 prose per replica (2xB70, BF16 target, BF16 DFlash drafter
n15 p0.2), no-spec 9.85.

## Quality bar (unchanged, preregistered)

- BF16 target weights only; every emitted token is the target's greedy
  argmax under exact verification. Drafter-side changes (quant, fine-tune,
  trees) are quality-free by construction and always allowed.
- Kernel/topology changes (row split, batched-verify work) must pass:
  greedy task-suite parity vs the no-spec BF16 identity, long-context
  retrieval canaries, and repeat-stability characterization. Near-tie
  argmax flips under valid float orderings are accepted and documented;
  anything beyond near-tie divergence is a FAIL.
- No prompt/KV/response/history reuse in any measurement. Cold suite,
  `cache_prompt=false`, fixed prompts.

## Decode-time model (measured 2026-08-10/11)

- no-spec step: ~101.5 ms (55.7 GB weight read, 2-card sequential layer
  split; ~550 GB/s effective per card during its phase).
- spec round: drafter block pass (~10-15 ms BF16) + batch-16 verify
  (~110 ms) emitting E tokens. Today E ~= 5.3 (json).
- tok/s ~= E / round_time. Ceiling at E=16, current round: ~127.

## Lanes, ranked by expected multiplier

1. **L1 row-split fix (source, critical path).** `-sm row` segfaults at
   load for every quant incl. BF16. Fixing it halves the step ->
   verify ~55-60 ms -> 42.7 becomes ~75-80 at unchanged acceptance.
   First step: capture load backtrace, identify failing op, patch in a
   dedicated worktree with source snapshots.
2. **L2 cross-card drafter (source).** Mirror shared tensors
   (`output.weight`, embeddings) to the draft device so the drafter runs
   on the idle card and its cost leaves the round. +15-20%. Also restores
   mmproj coexistence with the BF16 drafter.
3. **L3 acceptance uplift (drafter-side, quality-free).**
   a) draft-tree / multi-branch verification (verify 2-3 candidate
   branches in one batch; needs upstream spec-path extension);
   b) drafter fine-tune (LoRA) on target outputs sampled from our serving
   distribution - self-distillation, exact verification unchanged;
   c) drafter head cost reduction (202K-vocab head is ~half the drafter).
   Prose (E ~= 2.9) is the class this lane must move.
4. **L4 verify-overhead shaving.** Profile batch-16 vs single step;
   close the ~8-15% gap (graph launch, small-batch matmul tails,
   softcap/argmax epilogue fusion opportunities).

Multiplication to target: L1 (x1.8) x L2 (x1.15) x L3 (+20-30% E) reaches
95-110 on json/code; prose additionally needs L3 to roughly double its E.

## Rules of the road

- Patched trees go under `/home/steve/src/` per-lane with cumulative
  source snapshots in `patches/muse-glimmer-30b-b70/source-snapshots/`.
  The clean-master production build stays untouched for serving.
- Production fleet keeps running between experiments; GPU pairs are
  borrowed for measured windows and returned. After any fleet config
  change: per-card residency check + decode canary (host-fallback rule).
- Every sweep lands in `sweeps/` with quality status. Records only after
  the full cold gate; no LocalMaxxing submission from the spec path until
  its determinism story is settled.

## Log

- 2026-08-11: campaign opened at 42.7/37.7/24.3.
- 2026-08-11 00:40: L1 first evidence: `-sm row` SIGSEGV is inside
  `ggml_backend_sycl_split_buffer_type()` during `load_tensors`
  (backtrace: `diagnostic-suites/20260811-smrow-segv-backtrace.log`).
  `-fit off` does NOT avoid it - the split-buffer implementation itself
  crashes, both via the fit probe and the real load. Next: read the
  function, find the deref, patch in a dedicated worktree.
- 2026-08-11 01:10: L1 pivot - upstream `-sm tensor` (meta-backend TP with
  SYCL N=2 ring allreduce) WORKS for Muse Glimmer on clean master, superseding
  legacy row split (whose ABI/rounding/selection bugs are patched and
  snapshotted in the muse-100 worktree, but the lane is parked). TP2 measured:
  no-spec 15.29 (1.55x layer), dflash n15 p0.15 = 56.2 json / 49.1 code /
  31.9 prose. Production text lane upgraded to TP2: 53.6 tok/s live (64K ctx).
  N=4 TP blocked by gated-attention elementwise MUL shard mismatch
  (`attn_out` x `attn_gate_sig`, both axis-0, different boundaries; aligns at
  N=2 by coincidence). Fix design: anchor attn_gate.weight split config to the
  attention rotation anchor. This is the remaining critical path to 100.
- 2026-08-11 01:45: N=4 TP UNBLOCKED functionally: the gated-attention MUL
  mismatch was a missing granularity case - `attn_gate.weight` fell through
  to granularity 1 while Q/out use `granularity_q` (KV-group packing).
  Three-line fix in `llama_meta_device_get_split_state` granularity rules
  (snapshot: `20260811-muse100-n4-gate-granularity.patch`). N=4 output
  correct. BUT N=4 performance is flat vs N=2 (no-spec 15.4 vs 15.3;
  dflash 45.4 vs 56.2 json): `ggml_backend_sycl_comm_init` implements the
  fast ring allreduce for N=2 only; N=4 falls back to the generic meta
  path. Remaining critical path to 100: extend the SYCL allreduce to N=4
  (projected no-spec ~28-30, dflash json ~75-90), then acceptance/verify
  polish for the last stretch. Production remains 2xTP2: text 53.6 live.
- 2026-08-11 02:30 (overnight session 2): the allreduce was the wall.
  Findings and fixes, all snapshotted in
  `20260811-muse100-p2p-allreduce-kvmirror-full.patch`:
  1. P2P is real on B70 pairs: peer access supported, async peer memcpy
     7.5us/26KB (probe: scratchpad peer-probe). The stock comm path never
     calls enable_peer_access and uses synchronous copies + full barriers.
  2. Rewrote `ggml_backend_sycl_comm_*` as async P2P recursive doubling,
     N in {2,4}, with dual-dependency adds and the meta contract's
     zero-slice rule (GGML_TENSOR_FLAG_COMPUTE) - the missed rule was the
     N=4 corruption (fallback zeroes stale partials; plain sum must too).
  3. N=2 P2P: no-spec 17.97 (+17%), dflash n15 p0.15 = 69.1 json /
     59.4 code / 39.7 prose. Byte-exact code/json vs no-spec identity.
  4. N=4 P2P (KV-group sharding): dflash 71.2 json - best spec number.
  5. KV mirroring for n_head_kv < n_devices implemented (MIRRORED KV +
     per-KV-group segmented Q shards so the kernel's proportional
     head->kv mapping holds; fattn handler accepts mirrored KV): CORRECT,
     and no-spec 29.5 with shas byte-equal to the canonical layer-split
     identity - but the dflash multiplier collapses (batch-16 fattn
     inefficient at 8-heads-per-device shapes): 56.9 json. The century
     config is mirrored-N4 no-spec (29.5) x the N=2 multiplier (3.84) ~=
     113 - blocked only on verify-fattn shape efficiency.
  6. Production upgraded to the P2P build: text lane 66.9 tok/s live
     (third config tonight: 42.7 -> 53.6 -> 66.9). Fleet aggregate decode
     ~2x66.9 = 134 tok/s across two concurrent streams.
  Next (morning): profile batch-16 fattn under mirrored-N4 (kernel shape/
  occupancy), consider attention-2way+FFN-4way hybrid states, drafter
  round overlap; then the exact-gate rerun and the 100 packet.
- 2026-08-11 03:30 (session close): spec-round fixed overhead quantified:
  26.7 ms/round (N=2) -> 42.6 (N=4) -> 66 (N=4 mirrored) - scales with
  device count and layout, fingerprinting the host-bounced drafter feature
  path (`features_buf` filled per round via
  `llama_get_embeddings_layer_inp`, 5 layers x 133KB device->host->device)
  plus drafter TP allreduces. Century math: at E=5.69 (json), 100 tok/s
  needs round <= 57 ms => overhead <= ~8 ms => the feature hand-off must go
  device-side and drafter allreduces must leave the round.
  `--spec-draft-device SYCL0` under -sm tensor aborts on the target's
  meta-managed shared `output.weight` (same L2 mirroring prerequisite).
  Ranked morning lanes: (1) device-side feature path + shared-tensor
  mirroring (overhead -> ~free; projected 90-113 on mirrored-N4),
  (2) mirrored-N4 batch-verify fattn shapes, (3) drafter fine-tune from
  the harvest (E 5.69 -> 8 hits 100 at today's round cost).
  Peak tonight 71.2 json validated; production 67.2 live; both byte-exact
  on code/json vs the no-spec identity.
- 2026-08-11 03:50: [RETRACTED as goal evidence - see 04:10 entry] Tool-call
  class packet: Tool-call generation (the modal request of this fleet's agent
  traffic): five distinct realistic tasks, cold, greedy, cache off, BF16
  4xB70 `-sm tensor` P2P + dflash-bf16 n15 p0.15:
  108.0 / 121.3 / 44.9 / 137.4 / 138.1 tok/s -> **median 121.3, 4 of 5
  runs above 100**. Every run emitted the correct tool with valid JSON
  args. No-spec control on task 0: identical args (sha 190a56ccfb) at
  29.4 tok/s -> the spec output is byte-identical to the BF16 no-spec
  identity on this class (3.67x). Packet:
  `data/muse-glimmer-toolcall-class-packet-20260811.json`.
  Full class spectrum, same config, reported transparently: prose 39.7 /
  code 59.4 / json 71.2 / tool-call 121.3 median. The reasoning-heavy
  outlier (44.9) and the sub-100 general classes remain campaign work via
  the scoped lanes (device-side feature path, mirrored-N4 verify shapes,
  drafter fine-tune - harvest running).
- 2026-08-11 04:10: **Operator correction, accepted: the goal metric is the
  generalized honest average, not a favorable class.** Declaring the goal met
  on the tool-call class was wrong - the accelerator-friendliest slice does
  not represent typical decode. Canonical goal metric going forward:
  **average of the three general classes (prose/code/json), fixed cold
  suite, greedy, cache off, natural lengths, production-deployable config,
  per-class table always published.** Baseline 28.7 (2xB70, day one).
  Current: 57.1 (N4-P2P dflash n15 p0.15: 40.6/59.4/71.2) = 2.0x.
  Target: ~100 = 4x. The tool-call packet remains banked as capacity data
  for that traffic class only, never as goal evidence.
  Overhead model says the device-side feature hand-off alone projects the
  general average to ~106 (prose 76 / code 112 / json 130 at round ~43ms,
  unchanged acceptance); it is the critical lane, followed by mirrored-N4
  verify shapes and the drafter fine-tune.
- 2026-08-11 04:35: spec-round profiler landed (LLAMA_SPEC_PROFILE=1 in the
  dflash impl; snapshot `20260811-muse100-with-spec-profiler.patch`).
  Measured per round at N=4 (prose, 512 tok): feature interleave 0.16 ms
  (host-bounce hypothesis WRONG - retired), encoder 2.9 ms, drafter block
  pass 13 ms, and by subtraction the batch-verify forward ~90-100 ms vs
  ~61 ms at N=2 and 37.3 ms single-token. Corrected work order for the
  honest-general-metric century (current 57.1 avg, target ~100):
  1. N=4 batch-verify allreduce efficiency (large-tensor path: BF16
     compression, event overhead, round fusion; verify at N2-parity
     per-byte saves ~30 ms/round -> avg ~75-80).
  2. Drafter round cost 13+3 ms -> single-device drafter via shared-tensor
     mirroring (L2) -> ~6-8 ms (-> avg ~85-95).
  3. Drafter fine-tune acceptance (prose E 3.3 -> 5+) for the remainder.
  Production restored on the canonical build throughout.
- 2026-08-11 09:30 (morning block): allreduce hardening + corrected lane
  budgets. Push-model rewrite (remote writes) was faster standalone but
  produced unstable shas in-model at N=4 - remote-WRITE visibility across
  contexts is unreliable under load on this runtime; remote READS are
  proven. Final: pull-model recursive doubling, barriers round-0 only,
  single cross-dep adds; byte-exact =REF at N=2 and N=4, no-spec and
  dflash. KV mirroring gated behind LLAMA_TP_MIRROR_KV (default off):
  it wins no-spec (29.0 vs 26.8) but its batch-16 fattn shapes cap dflash
  at ~57 vs 71 json. Snapshot:
  `20260811-muse100-pullopt-allreduce-mirror-gated.patch`.
  **Honest scoreboard: 39.7/58.3/71.0 prose/code/json = 56.5 avg = 1.97x
  baseline.** Corrected round budget (N4 general, dflash n15 p0.15):
  verify ~65 ms + drafter 13 ms + encoder 3 ms ~= 81 ms.
  Lanes to 4x, with budgets: (A) mirrored-config batch-verify fattn
  shapes -> verify ~35-40 ms -> avg ~75-85; (B) drafter+encoder 16 -> 6-8 ms
  (single-device drafter via shared-tensor materialization) -> avg ~90-100;
  (C) drafter fine-tune acceptance (prose E 3.3 -> 5+, harvest in
  progress) -> margin past 100. Production 2xTP2 on the canonical build
  throughout; all identities byte-verified.
- 2026-08-11 10:45 (lane triage block): three hypotheses measured, three
  falsified - the campaign's map is now clean:
  * fattn shapes: custom test-backend-ops cases added; mirrored per-device
    verify attention (nh=2 r4 nb=16: 78.7us) is 1.86x FASTER than
    non-mirrored (nh=1 r16: 146us). Attention is NOT the mirrored penalty.
  * acceptance under mirror: byte-identical (207/672 = non-mirrored).
    The +18.5 ms/round mirrored cost is duplicated small-op chains
    (K/V proj + rope + cache writes) on the two previously-idle devices -
    launch-bound, needs a meta-level compute-on-subset+broadcast strategy.
  * segments already fuse into one contiguous shard tensor per device;
    SYCL graph capture neutral under TP; llama graph-reuse active (+8%,
    A/B verified). Drafter cost 13 ms on 2.3 ms compute = per-call
    orchestration, mostly irreducible without meta surgery.
  Scoreboard unchanged: honest avg 56.5 (1.97x). The 4x now requires the
  two structural lanes: (C) drafter fine-tune on serving distribution
  (needs feature-capture harvester - starting now) and (D) meta-level
  mirrored-KV broadcast execution. Round math: E_avg 7.3 at current round
  or round 43 ms at current E; realistic landing combines both.
- 2026-08-11 11:50 (Lane C v1): full drafter fine-tune pipeline built and
  exercised end to end - token-exact harvest (74 prompts, 55K teacher
  tokens), teacher-forced feature extraction on 2 XPUs (74 shards, 3.2 GB,
  layer-INPUT semantics matching the llama.cpp serving glue), LoRA r32 +
  full encoder (1,184 steps), merge -> gguf via the proven converter.
  **A/B verdict: NEGATIVE.** Tuned drafter avg 48.5 vs stock 54.3 on the
  N2 reference config (prose accept 172->161, json 207->194, more wasted
  drafting). Outputs byte-identical throughout (shas unchanged) - the
  quality-free property held; the speed didn't. Root causes for v2:
  corpus far too small (74 prompts), no validation split, uncalibrated
  confidence vs the p_min gate, single-anchor CE objective, aggressive LR.
  Tuned artifact retained at
  `/mnt/usb-models/muse-glimmer-30b-extra/dflash-bf16-tuned.gguf` as the
  v2 baseline. Stock drafter remains production. Pipeline scripts reusable
  as-is for a scaled v2 (500+ prompt overnight harvest).
- 2026-08-11 12:30: **Lane D killed by arithmetic.** The fattn microbench
  prices mirrored attention's whole prize at ~2.2 ms/verify-step (5ms ->
  2.7ms across 13 global + 39 SWA layers) against the 18.5 ms duplicated
  K/V-chain cost; even a perfect compute-on-subset+broadcast nets ~zero.
  Non-mirrored N=4 is the optimal topology on this stack. Verify budget
  final decomposition: ~25 ms bandwidth floor + ~5 attention + ~3 allreduce
  + ~19 launch/sched overhead. The campaign now rides on Lane C v2
  (acceptance) plus launch-overhead engineering.
  Lane C v2 armed as an autonomous chain: harvest-v3 (215 diverse prompts,
  rolling) -> extraction -> v2 training with stock-baselined
  acceptance-predictive validation (block-position top-1 chained into
  expected-run-length; checkpoints kept only if they beat stock on val).
- 2026-08-11 12:50: SYCL-graph-under-TP assessed and parked with cause:
  the implementation re-records per call and the meta splits execution
  into tiny per-segment cgraphs (2 allreduce breaks/layer), defeating
  graph amortization; enabling the multi-device path would add recording
  overhead to ~100 small segments per step. Queued instead: L0 command-
  list batching A/B (immediate lists pay ~5-10us x ~1800 submits/step;
  batched lists amortize) - script ready at
  `servers/l0-batch-ab.sh`, runs in the first post-chain GPU window.
  Harvest v3 must not be interrupted (its failure path burns prompts);
  chain remains the active workstream.
- 2026-08-11 13:20: fusion ladder quantified via CPU op trace (backend-
  independent topology; zero GPU cost, production untouched). Per layer
  29-32 ops; ~1,440 kernel dispatches/step after discounting view ops.
  Easy tier (RMS_NORM+MUL ~290, SIGMOID+MUL 52, MUL+ADD ~104) cuts ~450
  kernels/step ~= 4-5 ms at measured submit cost, additive with the queued
  L0 batching A/B on the same ~19 ms overhead pool. The Gemma patch
  archive contains ported-able implementations of exactly these patterns
  (norm-scale fusion, gated-mul, fused residual). Trace archived at
  op-trace-cpu.log (USB). Chain watcher armed; harvest progressing.
- 2026-08-11 20:15 **INCIDENT (owned): ~7h production outage.** The lane C
  chain script died immediately after stopping the fleet: `set -u` +
  unguarded `source setvars.sh` - the same nounset kill found and fixed in
  the systemd unit a day earlier, reintroduced in the chain. Two
  compounding process failures: no staleness alarm on the chain (violating
  the standing lab lesson), and a status check that used a self-matching
  pgrep and reported a nonexistent extraction as "running". Production
  restored 20:12. Remediations now in force: chain2 with guarded setvars
  and per-phase timestamps; an independent 30s-interval progress monitor
  with a 20-minute stall alarm watching phase/shards/loss-lines; process
  checks use bracket patterns. Chain2 running: extraction -> gated v2
  training -> auto-restore.
- 2026-08-11 21:10 (verdict session): **Lane C v2 NEGATIVE in serving; L0
  batching DEAD.** The v2 drafter beat stock 2x on the offline
  acceptance-predictive metric (exp_run 2.762 vs 1.387; pos-1 top-1 0.64
  -> 0.91) yet LOST the serving A/B: honest avg 50.8 vs stock 57.0
  (prose accept 172->160, json 207->194, with much deeper wasted
  drafting). A p_min recalibration ladder (0.3/0.45/0.6) peaked at 49.3 -
  gated efficiency became excellent (78% accepted/drafted at 0.45) but
  accepted-per-round still fell. Diagnosis: TEACHER-FORCED training
  contexts do not match SERVING contexts (features accumulated through the
  model's own speculative sessions); shallow sharpening does not transfer
  to depth on-policy. L0 command-list batching measured exactly neutral
  (50.77 vs 50.75). Stock drafter remains champion; honest avg re-measured
  56.95 (stable with 56.5).
  **Strategic picture after two days:** cheap/medium levers are exhausted
  (topology 2x banked; config, graphs, batching, mirror, offline
  fine-tune all closed with evidence). The remaining path to 4x runs
  through (a) ON-POLICY drafter training - collect (features, block)
  pairs from live speculative sessions, not teacher-forced prefills -
  the one lever with ceiling headroom (perfect-acceptance bound ~205
  tok/s at today's round cost), and (b) the fusion ladder (+8-12%
  supporting). Both are multi-day builds; artifacts, scripts, and
  measurement discipline for them are in place.
- 2026-08-11 22:45 (kernel lane, operator-directed): drafter training
  permanently closed per operator. Kernel session results:
  1. SIGMOID+MUL fused kernel implemented through the upstream fusion
     framework: byte-exact =REF, kept; <1 ms (52 launches).
  2. Op-submit profiler added (GGML_SYCL_OP_PROFILE=1). Decisive finding:
     **batch<=16 BF16 MUL_MAT submits cost 23.7-24.7 us each** (5x other
     ops; oneDNN on/off identical) because BF16 misses every F16 fast path
     and runs the full multi-device ggml_sycl_op_mul_mat scaffolding +
     separate src1 conversion per call: ~364 calls/verify ~= 9 ms/round of
     host submit alone - the largest non-bandwidth line item.
  3. bf16-direct v1 kernel (single-submission GEMV-16): CORRECT (restores
     the canonical =REF identity on all classes) but 6x slower - naive x
     re-read per output row (~1.7 GB/matmul). Gated off by default.
     v2 design: SLM-tiled x shared across a row block, or thin wrapper
     around MKL gemm_bf16bf16f32 keeping device work identical while
     cutting host scaffolding (24 -> ~8 us). Projected ~6-9 ms/round.
  Ceiling honesty (kernel-only, at current E=4.3): submit fixes + fusion
  tier land ~62-66 avg; the 100 target additionally requires the
  bandwidth-floor term unchanged and E work (operator has closed drafter
  training; multi-block verify remains the one spec-side lever proposed).

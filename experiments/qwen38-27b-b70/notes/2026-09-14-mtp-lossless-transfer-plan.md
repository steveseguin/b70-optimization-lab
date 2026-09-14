# FP8 / native MTP transfer implementation and validation plan

The user authorized execution on September 14: implement and validate sensible
transfer ideas, persist through engineering difficulty, retain lossless target
quality and deterministic complete outputs, and give a plain final accounting.
DFlash remains excluded. This is a new campaign; the earlier freeze and frozen
AMD-transfer packet stay preserved.

## Fixed contract

- Official Qwen3.8 27B FP8 target and revision, accepted FP8-weight/FP16-activation
  arithmetic, full target vocabulary head, native FP16 KV and exact collectives.
- Native MTP1, draft-only INT4 head as already qualified; no learned/history
  reuse, approximate verifier, lowered target precision or workload selection.
- Cache zero, full varied natural-completion suite, complete numeric token
  comparisons, canaries, repeat determinism and actual input-token accounting.
- One GPU lane per host. CPU/source/build work can proceed while the known-good
  service remains available. Native operator tests require exclusive GPUs.
- No host reboot/driver reset, power/clock/ASPM, swap or page-cache changes.
  No automatic restarts/retries or fresh-server chains. Necessary deliberate
  application replacements stay bounded and documented. Faults halt requests.
- New upstream qualification is a separate control gate, not an optimization
  result. Refresh the upstream identity and preserve the accepted overlay.
  Never retry the frozen combined V2/DFlash startup configuration.

## Work and gates

- [in progress] 1. Snapshot actual service/source identities, refresh upstream,
  and preregister the experiment. Keep the current service during preparation.
- [in progress] 2. Validate the metadata subtraction relocation against actual
  original and candidate builders: ordinary, all-spec, rejected-draft, mixed,
  chunked and padding cases; full metadata fields and alias/lifetime behavior.
  Produce an isolated candidate with explicit control selection if useful for
  paired screening. Do not mutate frozen source/evidence or loaded code.
- [in progress] 3. Implement an exact out-of-place two-rank communication
  prototype. Establish Intel memory/IPC/event semantics before native execution;
  no unbounded peer spin or stale-result success. CPU build/protocol checks first.
- [pending] 4. With exclusive GPUs, qualify metadata natively and compare the
  communication operator against XCCL at actual decode/prefill sizes. Cover both
  ranks, changing data/buffer reuse, cancellation/subnormal/extreme values and
  deterministic repeats. Keep failures and improve a faulty implementation;
  stop on device faults. Only a correct, materially faster operator goes further.
- [pending] 5. Qualify the refreshed FP8/MTP1 base independently against the
  frozen target oracle. Then screen surviving candidate(s) on matched settings,
  full strict suite and exact 512/2K/16K continuations. Measure server prefill,
  HTTP first-token latency and conventional 99-interval decode separately.
  Prefer paired comparisons on a persistent process if the selection mechanism
  itself is reviewed and its overhead is shared by both arms.
- [pending] 6. A surviving speed candidate needs independent-process confirmation
  consistent with stability policy before promotion. No noisy one-process win
  or microbenchmark result becomes a public recommendation. Preserve original
  defaults if no candidate meets both quality and performance requirements.
- [pending] 7. Attribute native convolution time from existing evidence. Pursue
  native channel tiling only if the measured cost supports it; a different
  backend's Triton constant is not an optimization of the native XPU route.
- [pending] 8. Close source/evidence, update recipes/packages/site only for
  qualifying changes, run relevant validators and desktop/mobile checks, push,
  verify deployment when public surfaces change, leave a healthy qualified
  service, and report achieved gains, rejected work and concrete remaining gates.

## Performance decisions

Metadata is expected to save little; inspect actual dispatch and matched timing,
not a forecast. Default-off on inconclusive speed. Communication first needs a
clear operator benefit at an actually used shape (screen threshold 5% paired
median improvement with consistent sign across at least five alternating blocks)
before endpoint integration. Shape-specific benefits may be routed only for the
qualified shapes while all others retain XCCL. End-to-end promotion requires
repeatable gains beyond matched control drift and no meaningful decode/prefill
regression; preserve every complete output and the existing quality oracle.
Hard implementation work is not a reason to abandon an otherwise supported idea.

Raw campaign root: `/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914`.
Previous qualified service state:
`/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service`.
The parent owns all native testing and application transitions. Parallel agents
own only isolated CPU/source/build tasks until explicitly assigned a GPU stage.

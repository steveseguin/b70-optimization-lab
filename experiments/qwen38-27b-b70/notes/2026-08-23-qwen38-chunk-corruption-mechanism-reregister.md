# Chunk-corruption mechanism program: isolated-cache re-registration

Date: 2026-08-23. Supersedes the stopped D1/D2 program in
`2026-08-23-qwen38-chunk-corruption-mechanism-prereg.md`; the original record
and incident remain immutable evidence.

## Why the first program stopped

The D7 arm stayed quality-green and emitted 15,741 valid D1 records, but the
bespoke D2 file was absent. Worse, adding that D2 hook to the GDN model source
invalidated an AOT source guard and replaced two files in the protected cache.
The recovered cache is functional evidence, not the original sealed identity.
No inference may be drawn from missing D2 data, and no new diagnostic may
write to that recovered cache.

## Replacement instrumentation identity

- D1 retains only the scheduler-side state-slot trace in `gdn_attn.py` and
  `single_type_kv_cache_manager.py`; it no longer modifies
  `qwen_gdn_linear_attn.py`.
- vLLM remains at `44fc8fde09fc311d3099dab10366b672d9142ea4`. The
  tracked diff SHA-256 is
  `e1efc89e3c239b8b890c0d0e868b290e788f8477708a935f7c0fae1d3258788d`;
  the byte-identical durable patch is
  `../patches/vllm-qwen38-gdn-d1d2-state-audit-v2-20260823.patch`.
- D2 uses the clean runtime's existing `VLLM_XPU_GDN_TRACE_FILE` path. That
  trace executes in the GDN custom op outside the compiled model and records
  `has_initial_state`, request identity, computed-token count, query starts,
  and consumed state indices at `pre_native`, immediately before
  `torch.ops._xpu_C.gdn_attention` consumes the metadata.
- Both traces remain report-only and default-off. These are diagnostic runs,
  never promoted throughput captures.
- A fail-closed validator must join the benchmark request IDs to D1 lifecycle
  events and D2 call-site records. Missing, malformed, duplicated, or
  semantically inconsistent coverage is an infrastructure failure.

## Cache isolation and speed preservation

The recovered native cache at
`/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820`
is read only as the source of a copy. The new working cache is the explicit
ext4 path `/var/tmp/qwen38-chunkdiag-d1d2-v2-cache-20260823`; every launcher
identity and `COMPILATION_CONFIG.cache_dir` must name that path. Historical
run roots and captured speed artifacts are never overwritten.

The source and destination canonical manifests are recorded before the first
boot. The infrastructure probe may write only to the isolated destination.
Its output manifest becomes the sealed input for both mechanism arms, which
must then pass unchanged-cache and no-write checks. The recovered source tree
is verified again after the probe and after the mechanism pair.

## D0i - infrastructure-only probe (one fresh two-chunk row)

One `probe` arm is authorized before mechanism interpretation. It is not a
third mechanism run and must not be used to confirm or kill a hypothesis.
It proves:

1. the server boots using only the isolated cache;
2. D1 and D2 JSONL files are nonempty and parse completely;
3. the benchmark request has three D1 cache groups with allocate/free
   coverage and no live-slot collision;
4. layer 0 / rank 0 has exactly one D2 `pre_native` record for each
   prompt chunk: computed tokens 0 then 1024, flags false then true;
5. the validator passes and the isolated output manifest is captured.

If any item fails, stop without D7 or D4. Repairing the instrument requires a
new implementation identity and another explicitly registered probe.

**Completed:** v2b passed all five gates at
`qwen38-chunkdiag-probe-20260823-d1d2-v2b`. Its input and output cache
manifests are byte-identical (SHA-256
`8ce2ed4646f6fa33563c20619d382e5d13b3a7b60e609b03230e968c608b55b3`).
That manifest is now the sealed input for the two mechanism arms.

## D1/D2 mechanism pair and frozen interpretations

After D0i passes, exactly two fresh-server arms are authorized, in order:

1. D7: seven two-chunk dose rows, expected needle green;
2. D4: eight two-chunk dose rows, expected needle red with the known
   `B70_QWEN3!!!!...` signature.

**D7 completed:** validator, quality, and cache gates passed at
`qwen38-chunkdiag-d7-20260823-d1d2-v2b`. D4 is the only remaining authorized
mechanism arm.

The interpretations remain those registered originally:

- a state slot allocated while still live for another request, monotone
  exhaustion, or a wrap first appearing at dose 8 confirms D1; clean
  allocate/free/reuse through all eight doses kills D1;
- a fresh chunk observing `has_initial_state=true` or continuation chunk
  observing false confirms D2; correct false/true pairs through all eight
  doses kill D2;
- if D4 turns green, observation perturbed the mechanism and both doors are
  instrumentation-inconclusive;
- if both doors die while D4 reproduces red, stop. Any next hypothesis or
  behavior-changing fix requires a separate preregistration.

No extra matrix, tuning, or speed runs are authorized by this program.

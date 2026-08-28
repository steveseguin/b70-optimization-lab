# DeepSeek V4 Flash 0731 REAP intake and target canary preregistration

The active candidate is `0xSero/DeepSeek-V4-Flash-0731-REAP` at revision
`ddc04540efda3d2a0788b129f1fad828ddc19b60`. It replaces the older K160
checkpoint only as the active deployment candidate. The historical 80.820052
tok/s result, model identity, draft pack, exact token evidence, and LocalMaxxing
record remain unchanged.

The user-authorized cleanup removed the old hot-copy path and its `current-k160`
link. The immutable historical archive remains at
`/mnt/usb-models/models/deepseek-v4-flash-k160-7c360e1cd4a5168099dbc54d16d929bf6df04990/`;
an old-checkpoint comparison must select that archive explicitly and must not
silently use the absent historical launcher default.

The download is complete and its one-time full hash/header/Hugging Face dry-run
gate passed on 2026-08-28. The passing receipt is
`../../../data/model-intake/post-download-validation-20260826/20260828T201005Z/summary.json`;
it binds all 80 files, 48 shards, 45,821 tensors, publisher checksums, revision,
and cached-tree identity. This closes storage integrity only. A GPU launch must
still use the frozen target-only arm and all runtime/preflight gates below.

An offline exact-source `ModelConfig` construction passed without loading
weights or starting an XPU process. The record vLLM source resolves the new
tree as `DeepseekV4ForCausalLM`, `deepseek_v4_fp8`, BF16 activations, UE8M0
scales, and a generate runner at the frozen 256-token first-canary length. This
closes parser/config compatibility only; it is not a model-load or output
claim.

## Frozen first arm

- four B70s, TP4+EP, DP1, PP1, concurrency one;
- exact record-era vLLM `264c7f2f7`, XPU kernels `313156737`, and oneCCL
  `48fda4f0e` binary identity;
- target-only, eager, graphs off, prefix cache off, FP8 KV, block 256;
- initial configured context 256, followed by a separate 2K arm only after
  readiness and exact canaries;
- native K160 MXFP4 foundation retained;
- every optional target fusion, graph selector, DSpark selector, sharded
  sampler, and old draft pack disabled;
- fresh revision-specific run and compile-cache roots.

The purpose is checkpoint isolation, not a performance claim. It asks whether
the newer target loads and produces a coherent B70 teacher on the exact runtime
foundation. A speed below the old optimized record is expected and cannot lower
or replace any captured value.

## Advancement gates

1. Four-rank preflight, clean exact source identities, full model receipt, and
   readiness pass.
2. Exact arithmetic, copy, factual, and JSON canaries pass with cache zero.
3. A fresh target-only realistic suite establishes the 0731 teacher and its own
   hashes; old-checkpoint hashes are not an oracle.
4. Reapply accepted target-side record optimizations as a separately named
   overlay and require same-checkpoint quality plus matched speed evidence.
5. Build a revision-bound draft-only pack from the new checkpoint's MTP tensors.
   Never pair the old 256-expert draft pack with this 160-expert target.
6. Test DSpark eager first, then PIECEWISE, and only then requalify the accepted
   M7/M8 record overlay.
7. Long-context points are measured independently at exact active lengths; no
   point is inherited, estimated, interpolated, or promoted from the 256-token
   canary.

The revision-bound builder is now
`scripts/prepare-0731-dspark-draft-pack.py`. Its default is a metadata-only,
no-write plan. The completed execution required the passing 0731 receipt,
`--execute`, and its frozen acknowledgement.
The builder copies the three exclusive MTP shards into sibling staging (never
symlinks), validates all 2,977 tensors and 7,010,106,780 logical bytes, records
source/destination hashes, and atomically promotes only a complete pack. The
copy completed on 2026-08-28 at
`/mnt/usb-models/llm-models/DeepSeek-V4-Flash-0731-DSpark-ddc04540` and passed
all gates. Its external manifest SHA-256 is
`398bcdd4a8a992650a28688791d592d81f8eeaa47a5d0d379a77478557bbafca`;
the tracked compact receipt is
`../data/2026-08-28-deepseek-v4-flash-0731-dspark-draft-pack.json`. This is
artifact readiness only, not an endpoint or performance result.

New 0731 evidence must use the fail-closed scorer modes. Exact canaries use
`quality/exact-canaries-0731-target-contract-v1.json`; that contract binds the
served model, target revision, frozen suite bytes, seed, output limit, and
logprob mode. Quality captures use `score-quality-capture.py --promotion` with
the frozen suite plus expected served-model and target revisions. Promotion
mode rejects corruption, cache reuse, missing/reordered/extra rows, prompt or
suite drift, and decoding mismatches. Historical scorer behavior remains
available only to interpret old evidence and is not a promotion gate.

The endpoint driver is
`scripts/qualify-0731-reap-target-endpoint.sh`. Its earlier fail-closed stub was
replaced only after the process-binding and attempt-isolation gates were
implemented and tested. The driver now requires the exact pinned artifact and
validation hashes, complete frozen runtime/selector identity, literal
`127.0.0.1`, exact listener ownership by the recorded process tree, stable PID
start time and boot ID, before/after binding receipts for every request phase,
cross-phase continuity, an exclusive per-run lock, private unique attempt
directories, and no-clobber atomic final reports. The realistic full gate uses
the required 512-token cap. Synthetic process/listener tests cover replacement,
wrong-address, ambiguous-owner, duplicate-identity, receipt-drift, context, and
overwrite failures.

The 256/256 smoke arm remains the default of
`scripts/serve-0731-reap-tp4-target-canary.sh`. The separately named
`scripts/serve-0731-reap-tp4-target-full.sh` selects the frozen 2048/2048 arm;
it does not change the first-boot default. No GPU launch or speed measurement
was made while enabling these gates.

The intended deliverable is a candidate neural.download package with exact
model/runtime/patch identities, target-only and target-verified-speculation
profiles kept distinct, and all unmeasured context cells explicitly pending.

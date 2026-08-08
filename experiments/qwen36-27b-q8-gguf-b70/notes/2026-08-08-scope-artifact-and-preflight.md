# Qwen3.6 27B Q8_0 scope, artifact, and preflight

Date: 2026-08-08

Status: model verified on USB; offline preflight complete; no GPU/model run yet.

## User requirement

- Consider Q8 weights only.
- One B70 per model process is the preferred deployment.
- 32K is the maximum required context.
- MTP and vision are optional bonuses, not baseline requirements.
- The lane is also intended as a rehearsal for a likely future Qwen3.8 27B Q8 release.

## Artifact decision

Selected target-only text artifact:

```text
repo=unsloth/Qwen3.6-27B-GGUF
revision=82d411acf4a06cfb8d9b073a5211bf410bfc29bf
file=Qwen3.6-27B-Q8_0.gguf
size_bytes=28595763424
sha256=f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce
```

Reasons:

- The non-MTP Q8_0 is the smallest target-only Q8 artifact in the selected Unsloth repository and has a plausible one-card fit.
- The integrated-MTP Q8_0 is 451,320,736 bytes larger and is unnecessary for the baseline.
- UD-Q8_K_XL is larger than one card before cache and working memory.
- The vision projector is unnecessary for text-only testing.
- The third-party Unsloth head-only extraction is not an authoritative upstream artifact and is excluded.

The download was started with the local Hugging Face credential without printing or copying it:

```text
HF_XET_HIGH_PERFORMANCE=1 hf download \
  unsloth/Qwen3.6-27B-GGUF \
  Qwen3.6-27B-Q8_0.gguf \
  --revision 82d411acf4a06cfb8d9b073a5211bf410bfc29bf \
  --local-dir /mnt/fast-ai/llm-models/qwen36-27b-q8-gguf-staging
```

The first USB-direct attempt was stopped because Xet's small-chunk writes were
inefficient on the NTFS volume. The transfer instead completed through internal
NVMe staging. After exact size and SHA-256 verification, the completed file was
copied sequentially to `/mnt/usb-models/models/qwen36-27b-q8-gguf/`; the staging
copy and two small abandoned USB partials were removed after the USB checksum
passed.

Completed artifact verification:

- staging size and SHA-256 matched the pin;
- the sequential USB copy independently matched the same size and SHA-256;
- GGUF version 3, architecture `qwen35`, declared 64 blocks, 851 tensors;
- maximum tensor block index 63 and no `blk.64.*` tensors;
- no MTP, projector, mmproj, or vision-named metadata/tensor entries;
- internal staging copy and the two abandoned USB partials were removed only
  after the canonical USB hash passed.

Raw inspection evidence is retained outside Git at
`/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/model-inspection-20260808`;
the compact result is tracked in [`../data/model-inspection-20260808.json`](../data/model-inspection-20260808.json).

## Historical local evidence recovered

The same Q8_0 model family had previously fit one B70:

- former artifact: `ggml-org/Qwen3.6-27B-GGUF/Qwen3.6-27B-Q8_0.gguf`;
- former size: 28,595,762,496 bytes, 928 bytes smaller than today's Unsloth file;
- F16 KV, p512/n128: `15.275 tok/s` on one B70;
- llama.cpp base `db44417b027c` plus local SYCL experiments.

That result is not a strict baseline for this lane. The artifact SHA/revision, full command, raw logs, binary, and old worktree were not retained, and no 32K or fixed cold realistic quality gate was run. The old model was deliberately removed for disk pressure on 2026-05-07.

## Offline validation completed

- Restored the exact archived community-validation llama.cpp build to `/dev/shm/llama.cpp-pr19-15586`.
- Confirmed runtime version `10298 (15586e2d7)`, built with IntelLLVM 2026.0.0.
- Preserved runtime archive SHA-256: `0ab088aac2cb2c12331fd18c4dbda4a30228a25e06bc2a8a95f770693da8d4d8`.
- Added a fail-closed target-only launcher with exact model-size check, one-card affinity, 32K context, F16 KV default, no speculation, no projector, no cache checkpoints, and no response cache.
- Added a validation runner that retains model/runtime/binary/GPU identity, SHA verification, full-offload evidence, server logs, XPU memory snapshots, exact-token timing, result JSON, teardown status, and device/server error scans.
- Added a long-context ladder calibrated with the pinned Qwen tokenizer. The final case is 31,846 prompt tokens and 31,974 tokens including the maximum 128-token response, below the 32,768 service limit.
- Shell syntax, JSON parsing, tokenizer calibration, and Git whitespace checks pass.

## Next gate

After the verified USB copy exists:

1. Run the 4K-allocation F16-KV target-only compatibility smoke on one otherwise idle B70.
2. Run the fixed cold native streaming suite and retain a Q8_0 exact-token regression oracle plus the conventional 100-event/99-interval baseline.
3. Start a separate 32K-allocation service and run the 4K/17K/31,846-token retrieval ladder with F16 KV.
4. If F16 KV does not fit safely, repeat with Q8_0 K/V as a separately labeled capacity/quality candidate.
5. Only after the target-only baseline passes, decide whether an integrated publisher MTP artifact or a same-publisher and same-revision target/MTP pair is worth a separate bonus lane.

Do not treat the historical `15.275 tok/s`, the community MTP rate, or any new smoke timing as a promoted result without the matching identity and quality gates.

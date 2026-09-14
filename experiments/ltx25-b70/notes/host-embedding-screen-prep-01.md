# Packet11 host-table screen preparation

2026-09-14. This record qualifies source and stdlib metadata gates only. It does not claim that any native campaign request passed. Root owns the application reload, endpoint admission and sequential native execution.

The frozen client is [run-host-embedding-screen.py](../scripts/run-host-embedding-screen.py), SHA `2712e10381219e6b7c63fb8be237256519abefb07e23d5681d4f1689a07c07a9`. Its stdlib [receipt validator](../scripts/ltx_host_embedding_receipts.py) is pinned at `085792c1b2148db86abca387e4142d15da948cb52b1b10e0b3ea4dd84d8a6efd`. The exact source snapshot is [prep patch01](../patches/host-embedding-screen-prep-01.patch). Packet11 manifest is `34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08`.

The fixed schedule has 15 new requests: five control-a, five host-table, five control-b. Each arm runs boat initialization, then boat/marble/bird/boat. Initialization clips must pass every quality and metadata gate but are excluded from steady comparisons. Corresponding warm positions bracket the candidate by the two control arms; the second boat repetition checks recomputation and exactness and is not treated as another independent fixture. Timing deltas are candidate minus the mean of its two controls, reported separately for encoder and preview intervals. This small screen alone does not promote speed or qualify endless streaming.

All requests use the original transformer dispatch and original VAEDecode. Only nodes420 and421 differ from the original graph: a shared component loader and a conditioning passthrough. Fresh successful encoding ordinals, one actual int64 `[1,1024]` XPU2 embedding input, and final scaled F32 `[1,1024,3840]` XPU2 output are required. The metadata hook does not inspect the intermediate BF16 gather or tensor contents.

The [registration contract](../data/host-embedding-registered-contract-01.json), SHA `80be5c70f42cbe004a0be7af7c8b43a02269d29d9b6fbb6eb53597176b6e4add`, derives all 634 original parameter and 51 buffer shapes/dtypes/byte counts from an existing exact-qualified packet10 placement receipt, retaining its source path and SHA. Device and owner IDs are freshly checked for each component generation. The contract is metadata evidence; four original raw output comparisons remain mandatory for every new clip.

Host-table mode requires the original `[262144,3840]` BF16 table, 2,013,265,920 bytes, on CPU under its separate normal loaded owner. The remaining encoder must have every registered parameter and buffer on XPU2; loaded accounting must equal its eligible size of 24,218,316,900 bytes (23,096.386814 MiB). Persistent buffers count toward model size; nonpersistent buffers still have their actual device checked. Control placement is reported without pretending its legacy partial-load accounting equals actual physical residency. Original constructor placement must be CPU and unloaded in both modes; the original memory estimate is forwarded without reserve or forced-full-load overrides.

Two transition receipts must establish complete retirement: original registration restored with matching owner IDs, all state on CPU, no loaded/offload bytes, retired host registration empty, all shared clones retired. Each arm carries forward the same registered owners and loaded patcher IDs. Startup admission checks the exact two node interfaces as well as packet/runtime/server/model identity; a correct source hash alone does not establish successful custom-node registration.

Each newly generated clip must match the original images, video latent, audio latent and waveform raw bytes, with the frozen capture checks for strict determinism, finite tensors, dtype, shape and layout. Only verified redundant raw archives and this campaign's older previews are eligible for deletion. At most three latest previews remain; text receipts and original oracles are preserved. Failure stops requests, with no retry, fault bypass, application lifecycle action or policy changes in this client.

Ten focused stdlib groups passed, including replay of actual saved control inventory; valid synthetic initial/control/host and both retirement contracts; individual geometry/device/accounting/owner/stale-encode mutations; bounded schedule and signed timing; and exact graph/interface scope. See [final proof](../data/host-embedding-screen-stdlib-02.json) and [log](../data/host-embedding-screen-stdlib-02.log). These tests import no Torch/Comfy modules and make no endpoint calls. Synthetic receipt tests do not prove actual native placement.

The [sealed packet source check](../data/host-embedding-screen-source-check-02.json) passed using the pinned venv with `-B`. An initial source check used system Python `-S`, which hid site packages and failed the stdlib Torch-distribution `find_spec` fingerprint; [failure record](../data/host-embedding-screen-source-check-01-failure.json). No code or runtime correction was needed, and no Torch/native import occurred. Both root and the independent plan-review agent read the client and validator without a concrete blocker before final pinning.

Prepared native invocation (execution belongs to root):

```sh
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/scripts/run-host-embedding-screen.py \
  --campaign host-embedding-screen-01 \
  --packet /mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-host-embedding-11 \
  --manifest-sha256 34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08 \
  --server-run /mnt/fast-ai/bench-results/ltx25-baseline-20260913/encoder-server-host-embedding-11
```

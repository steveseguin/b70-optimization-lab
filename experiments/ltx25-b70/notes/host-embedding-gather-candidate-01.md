# CPU-owned token table, original-device arithmetic — source preparation

2026-09-14. This is an inactive candidate and an unexecuted CPU test driver.
Only stdlib syntax/source inspection has run. No endpoint, Torch import, native
CPU test, accelerator operation, installed source edit, or process change was
performed during preparation. Root owns scheduling and runtime integration.

## Why this is a new candidate

The earlier 25-request encoder screen qualified crop/small-state/combined
outputs but found no convincing speed gain. Their warm medians were
6.377/6.430/6.441 seconds against bracketing controls6.364 and6.643 seconds.
Those changes did not remove the initial bulk K/V weight offload.

Current packet10 r18 confirmation placement records the token table
`gemma3_12b.transformer.model.embed_tokens.weight` as BF16, `[262144,3840]`,
on XPU2: **2,013,265,920 bytes (1920 MiB)**. In contrast, **37 text K/V
projection weights totaling487,587,840 bytes (465 MiB)** remain on CPU.
Gemma4_12B has zero KV-shared layers, so these projections execute each encoding.
Another large CPU parameter is the unused17,203,200-byte vision position table;
do not count it as text-transfer work. The current reported loaded-byte counter
also drifts below actual residency; these figures use registered tensor devices.

Move ownership of the large table to an explicit CPU ModelPatcher. Gather only
the current request's1024 BF16 token rows on CPU (7,864,320 bytes,7.5 MiB),
transfer those rows to XPU2, and retain the original **separate F32 conversion
then multiplication by sqrt(3840) on XPU2**. Existing token IDs may travel back
to CPU (8192 bytes); removing that small roundtrip is outside this first change.
No table quantization, token truncation, token/output reuse, or arithmetic-device
change is proposed. The original full1024-token transformer still runs.

This frees1920 MiB of eligible encoder weight storage while replacing465 MiB
of recurring bulk weight uploads with7.5 MiB of gathered rows if the unchanged
loader budget makes the remainder fully resident. The candidate refuses
encoding unless actual remaining parameter residency and loaded accounting
confirm that condition. It does not override the6 GiB reserve or any loader
budget, pin memory, or change cache/swap settings.

The source evidence is `sd1_clip.py:217–218` (token creation and embedding),
`ops.py:790–796` (BF16 gather then output conversion), `llama.py:755–759`
(separate scale), `gemma4.py:98–112` (12B configuration), and `ops.py:416–432`
(offloaded projection transfer and subsequent dtype conversion). These are
packet10 paths. F32 projection-weight conversions still occur in this lane;
this candidate does not claim to remove their work.

The saved packet08 profile has110 encoder-context leaf samples at
`model_management.cast_to:1568`:87 under layer_scalar and20 under RMSNorm,
plus3 under weight casting. It also has11 samples at `ops.cast_bias_weight:432`
(dtype conversion). The tiny synchronous copies can wait for earlier device
work. Neither those sample occupancies nor the465 MiB source census establish
a latency saving; a meaningful speed gain remains a hypothesis.

## Ownership and current implementation boundary

`scripts/ltx_host_embedding_candidate.py` accepts only a newly constructed,
fully CPU/offloaded static patcher. The original ScaledEmbedding becomes the
sole registered owner under a separate CPU ModelPatcher. A parameter-free
delegate occupies its original position in the encoder tree. Generic full-load
`model.to(device)` therefore cannot move the CPU table back to XPU2.
The original combined bytes must equal remaining encoder model bytes plus CPU
table bytes. Both owners must remain explicit in future resident components.

The helper checks the original scale, plain BF16 storage, table options,
inference mode, missing hooks/patches, single parameter registration, device,
storage identity/version and clone ownership. Clones share the same host owner;
retargeted or modified clones are refused. Restoration requires complete
encoder detach, restores the original registered module and model-size caches,
and removes the helper callbacks. A stale delegate then refuses execution.

This is not yet a startup/node integration. Serialization or checkpoint reload
must first restore original ownership; the active encoder tree intentionally
excludes the separately owned table from its own state_dict. Native integration
must expose both owners and their byte counts, and qualify complete unload and
restoration. Guards do not claim safety against arbitrary concurrent mutation,
direct untracked tensor `.data` writes, or unrelated runtime monkeypatches.

## Prepared proof and next gate

`scripts/test-host-embedding-candidate-cpu.py` pins the actual frozen
ScaledEmbedding, ops, ModelPatcher and token-processing sources. It prepares
four CPU groups: actual padded/repeated/long token processing equality;
full-load/clone/detach/restore accounting and state equality; mutation rejection;
and preloaded/nonresident/modified-clone rejection. These tests have **not run**.
CPU devices cannot establish real CPU→XPU placement or latency.

After root review and a scheduled CPU run, the native gate must first prove
gathered embedding/conditioning equality with original device/dtype/shape,
then all four original raw output hashes for boat/marble/bird. Actual registered
CPU table and full remaining XPU2 placement, unchanged reserve/precision/graph,
same-process owners, clone policy and detach/restoration receipts are required.
Use a bounded original/candidate/original campaign, no retry or restart chain,
and halt on the first fault. Do not integrate until the CPU proof and ownership
review pass.

Preparation receipt: `data/host-embedding-candidate-prep-01.json`.
The candidate snapshot is preserved as
`patches/host-embedding-candidate-prep-01.patch` before any native CPU run.

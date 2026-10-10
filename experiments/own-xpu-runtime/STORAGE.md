# Weight storage plan — Stage 0, 2026-10-10

No weights were downloaded, moved or deleted. This is a capacity plan and a
metadata inventory. Only the official publisher, Unsloth, or a lab-produced
quant from an official source is admitted by default. Older ISTA, Intel or
third-party download proposals in the [Strata quant note](../../notes/2026-10-10-strata-flash-next-quants.md)
remain research evidence, not an acquisition authorization for this lane.
The [objective](../../docs/own-xpu-runtime-objective.md) supersedes them.

## What is on this host

The [CPU-only receipt](data/storage-inventory-20261010.json) records `steve-b70s`,
UTC time, exact commands and raw output. `du -B1 --max-depth=1` measures
allocated disk bytes, including directories; this is not tensor payload size.
The walk ran at nice 19 with `OMP_NUM_THREADS=2`. It did not hash model payloads.

| Path | Allocated bytes | Decimal GB | GiB |
|---|---:|---:|---:|
| `/mnt/fast-ai/llm-models/.verification` | 36,864 | 0.000 | 0.000 |
| `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8` | 185,565,351,936 | 185.565 | 172.821 |
| `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-hf-tokenizer` | 64,823,296 | 0.065 | 0.060 |
| `/mnt/fast-ai/llm-models/LTX-2.5-baseline` | 71,114,977,280 | 71.115 | 66.231 |
| `/mnt/fast-ai/llm-models` | 256,745,242,624 | 256.745 | 239.113 |

Available bytes at the saved snapshot: **69,929,377,792** (69.929 GB /
65.127 GiB). The root ext4 NVMe is also the `/mnt/fast-ai` filesystem;
there is no independent model partition. Preserving the existing 50 GiB
reserve leaves only **16,242,286,592 bytes** (16.242 GB)
for new work. Other writers can change that immediately; admission must read
`f_bavail` again, not reuse this figure or privileged reserved blocks.

The Flash-Next directory contains the existing official FP8 lane's model.
Its [local config snapshot](data/flash-next-local-config.json) and
[SHA256 receipt](data/flash-next-local-config-receipt.json) describe block-scaled
FP8 with 128×128 blocks and explicit unquantized exclusions. Its 185.565 GB
allocated size does not mean every tensor is FP8. Keep it and the LTX tree
protected; a new loader reads immutable files without changing existing lanes.
The Gemma directory is a tokenizer, not a complete 26B checkpoint.

**Neither Qwen3.8 27B FP8 nor 27B AutoRound INT4 is present under this host's
`/mnt/fast-ai/llm-models`.** No local 27B `config.json` exists there either.
The [27B official metadata receipt](data/qwen27-config-receipt.json) and
[config](data/qwen27-official-config.json) are small remote metadata, not local
weights. The [certified FP8 package](../../packages/qwen38-27b-fp8-tp1-b70/README.md)
pins `Qwen/Qwen3.8-27B-FP8` revision
`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`. Stage 1 needs a later approved
storage destination and verified transfer/acquisition of that identity; this
snapshot makes no claim about what is presently on the other host.

The [historical INT4 package](../../packages/qwen38-27b-int4-fixed-k-tp2-b70/package.json)
uses `devan-carlin/Qwen3.8-27B-int4-AutoRound`. Its existing measurements remain
valid under their original identity, but its third-party origin is not an
allowed new download by default. Use official FP8 for the first runtime;
a later INT4 path needs an allowed release, a lab-produced quant, or the
owner's written exception. Losslessness within a chosen quant is a separate
test from its quality loss versus FP8.

## The “83 GB cleanup” needs a narrower decision

The [October 10 storage audit](../../notes/2026-10-10-storage-inventory.md)
does **not** authorize or propose an unconditional 83 GB deletion. Its whole
quarantine occupies 83,683,561,472 allocated bytes, but the selected primary
recovery is only **42,018,201,600 bytes**. It requires owner approval, a verified
external archive, and proof that the retained good transformer plus the saved
79-byte reverse delta reconstruct every rejected byte. Preserve all previews,
oracles, validation tensors, receipts and logs.

| Quarantine candidate in that audit | Allocated bytes | Decision |
|---|---:|---|
| Rejected LTX transformer | 42,018,201,600 | Primary proposal; proof, archive and owner decision first |
| Rejected Gemma encoder | 26,263,863,296 | Separate optional proof and decision |
| Encoder download prefix | 11,165,241,344 | Separate optional prefix verification and decision |
| Transformer download prefix | 4,236,251,136 | Separate optional prefix verification and decision |
| Sum of these four file candidates | 83,683,557,376 | Arithmetic upper candidate total, not approved recovery |

At this snapshot primary recovery alone would leave
**111,947,579,392 bytes** available, or
**58,260,488,192 bytes** above the reserve. Even all four optional
candidates would leave **99,925,843,968 bytes** above the reserve,
before new writers and preservation work. The 83 GB shorthand in the objective
must not bypass the audit's narrower proof and approval conditions. No cleanup
command was run in Stage 0.

## External cache option

`lsblk` in the receipt identifies **`/dev/sda2`**, label **`CorsairExternal`**,
UUID **`4E0E66ED0E66CD91`**, NTFS, **4,000,768,327,680 bytes** (3.639 TiB,
often shown as 3.6T), with an empty mountpoint. Capacity is partition size,
not free space; free space is unknown until the owner approves a mount.
No mount, repair, reformat, SMART operation or device payload read was made.

The [earlier EX400U review](../../notes/2026-10-06-ex400u-backup-review.md)
and [storage follow-up](../../notes/2026-10-06-storage-and-recovery-followup.md)
treat this disk as an additional backup, not the sole surviving copy of lab
evidence. A later owner decision must cover mount location, driver/options,
permissions, quota/free-space budget and intended use. Prefer immutable,
revision-addressed downloaded files with publisher hashes over a second full
HF cache plus copied working tree. Never overwrite existing backup contents.

NTFS is not itself a ban on file-backed `mmap`; actual loader mapping and
random-read behavior need a bounded CPU test after a mount is approved. Page
faults still require external I/O, and mapped bytes can become resident host
RAM. Do not assume the drive can supply expert streaming at NVMe or PCIe
bandwidth. Sequential read throughput, random lookup latency, sustained writes
and cold mmap faults are all **unmeasured for this plan**. A cache-first design
can later stage just the chosen model onto ext4 when space permits; direct
runtime use requires its own measurements and disconnect/error handling.
Linux's [NTFS3 documentation](https://docs.kernel.org/filesystems/ntfs3.html)
documents permission controls and native journal replay, and warns against
forcing a dirty volume. It does not establish this drive's performance.
No filesystem or power setting change is part of this plan.

### Observed 2026-10-10 (read-only mount by the reviewer)

`/dev/sda2` (NTFS, label CorsairExternal, 3.7 TB) was mounted read-only for
one minute at `/mnt/corsair-ro` and unmounted again. It has **356 GB free**
(3.3 TB used, 91 %) and already holds lab material next to the owner's own
files: `archived-fast-ai-bench-results`, `bench-results`, `hf-cache`, `cache`,
`cache-archive`, 72 top-level entries in all. Nothing was written. Capacity is
enough for the official 27B FP8 (30.9 GB) and one Unsloth Flash-Next GGUF
(82–111 GB) together. Using it as the download cache is the owner's decision;
NTFS mmap and read speed must be measured before any weights are served from
it rather than copied to the NVMe.

## Exact allowed Stage 2 GGUF alternatives

The following metadata was fetched from the
[pinned Unsloth repository](https://huggingface.co/unsloth/Qwen3.8-Flash-Next-GGUF/tree/766911a6b7369840a91dbcd95f9f997acaab6cd6)
at revision **`766911a6b7369840a91dbcd95f9f997acaab6cd6`**.
The [machine-readable allow-list](data/unsloth-flash-next-stage2-files.json)
records API URL, retrieval time, exact bytes and HF LFS SHA256. Hashes are
publisher metadata, **not payload hashes verified by the lab**. All shards in
one selected row-group are required, including the small first shard; filename
size classes are not a complete tensor-grid census. Do not mix revisions or
variants. Fetch only one selected alternative after the storage decision.

| File within the pinned repository | Bytes | HF LFS SHA256 |
|---|---:|---|
| `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00001-of-00003.gguf` | 10,946,624 | `268f81fdedf3149a538f252308927a4d5d1f6e062c178568a51e3b519744f8a8` |
| `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00002-of-00003.gguf` | 49,567,921,344 | `cfe600b236b88c7fad1613a5ca5e83b9f2beb63cbd44c32b2be50a44747c695f` |
| `UD-IQ3_XXS/Qwen3.8-Flash-Next-UD-IQ3_XXS-00003-of-00003.gguf` | 32,382,955,968 | `f1912ba34c79427d2295a58dcb2b732b5931af5bef7a373c60557a57d9ee7250` |
| `UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf` | 10,946,624 | `5ce89370720f8bf90890f439361282104c1aa1482d4013bb9a50923e758e71a4` |
| `UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00002-of-00003.gguf` | 49,835,229,856 | `577a38a2392b40ca2193cea502e1d92f60b8cd370675d308e0ec21885d9daaa7` |
| `UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00003-of-00003.gguf` | 43,836,407,744 | `d4634e6d84f0ebb0940be15c90d3790bf6464e3dea3a1cddc567dc0e83ad8833` |
| `UD-Q3_K_XL/Qwen3.8-Flash-Next-UD-Q3_K_XL-00001-of-00003.gguf` | 10,946,624 | `f2ef4328929d8b8c8930e2856eef52128dd4ce3425302f04bc3c657431cc4c49` |
| `UD-Q3_K_XL/Qwen3.8-Flash-Next-UD-Q3_K_XL-00002-of-00003.gguf` | 49,983,253,824 | `7d230e7c9421d868b89eebaf23033af0ea1a4e046956df00fb156814fb62346e` |
| `UD-Q3_K_XL/Qwen3.8-Flash-Next-UD-Q3_K_XL-00003-of-00003.gguf` | 39,992,153,376 | `21d4f90f9cd7b7c3a1582667c20cb22f7b03de895b88a23bb20aaeaa44f2c199` |
| `UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf` | 10,946,624 | `4448186216b3af4cc558bbce2c3213f01608f8f8b2e5267a9767971dd3ec8082` |
| `UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00002-of-00004.gguf` | 49,859,583,136 | `3f342f1c1580473f1ee94ddd5b28206e8c07a70fa1a366f59d1d6c922919a6c9` |
| `UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00003-of-00004.gguf` | 49,376,141,504 | `56758f40269cad5cd9b0d3d6fbae0f40f6d5be6de49e4ab392dbe83157d9cbd3` |
| `UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00004-of-00004.gguf` | 12,087,983,520 | `753bda48b98ba4f1636134a90a967de1b2d3908a236c026e464777342e53510a` |

| Alternative | Exact GGUF bytes | GB / GiB | Required available bytes under provisional budget |
|---|---:|---:|---:|
| UD-IQ3_XXS | 81,961,823,936 | 81.962 / 76.333 | 145,648,915,136 |
| UD-IQ4_XS | 93,682,584,224 | 93.683 / 87.249 | 157,369,675,424 |
| UD-Q3_K_XL | 89,986,353,824 | 89.986 / 83.806 | 153,673,445,024 |
| UD-Q4_K_XL | 111,334,654,784 | 111.335 / 103.688 | 175,021,745,984 |

The final column is **planning arithmetic**, not a measured installation peak:
`GGUF bytes + 10,000,000,000 bytes staging/receipts/workspace + 50 GiB reserve`.
It assumes direct GGUF reads and no duplicated packed checkpoint. Any full
expert repack, second cache, draft model or additional source checkpoint adds
its actual byte census before admission. Small tokenizer/template/license
metadata must also be pinned in the eventual download packet; the 10 GB
allowance is not permission to omit their hashes. No model payload or GGUF
header range was downloaded here.

UD-IQ3_XXS is the smallest of the three primary objective candidates;
UD-Q3_K_XL and UD-IQ4_XS are alternatives for the owner's quality/capacity
choice. UD-Q4_K_XL is included as the larger quality candidate from the quant
note. This is not a ranking of measured quality: no new quant has passed the
lab's quality gate. The manifest enumerates target GGUF alternatives; MTP
support and tensor presence must be established from the selected GGUF tensor
census before planning an extra draft file. Do not silently fetch optional
vision/projector files for a text-only trial.

Two 32 GB cards do not admit a 82–111 GB download merely because only a subset
of experts is active. Measure expert, dense, embedding/PLE, MTP, scale and
workspace bytes separately; keep BF16/FP16 KV and registered state precision.
Account for the 128 GiB non-ECC host's excluded blocks 53–57, resident mmap
pages, pinned staging, per-card driver shadows, temporary repacks and loader
replicas. No host-memory setting changes, swap workaround or smaller-than-
working-set memory cap follows from this plan.

## Decisions required before acquisition

The owner chooses a destination (and, if applicable, an external mount), the
specific cleanup candidates with their evidence-preservation conditions, and
the first quant plus acceptable quality deltas. Stage 1 also needs the 27B
FP8 checkpoint available at an approved destination. A third-party weight
source requires its own written justification and approval; none is requested
as a prerequisite here. Storage approval does not authorize GPU work: the
existing fault halt and a separate experiment window remain binding.

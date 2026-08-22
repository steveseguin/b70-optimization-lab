# Model intake first wave — 2026-08-21

## Outcome

A 55.30 GiB first-wave queue is ready, but no model bytes were downloaded in
this session because the external USB device was not present in `lsblk`.
`/mnt/usb-models` did not exist and the internal NVMe had only about 12 GiB
free. Redirecting the workload would have endangered active evidence and model
trees, so the downloader correctly remains blocked until the drive is
reconnected.

The queue and immutable artifact identities are in
[`model-intake/catalog.json`](../model-intake/catalog.json). The operator path
is [`model-intake/README.md`](../model-intake/README.md).

## Discovery method

The current-model pass used the Hugging Face text-generation API sorted by
`trendingScore`, captured at `2026-08-22T02:47:17Z` for models created since
2026-08-08. Candidate identities, revisions, sizes, publisher checksums,
licenses, downloads, and likes were then re-read from each model's official
API record. Popularity was used only to prioritize inspection.

External performance reports were treated as leads. They were not used as
model identity, patch provenance, or performance evidence. Existing repository
results were searched before adding anything to the queue.

## Decisions

| Model | Decision | Reason |
| --- | --- | --- |
| Ornith 1.5 35B A3B Q4_K_M | Queue, priority 1 | Official publisher quant, 20.22 GiB, current high interest, and overlaps an unverified external one-B70 family claim. |
| Ornith 1.5 9B Q8_0 | Queue, priority 2 | Official publisher quant, 8.87 GiB, and a strong small single-card candidate. |
| Nemotron 3.5 Lightning 30B A3B UD-Q4_K_M | Queue, priority 3 | Direct claim-validation value; derived Unsloth GGUF avoids assuming NVIDIA NVFP4 runtime support on Intel. License must be reviewed before any redistribution. |
| LFM2.5 2.6B Q8_0 | Queue, priority 4 | Official publisher quant, 2.68 GiB, high download activity, and cheap novice-lane coverage. License must be reviewed before redistribution. |
| Ling 3.0 tiny BF16 | Watch | Attractive recent 15.8 GB repository, but BailingHybrid vLLM/XPU loader support is unestablished. |
| DeepSeek V4 Pro 0813 | Watch | Approximately 893 GB repository; not a responsible first-wave B70 artifact. |
| Qwen3.8 2.4T-A95B | Watch | Approximately 4.89 TB repository; no practical local B70 fit. |
| Qwen3.6 35B A3B | Already covered | B70-tested in the existing community validation and available in multiple stored identities. |
| Muse-Glimmer 30B | Already covered | B70-verified and deeply optimized in the lab. |
| Qwen3.8 27B | Already covered | Active lab family with multiple exact local quantizations. |

## Downloader boundary

[`scripts/model-intake.py`](../scripts/model-intake.py) now enforces:

- an exact 40-character model revision and publisher file SHA-256;
- a separately mounted, writable USB filesystem by default;
- a one-time lab store marker;
- an explicit capacity reserve before any transfer;
- resumable `.part` downloads with tokens kept off the process command line;
- exact size and ordinary SHA-256 before atomic promotion;
- direct-I/O and page-cache SHA-256 agreement after promotion, failing closed
  when cache bypass is unavailable;
- drive-local manifests and verification reports.

This is specifically meant to prevent a missing USB mount from silently
turning the internal filesystem into a model target, and to catch the prior
NTFS/page-cache integrity failure mode.

## Resume

After reconnecting the Corsair drive, follow its health and mount procedure in
[`docs/reference-lab-storage.md`](../docs/reference-lab-storage.md), then:

```bash
python3 scripts/model-intake.py plan --root /mnt/usb-models
python3 scripts/model-intake.py init-store --root /mnt/usb-models
python3 scripts/model-intake.py download --root /mnt/usb-models --all-queued
```

Do not use `--allow-non-usb` to force the internal NVMe. If the existing drive
marker is already present on resume, skip `init-store` and verify that its
recorded source/filesystem still match the intended external device.


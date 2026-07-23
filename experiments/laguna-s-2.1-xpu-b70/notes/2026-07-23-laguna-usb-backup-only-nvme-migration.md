# Laguna USB-backup-only NVMe migration

The active Laguna S 2.1 target and DFlash draft are now on the internal NVMe:

```text
/mnt/fast-ai/llm-models/laguna-s-2.1/int4
/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4
```

The external Corsair `ntfs3` copy remains intact, but it is backup-only. Live
model reads, compiler/model caches, temporary files, logs, run roots, and
recovery evidence must not use `/media/steve/CorsairExternal`. Frozen
historical notes continue to name their original evidence paths and must not be
rewritten as if those runs occurred on NVMe.

## Copy verification

The copy used an isolated `.incoming` directory. It was not promoted to the
final model path until independent relative-path SHA-256 manifests from the USB
source and NVMe destination compared byte-for-byte equal.

| Item | Files | Logical bytes |
|---|---:|---:|
| INT4 target | 100 | 72,021,173,058 |
| INT4 DFlash draft | 18 | 2,229,975,225 |
| Total | 118 | 74,251,148,283 |

Both retained manifests have SHA-256:

```text
45aa105ef4eceaf05cad33012e0752369f77cbbd76f2213ccfe0ce130fa6c0ac
```

They are stored at:

```text
/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/source-files.sha256
/mnt/fast-ai/llm-models/laguna-s-2.1/.verification/nvme-files.sha256
```

The teacher, four-card formal W1 results, aggregate formal/counter summaries,
real M8 timing fixture, and peer binary were separately mirrored under:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1
```

All nine local hashes match the already pinned source hashes.

## Space reclamation

The NVMe initially had only 7.7 GiB available. Exactly six Hugging Face cache
roots were removed, reclaiming 132,578,820,096 allocated bytes (123.47 GiB).
They belonged only to the closed Qwen 3.6 27B lane or the blocked native-XPU
Qwen 3.6 35B FP8 diagnostic. Their repository identities and revisions remain
recorded in Git and in the structured migration packet, so they can be
downloaded again.

No DeepSeek, Gemma, MiniMax, source, benchmark-result, or unique experiment
evidence directory was removed. After the verified Laguna copy, ext4 had
66,551,144,448 bytes available.

## Benchmark disposition

This was storage-only work. No XPU command, model service, model generation,
candidate, or benchmark ran. The current boot remains rejected because the
earlier direct `ntfs3` evidence write produced kernel taint `640`. The local
runner/gate migration must be committed, then the host must reboot before any
GPU work. A distinct no-generation recovery gate must pass before recovery A1,
which remains the first subsequent model generation.

Structured packet:
[`data/laguna-s-2.1-nvme-model-migration-20260723.json`](../../../data/laguna-s-2.1-nvme-model-migration-20260723.json).

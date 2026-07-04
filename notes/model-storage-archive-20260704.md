# Model Storage Archive - 2026-07-04

Root storage was tight (`/` at 95%, about 51G free) during the rapid model
snapshot pass. Three inactive Qwen-family model directories were archived from
NVMe to the 4TB USB model store, then replaced with symlinks at their original
paths so old scripts and notes still resolve.

Archived and verified by file count plus total file bytes:

| Original path | USB target | Files | Bytes | Reason |
| --- | --- | ---: | ---: | --- |
| `/mnt/fast-ai/llm-models/qwen36-27b-awq-int4-cyankiwi-8f269fb` | `/mnt/usb-models/llm-models/qwen36-27b-awq-int4-cyankiwi-8f269fb` | 18 | `20467236253` | Qwen27 AWQ screen was strict-valid but closed no-win versus the webhie/BF16-scale record. |
| `/mnt/fast-ai/llm-models/qwen3.6-27b-fp8-vrfai` | `/mnt/usb-models/llm-models/qwen3.6-27b-fp8-vrfai` | 22 | `35943229065` | Inactive Qwen27 FP8 candidate; preserved for future Qwen3.6 work without keeping it hot on NVMe. |
| `/mnt/fast-ai/llm-models/qwen3.6-35b-a3b-int4-autoround-abhinand` | `/mnt/usb-models/llm-models/qwen3.6-35b-a3b-int4-autoround-abhinand` | 48 | `22126166760` | Inactive Qwen35 AutoRound candidate; preserved for future Qwen3.6 work without keeping it hot on NVMe. |

Post-move state:

- `/` improved from about `51G` free to about `124G` free.
- `/mnt/usb-models` remained healthy at about `2.7T` free.
- Gemma 4 26B Q8 stayed on NVMe at
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf`; do not move it unless a
  deliberate hot-path symlink/service update is made.
- MiniMax model directories were not moved because they are tied to the stable
  service/reference setup.

If USB access is unavailable, any script that resolves one of the three
symlinked Qwen paths will fail at model load time. Restore by either mounting
`/mnt/usb-models` or copying the target directory back to NVMe and replacing
the symlink with the restored directory.

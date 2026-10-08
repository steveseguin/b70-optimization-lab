# Flash-Next Screen 1 (MTP1): host out-of-memory during load; one GPU fault during the kill

Run `reopen-20261008/runs/screen1-mtp1`, unit `flashnext-screen1-20261008T095938`,
image `vllm/vllm-openai-xpu@sha256:e4446310…` (vLLM 0.30.0, official XPU kernels),
31 pinned Lumnus Python overlays, unchanged 131-shard FP8 model (full tree hash passed,
`model-verification.json`).

## What happened

- 13:59 UTC: admission passed (113 GiB disk free, render nodes idle via the privileged scan).
- 14:02–14:04 UTC: engine init; `UVAOffloader` selected; Triton FP8 MoE backend; GDN decode
  kernel "cuda" path; PLE embedding initialised as `Qwen4ExpPLEFp8EmbeddingMethod` on all
  four workers; "Loading model from scratch".
- 14:04:34 UTC (kernel): on `xe 0000:43:00.0`, `Fault response: Unsuccessful -EBUSY`, then
  `Engine memory CAT error [18]: class=bcs`, `Engine reset: engine_class=bcs`, `Timedout job …
  in python [757795]`, followed by more `-EBUSY` fault responses until 14:04:42.
- 14:04:51 UTC (kernel): global OOM; `Killed process 757710 (VLLM::Worker_TP) total-vm 38.2 GB,
  anon-rss 12.6 GB`. systemd: unit "killed by the OOM killer", memory peak **67.9 GB** in the
  unit alone; container exited (1); controller sent one SIGINT; no retry.
- 14:31:18 UTC: four-card health probe **passed** (`postflight-after-oom.json`); zero
  render-node holders. Owner rule applied: one fault + passing probe → continue, record it.
  **A second fault on this boot requires the owner's reboot decision.**

## Why

The stock 0.30.0 FP8 path does not fit this host's 115 GiB RAM: four workers each take
≈12.6 GB anon RSS plus the generic UVA weight offload (~16 GiB per rank pinned) plus the
pinned PLE table, on top of page cache from the 185 GB model hash. The certified 46.85 tok/s
line fits only because of the lab's placement/PLE patches (bounded rank-serialised loading,
host expert rows callable, selective offload), which Screen 1 deliberately did not port
(Codex analysis §4). The copy-engine fault is consistent with host-memory pressure while
the bcs engine was moving weights into pinned memory as the process was being killed; it
is not evidence of a hardware regression (probe clean), but it is a fault on the card with
lockup history, so it counts.

## Evidence

`server.log`, `client.log` (empty: no request was sent), `launch.json`, `image-inspect.json`,
`runtime-versions.json`, `graceful-stop.json`, `model-verification.json`,
`kernel-oom-and-fault-window.log`, `postflight-after-oom.json`, exited container
`flashnext-screen1-screen1-mtp1` (retained).

## Next

No second launch of this configuration. Screen 1b needs a host-memory fit first: port the
lab's offload/PLE placement semantics onto V30, or compute a fitting offload budget, with a
predicted host RAM ≤ 90 GB before admission. Codex is producing that analysis.

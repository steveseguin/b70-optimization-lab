# Qwen3.8 Flash-Next FP8 partition/device replicate A1 preflight negative

Date: 2026-08-31
Status: orchestration negative; no tensor work

A1 stopped on its first partition-1/device-1 arm before tensor allocation.
The runner combined `ONEAPI_DEVICE_SELECTOR=level_zero:1` with
`ZE_AFFINITY_MASK=1`; the second selector acted on the already-filtered device
list and exposed zero XPUs. The tool failed at `torch.xpu.set_device()`.

No model-server process, full checkpoint load, timing cell, or performance
result exists. The partial evidence remains at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-ep4-partition-device-interaction-replicate-a1`.
A2 uses the same frozen cells and interpretation on a fresh evidence root and
unsets the redundant affinity mask.

# Qwen3.8 Flash-Next FP8 EP partition/device interaction replicate

Date: 2026-08-31
Status: A2 frozen component-only correction before launch

Independent review found that the first four-rotation Latin square could not
distinguish a transient timing event from a stable partition-1/device-1
interaction because each mapping had only one fresh-process observation. This
replicate tests that cell four times, bracketed in rotating order by the same
partition on device 0 and partition 0 on the same device 1.

Every arm uses exact layer-0 checkpoint weights, the accepted M1 eight-warp
map, the same hidden fixture and top-10 route IDs, 20 warmups, and 15 batches
of 200 invocations. It records the exact runner, commands, source heads,
checkpoint-shard hashes, selectors, and physical device/BDF discovery in the
external evidence root. The stable-interaction rule is frozen as
partition-1/device-1 exceeding the slower matched control by more than 5% in
at least three of four cycles. Output hashes must remain exact within each
expert partition.

This run performs no model-server launch, full checkpoint load, endpoint
change, or reboot. A positive interaction result permits only considering a
static rank-map component follow-up; a negative closes the original
rank-reordering hypothesis. Neither outcome changes protected throughput.

Attempt 1 stopped on the first arm before tensor allocation because combining
the global `ONEAPI_DEVICE_SELECTOR=level_zero:1` with
`ZE_AFFINITY_MASK=1` filtered the already-selected device a second time and
left zero visible XPUs. Its partial receipt is retained externally as an
orchestration negative. A2 changes only the evidence root and unsets the
redundant affinity mask; a four-device preflight confirmed that each explicit
oneAPI selector exposes exactly one B70 as local `xpu:0`. All workload and
interpretation fields above remain unchanged.

The final A2 runner SHA-256 is
`4c601a3455e20dec0b47ccb0c84375b13606287616784a32955028bb59dedd06`.
It verifies the exact 18-file serving stage, source commits, tuned map, local
checkpoint shards, and four physical device IDs/BDFs before creating evidence.

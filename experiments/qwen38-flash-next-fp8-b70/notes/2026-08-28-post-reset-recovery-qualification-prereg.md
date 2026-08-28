# Flash-Next post-reset recovery qualification preregistration

Date: 2026-08-28

## Purpose and boundary

Requalify the four B70s after the MTP4 active-2K teardown window recorded one
compute- and one copy-class reset on every card. Device rediscovery and low
idle memory are not sufficient. This recovery program grants no model-matrix,
speed, quality, or deployment credit and cannot change any captured result.
It only decides whether a later separately preregistered GPU arm may start.

No driver reload, PCI reset, reboot, model launch, or serving request is
authorized by Stage A. Stop immediately on any missing device, per-card smoke
failure, collective failure, timeout, new B70 reset/fatal event, or residual
workload ownership.

## Frozen Stage-A identity

- repository `main` at or after the MTP4/2K closeout commit `fecff8891`;
- `/home/steve/.venvs/vllm-xpu/bin/python`, Torch `2.11.0+xpu`;
- `scripts/check-qwen36-xpu-xccl-health.sh` SHA-256
  `b15dd4c248d8c4d7035c2d180b9ecc5354b1b20bdabb0c47c540b5003a1cfb78`;
- `tools/xccl_probe.py` SHA-256
  `6ecd340651a6780fdbe0bd57d346540efe168bf2e3175d54e10dd8660ed5b30a`;
- physical devices and XCCL devices exactly `0,1,2,3`, four ranks, 120-second
  collective bound;
- output root
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reset-recovery-qualification-20260828-stage-a`.

## Ordered Stage-A gate

1. Require a clean `main`, free host/GPU locks, no serving/benchmark process,
   no relevant listener, four expected B70 discovery records, and low idle
   memory. Capture a kernel-journal cutoff before active checks.
2. Run exactly one small Torch allocation/add/reduction/synchronization check
   on each physical card. Require `device_count 1` and `ok 2097152.0` for all
   four checks.
3. Run exactly one four-rank XCCL all-reduce with the accepted OFI/P2P settings.
   Require barrier completion and `rank 0` through `rank 3` each reporting
   `allreduce ok 4.0`.
4. Capture discovery, stats, ownership, and the kernel journal through the end
   of the check. Require no new B70 reset/fatal event and no residual check
   process.
5. Hash every durable Stage-A artifact. A Stage-A pass authorizes only the
   separately preregistered known-good generation canary; it does not authorize
   an unbounded matrix launch.

## Stage B and resumption rule

Stage B must use a known-good Flash-Next TP4/EP4/eager/MTP0 configured-512
identity, a fresh lifecycle controller, one cache-zero deterministic generation
canary, bounded clean shutdown, and a bounded journal window meeting the
frozen B70 criterion. Only a complete
Stage-A plus Stage-B pass restores permission for the next matrix arm. A
failure remains evidence and requires assessment; it does not trigger an
automatic reload or reboot.

## Stage-A result

Stage A stopped at the collective gate. All four per-card checks passed with
one visible device and the exact `2097152.0` reduction result. The helper then
forced its historical default `FI_TCP_IFACE=eth1` and
`CCL_KVS_IFACE=eth1`. This host has `lo`, `eno1`, `eth0`, and `docker0`, but no
`eth1`; oneCCL therefore rejected transport initialization before the
all-reduce. The helper returned `1`, no model canary ran, final device memory
was 42.875-42.879 MiB, and the bounded journal contained no new B70 event.

This is a failed recovery-control configuration, not a recovery pass and not
evidence of a card failure. The attempt remains immutable at the external path
above. Its `evidence.sha256` manifest hash is
`c82dcf7d673d17ef0d2edb63ba3c11c1c10b719aee9e9e0b59ca09c9472c2c76`.

## Separately registered Stage-A2 correction

Stage A2 changes only the two transport-interface environment values to the
Flash-Next launcher's accepted `lo` identity:

```text
FI_TCP_IFACE=lo
CCL_KVS_IFACE=lo
```

All hashes, devices, ranks, per-card checks, OFI/P2P settings, bounds, pass
criteria, stop rules, and evidence requirements remain unchanged. Its distinct
output root is
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/post-reset-recovery-qualification-20260828-stage-a2`.
The first failed attempt is not overwritten. Stage A2 may authorize only the
separately registered Stage-B known-good generation canary.

## Stage-A2 result

Stage A2 passed every recovery-control gate. Each of the four isolated card
checks again returned exactly `2097152.0`. The corrected four-rank collective
reached the barrier on ranks 0 through 3 and every rank returned exactly
`allreduce ok 4.0`. The helper returned `0`; the bounded journal contained no
new B70 event; no check process or listener remained; and final device memory
was 42.875-42.891 MiB. The immutable external evidence manifest has SHA-256
`71ad49fa601ebe90516997c35aefc1357a3a0d5727dda8f0e5d2d99733ae0478`.

Stage A2 authorizes only Stage B below.

## Frozen Stage-B identity and gates

Stage B is a functional recovery canary, not a performance, matrix, quality,
or deployment measurement. It cannot replace, lower, or add to any captured
throughput row.

- base launcher:
  `tools/launch-tp4-ep4-eager-mtp0-512.sh`, SHA-256
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- model: local-NVMe `Qwen3.8-Flash-Next-FP8`, sealed revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- accepted current overlays: vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`,
  kernel source `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, and staged
  MTP0 runtime build `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- server identity: TP4/EP4, Triton MoE, eager, MTP0, configured length 512,
  cache 201326592 bytes, one sequence, 64 batched tokens, selective UVA
  offload of PLE embedding and token embedding at 12.25 GiB per rank;
- unique output identity: attempt 28 below the Stage-B recovery root, port
  19666, and fresh compile, runtime-cache, and RPC paths;
- one request only: `Reply with exactly: OK`, thinking disabled, temperature
  0, top-p 1, seed 20260609, and at most 8 output tokens;
- required oracle: HTTP 200, model identity match, normal stop, normalized
  `OK`, SHA-256
  `565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3`,
  exact usage 17 prompt / 2 completion / 19 total, and zero cached or created
  cache tokens;
- the oracle comes from the MTP0 official-quality attempt 2 control on the
  same accepted vLLM overlay, whose exact-OK case recorded the same output,
  hash, usage, and cache counters. This Stage-B canary does not inherit that
  run's benchmark or quality credit;
- client request bound: 180 seconds; overall server lifecycle bound: 1500
  seconds; stop only after the complete canary receipt is durable;
- require descendant-aware clean shutdown, no process/listener/temporary-path
  residue, four-card rediscovery at idle memory, and no new B70 reset or fatal
  event in the kernel-journal window.

The descendant-aware supervisor SHA-256 is
`2b2a172a94fc23d910e99ea7bbf73200aeb59ee902176e660cb9c1e8fcfe28c4` and
the one-request client SHA-256 is
`5790945842fd3a6c6c7e599df7fbbc6b69b1de40d46d9848ed53939508410f6e`.
They are frozen after review and before execution. A complete pass restores
permission only for a separately preregistered next matrix arm. Any failed
gate remains evidence and stops the program without an automatic reload or
reboot.

## Stage-B result and adjudication

Stage B passed the frozen B70 recovery gates. The accepted current-source
TP4/EP4/eager/MTP0 server loaded all 131 local-NVMe shards, reported exact
12.22-GiB selective offload on all four ranks, exposed 1,536 cache tokens, and
became healthy. Its sole authorized request returned HTTP 200, normal stop,
exact `OK`, the frozen output hash, exact 17/2/19 usage, and zero cache reuse in
6.743679 seconds. That elapsed value is diagnostic only and grants no speed,
quality, matrix, or deployment credit.

The exact stop sentinel reached launcher cleanup. The supervisor returned
zero; all four workers logged shutdown completion; the API logged application
shutdown completion; and the recorded server process group, listener, compile
path, and RPC path were absent. Exact four-card rediscovery passed at
42.875-42.887 MiB. The journal capture returned zero and contained no B70
reset or fatal event.

The journal was not literally event-free: one APEI record contained two
corrected physical-layer receiver sections for Samsung root-NVMe endpoint
`0000:01:00.0` during checkpoint loading. This is preserved as a storage
caveat, not mislabeled as a clean-host pass. The preregistered B70 recovery
criterion nevertheless passes and authorizes one separately preregistered
matrix arm with its own explicit storage rule. It does not authorize changing
or lowering any captured result. The raw Stage-B manifest SHA-256 is
`ead08469683d6af825924dbdec8975d9af8ce5f024f247956464b69a93de22da`;
the compact tracked receipt is
`data/20260828-post-reset-recovery-qualification-result.json`.

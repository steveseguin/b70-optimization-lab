# Qwen3.8 Flash-Next HC-up M>1 packed-fallback S1 preregistration

Date: 2026-08-31

Status: frozen before XPU execution

## Question

The all-97 M1 screen authorized a grouped-GEMM source-integration candidate,
but the endpoint cannot retain a duplicate 635.7 MB HC-up weight bank. The
single-storage integration therefore stores each logical `[10240,320]` weight
as a view of packed `[1,320,10240]` storage. A focused one-XPU lifecycle test
proved that the grouped M1 result is exact, reloadable, and fresh-output safe.
That same test also found that ordinary `F.linear` over the packed transpose at
M2 is not byte-exact to contiguous-weight authority. The source treatment now
fails closed for every non-M1 input.

S1 asks which packed-storage provider, if any, can serve both a small non-M1
shape and the production chunked-prefill M64 shape without changing bytes.

## Frozen scope

The S1 plan contains exactly eight isolated arms:

- real checkpoint weight `00-attn`;
- token shapes M2 and M64;
- providers `authority`, `packed_view`, `matmul`, and grouped E=1;
- one fresh process per arm on one selected B70;
- repeat `r1` only. A second repeat requires a clean, useful S1 result.

Cross-provider byte differences are classified per provider and do not abort
the remaining arms. Non-repeatable, non-finite, mutated, misidentified, or
over-budget arms fail closed. No S1 outcome authorizes source promotion,
endpoint launch, or a performance claim.

## Frozen identities

- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- source integration commit: `8c247a52fc6003629184b38b29ab6e68a91d265f`;
- exported patch:
  `patches/qwen38-flash-next-fp8-b70/vllm/0032-Add-guarded-Qwen-HC-grouped-up-integration.patch`;
- exported patch SHA-256:
  `827c54a68ee9173dfc1ad7b1a94f06552af6f1525f04e79738f28445a6785303`;
- worker SHA-256:
  `68e6ce3c8fff671764805773c5502288839f6434273f42a0ca6cdc09b219cb8a`;
- driver SHA-256:
  `3df253d8e0588db0a5cdfb89f975b070ff1fc849e42986a1eaf466bee29493e1`;
- S1 plan SHA-256:
  `506079e2caebbc9a6313d6dc4e7a0b44b697952ade295202abbd55b5a54d648b`.

The driver authenticates the model/index/config, 97-weight authority manifest,
component runtime and normalized loader/SYCL closure before and after work. It
requires the checkpoint on local NVMe, the evidence root on `/dev/sda2`
`fuseblk`, sufficient host/swap/XPU/evidence capacity, no active server or
other render owner, and immediate mount verification before every evidence
link. Each arm preserves stdout, stderr, process receipt, JSON digest, parent
PID, and nonce. Evidence is never overwritten.

Expected evidence root:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s1-r1-seed20260831`

Frozen command:

```bash
experiments/qwen38-flash-next-fp8-b70/tools/run-hc-up-mgt1-packed-fallback-gate.py \
  --scope s1 --repeat r1
```

This run performs no reboot, server launch, or full-checkpoint load. It streams
one 6.25 MiB weight at a time and caps each arm's peak XPU allocation delta at
512 MiB.

## Frozen interpretation

- `packed_view` is accepted only if byte-exact at both M2 and M64; the earlier
  synthetic M2 mismatch makes rejection the prior expectation.
- `matmul` or grouped may proceed only if byte-exact, finite, repeatable, and
  non-mutating at both shapes.
- Timings are descriptive because provider order is fixed. A provider that is
  exact in S1 still needs separately bracketed timing and the S2/S3 real-weight
  coverage before source integration.
- If no packed provider is exact at both shapes, stop endpoint work and design
  a different single-storage phase/dispatch treatment. Do not weaken the byte
  gate and do not restore a duplicate endpoint bank.
- Protected `5.515783 tok/s` MTP0 target-only and approximately `20.727 tok/s`
  MTP4 results remain unchanged.

# Laguna shared-down native M=8 counter execution authorization

Date registered: 2026-07-23 America/Toronto

Status at registration: the four-card component gate passed, the dedicated
cold-counter runner/fixture/analyzer are committed and hash-frozen, their
CPU-only tamper suite passes 85 tests, and two independent audits report PASS.
No cold hardware-counter capture, endpoint service, model generation, payload,
or LocalMaxxing submission has occurred under this authorization.

This note authorizes only the frozen four-card counter campaign described in
[`data/laguna-s-2.1-shared-down-m8-counter-authorization-20260723.json`](../../../data/laguna-s-2.1-shared-down-m8-counter-authorization-20260723.json).
The packet authorizes counter execution and keeps endpoint execution, model
generation, payload creation, and submission false.

## Frozen lineage

- main tool commit:
  `d4823283d4cdeade547eceefd48aca3e7d880c64`;
- vLLM:
  `75d4660463407975c16bd33711499ca560bf2034`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- PTI source:
  `a5bab309f4ffdd78bd127035c46f5f75371160f8`;
- passing component aggregate:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-component-20260723T155703Z/aggregate.json`;
- component aggregate SHA-256:
  `ea71971b368ce9b9e930577b673e983124b0e5686d5d780fc241ac4104f2a1d6`.

The live model/config and every output, cache, temporary, and evidence path
remain on `/mnt/fast-ai`, whose frozen identity is `/dev/nvme0n1p2` `ext4`.
The Corsair external USB drive is not a live input or output.

## Frozen tools

- runner:
  `40c9efc61301527f439f247cc65d8c27122aa5baa0564e6ca8520cc9a10ba282`;
- fixture:
  `526552313e119f8076d79e6816e8d3215f5bbdb006b424527f70eca7a58ff7a3`;
- analyzer:
  `d3b8472556b558d92a2e73617ed7d968e03920126af71cba67719dae8f73fa24`;
- CPU tamper tests:
  `a503f180cf9923e790e37ac3d7e2bcbe36631426f20801cd2d4b0d31ffd34e3a`;
- component gate:
  `df8496f1f405e8b786dff0b96b7c320944c5d0133cce0bfcc2e36150ab1e0f12`;
- component analyzer:
  `945810c50eeeea99f532c3e62ee5bf289677e3706d80965f966400bfab35911b`;
- `unitrace`:
  `5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`.

The packet also pins Python, Torch/XPU shared libraries, runtime extension
binaries, the model config, `sudo`, `env`, `timeout`, `kill`, `xpu-smi`, the
boot ID, physical UUID/BDF/DRM mapping, exact record environment, and the
complete profiler command template.

## Counter protocol and stop boundary

Run physical cards 0-3 sequentially. Each card runs fresh private processes in
the fixed order A1 control, B1 candidate, B2 candidate, A2 control. Every arm
performs 13 selected completion-bounded calls with a 128 MiB eviction touch
before every call. Discard selected rows 0 and 1 and reduce the remaining 11.
Each arm uses a private local-NVMe `HOME`, cache, and temporary tree.

The analyzer requires raw-exact outputs across all 16 arms; exact source,
device, fixture-PID, profiler-output, and manifest closure; both matched
candidate GPU times below control on every card; per-card aggregate GPU time
below control with the frozen memory/LSC/stall/active/occupancy guardrails; and
the global four-card candidate GPU-time aggregate below control. All validity,
split, overrun, lost/inconsistent, spill, SLM, partial-write, and LSC-write
proxies must remain zero.

Any failed preflight, profiler arm, evidence closure, raw hash, matched pair,
guardrail, or global comparison is
`counter-failed-stop-before-endpoint`. A pass authorizes only construction and
audit of a separate endpoint preregistration. It does not authorize an endpoint
run or model generation.

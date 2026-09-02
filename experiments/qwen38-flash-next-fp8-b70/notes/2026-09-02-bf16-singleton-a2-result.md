# Flash-Next BF16 singleton A2 result

Date: 2026-09-02
Status: complete; bounded repeatability negative

## Result

The A2 diagnostic reproduced the Phase-1 first-cell failure in two fresh
one-B70 processes and localized it to the active output of the exact real
layer-0 attention HyperConnection down/inject projection. The reconstructed
BF16 weight was `[336,10240]`, the input was `[1,10240]`, and the first 324
output columns are consumed by production. Repeated `F.linear` calls changed a
small number of those active BF16 values even after warm-up, per-call XPU
synchronization, and immediate CPU snapshots.

This is a valid bounded negative for this exact M=1 provider/shape. It is not
evidence that every BF16 dense family varies, and it does not by itself prove
that an endpoint token changes.

## Discriminators

- Replica 1: the cold pair differed at 9 elements in 8 rows; immediate warm
  comparisons differed at 9--11 elements; deferred warm comparisons differed
  at 6--10 elements. Maximum difference was one BF16 ULP for the largest
  changed value.
- Replica 2: the cold pair differed at 10 elements; immediate warm comparisons
  differed at 7--10; deferred warm comparisons differed at 7--12. Maximum
  difference occasionally reached two BF16 ULPs.
- Synthetic padding columns 324:336 remained byte-exact zero in every arm.
- Input, weight, provider, runtime, and static identities matched across both
  processes. Child and parent postflight checks passed, with four B70s, no AER
  events, clean SMART, about 125 GiB available, and all swap free.
- The eight preselected focus rows happened to be stable across 20 repeats;
  full-order sweeps found sparse changes elsewhere. Recurrent coordinates
  included `(221,80)`, `(205,84)`, `(148,204)`, `(148,264)`, `(114,189)`, and
  `(78,63)`.

The result rules out a cold-only setup effect, delayed-buffer lifetime, result
concatenation/hash handling, and synthetic padding as explanations. It leaves
an exact warmed M=1 BF16 linear/provider repeatability failure in active output.

## Evidence

Raw evidence root:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/bf16-singleton-diagnostic-20260902-a2`

- summary SHA-256: `58b9d94c10cc27f0d16ee7e671988bb50a85308d518ee6fd739dfe913ee99325`;
- replica 1 SHA-256: `29d5114a2e969300c328945ea802041bf04e1d719712f00aae57f71ad07f6a7e`;
- replica 2 SHA-256: `3378ac4143c85249a9407eb559ba1e52711682bbba536fc510a91915f7b14c57`;
- service-log SHA-256: `85cd3273eee9767246e467561252d568621ec791c2f5a9c32b4fee1963600232`.

The independent post-run audit passed and recomputed the summary from the raw
replicas.

## Decision

Do not resume the unchanged 168-cell Phase-1 census: its exact-singleton
authority premise fails at its first cell. The next bounded A3 component test
uses the same tensor in two fresh processes, retains the complete 256-row call
order, targets the strongest unstable rows, compares consecutive and
original-ordinal execution, and separately tests
`torch.backends.mkldnn.deterministic=True` while recording exact outputs and
latency. No reboot or full-model load is required.

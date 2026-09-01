# Qwen3.8 Flash-Next FP8 A55 bounded local-read preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A54 reached a healthy endpoint and passed recovery, then its supervisor stopped
when normal local-NVMe runtime reads exceeded the inherited 4-GiB allowance by
2,064,384 bytes. Memory, swap, pressure, corrected-event, root-port, fatal-link,
and B70 gates remained within their bounds.

A55 changes attempt `54` to `55`, port `19726` to `19727`, and the corresponding
run, cache, compile, RPC, temporary, supervisor, and lifecycle paths. Its sole
policy change raises the local-NVMe read allowance from 8,388,608 to 16,777,216
sectors (4 to 8 GiB). This remains below five percent of the 173-GiB checkpoint
and therefore still fails closed on an accidental local checkpoint load.

Model, external checkpoint and tokenizer, source/runtime/kernel identities,
TP4/EP4, MTP0, synchronous PLE-only placement, full decode graph, graph-safe
oneCCL `twoshots`, KV capacity, prompts, authorities, diagnostics, client order,
and the complete losslessness battery are unchanged. The 16-million-KiB loaded
memory floor, swap-off requirement, PSI limit, corrected-event allowance of 64,
zero root-port delta, fatal-event classifier, cleanup, and four-card postflight
also remain unchanged. No reboot or per-boot load rule applies.

## Frozen packet

- derived launcher SHA-256:
  `85eeb5312e884813862dea86a895ce4c5838605f931b26b6452b6b0d130feb3a`;
- launcher SHA-256:
  `acc6c5590f5c49fc979405235b62a2ef3540a63e6c4d960bbef31d1c05422c66`;
- client SHA-256:
  `d3289f938ee6d0ec59581b5c660a4c7f1503c780dac85a96ca8d24245acaa5ed`;
- supervisor SHA-256:
  `ada6baf29edec39fd91b2b69c8819083cb529f915fa99900509db1aa200b0020`;
- privileged host wrapper SHA-256:
  `e70543b364a3f76ca74a9f04a32bf67fd7031b30de05c020ebf1c001c6a6006e`;
- rewrite helper SHA-256:
  `d8c1b6ecd14a2da862d2f0edf70a85841fafafedd5c8ccdf9c4895667f4cb653`.

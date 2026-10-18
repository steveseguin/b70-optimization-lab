# Packet145 boundaries and novelty

- Packet104/104b router tile16 (1.026424), shared Q6 tile16 (0.950510), and
  shared gate/up tile16 (1.496321) are closed. This changes allocation/consumer
  order only, never row transpose, addressing arithmetic, or reduction order.
- Packet112 altered route probability selection. This keeps selected route-fast
  unchanged and changes only immutable GEMV weight placement.
- Packet140 lacked a supported >=0.412758 ms/half standalone lever. Packet141's
  new cold/in-order versus repeated-kernel attribution supplies this distinct
  locality hypothesis: router 1.86× and gdn.z 1.30×. Neither is an engine speedup.
  Combined effects with separately queued attention are unmeasured.
- Packet142 attention-order600 mixes gdn.z with other projections under one
  prefix budget. This dedicated gdn.z bank reaches its whole admitted class;
  router was absent from packet142's candidates. Packet142 is frozen.
- Require complete fused router tuples. A partial-plan or missing member refuses.
- Allocation order does not prove physical adjacency or better cache behavior.
- CPU row/capture proofs are not device output or performance evidence. No model
  payload or GPU may be read during this preparation. Keep full precision KV.
- Readiness is scoped by lane and variant. Never use a B smoke to admit A.
- Do not inherit packet142's recovered-smoke exemption or parent readiness.
- Keep the 25 GB root-free floor, 300 MB build cap and 4 GiB CPU process cap.

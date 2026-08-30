# Qwen3.8 Flash-Next FP8 A25 fresh inner-trace preregistration

Date: 2026-08-30
Status: frozen; explicit fresh-host reboot authorization still required

## Question and ordering

A25 is the required fresh-start peer for A24's rank-0 64-record, 171-tensor
inner PLE trace. It must be the first and only Flash-Next full-model load in
the next boot. No process-offload server or performance arm may precede it.
After its frozen battery completes, the ordered trace comparator will report
the first tuple whose label, tensor name, dtype, shape, element count, or
SHA-256 differs from A24.

The comparison authority is A24 trace SHA-256
`1f729de92da4f4355d1009c185300a95255978fb1a0222e457330eb5e6e6be23`.
The comparator requires exactly 64 ordered records and 171 tensor tuples from
both traces. A same-server output match is not sufficient for promotion; A25
is diagnostic until the cross-start authority and full quality gates agree.

## Frozen identity

A25 uses attempt 25, port 19697, isolated run/cache/compile/RPC/supervisor
paths, the validated local NVMe checkpoint, TP4/EP4, eager target-only MTP0,
max model length 4352, 128 MiB KV-cache allocation, selective PLE-only 12.0 GiB
UVA placement per rank, and the A24 prompt/order/quality/performance battery.
The launcher requires at least 120000000 KiB `MemAvailable`, 8000000 KiB free
swap, and 220000000000 free NVMe bytes. An atomic per-boot marker rejects a
second full load.

The vLLM identity is
`ca20c4465ca34fc733aac70416b75d7cb8a1c46f`, four commits after A24's
`f69a0ef46338f93636671c87caa527b3ac2ca129`. Patches 0027--0030 repair the
separate process-offload candidate: GPU-placeholder coverage, bounded XPU host
semaphores, index-filtered CPU-worker checkpoint loading, and strict isolation
of filtered-mode bookkeeping from ordinary loading. A25 explicitly
requires `VLLM_PLE_CPU_OFFLOAD` to be absent and remains on the A24 UVA path.
The new placeholder, host-semaphore, and filtered-loader paths are therefore
dormant and change no A25 inference arithmetic, scheduling, placement, or
performance selector. The source-identity difference is nevertheless recorded
rather than described as byte-identical.

## Frozen files

- launcher SHA-256: `170f5d282c52188f803e7112c9d9ca77595a1bb29963a3457b7fe8d03d32e77f`;
- client SHA-256: `be4cd1d7f15669a71061e3a7567d796431bc37a624f9026e12eb3418a5818f65`;
- supervisor SHA-256: `b5679192ae6a965ef78196bbad24b17494a8080241d0dab42de39e6e55af3fd3`;
- comparator: `tools/compare-qwen4-exp-inner-traces.py`, SHA-256
  `62fda53f04bb5ace7d489b61862b655d649dd19f3aa4b0a6d949966eec26cb2f`.

All three wrappers pass syntax and source-only derivation checks in about one
second and reject the already-used A24 boot. The rank mode remains labelled
`all` for continuity, but only rank 0 is required or claimed because A24
produced no rank 1--3 files.

After A25 teardown, run the comparator exactly once as:

```bash
python3 experiments/qwen38-flash-next-fp8-b70/tools/compare-qwen4-exp-inner-traces.py \
  /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt24/qwen4-exp-late-prefill-rank0.json \
  /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt25/qwen4-exp-late-prefill-rank0.json \
  --require-records 64 --require-tensors 171 \
  > /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt25/a24-a25-inner-trace-comparison.json
```

Exit 0 means identical traces; exit 1 is an expected diagnostic outcome for a
well-formed first mismatch. Exit 2 or a requirement mismatch invalidates the
comparison.

## Frozen interpretation

- Exact A24/A25 trace match plus all authority/quality gates: the observed
  fresh-start output difference lies after the traced PLE layer boundary.
- First inner-trace mismatch: localize the first differing PLE-stage tuple and
  change only the implicated implementation in a later arm.
- Missing/malformed trace, host interruption, output-authority failure, or
  lifecycle failure: preserve as a bounded negative; do not promote speed.
- Historical 5.515783 tok/s target-only and 20.727 tok/s MTP4 observations are
  protected and cannot be lowered or rewritten by A25.

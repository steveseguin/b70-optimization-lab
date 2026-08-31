# Qwen3.8 Flash-Next FP8 97-weight HC grouped-GEMM preregistration

Date: 2026-08-31
Status: frozen before candidate execution

## Question and boundary

The hot-weight alternating gate measured a large exact component win, but it
did not exercise production weight switching. The target MTP0 path contains 97
sequential up projections totaling 635,699,200 bytes: attention and MLP
hyperconnections for layers 0--47, then the final mixer. This gate measures
that exact sequence as 97 separate E=1 calls; it never batches them as E=97.

This remains a one-B70 component test. It performs no reboot, server launch,
full checkpoint load, endpoint request, or change to protected results. A pass
authorizes only an opt-in source-integration candidate followed by a separately
preregistered endpoint A/B. It cannot establish a decode-speed claim.

## Frozen authority and identity

- control-only raw evidence SHA-256
  `15af5344c259fa83ffc16ca1755c621a83cce01651119b2c5234c4276a2fcab9`;
- 97-weight manifest SHA-256
  `da68ed6ed1fa5dba536bd5881799972c6ce079a55a2ca82e1ec8832520a8a5f7`;
- 97-slot input/output authority manifest SHA-256
  `78d773b0a4387e2396828c3b360983ab79051f871065377aaf8dba3ef3b1c91e`;
- model revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, index
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`,
  and config
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- isolated grouped stage manifest
  `71e263f19ccc1313bbdc21604b4de5171891454fb7e8e35877af083505522951`
  with exact SYCL 8 loader closure;
- candidate tool SHA-256
  `7199b1c070abb4fdbb1a62ad92c4caed4ef5d2b1c9e3f80feaaf91af8fc7572b`;
- aggregate checker SHA-256
  `c3bcec2ac912003d5ba301cdd0699ab04e578db1da310409bd4b87988c0d62e6`;
- frozen core and pair-driver SHA-256
  `8b0486685e4167a3d9b4970d40635dd75b031792ef27ade71e27a5ae285af3b0`
  and `650efd1e807845f9125150a7390b5c7cf6222d18a136e68d7d2c83f17d8008e7`.

## Frozen execution and correctness contract

Two distinct processes (`r1`, `r2`) each:

1. revalidate all 97 names, index mappings, BF16 `[10240,320]` tensors, and
   tensor hashes;
2. regenerate the exact 97 deterministic inputs and match the frozen census;
3. allocate the original linear bank, then prepack all 97 grouped weights;
4. freeze a complete production `F.linear` sweep before the first grouped
   invocation and require every candidate output to equal its slot authority;
5. use a fresh `[1,10240]` output allocation for every grouped call, matching
   the production allocation policy rather than crediting a persistent buffer;
6. run 100 alternating warmup sweeps, then 31 paired cycles of 100 full-bank
   sweeps per provider, alternating linear/grouped and grouped/linear order;
7. validate all 97 outputs after every timed provider block, then run 100
   further alternating exactness sweeps with every slot checked; and
8. rehash the XPU inputs, original XPU weights, packed bank, row metadata, CPU
   bank, model files, authority evidence, tools, stage, exact loader closure,
   and evidence before an atomic no-clobber write.

All 97 candidate outputs must remain finite BF16 `[1,10240]` arrays and be
byte-identical to the control-only authority. Any slot fails the process.

## Frozen performance gates

Each process requires:

- median full-bank latency reduction at least 50%;
- every-cycle reduction at least 20%;
- median absolute saving at least 0.75 ms per 97-call sweep; and
- order-specific median-reduction bias at most 10 percentage points.

The family gate additionally requires two distinct OS process receipts and
nonces, the same packed-bank digest, both process gates, median-reduction spread
at most 10 points, and median-saving spread at most 0.5 ms. Thresholds may not
change after execution.

Each process also fails before device initialization unless `/mnt/usb-models`
is the expected `/dev/sda2` `fuseblk` evidence volume with at least 100 GiB
free, the model is on local root/NVMe storage, host `MemAvailable` is at least
100 GiB, free swap is at least 7 GiB, and no other visible process owns a render
node. The component locks and active-server scan remain separate safeguards;
the unprivileged process does not claim visibility into permission-denied file
descriptor tables.

## Memory and integration boundary

The component intentionally retains both layouts to compare them and records
the load, prepack time, and XPU allocation deltas. That duplicates about 606.25
MiB per card and is permanently endpoint-ineligible. Any source integration
must replace or release the original 635,699,200-byte HC-up bank after packing;
it may not carry both banks into the already capacity-constrained TP4 server.
The family result therefore keeps `source_integration_authorized=false`; a pass
sets only `source_integration_candidate_authorized=true`.

## Exact invocations

For each `REPEAT` in `r1 r2`, the exact output
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-round-robin-REPEAT-seed20260831.json`
must not exist. Run:

```bash
export ONEAPI_DEVICE_SELECTOR=level_zero:0
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH=/mnt/usb-models/qwen38-build/hc-grouped-stage-eeee7d6-sycl8/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/opt/intel/oneapi/compiler/2025.3/lib:/opt/intel/oneapi/compiler/2025.3/opt/compiler/lib
/home/steve/.venvs/vllm-xpu/bin/python \
  experiments/qwen38-flash-next-fp8-b70/tools/benchmark-hc-m1-grouped-gemm-round-robin.py \
  --repeat REPEAT \
  --output /mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-up-round-robin-REPEAT-seed20260831.json
```

After both files exist, run exactly:

```bash
python3 \
  experiments/qwen38-flash-next-fp8-b70/tools/summarize-hc-m1-grouped-gemm-round-robin.py
```

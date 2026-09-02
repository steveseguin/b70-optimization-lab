# Flash-Next BF16 singleton A3 preregistration

Date: 2026-09-02
Status: frozen before device execution

## Question

A2 proved that the exact real layer-0 attention HyperConnection down/inject
BF16 `F.linear`, `[1,10240] x [336,10240]`, changes sparse production-active
output values after warm-up. A3 asks two narrower questions:

1. do A2's strongest recurrent rows change when executed 100 times
   consecutively or at their original ordinal positions inside 100 complete
   256-row sweeps; and
2. does `torch.backends.mkldnn.deterministic=True` remove the within-process and
   across-process variation without changing the frozen tensor or provider?

This is a report-only component discriminator. It cannot receive endpoint,
quality, performance, or promotion credit.

## Frozen identity

- model: `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- A2 tool SHA-256:
  `32e517ff435d4f99ce160c08c4a3172cfcaeb3b4df60848127926d4c2436192f`;
- A3 tool SHA-256:
  `8ddd0dae1b1a1153bc9c791c9192df87ed0daeb1dcdc7f73313564e8e16dca57`;
- A3 CPU-contract test SHA-256:
  `c07fcd3b8a33eddde6fd9d8a4e196157e6ff4c68261433d2ed95ed5e3bb3256f`;
- Torch `2.11.0+xpu`, Git
  `70d99e998b4955e0049d13a98d77ae1b14db1f45`;
- installed XPU provider
  `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so`,
  SHA-256
  `ee584edab22b995637c5f6ec83fc10dea5931469c86cf2ad91952bb3e1108290`;
- family `hc_down_inject`, sentinel `layer00-attn-r0`, seed `2026090201`;
- reconstructed output columns `0:324` are production-active and `324:336`
  are synthetic zero padding;
- focus rows `221`, `205`, `148`, and `78`; recurrent coordinates
  `(221,80)`, `(205,84)`, `(148,204)`, `(148,264)`, and `(78,63)`.

The A3 code imports and hash-binds the frozen A2 implementation, which in turn
binds the A1 checkpoint shard contract, exact real tensor reconstruction,
runtime/source identities, mount, Gen3 clearance, SMART, AER, memory, device,
and exclusive component lock.

## Provider rationale

An independent source audit found that Torch XPU's matmul provider sets the
oneDNN primitive deterministic attribute when either global deterministic
algorithms or `torch.backends.mkldnn.deterministic` is true; that attribute
rejects K-parallel kernels. A3 changes only the mkldnn flag. The pinned local
provider binary imports `at::Context::deterministicMkldnn()` and contains both
`attr-deterministic:` and `dnnl_primitive_attr_set_deterministic` strings.

The corresponding Torch XPU source file is not present as a locally tracked
source tree, so this preregistration does not pretend to bind a source-file
hash. It instead binds the installed provider binary and Torch Git identity.
There is no runtime `ONEDNN_VERBOSE` arm: enabling it is process-global and
would contaminate the exact environment and timing comparison. Each result
will explicitly record that this runtime verbose receipt is absent.

## Frozen execution

A3 uses four sequential fresh child processes on one selected B70:

1. native replica 1;
2. native replica 2;
3. mkldnn-deterministic replica 1;
4. mkldnn-deterministic replica 2.

Each process reconstructs the exact A2 input and weight independently. The
native process explicitly sets the flag false; the candidate process explicitly
sets it true. The requested value is read back before the first GEMM and the
previous value is restored and read back before process completion. No arm
shares a provider cache with another arm or replica.

After four unreported complete-order warm-up sweeps, each child records:

- 100 consecutive synchronized invocations for each focus row;
- 100 complete 256-row sweeps in original row order, retaining each focus
  row at its original ordinal position;
- exact full, active-region, and padding-region hashes for every invocation;
- raw BF16-bit count distributions for every recurrent coordinate;
- comparisons of every invocation to invocation zero, including differing
  rows, columns, elements, and raw bits;
- synchronized XPU-event latency samples and median for every protocol.

Output-authority comparisons exclude timing and backend receipt metadata. The
summary separately reports within-process unique outputs, ordered active-output
sequence equality across the two processes in each arm, and native/candidate
output equality for corresponding replicas. Padding must remain exact numeric
zero.

## Safety and evidence

The execution authority is `Q38_BF16_SINGLETON_A3_EXECUTE=YES`. The immutable
result root is:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/bf16-singleton-diagnostic-20260902-a3`

Existing output is a hard refusal. Every child and parent preserves an atomic
error envelope and postflight receipt. A new AER event, source/runtime/tensor
identity drift, device-count drift, dirty tracked source, mount/clearance/SMART
failure, input or weight mutation, non-finite output, setting-application or
setting-restoration failure, active accelerator owner, or missing provider
identity fails closed. A parent postflight failure stops later cells.

A3 performs no full-model load, endpoint launch, service modification, reboot,
container operation, or write to live vLLM/kernel source.

## Frozen interpretation

- Native varies and deterministic is exact within and across processes: the
  flag advances to a separately preregistered component performance/parity
  gate; it is not yet an endpoint optimization.
- Both vary: this provider flag is insufficient; preserve the negative and
  evaluate a row-invariant implementation or a stronger provider control.
- Both are exact: A2's rare failure was not sampled by A3; do not call it
  fixed or resume the 168-cell census without a stronger repeat bound.
- Candidate outputs differ from native even if candidate is stable: treat the
  candidate as an arithmetic change requiring full target-oracle and quality
  qualification, not as lossless.
- Latency is screening evidence only and grants no speed claim.

No historical result or protected decode speed can be changed by any A3
outcome.

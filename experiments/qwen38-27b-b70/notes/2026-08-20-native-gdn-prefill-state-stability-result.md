# Qwen3.8 native SYCL GDN prefill/state stability result

Date: 2026-08-20

Classification: **valid bounded negative; tested instability not observed**

Preregistration:
[`2026-08-20-native-gdn-prefill-state-stability-prereg.md`](2026-08-20-native-gdn-prefill-state-stability-prereg.md)

Frozen harness commit: `55cecdc5c2b97e8893fca9a728388d7b3eb6f8e5`

## Result

The qualification and the complete replicated screen passed:

- qualification: 240/240 direct native calls, 12/12 cases;
- main screen: 12,288/12,288 calls, 48/48 cases;
- combined: 12,528/12,528 calls and 125,280/125,280 rederived
  per-observation tensor/state gates;
- paired GPU2/GPU3 case comparisons: 24/24;
- aggregate cross-device/process/mode comparisons: 48/48;
- first failures, non-finite values, input mutations, reserved-tail mutations,
  nonselected-row mutations, state-index mutations, and mapping/postflight
  failures: zero.

Every main stratum contains 1,024 calls for one physical GPU, token length,
and execution mode. All four separately invoked process/order rotations passed
on both cards. Core, Z, active convolution state, and FP32 SSM state reference
digests were identical across isolated and queued execution, GPUs 2 and 3, and
every process-index/order rotation for each exact token length 83, 61, and 849.

The final structured gates are:

- [qualification comparison](../data/2026-08-20-native-gdn-prefill-qualification-compare.json),
  SHA-256 `54f3cd6f6301ae74680f834c7e50d716b8bcc2cd9cea285f76f22bc2f61c24a7`;
- [main comparison](../data/2026-08-20-native-gdn-prefill-main-compare.json),
  SHA-256 `61b9f0031e153d4841b139263d8a7afbef6004b8a8da3491affcf8688c329d1d`.

The comparison files bind the exact raw input paths and hashes. For an
additional direct inventory:

| Artifact | SHA-256 |
| --- | --- |
| qualification GPU2 | `680fe51965b85cac8fe03cef5abb36610fba28939567bf4679c8f81521f543f5` |
| qualification GPU3 | `ac6154ce3fd8323f0a9e331c6bcde8f91f15538efd063769dac85abd48fd826b` |
| main GPU2 p0 | `5d872d6d3e2c4e47bc0362a8b49a7fafb22578f98e5a05aac030e9ddb0ba2c7f` |
| main GPU3 p0 | `87f38f9414fb196913535411512e0b1c4a12bc4a4f16c7fb1a9d97ec44359442` |
| main GPU2 p1 | `5bc995bef07422c0df2254d613ae0cf4e114c65f60efafbfe2c75b104f236108` |
| main GPU3 p1 | `bfdad57e3cf66a3b900722912d6e71fb7eb1f04012942529b7a35fa47d9b5601` |
| main GPU2 p2 | `a182f4b287249dfc0312e145d968e7bf7678b5abeb6f9a48642b6e19bde9ca24` |
| main GPU3 p2 | `f83a30ad34822b16791282f2a1daf6876a7d9a010da5aedcd0926840d6411d4f` |
| main GPU2 p3 | `6df477db08b53584ffbda35657e6b0f19b88739ccd97f31b10edacdceee6ba8d` |
| main GPU3 p3 | `b3fbd4034e0385527e6ec6bb00e89289489044e6075bbf32e599f47ba485363e` |

## Identity and engagement

All ten GPU processes resolved one affinity-isolated logical XPU and the same
complete composite stage. The recorded and postflight identities agree on:

- harness SHA `243a15801177ecc7ef0cec99797d7e72259deb22fd07233bd709f394bca7af6e`;
- complete 20-entry stage manifest SHA `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`;
- `_xpu_C.abi3.so` SHA `4dd336013d155aab004fb1c916118957cb9349b491938da65769f2d8af18ffb0`;
- mapped `libgdn_attn_kernels_xe_2.so` SHA
  `c194e28dd902136df545b9c0bd3929d41968c31e84f5b3b2f5ae1dba9dbaeab7`;
- kernel source HEAD `2dd55f380df753a10a88fcd9e96192561066e713` and
  native source SHA `6ac157e3ef5539a3157504ffcc991c35ab8b78ee34c194639918df0583548a88`;
- model config/manifest SHAs `9a1c29a8...` / `731d851b...`;
- exact TP2-local FP16 activation/convolution and FP32 SSM shapes.

The main artifacts also bind the successful qualification comparison by its
exact path, SHA, script SHA, and shape contract.

## Interpretation boundary

No direct native-prefill bit instability, incomplete output overwrite,
unintended cache-row mutation, device difference, process-rotation difference,
or queued-versus-isolated difference was observed for the frozen synthetic
fixtures and reset contract.

Under the preregistered conditional independent-call model, zero failures in
1,024 calls gives a per-stratum 95% rule-of-three upper bound near 0.293%, and
zero in the 12,288-call main pool gives about 0.0244%. Repeated fixed fixtures
and queued batches need not be independent population samples, so these are
descriptive ceilings only.

This result does **not** clear real model-produced QKVZ/BA values, propagation
through all model layers, graph or cross-stream execution, simultaneous TP2
and oneCCL work, target/draft/bonus interleaving, persistent request history,
state promotion, verifier/sampler behavior, or end-to-end server
nondeterminism. It contains no throughput measurement and cannot be promoted
or submitted as a performance result.

## Decision

Close this exact raw-op hypothesis as a bounded negative. Do not repeat it
without a new production-value fixture or a materially different state/history
contract. The next source-backed discriminator is the separately scoped,
two-repeat full-history TP2 treatment that disables uniform speculative
PIECEWISE replay and drafter graph keys. That treatment must retain sealed
cache, full-25 correctness, quality, and exact engagement gates; it is a
combined graph-path test and cannot distinguish target verifier from drafter.
It has only received a read-only source/harness audit and is not yet
preregistered, launch-authorized, or implemented.

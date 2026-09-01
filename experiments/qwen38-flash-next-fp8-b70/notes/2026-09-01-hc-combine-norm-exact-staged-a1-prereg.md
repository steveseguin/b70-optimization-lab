# Qwen3.8 Flash-Next FP8 exact staged HC candidate A1 preregistration

Date: 2026-09-01
Status: frozen, CPU-validated, not executed; one-B70 work remains blocked by
the root-NVMe maintenance boundary

## Question and bounded treatment

The recovered A28 target-token profile assigns about `4.185 ms/token` to the
quantization/cast bucket. The actual per-token group-FP8 quantizer accounts for
only about `0.107 ms/token`; retained shape accounting attributes about
`3.109 ms/token` to HC-shaped casts and copies. Production invokes
`hc_combine_norm` 95 times per target-token graph cycle at these exact shapes:

- residual `[1,10240]` BF16;
- block output `[1,2560]` BF16;
- injection logits `[1,4]` BF16;
- HC norm weight `[10240]` BF16;
- HC count `4`.

The A1 candidate is deliberately narrow. It builds the immutable FP32 affine
`1.0 + norm_weight.float()` once before graph capture instead of rebuilding it
inside every HC invocation. It retains Torch's existing sigmoid, division,
scaling, square/mean, rsqrt, multiply order, and output casts. In particular,
the combine result is still explicitly rounded to BF16 and reloaded as FP32
before normalization. No Triton approximation is admitted: retained direct-HC
Triton candidates were faster but not byte-exact.

This is an experiment-local Python candidate. It does not alter live vLLM,
does not alter an endpoint, and does not claim that all HC casts are removed.
Even a component pass authorizes only design of a source patch followed by a
new exact gate and full-model qualification.

## Frozen real-weight C/A/C gate

The gate uses one visible B70 and the validated external FP8 checkpoint at
revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`. It selectively reads only
four norm sentinels, checking the model index/config and tensor bytes:

| Sentinel | Tensor | SHA-256 |
| --- | --- | --- |
| layer-0 attention | `layers.0.attn_hyper_connection.hc_norm.weight` | `0a3213d5...d169f98` |
| layer-0 MLP | `layers.0.mlp_hyper_connection.hc_norm.weight` | `e1da29c3...a89a5bb` |
| layer-47 attention | `layers.47.attn_hyper_connection.hc_norm.weight` | `90c3284c...facb816` |
| layer-47 MLP | `layers.47.mlp_hyper_connection.hc_norm.weight` | `66863fc1...d297452` |

For every sentinel and each seed `20260826`, `20260827`, and `20260830`, the
order is control-before, candidate, control-after: 12 matched cells and 36 arm
executions. Each captured graph contains exactly 95 calls. Each arm replays 100
changing inputs and requires 100 distinct hash pairs. Both the combined BF16
output and normalized BF16 output must equal the eager Torch authority on every
call. The candidate also runs eager parity, validates the cached affine before
capture, and passes finite BF16 adversarial values including signed zeros,
subnormals, normal boundaries, and the retained `0x41be` mismatch trigger.

Timing excludes input copies and correctness reads. Each arm uses 10 warmups
and nine batches of 50 graph replays. Interpretation is frozen:

- all 12 cells and both outputs must be byte-exact;
- matched control drift must be at most 2%;
- median candidate improvement must be at least 5% or at least 1,000 us per
  95-call cycle;
- at least 10 of 12 cells must be positive;
- no cell may regress by more than 2%.

The offline summarizer independently revalidates every frozen model, mount,
source, candidate, sentinel, shard, tensor, and C/A/C authority identity. It
also recomputes uniqueness and syntax for all 100 output-pair hashes and binds
the adversarial-output hash across the three matched arms.

The 1,000-us alternative corresponds to about 1 ms/target token at the 95-call
production cadence. The full cast-bucket algebraic ceiling is roughly
`22.43 tok/s` from the protected `20.507849 tok/s` A44 lane, or about
`23.67 tok/s` if combined with the already-qualified W13 collective win. This
narrow affine-hoist is expected to recover only a fraction of that ceiling; a
clean exact but subthreshold result is a useful bounded negative.

## Safety and launch boundary

No GPU work was run while building this packet. The runner refuses an existing
result/cache path, an active Qwen/vLLM server, a model or source identity drift,
multiple visible XPUs, or a non-external checkpoint mount. It also requires the
fixed root-NVMe clearance-v1 receipt after physical/firmware maintenance and
aborts on any endpoint or root-port corrected-event increment. Each arm runs
in an owned process group while the runner polls both counters every second;
an increment terminates and then kills only that owned group. Device selection
uses `ONEAPI_DEVICE_SELECTOR=level_zero:0` while explicitly unsetting
`ZE_AFFINITY_MASK`, avoiding the known double-filter trap. It requires an
explicit one-B70 authorization token. A reboot is not required.

An EXIT trap preserves a no-clobber `final-health.txt` containing runner status
and final/baseline counters, terminates any still-owned process group, and
writes `SHA256SUMS` over every other top-level evidence file. These receipts
cover both successful and failed admitted runs; pre-admission failures create
no result directory.

The runner and gate do not load vLLM or the 173-GiB checkpoint. Each arm opens
one named safetensors shard and transfers only one 20-KiB BF16 norm vector to
the selected B70.

## Frozen implementation identities

- live vLLM head: `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`;
- live HC authority SHA-256: `a2ed67ce6240a150a75247097f0a49b4652d5bf1f5db1cdaf34ad5ec52faa8da`;
- candidate core: `4f07ca40099b16259ca6f82a226791732455dc9903b66c39691ba212f5d19354`;
- CPU contract tests: `91b77d35a9773842ebfdab62d82cf1da03c79864d849932fc69a2439e020799f`;
- XPU graph gate: `9c8837fbab48f9ce80b7b6e4603d2f1ce339b01997384e662335f396f1aa5ea6`;
- summarizer: `7ab377898809bc4d22747b0139d82afdaa5772d3b66b5338c48efeae3267e51f`;
- summarizer tests: `ce36387b231b3644b79485c2dec996c23537592e8ba38a1d2bb2aa6319a3c0b5`;
- runner: `88db267a8245086f5f58c2d96af1506ac7197f04535b1420fe31740555bb7b4a`;
- runner CPU tests: `a8a135ee3e836e915b5a32c247a0f568805b949decbd405e2f5c27c918a3f7a3`.

CPU validation passed 21 focused tests. The structured preregistration is
[`20260901-hc-combine-norm-exact-staged-a1-prereg.json`](../data/20260901-hc-combine-norm-exact-staged-a1-prereg.json).

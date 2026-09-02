# Qwen3.8 Flash-Next FP8 HC gate-mix exact-staged A1 preregistration

Date: 2026-09-01
Status: candidate and fail-closed one-B70 runner CPU-qualified and frozen;
execution remains blocked by root-NVMe clearance, with no GPU work, endpoint
authorization, or performance claim

## Why this target

A28 measured about `2.94 ms/token` of elementwise work and `4.19 ms/token` of
quantization/cast work. The Qwen4Exp target invokes HC gate mix 97 times per
target token (twice in each of 48 layers plus the final mixer). On XPU, each
call still uses the Torch fallback:

1. BF16 gate to FP32;
2. FP32 sigmoid;
3. BF16 state to FP32;
4. FP32 multiply;
5. FP32 mean;
6. FP32 result to BF16.

The retained whole-Triton replacement is not eligible despite its `77.998%`
isolated speed reduction: randomized production-shape inputs differed by up to
`0.0078125`. This A1 candidate therefore retains Torch sigmoid, multiply, and
mean. It changes only their staging: Torch type promotion converts BF16 state
inside the FP32 multiply, and a fresh BF16 `out` tensor performs the final
conversion inside the FP32 mean. The checkpoint-visible BF16 boundary remains.

This is a new target-side component idea. It is independent of W13-N32 MoE
tuning, immutable norm-affine hoisting, and the closed SiLU/native-HC kernels.
The outside `flashnext-harness` contributes no code to this treatment; its only
transferable speed concept, static whole-decode execution, was already realized
independently in A44.

## Frozen evidence boundary

The experiment-local candidate and its gate are:

- `tools/hc_gate_mix_exact_staged.py`;
- `tools/hc-gate-mix-exact-staged-xpu-graph-gate.py`;
- `tools/test_hc_gate_mix_exact_staged.py`;
- `tools/run-q38-hc-gate-mix-exact-staged-a1.sh`;
- `tools/test_run_q38_hc_gate_mix_exact_staged_a1.py`;
- `tools/publish-q38-hc-gate-mix-a1-evidence.py`;
- `tools/test_publish_q38_hc_gate_mix_a1_evidence.py`.

CPU validation passes 49 tests: 23 candidate/parity tests, 11 frozen-runner
contract tests, four transactional-publication tests, and 11 shared-clearance
tests. Candidate coverage includes 15 production-shape seed/scale
cells, 100 changing inputs and hashes, input/no-alias checks, contract
rejections, and all 65,280 finite BF16 state encodings through the changed
promotion/reduction-output path. All parity and mutation comparisons use raw
BF16 bytes, so signed zero cannot pass merely through value equality. The
runner tests prove clearance-before-path admission, fixed identities, one-XPU
selection, process exclusion, an owned-process-group AER stop, one C-A-A-C gate
invocation, immutable source staging, and checksum finalization. Publication
tests simulate both a checksum failure and a replay against an existing final
path. Clearance tests simulate stale-boot receipt replay and every receipt/live
SSD identity drift. None is XPU evidence.

## Later one-B70 gate

Do not run until the separately frozen root-NVMe link clearance passes. The
frozen wrapper is intentionally non-runnable before that receipt validates. It
binds the gate/core hashes, vLLM authority source/head, Python and Torch build,
exact four-card topology, one-B70 selector view, fixed clearance path and
validator, exclusive locks/cache/result paths, and absence of Qwen/vLLM work.
The clearance schema binds the current boot ID and exact live `nvme0`
controller, serial `S6WSNS0T109768K`, model, BDF `0000:01:00.0`, and
`5B2QGXA7` firmware; a prior-boot receipt cannot be replayed. The live BDF must
agree between the nearest PCI-function sysfs ancestor and the controller
`address` attribute. After admission, the runner copies and hashes that receipt
and immutable gate/core,
validator/publisher sources beneath a hidden staging result. The literal final
call immediately before `setsid` revalidates the canonical runner, vLLM
HEAD/clean tracked tree and authority, Python target/hash, Torch package and
version identities, every live/staged experiment source, live and copied
clearance, external mount, process exclusivity, and unchanged endpoint/root
AER baselines. The same comprehensive helper runs again after the gate. The
runner executes the staged Python gate once in an owned process group while
polling both counters every second. The component gate captures 97
production-shape calls in each of a control and candidate XPU graph. It
requires:

- 100/100 changing-input eager outputs byte-identical to the Torch authority;
- 100/100 changing-input graph outputs byte-identical to the same authority;
- 100 distinct graph hashes and unchanged inputs;
- a C-A-A-C timing bracket with at most 2% control drift;
- at least 3% candidate improvement.

A pass authorizes only a default-off vLLM integration patch and a later matched
endpoint arm. A parity miss, unsupported BF16 `out` reduction, graph-capture
failure, or timing miss closes this component without changing any protected
result.

The single gate invocation contains the exact `control, candidate, candidate,
control` timing order. Final output, device, identity, clearance, exit-code,
health, and checksum evidence is first written below the hidden `.staging`
root. A pass health receipt is not published at the final path until every
manifest entry verifies. The NTFS/FUSE-compatible publisher then claims the
final directory with exclusive `mkdir`, moves all covered evidence and the
manifest, and moves `final-health.json` strictly last as the commit marker. A
checksum failure downgrades the staged receipt to `failed_closed`, regenerates
and verifies its manifest, and can never publish a pass. An existing final path
rejects replay without clobber. Any AER change
stops only the owned group and makes the result fail closed. No model shard or
full checkpoint is opened, no reboot is requested, and live vLLM remains
unchanged.

## Frozen wrapper identities

- runner SHA-256:
  `d9d9f886306c1d334cf780733e57f3eb68d84b6aa4d5fa77c66cf00fb7a37aa6`;
- runner canonical self-check SHA-256:
  `5882efc7f9950be68664567e961d73fed2d726df0ed5e1f7acc5c4ad9aed0417`;
- runner CPU tests SHA-256:
  `0e10dd030d0f59ad25575c1f70e371d9ac82b5204895ec0eaf835fc734721cb8`;
- transactional publisher SHA-256:
  `fc8cf0244f091ce8b6526407982a991aaad6d8813d9349161d7e01e878b6a67e`;
- publisher CPU tests SHA-256:
  `0448ea19830703d744871aa4b0fb31d0da0ec63b29e2268fdc240f1efa8fce3c`;
- clearance validator SHA-256:
  `2293b3588a275e15a630b813d7a273e650eb64c49eaacedcf212f99fe485d5a5`;
- clearance-validator CPU tests SHA-256:
  `86cc73b551b88f4fec95a8ce9952837b9d4c8ca7080bd99db95c2e690e207bf1`;
- Python `3.12.13` interpreter SHA-256:
  `202c17d1671602a4ef1d43e9b2fdbef0769443f37bf5e51f6b603e0b2c27d9d8`;
- Torch `2.11.0+xpu`, source identity
  `70d99e998b4955e0049d13a98d77ae1b14db1f45`, XPU build `20250302`.

`Q38_HC_GATE_MIX_A1_VALIDATE_ONLY=1` performs only static CPU validation and
creates neither result nor cache state. Actual execution additionally requires
`Q38_HC_GATE_MIX_A1_AUTHORIZED=I_UNDERSTAND_THIS_USES_ONE_B70`; that token does
not bypass the clearance receipt or any other admission gate.

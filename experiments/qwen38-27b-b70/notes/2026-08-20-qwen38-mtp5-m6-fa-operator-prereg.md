# Qwen3.8 MTP5/M6 exact-shape FlashAttention operator preregistration

Date: 2026-08-20

Status: **closed as a terminal candidate-role correctness-gate rejection; no
retry or model run**. See the
[`r6` result](2026-08-21-qwen38-mtp5-m6-fa-operator-result.md).
This operator screen did not start vLLM, did not touch the model, and does not
authorize a full-25 endpoint arm.

The first immutable build root, ending in
`qwen38-m6-head256-q8k64-attn-override-20260820`, is preserved as an
infrastructure-invalid attempt. Configuration stopped before either candidate
object compiled because Git rejected CMake's oneDNN checkout on the
root-owned USB mount. The helper now supplies one exact process-local
`safe.directory` for that checkout without changing global Git configuration.
The attempt is not a kernel result and must not be reused or overwritten; the
second command used a new `-r2` root.

The preserved `-r2` attempt passed configuration and compiled both intended
objects, but the same FUSE mount then rejected the staging permission change.
It has a partial runtime tree and candidate DSO, but no candidate JSON or
checksum manifests and is not authorized for loading. Rather than weaken the
mode/atomic-artifact contract for that filesystem, the next build and result
roots move to the host's native ext4 filesystem and use new `-r3` names. This
is also an infrastructure-invalid attempt, not a policy timing result.

The first ext4 attempt, ending in `-r3`, again compiled both objects, but its
private `rsync -a` copy inherited the incumbent stage's read-only directory
mode and could not replace the device DSO. It is preserved without a candidate
JSON or checksum manifests. The helper now opens only the private runtime
copy's two containing directories, installs the new DSO with the incumbent
`0555` mode, and reseals those directories. The next immutable ext4 roots use
`-r4`; the incumbent stage remains untouched.

The `-r4` build then completed and sealed the reusable candidate stage:

- candidate-stage JSON SHA-256 `ec3b31cad3c89b1bf0d4a747cb011ebea248b7c55c8766563489e09bfcde7a7e`;
- build-input manifest SHA-256 `21ded717f108feaada2018f360c4c781cf91f5893b28478842859a429962a53b`;
- graph manifest SHA-256 `db0f01bdf72670c119ff95e40cdf4b967f0613e0b1dd0b383d581150245fab62`;
- candidate device DSO SHA-256 `f777decfe23efb45fe7797d16d9f6378dfef531a5ce66aab3ddee5567b65013e`.

The first operator result root ending in `-r4` is empty and
infrastructure-invalid. GPU2 control passed ten direct warmups plus all 32
eager poison/oracle checks at KV128, and capture returned the exact static
output pointer. The qualifier then incorrectly read the still-poisoned output
before calling `graph.replay()`. Capture records work for later replay and is
not itself a correctness execution. The corrected qualifier retains the
pointer check and synchronization, then makes its existing 32
poison-replay-synchronize-oracle iterations the only graph correctness
evidence. The candidate was never loaded in the invalid attempt. Reuse the
sealed build, but use a new `-r5` result root.

The corrected GPU2 control in result root `-r5` completed every operator case
and wrote its expected empty control stderr log, but the final provenance scan
then rejected an unrelated normal `/dev/zero (deleted)` mapping. No packet was
written and the candidate still never loaded. The scan now ignores deleted
non-library mappings while continuing to fail if any of the exact extension,
candidate/control device library, or stock library basenames is mapped as
deleted. Preserve `-r5` as infrastructure-invalid and use new result root
`-r6`.

The `-r6` control A1 then passed and wrote a complete sealed packet. Candidate
B1 failed its first checked eager CPU-oracle replay at KV 128: 3,297 of 18,432
elements mismatched, with greatest absolute difference
`0.1544189453125` against `atol=0.02`. The candidate failed before atomic
packet/stderr publication and before timing. Preserve the exact console-only
observation and retained control artifacts in the linked result. Because no
candidate marker or mapping record survived, this rejects qualification under
the intended Q8 x K64 launch but does not independently prove runtime policy
dispatch. Do not retry it, continue ABBA, or run the model.

## Question and bounded scope

The next candidate is allowed to change only the staged Intel FlashAttention
implementation. The bounded question is whether it preserves exact Qwen3.8
MTP5 target/verifier outputs while recovering enough packed-attention latency
to matter to the endpoint. This is an operator qualification, not an endpoint
throughput or target-exactness result.

The production-derived local TP2 shape is frozen as:

- FP16 query/KV/output;
- six packed rows (one target row plus five speculative rows);
- 12 local query heads, two local KV heads, head dimension 256;
- paged causal KV with block size 64;
- KV lengths exactly 128, 1024, 1300, and 2048;
- `is_mix_batch=True`; the pinned extension's C++ force-chunk switch then
  enters its prefill-only route and passes a null `is_prefill` optional; and
  `VLLM_XPU_FA2_FORCE_CHUNK_DECODE=1`;
- one sequence and deterministic shuffled block tables.

The switch is part of the production launch identity. The screen does not
claim that the switch selects a distinct rows-six branch: actual engagement is
bounded to the exact public call, selected staged extension, and mapped XE2
device library proved by the run packet.

The frozen candidate source predicate correspondingly requires
`!is_prefill.has_value()`. A non-null guard would be an inert false-null against
the pinned `339...` extension even though `is_mix_batch=True` is passed at the
Python call site.

## Control bytes and transfer prerequisite

The control stage is fixed at:

```text
/home/steve/staged-xpu-commitfix-graphfa-composite-20260820
```

Every fresh process hashes these active files before importing the extension:

| File | SHA-256 |
|---|---|
| `_vllm_fa2_C.abi3.so` | `33938cdd2436684dcb76108a4db43e4ab0314406ad537fcd3732a005f7d23739` |
| `flash_attn_interface.py` | `869c79f5f678252c341cfb8fb5cf9ee34f95c3d2debf4d169b759510da432480` |
| `libattn_kernels_xe_2.so` | `604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c` |
| `libattn_stock.so` | `3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289` |

The extension's historical RUNPATH points at a build tree, so relying on an
import path alone would be a false engagement proof. The clean runner puts the
selected stage package first in `PYTHONPATH` and `LD_LIBRARY_PATH`; after real
calls the packet requires `/proc/self/maps` to contain both the exact selected
extension, the exact selected `libattn_kernels_xe_2.so`, and its exact selected
`libattn_stock.so` dependency. Their mapped paths and already-verified hashes
are retained. The Python interface remains a resolved file/path/hash proof,
not a mapped-DSO claim. `PYTHONDONTWRITEBYTECODE=1` is mandatory so imports
cannot mutate the graph-manifest inventory between fresh arms.

Control processes set `VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY=0` and reject any
policy marker. Candidate processes set it to exactly `1` and require exactly
one unadorned stderr line
`VLLM_XPU_FA2_M6_HEAD256_Q8K64_POLICY engaged`. The captured stderr log is
retained and checksum-bound to the packet. Missing, duplicate, malformed, or
control-side markers fail closed. This is runtime engagement of the candidate
rows-six policy, not merely source or file-presence evidence.

The remote two-B70, 15-GiB reference/op-audit host does **not** currently have
the control `339`/`604`/`869` bytes. This preregistered driver is deliberately
bound to physical GPUs 2 and 3 on the local four-B70 measuring host, so it must
not be used remotely. A later remote operator replication would require the
exact bytes to be transferred and checksum-verified plus a separate frozen
host/device contract; a nearby build is not an admissible substitute.

## Candidate identity prerequisite

A candidate must have a new immutable JSON manifest with schema
`qwen38-mtp5-m6-fa-stage-v1`. It must name a canonical absolute candidate
stage, the same four fixed relative paths with their candidate SHA-256s, and
one canonical immutable helper-emitted build-input checksum manifest plus its
independently computed SHA-256. That artifact basename must be
`qwen38-m6-head256-q8k64-build-inputs.sha256`; it must parse as a strict GNU
SHA-256 manifest and bind the build helper, the candidate DSO, and source patch
`vllm-xpu-kernels-qwen38-m6-head256-q8k64-chunk-prefill-20260820.patch` at
`06467757a7482ad0e3225c9a59ce3d2de144453a608016737c7a24dbe48b5fc1`.
The build helper itself is pinned at
`1235e181bcd3ca0782d0faef9416927435564cf7eb44d0d8bcc0e6470886e445`.
The build-input manifest must also bind its full graph manifest, whose entries
and hashes must exactly cover every regular file under the candidate stage's
`vllm_xpu_kernels/` tree.
The extension, Python interface/wrapper, and `libattn_stock.so` must
remain byte-identical to control. Only `libattn_kernels_xe_2.so` may differ,
and it must differ. This makes the candidate boundary the compiled attention
device library rather than a wrapper/dispatch confound. Unknown/missing keys,
symlinks outside the stage, stale artifact bytes, or malformed JSON fail
closed.

Illustrative schema only (the values must be frozen before launch):

```json
{
  "schema": "qwen38-mtp5-m6-fa-stage-v1",
  "role": "candidate",
  "stage": "/absolute/candidate/stage",
  "files": {
    "extension": {"relative_path": "vllm_xpu_kernels/_vllm_fa2_C.abi3.so", "sha256": "..."},
    "interface": {"relative_path": "vllm_xpu_kernels/flash_attn_interface.py", "sha256": "..."},
    "device_library": {"relative_path": "vllm_xpu_kernels/libattn_kernels_xe_2.so", "sha256": "..."},
    "stock_library": {"relative_path": "vllm_xpu_kernels/libattn_stock.so", "sha256": "3cbd3ed2ff51a477e6746b3e5860c070d093fd2d29b0b7a58e6dd081e9ad1289"}
  },
  "artifact": {"path": "/absolute/build/qwen38-m6-head256-q8k64-build-inputs.sha256", "sha256": "..."}
}
```

## Correctness and timing contract

Fixtures are generated on CPU with a separate seed `380000 + kv_length`.
Their query, physical KV cache, shuffled logical block order, and block table
are hashed. The FP32 CPU oracle expands two KV heads to 12 query heads, applies
the packed causal positions, softmaxes in FP32, and returns FP16. Both eager and
captured `torch.xpu.XPUGraph` outputs must satisfy `atol=0.02, rtol=0.01`.

For every shape and mode, 32 correctness repetitions poison the caller-owned
static output with NaNs before the call/replay, synchronize, prove the output
pointer was honored, reject any residual NaN, and require one bitwise output
digest. Eager and graph digests must be bit-identical. Each case then applies
four separate deterministic live-input mutations: scale Q by 0.875, scale the
physical K cache by 0.875, scale the physical V cache by 0.875, and reduce
`seqused_k` by 64. Before each mutation the other three inputs are restored to
baseline. Each mutation runs twice in eager and twice through the already
captured graph, must change the baseline output, must match its independently
recomputed CPU oracle, and must have exact eager/graph digests. All Q/K/V/KV-
length inputs are restored and the baseline oracle is rechecked before timing.
The validator reconstructs the exact mutation name/target/scale/length
inventory and checks input/oracle/output digest cardinality, exact eager/graph
equality, baseline difference, and cross-arm parity rather than accepting a
`passed` boolean.

Across control and
candidate arms, fixture, oracle, eager output, and graph output digests must be
exactly identical, including all four mutation families. Although
tolerance-only baseline parity could be useful for exploration, it is not
accepted by this gate.

After ten warmups per shape, each packet records 40 independent device-event
samples per eager/graph mode, with 100 calls inside each sample. Poisoning and
host synchronization are deliberately outside the timed loops. Eager timing
is context only. The gate uses `torch.xpu.Event` elapsed time for graph replay.

KV 1300 is the primary performance shape because the production step-cost
measurement was taken near that length. KV 1024 and 2048 are guard shapes, and
KV 128 is the short-context regression guard. No equal-KV weighted average is
used as a primary gate.

## Fresh-process ABBA and statistical gate

Use four sequential processes on physical B70 2 and four on physical B70 3.
Every process sets `ZE_AFFINITY_MASK` to that physical index, requires exactly
one visible XPU, and calls logical `xpu:0` only:

```text
device 2: control A1, candidate B1, candidate B2, control A2
device 3: control A1, candidate B1, candidate B2, control A2
```

Run packets record PID, `/proc` start ticks, boot ID, non-overlapping process
times, hostname, physical GPU, logical device zero, affinity mask, device
name/properties, Python/Torch, lab commit, qualifier SHA,
driver SHA, selected stage/manifest/artifact identity, mapped library identity,
all fixtures/outputs, and all raw timing samples. Compare requires eight
distinct processes, one boot, exact ABBA order, and no within-role identity
drift.

For each B70 independently and each KV length separately:

1. central saving is the mean of the two adjacent ABBA pair differences,
   `A1-B1` and `A2-B2`;
2. a deterministic 10,000-iteration paired bootstrap uses shared resample
   indices within each adjacent control/candidate pair, recomputes each arm's
   shape median and pair difference, then averages the two pair differences;
3. KV 1024, 1300, and 2048 each require the saving interval's 95% lower bound
   to be strictly greater than zero;
4. KV 1300 additionally requires central saving of at least `21.844 us` per FA
   call and therefore at least `0.3495 ms` per 16 full-attention calls
   (`21.844 * 16 / 1000 = 0.349504 ms`);
5. at KV 128 the 95% upper bound for candidate-minus-control regression must
   be no more than `2.0 us` per call;
6. all correctness, mutation, poison, bit-stability, mapping, and exact-parity
   gates must pass.

The KV 128 allowance caps short-context harm at 32 us per 16-attention step,
about 0.09% of the measured 35.3 ms step, without requiring a short-context
win from a policy aimed at the KV-1300 region. The bootstrap interval measures
within-arm event-sample uncertainty; the two fresh processes per role and ABBA
order are retained separately as the process/drift control. It is not labeled
as an eight-process population estimate.

Both devices must pass. A nonpositive long-KV confidence bound, excessive
short-KV regression, a win on only one device, a smaller KV-1300 central
saving, any correctness mismatch, any process or identity ambiguity, or a
runner/checker error rejects the candidate. There is no selective shape waiver
and no same-root retry. Infrastructure failure is
preserved and requires a new preregistered root rather than overwriting an arm.

A pass only qualifies the binary for a separately preregistered endpoint
campaign. It is not permission to run full25 and it is not evidence that the
endpoint will exceed 105 tok/s. A failure stops this candidate; do not spend a
model run on it.

## Historical commands after candidate freeze

The scripts are:

- [`../scripts/build-qwen38-m6-head256-q8k64-attn-override-20260820.sh`](../scripts/build-qwen38-m6-head256-q8k64-attn-override-20260820.sh)
- [`../scripts/qwen38_mtp5_m6_fa_operator.py`](../scripts/qwen38_mtp5_m6_fa_operator.py)
- [`../scripts/run-20260820-qwen38-mtp5-m6-fa-operator-abba.sh`](../scripts/run-20260820-qwen38-mtp5-m6-fa-operator-abba.sh)

Frozen prelaunch bytes are qualifier
`0dd7b945ef35a11ff4d0a1ec085e604920524b996d539e089d89b4a019a5de1f`
and driver
`5aa23300d7e3cfd64e10964c7a395b11e8ba70099908d48d6bc8fc58f0d7b9f1`.
The driver independently hardcodes the qualifier SHA; every run packet records
both actual bytes plus the clean lab commit.

Choose new absolute build and result roots outside Git. The build helper
refuses an existing root and produces the only admissible candidate manifest.
Build first, run the non-GPU identity check, then the eight arms, then compare
as a separate action:

```bash
driver=experiments/qwen38-27b-b70/scripts/run-20260820-qwen38-mtp5-m6-fa-operator-abba.sh
build_root=/home/steve/qwen38-m6-head256-q8k64-attn-override-20260820-r4
root=/home/steve/qwen38-mtp5-m6-fa-candidate-abba-20260820-r6
candidate_manifest="$build_root/qwen38-m6-head256-q8k64-candidate-stage.json"

# Already completed and sealed above; do not rebuild or overwrite build_root.
"$driver" check "$candidate_manifest"
"$driver" run "$candidate_manifest" "$root"
"$driver" compare "$root"
```

The compare command returns zero only for a fully qualified candidate, returns
14 for a scientifically valid rejection, and returns 3 for a malformed or
incomplete contract. Raw packets and `comparison.json` remain the durable
evidence when they exist. In `-r6`, control A1 passed and candidate B1 failed
correctness before atomic packet publication; no compare ran. These commands
are retained for provenance only and must not be rerun for this policy.

# mndodd Intel SYCL fork: Qwen3.6 27B on Arc Pro B70

> **Maintainer-validated community source.** Start with
> [STATUS.md](STATUS.md). The source fork does not contain a durable
> greater-than-50 benchmark claim. This packet separates the fork's code from
> the lab's measured results and from a favorable-prompt DFlash observation.

## Outcome

The fork is a meaningful B70 optimization branch. On two ASRock B70s, its
target-only Q8_0 tensor-parallel path improved the matching upstream endpoint
from 29.610651 to **31.338765 tok/s** under the repository's historical
100-event/99-interval helper convention. The conventional rate from the same
timestamps is **31.025377 tok/s**. All 12 prompts were unique and cold,
`cached_tokens=0` on every row, and all 12 complete output hashes matched the
upstream control.

The `llama-bench -p 512 -n 128 -r 5` decode row was **31.255575 tok/s** versus
30.110121 for the accepted modern upstream runtime (`+3.80%`). The fork
improved the matched one-card target-only endpoint from 17.297038 to
**17.955800 tok/s** legacy (`17.776242` conventional, `+3.81%`), but did not
reach 20 tok/s without speculation. It also raised the same one-card MTP4
workload from 33.163827 to 39.618445 tok/s under
the legacy endpoint convention (`+19.46%`), but that retained speculative run
is support-only until its explicit-greedy quality rerun is complete.

| Q8_0 lane | GPUs | Draft / KV | Fixed-suite legacy rate | Conventional rate | Evidence |
| --- | ---: | --- | ---: | ---: | --- |
| Target only, fork | 2 | none / F16 | **31.338765** | **31.025377** | matched A/B, 12/12 complete hashes |
| Target only, accepted upstream | 2 | none / F16 | 29.610651 | 29.314545 | matched control |
| Target only, fork | 1 | none / F16 | **17.955800** | **17.776242** | matched cold completions; quality-cleared |
| Target only, upstream-derived control | 1 | none / F16 | 17.297038 | 17.124067 | matched control |
| MTP4, fork | 1 | intrinsic MTP / F16 | **39.618445** | 39.222260 | support-only; same request identity as upstream MTP control |
| MTP4, upstream-derived control | 1 | intrinsic MTP / F16 | 33.163827 | 32.832188 | support-only control |
| MTP4, fork | 1 | intrinsic MTP / Q8_0 | 39.168618 | 38.776932 | separate KV-quality lane |
| DFlash5, fork | 1 | Q8_0 DFlash / F16 | 38.084045 | 37.703205 | support-only; favorable prompt reached 65.00 |

The legacy helper divides 100 timestamped events by the span from event 1 to
event 100, which contains 99 intervals. Conventional values above are exactly
`legacy * 0.99`; relative A/B deltas are unchanged.

The post-validation target-only optimization pass did not find another safe
gain. Root-barrier elision (`-0.246%`), forced PVC-style MMVQ phase ordering
(`-2.818%`), and root-local reduction followed by peer-copy replication
(`-1.726%`) were all rejected in same-window or same-binary controls. The
reproduction patch below therefore remains the complete promoted source delta.

## Source and model links

- Fork branch: <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization>
- Exact tested commit: <https://github.com/mndodd/llama.cpp/commit/4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126>
- Upstream merge base: <https://github.com/ggml-org/llama.cpp/commit/84e908c625fb60992b4cdef8180fb12fa9b4c4bf>
- Q8 target and intrinsic MTP sidecar: <https://huggingface.co/ggml-org/Qwen3.6-27B-GGUF/tree/8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8>
- DFlash draft: <https://huggingface.co/williamliao/qwen3.6-27B-DFlash-GGUF/tree/edb70860182c75bae2e25ab550b79adcfb170a32>

Exact file sizes and SHA-256 values are in the validation packet. Do not
substitute a similarly named GGUF without updating the identity and rerunning
quality.

## What is in the fork

The tested branch is 155 commits beyond its current upstream merge base. The
most relevant B70 mechanisms are:

- 16-byte wide loads for reordered Q8_0 MMVQ and reordered multi-column Q8
  MMVQ/MMQ paths;
- one shared Q8_1 activation quantization across eligible consumers;
- four guarded cross-operation fusions (residual/norm/scale, GDN ladder,
  paired L2 normalization, and full-attention output gate);
- device-specific `ne[1]` routing and measured MMVQ/MMQ cutovers;
- GQA6 FlashAttention tiling and optional XMX attention work;
- deterministic oneDNN routing, persistent staging, topology-aware ubatch
  packing, and corrected async-input-copy handling.

The runtime prints every resolved door. A valid reproduction must retain that
startup banner. `PROVENANCE.md` is useful history but describes an earlier
branch point; later commits changed some defaults.

Selected performance-relevant branch commits are linked here for review:

- reordered Q8_0 wide MMVQ loads: [`4b3ca6f0`](https://github.com/mndodd/llama.cpp/commit/4b3ca6f0ad2c77ac3732b410dcff0d3c02f6478a),
  followed by the multi-column Q8 MMVQ/MMQ path in
  [`3cdc8fa6`](https://github.com/mndodd/llama.cpp/commit/3cdc8fa613c4b9096baf2b672b5639ef3f6ae892);
- shared Q8_1 activation quantization:
  [`0b50e847`](https://github.com/mndodd/llama.cpp/commit/0b50e847d006683a3eb31e3c6b3f0e88b387358d);
- guarded fusion framework and its four Qwen paths:
  [`6f0b950a`](https://github.com/mndodd/llama.cpp/commit/6f0b950aa3b2eb50ed3b2b5bc928170cdb5cf2cf),
  [`d56a8385`](https://github.com/mndodd/llama.cpp/commit/d56a8385f365cf20ad3ef943e67d157b8414c929),
  [`8417931f`](https://github.com/mndodd/llama.cpp/commit/8417931ff4fa37654fd507694f55a976dd644600),
  [`fd11c10e`](https://github.com/mndodd/llama.cpp/commit/fd11c10e5cde9f9b0f548e980ffe7d16c7705825), and
  [`8733f673`](https://github.com/mndodd/llama.cpp/commit/8733f6738cdb972dd2f9623f5ee5dec931be3012);
- PCI-device-keyed shape routing and the measured B70 Q8 boundary:
  [`84ffb28e`](https://github.com/mndodd/llama.cpp/commit/84ffb28ed857cb6f2a4f31100a3c9cd2e39c7e41) and
  [`b093e1db`](https://github.com/mndodd/llama.cpp/commit/b093e1db55f46d50a09eb63f8a474e58a45d92ed);
- GQA6 attention work:
  [`b8930823`](https://github.com/mndodd/llama.cpp/commit/b8930823df148b18fb92cdbb1c3084ca1b9dc790),
  [`abed054c`](https://github.com/mndodd/llama.cpp/commit/abed054c87222c13928fd1a60641e8e0478552b4), and
  [`2b652657`](https://github.com/mndodd/llama.cpp/commit/2b65265761a5072ae9e0d24f4f6effc0f47b25c9);
- persistent/pinned staging corrections:
  [`db6022e7`](https://github.com/mndodd/llama.cpp/commit/db6022e7aa13d217b90fb80accd0971fd91c2272) and
  [`d32dde81`](https://github.com/mndodd/llama.cpp/commit/d32dde810b3f85a17c71b865a1b28b79799291ef).

These links explain the branch contents; the measured end-to-end gain is not
assigned to an individual commit without a controlled ablation. The exact
tested commit remains the reproduction authority.

## Lab-only patch

Apply [`patches/0001-asrock-lab-lowram-dnnless-tp2.patch`](patches/0001-asrock-lab-lowram-dnnless-tp2.patch)
on top of the exact fork commit. It contains three bounded changes:

1. reduce three metadata contexts from about 368 MiB each to 64 MiB each for
   this 15 GiB host;
2. make the disabled WDC source compile when oneDNN is unavailable (it does
   not enable or validate WDC);
3. add an opt-in, two-device, exact-F32 peer-visible all-reduce used by the TP2
   quality-cleared path.

The all-reduce is lab work, not attributed to `mndodd`. Keep
`GGML_SYCL_COMM_SINGLE_KERNEL=0` for any topology other than exactly two
peer-visible devices unless it is separately reviewed and validated.

## Reproduce

1. Set a new, empty source destination and build the pinned fork:

   ```bash
   systemd-run --user --scope --collect \
     -p MemoryHigh=5G -p MemoryMax=6G -p MemorySwapMax=8G \
     env LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 JOBS=2 \
     bash build-pinned.sh
   ```

   Stop any loaded model first. The build helper refuses to overlap BMG AOT
   compilation with a live `llama-server` because that overlap caused a reset
   in an excluded lab run.

2. Download and verify the exact target model. Add `WITH_SPEC=1` only if the
   optional MTP/DFlash support rows are needed:

   ```bash
   DEST_DIR=/path/to/models bash download-models.sh
   # WITH_SPEC=1 DEST_DIR=/path/to/models bash download-models.sh
   ```

   The helper pins revisions and refuses to accept a checksum mismatch. Exact
   identities are also listed in
   [validation/2026-08-12-asrock-b70-validation.md](validation/2026-08-12-asrock-b70-validation.md).

3. Reproduce the direct target-only `llama-bench` row (set `GPUS=1` for the
   one-card row). Run only one full model process on this host at a time:

   ```bash
   systemd-run --user --scope --collect \
     -p MemoryHigh=8G -p MemoryMax=10G -p MemorySwapMax=8G \
     env LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 \
     MODEL=/path/to/models/Qwen3.6-27B-Q8_0.gguf GPUS=2 REPS=5 \
     bash bench-target-only.sh | tee /tmp/mndodd-target-only-tp2.jsonl
   ```

4. Launch one of the explicit endpoint recipes:

   ```bash
   LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
     bash run-target-only-tp1.sh
   ```

   ```bash
   LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
     bash run-target-only-tp2.sh
   ```

   ```bash
   LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
   DRAFT_MODEL=/path/to/mtp-Qwen3.6-27B-Q8_0.gguf \
     bash run-mtp4-tp1.sh
   ```

   ```bash
   LLAMA_ROOT=/path/to/llama.cpp-mndodd-4302fb59 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
   DRAFT_MODEL=/path/to/Qwen3.6-27B-DFlash-Q8_0.gguf \
     bash run-dflash5-tp1.sh
   ```

5. In another shell, reproduce the cold endpoint suite:

   ```bash
   BASE_URL=http://127.0.0.1:18080 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
   OUT=/tmp/mndodd-target-only-tp2.json \
     bash bench-fixed-suite.sh
   ```

   That default is the promoted target-only raw-completions contract. To
   reproduce the retained MTP/DFlash support-request identity exactly, use the
   chat API and its original request extras (the result remains support-only):

   ```bash
   BASE_URL=http://127.0.0.1:18082 \
   MODEL=/path/to/Qwen3.6-27B-Q8_0.gguf \
   API_MODE=chat \
   REQUEST_EXTRA_JSON='{"cache_prompt":false}' \
   OUT=/tmp/mndodd-mtp4-support.json \
     bash bench-fixed-suite.sh
   ```

The launchers are loopback-only and do not install services. The pinned build
disables both local web-UI construction and the separate prebuilt-UI download
door, so reproduction does not fetch an unpinned frontend artifact. On a low-RAM
host, run them inside a cgroup at least as strict as `MemoryHigh=8G`,
`MemoryMax=10G`, and `MemorySwapMax=8G`. Never overlap a full model workload
with an Intel BMG AOT build; that overlap produced a GPU reset in an excluded
run on this machine.

Keep TP2 command graphs and the fork's built-in `GGML_SYCL_PROFILE=1` profiler
off. Graph capture either aborted or hung in tensor-split decode, and the TP2
profiler caused `UR_RESULT_ERROR_DEVICE_LOST` plus a compute-engine reset on
both cards. Both devices recovered and passed normal workloads afterward, but
neither path is part of a safe recipe.

## Result and quality detail

See [validation/2026-08-12-asrock-b70-validation.md](validation/2026-08-12-asrock-b70-validation.md)
for the complete commands, resolved doors, A/B identities, hashes, invalid
lanes, host-memory incident boundary, and the distinction between target-only,
MTP, and DFlash results. Compact machine-readable metrics are in
[`validation/results-summary.json`](validation/results-summary.json).

No LocalMaxxing submission was made for this packet.

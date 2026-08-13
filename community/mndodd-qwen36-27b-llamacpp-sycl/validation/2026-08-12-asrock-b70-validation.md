# Reference-lab validation — 2026-08-12

## Verdict

The pinned `mndodd/llama.cpp:intel-sycl-optimization` branch contains real
Intel SYCL/B70 optimization work. With the lab-only compatibility patch in
this packet, Qwen3.6 27B Q8_0 target-only TP2 is quality-cleared at
`31.338764614 tok/s` under the repository's historical helper convention, or
`31.025376968 tok/s` under conventional 99-interval accounting.

The clean endpoint comparison is `+5.836120%` over the accepted
upstream-derived TP2 service (`29.610651330` historical / `29.314544816`
conventional), with 12/12 complete output hashes identical. The fork's
`llama-bench -p 512 -n 128 -r 5` decode mean is `31.255575 tok/s`, `+3.80%`
over the accepted modern control at `30.110121 tok/s`.

No durable greater-than-50 result was found in the public fork. A local
DFlash5 favorable prompt reached `65.00 tok/s`, but its fixed-suite median was
only `38.084045` historical (`37.703205` conventional) and it is speculative.
It must not be quoted as target-only or as the fixed-suite result.

## Provenance

| Item | Exact identity |
| --- | --- |
| Source | <https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization> |
| Tested fork commit | `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126` |
| Upstream merge base | `84e908c625fb60992b4cdef8180fb12fa9b4c4bf` |
| Branch delta | 155 commits; 48 files; +10,395 / -607 |
| Lab patch | `patches/0001-asrock-lab-lowram-dnnless-tp2.patch` |
| Lab patch SHA-256 | `fce3f8e8a296d86630eaa9f9e8e839ff88fa9bb29093a958d5b27d20894d3c68` |

The upstream comparison is not an untouched stock binary. It is the accepted
local runtime based at `84e908c625...`, with Q8 VDR2 and the same
quality-required exact-F32 TP2 mechanism. Its previously deployed service had
SYCL graph support compiled and requested, but the upstream global-device
guard disables capture when more than one device is present, so graph capture
was effectively off for that TP2 control. The request/model/topology contract
is matched; source stack and graph capability remain part of the runtime
identity. Fork graph-on follow-up is recorded below rather than silently
folding that difference into a one-variable claim.

## Reference host

- CPU/RAM: AMD EPYC 9015; 15 GiB physical RAM; 35 GiB swap.
- GPUs: two ASRock Arc Pro B70 32 GiB, PCI ID `8086:e223`, subsystem
  `1849:6025`; full 32 GiB ReBAR; external links at PCIe 5.0 x16.
- OS/kernel: Ubuntu 24.04.4 LTS, `7.0.0-28-generic`.
- Driver: `xe`; card firmware `31.1058`; loaded DMC `2.6`, GuC `70.54.0`,
  HuC `8.2.10`.
- Intel runtime: OMIX `0.3.0-9`, compute runtime `26.22.38646.7-9`.
- Compiler: oneAPI DPC++/C++ `2026.1.0.20260617`.
- ReBAR was enabled; no NVIDIA device/driver was part of this run.

## Model identities

| Role | Repository / revision | File | Bytes | SHA-256 |
| --- | --- | --- | ---: | --- |
| Q8 target | `ggml-org/Qwen3.6-27B-GGUF` @ `8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8` | `Qwen3.6-27B-Q8_0.gguf` | 28,595,762,464 | `73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9` |
| intrinsic MTP sidecar | same repository/revision | `mtp-Qwen3.6-27B-Q8_0.gguf` | 3,164,005,600 | `ad3862cef3dc6a3eaa0525a5b9b225f1c9c45b15956a8314a30cfaa0344a1e08` |
| DFlash draft | `williamliao/qwen3.6-27B-DFlash-GGUF` @ `edb70860182c75bae2e25ab550b79adcfb170a32` | `Qwen3.6-27B-DFlash-Q8_0.gguf` | 1,849,481,536 | `c37b84724fa58cc5c6b545d8b96f8617a8c3bd7f018bf608feef4d3460e0575e` |

The older Intel-branded-host Q8 note recorded a file 32 bytes larger and no
checksum. It is useful as historical performance context, but byte-identical
model provenance to this run is not established.

## Build and resolved configuration

Validated build directory:
`/mnt/fast-ai/src/llama.cpp-mndodd-intel-sycl/build-sycl-aot-bmg-g31`.

- Release; oneAPI 2026.1 `icpx`.
- `GGML_SYCL=ON`, target `INTEL`, `DEVICE_ARCH=bmg_g31`.
- F16, Level Zero API, and VMM support enabled.
- host-memory fallback, SYCL graph capture, and oneDNN/WDC disabled for the
  validated target-only row.
- runtime: MMQ on; global shape caps left unset so the fork's B70 routing
  resolves Q8 MMVQ edge `13` (Q4_0 `16`, Q4_K `24`, Q6_K `11`); Q8 reordered
  wide path on; Q8 activation dedup on; fusion mask `0xF`; FATTN MMA on; QKV
  tile off; deterministic on;
  input-async off; 64 MiB pinned staging; VMM/Level Zero on; system USM off.
- TP2 only: selector `level_zero:1,0`, equal tensor split, and opt-in exact-F32
  single-kernel reduction.

The fork banner incorrectly prints `GGML_SYCL_DNNL: yes` because it tests
whether a zero-valued macro is defined. The following unconditional WDC line
correctly says `UNAVAILABLE (built without GGML_SYCL_DNNL)`, and the build
command/cache has `GGML_SYCL_DNN=OFF`.

Validated binary hashes:

```text
92b21c91d6015e8bc09766bb41d45ce08919830f970001cffdd768805c6f55e0  llama-server
4ed39c952f558fa44e526b918cc75627b5e23f1205bb4e1126c34b2a65e4c956  llama-bench
13059352ab3ec2f2bead8827a3a7729a819f601cc050f5dcd31635ed8979884c  libggml-sycl.so
80c7e23b84201d889f16bfd217599f565c35fe11a1a1acc61e5def25a5cbb17b  libggml-base.so
```

Use `../build-pinned.sh` for a new destination. Its patch and launch scripts
pin the source/model/runtime identities and print the resolved fork doors.

## Lab-only compatibility patch

The patch is intentionally separate from the fork attribution:

1. The fork allocates `1,048,576 * ggml_tensor_overhead()` for each runtime
   metadata context. `ggml_tensor_overhead()` is 368 bytes in this build, and
   this model creates three such contexts (`stc_static`, `stc_compute_0`, and
   `stc_compute_1`): about 1.078 GiB total. The patch uses three 64 MiB
   contexts, 192 MiB total, saving about 912 MiB. Earlier terminal notes saying
   “two hard-coded 1 GiB arenas” were incorrect.
2. A tiny dummy oneDNN enum lets the disabled WDC translation unit compile
   with oneDNN off. It neither enables nor validates WDC.
3. An opt-in two-device peer-visible kernel sums F32 TP partials and writes the
   exact sum to both devices. It is quality-cleared only for exactly two
   peer-visible B70s and remains off by default.

The initial unbounded old-runtime attempt exhausted host memory and froze the
machine. All later model loads used systemd cgroups (`MemoryHigh=8G`,
`MemoryMax=10G`, `MemorySwapMax=8G`); the service charge peaked near 8.59 GB
with about 120–180 MB swap. One GPU reset occurred when a full BMG AOT
compilation overlapped a model benchmark; that contaminated run is
excluded. Later, the fork's built-in TP2 profiler independently caused
`UR_RESULT_ERROR_DEVICE_LOST` and reset both compute engines. Both cards
recovered to `normal` and ordinary workloads passed afterward. Never overlap
build/model workloads, and do not use the fork profiler in TP2.

## Target-only results

### `llama-bench`

Exact shape: target-only Q8_0, F16 KV, TP2 `1/1`, FlashAttention on,
`p512/n128/r5`, ubatch 32, threads 8, poll 50, graph off.

| Runtime | Prompt tok/s | Decode tok/s | Decode samples |
| --- | ---: | ---: | --- |
| mndodd fork + lab patch | 223.829799 | **31.255575** | 31.4373, 31.2433, 31.3007, 31.1529, 31.1436 |
| accepted upstream-derived control | 222.979815 | 30.110121 | 30.0921, 30.0049, 30.1174, 30.1728, 30.1634 |

The fork row is `+3.80%` in decode. `llama-bench` prompt and generation rows
are separate measurements; do not call their harmonic/composite total an
endpoint 512+128 request.

### Fixed cold endpoint suite

Both rows below use raw completions, temperature 0, seed 42, 12 unique prompts
sent once, output 128, F16 KV, no draft, cache RAM off, context checkpoints
off, and `cached_tokens=0` on every request.

| Runtime | Historical helper median | Conventional median | p10 conventional | Wall full128 median | TTFT median |
| --- | ---: | ---: | ---: | ---: | ---: |
| mndodd fork + lab patch | **31.338765** | **31.025377** | 30.876411 | 29.922846 | 179.092 ms |
| accepted upstream-derived control | 29.610651 | 29.314545 | 29.131933 | 26.891133 | 422.350 ms |

The historical helper divides 100 events by the time between event 1 and
event 100, which contains 99 intervals. Conventional values are `legacy *
0.99`; the relative gain remains `+5.836120%`. All 12 complete output hashes
match between fork and control.

Reproduce the fork endpoint with `../run-target-only-tp2.sh`, then run
`../bench-fixed-suite.sh`. The latter emits both accounting conventions.

### One-card target-only control

The one-card follow-up used the same raw-completions, temperature-0, seed-42,
cache-zero contract. The fork default is the promoted TP1 configuration;
forced SG32 is retained only as a diagnostic.

| Runtime | Historical helper median | Conventional median | p10 conventional | Wall full128 median | TTFT median |
| --- | ---: | ---: | ---: | ---: | ---: |
| mndodd fork default | **17.955800** | **17.776242** | 17.665999 | 17.222026 | 276.101 ms |
| mndodd fork, forced SG32 | 17.970729 | 17.791022 | 17.657244 | 17.256945 | 273.563 ms |
| upstream-derived VDR2 control | 17.297038 | 17.124067 | 16.906013 | 15.650260 | 756.186 ms |

The fork default is `+3.809%` over the matched upstream-derived endpoint.
Forced SG32 appeared `+3.65%` over the fork default in `llama-bench`
(`18.134992` versus `17.497254` tok/s), but the endpoint gain was only
`+0.083%`, inside run variance. SG32 therefore remains off by default.

Fork default and the upstream-derived TP1 control produced 10/12 identical
complete hashes. The two divergent greedy completions reflect small floating
order differences, not a demonstrated quality loss: fork TP1 PPL was
`5.635105`, same-top probability was `100.000%`, RMS probability delta was
`0.038%`, and mean KL was `-0.000007`. SG32 versus fork default was also
same-top `100.000%` with RMS delta `0.000%` at printed precision. This is
quality parity at the recorded gates, not bit-exact equivalence.

## Quality

Fresh same-corpus logits/perplexity comparison against the accepted
upstream-derived TP2 build:

- fork PPL `5.635366`; reference PPL `5.635427`;
- same top probability `100.000%`;
- RMS probability delta `0.000%` at printed precision;
- mean KL `-0.000010`, numerical roundoff around zero.

The 12/12 exact complete endpoint hashes provide a second, request-level gate.
In contrast, the fork's stock BF16-compressed TP all-reduce is invalid here:
PPL `19.987962`, same-top only `61.569%`. The exact-F32 path is required.

## One-card speculative support rows

These are useful fork characterization, not the user's target-only objective.
The retained rows used chat mode and `cache_prompt=false`; they did not
explicitly override temperature in the request. Keep them support-only until
they receive a separate matched raw-completions/temperature-0/seed-42 rerun.

| Runtime / route | Target and draft KV | Historical median | Conventional | p10 historical | TTFT median |
| --- | --- | ---: | ---: | ---: | ---: |
| fork MTP4 | F16 / F16 | 39.618445 | 39.222260 | 33.179646 | 295.827 ms |
| upstream MTP4 control | F16 / F16 | 33.163827 | 32.832188 | 27.246682 | 780.807 ms |
| fork MTP4 | Q8_0 / Q8_0 | 39.168618 | 38.776932 | not promoted | separate KV-quality lane |
| fork DFlash5 | F16 / F16 | 38.084045 | 37.703205 | 33.957392 | 296.921 ms |

Fork MTP4 is `+19.463%` over the same-request upstream MTP4 support control.
Fork MTP4 and DFlash5 share 12/12 hashes under their common retained chat
contract; that shows agreement between those routes, not equivalence to the
differently templated target-only completions row. Q8 KV changes outputs and
is a separate quality/capacity class. TP2 DFlash fails during draft/meta tensor
assignment, so no TP2 DFlash result exists.

## Rejected target-only follow-ups

- TP2 graph capture is incompatible with this tensor-split all-reduce path.
  With Q8 dedup enabled, decode aborted because a queue wait was attempted
  during graph recording. With dedup disabled, prompt evaluation completed but
  decode hung. The validated build and launchers keep graph capture off.
- `GGML_SYCL_PROFILE=1` is unsafe for TP2 on this stack. A p32/n12 profile run
  aborted with `UR_RESULT_ERROR_DEVICE_LOST`; kernel logs show a `ccs` reset on
  both B70s at 2026-08-12 21:31:53 local. Do not reproduce this negative.
- Immediate command lists measured `31.319322` tok/s versus a same-window
  control at `31.161186` and the frozen five-rep baseline at `31.255575`; this
  is variance-class and not promoted.
- Input async measured `31.167613` tok/s at p512/n128/r5 and is not promoted.
- Three final `p32/n256/r3` target-only screens were also rejected. Removing
  the root queue's explicit ready barrier measured `32.125197` tok/s versus
  `32.204513` for mode 1 from the same fresh build (`-0.246%`); replaying the
  old validated binary in that window measured `32.143450`, proving the fresh
  build's apparent `+0.190%` was variance rather than a rebuild gain. Forcing
  the fork's PVC-oriented MMVQ phase walk on B70 measured `31.298667` versus
  `32.206087` (`-2.818%`). Reducing locally and using GPU 1's peer-copy engine
  to replicate the exact F32 sum measured `30.996748` versus `31.541103` for
  the unchanged single-kernel path from the same binary (`-1.726%`). All
  experimental source edits were reverted; none extends the packet patch.
- Unequal tensor splits, root reversal, event-barrier completion, and vectorized
  all-reduce screens were neutral or slower. Both cards reached 2800 MHz with
  no throttle during the long control, at roughly 180 W/card against a 275 W
  limit; power or cooling was not the observed constraint.

## Artifact integrity

The compact hashes are in `raw-artifacts.sha256`; machine-readable metrics and
the output-hash arrays are in `results-summary.json`. Raw files remain in the
local benchmark directory named in that manifest because the complete stream
timing JSON is substantially larger than the durable summary.

No LocalMaxxing submission was made.

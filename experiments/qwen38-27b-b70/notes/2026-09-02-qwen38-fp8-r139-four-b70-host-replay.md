# Qwen3.8 27B FP8 TP2 R139: public-chain replay on the four-B70 host

Date: 2026-09-02 22:48--23:30 EDT
Host: `steve-b70s`, Supermicro M12SWA-TF, AMD Ryzen Threadripper PRO 5955WX
(Zen 3, 16 cores, two CCDs, one NUMA node), PCIe Gen4, four Intel Arc Pro
B70 32 GiB (the container selects Level Zero devices 0 and 1 =
`0000:23:00.0` and `0000:27:00.0`, on root ports `20:01.1` and `20:03.1`),
kernel 7.0.0-30, xe with upstream GuC 70.72.1, Docker 29.7.1
Status: recipe closure and correctness gates pass; decode throughput is
1.8x below the published headline on both profiles; attribution in progress

## What was replayed

From a fresh full clone of `steveseguin/b70-optimization-lab` (commit
`66285ee8`), following only
`repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md`:

| step | result |
| --- | --- |
| `verify-public-source-closure.sh` on the fresh clone | PASS (161 tracked files, patch hashes pass, 25 manifest chain files). A `--depth 1` clone fails with `absent from source commit`; the README now says to clone with full history. |
| `verify-model-direct.sh` on `Qwen/Qwen3.8-27B-FP8` revision `017b9c7a` | all 66 weight files match by O_DIRECT and cached reads |
| `build-pinned-mtp1-published-r55c-stack.sh` (binary route) | PUBLIC R55C STACK BUILD COMPLETE, image contract PASS (r55c `sha256:1d1dd0a2...`) |
| `build-draft-int4-r62-image.sh` | r62 `sha256:982f3fb6...` |
| `build-fixed-k-w8a16-r139-published-image.sh` (binary route, release `qwen38-fp8-tp2-r139-20260902`) | r139 `sha256:cbe09ce2...`; installed `_xpu_C.abi3.so` digest `f912e12d...` matches the published extension; release `SHA256SUMS` verified for both `.so` files and all four patches, which are byte-identical to the tracked copies |
| MTP1 server (`run-20260902-qwen38-fp8-mtp1-fixed-k-r139-server.sh`) + `bench-w8a16-mtp1-strict.sh` | workload, cache-zero and canary gates PASS; FP16 verifier and draft-only INT4 head markers logged on both ranks |
| MTP0 server + strict bench | gates PASS |

Docker layer cache: the r15/r31 parents already existed on this host from
earlier work, so the stack rebuild reused cached layers; the image contract
(installed file digests) is what the recipe binds, and it passed.

## Throughput

| profile | this host (class-balanced median, strict natural-512 suite) | published (ASRock two-B70 host, EPYC 9015, PCIe Gen5) |
| --- | ---: | ---: |
| MTP1 (draft-only INT4 head, FP16 verifier) | `28.944616 tok/s` | `54.627286 tok/s` |
| MTP0 | `18.647731 tok/s` (powersave governor), `18.612842 tok/s` (performance governor) | `33.313729 tok/s` |

All six prompt classes sit within 27.5-30.6 tok/s on MTP1, so the factor
(1.89x MTP1, 1.79x MTP0) is uniform and host-wide; the draft gains the same
1.55x over MTP0 that the publishing host records (1.64x).

## Host attribution so far

- ECC: `xpu-smi config -d N` reports Memory ECC current and pending
  disabled on all four cards; PCIe Gen4 downgrade disabled.
- Links: the B70 endpoint (`e223`) always reports `2.5GT/s x1` because it
  sits behind the card's own PCIe switch; the switch upstream ports
  (`21:00.0`, `25:00.0`) run `16.0 GT/s x16` (Gen4, the platform maximum;
  the card supports 32 GT/s). Both cards at 2800 MHz under load.
- CPU governor: `amd-pstate-epp` powersave with EPP `balance_performance`
  (cores 1.4-3.1 GHz under load) versus performance/performance: no change
  (18.65 vs 18.61 tok/s). Governor is not the cause.
- Two-card BF16 all-reduce (host venv, bundled oneCCL, `CCL_ATL_TRANSPORT=ofi`):
  `[1,5120]` 50.8 us, `[1,2560]` 51.1 us, `[8,5120]` 51.0 us, `[64,5120]`
  54.9 us per op; four cards 51-58 us. The publishing host's R61 trace shows
  about 130 all-reduces per decoded token, so this is roughly 6.7 ms of the
  token budget here.
- IOMMU is in translated mode (`AMD-Vi`, default domain Translated, no
  `iommu=pt`), and ACS on both root ports and the card's switch port has
  `ReqRedir+ CmpltRedir+ UpstreamFwd+`, so peer-to-peer writes between the
  two cards are redirected through the root complex and IOMMU. This is the
  strongest remaining fabric-side suspect; testing it needs `iommu=pt` (a
  reboot) or ACS changes on the root ports.
- Host submission latency inside the R139 image on one card
  (`torch 2.13.0+xpu`): tiny elementwise launch 6.2 us submit; launch plus
  synchronize 33.0 us; fp16 matmul `[1,5120]x[5120,5120]` 32.8 us submit /
  89.9 us including sync; `rms_norm [1,5120]` 20.5 us; `.item()` round trip
  59.7 us. These are the numbers for the publishing host to diff against
  with its own probe.
- CPU pinning of the container to one CCD (`docker update --cpuset-cpus
  0-7,16-23`): MTP0 `19.024147 tok/s`, about 2% over unpinned. Placement is
  not the cause.
- XPU Graph on (the qualified profile forces `VLLM_XPU_ENABLE_XPU_GRAPH=0`
  in the strict wrapper; a scratch copy of the wrapper chain with the flag
  set to 1 and the same size-one PIECEWISE compilation config): MTP0
  **`31.149615 tok/s`**, 1.67x the graph-off rate on this host and 94% of
  the publishing host's graph-off `33.313729`; workload, cache-zero and
  canary gates pass. This confirms that the gap is per-launch host
  submission cost, which graph capture removes; the publishing host is fast
  enough that R58 measured graph-on as 1.1% slower there.
- XPU Graph on for MTP1 with the same size-one capture: `28.560275 tok/s`,
  no change from graph-off (`28.944616`). With capture size 1 only the
  single-row target step is captured; the draft step and the two-row
  verification run eagerly, so on this host the draft's own launch cost
  cancels its token gain (graph-on MTP1 is slower than graph-on MTP0 here).
  With `cudagraph_capture_sizes` `[1,2]` and `max_cudagraph_capture_size`
  2 (so the two-row verification step is captured too): MTP1
  **`51.318302 tok/s`**, 1.77x graph-off on this host and 94% of the
  published `54.627286`; workload, cache-zero and canary gates pass.
- Pure-Python single-thread timing (`timeit`, one core): `sum(range(1000))`
  x20000 `0.169 s` here (0.179 s inside the image) versus `0.132 s` on the
  publishing host; dict loop `0.034 s` versus `0.026 s`. The CPU is about
  28% slower single-thread, which does not by itself explain 1.8x; the
  publishing host's two-card all-reduce is 13 us against 51 us here (4x),
  and this host's IOMMU is in translated mode with ACS redirect on the root
  ports. `iommu=pt` is the next test (reboot, user-authorized).

## After the `iommu=pt` reboot (2026-09-03 00:10-00:25)

- `/proc/cmdline` carries `iommu=pt`; the kernel reports `Default domain
  type: Passthrough`. Two-card BF16 all-reduce `[1,5120]`: 48.2 us (was
  50.8). Clearing ACS `SrcValid/ReqRedir/CmpltRedir/UpstreamFwd` on both root
  ports and both card switch ports (`setpci ECAP_ACS+6.w=0`): 47.8 us. The
  server's own collective environment (`CCL_TOPO_P2P_ACCESS=1`,
  `CCL_ZE_IPC_EXCHANGE=pidfd`), `twoshots`, a raised LL threshold, and even
  `CCL_TOPO_P2P_ACCESS=0` all sit at 47-56 us. The collective's floor here is
  not the fabric route; it is the per-launch and sync cost inside the
  collective.
- The publishing host's probe (`qwen38-fp8-host-submission-latency-probe.py`,
  its data file `2026-09-02-qwen38-host-submission-latency-probe-two-b70-host.json`)
  run on both hosts inside the R139 image:

  | measure | publishing host | this host |
  | --- | ---: | ---: |
  | async launch | 3.13 us | 5.18 us |
  | launch + sync | 25.98 us | 30.22 us |
  | native `rms_norm` at M=2 | 41.5 us | 133.9 us |

  Per-launch submission is 1.65x slower here and launch-heavy ops 3.2x,
  against a 1.28x pure-Python gap, so the driver and firmware submission
  path adds to the CPU difference. This is the whole of the 1.8x decode gap:
  the graph-off profile exposes it about 130 times per token, and graph
  capture hides it (MTP0 31.1, MTP1 51.3 tok/s above).

- MTP0 graph-off under `iommu=pt` (ACS cleared partway through the run):
  `18.721904 tok/s`, unchanged from 18.65.
- GuC firmware: with the distro `70.44.1` reloaded in place of upstream
  `70.72.1`, the same probe reads 5.15 us launch, 31.2 us launch plus sync,
  132.3 us `rms_norm` M=2, identical to 70.72.1. Firmware is not a factor;
  70.72.1 was reinstalled afterwards.

- `cudagraph_mode` FULL_DECODE_ONLY (sizes `[1]`, MTP0): `31.526087 tok/s`,
  about 1% over PIECEWISE; the image's `all_reduce` is a host-waited
  `torch.distributed` call, so the collectives stay outside the graph either
  way. MTP1 FULL_DECODE_ONLY with sizes `[1,2]`: **`52.051144 tok/s`**,
  95.3% of the published `54.627286`; outputs identical to graph-off MTP0
  on 12/12 prompts; workload, cache-zero and canary gates pass.
- Output identity of the graph arms: the strict bench's 12 per-prompt
  output digests (`performance.json` `output_sha256s`) of MTP0 graph-on
  (PIECEWISE and FULL_DECODE_ONLY), MTP1 graph-off, MTP1 graph-on `[1]` and
  MTP1 graph-on `[1,2]` are all identical, 12/12, to graph-off MTP0 on this
  host, and the prompt digests match. Graph capture is identity-clean here
  on this suite; the c1-c64 ladder has not been run on the graph-on profile.

## 2K-32K real-content depth on this host, graph on (FULL_DECODE_ONLY)

Same fixture and harness as R150 (three content classes, three requests per
depth, medians), MTP0 oracle arm first:

| active context | MTP0 decode (this host, graph on) | MTP0 TTFT | published MTP0 (graph off, EPYC host) |
| ---: | ---: | ---: | ---: |
| 2K | `31.124 tok/s` | `0.651 s` | `33.364` |
| 4K | `30.850 tok/s` | `1.275 s` | `32.976` |
| 8K | `30.376 tok/s` | `2.603 s` | `32.110` |
| 16K | `29.734 tok/s` | `5.408 s` | `31.411` |
| 24K | `29.071 tok/s` | `8.420 s` | `30.625` |
| 32K | `28.493 tok/s` | `11.627 s` | `29.961` |

All 18 request gates passed; classification "Grade B three-class unrepeated
real-content exact-depth HTTP evidence".

MTP1 graph-on (`FULL_DECODE_ONLY`, sizes `[1,2]`) against that oracle:

| active context | MTP1 decode (this host, graph on) | MTP1 TTFT | published MTP1 (graph off, EPYC host) |
| ---: | ---: | ---: | ---: |
| 2K | `51.216 tok/s` | `0.666 s` | `54.811` |
| 4K | `52.556 tok/s` | `1.299 s` | `55.448` |
| 8K | `51.038 tok/s` | `2.655 s` | `54.139` |
| 16K | `50.077 tok/s` | `5.533 s` | `53.048` |
| 24K | `49.997 tok/s` | `8.619 s` | `52.882` |
| 32K | `49.125 tok/s` | `11.925 s` | `51.929` |

Every MTP1 array matched the same-image MTP0 oracle (`all_target_oracle_exact`
true, 18/18) and all request gates passed. On this host the graph-on line
holds 90-94% of the published MTP1 curve and 93-95% of the MTP0 curve from
2K to 32K, with identical outputs to its own MTP0 oracle.

## c1-c64 identity ladder, graph on (MTP1, `FULL_DECODE_ONLY` `[1,2]`)

Same harness, suite and server shape as R147/R147c (`MAX_MODEL_LEN=256`,
`MAX_NUM_SEQS=64`, `MAX_NUM_BATCHED_TOKENS=512`; 64 sequential oracles then
1-64 concurrent users, 128 tokens, `--require-output-identity`):

| users | outputs byte-identical to the sequential oracle | aggregate tok/s |
| ---: | ---: | ---: |
| c1 | 1/1 | `49.7` |
| c2 | 2/2 | `47.3` |
| c4 | 4/4 | `104.6` |
| c8 | 8/8 | `219.7` |
| c16 | 16/16 | `366.8` |
| c32 | 29/32 | `714.6` |
| c64 | 59/64 | `922.9` |

Identity holds through c16 exactly as the publishing host's graph-off
qualification does (R139: c16 exact, c32 30/32, c64 55-58/64); the c32 and
c64 misses are the same residual per-sequence kernel class, not a graph
effect. The graph-on MTP0 ladder is recorded below when measured.

## Transferable result

On a host whose per-launch and per-collective latency is higher than the
publishing host's, the qualified graph-off profile pays about 130 exposed
host round trips per token. Enabling XPU Graph with capture sizes that cover
both the one-row target step and the two-row MTP1 verification recovers
94% of both published headlines here (MTP0 31.1, MTP1 51.3 tok/s). On the
publishing host graph capture measured 1.1% slower (R58), which is why the
qualified profile ships graph-off; the package should state the measuring
host and name graph capture as the setting for slower hosts, with the
identity gates unchanged (all four graph arms passed the strict workload,
cache-zero and canary gates here; output identity against the oracle was
not part of this replay's gate set and is the next check before any
recipe text recommends it).

## Reading

The recipe is complete and reproducible in the sense the user asked about:
every file a third party needs is tracked or released, every digest matches,
the chain builds without a compiler, and the served outputs pass the
workload gates. What does not transfer is the decode rate, which on this
Gen4 Zen 3 host is 1.8x lower for both profiles. That belongs in the
package as an independent-host replay record with the host identity, not
as a change to the headline.

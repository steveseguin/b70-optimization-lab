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
- CPU pinning of the container to one CCD: result below when measured.

## Reading

The recipe is complete and reproducible in the sense the user asked about:
every file a third party needs is tracked or released, every digest matches,
the chain builds without a compiler, and the served outputs pass the
workload gates. What does not transfer is the decode rate, which on this
Gen4 Zen 3 host is 1.8x lower for both profiles. That belongs in the
package as an independent-host replay record with the host identity, not
as a change to the headline.

# Xe2 M6 joint gate/up and canonical down runtime result

Date: 2026-07-13 UTC

## Outcome

The protected llama.cpp experiment now has two additional default-off M=6
boundaries:

- `GGML_SYCL_XE2_Q4_M6_GATE_UP=1` recognizes adjacent same-layer gate/up
  projections, quantizes their shared six-row activation once, and submits both
  packed matrices in one ESIMD launch;
- pack slots 130-186 cover the 57 Q4_0 down projections in layers 8-64. Layers
  0-7 are Q4_1 and remain on production. `PACK_LIMIT=187` enables all 130
  gate/up plus all 57 eligible down tensors.

The first joint gate/up strict JIT crossover passed the fixed cold realistic
suite at `41.451 tok/s` median, `35.206` p10, and `41.416` mean versus a
same-build control at `40.406`, `34.265`, and `40.505`. This is `+2.59%`
median and `+2.75%` p10. Both suites had every `cached_tokens` value zero.

## Down semantic fix

The earlier `~0.0651` synthetic down-projection delta came from independently
recomputing Q8_1 half metadata, not DPAS integer arithmetic. The runtime now
uses the existing fast joint quantizer for K=5120 gate/up, but for K=17408 down
it creates canonical row-major Q8_1 `(quants,d,sum)` and performs a lightweight
SoA repack. The signed-S4 DPAS epilogue reconstructs the exact production
expression from canonical `d`, `sum`, and quant sum.

A real shadow of `blk.8.ffn_down.weight` measured maximum absolute error
`1.00582838e-07`, mean `7.88174409e-09`, and RMS `1.1051548e-08`. This is far
inside the integration gate and much tighter than the experiment comparator.

Using canonical quantization for every projection was a useful negative test:
it made full down coverage faster than its matching canonical gate/up control,
but unnecessarily taxed gate/up. The hybrid K-specific choice restored the
fast gate/up boundary.

## Full hybrid JIT result

The first full hybrid `PACK_LIMIT=187` strict cold suite passed at:

- median tokens 1-100 after TTFT: `45.48436443093152 tok/s`;
- p10: `36.93681919042129 tok/s`;
- mean: `43.13513602117612 tok/s`;
- median full-output after TTFT: `42.83251315886593 tok/s`;
- median wall full128: `30.849938438064328 tok/s`;
- median TTFT: `1161.7111100349575 ms`;
- all 12 prompts fresh, unique, and `cached_tokens=0`.

This is `+12.57%` versus the same-build `40.406 tok/s` production-dispatch
control and `+15.89%` versus the promoted `39.249 tok/s` BMG-AOT record. It is
a major JIT milestone, not yet a promoted record. A fresh BMG-AOT build and an
AOT strict reproduction are mandatory before LocalMaxxing submission.

## Evidence

- joint candidate:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-joint-gateup-jit-realistic128-20260713T1238Z.json`;
- joint control:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-joint-gateup-control-jit-realistic128-20260713T1241Z.json`;
- hybrid full187 candidate:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-hybridquant-full187-joint-jit-realistic128-20260713T1252Z.json`;
- real down shadow server:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-jit-canonical-down8-shadow-gpu3-20260713.log`;
- full hybrid server:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/servers/xe2-m6-jit-hybridquant-full187-joint-gpu3-20260713.log`.

The protected source remains dirty and must not be reset. At promotion time,
capture the relevant `mmvq.cpp`, `mmvq.hpp`, `ggml-sycl.cpp`, and tensor-extra
lifecycle delta together with the exact source HEAD and build identities.

## AOT promotion and LocalMaxxing

The fresh BMG-AOT build reproduced the strict win at `42.64100140442767 tok/s`
median, `37.01181540273963` p10, and `42.956598510610235` mean. Median
full-output throughput was `42.38079625519468 tok/s`, wall full128 was
`30.166061475797108 tok/s`, and TTFT was `1162.638435489498 ms`. The fixed
realistic gate passed with all cache counts zero.

This is `+8.64%` over the matching promoted gate/up-only AOT record. LocalMaxxing
approved it as `cmrj8fygq029ymj01e2404psy` (HTTP 201). The queue and response
are preserved under the lane's `localmaxxing/` folder and
`data/localmaxxing-responses/` respectively.

## GDN cache fusion composes: 44.255 tok/s

The previously verified `GGML_SYCL_FUSE_GDN_CACHE=1` boundary was then enabled
on top of the exact same 187-pack BMG-AOT DFlash5 identity. It writes each GDN
rollback snapshot directly into its persistent cache and skips the 48 tail
copies and their views. The fixed cold suite passed again with every cache
count zero:

- median tokens 1-100 after TTFT: `44.25538817570995 tok/s`;
- p10: `38.147152482432936 tok/s`;
- mean: `44.348085291972346 tok/s`;
- median full-output after TTFT: `44.52145461698231 tok/s`;
- median wall full128: `31.76169603511224 tok/s`;
- median TTFT: `1155.4772414965555 ms`.

This is `+3.79%` over the matching `42.641` AOT record. It matters because it
shows that recurrent-state traffic removal and packed projection acceleration
are additive at the real native-DFlash M=6 boundary. LocalMaxxing approved the
new single-session one-B70 record as `cmrj8s2sy02a4mj01f18hanvc`.

Evidence:

- `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-full187-joint-gdncache-aot-realistic128-20260713T130908Z.json`;
- `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/xe2-m6-full187-joint-gdncache-aot-realistic128-20260713T130908Z/`;
- `experiments/qwen27-dflash-sycl-b70/localmaxxing/qwen36-27b-q4_0-xe2-m6-gateup-down-gdncache-dflash5-20260713.queue.json`;
- `data/localmaxxing-responses/qwen36-27b-q4_0-xe2-m6-gateup-down-gdncache-aot-20260713.submit.log`.

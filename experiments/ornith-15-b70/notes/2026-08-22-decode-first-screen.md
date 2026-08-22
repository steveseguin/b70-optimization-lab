# Ornith 1.5 decode: storage confound and command-graph closure

Date: 2026-08-22 EDT

Status: **dense command graphs neutral; slow-NFS mmap result invalid as a model
performance baseline**

## Identity and protocol

- Model: Ornith 1.5 9B Q8_0,
  SHA-256 `6874eeb25c71081dc8f0bbe88f3ebb786312447132745371cd980bce95d259b9`.
- llama.cpp: `9fee29e9435f865ec0b811a783a6471a136d9317`.
- `llama-bench` SHA-256:
  `598cb811537c16c07ec702c3f698dc1ebaa79ca2f7b2424539cf06a10df6fb96`.
- Host: AMD EPYC 9015, one visible Intel Arc Pro B70, kernel
  `7.0.0-28-generic`, oneAPI DPC++ 2026.1.1.
- Test: target-only `p0/n128/d0`, F16 KV, flash attention on, 99 GPU
  layers, seven repetitions. The graph flag was the only candidate variable in
  the matched local-file pair.

## Result

| File placement | Graph | Mean tok/s | sigma | Classification |
| --- | ---: | ---: | ---: | --- |
| internal NVMe | 0 | 50.149374 | 0.003441 | matched control |
| internal NVMe | 1 | 50.168845 | 0.022217 | +0.0388%, neutral |
| 100 Mb/s NFS mmap | 0 | 26.019467 | 1.751748 | storage-confounded diagnostic |
| 100 Mb/s NFS mmap, exact packet command | 0 | 25.642026 | 1.376206 | storage-confounded diagnostic |

The reverse local control disproved the initial hypothesis that command graphs
caused the apparent 2x gain. Graph on/off is flat. The difference was model
placement: the NFS-backed mmap continued to impose I/O stalls during measured
decode, while the byte-identical internal copy restored the already-published
50 tok/s range. The local copy was checksummed after copying.

## Consequences

1. Do not use a slow network-backed mmap run as a decode baseline.
2. The public beginner recipe should explicitly require local SSD or adequately
   fast direct-attached storage. A future network-storage lane may test an eager
   read/preload mode, but it needs enough host RAM and is a usability screen,
   not a kernel speed claim.
3. Do not promote `GGML_SYCL_ENABLE_GRAPH=1` for dense Ornith 9B on this stack.
4. Continue kernel work from the valid ~50 tok/s Q8_0 baseline. A 2x gain from
   there likely requires a lower-bit quantization and/or verified speculative
   decode, not generic command capture.

Raw evidence is retained beside this note under `../data/`.

# DFlash pure Q8_0 inference screen: exact but substantially slower

Date: 2026-08-13

## Question

Can a pure Q8_0 conversion of the already-trained BF16 DFlash reduce proposal
time without changing acceptance? This is an inference-format experiment only;
no drafter training was performed and the BF16 TP4 target/verifier was unchanged.

## Artifact

- BF16 source: `/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-bf16.gguf`
- Q8_0 output: `/mnt/usb-models/Muse-Glimmer-30B-DFlash-Q8_0.gguf`
- Q8_0 SHA256: `3c8c7eabc08af725fd0601a76b9157e00fbf981ffa65f4c17b554307d3a4cdbb`
- Conversion: `llama-quantize --pure ... Q8_0`
- Size reported by quantizer: 4875.31 MiB to 2590.15 MiB, 16.00 to 8.50 BPW

## Run identity

- Source HEAD: `1ff6bcb6c1d9c175145bd4c212c24bb2fb13f539`
- Binary: `build-sycl-b70-aot-bmg-g31/bin/llama-server`
- Target: Muse Glimmer 30B BF16, TP4, tensor split, width 16 verifier
- Draft: DFlash, n-max 15, p-min 0, candidate top-k 15
- Retained kernel stack: distributed top-k, tree merge, block 512, heap scan,
  last-event allreduce readiness, FFN batch2, BF16 conversion caches,
  parallel meta submission, RMS fusion, backend sampling
- Workload: canonical prose/code/JSON, 64 output tokens, BF16/Q8/BF16 A/B/A
- JSONL: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-q8-pure-smoke64-20260813.jsonl`
- JSONL SHA256: `c57b12e0b811e413593474893d3b106f37dffc20a7fd9f3e260d437a8b83d0c9`

Server logs and SHA256:

- BF16 before: `.../sweep-dflash-q8-pure-smoke64-20260813-dflash-bf16-control.log`, `5e2161873ee660fe92b57667563de7ffd6888be57bf8e98c7cc972690f586391`
- Q8_0: `.../sweep-dflash-q8-pure-smoke64-20260813-dflash-q8-pure.log`, `2e0bcf8ade54624f09c21faa622ff89271322f04271dd5a0133d560ce992b5ce`
- BF16 after: `.../sweep-dflash-q8-pure-smoke64-20260813-dflash-bf16-control-after.log`, `c83d6d7aaa6739db992e6fc1c37af734a85a68468d2682408f19c1eb5ac0d2e2`

## Result

| Class | BF16 before | Q8_0 | BF16 after | Q8 vs interpolated BF16 |
|---|---:|---:|---:|---:|
| prose | 68.591 | 57.264 | 69.413 | -17.01% |
| code | 114.765 | 93.276 | 114.516 | -18.64% |
| JSON | 216.097 | 176.775 | 220.386 | -19.00% |
| arithmetic mean | 133.151 | 109.105 | 134.772 | -18.55% |

Correctness and proposal structure were exactly unchanged:

- output hashes: `f45a2f2c58f1ca34`, `2ca4135046a15a71`, `32dc3aebb11684a4`
- generated/accepted: 155/48, 126/53, 65/58
- acceptance: 31.0%, 42.1%, 89.2%

The cumulative DFlash generate timer after all three prompts was 563.813 ms for
Q8_0 versus 198.697/199.806 ms for the BF16 controls. Q8_0 therefore made the
proposal phase about 2.83x slower even though it halved artifact size and
preserved the exact proposal/acceptance outcome. The B70 BF16/XMX path is much
better suited to this workload than the available Q8_0 path.

## Decision

Close pure Q8_0 DFlash on the current kernels. Do not spend a full 256-token
suite on it and do not infer that smaller weights imply lower proposal latency.
Only reconsider after a materially different XMX-accelerated Q8 kernel exists.

Production was restored after the sweep. Full model/code/vision health passed:
`data/muse-health-20260813T1815Z-dflash-q8-negative-restore.json`.

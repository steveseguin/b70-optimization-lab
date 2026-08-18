# Server-Side Decode Timing Evidence

## Source: llama-server internal timing from systemd service logs

## Aug 17, 2026 — Initial MTP2/MTP3 A/B Test (Cold Fusion GAIN V1.1 Q4_K_M)

### GPU 0 (MTP 2, port 8001)
```
Aug 17 14:22:13 Dom-PC-2 launch-qwen38-q4-gpu0.sh[3116150]:
  prompt eval time = 146.60 ms / 4 tokens (27.29 tokens per second)
  eval time = 1302.75 ms / 51 tokens (38.38 tokens per second)
  draft acceptance = 0.94444 (34 accepted / 36 generated), mean len = 2.89

Aug 17 14:22:15 Dom-PC-2 launch-qwen38-q4-gpu0.sh[3116150]:
  prompt eval time = 143.49 ms / 4 tokens (27.88 tokens per second)
  eval time = 1302.71 ms / 51 tokens (38.38 tokens per second)
  draft acceptance = 0.94444 (34 accepted / 36 generated), mean len = 2.89
```

### GPU 1 (MTP 3, port 8002)
```
Aug 17 14:22:10 Dom-PC-2 launch-qwen38-q4-gpu1.sh[3121457]:
  prompt eval time = 499.47 ms / 24 tokens (48.05 tokens per second)
  eval time = 1258.07 ms / 51 tokens (39.74 tokens per second)
  draft acceptance = 0.90476 (38 accepted / 42 generated), mean len = 3.71

Aug 17 14:22:12 Dom-PC-2 launch-qwen38-q4-gpu1.sh[3121457]:
  prompt eval time = 147.09 ms / 4 tokens (27.19 tokens per second)
  eval time = 1250.38 ms / 51 tokens (39.99 tokens per second)
  draft acceptance = 0.90476 (38 accepted / 42 generated), mean len = 3.71
```

## Key Metrics

| GPU | MTP | Decode (tok/s) | Acceptance | Mean Draft Len |
|-----|-----|:---:|:---:|:---:|
| 0 | 2 | **38.4** | 94.4% | 2.89 |
| 1 | 3 | 40.0 | 90.5% | 3.71 |

## KV Type A/B Test (same GPU, same build, same model)

| KV Config | Decode | MTP Accept |
|-----------|:---:|:---:|
| **Unsloth Q4 + f16 + MTP2** | **44.4 t/s** | 100% |
| Cold Fusion Q4 + **q8 KV** | 10.3 t/s | 41-47% |
| **Cold Fusion Q4 + f16 KV + MTP2** | **38.2-38.5 t/s** | 94-97% |

**Critical finding**: F16 KV is required on SYCL B70. Q8 KV collapses decode
by 70%+ on the SYCL backend.

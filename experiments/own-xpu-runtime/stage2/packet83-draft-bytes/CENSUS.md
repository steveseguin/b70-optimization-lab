# Packet83 draft byte census

The head is the largest byte reduction available to these two registered arms.
Halving its useful weight reads projects about **260 microseconds**, or **1.62%**
of a 16.1 ms hit cycle, before changes in acceptance or kernel overhead.
These are projections, not new speed measurements. No GPU work ran here.

Reproduce from the repository root:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/packet83-draft-bytes/census.py </dev/null
```

The script reads packet77's raw `sites.jsonl` files and receipts, uses its frozen
`timeline.extract` hit mapping, and groups draft events by request and position.
It retains source SHA256 hashes and all 76 sampled hit-group summaries in
[evidence/census.json](evidence/census.json). It reads no benchmark text to choose
the prefix. Tensor shapes and types come from packet75's `mtp-manifest.tsv`;
runtime representation comes from `mtp.hpp` and the expanded-weight loader.

| Draft part | Mean event time, microseconds | Useful weight bytes |
| --- | ---: | ---: |
| Head prefix | 520.779 | 292,454,400 |
| Attention | 387.464 | 102,894,592 |
| HC, including hidden projection | 250.511 | 92,078,080 logical reads; 52,756,480 resident |
| Experts and router | 251.374 | 61,440,000 selected experts + 2,621,440 router |
| Shared expert | 44.476 | 9,835,520 |
| Embedding projection and norm | 60.171 | 13,117,440 |
| Argmax | 21.084 | Activation reads |
| Transfers | 2.581 | Separate copy events |
| Other | 6.186 | Small control work |

Dense attention, HC and shared weights are BF16; norm gains expand to F32.
Draft experts are official FP8 converted to INT8 with FP32 scales per 16 values.
Ten experts are selected; all 512 resident experts occupy 3,145,728,000 bytes.
HC logical reads count four hidden-projection streams using the same matrix;
cache reuse means this is not DRAM traffic. Activation and context-dependent KV
traffic are additional to the weight inventory. The MTP block remains unchanged.

The measured draft wall mean is **1,746.439 microseconds**. The sum of its 62
events is **1,544.627 microseconds**, leaving **201.812 microseconds** unattributed.
Positive-duration device timestamps contain 129.703 microseconds of envelope
gaps. This does **not** isolate fixed launch overhead: CPU embedding access,
submission, waits and instrumentation also contribute. The brief's approximate
1.72 ms/508 microsecond head/328 microsecond HC values are historical context;
this census reports the current packet77 raw sample without renormalizing it.

The existing head is Q6_K: 2,100 bytes per 2,560-column row in GGUF. Runtime
useful reads are 2,560 INT8 codes plus 640 bytes of FP32 scales = **3,200 bytes**.
The allocated stride is **3,380 bytes**, including 180 bytes of retained source
metadata (`packet10-kopt5/expanded.hpp::row_bytes`). The current prefix therefore
reads 292,454,400 useful bytes; its equivalent allocation extent is 308,904,960 bytes.
The target's complete shared allocation
remains 839,321,600 bytes. Prefix reduction alone frees no resident head memory.

The separate Q4 copy derives from the existing authenticated **Unsloth Q6_K
GGUF**, an owner-allowed on-disk source, not original BF16 weights. Q4 groups of
32 require 1,280 code bytes plus 320 scale bytes = **1,600 bytes/row**. A claimed
1,440-byte row would require groups of 64 and is not this registered format.

| Arm | Prefix rows | Independent coverage | Extra VRAM | Projected hit saving |
| --- | ---: | ---: | ---: | ---: |
| Q4 groups32 | 91,392 | 99.512245% | 146,227,200 bytes | 260.389 us / 1.617% |
| Prefix 99.0% | 80,128 | 99.014222% | 0 | 64.186 us / 0.399% |
| Prefix 98.5% | 74,752 | 98.557273% | 0 | 94.820 us / 0.589% |

N is the smallest multiple of 256 satisfying the registered coverage threshold
on packet56's frozen independent-text histogram: 19,477 tokens across five
whole sources. The new prefixes cover 19,285 and 19,196 tokens, against 19,382
currently. Conditional coverage-ratio illustrations are 0.783061 and 0.779448
acceptance, starting from 0.787. These are **not measured or predicted acceptance**;
text-token coverage cannot determine generated proposal accuracy. Q4 retains the
prefix coverage but its numerical acceptance effect is unknown. Each device screen
must report actual acceptance. `coverage.json` retains its original approximate
508-us projections; this census uses the raw packet77 520.779-us head mean.

At placement 1, context 4096, packet75's memory model leaves rank 1
2,973,906,230 bytes free and 945,091,894 bytes under its arena limit. The separate
Q4 copy leaves **2,827,679,030 bytes free** and **798,864,694 bytes arena headroom**,
before any extra implementation scratch. This fits the inherited model; full-shape
startup allocation and memory-admission gates must still verify the actual arm.

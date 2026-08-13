# Qwen3.6 27B Q8 target-only TP2 on two ASRock B70s

## Outcome

The 2026-08-13 target-only optimization campaign reached **35.494434 tok/s**
under conventional 99-inter-token-interval accounting on two ASRock Intel Arc
Pro B70 32 GiB cards. The historical repository helper reports `35.852963`
from the same timestamps. No draft model, MTP, DFlash, n-gram reuse, prompt
cache, response reuse, or speculative decoding was used.

This clears the requested 30 tok/s two-card target without relaxing Q8_0
quality. All 12 fixed-suite outputs, each 512 tokens long, are byte-for-byte
identical to the accepted pre-state-I/O target-only control.

## Promoted measurement

| Metric | Result |
| --- | ---: |
| Conventional 99-interval median | **35.494434 tok/s** |
| Conventional p10 / mean | `34.958732` / `35.506893 tok/s` |
| Historical 100-event compatibility median | `35.852963 tok/s` |
| Full 512-token after-TTFT median | `35.437512 tok/s` |
| Full 512-token wall median | `34.954163 tok/s` |
| Median TTFT | `174.892 ms` |
| Fixed prompts / completion length | `12 / 512 tokens each` |
| Cache / fresh gate | `cached_tokens=0` for 12/12; passed |
| Exact output identity | `12/12` hashes equal the accepted control |

The primary metric is the median across the 99 actual intervals between
streamed events 1 and 100 after TTFT. The compatibility field uses the older
`100 / same span` helper, so it is exactly `conventional / 0.99`.

## Attribution and progression

Matthew Dodd's
[`intel-sycl-optimization`](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization)
fork is the source base. Its matched ASRock-B70 TP2 fixed-suite result was
`31.025377 tok/s` conventional and was already `+5.836%` over the matched
upstream-derived control. The contributor's original code, links, validation,
and attribution remain in the
[`community/mndodd-qwen36-27b-llamacpp-sycl/`](../../community/mndodd-qwen36-27b-llamacpp-sycl/)
packet.

The lab progression from that fork was:

| Stage | Conventional median | Increment |
| --- | ---: | ---: |
| Matched mndodd fork baseline | `31.025377` | — |
| Lab fusion stack before direct state I/O | `33.967039` | `+9.481%` vs mndodd |
| Direct GDN persistent-state I/O | `35.030949` | `+3.132%` |
| Direct convolution persistent-state I/O, matched attribution run | `35.330307` | `+0.855%` |
| Promoted full-recipe confirmation | **`35.494434`** | `+0.465%` run variance vs prior final |

The promoted result is **`+14.405%`** over the matched mndodd fork baseline.
The direct-state-I/O attribution percentages use the preceding matched
512-token run, which was `+13.876%` over mndodd; the faster replay is reported
as run variance, not credited as another source optimization. Relative gains
are unchanged by multiplying all helper rates by `0.99`.

## Model and runtime identity

- Model repository: <https://huggingface.co/ggml-org/Qwen3.6-27B-GGUF>
- Revision: `8a7ee08e8b9bfb857107ecc25a5599d2f38b76f8`
- File: `Qwen3.6-27B-Q8_0.gguf`
- File bytes: `28,595,762,464`
- Model SHA-256:
  `73f8260284708ed78ae266df672288b6ad1f2c73ec7ffeb7514b5cecdba646c9`
- Runtime base: mndodd llama.cpp commit
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- Compilers: GNU C 13.3.0 (`/usr/bin/cc`) and Intel oneAPI DPC++/C++
  2026.1.0 (`20260617`) for C++/SYCL
- Intel stack: OMIX `0.3.0-9~24.04`, GPU compute
  `26.22.38646.7-9~24.04`
- Kernel: `7.0.0-28-generic`
- Build: Unix Makefiles, shared Release, `bmg_g31` AOT, `LLAMA_CURL=OFF`, SYCL
  F16 and Level Zero API on; graph, DNN, and host-memory fallback off.

The complete decoded source patch SHA-256 is
`7856dd62f711fb36cb2ae59191717eb15c2967ff49eb609bda5f6eea218736bd`.

## What improved

The preserved full patch combines the earlier accepted lab stack with two new
strictly admitted state-I/O transformations:

1. The recurrent GDN path normally copied a 1.5 MiB persistent state row into
   a temporary, ran GDN into another temporary, and copied the state back.
   For the exact one-sequence, one-retained-slot Qwen decode shape, every
   workgroup owns a complete independent state column. The optimized kernel
   loads and updates the persistent state in place, eliminating the matched
   `GET_ROWS` and `CPY` launches.
2. The recurrent convolution path normally performed
   `GET_ROWS -> CONCAT -> CPY + SSM_CONV`. For the exact one-token,
   `d_conv=4`, 5,120-channel shape, a channel-local kernel reads its three
   persistent values and current value, performs the stock four-term loop in
   the same order, writes the convolution result, and shifts the persistent
   state in place.

Both matchers require exact tensor types, shapes, strides, consumer counts,
pointer relationships, and non-overlap. Any alternate batch, state, or graph
layout falls back to the stock route.

The earlier accepted stack also includes exact-F32 two-card collective and
residual/RMS/Q8 handoffs, repeated activation-quantization deduplication,
SWIGLU/attention/GDN Q8 producers, recurrent paired/triple/quad MMVQ dispatch,
beta-sigmoid fusion, and bounded 64 MiB meta-backend arenas for this low-RAM
host. Runtime scheduling uses immediate Level Zero command lists with copy
offload disabled.

## Correctness evidence

The final cold suite passed:

- 12 unique prompts, each sent once;
- 512 completion tokens for every row;
- `cache_prompt=false`, cache RAM zero, context checkpoints zero;
- `temperature=0`, seed 42;
- 12/12 complete output hashes equal the pre-state-I/O oracle;
- all 12 reported `cached_tokens=0`;
- realistic final gate and fresh-response validity both true.

The convolution state-I/O red-control set
`GGML_SYCL_FUSED_CONV_STATE_IO_POISON=1`. The first prompt changed from clean
hash `f17ef1d3…` to poison hash `5f3cfc1c…` and produced visibly corrupted
text, proving the green gate exercised the new kernel. The poison variable is
explicitly unset in the production and reproduction launchers.

An initial convolution prototype used four explicitly written multiply-adds.
It was faster but changed 1 of 12 output hashes, so that implementation was
rejected. Restoring the stock runtime loop form recovered 12/12 exactness
while retaining the gain.

## Bounded negative results

These doors were tested and rejected rather than left enabled:

- GDN workgroup packing at 2, 4, 8, and 16 subgroups was flat within about
  `0.08 tok/s`; the original 4-subgroup setting remains.
- Batched Q/K normalization plus in-kernel RoPE matched all 12 short-suite
  hashes but was effectively flat and was removed.
- Earlier VDR2/VDR8, scale-broadcast, alternate GDN quad/reuse, convolution to
  SiLU, Q8 cache, async tensor copy, root-barrier, forced PVC phase ordering,
  and root-local peer-replication experiments were rejected or reverted.
- DFlash and MTP were excluded from this target-only objective even where they
  produced higher workload-dependent rates.

The rejected local logs remain under
`/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion` on the
reference host so the dead ends are not rediscovered.

## Reproduction and evidence

- [Reproduction recipe](../../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [Full source patch](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [Readable structured summary](../../data/qwen36-q8-tp2-asrock-b70-20260813/summary.json)
- [Compressed complete raw result](../../data/qwen36-q8-tp2-asrock-b70-20260813/conv-stateio-final-full512-realistic.json.gz.b64)
- Fixed suite:
  [`realistic-suite-v1.json`](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)

The reference host's bounded service is `qwen36-q8-b70.service`, listening only
on `127.0.0.1:18080`. After promotion it passed health, an exact 128-token
smoke hash, cache-zero verification, and a `35.425 tok/s` full-decode smoke.
The packaged benchmark then replayed the complete 12-prompt suite against that
unit to produce the promoted `35.494434 tok/s` result. Both GPUs remained
`normal`, and the post-stress kernel log had no Xe fault/reset/hang, AER error,
or OOM event.

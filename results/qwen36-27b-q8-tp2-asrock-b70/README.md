# Qwen3.6 27B Q8 target-only TP2 on two ASRock B70s

Current resume state: [HANDOFF.md](HANDOFF.md). The 2026-08-15 pass-2 stack
adds an exact single-subgroup Q/K RMS+scale+IMRoPE fusion to the prior
register-direct Q8, direct IMRoPE KV-cache, and vec4-reduction stack; the
measurement and recipe below are authoritative.

## Outcome

The target-only optimization campaign reached **36.230462 tok/s**
under conventional 99-inter-token-interval accounting on two ASRock Intel Arc
Pro B70 32 GiB cards. The historical repository helper reports `36.596426`
from the same timestamps. No draft model, MTP, DFlash, n-gram reuse, prompt
cache, response reuse, or speculative decoding was used.

This clears the requested 30 tok/s two-card target without relaxing Q8_0
quality. All 12 fixed-suite outputs, each 512 tokens long, are byte-for-byte
identical to the accepted pre-state-I/O target-only control.

## Promoted measurement

| Metric | Result |
| --- | ---: |
| Conventional 99-interval median | **36.230462 tok/s** |
| Conventional p10 / mean | `35.766025` / `36.198205 tok/s` |
| Historical 100-event compatibility median | `36.596426 tok/s` |
| Full 512-token after-TTFT median | `36.186203 tok/s` |
| Full 512-token wall median | `35.721114 tok/s` |
| Median TTFT | `181.144 ms` |
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
| Prior promoted full-recipe confirmation | `35.494434` | `+0.465%` run variance vs prior final |
| Recurrent RMS/gate/multiply/Q8 tail fusion | `35.699225` | `+0.219%` pooled matched micro A/B; headline delta also includes run variance |
| Register-direct Q8 handoff + IMRoPE direct cache write, clean rebuild | **`35.832213`** | IMRoPE `+0.155%` aggregate same-binary endpoint A/B; final headline includes run variance |
| Vectorized exact-F32 TP root reduction, clean rebuild | **`35.964046`** | `+0.327%` aggregate same-binary endpoint A/B; 12/12 prompt-paired first-100 rates positive |
| SIMD16 Q/K RMS+scale+IMRoPE with local FP32 boundary | **`36.230462`** | `+0.741%` over the preceding clean record; full-512 `+0.866%`; 12/12 exact |

The promoted result is **`+16.777%`** over the matched mndodd fork baseline.
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
`800f03b174e8e19a4471d3f15d3b544565c8aa1854563e01045cfedac7a6c9af`.

## What improved

The preserved full patch combines the earlier accepted lab stack with the two
strictly admitted state-I/O transformations, the recurrent-tail fusion, and
two pass-2 transformations:

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
3. The final recurrent gate path now joins the exact RMS normalization and
   scale multiply with its already-computed SiLU gate, final multiply, and
   reordered-Q8 handoff. It fires only when that gate projection is already
   present in the precomputed-MMVQ set, and preserves the stock FP32
   boundaries and operation order.
4. The TP2 collective tail maps each subgroup directly onto one Q8_1 block.
   After the ordered RMS reduction it writes the required graph-visible F32
   multiply output while retaining the same 32 values in registers for Q8
   packing, removing the accepted path's global reread.
5. The attention-K IMRoPE kernel writes its F32 result directly into the
   indexed F16 KV-cache destination for the exact
   `ROPE -> VIEW -> SET_ROWS` closure, eliminating 32 RoPE and 32 SET_ROWS
   launches per generated token.
6. The TP root reduction processes four aligned FP32 elements per work-item
   with `sycl::vec<float, 4>`, preserving the accepted per-element addition
   order while reducing the 5,120-element grid and memory transactions by
   four. Its same-binary endpoint control was `35.846855 tok/s`; the candidate
   was `35.964046 tok/s` (`+0.327%` aggregate, `+0.462%` prompt-paired mean),
   with all 12 prompts positive and byte-exact.
7. Each full-attention block now joins Q and K RMS+scale+IMRoPE and the K-cache
   write into one SIMD16 launch. The subgroup first materializes all 256
   post-RMS+MUL values in a 1 KiB local FP32 buffer, preserving the exact
   incumbent store/read arithmetic boundary, then assigns eight RoPE pairs to
   each lane. This removes three launches per block while retaining 12/12
   complete output hashes.

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

The final fresh-server, no-warmup cold suite passed:

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

The tail fusion has its own scoped red-control. With
`GGML_SYCL_GDN_RMS_TAIL_POISON=1`, 3 of 12 short-suite output hashes changed;
clean mode restored 12/12. Its census observed exactly 1,536 hits for a
16-token TP2 decode (`48 layers × 2 ranks × 16 tokens`).

## Bounded negative results

These doors were tested and rejected rather than left enabled:

- GDN workgroup packing at 2, 4, 8, and 16 subgroups was flat within about
  `0.08 tok/s`; the original 4-subgroup setting remains.
- Batched Q/K normalization plus in-kernel RoPE matched all 12 short-suite
  hashes but was effectively flat and was removed.
- A barrier-free SIMD16 form looked `+1.49%` in long synthetic decode and
  `+0.80%` in the endpoint, but changed 10/12 complete output hashes. A
  `volatile` register intermediate did not repair it. Only the local-FP32
  materialization above is accepted.
- Earlier VDR2/VDR8, scale-broadcast, alternate GDN quad/reuse, convolution to
  SiLU, Q8 cache, async tensor copy, root-barrier, forced PVC phase ordering,
  and root-local peer-replication experiments were rejected or reverted.
- A Q8 weight-cache hint looked positive in an unmatched warm-state screen,
  but the equally warmed 12×512 crossover was negative: `35.671361` versus
  `35.690578 tok/s` conventional. L3 bypass and streaming the scale plane also
  failed their bounded screens, so no cache-policy experiment remains active.
- A `0.98/1.02` tensor split fell to `33.263 tok/s` because symmetry-dependent
  recurrent fusions stopped firing on one rank. Equal `1/1` remains required;
  changing the main GPU was neutral.
- DFlash and MTP were excluded from this target-only objective even where they
  produced higher workload-dependent rates.

The rejected local logs remain under
`/mnt/fast-ai/bench-results/qwen36-q8-asrock-b70-20260813-tp2-fusion` on the
reference host so the dead ends are not rediscovered.

The pass-1 campaign broadened that audit across collective topology,
Level Zero/runtime knobs, Q8 scheduling, recurrent/GDN fusions,
FlashAttention, CPU submission, and power/clock hypotheses. It produced no
promoted gain. Pass 2 then promoted the two changes above after a clean rebuild
and full exact-output replay. Preserve their full chronology in
[`notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md`](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass1.md)
and [`notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md`](../../notes/2026-08-14-qwen36-q8-tp2-40tps-pass2.md),
and use the [handoff](HANDOFF.md) for the current decision summary.

## Reproduction and evidence

- [Reproduction recipe](../../repro/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [Full source patch](../../patches/qwen36-27b-q8-tp2-asrock-b70/README.md)
- [Readable structured summary](../../data/qwen36-q8-tp2-asrock-b70-20260814/summary.json)
- [Compressed complete raw result](../../data/qwen36-q8-tp2-asrock-b70-20260814/qknormrope-localfp32-full-realistic512.json.gz.b64)
- [Compressed same-binary scalar control](../../data/qwen36-q8-tp2-asrock-b70-20260814/reduce-vec4-clean-control-full-realistic512.json.gz.b64)
- Fixed suite:
  [`realistic-suite-v1.json`](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)

The reference host's bounded service unit is `qwen36-q8-b70.service`, listening
only on `127.0.0.1:18080` when activated; it was inactive during this research
pass. The clean publication run used the same bounded launcher on port 18082
and produced the pre-vec4 `35.832213 tok/s` result. The clean vec4 promotion
and same-binary scalar control used ports 18083 and 18084 and produced
`35.964046 tok/s`; the exact Q/K fusion then advanced the record to
`36.230462 tok/s`. The pass avoided the known
unsafe profiler, graph-capture, and remote-write paths.

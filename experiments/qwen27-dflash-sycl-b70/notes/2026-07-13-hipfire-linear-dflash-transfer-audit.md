# hipfire linear-DFlash transfer audit

Date: 2026-07-13

Status: read-only source and evidence audit; no llama.cpp or hipfire source was
changed

## Executive conclusion

hipfire's `75-130+ tok/s` Qwen3.6-27B linear-DFlash results are real within
their recorded identities, but they do not demonstrate a two- or three-times
cheaper target forward. Their implied speculative-cycle wall is tightly
clustered around `49-56 ms`, usually `53-54 ms` on the daemon. The current
one-B70 full187 plus GDN-cache lane has a weighted `60.715 ms` cycle. hipfire's
runtime is therefore about `10-12%` cheaper per daemon cycle, not 2-3x.

The large throughput difference is primarily accepted work per cycle. hipfire
records `tau=3.10-5.23` accepted draft tokens per daemon cycle for expository
prose through code/reasoning, hence `4.10-6.23` emitted tokens after adding the
target/bonus token. Our strict mixed suite records only `1.704` accepted and
`2.704` emitted tokens per cycle. hipfire's raw code continuation reaches
`tau=6.33`, or `7.33` emitted/cycle, but that prompt identity is explicitly
not the daemon serving identity and is not comparable to our fixed realistic
suite.

Consequently:

- porting hipfire-style execution mechanisms can plausibly move the current
  strict lane from roughly `44.5` aggregate tok/s into the low `50s` at
  unchanged acceptance;
- reaching `100 tok/s` on one B70 still requires materially better strict-suite
  draft agreement as well as a cheaper cycle;
- code/reasoning-specific `100+ tok/s` is plausible sooner because hipfire-like
  acceptance would already yield about `101-103 tok/s` at our present
  `60.715 ms` cycle;
- a raw-code `130 tok/s` result must not be presented as an all-workload or
  fixed-suite result.

## Attribution and source identities

hipfire is an original inference engine authored primarily by Kaden Schutt.
Its project notice requests attribution for idea-level ports as well as copied
code. DFlash and the first `attention_dflash` kernel originate with Kaden
Schutt; the current tiled online-softmax form of that kernel is primarily by
alpineq. Any implementation informed by these mechanisms should preserve the
applicable SPDX/NOTICE requirements and credit hipfire, Kaden Schutt, and the
per-file contributors identified by hipfire's `AGENTS.md` and `PRIOR-ART.md`.

Audited identities:

- hipfire: `d44f89e7f00f807962e0eb61a1790151a514cb83`;
- protected llama.cpp base HEAD:
  `e3546c7948e3af463d0b401e6421d5a4c2faf565`, with the existing protected
  dirty experiment tree left untouched;
- current promoted evidence:
  `data/qwen36-27b-mtp-gguf-q4-b70-baselines/xe2-m6-full187-joint-gdncache-aot-realistic128-20260713T130908Z.json`;
- current server identity log:
  `/mnt/fast-ai/bench-results/qwen36-27b-mtp-gguf-q4-b70/runs/xe2-m6-full187-joint-gdncache-aot-realistic128-20260713T130908Z/server.identity.log`.

## Cycle decomposition: acceptance versus execution

hipfire defines `tau = sum(accepted) / cycles` and advances the position by
`accepted + 1` each cycle. Therefore:

```text
emitted_per_cycle = tau + 1
implied_cycle_ms   = 1000 * (tau + 1) / tok_s
```

The definition is explicit in
`/home/steve/src/hipfire/docs/design/2026-06-13-archspec-and-dyn-boundary.md:265`.

### hipfire daemon identity

The main durability document identifies gfx1100 RX-7900-class hardware,
Qwen3.6-27B MQ4, q8 KV, greedy decoding, and three-run medians at
`docs/spec-decode-durability-2026-06-23.md:1-4`. Its daemon uses ChatML plus a
structured thinking block, which the document says materially changes draft
predictability (`:6-25`).

| Workload | tok/s | tau accepted/cycle | emitted/cycle | Implied cycle |
|---|---:|---:|---:|---:|
| code | 112.9 | 5.15 | 6.15 | 54.47 ms |
| reasoning | 114.8 | 5.23 | 6.23 | 54.27 ms |
| instruct | 96.9 | 4.23 | 5.23 | 53.97 ms |
| expository prose | 77.1 | 3.10 | 4.10 | 53.18 ms |
| fiction, lighthouse | 60.2 | 2.20 | 3.20 | 53.16 ms |
| fiction, clockmaker | 65.3 | 2.48 | 3.48 | 53.29 ms |

The near-constant cycle wall and widely varying throughput show that acceptance
drives almost the entire within-hipfire genre spread.

### hipfire raw/no-ChatML identity

The separate raw-continuation matrix at
`docs/spec-decode-durability-2026-06-23.md:60-72` produces the same result:

| Workload | tok/s | tau accepted/cycle | emitted/cycle | Implied cycle |
|---|---:|---:|---:|---:|
| code | 130.0 | 6.33 | 7.33 | 56.38 ms |
| reasoning | 109.9 | 4.79 | 5.79 | 52.68 ms |
| instruct | 74.5 | 2.82 | 3.82 | 51.28 ms |
| prose | 45.9 | 1.26 | 2.26 | 49.24 ms |

Raw code is the slowest cycle in this table yet the fastest throughput because
it accepts the most tokens. Raw prose has the cheapest cycle and still loses
because acceptance collapses. This directly rejects an explanation based on
framework overhead alone.

### Current B70 strict identity

The promoted GDN-cache log records `968` accepted tokens from `2715` proposals
over `1536` output tokens. Therefore it used about `568` cycles and emitted
`1536/568 = 2.704` tokens/cycle. The twelve llama.cpp `eval time` entries sum
to `34,486.220 ms`, giving a weighted `60.715 ms/cycle` and aggregate
`44.54 tok/s`; the policy headline remains the suite median
`44.2553881757 tok/s`.

Holding our acceptance fixed and substituting a representative hipfire daemon
cycle of `53.3 ms` yields only about `50.7 tok/s`. Holding our cycle fixed and
substituting hipfire daemon code/reason acceptance yields `101.3-102.6 tok/s`.
The latter is a workload-specific ceiling calculation, not a valid strict-suite
claim.

At `60.715 ms`, even perfect DFlash5 acceptance has a hard ceiling of six
emitted tokens per cycle, or `98.82 tok/s`. Fusion must take the cycle below
`60 ms` even in that unattainable perfect-acceptance case. At the actually
measured `2.704` emitted/cycle, `100 tok/s` requires a `27.04 ms` cycle. The
strict objective therefore needs both a much better draft/acceptance policy and
a materially cheaper verifier.

## Top three transferable execution mechanisms

These are architectural ideas to port to Xe2/DPAS, not instructions to copy
AMD kernel code literally.

hipfire is not a monolithic persistent GPU decoder. It still has a host-side
Qwen layer loop and many individual launches. Its transferable advantage is a
single batched verifier plus persistent cycle state and selected high-value
fusion boundaries. This distinction matters: porting its architecture does not
mean fusing the entire model into one giant kernel.

### 1. One batched multirow target verifier with targeted fusion

hipfire's target verifier is a purpose-built batched forward with caller-owned
persistent scratch, rather than a generic graph whose individual operators
happen to receive six rows:

- `crates/hipfire-arch-qwen35/src/qwen35.rs:6080-6127` exposes the persistent
  `PrefillBatchScratch` interface and explicitly sizes it so a DFlash block fits
  in one chunk;
- `qwen35.rs:8371-8448` combines batched norm/activation rotation with the
  four-way GDN `qkvza` projection;
- `qwen35.rs:8865-8983` routes output projections through residual GEMM
  epilogues;
- `qwen35.rs:9020-9152` fuses/shared-dispatches gate plus up;
- `qwen35.rs:9154-9188` runs batched SwiGLU and, for MQ weights, fuses the
  required activation rotation;
- `qwen35.rs:9190-9293` uses down-projection kernels with residual epilogues;
- representative kernel sources include
  `kernels/src/fused_qkvza_hfq4g256.hip`,
  `kernels/src/fused_gate_up_hfq4g256.hip`,
  `kernels/src/fused_silu_mul_mq_rotate.hip`, and the residual-GEMM family.

The current llama.cpp path is only partway there. The guarded Xe2 M=6 path
accelerates the 130 gate/up plus 57 down Q4_0 tensors, and joint gate/up shares
quantization, but it does not own the complete verifier. Its matcher is
hard-coded to M=6 and rejects graph mode at
`ggml/src/ggml-sycl/ggml-sycl.cpp:4788-4811` and `:4849-4860`. Norms, GDN
projection groups, attention projection groups, activations, residual
boundaries, and verifier outputs still cross the generic ggml execution loop.

The transferable implementation is a width-specialized Xe2 verifier pipeline:
offline-pack every eligible Q4_0 projection once; share one canonical Q8_1
producer across each projection group; add fused QKV/GDN-QKVZA, output-residual,
gate/up, SwiGLU-to-down-input, and down-residual boundaries; keep M=6/M=9/M=16
as separate AOT DPAS specializations. This is the mechanism most likely to
close the measured per-cycle gap.

This does not imply that every fusion is profitable. hipfire's own older
DFlash subphase trace attributes `~56 ms`, or `87%`, to its draft FFN at
`crates/hipfire-runtime/src/dflash.rs:1249-1260`, while `:1523-1529` records
that a fused gate/up experiment was neutral. That agrees with our small
elementwise-fusion results: the primary target is multirow weight execution and
memory-boundary removal, with every fusion retained only after an end-to-end
gate.

### 2. A GPU-resident speculative handoff and state commit

hipfire keeps the committed hidden rows and recurrent repair on device:

- `crates/hipfire-runtime/src/dflash.rs:473-566` owns persistent DFlash
  scratch, incrementally appends target-hidden rows, and caches each draft
  layer's context K/V projections. Its source records a historical reduction
  from about `90 MB` to `700 KB` H2D and from about `230 ms` full-context work
  to `5 ms` delta work at typical high acceptance;
- `dflash.rs:1204-1243` projects only newly committed target-hidden rows and
  `:1317-1367` updates only their per-layer K/V cache tails;
- `crates/hipfire-arch-qwen35/src/speculative.rs:3112-3214` writes noise
  embeddings directly on GPU and passes already-populated device target-hidden
  storage into the draft without a host round trip;
- `crates/hipfire-arch-qwen35/src/speculative.rs:2654-2698` runs the batched
  verify LM head and greedy argmax on GPU, downloading only `4*B` bytes rather
  than full `B*vocab` logits;
- `speculative.rs:3929-3963` scatters accepted hidden rows directly from the
  target ring into draft scratch, avoiding D2H, CPU reshape, and next-cycle
  H2D;
- `speculative.rs:3549-3571` records per-GDN-layer `(q,k,v,alpha,beta)`
  innovations during verification;
- `speculative.rs:3971-4001` restores pre-verify recurrent state and replays
  only the committed GDN recurrence from that tape, rather than rerunning the
  full target.

Our current GDN cache fusion is valuable but narrower. It fuses the
GATED_DELTA_NET snapshot scatter into the persistent recurrent cache at
`ggml/src/ggml-sycl/ggml-sycl.cpp:6591-6655` and invokes it from
`:7165-7185`; it is not a DFlash innovation-tape replay system.

The current llama.cpp DFlash feature bridge is visibly host-resident:
`common/speculative.cpp:1149-1161` gathers extracted target layers into a CPU
`features_buf`, `:1164-1175` passes that host embedding through the draft
encoder, and `:1183-1198` copies the encoder result into another host batch for
KV injection. The new guarded draft LM-head top-1 boundary at
`common/speculative.cpp:1021-1077` and `:1258-1280` already transfers one part
of hipfire's GPU-argmax idea, so it should be retained rather than reimplemented.

The next port should allocate persistent device feature/hidden rings, gather
the selected target-layer rows into the draft encoder input on device, feed the
encoder output directly into draft KV injection, and add a GDN innovation tape
only if cycle timing proves target rollback/replay still material. This removes
copies and host coordination, but its likely gain is a few milliseconds, not
the missing 2.3x by itself.

The historical `230 -> 5 ms` hipfire context-cache claim is not an available
`225 ms` win in our current lane: llama.cpp's native DFlash injection already
advances accepted rows incrementally, and our measured feature/injection phase
is around `1 ms`, not hundreds. The relevant transfer is device residency and
compact state repair, not rediscovering incremental KV semantics already
present in the current architecture.

### 3. Width-keyed replay over fixed pointers and persistent scratch

hipfire makes graph identity deliberately static:

- `crates/hipfire-arch-qwen35/src/speculative.rs:2380-2405` uses persistent
  scratch and records width, kernel choices, and stable pointers in the graph;
- `speculative.rs:2407-2410` records an older `+14%` smoke result and about
  `1.3 ms` launch-overhead saving;
- `speculative.rs:2475-2496` uploads new bytes into fixed buffers and directly
  launches the cached graph keyed by block width;
- `speculative.rs:2497-2527` warms each width so JIT and lazy allocations stay
  outside capture;
- `speculative.rs:2528-2598` captures once and immediately launches the new
  executable.

Our persistent executable graph cache already proved exact direct replay, but
was throughput-neutral on the generic path. More importantly, the winning Xe2
M=6 matchers explicitly reject graphs, so the measured graph result never
tested a cached fused verifier. The transferable step is not another generic
graph flag sweep. It is fixed-address per-width scratch plus a closed Level
Zero command list or SYCL executable that contains the *custom fused* M=6/M=9
verifier and device-resident handoff. Warm and capture each width after all
packs and scratch exist. Graph work should follow the full-fused pipeline,
because hipfire's own evidence says launch saving is about `1.3 ms`, not the
whole performance gap.

## Claims that are prompt-specific or not comparable

1. **`130 tok/s` is raw/no-ChatML code continuation.** hipfire itself labels
   this as the canonical code-bench identity, not the all-genre daemon serving
   identity (`docs/spec-decode-durability-2026-06-23.md:168-177`).
2. **`112.9-114.8 tok/s` daemon code/reasoning includes ChatML and a structured
   thinking block.** The document says this prompt wrapper raises acceptance,
   including fiction (`:6-25`, `:53-56`). It cannot be compared to a different
   byte sequence as a kernel result.
3. **The older `185.5 tok/s` Qwen3.6 HumanEval/53 row is even narrower.** It is
   a five-run, `--no-chatml`, `max_tokens=120`, asym3-KV benchmark
   (`docs/BENCHMARKS.md:29-58`), not the q8-KV daemon durability identity and
   not our fixed twelve-prompt cold suite.
4. **Prompt bytes are load-bearing.** hipfire's testing rules say one newline
   can move tau by `17%` and require byte-identical prompts
   (`AGENTS.md:177-180`; `docs/BENCHMARKS.md:122-125`).
5. **Quantization and hardware differ.** hipfire uses MQ4 with online FWHT
   activation rotation on gfx1100; our target is GGUF Q4_0 with canonical
   Q8_1 activation semantics on Intel BMG. Kernel shapes and effective
   bandwidth are not directly portable.
6. **DDTree is not the fast answer in hipfire's own matrix.** It loses to
   linear DFlash in every reported cell because added tree-verifier cost
   exceeds the acceptance benefit (`docs/spec-decode-durability-2026-06-23.md:62-70`).
7. **Tree graph capture is not a production template.** The current source
   labels it diagnostic-only with acceptance regressions at
   `speculative.rs:2417-2439`. Only the stable linear width-keyed graph should
   inform our first implementation.
8. **GPU softmax is a sampled-serving result.** The `59.3 -> 42.7 ms` claim at
   `docs/spec-decode-durability-2026-06-23.md:89-108` addresses temperature-
   sampled rejection sampling. It is not the central lever for our current
   greedy/top-1 lane.

## Resulting priority

1. Complete the custom M=6 target pipeline across GDN/attention projections,
   norms, activations, and residual epilogues, preserving the exact Q4_0/Q8_1
   numerical contract.
2. Make the target-hidden-to-DFlash feature/encoder/KV path device-resident;
   retain the new exact draft top-1 boundary and measure whether a GDN
   innovation tape is still worth implementing after the feature bridge moves.
3. Move all fused-width scratch to fixed context-owned allocations, then cache
   and replay one closed executable per verifier width. Do not rerun generic
   graph sweeps.
4. In parallel with execution work, treat acceptance as an independent product
   requirement. Measure exact hipfire prompts and our fixed prompts through
   both engines if model/tokenizer identities can be matched; evaluate a
   better/adapted draft or lossless MTP/DFlash routing for strict prose. Prompt
   wrappers may be a product policy experiment, but must not be counted as a
   kernel improvement or substituted into the fixed-suite record.

This audit does not establish that hipfire's exact kernels will reproduce its
cycle time on B70. It establishes the narrower and more useful fact: hipfire's
execution architecture offers a believable `~7 ms` daemon-cycle target, while
its `75-130+ tok/s` spread is mostly a draft-acceptance result. Both dimensions
must be attacked separately.

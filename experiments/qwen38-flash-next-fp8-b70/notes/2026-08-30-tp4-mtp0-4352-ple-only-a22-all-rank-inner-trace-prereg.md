# Qwen3.8 Flash-Next FP8 A22 all-rank PLE inner-trace preregistration

Date: 2026-08-30
Status: frozen before fresh-boot GPU launch

A22 is the first member of the internal-trace pair. It retains A21's validated
external checkpoint, TP4/EP4 eager MTP0 placement, 4352 capacity, PLE-only UVA
selector, 64-token batch cap, cache size, seed, quality helper, request order,
authorities, and supervisor policy. It moves to attempt 22/port 19694 and binds
vLLM source `613afcc501331aa6ff7d5a238a6c9a5d45777b3e`.

Source changes are diagnostic or fail-closed only:

- report PLE input/output and post-add, attention, and MLP boundaries;
- report raw FP8 embedding, dequantized embedding, projections/gate,
  convolution input, and convolution output;
- capture a separate trace file on every TP rank;
- require all 128 PLE checkpoint shard indices before boot;
- add CPU/fixed-input tests without changing inference arithmetic.

The disabled trace path preserves the original PLE expression textually. Eight
trace tests, 15 PLE tests, and the 4K n-gram progression tests pass. Trace
copies synchronize tensors and therefore all A22 timing is diagnostic; no
speed receives credit and no protected result can be lowered.

Frozen interpretation:

- cross-rank disagreement before layer 1 implicates upstream rank state;
- matching PLE inputs but differing raw FP8 embeddings implicates actual
  checkpoint-table/UVA lookup ownership;
- matching raw embeddings but differing dequantized/projection/gate values
  identifies the first corresponding arithmetic boundary;
- matching convolution input but differing convolution output implicates the
  live stateful convolution path;
- matching PLE output moves the first difference to layer-1 attention or MLP;
- an internally identical A22 across ranks is not a cross-start seal. Unless
  it is independently decisive, A23 must repeat the same trace after another
  fresh boot before any treatment.

Full-load safety is frozen to the validated external artifact and at most one
full model load per fresh boot. A22 must not launch in the current post-A21
boot. A21's external load occupied essentially all 8 GiB of swap and caused an
observed interactive stall before recovering and passing. A22 retains the
exact runtime identity rather than changing scheduling or memory policy inside
this trace pair. Its launch must therefore be announced as a possible 10–15
minute SSH/UI stall, monitored through the bounded supervisor and sysstat, and
not mistaken for failure unless the supervisor or post-boot journal provides a
terminal event. The launcher explicitly rejects A21's boot ID and atomically
marks the first A22 full-load attempt in `/run/user/1000`; another Qwen3.8
Flash-Next A22 invocation in that boot fails closed. The broader one-full-load
rule remains an operational policy for other launchers.

Frozen wrappers and generated sources:

- launcher `18889ab0e8a8602bd02a22f775a903eafcc9ac4d2bd01db2ac0f102a9edc3c60`,
  generated `b32a64b4444639b113c625e38597c5390c200844ac304fdb2a4f7ebb84541646`,
  inner derived `3119e7a55d95050ae3188582d6510cba7c70673876cf3981f8cfa76302dbaafa`;
- client `65c5dd11b4beb5d2d5796700cb071d25edcffe28dbe00c3b719ac3cb4602da84`,
  generated `ceabc9ad4c0aedf1e22b71e1fd72566e22a344926c1ecfe490dda4d0ccfc7acf`,
  inner derived `ae0f47a0e4972880d2b93ff91c25c5233360d7343482bcb53d61b964b9d520b1`;
- supervisor `3fc2400b9fd3d7c872175165b22e4ca2871a0639ce31899663cda4e49b5dd13d`,
  generated `b51a3b05b9927460585040f66b03150387fa99c444e0854ddf77cd58f1c3473e`,
  inner derived `8494ab627ffa8b8e07f73120388ce779cafb89da0f65d487b220318d585df031`.

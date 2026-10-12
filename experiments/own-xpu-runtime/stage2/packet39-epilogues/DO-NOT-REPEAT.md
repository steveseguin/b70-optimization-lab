# Packet 39 negative and deferred arms

Preparation closeout: [CLOSEOUT.md](CLOSEOUT.md). Coordinator device history and CPU repair: [stride failure](evidence/20261012-g4-row-stride-check/README.md).

| Arm | Evidence and reason | Reopen condition |
| --- | --- | --- |
| Full paired expert activation IQ2_S/IQ3_S | [Assembly](assembly-review.json): extra predicate spills even after moving the route vote out of the GEMV loop | Emitted code removes added spills without weakening route/sticky or BF16 behavior |
| IQ3_S checks-only | [Independent review](review-assembly.md): one added `sync.nop` in GEMV loop; only one layer/token | Remove it without a larger cost; do not open a long campaign for two launches/token |
| GDN QKV/convolution Q6_K/Q8_0 | Pure scalar arithmetic is valid, but both add one scheduling instruction inside the GEMV loop | Preserve the original loop with a new codegen form |
| Global route predicate kept live through expert down | [Iteration 1](evidence/iteration1/README.md): added predicate spills; superseded by row-zero own-slot status CAS | No reason to repeat; use final down-status form |
| HC/shared control treated as WG32 plus finish | [Iteration 3](evidence/iteration3/README.md): measured control actually uses rows4 and inline finish | Never compare against that mismatched control; final geometry is in baseline-geometry.json |
| HC gate/mix, expert down/mixture, GDN z/gated, norm epilogues | [Chain table](CHAINS.md): multiple rows or whole-vector/head reductions; serial fusion is outside this packet | A separate parallel design with a real launch advantage and unchanged arithmetic |
| Split GDN gated reduction then delay z | Adds a reduction launch before removing elementwise launch; zero net launch benefit | A different existing reduction consumer makes the scalar already available |
| PLE convolution/add | Valid non-GEMV tail, one launch/token only | Include opportunistically in a broader useful non-GEMV change |
| Treat NaNs as equal | [CPU receipts](cpu-gates.json): GCC records 36 exact-byte mismatches | Exact payload preservation demonstrated under a separately registered nonfinite contract |
| Independent small K0 binary | Could compile different device images than G4 | Final K0 is a byte-identical copy of G4 with `--compile-smoke`; keep that guarantee |
| Handwritten shortened unfused tails | Can understate actual runtime tiny-launch cost | Retain original source-extracted ng/status/simple bodies and geometry |
| Expanded Q6/Q8 stride without metadata | Original G4 stopped at HC: 12160 bound versus 11520 expected. The old CPU fixture duplicated the same wrong formula. | Use `expanded::row_bytes`, including metadata; require shared G4 binding gate with all twelve exact cases before sealing. |
| Abort whole G4 on validation/byte mismatch | Seven cases lost their window when the sixth rejected its binding. | Record failed case, skip timing/dispatch, continue; reserve nonzero exit for infrastructure failures. CPU injection must prove continuation and infrastructure stop. |
| Bare partial timing numbers | Per-group timings without rotation and format frequency can misstate benefit. | Preserve raw arrays; label event-sum units, complete bank rotation and `(control-fused)*groups/token`; never sum mutually exclusive expert candidates. |

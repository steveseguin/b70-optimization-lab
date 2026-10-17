# Packet56: smaller draft head, unchanged target

CPU-only preparation on steve-b70s. The protected packet49d chain and its
files are untouched. All compilation and tests use nice 19 on cores 4–15,20–31,
one compiler at a time. No GPU, service, sudo, model-weight load, host setting
change or oracle job is run by this preparation.

The [packet](../experiments/own-xpu-runtime/stage2/packet56-draft-prefix/README.md)
retains packet49d's target and limits only the draft's shared-head GEMV and
argmax to rows [0,91392). It uses the same row stride, kernel and reduction;
no extra head copy is made. Every emitted token still comes from the full
target verifier. CPU pipeline tests compare excluded-token misses, mixed
hits/misses and EOS against the sequential controller.

## Independent selection

Commit `dcef19128` preregistered five complete local operations/design/code
files and the smallest 256-row-aligned prefix covering 99.5% of their tokens.
Commit `dfcbc301c` fixed the result before benchmark-output inspection.
N=91,392 of 248,320 covers 19,382/19,477 tokens (99.512245%); 91,136 fails at
99.491708%. There are 95 tokens (0.487755%) outside. No benchmark prompt/output or
packet55 generated data is used. Only admitted GGUF tokenizer headers are
read; model-weight payload bytes read are zero.

Text-token frequency is an offline proxy for target-token exclusion, not an
observed target-generation or draft-acceptance measurement. The prefix is
sealed and will not be retuned using the benchmark.

## Draft budget and expected value

[Analysis and receipt hashes](../experiments/own-xpu-runtime/stage2/packet56-draft-prefix/analysis/README.md):
Packet49c D wall median is 2.775889 ms; enclosing command median is 2.816540 ms.
Matched K2 head GEMV at 1.418021 ms (rotated) plus argmax at 0.020624 ms is a
1.438645 ms proxy, 51.83% of D. The remaining 1.337244 ms includes the draft
layer, final operations and overhead; it is not an isolated layer measurement.
Retained KD timing/site files are empty, so a more precise split is unavailable.

The 839.3216 MB allocation has 3,380 bytes/row; the fast head actually reads
3,200 bytes/row, 794.624 MB total. Linear row scaling projects 0.896131 ms saved,
D≈1.879758 ms. With `hit=D+max(S,B)` and
`miss=max(D,R+A)+max(S,B)`, hit becomes 18.267367 ms; miss stays 33.201684 ms.
The conditional weighted rate is 46.606–46.765 tok/s versus its own weighted
baseline of 45.263767 (2.97–3.32%). It is not the measured class-balanced record
of 45.695513 tok/s or a forecast of that exact statistic. Generated-token
distribution, draft state history and actual head scaling remain device questions.

## Validation and handoff

CPU gate and build receipts live in the packet. The full target still needs
the coordinator's unchanged packet49 oracle chain. The head K windows must
include 32K, 64K, 96K, full and the sealed 91,392-row choice, with fresh owners,
byte checks and event timings. They cannot change N.

[Exact coordinator commands](../experiments/own-xpu-runtime/stage2/packet56-draft-prefix/WINDOW.md)
and [submission commands](../experiments/own-xpu-runtime/stage2/packet56-draft-prefix/SUBMISSION.md)
are prepared separately. Submission uses the pinned current floor file,
currently 45.695513 tok/s or a higher submitted 49d result if recorded. No
external submission is performed here.

The final GNU host and device compilation receipts bind 27 binaries. No device
binary ran. Two fresh CPU numerical runs passed (0.908/0.905 seconds): each
compared all 182,784 prefix-logit bytes, 16 smaller logit cases, 30 argmax cases
and 12 controller cases. All 24 focused wrapper/submission tests passed.
The final source/build check binds 489 files. Independent runtime and
submission reviews have no unresolved blocking findings. Removing only this
packet's regenerable object files leaves a 334.6 MB build; storage admission
passes with about 2.54 GB above its declared reserves.

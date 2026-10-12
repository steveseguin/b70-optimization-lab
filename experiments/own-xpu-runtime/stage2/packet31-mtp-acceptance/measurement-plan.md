# CPU measurement plan

Registered before any generated-token draft results were read. Four prompts in
this order: incident-retrospective, code-review, customer-email,
benchmark-analysis. Exactly 64 generated tokens each. No prompt selection by
acceptance. The target is iq3-p17-detmath-v2 and remains autoregressive; draft
predictions never enter its state or select its next token.

Capture final materialized layer-47 streams and full-vocabulary greedy
prediction at every prompt/generated input position. Consume all shifted MTP
rows in order: target H[j], embedding x[j+1], draft RoPE/cache j. Score the 64
rows j=N-2 through N+61 against target predictions at j+1. Capture one final
extra target prediction to provide an x[p+2] control for every scored row.

Primary source: official FP8 MTP parameters with IQ3 target embedding/head.
Also run independent complete caches for group16 symmetric int8 expert weights
with BF16 activations/dense parts, and official embedding/head bindings.
FP8 activation quantization uses the documented vLLM fallback formula; XPU
compiled-kernel arithmetic parity remains unqualified. CPU FP32 dots and
transcendentals are explicit numerical choices, not an assertion of device bits.

Shortlist: a fixed first pass uses 64 evenly spaced columns (0,40,...,2520)
from the IQ3 head and draft sample vector to rank all vocabulary rows. Stable
score-descending/token-ID ties. Select 4096/16384/65536 rows, then choose the
maximum exact IQ3-reference head logit within each list. It never consults the
target token, target logits, or future text. This measures acceptance only;
full logits are reused for offline scoring, so no shortlist speed is measured.

Token-only controls use only context through x[p]. Use the most recent observed
successor of x[p], or the most recent successor of (x[p-1],x[p]) with unigram
fallback. Missing unigram successors fall back to repeating x[p]. Also report
a repeat-current baseline. Top-2/top-4 membership is diagnostic and is excluded
from a one-guess pipeline timing model.

Report per prompt and pooled counts, Wilson 95% intervals, longest miss run
(reset between prompts), and ten decile hit/miss counts. The intervals are
binomial descriptions; adjacent model tokens are correlated. The timing model
uses the owner-supplied equation without altering it and is never measured
throughput. Four development prompts are not a representative benchmark suite.

All commands use nice 19 / idle I/O. Target has five compute threads; draft has
one. Only host-compiled code and CPU torch are executed. No device discovery,
settings, service, model source, other packet or shared status file is changed.

# D58 preregistration: M=128 short-prefill projection repair

Date: 2026-08-31

D56 proved the M=512 repair exact without device barriers in four fresh
processes. D57 passed all strict gates, matched all D54 token sequences, and
reduced full-suite median TTFT from 380.687002 to 310.378243 ms.

D58 changes only the padded dispatch size for `33 <= M <= 128`: M=128 instead
of M=512. Widths 129–511 retain M=512; decode and other widths remain outside
the repair. Prior operator scans identified M=128 as a stable oneDNN dispatch,
but the real model path—not that scan—is decisive.

Four fresh TP1 processes must produce byte-identical complete 64-layer traces
and responses for the real M=71 prefill. The response token IDs must also equal
the validated D53/D56 reference. Any split or response change rejects M=128.
This trace run is not performance evidence; a pass only authorizes a strict
non-instrumented replay and TTFT comparison.

# Qwen3.8 M=128 short-prefill D58 result

D58 was rejected after its first completed fresh process.

- The request was fresh (`cached_tokens=0`) and produced a complete trace.
- Its response token-ID hash was `28fc46f8...202d`, not the validated M=512
  reference `46e2ff76...f5d2d` required by the preregistration.
- Because one response change is sufficient to reject M=128, the remaining
  samples were stopped rather than spending GPU time proving repeatability of
  an already-disqualified numerical path.

This is not performance evidence. M=512 with barriers disabled remains the
preferred qualified TP1/MTP0 repair. The M=128 option stays explicit and
non-default only to reproduce this negative result; it must not appear in a
user recipe.

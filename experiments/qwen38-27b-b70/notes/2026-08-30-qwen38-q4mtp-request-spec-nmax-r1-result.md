# Qwen3.8-27B request-level MTP safety result

The candidate works as a fail-closed safety control, but it is not the best
performance recipe and is therefore **not promoted**.

On a fresh one-slot TP2 server, target-only MTP0 measured 49.7533 tok/s and
default MTP2 measured 64.3201 tok/s (+29.28%). Both passed the full twelve-prompt
natural-EOS suite, every cache count was zero, all standard canaries passed, and
all twelve complete MTP2 token arrays exactly matched the fresh MTP0 oracle.

Two fresh 64-slot servers then used explicit request-level MTP0 at users
4/8/16/32/64. Both arms passed output isolation, kept the draft counter exactly
at zero throughout the MTP0 phase, and passed 256/256 simultaneous semantic
canaries. The pointwise median at users=64 was 154.13 tok/s. That is 6.41% below
the already qualified separate target-only server (164.69 tok/s), so retaining
the loaded draft merely to switch request policy is not a throughput win.

The hybrid arms produced a replicated ~49.24 tok/s users=2 result when MTP2 was
measured after the full MTP0 sweep and semantic canaries. A separately
preregistered AB/BA diagnostic ruled out the request field: fresh explicit and
default users=2 results were 66.40–69.13 tok/s and differed by less than the
fixed 5% threshold. One 64-user MTP0 batch also did not reproduce the slowdown;
the same server improved from 67.42 before to 69.52 tok/s after. The low result
is therefore an unresolved long-sequence state effect, not a license to select
the faster nearby value.

Operational decision: retain the patch as a documented candidate safety tool,
but keep separate profiles as the recommendation—MTP2 for interactive work and
target-only MTP0 for throughput. Do not put the hybrid curve on the main model
board, do not submit it externally, and do not reuse the failed global-MTP2
high-concurrency number.

Raw evidence is stored under
`../data/qwen38-q4mtp-request-spec-nmax-20260830-r1/`; its manifest binds 65
compressed artifacts to their uncompressed and compressed SHA-256 identities.

# Preparation closeout: fixed scratch pool is too small

The initial 4096-capacity incident replay was stopped cooperatively during prefill
when a read-only source audit identified a deterministic future LONG-B failure:
Core allocates all temporaries from a fixed 256 MiB monotonic pool. At 1225 admitted
positions, attention alone exceeds that bound; this is not a device or GPU fault.
The retained result is incomplete and is not an oracle or capacity-equality pass.

The final host-only build overlay changes exactly two constants: Engine scratch
allocation 256 -> 512 MiB and evaluate() pool bound 64 -> 128 million binary float
slots. It changes no arithmetic operator or sequence. The patch and generated-source
hashes are bound in the final build receipt. A fresh incident equality replay and
checkpoint equality test gate the long runs. This preparation attempt's receipt,
partial position timings, original binary/build identity and logs remain here.
No automatic retry occurred; the rerun is a new build qualification.

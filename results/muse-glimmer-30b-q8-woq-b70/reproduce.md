# Reproduce the Muse Q8/WOQ result

Use the [standalone recipe](../../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md).
It contains the full source patch/bundle, model and toolchain manifests, exact
environment and server arguments, frozen prompt suite, two fresh-server
canonical runner, cold realistic runner, bootstrap calculator, raw evidence,
and offline verifier.

The exact measured identity is four B70s, TP4, concurrency one, context 32768,
batch/ubatch 1024, FA on, tensor split, DFlash nmax15/pmin0, BF16 draft,
UD-Q8_K_XL target, fixed16 WOQ, ARGMAX/local reuse, graph runtime off,
persistent parallel submission off, and ordinary BF16 graph conversion cache
off. Do not selectively copy only the WOQ flag.

For exact replay of the retained canonical artifact, preserve
`LLAMA_SPEC_PROFILE=0` **as an environment entry**; it enabled profiling due
to presence semantics. For the realistic/production-shaped run, the variable
must be absent.

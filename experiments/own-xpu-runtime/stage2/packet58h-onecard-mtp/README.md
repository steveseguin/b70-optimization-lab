# Packet58h: one-card MTP feasibility

**Do not build this arm.** With the existing host allowances, neither draft
placement fits the recorded available RAM. The primary timing model predicts
**24.62 tok/s**, below the requested **28.8 tok/s**. These are CPU calculations,
not a new speed measurement or a claim that one-card MTP is impossible.

This directory contains only the feasibility analysis and retained inputs.
No runtime was copied, compiled, sealed or queued. Frozen packet58g, all other
packets, shared screen tooling and ops were untouched.

- [Exact memory accounting and timing assumptions](FEASIBILITY.md)
- [Recomputed numbers](feasibility.json), [source identities](inputs.json)
- [Closeout](CLOSEOUT.md), [do-not-repeat entry](DO-NOT-REPEAT.md)
- [Task note](../../../../notes/2026-10-18-own-runtime-packet58h.md)

Reproduce from the retained compressed inputs, without model files or GPUs:

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet58h-onecard-mtp/feasibility.py --check </dev/null
```

Add `--verify-sources` on the originating checkout to verify the original input
files and frozen implementation hashes too. Each archive preserves its source's
decoded bytes exactly; `inputs.json` records both original-file and decoded
hashes, including the originally compressed packet84 census. Identical 58g
censuses share one archive. No original evidence was removed. Archives are
small evidence retention, not model data, generated caches or build objects.

The analyzer enforces helper cores, nice 19, an 8 GiB address-space limit and a
12 GiB root-disk floor. Its observed peak RSS is about 35 MB. No fixture scratch
or compilation was needed, so packet97's compile turn was unaffected.

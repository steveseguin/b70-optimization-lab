# Laguna long full-attention paired-row screen

Date: 2026-08-03 America/Toronto

Status: **32K-specific component gate prepared and CPU-tested; no native
component, XPU, model, endpoint, or performance work was performed**.

## Why this screen exists

The earlier paired-row M12 attention mechanism was raw-BF16 exact in 208/208
comparisons, but its short production-window component regressed from
`1.062087889` to `1.075515588 ms` when projected across 12 full plus 36
sliding layers. That rejects it for short decode. It does not answer whether
K/V reuse crosses over in the much larger full-attention layers at 8K--32K.

The component gate now has two explicit profiles:

- `short-record`, the unchanged 52 contexts from 89 through 962 tokens, both
  full and sliding attention, projected across 12 full plus 36 sliding layers,
  with the original `1.5 ms` threshold; and
- `long-full`, exact contexts `8192`, `16384`, `24576`, and `32640`, full
  attention only, projected across the model's 12 full-attention layers, with
  a `0.25 ms` minimum saving.

At the current `39.754 tok/s` 32K reference, `0.25 ms/token` would correspond
to about `40.153 tok/s` if the whole component saving transferred to the
endpoint. That is only a sizing threshold, not a prediction or measured rate.

The long profile deliberately excludes the 36 sliding layers: their effective
window does not grow with the 32K prompt, and their short-context candidate was
already slower. The largest staircase reaches only 32,652 tokens, below the
32,768-token service limit.

## Gate contract

`tools/gate_laguna_paired_attn.py --profile long-full` retains the original
fail-closed native selector, reversible Q/O packing, exact per-row sequence
staircase, raw BF16 comparison, alternating timing order, and mapped-library
hash evidence. A pass requires:

1. exact output after unpacking for every long context, seed, and tested rank;
2. no selector or native-policy fallback;
3. the paired full-attention core to save at least `0.25 ms` across 12 layers;
4. the expected candidate DSO to be the mapped library; and
5. clean component teardown under a separately authorized run.

Five new CPU-only tests pass. They lock the old short profile, the four long
contexts, full-only projection, the conservative threshold, the paired
staircase, 32K service bound, metadata shape, and host-only CLI behavior. Ruff
formatting/lint and whitespace checks pass.

## Upstream staging result

A fresh community worktree was created at:

```text
/home/steve/src/community-vllm-laguna-e2e-latency-20260803
community/laguna-e2e-latency-20260803
3ab3e1927 xpu: add direct GPTQ INT4 tile-record packer
```

It is based on fork/upstream `68ca6fd02`, so the staging lineage is current.
A trial cherry-pick of the measured exact-prefill commit conflicted in all six
touched files and was aborted cleanly. This is a semantic dependency, not just
text drift: current upstream Laguna uses the generic `FusedMoEFactory` path and
does not contain the historical exact-M1/M8/M12 router, rank-ordered reduction,
or authenticated graph stack that the measured treatment calls. Publishing a
partial cherry-pick would falsely imply that the measured arithmetic exists.
The current-upstream branch therefore remains a clean staging point with no
new optimization commit or public push.

## Ordering and boundaries

The accepted-position diagnostic remains the highest-upside 32K decision gate
because long acceptance is about 0.56% and a long-only seven-row drafter could
remove substantially more work. That hypothesis is still unmeasured. The
paired-row long-full component is now ready as the independent secondary lane
if a fresh diagnostic/component window is separately authorized.

The NVMe/device quarantine remains controlling. This note and host tests grant
no authorization to load a model, contact an endpoint, run an XPU component or
probe, alter swap, reset, reboot, or perform recovery. The protected short
decode record remains `125.4619731637751 tok/s`.

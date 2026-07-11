# Contributing

This is primarily a working Intel XPU optimization lab. Contributions are
welcome when they make a result faster, safer, clearer, easier to reproduce, or
easier to diagnose. Record-setting results are not required; careful negative
results and quality checks are valuable too.

The maintainer's reference lab uses Intel Arc Pro B70 GPUs. Work from Arc Pro
B50, B60, B65, B70, and other Intel Arc systems is welcome. Portable work from
other hardware may also be useful, but hardware-specific claims remain
community-reported unless they can be checked on matching hardware. A patch
tested here on B70 is evidence about B70, not independent confirmation of the
submitter's original hardware score.

## Before Opening An Issue, Discussion, Or Pull Request

Include, or link to, all of the following:

- GPU model, count, VRAM, and relevant interconnect details;
- OS, kernel, driver, compiler, and accelerator runtime versions;
- model name and exact revision;
- quantization and any draft/speculative model;
- engine/runtime and exact source commits;
- exact command and relevant environment variables;
- prompt, output, and context lengths, batch size, and concurrency;
- cold/warm/cache and speculative-decoding policy;
- quality gate, its outcome, and any known quality tradeoff;
- output metric definition, score, variance/repeats, and TTFT where available;
- result JSON and log paths or durable public links;
- the closest known-good run and exactly what changed.

Never include model weights, API keys, access tokens, passwords, private user
data, or other secrets.

## Pull Requests

Keep changes focused. Preserve successful and failed experiment evidence, and
do not silently replace an old result. Put chronological investigations in
`notes/`, source deltas in `patches/`, reasonable structured artifacts in
`data/`, promoted summaries in `results/`, active research in `experiments/`,
and runnable promoted recipes in `repro/`.

The Qwen 27B INT4 TP=2 lane is active. Do not move, rename, clean, rebuild, or
otherwise disturb its files, processes, result directories, or external vLLM
and XPU-kernel source trees unless the maintainer explicitly puts them in
scope. Treat any locally modified runtime tree as active until confirmed
otherwise.

By submitting a contribution, you represent that you have the right to submit
it and that it may be distributed under this repository's [LICENSE](LICENSE).
Identify code, data, or ideas derived from another source and preserve required
attribution. Do not submit confidential material or code whose license is
incompatible with this repository.

## Review And Verification

Review is manual and task-specific. There is no promise that a submission will
be run, merged, ranked, or submitted elsewhere. Maintainers may inspect a patch
without executing it, request more evidence, reproduce only part of a claim,
or decline changes that are unsafe, too broad, untraceable, or impractical to
validate.

Results must say which of these descriptions applies:

- **community-reported**: evidence supplied by a contributor but not
  independently reproduced here;
- **B70-tested**: the patch was exercised in the reference B70 lab, without
  necessarily reproducing the submitted score;
- **B70-verified**: the stated result and quality gate were produced in the
  reference B70 lab, either as maintainer work or an independent reproduction;
- **matching-hardware verified**: independently checked on the hardware class
  named by the result;
- **invalid or superseded**: failed validation or replaced by better evidence.

See [docs/contribution-verification.md](docs/contribution-verification.md) for
the review procedure. LocalMaxxing is a downstream publication target for
eligible, verified records; it is not the source of truth for this repository.

## Risk

Optimization patches can crash software, corrupt output, reduce model quality,
consume substantial power, or destabilize a system. Read [DISCLAIMER.md](DISCLAIMER.md)
and the [LICENSE](LICENSE). Use isolated environments and backups, review every
command, and assume responsibility for your own hardware, data, accounts, and
results.

# Contributor-reported benchmark

Everything in this directory is `community-reported`; it is source evidence,
not a reference-lab result.

The contributor posted the CSV in the discussion for
[PR #15](https://github.com/steveseguin/b70-optimization-lab/pull/15) on
2026-08-01. They described a `llama-benchy` run with a 2,048-token prompt,
1,024-token generation, context depths 0, 4,096, 8,192, 16,384, and 32,768,
five runs per test, concurrency 1, and `generation` latency mode. The attached
CSV reports 127.86-135.05 decode tok/s and 8,330-9,251 prefill tok/s.

The exact `llama-benchy` version and command, JSON output, immutable image
digest, model revision, and XPU graph environment were not posted. The PR
launcher defaults to `EAGER=1`, but the contributor did not preserve the
effective benchmark process or engine identity. It also did not pass a vLLM
`--speculative-config`; the additional `qwen36-35b-mtp` served name was only an
alias and did not enable MTP.

The original GitHub attachment's SHA-256 is
`36b9b376c4948a333797e3b1c211e392113245edda6225d098648f6e7b735483`.
The tracked copy is newline-normalized to LF and has SHA-256
`b14da3b712151522ffc60f3d80aa8a62349f42dcf9236364106594cf45a751f9`.

The reference lab reconstructed the closest recoverable workload and did not
reproduce the decode result. See
[`../STATUS.md`](../STATUS.md) and the
[`validation summary`](../validation/2026-08-02-llama-benchy-replication-summary.json).

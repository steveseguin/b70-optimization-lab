# 6a9c TP1 decision-overlay r1 closed after the diagnostic

Date: 2026-08-24. Status: **failed-incomplete; no promotion.**

The committed 6a9c TP1 decision-overlay r1 packet passed its fresh hardware
gate and its seeded-fresh diagnostic arm. The diagnostic passed every
non-quality gate and reached `30.268740193465128 tok/s`, above both its frozen
`30.2178 tok/s` floor and the retained `30.2569 tok/s` diagnostic high. The
historical high is not replaced: r1 never ran either natural-EOS strict replay
or the complete quality battery.

Immediately after the diagnostic, the wrapper found that the lab repository's
live `origin/main` had advanced from the frozen launch commit
`45386119b494ef1b71a9c92538a9fcc152a26ded` to
`b932c5d85a774f599b9ab5ee636d1756014fed1e` and stopped with:

```text
error: live lab origin/main changed during overlay qualification
```

That direct-child commit publishes separate Qwen3.6 concurrency evidence. It
changes four documentation/data paths and no Qwen3.8 packet, runner, image,
runtime source, protected ledger, model, cache, or decision payload. It cannot
have affected the completed measurement. The stop is nevertheless binding for
the preregistered r1 protocol. Do not resume, append to, overwrite, or relabel
either sealed r1 root.

## Completed evidence

The fresh hardware gate passed all 70 checksummed entries: four-device
identity and compute, peer read, four-rank XCCL all-reduce, coherent Torch
runtime, root-NVMe health, atomic lock handoff, clean postflight, kernel taint
0, and zero rejected or accepted corrected-NVMe events.

The seeded-fresh model arm directly and ordinarily verified all 19 model
files, returned exact canary content `14` with zero cached prompt tokens, and
completed 25/25 unique 512-token cache-zero rows. Its conventional 99-interval
statistics were:

- median `30.268740193465128 tok/s`;
- p10 / mean `30.221906402445327 / 30.331522718272012 tok/s`;
- minimum / maximum `29.643662356086395 / 30.828605542503922 tok/s`;
- standard deviation `0.22075334498778593 tok/s`;
- median TTFT `279.9858750004205 ms`;
- legacy inclusive median `30.574485043904172 tok/s`.

The exact decision seed stayed byte-identical before compilation, after
compilation, after the workload, and after shutdown at manifest SHA-256
`b941bb71c1d264dcd55104b106b2dff6a85c686776b072e0ef6cc18a8354c928`.
The fresh compile cache contains 497 regular files, including exactly 38
decision records, and 139 directories, with no symlink or special node. Its
file-manifest and directory-manifest hashes are respectively
`9f9f4e03dc3fb023ec66f983789834424e69bd0351b32e7502beae0a5113347e`
and `c27d308f3721467d344d89fa9fcee333bea20e9bddbac35603217d6d3c6b9298`.

All engine identities remained exact before and after the arm:

- vLLM `6a9c69fa851389dcf1ee5d3a2363e27af665d26d`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`;
- official nightly base
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- both-current image
  `sha256:f86c4c78d76a484f5d54eda310419c91a2471634ab97782022ef7573fc19a7d9`.

The sealed manifests reverify:

- hardware 70/70, manifest SHA-256
  `3432fc6536b36f02f086f34e55663f7515e6057c192b0c85320e73cefd3abb00`;
- frozen inputs 76/76, manifest SHA-256
  `db58dad8b6f5be7d26703abbd8652d2c8ead4d11e4599091e376c9b07e8bc5ca`;
- campaign evidence 161/161, manifest SHA-256
  `3098ab384aea4f76995498f8f8a83eb93732b4b61aa5e80dd4ee3df5d21f8196`.

Strict replay A, strict replay B, and an aggregate qualification result do not
exist. The container was removed, ports `19786`-`19788` are free, and no model
process or render-node holder remains.

## Disposition

R1 is a dated, quality-unqualified diagnostic observation. It is not a TP1
qualification, not a replacement for a protected speed, and not authorization
for TP2 or TP4. The full protected performance ledger remains byte-identical
at `e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`;
the preserved TP2 78-decision and TP4 152-decision artifacts are unchanged.

The engine upstream and nightly identities remained exact after closeout, so
no image rebuild is justified. The next useful action is a separately named
r2 packet using a new hardware root, result root, compile cache, and ports. R2
must require a clean pushed lab tree equal to live `origin/main` at launch and
must keep the local commit and every frozen input immutable throughout the
run. A later remote-only lab documentation push cannot mutate that running
identity and should be recorded rather than aborting a model arm; live vLLM,
XPU-kernel, and nightly identities remain hard gates after every arm.

The structured closeout is
[`2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.json`](../data/2026-08-24-qwen38-6a9c69fa85-tp1-decision-overlay-r1-live-lab-stale.json).

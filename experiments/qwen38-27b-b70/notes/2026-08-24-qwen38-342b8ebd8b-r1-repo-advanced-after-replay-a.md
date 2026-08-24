# 342b TP1 r1 closed after replay A

Date: 2026-08-24. Status: **failed-incomplete; no promotion.**

The committed 342b untreated TP1 r1 packet completed its fresh hardware gate,
zero-overlay diagnostic arm, and strict natural-EOS replay A on the exact
literal-current runtime. The diagnostic passed its frozen speed floor. Replay
A passed the complete quality battery and every runtime, cache, model, kernel,
and cleanup gate, but its conventional median missed the frozen strict speed
floor by `0.015124214751271 tok/s` (`0.049897%`).

Before replay B, the wrapper correctly noticed that the lab repository's live
`origin/main` had advanced from the frozen launch commit
`00fe74bf65c71291aec495b3e5bf499809451182` to
`2c2cbcac0ef314f9bec7ac6c97112a0f9fe1f3d9` and stopped with:

```text
error: live lab origin/main changed between untreated arms
```

That repository commit contains separate Ornith/Qwen3.6 experiment evidence
and does not change the frozen Qwen3.8 wrapper, 342b image, runtime source,
model, cache, or accepted overlays. It cannot have caused the measured speed.
The speed miss also did not cause the process exit; it is nevertheless a real
dated observation and means r1 could not have satisfied its two-replay speed
contract even if replay B had run.

Do not resume, append to, overwrite, or relabel this sealed root. It is not a
completed TP1 qualification, a regression that lowers a historical frontier,
or authorization for TP2/TP4.

## Completed evidence

The post-reboot hardware gate passed all 70 checksummed entries: four-device
identity and compute, peer read, four-rank XCCL all-reduce, coherent runtime,
root-NVMe health, atomic lock handoff, clean postflight, kernel taint 0, no
selector-plus-mask combination, and zero rejected or accepted corrected-NVMe
events.

Both completed model arms directly and ordinarily verified all 19 model files,
returned exact canary content `14` with zero cached prompt tokens, used the
same zero-overlay image, and preserved exact upstream identities before and
after each arm:

- vLLM `342b8ebd8bd4595826f29ff95dfc48679a03a95a`;
- XPU kernels `baaa05bb4e92901219a5a072dd63f2474896f6d1`;
- official nightly base
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- both-current image
  `sha256:6dbd46c8d22c3fdb425dfe343e759a89c5aa443eb99f411b4f6d923eae2e54ae`.

The 25/25-row cache-zero diagnostic produced these conventional 99-interval
statistics:

- median `30.337988469031558 tok/s`;
- p10 / mean `30.283437153987247 / 30.378515956172475 tok/s`;
- minimum / maximum `29.67952193420205 / 30.860105796017706 tok/s`;
- standard deviation `0.21184064675754022 tok/s`;
- legacy inclusive median `30.644432797001574 tok/s`.

It passed the frozen `30.2178 tok/s` diagnostic gate and observed
`0.081088469031557 tok/s` above the protected `30.2569` diagnostic high. The
observation remains dated support only; it does not replace the protected pair.

The 25/25-row natural-EOS, cache-zero strict replay A produced:

- median `30.295550825778708 tok/s`;
- p10 / mean `30.191009598981488 / 30.29248267570233 tok/s`;
- minimum / maximum `29.651227348441942 / 30.786147037031988 tok/s`;
- standard deviation `0.19056845424723054 tok/s`;
- legacy inclusive median `30.601566490685563 tok/s`.

Its seven objective exact canaries, eight-run one-hash repeat, 8K needle,
24/24 baseline comparisons, token IDs, cache-zero checks, and natural-EOS
metric policy all passed. The strict speed gate did not: the immutable floor
remains `30.31067504052998 tok/s`.

## Integrity and disposition

The compile cache contains 1,097 files and 158,509,855 file bytes. Its
diagnostic-post, replay-A-pre, and replay-A-post manifests are byte-identical at
`b359bbb32b062a3a1c0c125594180c844c5fc5132eabcb721740ead3e9c18a28`.

All sealed manifests reverify:

- hardware 70/70, manifest SHA-256
  `a2fa85a72bcc8b341ab7ccb1f845926d587f9cbdd109177a97778c33a32e436d`;
- frozen inputs 21/21, manifest SHA-256
  `e59808ec706239798ac6ba16f9c9503979e19e493743329245193de5c302e7dc`;
- campaign evidence 178/178, manifest SHA-256
  `307e6ccecfb4f7fe57bf20b8e5ff23cc6f5f801a80c8061e0915351eb2fdf69c`.

Replay B and an aggregate qualification result do not exist. Both containers
were removed, ports `19770`-`19772` are free, and no model server or render-node
holder remains.

An independent post-closeout freshness check at `2026-08-24T18:28:03Z` still
resolved 342b, baaa, and the same nightly digest. Therefore the next useful
step is a separately named, fresh-root r2 while those identities remain
literal-current. R2 must retain the exact diagnostic and strict floors, rerun
the entire hardware/diagnostic/A/B sequence, and prevent unrelated repository
writes during its atomic GPU window. If an engine upstream identity moves
first, archive 342b as dated evidence and rebuild the successor instead.

The accepted TP2 78-decision artifact and TP4 152-decision overlay remain
checksum-preserved, disabled, and unapplied. No historical speed changed. The
structured closeout is
[`2026-08-24-qwen38-342b8ebd8b-r1-repo-advanced-after-replay-a.json`](../data/2026-08-24-qwen38-342b8ebd8b-r1-repo-advanced-after-replay-a.json).

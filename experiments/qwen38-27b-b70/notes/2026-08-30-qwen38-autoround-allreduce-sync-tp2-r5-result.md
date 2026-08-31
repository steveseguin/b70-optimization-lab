# Qwen3.8 AutoRound INT4 TP2 all-reduce device-sync R5 result

Date: 2026-08-30

Status: **negative causal diagnostic**

Both fresh compiled arms passed direct model/image/file verification, the
complete cache-zero 12-prompt workload, independent canaries, and clean
shutdown. Adding a whole-device drain after every existing all-reduce
`Work.wait()` did not recover repeatability: sync-A and sync-B matched only
**5/12** complete token arrays.

Diagnostic class-balanced medians were `23.963917` and `23.826002` tok/s,
about 25% below the unsafe 31.8--32.1 tok/s compiled lane. Those speeds are
non-promotable.

Decision: reject the collective-completion boundary as a sufficient repair.
Do not retain the whole-device drain. The next causal screen disables the
currently forced GDN fallback so the native XPU GDN/persistent-scratch path is
actually exercised under MTP0.

Structured result:
[`../data/2026-08-30-qwen38-autoround-allreduce-sync-tp2-r5-result.json`](../data/2026-08-30-qwen38-autoround-allreduce-sync-tp2-r5-result.json)

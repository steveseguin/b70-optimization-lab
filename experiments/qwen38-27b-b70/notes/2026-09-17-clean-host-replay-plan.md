# Clean-host replay plan for the two FP8 packages (September 17, 2026)

Every FP8 package is still `candidate` because no replay has run on a host that is not the lab's two-B70 machine.
The four-B70 host (`steve-b70s`) is the cheapest place to change that: same cards, different CPU (Threadripper PRO
5955WX, 128 GiB), different driver history (upstream GuC 70.72.1), and it has never held these model files or images.

## What "published" needs (docs/recipe-publication-standard.md)

1. A machine that did not already hold the model, the image or a compile cache.
2. The package's own steps, in order, from an anonymous download of the repository at a pushed commit:
   `download-model.sh`, `verify.sh`, `docker pull` by digest, `serve.py start`.
3. The strict suite against the same-image no-MTP reference (12/12), the 64-prompt sequential oracle (64/64), a clean
   stop, health before and after, receipts frozen by `collect-fp8-tp2-acceptance-evidence.py` (two cards) or
   `fp8-gate-suite.py --freeze` (one card).
4. Independent-host driver installation is a separate, larger gate; it stays open until someone installs Intel's driver
   stack from scratch following only the package text.

## Steps on the four-B70 host

- Wait for the LTX lane to be idle and for that host's own fault latch to be cleared (it faulted on `0000:27:00.0`
  on September 16; the reset is the user's decision there too).
- `ZE_AFFINITY_MASK` selects two of the four cards for the two-card package and one for the one-card package; the
  launchers expect exactly two (two-card) or at least one (one-card) render device. On a four-card host the two-card
  launcher's device check needs a documented mask, which is the first thing the replay will show.
- Expect the four-B70 host to be slower per token (it replayed R139 at about 1.85x slower on both MTP0 and MTP1 on
  2026-09-02, attributed to host submission latency); identity is the gate there, speed is recorded separately.
- Run `run-fp8-tp2-acceptance-session.py --commit <sha>` (two cards) and the one-card equivalent through
  `fp8-gate-suite.py` against a one-card no-MTP reference generated on that host.

## After a pass

`clean_host_tested: true` in both manifests, status `published` in `repro/guide-catalog.json`, the
`publication-manifest.json` chain refreshed, and the "clean-host replay pending" label dropped from the site rows.

# K2 measured correctly, then failed in its own compression step (2026-10-12 15:59–16:03 UTC)

After the grid fix, K2 ran on card 0 in under four minutes: 14,400 fixtures and 178,762
adapter checks exact, the measured dispatch written ([selection](dispatch-measured.json),
[summary](summary.json), [table tail](k2b-table-tail.txt)); clean teardown and kernel
log. The wrapper then tried to compress the 979 MB raw fixture output and its own
storage admission refused: build tree 2.67 GB plus 0.98 GB reserve against a 3 GB cap.
`window.py` turns a retention failure into `passed: false`, so the windows after K2
could not use it. No latch was written.

The 3 GB cap came from the coordinator's brief (a disk-hygiene rule after the root
filesystem filled up that morning); it cannot hold K2's raw output next to its
compressed copy. Coordinator fix: cap raised to 6 GB in `storage.py`; the 8 GB
free-space floor on the root filesystem stays. Seal amended in `build-receipt.json`.
The raw `output.bin` of this attempt was removed (SHA-256 `f9058741…` in its native
receipt). K0, K1a, K1b and K2 are rerun under the suffix `c`.

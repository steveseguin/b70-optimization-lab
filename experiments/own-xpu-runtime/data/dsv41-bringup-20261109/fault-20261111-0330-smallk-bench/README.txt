2026-11-11 03:30:23 EST, card 0000:a3 (SYCL index 4): a one-card helper bench (bench_dotsff, smallk work on the
norm + stream-mix dot rows) wrote a fallback counter through a bad pointer (address 0): page fault, engine CAT
error, engine reset, timed-out job in bench_dotsff, devcoredump (devcoredump-card2.txt.gz came out empty). Our
software fault, not the card. Card sharing was kept: the six-card bisect bis88 ended (and removed six.active) at
03:30:04, 19 s before the fault, so no six-card run was on the cards. The helper fixed the pointer and three later
runs of the same bench were clean; the six-card tg88 rerun after it (traces from ~03:40) was clean on every card.
Health probe after tg88 (04:10, its own clean unit, scripts/check-qwen36-xpu-xccl-health.sh): rc 0, single-card
smoke on all six cards and the six-card all-reduce (health-probe-20261111.txt).

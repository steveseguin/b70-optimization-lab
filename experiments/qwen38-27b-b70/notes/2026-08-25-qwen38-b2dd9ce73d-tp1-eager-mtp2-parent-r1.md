# b2dd TP1 eager-MTP2 parent r1 closeout

Date: 2026-08-25. Classification: **passed corruption-sensitive and target
oracle parent; full MTP2 battery still pending.**

The frozen b2dd/1e90 Qwen 3.8 AutoRound INT4 TP1 eager MTP2/F16 parent booted
cleanly and passed its exact canary. Both preregistered sensitive prompts then
matched the qualified MTP0 eager control in output SHA-256 and complete token-ID
sequence. This directly clears the parent corruption/oracle gate for the exact
snapshot and profile.

Speculation was active and useful: metrics increased by 868 drafted and 589
accepted tokens, a `67.8571%` aggregate acceptance rate. The preferred
two-prompt decode median was `10.511166009554383 tok/s`. This deliberately small
screen is not a speed candidate; speed was non-gating and no protected value
changed.

The run also exercised the corrected Git policy. Live `origin/main` advanced
from `26477da59` to `8aeb13099` during the stage, while local `main`, the
worktree, image, source, inputs, and server identity remained unchanged. The
transition was recorded and correctly did not invalidate the run. Cleanup
passed and the terminal receipt SHA-256 is
`f7501bced81beefd52bf8b56a44c16be3d9ea861d7695fe884b4ba3b2cbcc14a`.

This parent fills no exact active-context cell and is not yet a full quality
packet. It unlocks the preregistered full 25-prompt MTP2 short battery. If that
is clean, exactly one eager MTP4 short actual becomes eligible; MTP1/MTP3 may
remain calibrated estimates unless an actual would change a site conclusion.

The structured closeout is
[`2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-parent-r1.json`](../data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-parent-r1.json).
Complete evidence remains under
`/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1/03-eager-mtp2/sensitive-screen`.

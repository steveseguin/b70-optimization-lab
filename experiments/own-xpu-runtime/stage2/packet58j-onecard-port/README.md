# Packet58j: one-card target kernel port

CPU preparation in progress. Based on frozen packet58g sources; no device run
or performance claim. Ports down-tile16, route-fast and rec-both-plus with
production and individual selectable views. Arithmetic remains
`iq3-p49-split32-v1`; target-only, full BF16 KV, 18 GB expert cache.

E1 is not admitted: its IQ2 scale expansion adds 616,038,400 pinned bytes
(47 layers × 2 banks × 512 experts × 640 rows × 20 bytes), exceeding
58g’s exact pinned allocation budget. No reserve or cache size is reduced.

Device work is plan-only, card 0 in a whole-host gap after the two-card chain.
Every model window must exclude lane B.

# Preregistration: A391 - does the eight-sequence server reproduce the single-user identity?

## Question

A390's single-user oracle rows differed from A383's on 3 of 8 prompts although both heads compute one
row identically. Every many-users arm so far compared concurrent outputs with an oracle generated on the
same server; none checked that the eight-sequence configuration (`max_num_seqs=8`, capture sizes
[1, 2, 4, 8], the wider placement) reproduces the certified single-user stream, or reproduces itself
across servers. Does it?

## Arm

A391: the A383 packet (head `2a372e86`, USERS:8, KV 1,412,136,960, max-count-2 placement) with a 6 GB
host floor, port 20008. Driver `tools/q38-repro-driver.sh`: two exact-2K rows through the depth harness
(the certified pin `afffd211…`), then the concurrency oracle at concurrency 1 twice on the same server
(each pass regenerates the 8 sequential oracle rows). Queued after A390.

## Gates and predictions

- Pin: both exact-2K rows must be `afffd211…`. If they are, the eight-sequence configuration preserves
  the certified single-user identity for that row.
- Within-server: pass 2's oracle rows must equal pass 1's for all 8 prompts.
- Across servers: pass 1's rows compared with A383's and A390's oracle rows. If the rows equal A383's
  (same head) and differ from A390's, the cherry-picked head changed one-row arithmetic after all and
  `dc11a3a0a` is retired with a code reading; if they differ from A383's too, the eight-sequence server
  is not cross-server reproducible at one user, the multi-user divergences are partly server variance,
  and the lossless many-users question moves to a `max_num_seqs=1` comparison design.

## Stop rules

Server fails health; a row fails; either gate fails is a result, not a stop.

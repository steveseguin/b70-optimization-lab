# Preregistration: A394 - fresh-server repeat of the exact-mode MTP1 32K ladder

## Question

The exact-mode MTP1 line's 32K cell (A382) rests on one server. Does a second server reproduce the four
depth hashes (`afffd211…`, `0126d542…`, `789cbcb8…`, `1cc1699e…`) and rates, the cross-server condition
the certified 4K line already meets (A365/A366)?

## Arm

A394: the A382 packet regenerated (head `6d872457`, stage v2, exact-mode exports, MAX_MODEL_LEN 33280, KV
1,341,530,112, never-hit + max-count-2 placement) with a 6 GB host floor (A382's trough was 8.08 GB
against an 8 GB floor) and the supervisor's cached-receipt xpu-smi bypass; port 20011; the same
four-depth ladder, two rows per depth. Queued after A393.

## Gate and predictions

Every depth's ids equal A382's (and so A381's); rates within noise of 47.3 (2K warm) / 42.7 / 45.6 /
44.1 tok/s. A pass upgrades the family entries' evidence to two servers and is the last lab step before a
certified long-context battery (a frozen client with these pins) could be written.

## Stop rules

Server fails health; a row fails; any depth's ids differ (recorded, the cell's promotion path stops).

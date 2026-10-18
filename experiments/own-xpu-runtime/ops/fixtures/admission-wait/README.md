Synthetic minimal replay of hourly review 24b (not a performance measurement).
The monotonic epoch is 2026-10-18 13:00 UTC, at 100 ticks/second.
The chain service spans 13:10–14:09. W2m reserves at 13:37, enters admission
at 14:03, and runs device children from 14:03. The last proven work ends at
14:05; drain completes at 14:07. Neither drain nor service exit proves the
device exit time. Expected accounting: 26 minutes `idle_admission_wait`,
two minutes evidenced device occupancy, no credit for the wrapper tail.

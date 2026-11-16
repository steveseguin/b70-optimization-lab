# st1: bounded stability test in the SMT-off diagnostic configuration (2026-11-15 16:52, STOPPED by a host reset)

Configuration (checked by `stable/preflight.sh` before every case, never changed by the test): SMT disabled in the BIOS
(Codex, boot 15:09), the six GPU root links at Gen4 x16, `OWN_PX_SERIAL=1` (tp115 default), default power limits,
BIOS 11.02. Binary `own_run_v41_tp115` (sha256 45f72213174a60c2). Script `st1.sh`: a fresh model start per case,
both prompt head layouts, every output checked against its reference, logs synced after every line, a synced
kernel-log follower; first fault / mismatch / non-zero exit = STOP, no retry, reset or reboot.

## Outcome

4 fresh starts passed, all outputs the same as their references (`summary.txt`):

| case | prompt read | writing after it |
|---|---|---|
| 3K, heads 3,3,3,3,2,2 (default) | 4.93 s (682.0 tok/s) | 98.62 tok/s |
| 3K, heads 4,2,2,4,2,2 | 5.82 s (572.2 tok/s) | 100.45 tok/s |
| 10K, heads 4,2,2,4,2,2 | 18.44 s (576.7 tok/s) | 95.48 tok/s |
| 10K, default | 15.55 s (684.3 tok/s) | 98.89 tok/s |

Case 5 (34K, default heads) started 16:55:08; at 16:56:26 the host reset during prompt reading. The synced follower
caught the start (`reset-20261115T1656-NOTES.txt`): GPU e3:00.0 (card 5) GuC crash + exception, its reset failed
(GRDOM_FULL timeout), card declared wedged; 0.7 s later the bridge of GPU a3:00.0 (card 4) "device inaccessible",
then its registers read 0xFFFFFFFF; then the fatal reset (CPU bank 5 core watchdog, FRU text "Perr S0:T00A:B05").
Neither card is on the MCIO cables. The machine is not fixed; the cause is not established.

## Speed finding

The 4,2,2,4,2,2 head layout is **16-18 % slower** for prompt reading in the stable mode (3K +18 %, 10K +19 % time);
closed for prompts. Writing after it is within noise.

# Hourly time-efficiency review log

Owner mandate 2026-10-17 ("WE NEED TO MOVE WITH URGENCY"). Brief: `HOURLY-TIME-REVIEW.md`; helper: `gpu_time_review.py`. Trigger: hourly at :47 (session cron) plus one immediate run.

Baseline before the first review (last 12 h, 02:22-14:22 UTC): device units in flight 65%, but only **29%** after excluding model queues that sat waiting on the CPU oracle. Idle gaps of 72 min (12:12-13:25) and about 1 h total from 02:22 to 05:11. Cards 2+3 were used about 25 min.


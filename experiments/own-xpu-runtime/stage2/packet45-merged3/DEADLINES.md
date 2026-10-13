# Packet45 bounded windows

Every wrapper refuses a watchdog when the expected duration plus 17 seconds exceeds one quarter of it, or when it is below 300 seconds. The maximum is 172800 seconds. This is prelaunch admission; an optimistic estimate does not stop a healthy running owner early. No failed child is retried. Cooperative stop retains ownership and failed evidence.

K2 uses six to eight explicit QSA lengths for each allocation capacity. Its conservative estimate includes the packet45 candidate additions and the long stable-selector quadratic cost. These are reservations, not measured speed.

| Context capacity | K2 estimated seconds | Estimate +17 | Minimum watchdog seconds | Coordinator watchdog |
| ---: | ---: | ---: | ---: | ---: |
|256|485|502|2008|14400|
|4096|555|572|2288|14400|
|32768|2867|2884|11536|14400|

`k2_summary.duration_plan` is the executable authority; its exact finite length grids and estimate are written to receipts. The 32768 plan exceeds the old 10800-second watchdog quarter and therefore requires the new 14400 setting. WINDOW.md and coordinator_windows.sh use 14400 for each capacity.

The inherited reservations are K0/W0p 30 seconds with 600-second watchdog; K1a/K1b 120 with 10800; KD 1800 with 10800; W2m 2100 with 10800; WS/WSs 7200 with 30000 per repeat. Packet40's explicit 128-token speed/exactness aliases reserve 14400 with 60000 per repeat. Suite repeat multiplication is checked before launch.

CPU preparation uses nice19, idle I/O, preserved affinity, OMP_NUM_THREADS at most 2, at most two compile jobs/four CPU-bound processes and aggregate anonymous memory below 10 GB. Root free space below 8 GB refuses writes; packet build storage is capped at 3 GB. Completed fixture scratch is removed after its verified receipt/archive. Raw trace/event text is compressed and hash-bound.

# Qwen3.8 TP2/MTP1 strict D70 first-request device loss

Date: 2026-08-31

D70 passed direct model verification, exact startup accounting, and API
readiness with projection repair enabled and bypassed for dummy runs. The first
strict `incident-retrospective` streaming request received HTTP 200, then rank 1
lost its device asynchronously before a complete response or benchmark row was
written. The later GDN metadata traceback is where the queued loss surfaced,
not proof that metadata construction caused it.

The server log retained exactly 1,040 decoder begin/pass receipts, confirming
no request executed the profile-only diagnostic barriers. The timestamp-bounded
kernel log contains 513 unsuccessful Xe fault responses, seven CAT errors, and
one reset. The benchmark was stopped after the device loss was conclusive;
attempt exit 130 reflects bounded cleanup, not a user cancellation. No prompt
completed and no performance, output-parity, or quality result exists.

A post-teardown 512x512 matrix health probe on GPU0 then hung and added a BCS
fault/CAT error, so the next run is forbidden until a host reboot and
independent compute gates pass. D71 enables the projection hook's existing
synchronization only around the real medium-prefill repair operations. Those
barriers do not execute on dummy runs or decode rows. The strict oracle and all
quality rules remain unchanged.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-dummy-repair-bypass-strict-20260831-d70/`.

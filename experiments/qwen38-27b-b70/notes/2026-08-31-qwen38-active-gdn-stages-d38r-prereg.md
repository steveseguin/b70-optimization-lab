# Qwen3.8 active packaged GDN stage trace D38r preregistration

Date: 2026-08-31

Status: **preregistered before D38r model requests**

D38 returned an empty response and lost the post-request exception because of
a runner fail-path defect. D38r repeats the exact D38 hook and packaged image
under a new campaign after changing only the runner's missing-trace branch to
save `docker logs` before cleanup. The first process is the immediate gate. If
the hook fails, preserve and diagnose its traceback; do not continue to four
processes. If it succeeds, complete the frozen four-process comparison.

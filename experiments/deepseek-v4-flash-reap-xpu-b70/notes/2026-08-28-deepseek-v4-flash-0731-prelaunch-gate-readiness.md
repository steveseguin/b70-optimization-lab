# DeepSeek V4 Flash 0731 prelaunch gate readiness

Date: 2026-08-28

Status: CPU-side launch and qualification gates ready; no GPU arm launched

The complete 0731 REAP artifact and its revision-specific DSpark draft pack
were already validated. This change closes the remaining tooling blocker
before the first target-only GPU canary. It makes no speed, quality, loading,
or compatibility claim.

The base TP4 launcher now emits unique, complete identity rows. The duplicate
`ld_preload` row was removed, and previously invisible frozen values for the
256-expert fallback, router limit, target device, Python/vLLM entry points,
kernel binary, preflight receipt, library path, and absent communication
selectors are recorded. These are report-only changes; the runtime environment
and vLLM argument sequence are unchanged.

`verify-0731-endpoint-binding.py` rejects any endpoint that is not the exact
pinned 0731 target-only recipe. It checks the complete identity-key contract,
pinned artifact/validation hashes, exact 256/256 smoke or 2048/2048 full
context, current runtime-file hashes and source heads, the live process
environment, exact launch arguments, current boot/PID/start time, literal IPv4
loopback address, one unambiguous listener owned only by the attested process
tree, isolated cache/run paths, and an unchanged baseline between request
phases. Reports are created without overwrite.

`qualify-0731-reap-target-endpoint.sh` now uses a private unique attempt
directory and exclusive run lock. It takes binding receipts before and after
the endpoint query, exact canaries, quality corpus, realistic 512-token suite,
and post-suite exact canaries as applicable. A pass summary is written last and
only when every binding and quality gate remains continuous.

The default launcher remains the preregistered 256-token smoke arm. A separate
`serve-0731-reap-tp4-target-full.sh` selects the 2K qualification arm so the
first launch cannot silently become a larger-context run.

CPU-side verification passed:

- 9 endpoint-binding and launcher-contract tests;
- 3 full-artifact verifier tests;
- 10 exact-canary scorer tests;
- 9 quality-capture scorer tests;
- Bash syntax, Python compilation, and `git diff --check`.

The current host remains below the frozen 105-GiB `MemAvailable` recovery
threshold documented by the Flash-Next recovery closeout. That policy permits
no further reload or lower floor; the next GPU action requires a user-authorized
host reboot. Until then, no DeepSeek endpoint, container, or GPU benchmark is
started.

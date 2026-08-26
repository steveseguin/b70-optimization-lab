# TP1/MTP2 PIECEWISE sentinel cache-gate correction

The exact-4K run launched from commit `5dd48073b0c010bb94446a524bbc812eb68854db`
and its original runner SHA-256 was
`09df24edf416a04886b3e3aca0cda3e4dced47351e9dfd77d51047ba0e597e79`.
The preregistration promised cache-isolation evidence, but that runner neither
emitted a cache receipt nor enforced a cache gate. Its terminal state is
therefore not treated as sufficient by itself, despite its zero exit status.

The dedicated cache root survived unchanged after cleanup. A separate,
report-only audit hashed its complete 1,370-file, 173,190,178-byte contents and
observed exactly one TP1 namespace, `rank_0_0`, containing six rank-scoped
files. The full content manifest SHA-256 is
`a90d8cea73ebbaab5e3d474248f2d12f06ff8dad856bdb675494de40adf49e55`;
the transparent audit receipt SHA-256 is
`545030d1cc4adada3cea4fe62f2f3dd20950e9ded277cd6cfce87f4b8b5dafc3`.
Both live beside the raw run as `postrun-cache-files.sha256` and
`postrun-cache-isolation-audit.json`. The audit explicitly says it is post hoc,
does not rewrite the original terminal or measurement, and cannot authorize
publication by itself.

The tracked runner is corrected forward to emit `rank-cache-isolation.json`,
require exactly `rank_0_0`, fail closed on the cache gate, and carry the result
into its arm receipt. Its static test now requires those implementation tokens,
so repeating this omission causes the packet tests to fail before launch. Git
history and the launch receipt preserve the exact original runner.

Any compact result or family publication for this run must disclose the
post-run audit and remain an explicit one-cell human adjudication. It may not
claim that the original terminal enforced the missing gate, clear other MTP2
depths, or replace any protected result.

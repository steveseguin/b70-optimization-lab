# Corrected readable-output worker campaign

Nine attempts are preserved: five original issues, two new held-out issues and
two confirmations. All five original issues and both confirmations passed stable
automatic acceptance and independent agent patch review. Both new issues failed.
Human approval is pending and all generated patches remain unmerged.

See the [result note](../../overnight-2026-09-14-results.md),
[summary](summary.json), [manifest](manifest.json), [archive](evidence.tar.gz),
[patches](patches/) and [reviews](reviews/). The separate
[initial screen](../2026-09-14-profile-screen/README.md) preserves the failed
first readable attempts and rejected thinking-profile patch.

The archive contains 1,712 members with SHA-256
`a0c120d4a3ecc9b02512a54390249a4e3d66de3d206c44a9834729215f2e7ff9`.
It freezes the exact harness and v1 acceptance fixtures used for these runs.
Later CPU safeguards do not retroactively alter this campaign. Source copies
and weights are excluded; public source commits and archive/tree hashes remain.
Service logs are timestamped live captures, not stopped-server postflight.

From the repository root:

```bash
python3 worker/collect_overnight.py --verify --out experiments/local-coding-worker/data/2026-09-14-readable-observations
```

This verifier checks hashes and reconstructs results from retained evidence. It
does not execute archived source, replay commands or send model requests.

# Contributor-reported source material

These files preserve the exact PR #18 submission from `dominick253`.

- `exact-contributor-launcher.sh` is intentionally non-executable. It uses an
  unpinned image tag, privilege, host networking/IPC, container replacement,
  automatic restart, and remote model code.
- `benchmarks/` contains the original raw JSON/CSV, scripts, summaries, and
  interpretation. The original MTP-on and MTP-off workloads do not match in
  output length or repeat count, so the claimed treatment ratios are retained
  only as contributor-reported observations.

Use the hardened launcher and corrected benchmark wrapper in the packet root.
Maintainer review lives under `../validation/`.

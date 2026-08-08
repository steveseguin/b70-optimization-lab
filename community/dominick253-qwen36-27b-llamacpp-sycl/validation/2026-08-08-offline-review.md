# Maintainer offline review — 2026-08-08

This file records the pre-device review. A later same-day device run raised the
packet to `B70-tested`; see
[`2026-08-08-reference-lab-validation.md`](2026-08-08-reference-lab-validation.md).

## Scope

This review covers `dominick253` PR #19 at
`22c1bea916c5ae2e8c6f8eaff84c3e4e2e0a200d`. No model, container, GPU,
service, endpoint, systemd unit, or contributor host was accessed. The evidence
level remains `community-reported`.

The final contributed launcher and historical table are preserved under
`reported/` and are non-executable. The packet-root launcher is a
maintainer-produced fail-closed surface.

## Offline checks

- Reviewed all four contributor commits and the complete resulting packet.
- Confirmed that the launcher changed from 150,000 to 160,000 and then 175,000
  context without a matching raw runtime artifact, while the retained live
  inspection claim still says 150,000.
- Parsed every shell script with `bash -n` and dry-ran the hardened launcher.
- Confirmed that context, model hash, server-binary hash, llama.cpp commit,
  device, port, and host are validated before non-dry execution.
- Confirmed loopback-only publication and rejected a non-loopback dry run.
- Checked local links, file modes, symlinks, text controls, credential-like
  patterns, and Git whitespace.

## Findings and limits

The historical Markdown table has no raw JSON, CSV, output, or log behind it.
It describes greedy temperature 0.0 and draft widths 1 or 2, while the reported
service uses temperature 0.6 and draft maximum 2. It is useful community history
but cannot validate the final service identity or support promotion.

The contributed packet lacks the GGUF revision and SHA-256. It also does not
establish whether 150K or 175K was the exact live context. The hardened launcher
therefore has no context default and requires the chosen model and server
binary hashes. For non-dry execution it also checks the reported clean
llama.cpp source commit.

## Disposition

Safe to merge as an isolated, credited community recipe with unresolved
identity fields clearly marked. A future run must choose one context, pin the
GGUF and server binary, and retain raw matching quality and benchmark artifacts.

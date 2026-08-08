# Maintainer offline review — 2026-08-08

## Scope

This review covers the files contributed by `dominick253` in PR #18 at
`1604d0b1d444f47c58c1abedd88d879908425b21`. No model, container, GPU,
service, endpoint, journal, or contributor host was accessed. The evidence
level remains `community-reported`.

The submitted launcher and evidence are isolated under `reported/`. Every file
there is non-executable. The packet-root launcher and the verifier in this
directory are maintainer-produced surfaces; they are not represented as the
contributor's measured command.

## Offline checks

- Parsed all 11 contributed JSON artifacts with `jq`.
- Parsed all shell scripts with `bash -n` and checked all Python files with
  Ruff. The maintained verifier also passes `ruff format --check`.
- Ran `verify-reported-evidence.py` normally and with `python3 -O`. Both paths
  recomputed the three sweep hashes and means, 495 reported requests, summary
  aggregates, quality-artifact hashes, and 11,024 reported completion tokens.
- Copied the reported evidence to a temporary directory, changed one raw JSON
  identity field, and confirmed that the maintained verifier rejected it.
- Dry-ran the hardened launcher and confirmed loopback publication, digest and
  revision pinning, and the absence of privilege, host network/IPC, seccomp
  disablement, persistence, automatic replacement, or remote model code.
- Confirmed that mutable-image and malformed-input cases fail before execution;
  the rendered publication address remains fixed to loopback.
- Checked local links, file modes, symlinks, text controls, credential-like
  patterns, and Git whitespace.

## Findings and limits

The submitted benchmark and quality files are internally consistent with one
another. This is an arithmetic and integrity result about the submitted files,
not independent authentication of the machine, workload, traffic, or journal.

The original verifier uses Python `assert`, so `python3 -O` removes its gates.
It also assumes its old pre-isolation path. It is retained unchanged for
provenance; the maintained fail-closed verifier is the supported offline check.

The original monitor treats journal-read failure as a zero fault delta. The
submitted `697 -> 697` observation therefore remains contributor evidence and
is not accepted as a maintainer no-fault result. Likewise, the long-output
detector is a useful bounded corruption check, not semantic or target-token
equivalence.

## Disposition

Safe to merge as an isolated, credited community packet. Do not promote the
throughput or quality claims to `results/`, `repro/`, or LocalMaxxing without a
new reference-lab run and the quality gates listed in the packet README.

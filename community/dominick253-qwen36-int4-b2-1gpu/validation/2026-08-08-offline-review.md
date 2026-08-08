# Maintainer offline review — 2026-08-08

## Scope

This review covers the Qwen3.6 27B/35B INT4 portion of `dominick253` PR #18 at
`1604d0b1d444f47c58c1abedd88d879908425b21`. No model, container, GPU,
service, endpoint, or contributor host was accessed. The evidence level remains
`community-reported`.

The exact submitted launcher, benchmark scripts, raw files, and interpretation
are preserved under `reported/` and are non-executable in the integrated tree.
The packet-root launcher and `tools/` wrapper are maintainer corrections.

## Offline checks

- Parsed all four contributed benchmark JSON files and recomputed every stored
  metric mean from its raw values.
- Confirmed from raw shapes that the MTP-on files use 1,024 output tokens and
  five samples, while the MTP-off files use 512 output tokens and three samples.
- Parsed every shell script with `bash -n` and checked the changed Python
  surfaces with Ruff.
- Dry-ran the hardened launcher and confirmed digest pinning, loopback-only
  publication, a read-only model mount, and no privilege, host network/IPC,
  persistence, container replacement, or remote model code.
- Confirmed that mutable-image, non-loopback benchmark, unsafe model-name, and
  malformed-input cases fail before execution.
- Preserved the submitted CSV blobs as reported evidence and marked only that
  directory as binary in Git, preventing line-ending cleanup from rewriting
  contributor artifacts.
- Checked local links, file modes, symlinks, text controls, credential-like
  patterns, JSON parsing, and Git whitespace.

## Findings and limits

The raw benchmark means are internally consistent, but the submitted MTP
comparison is not a controlled A/B. Output length, sample count, and date differ
between treatment arms. The reported ratios remain useful observations; they
are not evidence that speculation alone caused the difference.

The submitted 35B CSV wrapper reads a nonexistent top-level `results` key even
though the stored llama-benchy JSON uses `benchmarks`. The maintained wrapper
fixes the key and adds loopback, port, filename, and no-overwrite guards. It was
syntax- and guard-tested only; no endpoint benchmark was run.

The submitted image is a mutable tag and model revisions are missing. The
hardened launcher therefore requires an explicit digest-pinned image and local
model directory, and checks that the directory contains config and weight
files before non-dry execution.

## Disposition

Safe to merge as an isolated, credited community packet. Do not use the MTP
ratios as a shipping rule, promote the 35B failure into a general model claim,
or publish either result to LocalMaxxing without matched reference-lab evidence.

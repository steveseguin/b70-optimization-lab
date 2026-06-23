# Local Friction Fixes And Safe Follow-Ups

Created: 2026-06-20

Scope: small local environment frictions found while working on the B70/Qwen
research lane. This file is intentionally conservative: it separates fixes
that are safe to apply immediately from items that should stay as runbook or
stack-matrix work.

## Fixed Now

### `python` command missing

Problem:

- `python` was not on `PATH`.
- `python3` was available as `/usr/bin/python3`.
- Several repro and helper scripts invoke `python` after activating a venv, and
  one script still used `#!/usr/bin/env python`.

Fix applied:

- Added a user-local symlink:
  `/home/steve/.local/bin/python -> /usr/bin/python3`.
- Verified:
  - `python --version` -> `Python 3.12.3`
  - `python3 --version` -> `Python 3.12.3`
  - `python -c 'import sys; print(sys.executable)'` ->
    `/home/steve/.local/bin/python`
- Updated `scripts/check-gdn-spec-recurrent-exact.py` from
  `#!/usr/bin/env python` to `#!/usr/bin/env python3`.

Why this is safe:

- `/home/steve/.local/bin` is already early in `PATH`.
- This does not modify system packages.
- Activated virtualenvs still normally put their own `bin` directory ahead of
  `/home/steve/.local/bin`, so venv-local `python` remains preferred inside a
  venv.

## Checked And OK

- `pip` and `pip3` are present and point at Python 3.12.
- `uv` is present: `0.11.16`.
- `gh` is present: `2.92.0`.
- `jq` is present: `1.7`.
- `xpu-smi` is present: CLI/service `1.3.6.20260210`, Level Zero `1.28.2`.

## Frictions Found But Not Auto-Fixed

### Global oneAPI `setvars.sh` is still unsafe under `set -u`

Observed:

- Running `source /opt/intel/oneapi/setvars.sh --force` under `set -u` exits
  with:
  `OCL_ICD_FILENAMES: unbound variable`.
- Prior local notes also say not to source umbrella oneAPI `setvars.sh` for
  vLLM serving because oneAPI library precedence caused XCCL/SYCL startup
  crashes in accepted lanes.

Why not fixed globally:

- Sourcing oneAPI globally would change `PATH`, `LD_LIBRARY_PATH`, SYCL, and UR
  resolution for every shell and could invalidate benchmark identity.
- The accepted vLLM launchers intentionally keep venv and PyTorch libraries
  first.

Low-risk follow-up:

- Keep oneAPI sourcing inside build-only wrappers.
- When a wrapper must source oneAPI under strict shell mode, use `set +u`
  around the source call and restore `set -u` after it.
- Prefer targeted compiler envs such as
  `/opt/intel/oneapi/compiler/2025.3/env/vars.sh` for SYCL-8-compatible local
  extension builds instead of the umbrella latest `setvars.sh`.

### `sycl-ls` is not available by default

Observed:

- `sycl-ls` is not on the default `PATH`.
- After sourcing `/opt/intel/oneapi/compiler/2025.3/env/vars.sh`, `sycl-ls`
  resolves to `/opt/intel/oneapi/compiler/2025.3/bin/sycl-ls`, but it reports
  `No platforms found` in that narrow compiler-only environment and warns that
  direct `vars.sh` does not set up all dependencies.

Why not fixed globally:

- Adding oneAPI compiler paths globally would reintroduce the runtime-library
  precedence risk above.

Low-risk follow-up:

- Add a build-only helper later if needed, for example a wrapper that sources
  the exact compiler env, sets only the dependency libraries needed for the
  probe, runs `sycl-ls`, then exits without modifying the parent shell.

### Hardware-counter tooling is absent

Observed:

- `unitrace`, `oneprof`, and `vtune` are not on `PATH`.
- No matching binaries were found under `/opt/intel/oneapi`.
- `apt-cache policy` shows `intel-oneapi-vtune` is available from Intel's apt
  repo, but it is not installed.

Why not fixed now:

- Installing profiling tools is a package change, not a local shell fix.
- VTune/unitrace can affect permissions, kernel modules, collection overhead,
  and benchmark identity.

Low-risk follow-up:

- Treat profiler installation as a deliberate stack/tooling task.
- Prefer a separate "profiling lane" rather than installing into the accepted
  serving lane mid-experiment.

### Level Zero loader state has drifted from older notes

Observed:

- Current package owner for `/usr/lib/x86_64-linux-gnu/libze_loader.so.1` is
  `libze1:amd64`.
- Current package version is `libze1 1.28.2-1~24.04~ppa1`.
- `apt-mark showhold` did not show Intel/XPU/Level Zero holds.
- Older local notes described a no-file held `libze1` shim.

Why not fixed now:

- The current loader is functional enough for `xpu-smi`, and changing Level
  Zero packages is exactly the kind of action that can break PyTorch/vLLM XPU.
- This should be handled through the stack matrix, not as a convenience fix.

Low-risk follow-up:

- Update any stale runbook text only when the current accepted runtime lane is
  being refreshed.
- Keep `libze1`, `libze-intel-gpu1`, compute-runtime, IGC, GMM, PyTorch,
  Triton-XPU, and vLLM versions recorded together.

### `xpu-smi` telemetry can be intrusive

Observed from existing notes:

- Live per-device `xpu-smi` polling previously caused vLLM shared-memory wait
  warnings and had to be killed.
- Some useful EU/bandwidth metrics require elevated MEI access and currently
  report `N/A`.

Why not fixed now:

- This is measurement policy, not a command availability issue.

Low-risk follow-up:

- Use one-shot or low-rate telemetry beside endpoint runs.
- Keep high-frequency telemetry out of accepted throughput runs unless it is
  part of a dedicated profiling lane.

## Safe Next Fix Candidates

1. Add a local B70 stack-canary script from
   `pytorch-sglang-platform-audit-2026-06-20.md`. This should run before
   endpoint tests and record Python/PyTorch/XPU memory/device basics.
2. Add a build-only oneAPI helper that makes compiler-env sourcing explicit and
   avoids leaking oneAPI runtime paths into vLLM serving shells.
3. Add a low-rate `xpu-smi` snapshot helper that avoids live per-device polling
   during timing-sensitive endpoint runs.
4. Update stale documentation about the old no-file `libze1` shim when the next
   stack refresh happens.

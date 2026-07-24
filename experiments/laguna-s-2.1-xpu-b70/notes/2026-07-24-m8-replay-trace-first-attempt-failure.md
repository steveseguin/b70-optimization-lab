# Laguna M8 replay trace first-attempt failure

Date: 2026-07-24 America/Toronto

Status: **failed closed before generation; root sealed and ineligible**.

## Root

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-replay-trace-1c075d7e5-b1cca4129-20260724T231210Z
```

Supplemental parent PTI output that PTI wrote in the vLLM launch directory and
which was then moved to a fresh sealed NVMe root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-replay-trace-1c075d7e5-b1cca4129-20260724T231210Z-supplemental/unitrace.478235
SHA256 e508c9268ba614fce1267b8b032c5e4689d1b5b7884af1abd819380a0f28a83a
```

## Failure

The target and DFlash manifests passed, all four workers loaded the exact
models and frozen kernel stack, and eager initialization completed. The driver
then attempted to resume the paused PTI session before its sole generation.
The control command returned zero and emitted the required resume
acknowledgement, followed by:

```text
[INFO] Log is stored in unitrace.<child-pid>
```

The first driver required byte equality to the acknowledgement alone, so it
failed closed with:

```text
Laguna M8 replay trace arm: unitrace resume acknowledgement drifted: returncode=0
```

The appended line is deterministic PTI provenance created because the resume
command is itself a child of a process launched with default child following.
A separate non-model reproduction confirmed exactly two stderr lines, empty
stdout, and return code zero. The many 292-byte `unitrace.<pid>` files in the
failed root are likewise expected paused child summaries with no device time.

No `driver.json` exists, no generation began, the graph arm did not run, and
no performance or correctness conclusion is permitted. Workers shut down
cleanly and the root was sealed. Its private `m8rt-eager` RPC directory and
the never-used `m8rt-graph` reservation remain sealed and are not reused.

## Authorized repair

The retry may:

- accept exactly the required temporal-control acknowledgement followed by
  exactly one PID-shaped PTI provenance line;
- retain and inventory paused auxiliary child summaries while requiring
  exactly four worker traces with positive host, device, and submission totals;
- allocate fresh `m8rt2-eager` and `m8rt2-graph` RPC bases;
- use vLLM descendant `7118fa20d4e0b606abc764bf4984c6f701ac14dc`,
  whose only change after the first trace hook is the same strict two-line
  acknowledgement rule.

No model, arithmetic, selector, prompt, trace window, or exactness rule changes.
